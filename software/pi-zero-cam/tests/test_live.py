"""Unit tests for the live view (insectcam/live.py) and its frame endpoint (insectcam/control.py).

Fake camera and worker stand in for the hardware; the HTTP tests talk to the real server.

  py -m unittest discover tests        (from software/pi-zero-cam)
"""

import http.client
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam import control  # noqa: E402
from insectcam import detector as d  # noqa: E402
from insectcam.capture import Storage  # noqa: E402
from insectcam.live import LiveView  # noqa: E402


class FakeCamera:
    def __init__(self):
        self.grabs = 0

    def grab_rgb(self):
        self.grabs += 1
        time.sleep(0.01)  # keeps the producer from spinning flat out
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


CONFIG = SimpleNamespace(detection_enabled=False, detection_confidence=0.25)


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
        self.live.attach(self.camera, CONFIG, self.worker)

    def test_touch_refuses_without_a_session_a_model_or_room(self):
        self.assertEqual(self.live.touch("viewer111"), "live_not_available")
        self.attach()
        (self.models / "ant_test.onnx").unlink()
        self.assertEqual(self.live.touch("viewer111"), "no_model_installed")
        (self.models / "ant_test.onnx").write_bytes(b"x")
        self.assertIsNone(self.live.touch("viewer111"))
        self.assertIsNone(self.live.touch("viewer222"))
        self.assertEqual(self.live.touch("viewer333"), "live_busy")      # a third viewer is refused
        self.assertIsNone(self.live.touch("viewer111"))                  # an existing viewer keeps its place
        self.live.leave("viewer222")
        self.assertIsNone(self.live.touch("viewer333"))                  # and a slot is free once one leaves
        self.assertEqual(self.live.clients, 2)

    def test_frames_are_annotated_and_numbered(self):
        self.attach()
        self.assertIsNone(self.live.touch("viewer111"))
        first = self.live.next_frame(0, timeout=3)
        self.assertIsNotNone(first)
        seq, jpeg = first
        frame = Image.open(io.BytesIO(jpeg))
        self.assertEqual(frame.size, (640, 360))
        red, green, blue = frame.convert("RGB").getpixel((630, 3))
        self.assertTrue(red > 130 and green < 60 and blue < 60, "placeholder banner should be burned in")
        self.assertGreater(self.live.next_frame(seq, timeout=3)[0], seq)

    def test_a_viewer_that_goes_quiet_frees_its_slot_and_stops_the_producer(self):
        live = LiveView(self.models, viewer_timeout=0.25)
        self.addCleanup(live.detach)
        live.attach(self.camera, CONFIG, self.worker)
        self.assertIsNone(live.touch("viewer111"))
        self.assertIsNotNone(live.next_frame(0, timeout=3))
        time.sleep(0.5)
        self.assertEqual(live.clients, 0)
        time.sleep(0.2)
        grabs = self.camera.grabs
        time.sleep(0.3)
        self.assertEqual(self.camera.grabs, grabs, "nobody is watching, so the camera must not be read")

    def test_one_viewing_session_is_limited_in_time(self):
        live = LiveView(self.models, max_view_seconds=0.2)
        self.addCleanup(live.detach)
        live.attach(self.camera, CONFIG, self.worker)
        self.assertIsNone(live.touch("viewer111"))
        time.sleep(0.3)
        self.assertEqual(live.touch("viewer111"), "live_time_up")
        self.assertEqual(live.clients, 0)
        self.assertIsNone(live.touch("viewer111"))   # a fresh start is allowed

    def test_no_frames_are_grabbed_while_the_detector_is_busy(self):
        self.worker.is_idle = False
        self.attach()
        self.assertIsNone(self.live.touch("viewer111"))
        time.sleep(0.3)
        self.assertEqual(self.camera.grabs, 0)
        self.assertIsNone(self.live.next_frame(0, timeout=0.1))

    def test_nothing_runs_without_viewers(self):
        self.attach()
        time.sleep(0.2)
        self.assertEqual(self.camera.grabs, 0)

    def test_detach_ends_viewing_and_stops_the_producer(self):
        self.attach()
        self.live.touch("viewer111")
        self.live.next_frame(0, timeout=3)
        self.live.detach()
        self.assertFalse(self.live.active())
        self.assertEqual(self.live.touch("viewer111"), "live_not_available")
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
        self.assertEqual(self.live.default_model_id(), "ant_test")


class FrameEndpointTests(unittest.TestCase):
    """The real HTTP server with the fake camera: what the phone page's fetch loop talks to."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        models = Path(self.tmp.name) / "models"
        models.mkdir()
        (models / "ant_test.onnx").write_bytes(b"x")
        self.live = LiveView(models)
        self.service = SimpleNamespace(live=self.live, status=lambda: {}, latest_peek=lambda: b"")
        self.original_wait = control.LIVE_WAIT_S
        control.LIVE_WAIT_S = 0.4
        self.addCleanup(setattr, control, "LIVE_WAIT_S", self.original_wait)
        self.server = control.start_control_server(self.service, Storage(Path(self.tmp.name)), 0)
        self.port = self.server.server_address[1]
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.live.detach)

    def request(self, method, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, body

    def test_frames_arrive_one_per_request_with_increasing_numbers(self):
        self.live.attach(FakeCamera(), CONFIG, FakeWorker())
        status, headers, body = self.request("GET", "/api/live/frame?id=viewer111&after=0")
        self.assertEqual((status, headers["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(Image.open(io.BytesIO(body)).size, (640, 360))
        seq = int(headers["X-Seq"])
        status, headers, body = self.request("GET", f"/api/live/frame?id=viewer111&after={seq}")
        self.assertEqual(status, 200)
        self.assertGreater(int(headers["X-Seq"]), seq)

    def test_204_when_nothing_newer_arrives_in_time(self):
        worker = FakeWorker()
        worker.is_idle = False   # the detector is busy, so no frame is produced
        self.live.attach(FakeCamera(), CONFIG, worker)
        self.assertEqual(self.request("GET", "/api/live/frame?id=viewer111&after=0")[0], 204)

    def test_refusals_carry_an_error_code_the_page_can_translate(self):
        status, _, body = self.request("GET", "/api/live/frame?id=viewer111&after=0")
        self.assertEqual((status, json.loads(body)["errorCode"]), (409, "live_not_available"))
        self.live.attach(FakeCamera(), CONFIG, FakeWorker())
        self.assertEqual(self.request("GET", "/api/live/frame?id=viewer111&after=0")[0], 200)
        self.assertEqual(self.request("GET", "/api/live/frame?id=viewer222&after=0")[0], 200)
        status, _, body = self.request("GET", "/api/live/frame?id=viewer333&after=0")
        self.assertEqual((status, json.loads(body)["errorCode"]), (503, "live_busy"))
        self.assertEqual(self.request("GET", "/api/live/frame?id=a&after=0")[0], 400)           # id too short
        self.assertEqual(self.request("GET", "/api/live/frame?id=../../etc&after=0")[0], 400)   # not an identifier

    def test_stop_frees_the_slot(self):
        self.live.attach(FakeCamera(), CONFIG, FakeWorker())
        self.request("GET", "/api/live/frame?id=viewer111&after=0")
        self.request("GET", "/api/live/frame?id=viewer222&after=0")
        self.assertEqual(self.live.clients, 2)
        self.assertEqual(self.request("POST", "/api/live/stop?id=viewer111")[0], 204)
        self.assertEqual(self.live.clients, 1)
        self.assertEqual(self.request("GET", "/api/live/frame?id=viewer333&after=0")[0], 200)


if __name__ == "__main__":
    unittest.main()
