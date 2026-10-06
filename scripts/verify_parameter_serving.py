"""Replay complete author parameter records through actual HTTP, then audit scores."""
import hashlib
import json
import time
import uuid
import argparse
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from incidentlab.openstack_parameters import BASE,duration_event,SCHEMA
from incidentlab.research_pipeline import OUT,dump


def post(payload):
    request=Request('http://127.0.0.1:8768/api/openstack/parameters',
        data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response:return json.loads(response.read())['results']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=('v3','v4'),default='v3')
    args=parser.parse_args()
    expected={(r['source'],r['instance']):r for r in json.loads((OUT/'openstack_parameters_v3_predictions.json').read_text())}
    ranks={(r['source'],r['instance']):r for r in json.loads((OUT/'openstack_parameters_v4_predictions.json').read_text())} if args.profile=='v4' else {}
    rows,streams,hashes={}, {}, {}
    events_sent=0; began=time.perf_counter()
    for name,role in (('openstack_normal2.log','normal2'),('openstack_abnormal.log','abnormal')):
        path=BASE/name
        stream='parameter-replay-'+args.profile+'-'+role+'-'+uuid.uuid4().hex[:8]
        streams[role]=stream;hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        batch=[];last_event=None
        with path.open(encoding='utf-8') as source:
            for number,line in enumerate(source,1):
                event=duration_event(line,number)
                if event is None:continue
                last_event=event
                batch.append(event)
                if len(batch)==128:
                    for value in post(dict(stream=stream,feature_schema=SCHEMA,calibration_profile=args.profile,events=batch)):
                        rows[(role,value['instance'])]=value
                    events_sent+=len(batch);batch=[]
        if batch:
            for value in post(dict(stream=stream,feature_schema=SCHEMA,calibration_profile=args.profile,events=batch)):
                rows[(role,value['instance'])]=value
            events_sent+=len(batch)
        # Verify exact duplicate rejection via the public HTTP endpoint.
        try:post(dict(stream=stream,feature_schema=SCHEMA,calibration_profile=args.profile,events=[last_event]))
        except HTTPError as exc:
            if exc.code!=409:raise
        else:raise RuntimeError('Duplicate source line was accepted')
    errors=[];missing=[];ml_complete=0
    for key,reference in expected.items():
        if key not in rows:
            missing.append(dict(source=key[0],instance=key[1],reason='No explicitly associated numeric duration record'))
            continue
        actual=rows[key]
        if actual['parameters']!=reference['parameters']:
            raise RuntimeError('HTTP accumulated parameters differ from full-file adapter')
        for name in ('parameter_residual','parameter_isolation_forest'):
            errors.append(abs(actual[name]-reference['scores'][name]))
        if args.profile=='v4':
            errors.append(abs(actual['combined_tail_pvalue']-ranks[key]['combined_tail_pvalue']))
            assert actual['parameter_warning']==ranks[key]['warning']
        ml_complete+=int(actual['ml_eligible'])
    if max(errors)>1e-10:
        raise RuntimeError('Serving scores differ from frozen offline scores')
    result=dict(status='passed',profile=args.profile,streams=streams,parameter_events_sent=events_sent,
        heldout_sessions_compared=len(expected)-len(missing),eligible_complete_ml_sessions=ml_complete,
        missing_parameter_sessions=missing,max_score_difference=max(errors),
        duplicate_http_status=409,source_sha256=hashes,seconds=time.perf_counter()-began,
        scope='Archived full-file parameter replay through HTTP and SQLite, not a live company OpenStack connection',
        exclusions='All normal2 parameter events are ingested; score verification uses only the published held-out split identities. No labels enter HTTP requests.',
        caveat='Partial lifecycle ML decisions abstain; residual warnings use observed parameters. VM-session labels do not establish onset or early detection.')
    dump(OUT/f'parameter_serving_verification_{args.profile}.json',result)
    dump(OUT/'parameter_serving_verification.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
