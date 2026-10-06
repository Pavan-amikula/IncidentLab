import time

from .datasets import DATA, MODELS, digest, load_split, write_json
from .detector import Detector


def train():
    rows, windows, manifest = load_split("train")
    started = time.perf_counter()
    model = Detector().train(windows)
    model.dataset_manifest_sha256 = digest(DATA / "manifest.json")
    checkpoint = MODELS / "trained.joblib"
    checksum = model.save(checkpoint)
    report = {"stage": "training", "dataset": manifest["dataset"], "windows": len(rows),
              "trees": 120, "features": model.model.n_features_in_, "templates": len(model.template_ids),
              "seconds": round(time.perf_counter() - started, 3), "checkpoint": str(checkpoint),
              "checkpoint_sha256": checksum, "dataset_manifest_sha256": model.dataset_manifest_sha256,
              "threshold": None, "validation_used": False, "test_used": False}
    write_json("artifacts/training_report.json", report)
    print(f"TRAIN complete: {len(rows)} healthy windows, 120 trees, {report['features']} features")
    print(f"Saved {checkpoint.resolve()} | threshold not calibrated yet")
    return report


if __name__ == "__main__":
    train()
