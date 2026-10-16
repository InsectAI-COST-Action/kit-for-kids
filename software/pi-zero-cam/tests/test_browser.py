"""Real-browser check of the Pi phone page: Live view and the detection switch, against the real server.

Needs Playwright and Microsoft Edge (or Chrome); skipped otherwise:
  py -m pip install playwright      (no browser download: it drives the installed Edge)
  py -m unittest tests.test_browser -v        (from software/pi-zero-cam)

A fake camera and detector stand in for the hardware; everything else (the page with the Pi extras spliced in,
the HTTP server, the live-view producer, the MJPEG stream, the settings endpoints) is the real code.
Set INSECTCAM_SCREENSHOT_DIR to keep screenshots of each state.
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam import control  # noqa: E402
from insectcam import detector as d  # noqa: E402
from insectcam.capture import Storage  # noqa: E402
from insectcam.live import LiveView  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


class FakeCamera:
    """Frames with a dark 'ant' that moves, so successive live frames differ."""
    def __init__(self):
        self.n = 0

    def grab_rgb(self):
        self.n += 1
        frame = Image.new("RGB", (640, 360), (200, 190, 170))
        ImageDraw.Draw(frame).ellipse([100 + self.n * 6 % 400, 150, 130 + self.n * 6 % 400, 175], fill=(30, 20, 15))
        return frame


class FakeWorker:
    def idle(self):
        return True

    def try_detect_live(self, image):
        x = (self.last_x if hasattr(self, "last_x") else 0.2)
        ticket = SimpleNamespace(done=threading.Event(), result=d.DetectionResult(
            d.OUTCOME_OK, 321, [d.Prediction(0, "Ant", 0.77, x, 0.4, 0.06, 0.08)]))
        ticket.done.set()
        return ticket


def jpeg_bytes():
    import io
    buffer = io.BytesIO()
    Image.new("RGB", (640, 360), (90, 120, 150)).save(buffer, "JPEG")
    return buffer.getvalue()


@unittest.skipUnless(sync_playwright, "playwright is not installed")
class PhonePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        for channel in ("msedge", "chrome"):
            try:
                cls.browser = cls.playwright.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                continue
        else:
            cls.playwright.stop()
            raise unittest.SkipTest("neither Microsoft Edge nor Chrome could be launched")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.root = root
        models = root / "models"
        models.mkdir()
        (models / "ant_test.onnx").write_bytes(b"x")
        self.live = LiveView(models)
        self.camera, self.worker = FakeCamera(), FakeWorker()
        self.live.attach(self.camera, SimpleNamespace(detection_enabled=False, detection_confidence=0.25), self.worker)
        live = self.live
        self.service = SimpleNamespace(
            live=live, latest_peek=lambda: jpeg_bytes(), request_stop=lambda: None, request_start=lambda: True,
            status=lambda: {"state": "capturing", "runId": "run_000001", "captureCount": 12, "savedCount": 12,
                            "elapsedMs": 12000, "sdMounted": True, "error": "", "errorCode": "", "hasPeek": True,
                            "motionRecent": [], "features": ["live", "detect"], "liveAvailable": live.available(),
                            "liveClients": live.clients, "modelInstalled": live.model_installed(),
                            "detectionEnabled": False})
        self.server = control.start_control_server(self.service, Storage(root), 0)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.live.detach)
        self.page = self.browser.new_page(viewport={"width": 420, "height": 900})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def shot(self, name):
        folder = os.environ.get("INSECTCAM_SCREENSHOT_DIR")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)

    def wait_for_model_id(self, wanted, seconds=6):
        """The 'Saved' message is already on screen from the previous toggle, so wait for the file itself."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if json.loads((self.root / "config.json").read_text()).get("model_id") == wanted:
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        self.fail(f"config.json never got model_id {wanted!r}")

    def test_live_view_streams_annotated_frames_and_stops_cleanly(self):
        page = self.page
        page.goto(self.url)
        page.wait_for_selector("#btnLive:not([hidden])", timeout=8000)
        self.assertFalse(page.is_disabled("#btnLive"))
        self.assertIn("Live view", page.inner_text("#btnLive"))
        self.shot("1-before")

        page.click("#btnLive")
        page.wait_for_function("() => { const i = document.getElementById('liveImg'); return i && !i.hidden && i.naturalWidth === 640; }",
                               timeout=8000)
        page.wait_for_function("() => { const i = document.getElementById('liveImg'); return i.naturalHeight === 360; }", timeout=8000)
        self.assertIn("Stop live view", page.inner_text("#btnLive"))
        self.assertFalse(page.is_hidden("#liveNote"))
        self.assertIn("not reliable", page.inner_text("#liveNote"))
        self.assertEqual(page.evaluate("document.getElementById('peekStage').classList.contains('live-on')"), True)
        # A moving stream: the picture changes between two moments.
        first = page.evaluate("document.getElementById('liveImg').src")
        page.wait_for_timeout(1500)
        self.assertEqual(self.live.clients, 1)
        self.assertGreater(self.camera.n, 3)
        self.shot("2-live")

        page.click("#btnLive")
        self.assertIn("Live view", page.inner_text("#btnLive"))
        self.assertEqual(page.evaluate("document.getElementById('peekStage').classList.contains('live-on')"), False)
        page.wait_for_function("() => true")
        deadline = page.evaluate("Date.now()") + 6000
        while self.live.clients and page.evaluate("Date.now()") < deadline:
            page.wait_for_timeout(100)
        self.assertEqual(self.live.clients, 0, "the camera must stop streaming when live view is stopped")
        self.assertEqual(self.errors, [])
        del first

    def test_take_a_peek_during_live_view_ends_the_stream(self):
        page = self.page
        page.goto(self.url)
        page.wait_for_selector("#btnLive:not([hidden])", timeout=8000)
        page.click("#btnLive")
        page.wait_for_function("() => { const i = document.getElementById('liveImg'); return i && !i.hidden && i.naturalWidth === 640; }",
                               timeout=8000)
        page.wait_for_selector("#btnPeek:not([disabled])", timeout=8000)
        page.click("#btnPeek")
        page.wait_for_function("() => !document.getElementById('liveImg')", timeout=8000)
        self.assertIn("Live view", page.inner_text("#btnLive"))
        self.assertEqual(page.evaluate("document.getElementById('peekStage').classList.contains('live-on')"), False)
        self.assertEqual(self.errors, [])

    def test_live_view_button_is_disabled_when_there_is_no_session(self):
        self.live.detach()
        page = self.page
        page.goto(self.url)
        page.wait_for_selector("#btnLive:not([hidden])", timeout=8000)
        page.wait_for_function("() => document.getElementById('btnLive').disabled", timeout=8000)

    def test_detection_switch_saves_the_setting_and_says_when_it_applies(self):
        page = self.page
        page.goto(self.url)
        page.wait_for_function("() => !document.getElementById('detectRow').hidden", timeout=8000)
        page.evaluate("document.querySelector('.settings-details').open = true")   # it lives in the grown-up helper
        self.assertFalse(page.is_checked("#cfgDetect"))
        self.assertIn("test data", page.inner_text("#detectHint"))
        self.shot("3-settings")
        page.check("#cfgDetect")
        self.wait_for_model_id("ant_test")
        page.wait_for_function("() => document.getElementById('detectHint').textContent.includes('Saved')", timeout=8000)
        page.uncheck("#cfgDetect")
        self.wait_for_model_id("none")
        self.assertEqual(self.errors, [])

    def test_spanish_labels_follow_the_language_picker(self):
        page = self.page
        page.goto(self.url)
        page.wait_for_selector("#btnLive:not([hidden])", timeout=8000)
        # The page's own language picker rebuilds text through applyStaticText(), which the extras wrap.
        page.evaluate("() => { currentLocale = 'es'; applyStaticText(); }")
        self.assertIn("Vista en directo", page.inner_text("#btnLive"))
        self.assertIn("Detecci", page.text_content("#detectText"))   # inside the collapsed helper: text_content, not inner_text


if __name__ == "__main__":
    unittest.main()
