import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from incidentlab.datasets import load_split, prepare
from incidentlab.detector import Detector
from incidentlab.real_logs import features, parse_lines
from incidentlab.simulation import make_window


class TrainingTests(unittest.TestCase):
    def test_split_ids_disjoint_and_labels_not_in_observations(self):
        with TemporaryDirectory() as tmp:
            manifest = prepare(Path(tmp))
            a, b, c = [set(manifest["split_ids"][s]) for s in ("train", "validation", "test")]
            self.assertFalse(a & b or a & c or b & c)
            rows, windows, _ = load_split("test", Path(tmp))
            self.assertEqual(len(windows), 240)
            self.assertEqual(set(rows[0]), {"id", "observations"})
            file = Path(tmp) / "test.jsonl"
            file.write_text(file.read_text() + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_split("test", Path(tmp))

    def test_uncalibrated_model_cannot_serve_and_reload_preserves_prediction(self):
        model = Detector().train([make_window(60000 + i) for i in range(20)])
        with self.assertRaises(RuntimeError):
            model.analyze(make_window(63000))
        model.validate([make_window(61000 + i) for i in range(20)])
        sample = make_window(63000, "database_unavailable")
        expected = model.analyze(sample)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            model.save(path)
            actual = Detector.load(path).analyze(sample)
            for name in ("status", "score", "threshold", "diagnosis", "evidence"):
                self.assertEqual(expected[name], actual[name])
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "checksum"):
                Detector.load(path)

    def test_real_log_label_does_not_enter_feature_text(self):
        normal = "- 1117838570 2005.06.03 NODE 2005-06-03 NODE RAS KERNEL INFO same message"
        abnormal = normal.replace("- ", "FAILURE ", 1)
        rows_a, labels_a = parse_lines(normal)
        rows_b, labels_b = parse_lines(abnormal)
        self.assertEqual(features(rows_a[0]), features(rows_b[0]))
        self.assertNotEqual(labels_a, labels_b)
