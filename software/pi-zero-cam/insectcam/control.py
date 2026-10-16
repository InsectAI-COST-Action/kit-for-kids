"""Phone control app for the Pi camera: the XIAO's own page, the same API.

The page (control_app.html) is extracted from the ESP32 firmware by
tools/extract_control_app.py, so wording and translations stay identical. This
module answers the endpoints that page calls, with the same status fields,
states and error codes as ../TomA-insect-ESP32-software/src/control_server.cpp:

  GET  /api/status   state, runId, captureCount, savedCount, elapsedMs, ...
  POST /api/stop     finish the session safely (-> state safe_to_remove)
  POST /api/start    begin a new session (409 adventure_in_progress if one runs)
  GET  /api/peek     latest 640x360 preview JPEG (204 before the first frame)
  GET  /api/config   current setting, in the page's vocabulary
  POST /api/config   save a setting for the next session (validated here)

Any other path serves the page, so a phone's captive-portal check opens it.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from insectcam.capture import QUALITY_PRESETS, Config, Storage


# The page is shared with the XIAO (extracted from its firmware by tools/extract_control_app.py). Pi-only
# features are spliced in here, at serve time, from pi_extras.html, so the shared page and the XIAO build
# stay untouched. Each section goes at a fixed anchor of the shared page.
EXTRAS_MARKER = re.compile(r"<!-- @@([a-z-]+) -->\n")
INSERT_AFTER = {
    "after-peek-button": '<button class="btn-peek" id="btnPeek" data-i18n="control.takeAPeek">&#x1F441;&#xFE0F; Take a peek</button>',
    "after-motion-setting": '<label class="settings-check"><input type="checkbox" id="cfgMotion"> <span data-i18n="control.motionLabel">Save pictures only when something moves</span></label>',
}
INSERT_BEFORE = {"before-body-end": "</body>"}


def split_extras(extras: str) -> dict:
    """{marker name: html} for the sections of pi_extras.html (the text before the first marker is a comment)."""
    pieces = EXTRAS_MARKER.split(extras)
    return {pieces[i]: pieces[i + 1] for i in range(1, len(pieces) - 1, 2)}


def build_page(page: str, extras: str) -> str:
    """The shared page with the Pi-only sections inserted. Raises RuntimeError if an anchor has moved."""
    sections = split_extras(extras)
    for name, anchor in {**INSERT_AFTER, **INSERT_BEFORE}.items():
        if name not in sections:
            raise RuntimeError(f"pi_extras.html has no section {name!r}")
        if page.count(anchor) != 1:
            raise RuntimeError(f"shared page anchor for {name!r} found {page.count(anchor)} times (expected 1); "
                               "re-extracting the page from the firmware probably changed it")
    for name, anchor in INSERT_AFTER.items():
        page = page.replace(anchor, anchor + sections[name])
    for name, anchor in INSERT_BEFORE.items():
        page = page.replace(anchor, sections[name] + anchor)
    return page


def load_page() -> bytes:
    page = Path(__file__).with_name("control_app.html").read_text(encoding="utf-8")
    try:
        extras = Path(__file__).with_name("pi_extras.html").read_text(encoding="utf-8")
        return build_page(page, extras).encode("utf-8")
    except (OSError, RuntimeError) as error:
        # Never let a cosmetic mismatch stop the camera: serve the shared page without the Pi extras.
        print(f"[insect-logger] phone page: Pi extras not added ({error})", flush=True)
        return page.encode("utf-8")


PAGE = load_page()
LIVE_WAIT_S = 2.5                          # how long a frame request waits for a newer frame
VIEWER_ID = re.compile(r"[A-Za-z0-9]{6,32}")  # the page makes one up per live-view session
ALLOWED_INTERVALS_MS = (1000, 2000, 30000, 60000)   # the page's choices, as on the XIAO
ALLOWED_DURATIONS_S = (60, 300, 1800, 3600, 0)


def page_view(config: Config) -> dict:
    """The setting as the shared page reads it: it only knows 'QXGA' (high) vs 'VGA' q24 (low)."""
    low = (config.frame_size, config.jpeg_quality) == QUALITY_PRESETS["low"]
    return {"schema_version": 1, "capture_fps": 1, "capture_interval_ms": config.capture_interval_ms,
            "max_session_seconds": config.max_session_seconds, "capture_mode": config.capture_mode,
            "camera_preset": config.camera_preset, "motion_trigger_enabled": config.motion_trigger_enabled,
            "motion_threshold": config.motion_threshold,
            "frame_size": "VGA" if low else "QXGA", "jpeg_quality": 24 if low else 12,
            "model_id": config.model_id, "detection_confidence": config.detection_confidence,
            "pi_frame_size": config.frame_size, "pi_jpeg_quality": config.jpeg_quality}


def start_control_server(service, storage: Storage, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "insectcam"
        # Socket timeout for every request, including writes: a phone that disappears mid-stream (Wi-Fi
        # drop, no FIN) must not hold a live-view slot or a thread forever.
        timeout = 15

        def log_message(self, format, *args):  # noqa: A002 - quiet; the service logs what matters
            pass

        def send(self, code: int, body: bytes = b"", content_type: str = "application/json", headers: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def send_json(self, code: int, value: dict) -> None:
            self.send(code, json.dumps(value).encode("utf-8"))

        def do_GET(self):  # noqa: N802 - http.server naming
            path = urlparse(self.path).path
            if path == "/api/status":
                self.send_json(200, service.status())
            elif path == "/api/peek":
                peek = service.latest_peek()
                self.send(200, peek, "image/jpeg") if peek else self.send(204)
            elif path == "/api/config":
                config, _ = Config.load(storage.path("config.json"))
                self.send_json(200, page_view(config))
            elif path == "/api/live/frame":
                self.live_frame()
            else:
                self.send(200, PAGE, "text/html; charset=utf-8")

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/stop":
                service.request_stop()
                self.send_json(202, {"accepted": True})
            elif path == "/api/start":
                if service.request_start():
                    self.send_json(202, {"accepted": True})
                else:
                    self.send_json(409, {"error": "Finish the current adventure first.",
                                         "errorCode": "adventure_in_progress"})
            elif path == "/api/config":
                self.save_config()
            elif path == "/api/model":
                self.save_model()
            elif path == "/api/live/stop":
                self.live_stop()
            else:
                self.send_json(404, {"error": "Not found."})

        def live_frame(self) -> None:
            """GET /api/live/frame?id=<viewer>&after=<seq>: the next annotated frame (long-poll, one JPEG).

            200 image/jpeg with X-Seq; 204 if nothing newer arrives within LIVE_WAIT_S (ask again); 409 / 503 with
            an errorCode for the page when live view is not possible (not running, no model, two viewers already,
            ten minutes used). The request itself is the viewer's heartbeat (see insectcam/live.py).
            """
            query = parse_qs(urlparse(self.path).query)
            viewer = (query.get("id") or [""])[0]
            if not VIEWER_ID.fullmatch(viewer):
                self.send_json(400, {"error": "Bad viewer id.", "errorCode": "bad_request"})
                return
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            error = service.live.touch(viewer)
            if error is not None:
                self.send_json(503 if error == "live_busy" else 409, {"error": error, "errorCode": error})
                return
            item = service.live.next_frame(after, LIVE_WAIT_S)
            if item is None:
                self.send(204)
                return
            seq, jpeg = item
            self.send(200, jpeg, "image/jpeg", {"X-Seq": str(seq)})

        def live_stop(self) -> None:
            query = parse_qs(urlparse(self.path).query)
            viewer = (query.get("id") or [""])[0]
            if VIEWER_ID.fullmatch(viewer):
                service.live.leave(viewer)
            self.send(204)

        def save_model(self) -> None:
            """Switch recording of detections on or off for the next session (the model that is installed)."""
            length = int(self.headers.get("Content-Length") or 0)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8")).items()}
            if not storage.root.is_dir():
                self.send_json(409, {"error": "No camera card is mounted right now.", "errorCode": "no_card_mounted"})
                return
            model = "none"
            if form.get("enabled") == "true":
                model = service.live.default_model_id()
                if model is None:
                    self.send_json(409, {"error": "No detection model is installed.", "errorCode": "no_model_installed"})
                    return
            try:
                config = json.loads(storage.path("config.json").read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                config = {}
            config["model_id"] = model
            storage.write_atomic("config.json", json.dumps(config, indent=2) + "\n")
            self.send_json(202, {"accepted": True, "model_id": model})

        def save_config(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8")).items()}
            if not storage.root.is_dir():
                self.send_json(409, {"error": "No camera card is mounted right now.", "errorCode": "no_card_mounted"})
                return
            if not {"intervalMs", "quality", "durationSeconds", "motionTriggerEnabled"} <= form.keys():
                self.send_json(400, {"error": "Missing fields.", "errorCode": "missing_fields"})
                return
            try:
                interval_ms, duration_s = int(form["intervalMs"]), int(form["durationSeconds"])
            except ValueError:
                interval_ms = duration_s = -1
            if (interval_ms not in ALLOWED_INTERVALS_MS or duration_s not in ALLOWED_DURATIONS_S
                    or form["quality"] not in QUALITY_PRESETS):
                self.send_json(400, {"error": "Not a safe setting combination.", "errorCode": "unsafe_combination"})
                return
            motion = form["motionTriggerEnabled"] == "true"
            frame_size, quality = QUALITY_PRESETS[form["quality"]]
            pilot = not motion and interval_ms == 1000 and form["quality"] == "high" and duration_s == 3600
            duration_id = "infinite" if duration_s == 0 else f"{duration_s}s"
            preset = ("imx708_3mp_q85_1fps" if pilot
                      else f"custom_{form['quality']}_{interval_ms}ms_{duration_id}" + ("_motion" if motion else ""))
            config = {"schema_version": 1, "capture_fps": 1, "capture_interval_ms": interval_ms,
                      "max_session_seconds": duration_s, "capture_mode": "pilot" if pilot else "custom",
                      "camera_preset": preset, "frame_size": frame_size, "jpeg_quality": quality,
                      "motion_trigger_enabled": motion, "motion_threshold": 5, "model_id": "none",
                      "log_level": "info"}
            # The page only knows the settings above. Keep the detection settings it does not touch (they used
            # to be reset to "none" by every save), whether or not the old file was valid.
            try:
                previous = json.loads(storage.path("config.json").read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                previous = {}
            config.update({key: previous[key] for key in ("model_id", "detection_confidence") if key in previous})
            storage.write_atomic("config.json", json.dumps(config, indent=2) + "\n")
            self.send_json(202, {"accepted": True})

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="control-app", daemon=True).start()
    return server
