"""Tests for the Pi-only phone page section and the endpoints behind it (insectcam/control.py, pi_extras.html).

  py -m unittest discover tests        (from software/pi-zero-cam)
"""

import http.client
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam import control  # noqa: E402
from insectcam.capture import Storage  # noqa: E402
from insectcam.live import LiveView  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[1] / "insectcam"
SHARED_PAGE = (PACKAGE / "control_app.html").read_text(encoding="utf-8")
EXTRAS = (PACKAGE / "pi_extras.html").read_text(encoding="utf-8")


class PageSpliceTests(unittest.TestCase):
    def test_every_anchor_is_in_the_shared_page_exactly_once(self):
        """If re-extracting the page from the XIAO firmware moves an anchor, this fails loudly."""
        for name, anchor in {**control.INSERT_AFTER, **control.INSERT_BEFORE}.items():
            self.assertEqual(SHARED_PAGE.count(anchor), 1, name)

    def test_extras_have_a_section_for_every_anchor(self):
        self.assertEqual(set(control.split_extras(EXTRAS)), set(control.INSERT_AFTER) | set(control.INSERT_BEFORE))

    def test_built_page_has_the_pi_features_once_and_the_shared_page_intact(self):
        page = control.build_page(SHARED_PAGE, EXTRAS)
        for element in ('id="btnLive"', 'id="cfgDetect"', 'id="liveNote"', 'id="detectHint"'):
            self.assertEqual(page.count(element), 1, element)
        for element in ('id="btnPeek"', 'id="cfgMotion"', 'id="peekStage"', 'id="btnSaveConfig"'):
            self.assertEqual(page.count(element), 1, element)
        self.assertNotIn("@@", page)
        self.assertNotIn("Pi-only additions", page)               # the file's leading comment is not served
        self.assertLess(page.index('id="btnPeek"'), page.index('id="btnLive"'))          # beside the peek button
        self.assertLess(page.index('id="cfgMotion"'), page.index('id="cfgDetect"'))      # with the settings
        self.assertEqual(SHARED_PAGE.count("</body>"), 1)
        self.assertTrue(page.rstrip().endswith("</html>"))

    def test_a_moved_anchor_raises_instead_of_silently_dropping_the_ui(self):
        broken = SHARED_PAGE.replace('id="btnPeek"', 'id="btnLook"')
        with self.assertRaises(RuntimeError):
            control.build_page(broken, EXTRAS)

    def test_the_served_page_still_works_if_the_extras_cannot_be_added(self):
        # load_page falls back to the shared page (and logs) rather than stopping the camera.
        original = control.build_page
        control.build_page = lambda page, extras: (_ for _ in ()).throw(RuntimeError("anchor moved"))
        try:
            page = control.load_page().decode("utf-8")
        finally:
            control.build_page = original
        self.assertNotIn('id="btnLive"', page)
        self.assertIn('id="btnPeek"', page)

    def test_every_new_string_exists_in_both_languages(self):
        script = EXTRAS[EXTRAS.index("<script>"):]
        blocks = re.findall(r"Object\.assign\(TRANSLATIONS\.(en|es), \{(.*?)\n  \}\);", script, re.S)
        keys = {lang: set(re.findall(r"'(control\.[A-Za-z]+)':", body)) for lang, body in blocks}
        self.assertEqual(set(keys), {"en", "es"})
        self.assertEqual(keys["en"], keys["es"])
        for key in re.findall(r"t\('(control\.[A-Za-z]+)'\)", script):
            # a string is either added here or already in the shared page's own table
            self.assertTrue(key in keys["en"] or f"'{key}':" in SHARED_PAGE, key)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_injected_script_is_valid_javascript(self):
        script = re.search(r"<script>(.*)</script>", EXTRAS, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extras.js"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.models = self.root / "models"
        self.models.mkdir()
        self.live = LiveView(self.models)
        self.service = SimpleNamespace(live=self.live, status=lambda: {}, latest_peek=lambda: b"")
        self.storage = Storage(self.root)
        self.server = control.start_control_server(self.service, self.storage, 0)
        self.port = self.server.server_address[1]
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, **form):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()
        body = json.loads(response.read() or b"{}")
        connection.close()
        return response.status, body

    def config(self):
        return json.loads((self.root / "config.json").read_text())

    def test_switching_detection_on_picks_the_installed_model_and_keeps_other_settings(self):
        (self.models / "ant_test.onnx").write_bytes(b"x")
        (self.root / "config.json").write_text(json.dumps({"capture_interval_ms": 2000, "frame_size": "1MP"}))
        self.assertEqual(self.post("/api/model", enabled="true")[0], 202)
        self.assertEqual(self.config(), {"capture_interval_ms": 2000, "frame_size": "1MP", "model_id": "ant_test"})
        self.assertEqual(self.post("/api/model", enabled="false")[0], 202)
        self.assertEqual(self.config()["model_id"], "none")

    def test_switching_on_with_no_model_installed_is_refused(self):
        status, body = self.post("/api/model", enabled="true")
        self.assertEqual((status, body["errorCode"]), (409, "no_model_installed"))
        self.assertFalse((self.root / "config.json").exists())

    def test_saving_page_settings_keeps_the_detection_settings(self):
        (self.root / "config.json").write_text(json.dumps({"model_id": "ant_test", "detection_confidence": 0.4}))
        status, _ = self.post("/api/config", intervalMs="2000", quality="high", durationSeconds="300",
                              motionTriggerEnabled="false")
        self.assertEqual(status, 202)
        saved = self.config()
        self.assertEqual((saved["model_id"], saved["detection_confidence"], saved["capture_interval_ms"]),
                         ("ant_test", 0.4, 2000))

    def test_page_is_served_with_the_pi_extras(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request("GET", "/")
        page = connection.getresponse().read().decode("utf-8")
        connection.close()
        self.assertIn('id="btnLive"', page)


if __name__ == "__main__":
    unittest.main()
