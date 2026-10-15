"""Unit tests for insectcam/detector.py (numpy and Pillow; onnxruntime only for the optional model test).

  py -m unittest discover tests        (from software/pi-zero-cam)
  INSECTCAM_TEST_MODEL=path\\to\\model.onnx  also runs the real-model test
"""

import os
import sys
import threading
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam import detector as d  # noqa: E402


def e2e_output(rows):
    """YOLO26 end-to-end layout [1, 300, 6]: x1, y1, x2, y2, score, class (input-pixel coordinates)."""
    out = np.zeros((1, 300, 6), dtype=np.float32)
    for i, row in enumerate(rows):
        out[0, i] = row
    return out


def raw_output(boxes, size_n=8400):
    """Provided-model layout [1, 4+nc, N]: centre x/y, w, h, class score (here nc=1)."""
    out = np.zeros((1, 5, size_n), dtype=np.float32)
    for i, (cx, cy, w, h, score) in enumerate(boxes):
        out[0, :, i] = (cx, cy, w, h, score)
    return out


class LetterboxTests(unittest.TestCase):
    def test_wide_frame_is_scaled_and_padded_top_and_bottom(self):
        tensor, scale, pad_x, pad_y = d.letterbox(Image.new("RGB", (640, 360), (255, 0, 0)), 480)
        self.assertEqual(tensor.shape, (1, 3, 480, 480))
        self.assertAlmostEqual(scale, 0.75)
        self.assertEqual((pad_x, pad_y), (0, 105))
        self.assertAlmostEqual(float(tensor[0, 0, 240, 240]), 1.0)          # image area is red
        self.assertAlmostEqual(float(tensor[0, 0, 10, 10]), 114 / 255, places=3)  # padding is grey

    def test_decoded_boxes_map_back_to_the_original_image(self):
        _, scale, pad_x, pad_y = d.letterbox(Image.new("RGB", (640, 360)), 480)
        # A box covering original pixels (100, 80)-(200, 160) sits at (75, 165)-(150, 225) in the 480 canvas.
        found = d.decode(e2e_output([(75, 165, 150, 225, 0.9, 0)]), 0.25, scale, pad_x, pad_y, 640, 360)
        box, score, cls = found[0]
        np.testing.assert_allclose(box, [100, 80, 200, 160], atol=1e-3)
        self.assertEqual((round(score, 2), cls), (0.9, 0))


class DecodeTests(unittest.TestCase):
    def test_end_to_end_layout_filters_by_confidence_and_needs_no_nms(self):
        out = e2e_output([(10, 10, 50, 50, 0.9, 0), (12, 12, 52, 52, 0.4, 0), (200, 200, 240, 240, 0.1, 0)])
        found = d.decode(out, 0.25, 1.0, 0, 0, 480, 480)
        self.assertEqual(len(found), 2)  # the 0.1 row is below confidence; the overlapping 0.4 row is kept (model's job)

    def test_raw_layout_applies_nms(self):
        out = raw_output([(100, 100, 40, 40, 0.9), (102, 101, 40, 40, 0.8), (300, 300, 30, 30, 0.7)])
        found = d.decode(out, 0.25, 1.0, 0, 0, 480, 480)
        self.assertEqual(len(found), 2)  # the near-duplicate of the first is suppressed
        np.testing.assert_allclose(found[0][0], [80, 80, 120, 120], atol=1e-3)

    def test_nothing_above_confidence_gives_empty(self):
        self.assertEqual(d.decode(raw_output([(100, 100, 40, 40, 0.1)]), 0.25, 1.0, 0, 0, 480, 480), [])

    def test_boxes_are_clipped_to_the_image(self):
        found = d.decode(e2e_output([(-20, -10, 30, 40, 0.9, 0)]), 0.25, 1.0, 0, 0, 100, 100)
        np.testing.assert_allclose(found[0][0], [0, 0, 30, 40])


class YuvTests(unittest.TestCase):
    def test_padded_planar_yuv420_round_trips_to_rgb(self):
        """Pack a known RGB image the way libcamera delivers it (rows padded to a stride) and convert back."""
        width, height, stride = 640, 360, 672
        rng = np.random.default_rng(5)
        # Smooth colour field: chroma subsampling loses detail, so test with low-frequency content.
        xs = np.linspace(0, 1, width)[None, :, None]
        ys = np.linspace(0, 1, height)[:, None, None]
        rgb = np.concatenate([xs * 255 + 0 * ys, ys * 255 + 0 * xs, (1 - xs) * 200 + 0 * ys], axis=2).astype(np.uint8)
        ycc = np.asarray(Image.fromarray(rgb).convert("YCbCr"))
        yuv = np.zeros((height * 3 // 2, stride), dtype=np.uint8)
        yuv[:height, :width] = ycc[:, :, 0]
        u = ycc[::2, ::2, 1]
        v = ycc[::2, ::2, 2]
        quarter = (height // 2) * (stride // 2)
        flat = np.zeros(quarter * 2, dtype=np.uint8)
        flat[:quarter] = np.pad(u, ((0, 0), (0, stride // 2 - u.shape[1]))).reshape(-1)
        flat[quarter:] = np.pad(v, ((0, 0), (0, stride // 2 - v.shape[1]))).reshape(-1)
        yuv[height:] = flat.reshape(height // 2, stride)
        back = np.asarray(d.yuv420_to_rgb(yuv, width, height)).astype(int)
        self.assertLess(np.abs(back - rgb.astype(int)).mean(), 4.0)
        del rng


class FakeDetector:
    """Stands in for Detector: records order, takes `delay` seconds."""
    def __init__(self, delay=0.05):
        self.delay, self.calls = delay, []

    def detect(self, image):
        self.calls.append(image.size)
        time.sleep(self.delay)
        return d.DetectionResult(d.OUTCOME_OK, int(self.delay * 1000))


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDetector()
        self.worker = d.DetectorWorker(self.fake)
        self.worker.start()

    def tearDown(self):
        self.worker.stop()

    def test_capture_job_returns_a_result(self):
        result = self.worker.detect_for_capture(Image.new("RGB", (64, 64)))
        self.assertEqual(result.outcome, d.OUTCOME_OK)

    def test_capture_job_times_out_with_a_timeout_outcome(self):
        self.fake.delay = 0.4
        result = self.worker.detect_for_capture(Image.new("RGB", (64, 64)), timeout=0.05)
        self.assertEqual(result.outcome, d.OUTCOME_TIMEOUT)

    def test_live_job_is_refused_while_busy_and_accepted_when_idle(self):
        self.fake.delay = 0.2
        first = self.worker.try_detect_live(Image.new("RGB", (64, 64)))
        self.assertIsNotNone(first)
        time.sleep(0.02)
        self.assertIsNone(self.worker.try_detect_live(Image.new("RGB", (64, 64))))  # busy
        self.assertTrue(first.done.wait(2))
        time.sleep(0.02)
        self.assertIsNotNone(self.worker.try_detect_live(Image.new("RGB", (64, 64))))

    def test_capture_job_runs_before_a_waiting_live_job(self):
        self.fake.delay = 0.15
        blocker = self.worker.try_detect_live(Image.new("RGB", (11, 11)))   # keeps the worker busy
        time.sleep(0.02)
        order = []
        def capture():
            self.worker.detect_for_capture(Image.new("RGB", (33, 33)), timeout=3)
            order.append("capture")
        thread = threading.Thread(target=capture)
        thread.start()
        blocker.done.wait(2)
        thread.join(3)
        self.assertEqual(order, ["capture"])
        self.assertEqual(self.fake.calls[:2], [(11, 11), (33, 33)])


class DrawTests(unittest.TestCase):
    def test_banner_and_boxes_are_burned_in(self):
        frame = Image.new("RGB", (640, 360), (200, 200, 200))
        result = d.DetectionResult(d.OUTCOME_OK, 123, [d.Prediction(0, "Ant", 0.8, 0.25, 0.25, 0.25, 0.25)])
        out = d.draw_detections(frame, result)
        self.assertEqual(out.size, (640, 360))
        self.assertEqual(out.getpixel((630, 3)), (170, 0, 0))             # red banner across the top
        self.assertEqual(out.getpixel((160, 135)), (60, 255, 60))         # left edge of the box (x = 0.25 * 640, y 90..180)
        self.assertEqual(frame.getpixel((630, 3)), (200, 200, 200))       # the input frame is not modified


@unittest.skipUnless(os.environ.get("INSECTCAM_TEST_MODEL"), "set INSECTCAM_TEST_MODEL to run against a real ONNX model")
class RealModelTests(unittest.TestCase):
    def test_model_loads_reports_size_names_and_detects_nothing_on_a_blank_frame(self):
        model = d.Detector(Path(os.environ["INSECTCAM_TEST_MODEL"]), threads=2)
        self.assertIn(model.size, (320, 480, 640))
        self.assertEqual(model.label(0), "Ant")
        self.assertEqual(len(model.sha256), 64)
        result = model.detect(Image.new("RGB", (640, 360), (128, 128, 128)))
        self.assertEqual(result.outcome, d.OUTCOME_OK)
        self.assertEqual(result.predictions, [])
        self.assertEqual(model.detect(Image.new("RGB", (8, 8))).outcome, d.OUTCOME_INVALID)


if __name__ == "__main__":
    unittest.main()
