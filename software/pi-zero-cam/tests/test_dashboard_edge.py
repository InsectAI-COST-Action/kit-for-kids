"""The shared dashboard against cards written by the real Pi writer: edge-detector results, and cards without them.

Needs Playwright and Microsoft Edge (or Chrome); skipped otherwise:
  py -m unittest tests.test_dashboard_edge -v        (from software/pi-zero-cam)

A card is built with insectcam.capture (Session, DashboardWriter) exactly as the camera writes it, the dashboard
files are copied from the ESP32 project, and the card is served from its root over local HTTP.
Set INSECTCAM_SCREENSHOT_DIR to keep screenshots.
"""

import functools
import http.server
import io
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from insectcam.capture import Config, Session, Storage  # noqa: E402

DASHBOARD = HERE.parent / "TomA-insect-ESP32-software" / "dashboard"
FILES = ("dashboard.html", "dashboard.css", "dashboard.js", "settings.js", "analysis.js", "edge-results.js",
         "card-access.js", "i18n.js", "favicon.svg", "site.webmanifest")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (640, 360), (120, 140, 90)).save(buffer, "JPEG")
    return buffer.getvalue()


def detection(n, ms=410):
    predictions = [SimpleNamespace(class_id=0, label="Ant", confidence=0.3 + 0.01 * i, x=0.05 + 0.012 * i, y=0.2 + 0.005 * i,
                                   w=0.05, h=0.07) for i in range(n)]
    return SimpleNamespace(outcome="ok", elapsed_ms=ms, predictions=predictions,
                           max_confidence=max((p.confidence for p in predictions), default=0.0))


def record(session, storage, n, boxes):
    capture_id = session.next_capture_id()
    image_path = session.image_path(capture_id)
    storage.write_atomic(image_path, jpeg())
    session.record(capture_id=capture_id, uptime_ms=1000 * n, scheduled_ms=1000 * n, outcome="completed", width=640,
                   height=360, jpeg_bytes=3000, capture_ms=100, image_path=image_path, save_outcome="saved",
                   detection=detection(boxes) if boxes is not None else None)
    return capture_id


def build_card(root: Path, model: bool) -> Storage:
    storage = Storage(root)
    for name in FILES:
        shutil.copy(DASHBOARD / name, root / name)
    (root / "vendor").mkdir(exist_ok=True)
    for name in ("manifest.js", "summary.js"):
        pass
    cfg = Config(model_id="ant_test" if model else "none")
    kwargs = dict(model_sha256="ab" * 32, model_status="placeholder_unvalidated") if model else {}
    # Run 1 is finished (closed chunk + boxes file listed in the manifest); run 2 is left open (current files).
    first = Session(storage, cfg, "IMX708", "boot_1", **kwargs)
    first.begin()
    for n in range(1, 13):
        record(first, storage, n, (n % 4) * 7 if model else None)    # 0, 7, 14, 21 boxes
    first.dashboard.finish()
    first.finish()
    second = Session(storage, cfg, "IMX708", "boot_2", **kwargs)
    second.begin()
    for n in range(1, 4):
        record(second, storage, n, 9 if model else None)
    return storage


@unittest.skipUnless(sync_playwright and DASHBOARD.is_dir(), "playwright or the dashboard is not available")
class DashboardEdgeTests(unittest.TestCase):
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

    def open_card(self, model: bool):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        build_card(Path(tmp.name), model)
        # Served from the card's root over HTTP: the camera's image paths start with "/images/", which a drive's
        # file:// URL resolves against the drive root but a temporary folder's does not.
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        handler = functools.partial(Quiet, directory=tmp.name)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        page = self.browser.new_page(viewport={"width": 1300, "height": 1000})
        self.addCleanup(page.close)
        self.errors = []
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/dashboard.html")
        page.wait_for_function("() => document.querySelector('#loading-screen').hidden", timeout=15000)
        return page

    def shot(self, page, name):
        folder = os.environ.get("INSECTCAM_SCREENSHOT_DIR")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)

    # ---- a card whose camera ran the detector
    def test_card_with_results_says_so_and_labels_them_as_a_test_model(self):
        page = self.open_card(model=True)
        note = page.inner_text("#model-note")
        self.assertIn("test", note.lower())
        self.assertIn("15", note)                                   # 12 + 3 pictures with results
        self.assertNotIn("does not run AI on its own", note)
        self.assertFalse(page.is_hidden("#edge-panel"))
        self.assertIn("not ants", page.inner_text("#edge-panel").lower())
        self.assertEqual(page.locator(".edge-badge").count(), 10)    # the gallery's ten newest
        self.shot(page, "edge-1-front")
        self.assertEqual(self.errors, [])

    def test_frame_viewer_draws_labelled_boxes_and_the_slider_changes_them(self):
        page = self.open_card(model=True)
        page.evaluate("() => { document.querySelector('.adult-details').open = true; }")
        page.fill("#search", "run_000002_img_3")                     # 9 boxes, in the open (current) chunk
        page.locator(".gallery-item").first.click()
        page.wait_for_function("() => document.querySelector('#edge-controls') && !document.querySelector('#edge-controls').hidden")
        page.wait_for_function("() => /\\d+ of \\d+ boxes shown/.test(document.querySelector('.edge-shown').textContent)", timeout=8000)
        self.assertIn("9 of 9", page.inner_text(".edge-shown"))
        painted = page.evaluate("""() => {
            const c = document.querySelector('.edge-overlay'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let blue = 0; for (let i = 0; i < d.length; i += 4) if (d[i + 2] > 200 && d[i] < 80 && d[i + 3] > 0) blue += 1;
            const banner = c.getContext('2d').getImageData(4, 4, 1, 1).data;       // the red TEST MODEL band
            return { blue, bannerRed: banner[0] > 150 && banner[1] < 40 && banner[3] > 200 };
        }""")
        self.assertGreater(painted["blue"], 50)
        self.assertTrue(painted["bannerRed"], "the TEST MODEL banner must be burned into the overlay")
        self.assertIn("test model", page.inner_text(".edge-model-line").lower())
        page.evaluate("() => { const s = document.querySelector('#edge-threshold'); s.value = '0.35'; s.dispatchEvent(new Event('input')); }")
        shown = page.inner_text(".edge-shown")
        self.assertNotIn("9 of 9", shown)                             # scores run 0.30-0.38: some fall under 35%
        self.shot(page, "edge-2-frame")
        self.assertEqual(self.errors, [])

    def test_a_photo_from_a_closed_chunk_loads_its_boxes_lazily(self):
        page = self.open_card(model=True)
        self.assertEqual(page.evaluate("Object.keys(window.InsectData.detections || {}).length"), 0)   # nothing loaded up front
        page.evaluate("() => { document.querySelector('.adult-details').open = true; }")
        page.locator("#capture-toggle").click()
        row = page.locator("#capture-rows tr", has_text="run_000001_img_3").first    # 3 % 4 * 7 = 21 boxes, closed chunk 1
        row.locator("button").click()
        page.wait_for_function("() => /\\d+ of \\d+ boxes shown/.test(document.querySelector('.edge-shown').textContent)", timeout=8000)
        self.assertIn("21 of 21", page.inner_text(".edge-shown"))

    def test_table_columns_filters_and_spanish(self):
        page = self.open_card(model=True)
        page.evaluate("() => { document.querySelector('.adult-details').open = true; }")
        header = lambda: [h.lower() for h in page.locator("#capture-rows").locator("xpath=ancestor::table//th").all_inner_texts()]
        self.assertIn("boxes (test)", header())          # the table styles its headers in capitals
        page.check("#edge-only-boxes")
        rows = page.locator("#capture-rows tr").count()
        page.locator("#capture-toggle").click()
        self.assertGreater(page.locator("#capture-rows tr").count(), rows - 1)
        page.evaluate("() => window.i18n.setLocale('es')")
        self.assertIn("prueba", page.inner_text("#model-note").lower())
        self.assertIn("cajas (prueba)", header())
        self.assertEqual(self.errors, [])

    # ---- a card with no detector: a XIAO's, or a Pi with detection off
    def test_card_without_a_model_shows_nothing_new(self):
        page = self.open_card(model=False)
        self.assertIn("does not run AI on its own", page.inner_text("#model-note"))
        self.assertTrue(page.is_hidden("#edge-panel"))
        self.assertEqual(page.locator(".edge-badge").count(), 0)
        page.evaluate("() => { document.querySelector('.adult-details').open = true; }")
        self.assertEqual(page.locator("th.edge-col").count(), 0)
        self.assertTrue(page.locator(".edge-filters").first.is_hidden())
        page.locator(".gallery-item").first.click()
        self.assertTrue(page.locator("#edge-controls").is_hidden())
        self.shot(page, "edge-3-xiao-style")
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
