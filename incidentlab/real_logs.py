"""Separate real-log baseline; BGL is not mapped to fictional demo services."""
import re
import urllib.request
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from .datasets import digest, write_json, write_jsonl

REVISION = "dd61d0952749ee7963bde24220d1be5ede023033"
URL = f"https://raw.githubusercontent.com/logpai/loghub/{REVISION}/BGL/BGL_2k.log"
RAW_SHA256 = "2a819ea540909db682005c9cf948387a40729b5c2e9f19d430e29ce704825496"
BASE = Path("data/bgl_sample")


def parse_lines(text):
    observations, labels = [], {}
    for i, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        fields = line.split(maxsplit=9)
        if len(fields) != 10:
            raise ValueError(f"Unexpected BGL format at line {i + 1}")
        # Field zero is the anomaly label. Neither it nor node/timestamp is a feature.
        identity = f"bgl-line-{i + 1}"
        observations.append({"id": identity, "node": fields[3], "severity": fields[8], "message": fields[9]})
        labels[identity] = int(fields[0] != "-")
    return observations, labels


def features(row):
    message = re.sub(r"0x[0-9a-fA-F]+", "HEX", row["message"])
    message = re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", message)
    return row["severity"] + " " + message


def run():
    BASE.mkdir(parents=True, exist_ok=True)
    raw = BASE / "BGL_2k.log"
    if not raw.exists():
        with urllib.request.urlopen(URL, timeout=30) as response:
            raw.write_bytes(response.read())
    if digest(raw) != RAW_SHA256:
        raise ValueError("BGL source checksum differs from the reviewed revision")
    rows, labels = parse_lines(raw.read_text(encoding="utf-8"))
    groups = [r["node"] for r in rows]
    indices = np.arange(len(rows))
    trainval, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=42).split(indices, groups=groups))
    local_train, local_val = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=43).split(
        trainval, groups=[groups[i] for i in trainval]))
    splits = {"train": trainval[local_train], "validation": trainval[local_val], "test": test_idx}
    nodes = {k: {groups[i] for i in v} for k, v in splits.items()}
    if nodes["train"] & nodes["validation"] or nodes["train"] & nodes["test"] or nodes["validation"] & nodes["test"]:
        raise ValueError("Node leakage across splits")
    for name, selected in splits.items():
        write_jsonl(BASE / f"{name}.jsonl", [rows[i] for i in selected])
    write_json(BASE / "labels.json", labels)
    train = [rows[i] for i in splits["train"] if labels[rows[i]["id"]] == 0]
    validation = [rows[i] for i in splits["validation"] if labels[rows[i]["id"]] == 0]
    test = [rows[i] for i in splits["test"]]
    if min(len(train), len(validation), len(test)) < 10:
        raise ValueError("Insufficient rows in grouped split")
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=1500)
    x_train = vectorizer.fit_transform([features(r) for r in train])
    model = IsolationForest(n_estimators=120, random_state=42, n_jobs=1).fit(x_train)
    validation_scores = -model.score_samples(vectorizer.transform([features(r) for r in validation]))
    threshold = float(np.quantile(validation_scores, .99))
    path = Path("artifacts/models/bgl_sample.joblib")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"vectorizer": vectorizer, "model": model, "threshold": threshold,
                 "raw_sha256": digest(raw)}, path)
    path.with_suffix(".sha256").write_text(digest(path), encoding="ascii")
    # Reload frozen artifacts for testing; no fitting on test observations.
    saved = joblib.load(path)
    scores = -saved["model"].score_samples(saved["vectorizer"].transform([features(r) for r in test]))
    predictions = scores > saved["threshold"]
    actual = np.array([labels[r["id"]] for r in test])
    p, recall, f1, _ = precision_recall_fscore_support(actual, predictions, average="binary", zero_division=0)
    report = {"dataset": "Loghub BGL 2,000-line sample", "source": URL, "revision": REVISION,
              "raw_sha256": digest(raw), "rows": len(rows),
              "split_rows": {k: len(v) for k, v in splits.items()},
              "split_nodes": {k: len(v) for k, v in nodes.items()},
              "healthy_training_rows": len(train), "healthy_validation_rows": len(validation),
              "test_anomalies": int(actual.sum()), "threshold": threshold,
              "precision": float(p), "recall": float(recall), "f1": float(f1),
              "roc_auc": float(roc_auc_score(actual, scores)) if len(set(actual)) == 2 else None,
              "confusion_matrix_labels": [0, 1], "confusion_matrix": confusion_matrix(actual, predictions, labels=[0, 1]).tolist(),
              "method": "Healthy-only TF-IDF + IsolationForest; threshold from healthy validation; grouped by node",
              "label_field_excluded": True, "nodes_disjoint": True,
              "limitations": ["Small research sample, not full BGL or a Kubernetes benchmark.",
                             "Node-group split measures a particular cross-node sample; it is not a chronological deployment simulation.",
                             "Repeated event types and correlated failures may span nodes; independence is not guaranteed.",
                             "No hyperparameter search; low accuracy is retained rather than tuning on test results.",
                             "No diagnosis or latency features: BGL is a separate text-only baseline."]}
    write_json("artifacts/real_log_report.json", report)
    write_json(BASE / "manifest.json", {"source": URL, "raw_sha256": digest(raw),
                                       "split_policy": "GroupShuffleSplit by node; seeds 42/43",
                                       "files": {f"{k}.jsonl": digest(BASE / f"{k}.jsonl") for k in splits}})
    write_jsonl(Path("artifacts/real_log_predictions.jsonl"),
                [{"id": r["id"], "score": float(s), "prediction": bool(p)} for r, s, p in zip(test, scores, predictions)])
    print(f"REAL LOGS: {len(rows)} BGL observations | splits {report['split_rows']}")
    print(f"Held-out node test: precision={p:.3f}, recall={recall:.3f}, F1={f1:.3f}")
    print("Saved artifacts/real_log_report.json; sample-level results only")
    return report


if __name__ == "__main__":
    run()
