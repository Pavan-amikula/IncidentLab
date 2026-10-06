import hashlib
import json
from pathlib import Path

from .schema import LogWindow
from .simulation import SCENARIOS, make_window

DATA = Path("data/synthetic_v1")
MODELS = Path("artifacts/models")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_split(split, base=DATA):
    base = Path(base)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    file = base / f"{split}.jsonl"
    if digest(file) != manifest["files"][file.name]:
        raise ValueError(f"Dataset checksum mismatch: {file}")
    rows = read_jsonl(file)
    return rows, [LogWindow.model_validate(r["observations"]) for r in rows], manifest


def prepare(base=DATA):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    definitions = {"train": [(1000 + i, "healthy", i) for i in range(160)],
                   "validation": [(3000 + i, "healthy", i) for i in range(100)],
                   "test": [(10000 + s * 100 + i, scenario, i)
                            for s, scenario in enumerate(SCENARIOS) for i in range(40)]}
    identities, labels, all_hashes = {}, [], set()
    for split, cases in definitions.items():
        rows = []
        identities[split] = []
        for seed, scenario, step in cases:
            identity = f"synthetic-{seed}"
            observations = make_window(seed, scenario, step).model_dump(mode="json")
            content_hash = hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
            if content_hash in all_hashes:
                raise ValueError("Duplicate observations across dataset splits")
            all_hashes.add(content_hash)
            rows.append({"id": identity, "observations": observations})
            identities[split].append(identity)
            if split == "test":
                labels.append({"id": identity, "scenario": scenario,
                               "anomaly": scenario in ("database_unavailable", "worker_failure", "database_slow"),
                               "root_service": {"database_unavailable": "database", "worker_failure": "worker",
                                                "database_slow": "database"}.get(scenario)})
        write_jsonl(base / f"{split}.jsonl", rows)
    write_jsonl(base / "test_labels.jsonl", labels)
    manifest = {"dataset": "synthetic_v1", "source": "IncidentLab generator; not operational data",
                "counts": {k: len(v) for k, v in identities.items()}, "split_ids": identities,
                "files": {name: digest(base / name) for name in
                          ("train.jsonl", "validation.jsonl", "test.jsonl", "test_labels.jsonl")},
                "protocol": "Healthy-only training; separate healthy validation; disjoint synthetic test seeds. Labels separate from observations."}
    write_json(base / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    result = prepare()
    print(f"PREPARE complete: {result['counts']} -> {DATA.resolve()}")
