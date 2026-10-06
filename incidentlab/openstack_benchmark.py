"""Full OpenStack VM-session comparison using author instance annotations.

Annotations identify entire VM sessions, not faulty individual lines or onset times.
All files are scanned. Unassigned/ineligible records are counted explicitly.
"""
import hashlib
import json
import re
import time
from collections import Counter, defaultdict

import joblib
import numpy as np
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import precision_recall_fscore_support, average_precision_score

from .log_content import template
from .research_pipeline import ROOT, OUT, dump
from .semantic_models import Encoder, MODELS, DEVICE

from .openstack_schema import BASE, UUID, INSTANCE, LINE


def parse(path):
    sessions = defaultdict(list)
    all_texts, audit = [], Counter()
    with path.open(encoding='utf-8', errors='replace') as handle:
        for line in handle:
            audit['physical_lines'] += 1
            match = LINE.match(line)
            if not match:
                audit['unparsed_or_continuation_lines'] += 1
                continue
            audit['parsed_events'] += 1
            level, logger, body = match.groups()
            instance = INSTANCE.search(body)
            body = re.sub(r'^\[req-[^\]]+\]\s*', '', body)
            text = template(UUID.sub('<id>', body))
            all_texts.append(text)
            event = dict(text=text, error=level in ('ERROR', 'CRITICAL'), warning=level in ('WARN', 'WARNING'))
            if instance:
                sessions[instance[1]].append(event)
                audit['explicit_instance_events'] += 1
            else:
                audit['unassigned_instance_events'] += 1
    audit['sessions'] = len(sessions)
    return dict(sessions), all_texts, dict(audit)


def novelty_table(training_texts, all_texts):
    prototypes = sorted(set(training_texts))
    unique = sorted(set(all_texts))
    vectorizer = TfidfVectorizer(ngram_range=(1,2), max_features=30000, sublinear_tf=True)
    healthy = vectorizer.fit_transform(prototypes)
    lexical = {}
    for start in range(0, len(unique), 128):
        texts = unique[start:start+128]
        cosine = (vectorizer.transform(texts)@healthy.T).toarray()
        lexical.update(zip(texts, (1-cosine.max(axis=1)).clip(0,1).tolist()))
    encoder = Encoder()
    vectors = encoder.embed(unique)
    index = {text:i for i, text in enumerate(unique)}
    references = vectors[[index[text] for text in prototypes]]
    semantic = {}
    for start in range(0, len(unique), 128):
        scores = (1-(vectors[start:start+128]@references.T).max(axis=1)).clip(0,1)
        semantic.update(zip(unique[start:start+128], scores.tolist()))
    return lexical, semantic, dict(vectorizer=vectorizer, lexical_prototypes=healthy,
        semantic_prototypes=references, prototypes=prototypes,
        encoder_id=MODELS['encoder'][0], encoder_revision=MODELS['encoder'][1]), len(unique)


def session_features(session, lexical, semantic):
    n = len(session)
    lex = np.asarray([lexical[e['text']] for e in session])
    sem = np.asarray([semantic[e['text']] for e in session])
    features = [np.log1p(n), sum(e['error'] for e in session)/n,
                sum(e['warning'] for e in session)/n,
                len({e['text'] for e in session})/n, float(np.quantile(lex, .95)), float(np.mean(lex))]
    return features, float(np.quantile(lex, .95)), float(np.quantile(sem, .95))


def frozen_sequence_model(training_texts, training_sessions, all_texts):
    config = TemplateMinerConfig()
    config.profiling_enabled = False
    config.drain_max_clusters = 10000
    miner = TemplateMiner(config=config)
    for text in training_texts:
        miner.add_log_message(text)
    cluster_count = len(miner.drain.clusters)
    mapping = {}
    for text in sorted(set(all_texts)):
        match = miner.match(text)
        mapping[text] = match.cluster_id if match else 0
    if len(miner.drain.clusters) != cluster_count:
        raise RuntimeError('Frozen parser learned held-out templates')
    counts, totals = Counter(), Counter()
    for events in training_sessions.values():
        tokens = [-1]+[mapping[event['text']] for event in events]+[-2]
        for left, right in zip(tokens, tokens[1:]):
            counts[(left,right)] += 1; totals[left] += 1
    return dict(miner=miner, mapping=mapping, counts=counts, totals=totals,
                vocabulary=cluster_count+3, cluster_count=cluster_count,
                note='Healthy-fitted Drain3 templates plus first-order transition likelihood; end-of-session scoring')


def sequence_score(bundle, events):
    tokens = [-1]+[bundle['mapping'][event['text']] for event in events]+[-2]
    losses = [-np.log((bundle['counts'][(left,right)]+.1)/
                     (bundle['totals'][left]+.1*bundle['vocabulary']))
              for left, right in zip(tokens,tokens[1:])]
    return float(np.mean(losses))


def run():
    began = time.perf_counter()
    inputs = {}; audits = {}; hashes = {}; texts = []
    for filename in ('openstack_normal1.log', 'openstack_normal2.log', 'openstack_abnormal.log'):
        path = BASE/filename
        sessions, messages, audit = parse(path)
        inputs[filename] = sessions; audits[filename] = audit; texts.extend(messages)
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f'Scanned complete {filename}: {audit}', flush=True)
        if filename == 'openstack_normal1.log':
            training_texts = messages
    training = inputs['openstack_normal1.log']
    normal2 = inputs['openstack_normal2.log']
    # Exclude reused identities to prevent session leakage, and publish each exclusion.
    overlap = sorted(set(training)&set(normal2))
    validation = {key:events for key, events in normal2.items()
                  if key not in training and int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)%2 == 0}
    healthy_test = {key:events for key, events in normal2.items() if key not in training and key not in validation}
    abnormal = inputs['openstack_abnormal.log']
    duplicate_test = sorted(set(abnormal)&(set(training)|set(validation)|set(healthy_test)))
    abnormal = {key:events for key, events in abnormal.items() if key not in duplicate_test}
    labels_text = (BASE/'anomaly_labels.txt').read_text()
    positives = set(UUID.findall(labels_text))
    if not positives.issubset(abnormal):
        raise ValueError('Author-labeled sessions missing after identity audit')
    lexical, semantic, preprocessing, unique_count = novelty_table(training_texts, texts)
    sequence = frozen_sequence_model(training_texts, training, texts)
    def values(sessions):
        return [session_features(events, lexical, semantic) for events in sessions.values()]
    train = values(training); valid = values(validation)
    x_train = np.asarray([v[0] for v in train]); x_valid = np.asarray([v[0] for v in valid])
    center = np.median(x_train, axis=0)
    scale = np.maximum(np.median(np.abs(x_train-center), axis=0), [1,.01,.01,.01,.01,.01])
    model = IsolationForest(n_estimators=200, random_state=2026).fit((x_train-center)/scale)
    calibration = {'isolation_forest': -model.score_samples((x_valid-center)/scale),
                   'lexical': np.asarray([v[1] for v in valid]), 'semantic': np.asarray([v[2] for v in valid]),
                   'drain_sequence': np.asarray([sequence_score(sequence, events) for events in validation.values()])}
    thresholds = {name:float(np.quantile(values, .99)) for name, values in calibration.items()}
    checkpoint = dict(**preprocessing, model=model, sequence=sequence, center=center, scale=scale, thresholds=thresholds,
                      fitting='normal1 training; identity-disjoint normal2 validation only')
    checkpoint_path = OUT/'openstack_healthy_models_v2.joblib'
    joblib.dump(checkpoint, checkpoint_path)
    frozen = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    tests = [dict(instance=key, events=events, label=0, source='normal2') for key, events in healthy_test.items()]
    tests.extend(dict(instance=key, events=events, label=int(key in positives), source='abnormal') for key, events in abnormal.items())
    scored = [session_features(row['events'], lexical, semantic) for row in tests]
    matrix = np.asarray([v[0] for v in scored]); truth = np.asarray([r['label'] for r in tests])
    scores = {'isolation_forest': -model.score_samples((matrix-center)/scale),
              'lexical': np.asarray([v[1] for v in scored]), 'semantic': np.asarray([v[2] for v in scored]),
              'drain_sequence': np.asarray([sequence_score(sequence, row['events']) for row in tests])}
    results, predictions = {}, []
    for name, value in scores.items():
        predicted = value > thresholds[name]
        precision, recall, f1, _ = precision_recall_fscore_support(truth, predicted, average='binary', zero_division=0)
        results[name] = dict(precision=float(precision), recall=float(recall), f1=float(f1),
            average_precision=float(average_precision_score(truth, value)),
            threshold=thresholds[name], alerted_sessions=int(predicted.sum()),
            annotated_positive_hits=int((predicted&(truth==1)).sum()),
            false_alerted_normal2_sessions=int(sum(p and row['source']=='normal2' for p, row in zip(predicted, tests))))
    for i, row in enumerate(tests):
        predictions.append(dict(instance=row['instance'], source=row['source'], annotation=row['label'],
            event_count=len(row['events']), scores={name:float(value[i]) for name, value in scores.items()}))
    report = dict(scope='OpenStack development revision adding a conventional Drain3 sequence control after the initial check',
        drain_templates=sequence['cluster_count'],
        audits=audits, source_sha256=hashes, train_sessions=len(training), validation_sessions=len(validation),
        healthy_normal2_test_sessions=len(healthy_test), abnormal_test_sessions=len(abnormal),
        annotated_positive_sessions=int(truth.sum()), unique_text_templates=unique_count,
        overlap_normal2_exclusions=overlap, overlap_abnormal_exclusions=duplicate_test,
        results=results, checkpoint_sha256=frozen, encoder_device=DEVICE, seconds=time.perf_counter()-began,
        limitations=['Only four author-annotated abnormal VM sessions; uncertainty is large',
            'Annotation is at VM-session level; line/window labels, onset delay and root causes are not inferred',
            'Explicit instance association covers only part of logs; all other records are counted, not assigned by guess',
            'Unannotated abnormal-file sessions are treated as negative per supplied instance list; annotation may be incomplete',
            'Frozen sentence encoder is general-domain; no semantic-model fine-tuning',
            'Offline end-of-session comparison, not a streaming incident detector'])
    dump(OUT/'openstack_full_v2_report.json', report)
    dump(OUT/'openstack_full_v2_predictions.json', predictions)
    dump(OUT/'openstack_split_manifest.json', dict(train=sorted(training), validation=sorted(validation),
        normal2_test=sorted(healthy_test), abnormal_test=sorted(abnormal)))
    print(json.dumps(results, indent=2), flush=True)


if __name__ == '__main__':
    run()
