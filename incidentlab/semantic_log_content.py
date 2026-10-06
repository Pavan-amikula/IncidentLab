"""Frozen MiniLM healthy-reference novelty, matched to the lexical development check."""
import hashlib
import json
import time

import joblib
import numpy as np
import pyarrow.parquet as pq
import torch

from .anomod_healthy import DEST, sn_logs
from .external_evaluation import modality_directory
from .log_content import analyze, instrumentation, template
from .research_pipeline import OUT, dump
from .semantic_models import Encoder, DEVICE, MODELS


def run():
    started = time.perf_counter()
    encoder = Encoder()
    if DEVICE == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    cache = {}
    embedding_seconds = 0

    def embedding(texts):
        nonlocal embedding_seconds
        missing = sorted(set(texts)-cache.keys())
        if missing:
            began = time.perf_counter()
            vectors = encoder.embed(missing)
            embedding_seconds += time.perf_counter()-began
            cache.update(zip(missing, vectors))
        return np.asarray([cache[text] for text in texts])

    rows = pq.read_table(DEST/'SN_data-logs.parquet').to_pylist()
    begin, end = min(r['timestamp'] for r in rows), max(r['timestamp'] for r in rows)
    cutoff = begin+(end-begin)*.7
    training = [r for r in rows if r['timestamp'] <= cutoff and not instrumentation(r['message'])]
    validation = [r for r in rows if r['timestamp'] > cutoff and not instrumentation(r['message'])]
    templates = sorted({template(r['message']) for r in training})
    prototypes = embedding(templates)

    def novel_scores(bundle, texts):
        vectors = embedding(texts)
        return (1-(vectors@bundle['prototypes'].T).max(axis=1)).clip(0, 1).tolist()

    bundle = dict(prototypes=prototypes, templates=templates, model=MODELS['encoder'][:2],
                  cutoff=cutoff, window_novel_fraction=.1, minimum_events=20, consecutive_alert_minutes=2)
    uniques = sorted({template(r['message']) for r in validation})
    scored = dict(zip(uniques, novel_scores(bundle, uniques)))
    threshold = max(.05, float(np.quantile([scored[template(r['message'])] for r in validation], .995)))
    bundle['event_novelty_threshold'] = threshold
    path = OUT/'healthy_semantic_log_content.joblib'
    joblib.dump(bundle, path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cases, evidence = [], []
    preparation = json.loads((OUT/'anomod_development_v2_preparation.json').read_text())
    for case in preparation:
        if case.get('system') != 'SN_data' or 'excluded' in case:
            continue
        key = case['case'].split(':', 1)[1]
        raw, _ = sn_logs(modality_directory('SN_data', 'log_data', key))
        findings, counts = analyze(bundle, raw, case['start'], case['end'], novel_scores)
        for finding in findings:
            finding['case'] = case['case']
            finding['interpretation'] = 'Embedding distance from healthy text; not verified semantic fault or cause'
        evidence.extend(findings)
        cases.append(dict(case=case['case'], warning_service_windows=len(findings),
                          services=sorted({f['service'] for f in findings}), **counts))
        print(f"Semantic development check: {case['case']} ({len(findings)} warnings)", flush=True)
    lexical = json.loads((OUT/'log_content_development_report.json').read_text())
    report = dict(model='Frozen pretrained MiniLM + healthy template prototypes', device=DEVICE,
        model_id=MODELS['encoder'][0], revision=MODELS['encoder'][1], checkpoint_sha256=sha,
        neural_weights_fine_tuned=False, fault_data_used_for_fit=False,
        healthy_training_events=len(training), healthy_validation_events=len(validation),
        unique_training_templates=len(templates), event_novelty_threshold=threshold,
        matched_lexical_policy=dict(minimum_events=20, window_novel_fraction=.1, consecutive_minutes=2,
            text_input='same normalized message text; service IDs, fault names and timestamps excluded'),
        evaluated_fault_runs=len(cases), processed_events=sum(c['events'] for c in cases),
        runs_with_content_warnings=sum(c['warning_service_windows'] > 0 for c in cases),
        warning_service_windows=len(evidence), lexical_warning_service_windows=lexical['warning_service_windows'],
        unique_templates_embedded=len(cache), embedding_seconds=embedding_seconds,
        peak_cuda_allocated_mb=torch.cuda.max_memory_allocated()/1024**2 if DEVICE == 'cuda' else 0,
        cases=cases, seconds=time.perf_counter()-started,
        limitations=['Already-inspected AnoMod development cases; not a fresh held-out test',
            'One short healthy run split chronologically; no independent healthy alert-rate measurement',
            'General sentence encoder may suppress important log differences or miss familiar errors',
            'Distance-based warnings are not causal diagnosis or verified incident recall',
            'Neural encoder is frozen; prototypes and threshold fitted from healthy references only'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise RuntimeError('Semantic checkpoint changed during inference')
    dump(OUT/'semantic_log_content_report.json', report)
    dump(OUT/'semantic_log_content_evidence.json', evidence)
    print(json.dumps({key:report[key] for key in ('device', 'evaluated_fault_runs',
        'runs_with_content_warnings', 'warning_service_windows', 'embedding_seconds', 'peak_cuda_allocated_mb')}, indent=2))


if __name__ == '__main__':
    run()
