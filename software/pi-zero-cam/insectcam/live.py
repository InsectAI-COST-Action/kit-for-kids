"""Live view: camera frames shown only after the detector has run on them, boxes burned in.

Pi only. A producer thread runs while at least one phone is watching: it takes
the newest 640x360 frame from the camera, hands it to the DetectorWorker as a
best-effort job (capture-frame jobs always win, so live view can never delay
the photos or the records), draws the boxes and the PLACEHOLDER banner into the
frame, and publishes the JPEG. Pace is set by the detector: about 2-3 frames
per second.

Delivery is one JPEG per request (control.py: GET /api/live/frame, a long-poll),
not a multipart/x-mixed-replace stream: current Chromium/Edge do not render that
in an <img> (tested 15 October 2026 with Edge 155, four format variants), so the
page fetches frames itself. A viewer is a random id the page sends with every
request; it counts as watching while its requests keep arriving, so a phone
that vanishes frees its slot after VIEWER_TIMEOUT_S with nothing to clean up.

The detector is shared with recording when recording is on; otherwise the live
view loads its own and frees it when the last viewer leaves.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

from insectcam.detector import DEFAULT_CONFIDENCE, Detector, DetectorWorker, draw_detections

DETECTOR_THREADS = 3
JPEG_QUALITY = 78
MAX_CLIENTS = 2
VIEWER_TIMEOUT_S = 6.0        # a viewer that has not asked for a frame for this long has gone
MAX_VIEW_SECONDS = 600.0      # one viewing session; limits CPU and heat if a phone is left open
RESULT_TIMEOUT_S = 5.0


def report(message: str) -> None:
    print(f"[insect-logger] {message}", flush=True)


class LiveView:
    def __init__(self, model_dir: Path, max_clients: int = MAX_CLIENTS, threads: int = DETECTOR_THREADS,
                 viewer_timeout: float = VIEWER_TIMEOUT_S, max_view_seconds: float = MAX_VIEW_SECONDS) -> None:
        self.model_dir = Path(model_dir)
        self.max_clients = max_clients
        self.threads = threads
        self.viewer_timeout = viewer_timeout
        self.max_view_seconds = max_view_seconds
        self._cond = threading.Condition()
        self._attached = False
        self._camera = None
        self._config = None
        self._shared_worker: DetectorWorker | None = None
        self._own_worker: DetectorWorker | None = None
        self._thread: threading.Thread | None = None
        self._viewers: dict[str, list[float]] = {}   # id -> [first seen, last seen] (monotonic seconds)
        self._seq = 0
        self._jpeg = b""
        self.error = ""

    # --- model
    def find_model(self) -> Path | None:
        """The model the config names, else the first .onnx installed (None if there is none)."""
        config = self._config
        if config is not None and getattr(config, "detection_enabled", False):
            path = self.model_dir / f"{config.model_id}.onnx"
            return path if path.is_file() else None
        try:
            models = sorted(self.model_dir.glob("*.onnx"))
        except OSError:
            return None
        return models[0] if models else None

    def default_model_id(self) -> str | None:
        """The model recording would use when switched on: the first .onnx installed (None if there is none)."""
        try:
            models = sorted(self.model_dir.glob("*.onnx"))
        except OSError:
            return None
        return models[0].stem if models else None

    def model_installed(self) -> bool:
        try:
            return any(self.model_dir.glob("*.onnx"))
        except OSError:
            return False

    # --- session lifecycle (called by the capture service)
    def attach(self, camera, config, worker: DetectorWorker | None) -> None:
        with self._cond:
            self._camera, self._config, self._shared_worker = camera, config, worker
            self._attached = True
            self._viewers.clear()
            self._seq, self._jpeg, self.error = 0, b"", ""

    def detach(self) -> None:
        with self._cond:
            self._attached = False
            self._camera = None
            self._viewers.clear()
            thread = self._thread
            self._cond.notify_all()
        if thread is not None:
            thread.join(timeout=8)
        self._stop_own_worker()

    def active(self) -> bool:
        with self._cond:
            return self._attached

    def available(self) -> bool:
        with self._cond:
            return self._attached and self.find_model() is not None

    # --- viewers (called by the web server threads)
    def _prune(self, now: float) -> None:
        for viewer, (_, last_seen) in list(self._viewers.items()):
            if now - last_seen > self.viewer_timeout:
                del self._viewers[viewer]

    def touch(self, viewer: str) -> str | None:
        """A viewer asked for a frame. Returns None if it may watch, else an error code for the page."""
        now = time.monotonic()
        with self._cond:
            self._prune(now)
            if not self._attached:
                return "live_not_available"
            if self.find_model() is None:
                return "no_model_installed"
            record = self._viewers.get(viewer)
            if record is None:
                if len(self._viewers) >= self.max_clients:
                    return "live_busy"
                record = self._viewers[viewer] = [now, now]
            elif now - record[0] > self.max_view_seconds:
                del self._viewers[viewer]
                return "live_time_up"
            record[1] = now
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, name="live-view", daemon=True)
                self._thread.start()
        return None

    def leave(self, viewer: str) -> None:
        with self._cond:
            self._viewers.pop(viewer, None)
            self._cond.notify_all()

    def next_frame(self, after: int, timeout: float) -> tuple[int, bytes] | None:
        with self._cond:
            self._cond.wait_for(lambda: self._seq > after or not self._attached or bool(self.error), timeout)
            if self._seq > after:
                return self._seq, self._jpeg
        return None

    @property
    def clients(self) -> int:
        with self._cond:
            self._prune(time.monotonic())
            return len(self._viewers)

    # --- producer
    def _ensure_own_worker(self, model_path: Path, confidence: float) -> DetectorWorker | None:
        if self._own_worker is not None:
            return self._own_worker
        try:
            detector = Detector(model_path, threads=self.threads, confidence=confidence)
        except Exception as error:
            self.error = "model_load_failed"
            report(f"live view cannot load {model_path} ({error})")
            return None
        self._own_worker = DetectorWorker(detector)
        self._own_worker.start()
        report(f"live view: loaded {model_path.stem} ({detector.size}px)")
        return self._own_worker

    def _stop_own_worker(self) -> None:
        worker, self._own_worker = self._own_worker, None
        if worker is not None:
            worker.stop()

    def _loop(self) -> None:
        try:
            while True:
                with self._cond:
                    self._prune(time.monotonic())
                    if not self._viewers or not self._attached:
                        self._thread = None
                        return
                    camera, config, shared = self._camera, self._config, self._shared_worker
                worker = shared
                if worker is None:
                    model = self.find_model()
                    confidence = getattr(config, "detection_confidence", DEFAULT_CONFIDENCE)
                    worker = self._ensure_own_worker(model, confidence) if model is not None else None
                    if worker is None:
                        with self._cond:
                            self._thread = None
                            self._cond.notify_all()
                        return
                if not worker.idle():
                    time.sleep(0.02)
                    continue
                try:
                    image = camera.grab_rgb()
                except Exception:
                    time.sleep(0.2)
                    continue
                ticket = worker.try_detect_live(image)
                if ticket is None or not ticket.done.wait(RESULT_TIMEOUT_S) or ticket.result is None:
                    continue
                buffer = io.BytesIO()
                draw_detections(image, ticket.result).save(buffer, "JPEG", quality=JPEG_QUALITY)
                with self._cond:
                    self._seq += 1
                    self._jpeg = buffer.getvalue()
                    self._cond.notify_all()
        finally:
            with self._cond:
                if self._thread is threading.current_thread():
                    self._thread = None
                nobody = not self._viewers
            if nobody:
                self._stop_own_worker()
