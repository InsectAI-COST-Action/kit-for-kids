"""Unit tests for recording detections (insectcam/capture.py): rows, columns, manifest, config safety.

  py -m unittest discover tests        (from software/pi-zero-cam)
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam.capture import (CAPTURE_HEADER, DETECTION_HEADER, Config, Session, Storage,  # noqa: E402
                               csv_escape)


def result(outcome="ok", ms=300, predictions=()):
    preds = [SimpleNamespace(class_id=c, label=l, confidence=conf, x=x, y=y, w=w, h=h)
             for c, l, conf, x, y, w, h in predictions]
    return SimpleNamespace(outcome=outcome, elapsed_ms=ms, predictions=preds,
                           max_confidence=max((p.confidence for p in preds), default=0.0))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tmp.name))
        self.addCleanup(self.tmp.cleanup)

    def session(self, **config):
        cfg = Config(**config)
        s = Session(self.storage, cfg, "IMX708", "boot_1",
                    model_sha256="ab" * 32 if cfg.detection_enabled else "",
                    model_status="placeholder_unvalidated" if cfg.detection_enabled else "")
        s.begin()
        return s

    def record(self, s, detection=None, outcome="completed", image="/images/x.jpg", n=1):
        capture_id = s.next_capture_id()
        s.record(capture_id=capture_id, uptime_ms=1000 * n, scheduled_ms=1000 * n, outcome=outcome, width=2304,
                 height=1296, jpeg_bytes=300000, capture_ms=100, image_path=image, save_outcome="saved",
                 detection=detection)
        return capture_id

    def test_detection_off_keeps_todays_records(self):
        s = self.session()
        self.record(s)
        row = read_csv(self.storage.path("raw/captures.csv"))[0]
        self.assertEqual((row["model_id"], row["inference_ms"], row["prediction_count"], row["max_confidence"]),
                         ("none", "0", "0", "0.0000"))
        self.assertEqual(self.storage.path("raw/detections.csv").read_text().strip(), DETECTION_HEADER)
        self.assertEqual(list(row.keys()), CAPTURE_HEADER.split(","))

    def test_predictions_are_recorded_in_both_files(self):
        s = self.session(model_id="ant_test")
        cid = self.record(s, result(predictions=[(0, "Ant", 0.91, 0.1, 0.2, 0.05, 0.08), (0, "Ant", 0.4, 0.5, 0.5, 0.02, 0.03)]))
        row = read_csv(self.storage.path("raw/captures.csv"))[0]
        self.assertEqual((row["model_id"], row["inference_ms"], row["prediction_count"], row["max_confidence"]),
                         ("ant_test", "300", "2", "0.9100"))
        rows = read_csv(self.storage.path("raw/detections.csv"))
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual((first["capture_id"], first["prediction_index"], first["label_id"], first["label"],
                          first["confidence"], first["model_id"]), (cid, "0", "0", "Ant", "0.9100", "ant_test"))
        self.assertEqual((first["bbox_x"], first["bbox_y"], first["bbox_w"], first["bbox_h"]),
                         ("0.10000", "0.20000", "0.05000", "0.08000"))
        meta = json.loads(first["metadata_json"])
        self.assertEqual(meta["model_status"], "placeholder_unvalidated")
        self.assertEqual(meta["model_sha256"], "ab" * 32)

    def test_many_predictions_cost_one_sync_for_the_detection_file(self):
        """60 boxes written one fsync each held the Pi's capture loop for ~8 s (16 October 2026)."""
        import os
        from unittest import mock
        s = self.session(model_id="ant_test")
        many = [(0, "Ant", 0.5, 0.01 * i, 0.1, 0.02, 0.02) for i in range(60)]
        with mock.patch("insectcam.capture.os.fsync", wraps=os.fsync) as fsync:
            self.record(s, result(predictions=many))
        self.assertEqual(len(read_csv(self.storage.path("raw/detections.csv"))), 60)
        self.assertLess(fsync.call_count, 12)     # not 60+: the capture row, one detection write, dashboard chunk

    def test_dashboard_chunk_carries_inference_values(self):
        s = self.session(model_id="ant_test")
        self.record(s, result(ms=412, predictions=[(0, "Ant", 0.8, 0, 0, 0.1, 0.1)]))
        text = self.storage.path("data/captures_current.js").read_text()
        payload = json.loads(text[text.index("addCapture({") + len("addCapture("): text.rindex("});") + 1])
        self.assertEqual((payload["inferenceMs"], payload["inferenceOutcome"]), (412, "ok"))

    def test_a_check_with_no_inference_is_model_unavailable_like_the_xiao(self):
        s = self.session(model_id="ant_test", motion_trigger_enabled=True)
        self.record(s, None, outcome="motion_not_detected", image="")
        text = self.storage.path("data/captures_current.js").read_text()
        self.assertIn('"inferenceOutcome":"model_unavailable"', text)
        self.assertEqual(len(read_csv(self.storage.path("raw/detections.csv"))), 0)

    def test_failed_inference_records_its_outcome_and_no_rows(self):
        s = self.session(model_id="ant_test")
        self.record(s, result(outcome="timeout", ms=1500))
        self.assertEqual(read_csv(self.storage.path("raw/captures.csv"))[0]["inference_ms"], "1500")
        self.assertIn('"inferenceOutcome":"timeout"', self.storage.path("data/captures_current.js").read_text())
        self.assertEqual(len(read_csv(self.storage.path("raw/detections.csv"))), 0)

    # --- the dashboard's view of the results: optional record fields and per-chunk box files
    def boxes(self, n):
        return [(0, "Ant", 0.30 + 0.005 * i, 0.01 * i, 0.1, 0.02, 0.03) for i in range(n)]

    def test_chunk_record_carries_model_and_counts_and_boxes_go_to_their_own_file(self):
        s = self.session(model_id="ant_test")
        cid = self.record(s, result(predictions=self.boxes(3)))
        record = self.storage.path("data/captures_current.js").read_text()
        for expected in ('"modelId":"ant_test"', '"modelStatus":"placeholder_unvalidated"', '"predictionCount":3',
                         '"maxConfidence":0.31'):
            self.assertIn(expected, record)
        line = self.storage.path("data/detections_current.js").read_text().strip()
        self.assertTrue(line.endswith(");"))
        self.assertIn(f'addDetections("{cid}",[[0.02,0.1,0.02,0.03,0.31],', line)   # highest score first
        self.assertEqual(line.count("],["), 2)

    def test_without_a_model_nothing_new_appears_so_a_xiao_style_card_is_unchanged(self):
        s = self.session()
        self.record(s)
        text = self.storage.path("data/captures_current.js").read_text()
        for absent in ("modelId", "modelStatus", "predictionCount", "maxConfidence"):
            self.assertNotIn(absent, text)
        self.assertFalse(self.storage.path("data/detections_current.js").exists())
        s.finish()
        self.assertNotIn("detectionChunks", self.storage.path("manifest.js").read_text())

    def test_a_failed_inference_has_the_model_but_no_counts_and_no_boxes_line(self):
        s = self.session(model_id="ant_test")
        self.record(s, result(outcome="timeout", ms=1500))
        text = self.storage.path("data/captures_current.js").read_text()
        self.assertIn('"modelId":"ant_test"', text)
        self.assertNotIn("predictionCount", text)
        self.assertFalse(self.storage.path("data/detections_current.js").exists())

    def test_boxes_per_photo_are_capped_in_the_dashboard_file_but_not_in_the_csv(self):
        s = self.session(model_id="ant_test")
        self.record(s, result(predictions=self.boxes(130)))
        line = self.storage.path("data/detections_current.js").read_text().strip()
        self.assertEqual(line.count("],[") + 1, 100)
        self.assertEqual(len(read_csv(self.storage.path("raw/detections.csv"))), 130)

    def test_boxes_file_is_closed_with_its_captures_chunk_and_listed_in_the_manifest(self):
        s = self.session(model_id="ant_test")
        for n in range(100):
            self.record(s, result(predictions=self.boxes(2) if n % 2 == 0 else ()), n=n + 1)
        self.assertTrue(self.storage.path("data/captures_000001.js").is_file())
        self.assertTrue(self.storage.path("data/detections_000001.js").is_file())
        self.assertFalse(self.storage.path("data/detections_current.js").exists())
        self.assertEqual(self.storage.path("data/detections_000001.js").read_text().count("addDetections(\""), 50)   # one line per photo that had boxes
        self.assertIn('"detectionChunks":["data/detections_000001.js"]', self.storage.path("manifest.js").read_text())

    def test_a_torn_last_boxes_line_is_dropped_on_restart_so_the_file_still_loads(self):
        s = self.session(model_id="ant_test")
        self.record(s, result(predictions=self.boxes(2)))
        path = self.storage.path("data/detections_current.js")
        path.write_text(path.read_text() + 'window.InsectData.addDetections("run_x_img_9",[[0.1,0.2,0.0')   # cut mid-line
        s2 = self.session(model_id="ant_test")      # a new session recovers the old files
        self.assertFalse(path.exists() and "img_9" in path.read_text())
        for text in (self.storage.path("data/detections_000001.js").read_text(),):
            self.assertTrue(text.strip().endswith(");"))
            self.assertNotIn("img_9", text)
        del s2

    def test_manifest_names_the_model_and_its_status(self):
        s = self.session(model_id="ant_test", detection_confidence=0.4)
        manifest = json.loads(self.storage.path(f"raw/runs/{s.run_id}.json").read_text())
        self.assertEqual((manifest["model_id"], manifest["model_status"], manifest["detection_confidence"]),
                         ("ant_test", "placeholder_unvalidated", 0.4))
        self.assertEqual(manifest["model_sha256"], "ab" * 32)

    def test_manifest_keeps_the_state_text_the_recovery_code_rewrites(self):
        s = self.session(model_id="ant_test")
        text = self.storage.path(f"raw/runs/{s.run_id}.json").read_text()
        self.assertIn('"state": "running"', text)


class ConfigTests(unittest.TestCase):
    def load(self, **data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(data))
            return Config.load(path)

    def test_model_id_and_confidence_load(self):
        config, note = self.load(model_id="ant_test_placeholder_int8_480", detection_confidence=0.3)
        self.assertTrue(config.detection_enabled)
        self.assertEqual((config.model_id, config.detection_confidence), ("ant_test_placeholder_int8_480", 0.3))

    def test_none_means_off(self):
        self.assertFalse(self.load(model_id="none")[0].detection_enabled)

    def test_a_path_in_model_id_is_refused_and_defaults_are_used(self):
        for bad in ("../../etc/passwd", "a/b", ".hidden", "x" * 80, "with space"):
            config, note = self.load(model_id=bad)
            self.assertFalse(config.detection_enabled, bad)
            self.assertIn("model_id", note)

    def test_confidence_out_of_range_is_refused(self):
        self.assertIn("detection_confidence", self.load(model_id="m", detection_confidence=0.99)[1])


if __name__ == "__main__":
    unittest.main()
