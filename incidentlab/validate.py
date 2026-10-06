import numpy as np

from .datasets import DATA, MODELS, digest, load_split, write_json
from .detector import Detector


def validate():
    rows, windows, manifest = load_split("validation")
    model = Detector.load(MODELS / "trained.joblib")
    if model.dataset_manifest_sha256 != digest(DATA / "manifest.json"):
        raise ValueError("Dataset changed since training; retrain first")
    before = [(c.cluster_id, c.size, c.get_template()) for c in model.parser.drain.clusters]
    model.validate(windows)
    after = [(c.cluster_id, c.size, c.get_template()) for c in model.parser.drain.clusters]
    if before != after:
        raise ValueError("Parser changed during validation")
    scores = -model.model.score_samples([model.extract(w)[0] for w in windows])
    checksum = model.save(MODELS / "detector.joblib")
    report = {"stage": "validation", "purpose": "Healthy threshold calibration, not hyperparameter selection",
              "windows": len(rows), "threshold": model.threshold, "quantile": .99,
              "validation_alerts": int(np.sum(scores > model.threshold)),
              "score_min": float(scores.min()), "score_max": float(scores.max()),
              "checkpoint_sha256": checksum, "trained_checkpoint_sha256": digest(MODELS / "trained.joblib"),
              "parser_frozen": True, "test_used": False}
    write_json("artifacts/validation_report.json", report)
    print(f"VALIDATE complete: {len(rows)} healthy windows | threshold={model.threshold:.6f}")
    print(f"Saved calibrated checkpoint: {(MODELS / 'detector.joblib').resolve()}")
    return report


if __name__ == "__main__":
    validate()
