import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from pydantic import ValidationError

from incidentlab.detector import Detector
from incidentlab.schema import LogWindow
from incidentlab.simulation import make_window


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = Detector().fit()

    def test_frozen_parser_does_not_learn_evaluation_faults(self):
        before = [(c.cluster_id, c.size, c.get_template()) for c in self.detector.parser.drain.clusters]
        result = self.detector.analyze(make_window(51000, "database_unavailable"))
        after = [(c.cluster_id, c.size, c.get_template()) for c in self.detector.parser.drain.clusters]
        self.assertEqual(before, after)
        self.assertTrue(result["novel_templates"])
        self.assertTrue(result["anomaly"])

    def test_evidence_is_actual_input_and_diagnosis_has_no_labels(self):
        window = make_window(51001, "database_unavailable")
        result = self.detector.analyze(window)
        self.assertEqual(result["diagnosis"]["suspected_service"], "database")
        for evidence in result["evidence"]:
            self.assertEqual(evidence["message"], window.events[evidence["event_index"]].message)
        payload = window.model_dump(mode="json")
        payload["root_cause"] = "database"
        with self.assertRaises(ValidationError):
            LogWindow.model_validate(payload)

    def test_missing_telemetry_abstains_instead_of_claiming_health(self):
        result = self.detector.analyze(make_window(51002, "missing_telemetry"))
        self.assertEqual(result["status"], "insufficient_telemetry")
        self.assertFalse(result["anomaly"])
        self.assertIsNone(result["diagnosis"]["suspected_service"])

    def test_invalid_latency_rejected(self):
        payload = make_window(51003).model_dump(mode="json")
        payload["events"][0]["latency_ms"] = float("nan")
        with self.assertRaises(ValidationError):
            LogWindow.model_validate(payload)

    def test_api_ingestion_persists_evidence_and_rejects_labels(self):
        from incidentlab import server
        with TemporaryDirectory() as tmp:
            original = server.ARTIFACTS
            server.ARTIFACTS = Path(tmp)
            try:
                self.detector.save(Path(tmp) / "models" / "detector.joblib")
                with TestClient(server.app) as client:
                    self.assertTrue(client.get("/api/health").json()["ready"])
                    payload = make_window(51004, "worker_failure").model_dump(mode="json")
                    response = client.post("/api/analyze", json=payload)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["diagnosis"]["suspected_service"], "worker")
                    self.assertEqual(len(client.get("/api/history").json()), 1)
                    payload["scenario"] = "worker_failure"
                    self.assertEqual(client.post("/api/analyze", json=payload).status_code, 422)
                    self.assertEqual(client.post("/api/demo", json={"scenario": "invalid"}).status_code, 422)
                    self.assertEqual(client.get("/").status_code, 200)
            finally:
                server.ARTIFACTS = original


if __name__ == "__main__":
    unittest.main()
