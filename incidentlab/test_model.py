import numpy as np

from .datasets import DATA, MODELS, digest, load_split, read_jsonl, write_json, write_jsonl
from .detector import Detector


def test_model():
    rows, windows, manifest = load_split("test")
    label_path = DATA / "test_labels.jsonl"
    if digest(label_path) != manifest["files"][label_path.name]:
        raise ValueError("Test labels checksum mismatch")
    labels = {r["id"]: r for r in read_jsonl(label_path)}
    if set(labels) != {r["id"] for r in rows}:
        raise ValueError("Test label identities do not match observations")
    model_path = MODELS / "detector.joblib"
    model = Detector.load(model_path)
    if model.dataset_manifest_sha256 != digest(DATA / "manifest.json"):
        raise ValueError("Dataset changed since training")
    original_hash = digest(model_path)
    predictions, cases = [], []
    for row, window in zip(rows, windows):
        result = model.analyze(window)
        predictions.append({"id": row["id"], "result": result})
    for scenario in sorted({v["scenario"] for v in labels.values()}):
        subset = [r for r in predictions if labels[r["id"]]["scenario"] == scenario]
        expected = labels[subset[0]["id"]]["root_service"]
        results = [r["result"] for r in subset]
        cases.append({"scenario": scenario, "windows": len(results), "alerts": sum(r["anomaly"] for r in results),
                      "ml_alerts": sum(r["ml_anomaly"] for r in results),
                      "abstentions": sum(r["status"] == "insufficient_telemetry" for r in results),
                      "diagnosis_correct": sum(r["anomaly"] and r["diagnosis"]["suspected_service"] == expected for r in results) if expected else None})
    eligible = [p for p in predictions if labels[p["id"]]["scenario"] != "missing_telemetry"]
    tp = sum(p["result"]["anomaly"] and labels[p["id"]]["anomaly"] for p in eligible)
    fp = sum(p["result"]["anomaly"] and not labels[p["id"]]["anomaly"] for p in eligible)
    fn = sum(not p["result"]["anomaly"] and labels[p["id"]]["anomaly"] for p in eligible)
    tn = len(eligible) - tp - fp - fn
    if digest(model_path) != original_hash:
        raise ValueError("Checkpoint modified during testing")
    report = {"stage": "testing", "benchmark": "synthetic_independent_windows_v1",
              "calibration": model.calibration, "cases": cases, "model_sha256": original_hash,
              "dataset_manifest_sha256": model.dataset_manifest_sha256,
              "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
              "precision": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn),
              "p95_processing_ms": round(float(np.percentile([p["result"]["processing_ms"] for p in predictions], 95)), 3),
              "training_performed": False, "validation_performed": False,
              "limitations": ["Synthetic patterns and diagnosis rules are co-authored; no real-world accuracy claim.",
                             "Benign traffic-surge alerts are false positives.",
                             "Missing telemetry is reported as abstention and excluded from binary metrics.",
                             "Processing time excludes collection and transport; no incident-level lead-time yet."]}
    write_json("artifacts/evaluation.json", report)
    write_jsonl(MODELS.parent / "test_predictions.jsonl", predictions)
    print(f"TEST complete: {len(predictions)} held-out synthetic windows | TP={tp}, FP={fp}, FN={fn}, TN={tn}")
    print("Saved artifacts/evaluation.json and artifacts/test_predictions.jsonl; model was not retrained")
    return report


if __name__ == "__main__":
    test_model()
