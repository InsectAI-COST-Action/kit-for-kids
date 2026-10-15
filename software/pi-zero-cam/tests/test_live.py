"""Unit tests for the live view (insectcam/live.py) and its /api/live stream (insectcam/control.py).

Fake camera and worker stand in for the hardware; the HTTP test talks to the real server.

  py -m unittest discover tests        (from software/pi-zero-cam)
"""

import http.client
import io
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam import detector as d  # noqa: E402
from insectcam.capture import Storage  # noqa: E402
from insectcam.control import LIVE_BOUNDARY, start_control_server  # noqa: E402
from insectcam.live import LiveView  # noqa: E402


class FakeCamera:
    def __init__(self):
        self.grabs = 0

    def grab_rgb(self):
        self.grabs += 1
        return Image.new("RGB", (640, 360), (40, 40, 40))


class FakeWorker:
    """Answers every live job at once with one fixed prediction; can be made busy."""
    def __init__(self):
        self.is_idle = True

    def idle(self):
        return self.is_idle

    def try_detect_live(self, image):
        if not self.is_idle:
            return None
        ticket = SimpleNamespace(done=threading.Event(),
                                 result=d.DetectionResult(d.OUTCOME_OK, 123, [d.Prediction(0, "Ant", 0.8, 0.25, 0.25, 0.25, 0.25)]))
        ticket.done.set()
        return ticket


class LiveViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = Path(self.tmp.name)
        (self.models / "ant_test.onnx").write_bytes(b"x")   # present, never loaded (a worker is supplied)
        self.camera, self.worker = FakeCamera(), FakeWorker()
        self.live = LiveView(self.models, max_clients=2)
        self.addCleanup(self.live.detach)

    def attach(self):
        self.live.attach(self.camera, SimpleNamespace(detection_enabled=False, detection_confidence=0.25), self.worker)

    def test_open_refuses_without_a_session_a_model_or_room(self):
        self.assertEqual(self.live.open(), "live_not_available")
        self.attach()
        for model in self.models.glob("*.onnx"):
            model.unlink()
        self.assertEqual(self.live.open(), "no_model_installed")
        (self.models / "ant_test.onnx").write_bytes(b"x")
        self.assertIsNone(self.live.open())
        self.assertIsNone(self.live.open())
        self.assertEqual(self.live.open(), "live_busy")    # a third viewer is refused
        self.live.close()
        self.assertIsNone(self.live.open())                # and fits again once one leaves

    def test_frames_are_annotated_and_numbered(self):
        self.attach()
        self.assertIsNone(self.live.open())
        first = self.live.next_frame(0, timeout=3)
        self.assertIsNotNone(first)
        seq, jpeg = first
        frame = Image.open(io.BytesIO(jpeg))
        self.assertEqual(frame.size, (640, 360))
        red, green, blue = frame.convert("RGB").getpixel((630, 3))
        self.assertTrue(red > 130 and green < 60 and blue < 60, "placeholder banner should be burned in")
        second = self.live.next_frame(seq, timeout=3)
        self.assertGreater(second[0], seq)
        self.live.close()

    def test_no_frames_are_grabbed_while_the_detector_is_busy(self):
        self.worker.is_idle = False
        self.attach()
        self.assertIsNone(self.live.open())
        time.sleep(0.3)
        self.assertEqual(self.camera.grabs, 0)
        self.assertIsNone(self.live.next_frame(0, timeout=0.1))
        self.live.close()

    def test_nothing_runs_without_viewers(self):
        self.attach()
        time.sleep(0.2)
        self.assertEqual(self.camera.grabs, 0)

    def test_detach_ends_the_stream_and_stops_the_producer(self):
        self.attach()
        self.live.open()
        self.live.next_frame(0, timeout=3)
        self.live.detach()
        self.assertFalse(self.live.active())
        self.assertIsNone(self.live.next_frame(10**6, timeout=0.2))
        grabs = self.camera.grabs
        time.sleep(0.2)
        self.assertEqual(self.camera.grabs, grabs)

    def test_model_named_by_the_config_is_the_one_used(self):
        (self.models / "other.onnx").write_bytes(b"x")
        self.live.attach(self.camera, SimpleNamespace(detection_enabled=True, model_id="other", detection_confidence=0.25), self.worker)
        self.assertEqual(self.live.find_model().name, "other.onnx")
        self.live.attach(self.camera, SimpleNamespace(detection_enabled=True, model_id="missing", detection_confidence=0.25), self.worker)
        self.assertIsNone(self.live.find_model())


class StreamTests(unittest.TestCase):
    """The real HTTP server with the fake camera: the multipart stream a phone's <img> would read."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        models = Path(self.tmp.name) / "models"
        models.mkdir()
        (models / "ant_test.onnx").write_bytes(b"x")
        self.live = LiveView(models)
        self.service = SimpleNamespace(live=self.live, status=lambda: {}, latest_peek=lambda: b"")
        self.server = start_control_server(self.service, Storage(Path(self.tmp.name)), 0)
        self.port = self.server.server_address[1]
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.live.detach)

    def test_stream_delivers_complete_jpeg_parts_and_frees_the_slot_on_disconnect(self):
        self.live.attach(FakeCamera(), SimpleNamespace(detection_enabled=False, detection_confidence=0.25), FakeWorker())
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("GET", "/api/live")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn(f"boundary={LIVE_BOUNDARY}", response.getheader("Content-Type"))
        for _ in range(2):
            self.assertEqual(response.readline().strip(), f"--{LIVE_BOUNDARY}".encode())
            self.assertEqual(response.readline().strip(), b"Content-Type: image/jpeg")
            length = int(response.readline().split(b":")[1])
            self.assertEqual(response.readline(), b"\r\n")
            body = response.read(length)
            self.assertEqual(Image.open(io.BytesIO(body)).size, (640, 360))
            self.assertEqual(response.readline(), b"\r\n")
        self.assertEqual(self.live.clients, 1)
        response.close()   # the response holds the socket open until it is closed too
        connection.close()
        deadline = time.monotonic() + 5
        while self.live.clients and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(self.live.clients, 0)

    def test_refused_when_there_is_no_session(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("GET", "/api/live")
        response = connection.getresponse()
        self.assertEqual(response.status, 409)
        self.assertIn(b"live_not_available", response.read())


if __name__ == "__main__":
    unittest.main()
