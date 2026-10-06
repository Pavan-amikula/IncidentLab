"""Healthy-trained lexical log novelty. This is TF-IDF, not an LLM/semantic encoder."""
import hashlib
import json
import re
import time
from collections import defaultdict

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import TfidfVectorizer

from .anomod_healthy import BASE,DEST,normal,sn_logs
from .external_evaluation import run_key,modality_directory
from .research_pipeline import ROOT,OUT,dump


def template(message):
    text=re.sub(r'^\[[^\]]+\]\s*','',message.strip())
    text=re.sub(r'\b[0-9a-fA-F]{12,}\b','<id>',text)
    text=re.sub(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?','<num>',text)
    return re.sub(r'\s+',' ',text).lower()[:2000]


def instrumentation(message):
    return bool(re.search(r'\bchaos(?:blade|mesh|_|\b)|fault[_ -]injection',message,re.I))


def novel_scores(bundle,texts):
    vector=bundle['vectorizer'].transform(texts)
    # L2-normalized sparse TF-IDF cosine to frozen healthy prototypes, bounded batches.
    scores=[]
    for start in range(0,len(texts),256):
        similarities=(vector[start:start+256]@bundle['prototypes'].T).toarray()
        scores.extend((1-similarities.max(axis=1)).clip(0,1).tolist())
    return scores


def longest_alert_run(flags):
    longest=current=0
    for flag in flags:
        current=current+1 if flag else 0;longest=max(longest,current)
    return longest


def train():
    rows=pq.read_table(DEST/'SN_data-logs.parquet').to_pylist()
    begin,end=min(r['timestamp'] for r in rows),max(r['timestamp'] for r in rows)
    cutoff=begin+(end-begin)*.7
    training=[r for r in rows if r['timestamp']<=cutoff and not instrumentation(r['message'])]
    validation=[r for r in rows if r['timestamp']>cutoff and not instrumentation(r['message'])]
    templates=sorted({template(r['message']) for r in training})
    vectorizer=TfidfVectorizer(ngram_range=(1,2),max_features=30000,sublinear_tf=True)
    prototypes=vectorizer.fit_transform(templates)
    bundle=dict(vectorizer=vectorizer,prototypes=prototypes,templates=templates)
    uniques=sorted({template(r['message']) for r in validation})
    scores=dict(zip(uniques,novel_scores(bundle,uniques)))
    values=np.array([scores[template(r['message'])] for r in validation])
    # Strict greater-than avoids exact duplicates triggering at a zero threshold.
    threshold=max(.05,float(np.quantile(values,.995)))
    bundle.update(event_novelty_threshold=threshold,window_novel_fraction=.1,minimum_events=20,
                  consecutive_alert_minutes=2,cutoff=cutoff)
    joblib.dump(bundle,OUT/'healthy_log_content.joblib')
    report=dict(model='TF-IDF nearest healthy template, lexical novelty only',
        healthy_training_events=len(training),healthy_validation_events=len(validation),
        unique_training_templates=len(templates),vocabulary_size=len(vectorizer.vocabulary_),
        event_novelty_threshold=threshold,window_novel_fraction=.1,minimum_events=20,consecutive_minutes=2,
        chronological_healthy_split='first 70% training, final 30% validation; same normal run, not independent deployment',
        fault_data_used_for_fit=False,instrumentation_markers_excluded=True,
        input='message text only; timestamps/paths/service IDs not vectorized')
    dump(OUT/'log_content_training_report.json',report)
    return bundle,report


def analyze(bundle,rows,start,end,score_fn=novel_scores):
    retained=[r for r in rows if start<=r['timestamp']<end and not instrumentation(r['message'])]
    uniques=sorted({template(r['message']) for r in retained})
    scores=dict(zip(uniques,score_fn(bundle,uniques))) if uniques else {}
    windows=defaultdict(list)
    for row in retained:
        key=(row['service'],int((row['timestamp']-start)//60))
        windows[key].append((row,scores[template(row['message'])]))
    findings=[];n=(end-start)//60
    for service in sorted({r['service'] for r in retained}):
        consecutive=0
        for w in range(n):
            events=windows.get((service,w),[])
            novel=[e for e in events if e[1]>bundle['event_novelty_threshold']]
            fraction=len(novel)/max(len(events),1)
            active=len(events)>=bundle['minimum_events'] and fraction>bundle['window_novel_fraction']
            consecutive=consecutive+1 if active else 0
            if consecutive>=bundle['consecutive_alert_minutes']:
                top=sorted(novel,key=lambda e:e[1],reverse=True)[:3]
                findings.append(dict(service=service,start=start+w*60,end=start+(w+1)*60,
                    events=len(events),novel_events=len(novel),novel_fraction=fraction,
                    evidence=[dict(timestamp=row['timestamp'],novelty=score,message=row['message'][:600],
                        evidence_id=hashlib.sha256(f"{service}:{row['timestamp']}:{row['message']}".encode()).hexdigest()[:20])
                        for row,score in top],
                    interpretation='Log-content drift; not confirmed fault or causal diagnosis'))
    return findings,dict(events=len(retained),unique_templates=len(uniques),
        excluded_instrumentation_events=sum(instrumentation(r['message']) for r in rows))


def run():
    started=time.perf_counter();bundle,training=train()
    # Freeze healthy-trained artifact before development fault inference.
    checkpoint_sha=hashlib.sha256((OUT/'healthy_log_content.joblib').read_bytes()).hexdigest()
    preparation=json.loads((OUT/'anomod_development_v2_preparation.json').read_text())
    cases=[];evidence=[]
    for case in preparation:
        if case.get('system')!='SN_data' or 'excluded' in case:continue
        key=case['case'].split(':',1)[1]
        rows,audit=sn_logs(modality_directory('SN_data','log_data',key))
        findings,counts=analyze(bundle,rows,case['start'],case['end'])
        for finding in findings:finding['case']=case['case']
        evidence.extend(findings)
        cases.append(dict(case=case['case'],warning_service_windows=len(findings),
            services=sorted({f['service'] for f in findings}),**counts))
        print('Log-content development check: '+case['case']+f' ({len(findings)} content warnings)',flush=True)
    report=dict(training=training,checkpoint_sha256=checkpoint_sha,scope='SocialNetwork lexical baseline on already-inspected AnoMod development data',
        evaluated_fault_runs=len(cases),runs_with_content_warnings=sum(c['warning_service_windows']>0 for c in cases),
        processed_events=sum(c['events'] for c in cases),warning_service_windows=len(evidence),cases=cases,
        limitations=['Content drift warnings are not incident recall or root-cause accuracy',
                     'TF-IDF recognizes lexical changes, not semantic meaning; known errors can have zero novelty',
                     'Healthy validation shares one run and is short; independent healthy controls still needed',
                     'Positive/negative workload shifts can change text without a fault',
                     'No log-only TrainTicket claim; its clock normalization remains incomplete'],seconds=round(time.perf_counter()-started,2))
    dump(OUT/'log_content_development_report.json',report);dump(OUT/'log_content_evidence.json',evidence)
    print(json.dumps({k:report[k] for k in ['evaluated_fault_runs','runs_with_content_warnings','processed_events','warning_service_windows','seconds']},indent=2))


if __name__=='__main__':run()
