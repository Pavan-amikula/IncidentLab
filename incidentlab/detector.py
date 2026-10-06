import re
import time
import hashlib
from pathlib import Path
from collections import Counter

import joblib
import numpy as np
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from sklearn.ensemble import IsolationForest

from .schema import SERVICES, LogWindow
from .simulation import make_window


def normalize(message):
    # Retain semantic words while excluding volatile numeric identifiers.
    return re.sub(r"\b\d+(?:\.\d+)?\b", "<NUM>", message)


class Detector:
    def __init__(self):
        config = TemplateMinerConfig()
        config.drain_sim_th = 0.6
        config.drain_max_clusters = 1000
        config.profiling_enabled = False
        self.parser = TemplateMiner(config=config)
        self.template_ids = []
        self.model = None
        self.threshold = None
        self.calibration = {}

    def extract(self, window: LogWindow):
        vector, evidence = [], []
        for service in SERVICES:
            rows = [e for e in window.events if e.service == service]
            counts, unknown = Counter(), 0
            for event in rows:
                cluster = self.parser.match(normalize(event.message))
                if cluster is None:
                    unknown += 1
                else:
                    counts[cluster.cluster_id] += 1
            n = len(rows)
            latencies = [e.latency_ms for e in rows]
            vector.extend([n, sum(e.level == "ERROR" for e in rows) / max(n, 1),
                           sum(e.level == "WARN" for e in rows) / max(n, 1),
                           float(np.percentile(latencies, 95)) if n else 0,
                           unknown / max(n, 1)])
            vector.extend(counts[t] / max(n, 1) for t in self.template_ids)
            evidence.append({"service": service, "events": n,
                             "error_count": sum(e.level == "ERROR" for e in rows),
                             "warning_count": sum(e.level == "WARN" for e in rows),
                             "unknown_fraction": unknown / max(n, 1),
                             "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2) if n else None})
        return vector, evidence

    def train(self, train):
        if len(train) < 10:
            raise ValueError("At least ten training windows are required")
        if self.model is not None:
            raise ValueError("Create a new Detector for each training run")
        for window in train:
            for event in window.events:
                self.parser.add_log_message(normalize(event.message))
        self.template_ids = sorted(c.cluster_id for c in self.parser.drain.clusters)
        self.model = IsolationForest(n_estimators=120, random_state=42, n_jobs=1)
        self.model.fit([self.extract(w)[0] for w in train])
        self.calibration = {"train_windows": len(train), "templates": len(self.template_ids)}
        return self

    def validate(self, calibration, quantile=.99):
        if self.model is None:
            raise RuntimeError("Train before validation")
        if len(calibration) < 10 or not 0 < quantile < 1:
            raise ValueError("Need at least ten validation windows and 0 < quantile < 1")
        scores = -self.model.score_samples([self.extract(w)[0] for w in calibration])
        self.threshold = float(np.quantile(scores, quantile))
        self.calibration.update(calibration_windows=len(calibration), threshold=self.threshold,
                                threshold_quantile=quantile)
        return self

    def fit(self):
        """Synthetic convenience fixture; production server never calls this."""
        self.train([make_window(1000 + i, step=i) for i in range(160)])
        return self.validate([make_window(3000 + i, step=i) for i in range(100)])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".sha256").write_text(digest, encoding="ascii")
        return digest

    @staticmethod
    def load(path):
        path = Path(path)
        expected = path.with_suffix(".sha256").read_text(encoding="ascii").strip()
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Checkpoint checksum mismatch")
        model = joblib.load(path)
        if not isinstance(model, Detector):
            raise ValueError("Checkpoint is not an IncidentLab detector")
        return model

    def analyze(self, window: LogWindow):
        if self.model is None or self.threshold is None:
            raise RuntimeError("Training and validation must finish before inference")
        started = time.perf_counter()
        vector, summaries = self.extract(window)
        score = float(-self.model.score_samples([vector])[0])
        missing = [r["service"] for r in summaries if r["events"] == 0]
        novel = any(r["unknown_fraction"] > .1 for r in summaries)
        ml_anomaly = score > self.threshold
        anomaly = (ml_anomaly or novel) and not missing
        status = "insufficient_telemetry" if missing else "anomaly" if anomaly else "normal"
        evidence = []
        for i, event in enumerate(window.events):
            if event.level != "INFO" or event.latency_ms > 150:
                evidence.append({"event_index": i, **event.model_dump(mode="json")})
        diagnosis = self.diagnose(window, summaries) if anomaly else {
            "suspected_service": None, "reason": "Missing telemetry; investigate collection first." if missing else "No incident detected.",
            "next_check": "Check collectors and service heartbeats." if missing else None}
        return {"status": status, "anomaly": anomaly, "ml_anomaly": ml_anomaly,
                "novel_templates": novel, "score": round(score, 6),
                "threshold": round(self.threshold, 6), "missing_services": missing,
                "services": summaries, "diagnosis": diagnosis, "evidence": evidence[:30],
                "evidence_count": len(evidence), "event_count": len(window.events),
                "processing_ms": round((time.perf_counter() - started) * 1000, 3),
                "method": "Drain3 + IsolationForest + template novelty; heuristic diagnosis",
                "limitations": "Score is not a probability. Diagnosis is a hypothesis, not verified causality. No LLM is used."}

    @staticmethod
    def diagnose(window, summaries):
        # Dependency-oriented heuristic: never receives fault labels or scenario IDs.
        database = [e for e in window.events if e.service == "database"]
        workers = [e for e in window.events if e.service == "worker"]
        if any(e.level == "ERROR" for e in database):
            return {"suspected_service": "database", "reason": "Database errors coexist with downstream symptoms.",
                    "next_check": "Inspect database availability and client connectivity; distinguish server failure from network failure."}
        if any(e.level == "ERROR" for e in workers):
            return {"suspected_service": "worker", "reason": "Worker errors are present; downstream queue symptoms may be related.",
                    "next_check": "Inspect worker process health, restart history, and pending jobs."}
        db_summary = next(r for r in summaries if r["service"] == "database")
        if (db_summary["p95_latency_ms"] or 0) > 150:
            return {"suspected_service": "database", "reason": "Observed database latency exceeds the demo diagnostic threshold.",
                    "next_check": "Inspect slow queries, resource saturation, locks, and network latency."}
        return {"suspected_service": None, "reason": "Behavior differs from calibration, but evidence does not isolate a cause.",
                "next_check": "Check traffic changes and correlated service metrics before intervening."}
