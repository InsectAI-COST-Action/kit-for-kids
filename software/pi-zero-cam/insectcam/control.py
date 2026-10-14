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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from insectcam.capture import QUALITY_PRESETS, Config, Storage

PAGE = (Path(__file__).with_name("control_app.html")).read_bytes()
ALLOWED_INTERVALS_MS = (1000, 2000, 30000, 60000)   # the page's choices, as on the XIAO
ALLOWED_DURATIONS_S = (60, 300, 1800, 3600, 0)


def page_view(config: Config) -> dict:
    """The setting as the shared page reads it: it only knows 'QXGA' (high) vs 'VGA' q24 (low)."""
    low = (config.frame_size, config.jpeg_quality) == QUALITY_PRESETS["low"]
    return {"schema_version": 1, "capture_fps": 1, "capture_interval_ms": config.capture_interval_ms,
            "max_session_seconds": config.max_session_seconds, "capture_mode": config.capture_mode,
            "camera_preset": config.camera_preset, "motion_trigger_enabled": False, "motion_threshold": 5,
            "frame_size": "VGA" if low else "QXGA", "jpeg_quality": 24 if low else 12,
            "model_id": config.model_id, "pi_frame_size": config.frame_size, "pi_jpeg_quality": config.jpeg_quality}


def start_control_server(service, storage: Storage, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "insectcam"

        def log_message(self, format, *args):  # noqa: A002 - quiet; the service logs what matters
            pass

        def send(self, code: int, body: bytes = b"", content_type: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
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
            else:
                self.send_json(404, {"error": "Not found."})

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
            if form["motionTriggerEnabled"] == "true":
                # Not built on the Pi yet; refuse rather than save a setting that would be ignored.
                self.send_json(400, {"error": "This camera cannot save only when something moves yet.",
                                     "errorCode": "motion_not_supported"})
                return
            frame_size, quality = QUALITY_PRESETS[form["quality"]]
            pilot = interval_ms == 1000 and form["quality"] == "high" and duration_s == 3600
            duration_id = "infinite" if duration_s == 0 else f"{duration_s}s"
            preset = ("imx708_3mp_q85_1fps" if pilot
                      else f"custom_{form['quality']}_{interval_ms}ms_{duration_id}")
            config = {"schema_version": 1, "capture_fps": 1, "capture_interval_ms": interval_ms,
                      "max_session_seconds": duration_s, "capture_mode": "pilot" if pilot else "custom",
                      "camera_preset": preset, "frame_size": frame_size, "jpeg_quality": quality,
                      "motion_trigger_enabled": False, "motion_threshold": 5, "model_id": "none",
                      "log_level": "info"}
            storage.write_atomic("config.json", json.dumps(config, indent=2) + "\n")
            self.send_json(202, {"accepted": True})

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="control-app", daemon=True).start()
    return server
