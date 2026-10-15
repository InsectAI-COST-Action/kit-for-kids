"""Camera, session service and entry point for the Pi insect camera.

Storage formats and session bookkeeping live in capture.py; the phone web app
in control.py. Run:  python3 -m insectcam.service --data-root /srv/insectcam
"""

from __future__ import annotations

import argparse
import io
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from insectcam.capture import (FIRMWARE_VERSION, FRAME_SIZES, PEEK_SIZE, PERFORMANCE_HEADER,
                               PERFORMANCE_SAMPLE_INTERVAL, Config, Session, Storage)


# --------------------------------------------------------------------------- camera

class Camera:
    """IMX708 streaming continuously; main stream for saved photos, lores for the peek."""

    def __init__(self, config: Config) -> None:
        from libcamera import controls  # imported here so --help works without a camera stack
        from picamera2 import Picamera2
        self.picam = Picamera2()
        self.size = FRAME_SIZES[config.frame_size]
        frame_us = int(1_000_000 / config.sensor_fps)
        camera_config = self.picam.create_still_configuration(
            main={"size": self.size, "format": "RGB888"},
            lores={"size": PEEK_SIZE, "format": "YUV420"},
            buffer_count=2,
            controls={"FrameDurationLimits": (frame_us, frame_us),
                      "AfMode": controls.AfModeEnum.Continuous})
        self.picam.configure(camera_config)
        self.picam.options["quality"] = config.jpeg_quality
        self.picam.start()
        self.sensor_id = str(self.picam.camera_properties.get("Model", "unknown")).upper()

    def warm_up(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.picam.capture_metadata()

    def capture(self) -> tuple[bytes, bytes, int, int]:
        """One frame: (photo JPEG, peek JPEG, capture_ms, encode_ms). The peek is ~20 KB, ~7 ms."""
        started = time.monotonic()
        request = self.picam.capture_request()
        captured = time.monotonic()
        try:
            buffer = io.BytesIO()
            request.save("main", buffer, format="jpeg")
            encoded = time.monotonic()
            peek = self._peek_jpeg(request.make_array("lores"))
        finally:
            request.release()
        return buffer.getvalue(), peek, int((captured - started) * 1000), int((encoded - captured) * 1000)

    @staticmethod
    def _peek_jpeg(yuv) -> bytes:
        import simplejpeg
        width, height = PEEK_SIZE
        stride = yuv.shape[1]
        half = (height // 2) * (stride // 2)
        chroma = yuv[height:].reshape(-1)
        u = chroma[:half].reshape(height // 2, stride // 2)[:, : width // 2]
        v = chroma[half: 2 * half].reshape(height // 2, stride // 2)[:, : width // 2]
        return simplejpeg.encode_jpeg_yuv_planes(yuv[:height, :width], u, v, quality=80)

    def status(self) -> str:
        md = self.picam.capture_metadata()
        return (f"AfState={md.get('AfState')} lens={md.get('LensPosition', 0):.2f} "
                f"exposure_us={md.get('ExposureTime')} gain={md.get('AnalogueGain', 0):.2f} "
                f"colour_gains={tuple(round(g, 2) for g in md.get('ColourGains', ()))} "
                f"sensor_temp={md.get('SensorTemperature')}")

    def close(self) -> None:
        self.picam.stop()
        self.picam.close()


def soc_health() -> tuple[str, str]:
    try:
        millidegrees = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
        temperature = f"{millidegrees / 1000:.1f}"
    except (OSError, ValueError):
        temperature = ""
    try:
        throttled = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True,
                                   timeout=2).stdout.strip().split("=")[-1]
    except (OSError, subprocess.SubprocessError):
        throttled = ""
    return temperature, throttled


def report(message: str) -> None:
    print(f"[insect-logger] {message}", flush=True)


# --------------------------------------------------------------------------- service

class Service:
    """Runs sessions back to back as the phone app asks.

    States, as the shared phone page expects: warming_up -> capturing ->
    safe_to_remove (after Finish or the session's maximum length), or error.
    Unlike the XIAO, "start again" begins a new session in-process; nothing
    reboots. The camera is closed between sessions, so a finished camera makes
    no sensor heat.
    """

    def __init__(self, storage: Storage, warmup_s: float) -> None:
        self.storage = storage
        self.warmup_s = warmup_s
        self.lock = threading.Lock()
        self.state = "starting"
        self.error = ""
        self.error_code = ""
        self.run_id = ""
        self.capture_count = 0
        self.saved_count = 0
        self.session_started = 0.0
        self.session_ended = 0.0  # freezes elapsedMs once a session finishes
        self.peek = b""
        self.stop_requested = threading.Event()
        self.start_requested = threading.Event()
        self.shutdown = threading.Event()
        self.boot_id = f"boot_{int(time.time() * 1000) % 10**9}"

    # --- called from the web server thread
    def status(self) -> dict:
        with self.lock:
            end = self.session_ended or time.monotonic()
            elapsed = int((end - self.session_started) * 1000) if self.session_started else 0
            return {"state": self.state, "runId": self.run_id, "captureCount": self.capture_count,
                    "savedCount": self.saved_count, "elapsedMs": elapsed,
                    "sdMounted": self.storage.root.is_dir(), "error": self.error, "errorCode": self.error_code,
                    "hasPeek": bool(self.peek), "motionRecent": []}

    def latest_peek(self) -> bytes:
        with self.lock:
            return self.peek

    def is_capturing(self) -> bool:
        with self.lock:
            return self.state in ("capturing", "warming_up", "starting")

    def request_stop(self) -> None:
        self.stop_requested.set()

    def request_start(self) -> bool:
        if self.is_capturing():
            return False
        self.start_requested.set()
        return True

    # --- main thread
    def run(self) -> None:
        while not self.shutdown.is_set():
            self.run_session()
            # Finished: wait for "start another adventure" (or service stop).
            while not self.shutdown.is_set() and not self.start_requested.wait(0.5):
                pass
            self.start_requested.clear()

    def run_session(self) -> None:
        self.stop_requested.clear()
        with self.lock:
            self.state, self.error, self.error_code = "warming_up", "", ""
            self.capture_count = self.saved_count = 0
            self.peek = b""
            self.session_started = time.monotonic()
            self.session_ended = 0.0
        config, note = Config.load(self.storage.path("config.json"))
        report(note)
        try:
            camera = Camera(config)
        except Exception as error:  # no camera: say so on the phone rather than crash-looping
            report(f"fatal camera failure: {error}")
            with self.lock:
                self.state, self.error, self.error_code = "error", f"Camera failure: {error}", "camera_failed"
            self.stop_requested.wait()
            return
        report(f"camera initialised: {camera.sensor_id} {camera.size[0]}x{camera.size[1]} "
               f"q{config.jpeg_quality}, sensor {config.sensor_fps:g} fps, autofocus continuous")
        session = Session(self.storage, config, camera.sensor_id, self.boot_id)
        report(self.storage.tidy_root())
        try:
            for line in session.begin():
                report(line)
            with self.lock:
                self.run_id = session.run_id
            performance_path = f"system/performance_{session.run_id}.csv"
            if not self.storage.path(performance_path).is_file():
                self.storage.append_line(performance_path, PERFORMANCE_HEADER)
            camera.warm_up(self.warmup_s)
            report(f"camera warm-up complete ({self.warmup_s:g} s): {camera.status()}")
            with self.lock:
                self.state = "capturing"
                self.session_started = time.monotonic()
            self.capture_loop(camera, session, config, performance_path)
        finally:
            session.finish()
            camera.close()
            with self.lock:
                self.session_ended = time.monotonic()
                if self.state != "error":
                    self.state = "safe_to_remove"
            report(f"session complete: {session.run_id}, {session.sequence} captures; safe to remove")

    def capture_loop(self, camera: Camera, session: Session, config: Config, performance_path: str) -> None:
        interval = config.capture_interval_ms / 1000
        session_start = time.monotonic()
        next_due = session_start
        while not self.stop_requested.is_set():
            if config.max_session_seconds and time.monotonic() - session_start >= config.max_session_seconds:
                report("maximum session length reached")
                return
            delay = next_due - time.monotonic()
            if delay > 0:
                self.stop_requested.wait(min(delay, 0.5))
                continue
            total_start = time.monotonic()
            scheduled_ms = int((next_due - session.started) * 1000)
            start_lag_ms = int((total_start - next_due) * 1000)
            capture_id = session.next_capture_id()
            image_path = session.image_path(capture_id)
            outcome, save_outcome, error_code = "completed", "saved", ""
            jpeg, peek, capture_ms, encode_ms, write_ms = b"", b"", 0, 0, 0
            try:
                jpeg, peek, capture_ms, encode_ms = camera.capture()
            except Exception as error:  # camera faults must not stop the session
                outcome, save_outcome, error_code, image_path = "capture_error", "not_attempted", type(error).__name__, ""
                report(f"capture failed: {error}")
            if outcome == "completed":
                write_start = time.monotonic()
                try:
                    self.storage.write_atomic(image_path, jpeg)
                except OSError as error:
                    outcome, save_outcome, error_code, image_path = "storage_error", "failed", "image_write_failed", ""
                    report(f"image write failed: {error}")
                write_ms = int((time.monotonic() - write_start) * 1000)
            raw_ms = dashboard_ms = 0
            try:
                raw_ms, dashboard_ms = session.record(
                    capture_id=capture_id, uptime_ms=session.uptime_ms(), scheduled_ms=scheduled_ms, outcome=outcome,
                    width=camera.size[0] if jpeg else 0, height=camera.size[1] if jpeg else 0,
                    jpeg_bytes=len(jpeg), capture_ms=capture_ms + encode_ms, image_path=image_path,
                    save_outcome=save_outcome, error_code=error_code)
            except OSError as error:
                report(f"capture log failure: {error}")
            with self.lock:
                self.capture_count += 1
                if outcome == "completed":
                    self.saved_count += 1
                if peek:
                    self.peek = peek
            total_ms = int((time.monotonic() - total_start) * 1000)
            if session.sequence % PERFORMANCE_SAMPLE_INTERVAL == 0:
                temperature, throttled = soc_health()
                self.storage.append_line(performance_path, ",".join(map(str, [
                    capture_id, scheduled_ms, start_lag_ms, capture_ms, encode_ms, write_ms, raw_ms, dashboard_ms,
                    total_ms, len(jpeg), outcome, temperature, throttled])))
                report(f"performance {capture_id}: total {total_ms} ms (encode {encode_ms}, write {write_ms}), "
                       f"soc {temperature} C, throttled {throttled}; {camera.status()}")
            next_due += interval
            if time.monotonic() > next_due + interval:
                report("capture cadence overrun; schedule rebased without backlog")
                next_due = time.monotonic() + interval


def main() -> int:
    parser = argparse.ArgumentParser(description="Pi Zero 2 W insect camera service")
    parser.add_argument("--data-root", type=Path, default=Path("/srv/insectcam"))
    parser.add_argument("--warmup-s", type=float, default=3.0, help="let AF/AE/AWB settle before the first capture")
    parser.add_argument("--http-port", type=int, default=80, help="phone control app port (0 = off)")
    parser.add_argument("--once", action="store_true", help="run one session, then exit (testing)")
    args = parser.parse_args()

    storage = Storage(args.data_root)
    storage.ensure_dir("system")
    service = Service(storage, args.warmup_s)

    def handle_signal(signum, frame):  # noqa: ARG001 - signal handler signature
        service.shutdown.set()
        service.stop_requested.set()
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    report(f"firmware {FIRMWARE_VERSION} starting; data root {args.data_root}")
    if args.http_port:
        from insectcam.control import start_control_server
        start_control_server(service, storage, args.http_port)
        report(f"control app ready on port {args.http_port}")
    if args.once:
        service.run_session()
    else:
        service.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
