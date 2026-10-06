"""Review saved cluster traces and arrival-cutoff features without model tuning."""
import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
import joblib
import numpy as np
from incidentlab.live_monitor import aggregate,score


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def review(directory,rescore=False):
    report=read(directory/'report.json')
    bundle=joblib.load(directory/'native_monitor.joblib')
    training=read(directory/'healthy_train/windows.json')
    model_review={}
    for service,fitted in bundle['services'].items():
        values=np.asarray([r['features'] for r in training if r['service']==service and r['count']])
        used=Counter(int(f) for tree in fitted['model'].estimators_ for f in tree.tree_.feature if f>=0)
        model_review[service]=dict(training_feature_min=values.min(axis=0).tolist(),training_feature_max=values.max(axis=0).tolist(),
            feature_names=list(bundle['features']),split_counts_by_feature={bundle['features'][f]:n for f,n in used.items()},
            ml_threshold=fitted['threshold'],latency_limit_ms=fitted['latency_limit'],error_fraction_limit=fitted['error_limit'])
    phases=[]
    for trial in sorted(directory.iterdir()):
        if not trial.is_dir() or not (trial/'schedule.json').exists():continue
        schedule=read(trial/'schedule.json')
        events=[]
        for service in ('frontend','checkout','inventory'):
            events.extend(json.loads(line) for line in (trial/f'{service}.jsonl').read_text().splitlines() if line)
        clients=[json.loads(line) for line in (trial/'client_requests.jsonl').read_text().splitlines() if line]
        predictions=read(trial/'predictions.json')
        rows=read(trial/'windows.json')
        spans={e['span_id']:e for e in events}
        by_trace={}
        for e in events:by_trace.setdefault(e['trace_id'],[]).append(e)
        children=[e for e in events if e['parent_span_id']]
        links=[e for e in children if e['parent_span_id'] in spans and spans[e['parent_span_id']]['trace_id']==e['trace_id']]
        incomplete_success=[]
        for c in clients:
            if c['status']!=200:continue
            captured_services={e['service'] for e in by_trace.get(c['trace_id'],[])}
            missing={'frontend','checkout','inventory'}-captured_services
            if missing:incomplete_success.append(dict(trace_id=c['trace_id'],missing_services=sorted(missing),client_start=c['start'],client_end=c['end']))
        feature_mismatches=0
        decision_mismatches=0
        maximum_score_difference=0.0
        late_events=0
        snapshots=[]
        with closing(sqlite3.connect(trial/'capture.sqlite3')) as db:
            snapshots=[json.loads(r[0]) for r in db.execute('SELECT payload FROM snapshots ORDER BY observed')]
            for i,p in enumerate(predictions):
                observed=[json.loads(r[0]) for r in db.execute('SELECT payload FROM events WHERE end>=? AND end<? AND captured<=? ORDER BY end,service,span',
                    (p['start'],p['end'],p['decision_at']))]
                replay=aggregate(observed,p['start'],p['end'])
                for actual,saved in zip(replay,rows[i*3:i*3+3]):
                    if actual['count']!=saved['count'] or actual['features']!=saved['features'] or actual['evidence']!=saved['evidence']:
                        feature_mismatches+=1
                if rescore:
                    offline=score(replay,bundle)
                    offline.pop('inference_ms')
                    saved={k:v for k,v in p.items() if k not in ('inference_ms','decision_at','window_close_to_decision_ms')}
                    if offline!=saved:decision_mismatches+=1
                    reference={c['service']:c for c in p['candidates']}
                    for c in offline['candidates']:
                        old=reference[c['service']]['ml_score']
                        if c['ml_score'] is not None and old is not None:
                            maximum_score_difference=max(maximum_score_difference,abs(c['ml_score']-old))
                late_events+=db.execute('SELECT COUNT(*) FROM events WHERE end>=? AND end<? AND captured>?',
                    (p['start'],p['end'],p['decision_at'])).fetchone()[0]
            total=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            unique=db.execute('SELECT COUNT(*) FROM (SELECT service,span FROM events GROUP BY service,span)').fetchone()[0]
        inventories={service:set() for service in ('frontend','checkout','inventory')}
        missing_snapshots=Counter()
        restarts={service:0 for service in inventories}
        for pods in snapshots:
            present=set()
            for pod in pods:
                service=pod['metadata']['labels']['app.kubernetes.io/name']
                present.add(service);inventories[service].add(pod['metadata']['uid'])
                for c in pod.get('status',{}).get('containerStatuses',[]):restarts[service]=max(restarts[service],c.get('restartCount',0))
            for service in set(inventories)-present:missing_snapshots[service]+=1
        target=schedule['target'];onset=schedule['onset'];recovery=schedule['recovery']
        impact=[]
        if target:
            for e in events:
                if not onset-3<=e['start']<recovery:continue
                if schedule['kind']=='delay' and e['service']==target and e['duration_ms']>=200:impact.append(e)
                elif schedule['kind']=='error' and e['service']==target and e['status']>=400:impact.append(e)
                elif schedule['kind']=='unavailable' and e['dependency']==target and e['dependency_status']==0:impact.append(e)
        impact.sort(key=lambda e:e['start'])
        active=[c for c in clients if onset is not None and onset<=c['start']<recovery]
        faulty_clients=[c for c in active if c['status']==0 or c['status']>=400]
        active_frontend=[c for c in active if c['status']==0] if target=='frontend' and schedule['kind']=='unavailable' else []
        first=impact[0] if impact else None
        sampled=[]
        for e in impact[:3]:sampled.append(dict(trigger_span=e['span_id'],trace_id=e['trace_id'],linked_events=sorted(by_trace[e['trace_id']],key=lambda r:r['start'])))
        normal_latency=[e['duration_ms'] for e in events if e['service']==target and (onset is None or e['end']<onset or e['start']>=recovery)]
        phase=dict(phase=trial.name,kind=schedule['kind'],target=target,event_count=len(events),client_count=len(clients),
            planned_observation_seconds=rows[-1]['end']-rows[0]['start'] if rows else None,
            client_requests_per_planned_second=len(clients)/(rows[-1]['end']-rows[0]['start']) if rows else None,
            window_close_to_decision_p95_ms=float(np.quantile([p['window_close_to_decision_ms'] for p in predictions],.95)) if predictions else None,
            client_statuses=dict(Counter(str(c['status']) for c in clients)),client_traces_without_captured_events=sum(c['trace_id'] not in by_trace for c in clients),
            successful_client_traces_with_incomplete_service_chain=len(incomplete_success),incomplete_success_examples=incomplete_success[:10],
            unique_store_records=unique,total_store_records=total,duplicate_records=total-unique,
            parent_links_verified=len(links),parent_links_missing=len(children)-len(links),
            prediction_windows=len(predictions),arrival_cutoff_feature_mismatches=feature_mismatches,
            score_decision_replay_mismatches=decision_mismatches if rescore else None,
            maximum_replayed_ml_score_difference=maximum_score_difference if rescore else None,
            events_arriving_after_their_window_decision=late_events,
            observed_pod_uids={s:sorted(v) for s,v in inventories.items()},snapshots_without_service=dict(missing_snapshots),maximum_observed_restart_counts=restarts,
            cleanup=read(trial/'cleanup.json'),dropped_workload_requests=schedule['dropped'],
            operational_warning_windows=sum(p['operational_alert'] for p in predictions),ml_warning_windows=sum(p['ml_alert'] for p in predictions),
            impact_event_count=len(impact),active_client_count=len(active),active_failed_clients=len(faulty_clients),
            frontend_transport_failures_during_unavailability=len(active_frontend),
            first_impact_start=first['start'] if first else None,first_impact_completion=first['end'] if first else None,
            first_impact_start_minus_command_completion=first['start']-onset if first else None,
            normal_target_latency_median_ms=float(np.median(normal_latency)) if normal_latency else None,
            impact_target_latency_median_ms=float(np.median([e['duration_ms'] for e in impact])) if impact else None,
            reviewed_examples=sampled,
            interpretation='Trace inspection alongside control-command proxies; delay >=200ms is an inspection filter for the configured 250ms injection, not a tuned detector')
        phases.append(phase)
    result=dict(run_id=directory.name,quick=report['quick'],phases=phases,model_review=model_review,
        checkpoint_sha256=hashlib.sha256((directory/'native_monitor.joblib').read_bytes()).hexdigest(),
        stored_checkpoint_digest_matches_report=hashlib.sha256((directory/'native_monitor.joblib').read_bytes()).hexdigest()==report['checkpoint_sha256'],
        boundary='Window-level operational/ML flags are reviewed separately; the cluster runner does not implement grouped incident counts. Missing spans during pod deletion cannot be reconstructed.')
    (directory/'trace_review.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--rescore',action='store_true');args=parser.parse_args()
    result=review(args.directory,args.rescore)
    print(json.dumps(dict(run_id=result['run_id'],phases=[{k:p[k] for k in ('phase','event_count','impact_event_count','active_failed_clients','arrival_cutoff_feature_mismatches','events_arriving_after_their_window_decision','parent_links_missing','cleanup')} for p in result['phases']]),indent=2))
