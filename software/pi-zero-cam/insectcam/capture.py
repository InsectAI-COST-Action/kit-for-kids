"""Pi Zero 2 W insect camera capture service.

Port of the XIAO ESP32S3 firmware's capture loop (src/main.cpp,
session_logger.cpp, dashboard_writer.cpp in ../TomA-insect-ESP32-software).
It writes the same files in the same layout and formats, so the existing
offline dashboard and tools/audit_card.py read a Pi card unchanged:

  config.json                         read once at start (optional)
  raw/captures.csv                    one row per capture attempt (authoritative)
  raw/detections.csv                  header only (null model)
  raw/runs/<run_id>.json              run manifest, "running" -> "finished"
                                      (or "interrupted_power_removed" next start)
  images/<run_id>/shard_NNNN/<capture_id>.jpg   100 images per shard
  data/captures_current.js, data/captures_NNNNNN.js  dashboard chunks of 100
  manifest.js, summary.js             dashboard index
  system/next_run.txt, active_run.txt, dashboard_state.txt
  system/performance_<run_id>.csv     timing sample every 97th capture

Every file is written atomically (temporary file, fsync, rename) and every
CSV/chunk line is fsynced, matching the ESP32's data-safety contract: after
power loss, completed captures survive and a half-written image never appears
under its final name.

Differences from the ESP32, all deliberate:
  - Camera: Raspberry Pi Camera Module 3 (IMX708) via Picamera2, streaming
    continuously at a low sensor frame rate (default 5 fps) with continuous
    autofocus, auto exposure and auto white balance always running. Each
    scheduled capture takes the next frame and JPEG-encodes it; nothing is
    re-initialised between frames, so AF/AE/AWB never reset.
  - Default size 2304x1296 (3 MP; the ESP32 pilot is QXGA, 3.1 MP).
  - Time stays session-relative (uptime_ms since this process started,
    captured_at_utc empty), as on the ESP32: a kit has no internet clock.

Run:  python3 -m insectcam.capture --data-root /srv/insectcam
Stop: Ctrl+C or SIGTERM (systemd); the run is then marked "finished".
"""

from __future__ import annotations

import argparse
import io
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1
FIRMWARE_VERSION = "pi-0.1.0-dev"
CHUNK_SIZE = 100
SHARD_SIZE = 100
PERFORMANCE_SAMPLE_INTERVAL = 97  # prime, so samples do not land on chunk promotions (see ESP32 docs)

CAPTURE_HEADER = (
    "schema_version,device_id,run_id,boot_id,capture_id,captured_at_utc,uptime_ms,scheduled_ms,"
    "outcome,frame_width,frame_height,jpeg_bytes,capture_ms,inference_ms,model_id,prediction_count,"
    "max_confidence,image_path,save_policy,save_outcome,motion_score,motion_threshold,error_code")
DETECTION_HEADER = (
    "schema_version,run_id,capture_id,prediction_index,label_id,label,confidence,bbox_x,bbox_y,"
    "bbox_w,bbox_h,model_id,metadata_json")
PERFORMANCE_HEADER = (
    "capture_id,scheduled_ms,start_lag_ms,capture_ms,encode_ms,image_write_ms,raw_csv_ms,dashboard_ms,"
    "total_ms,jpeg_bytes,outcome,cpu_temp_c,throttled")

FRAME_SIZES = {"3MP": (2304, 1296), "12MP": (4608, 2592)}


# --------------------------------------------------------------------------- config

@dataclass
class Config:
    capture_interval_ms: int = 1000
    max_session_seconds: int = 3600       # 0 = until stopped
    frame_size: str = "3MP"
    jpeg_quality: int = 85
    sensor_fps: float = 5.0               # streaming rate; AF/AE need frames, heat scales with it
    capture_mode: str = "pilot"
    camera_preset: str = "imx708_3mp_q85_1fps"
    model_id: str = "none"

    @classmethod
    def load(cls, path: Path) -> tuple["Config", str]:
        config = cls()
        if not path.is_file():
            return config, "config.json missing; using defaults"
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            return config, f"config.json unreadable ({error}); using defaults"
        for key in ("capture_interval_ms", "max_session_seconds", "jpeg_quality"):
            if key in data:
                setattr(config, key, int(data[key]))
        for key in ("frame_size", "capture_mode", "camera_preset", "model_id"):
            if key in data:
                setattr(config, key, str(data[key]))
        if "sensor_fps" in data:
            config.sensor_fps = float(data["sensor_fps"])
        # Same spirit as the ESP32's safety bounds: refuse values that cannot
        # be delivered rather than silently doing something else.
        problems = []
        if config.capture_interval_ms not in (1000, 2000, 5000, 30000, 60000):
            problems.append("capture_interval_ms")
        if config.max_session_seconds not in (0, 60, 300, 1800, 3600):
            problems.append("max_session_seconds")
        if config.frame_size not in FRAME_SIZES:
            problems.append("frame_size")
        if not 50 <= config.jpeg_quality <= 95:
            problems.append("jpeg_quality")
        if not 1.0 <= config.sensor_fps <= 15.0:
            problems.append("sensor_fps")
        if problems:
            return cls(), f"config.json has unsupported {', '.join(problems)}; using defaults"
        return config, f"config.json loaded: {config.capture_mode}/{config.camera_preset}"


# --------------------------------------------------------------------------- storage

class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, relative: str) -> Path:
        return self.root / relative.lstrip("/")

    def ensure_dir(self, relative: str) -> None:
        self.path(relative).mkdir(parents=True, exist_ok=True)

    def write_atomic(self, relative: str, data: bytes | str) -> None:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        payload = data.encode("utf-8") if isinstance(data, str) else data
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        self._sync_dir(target.parent)

    def append_line(self, relative: str, line: str) -> None:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_text(self, relative: str) -> str:
        target = self.path(relative)
        return target.read_text(encoding="utf-8").strip() if target.is_file() else ""

    @staticmethod
    def _sync_dir(directory: Path) -> None:
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def csv_escape(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"' if any(c in escaped for c in ',"\n') else escaped


# --------------------------------------------------------------------------- dashboard chunks

class DashboardWriter:
    """Same chunk/manifest/summary files and recovery rules as dashboard_writer.cpp."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        state = storage.read_text("system/dashboard_state.txt")
        if state:
            closed, captures = state.split(",", 1)
            self.closed_chunks, self.closed_captures = int(closed), int(captures)
        else:
            self.closed_chunks, self.closed_captures = 0, 0
        self.current_count = 0
        self.current_path = "data/captures_current.js"
        self._recover()

    def _recover(self) -> None:
        current = self.storage.path(self.current_path)
        if not current.is_file():
            return
        lines = [line for line in current.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            current.unlink()
            return
        self.current_count = len(lines)
        self._promote()

    def append(self, record: dict) -> None:
        line = ("window.InsectData=window.InsectData||{captures:[],addCapture:function(c){this.captures.push(c);}};"
                f"window.InsectData.addCapture({json.dumps(record, separators=(',', ':'))});")
        self.storage.append_line(self.current_path, line)
        self.current_count += 1
        if self.current_count >= CHUNK_SIZE:
            self._promote()

    def finish(self) -> None:
        if self.current_count > 0:
            self._promote()
        self._write_summary()

    def _promote(self) -> None:
        chunk_id = self.closed_chunks + 1
        final = self.storage.path(f"data/captures_{chunk_id:06d}.js")
        os.replace(self.storage.path(self.current_path), final)
        Storage._sync_dir(final.parent)
        self.closed_chunks += 1
        self.closed_captures += self.current_count
        self.current_count = 0
        self.storage.write_atomic("system/dashboard_state.txt", f"{self.closed_chunks},{self.closed_captures}")
        chunks = ",".join(f'"data/captures_{index:06d}.js"' for index in range(1, self.closed_chunks + 1))
        self.storage.write_atomic(
            "manifest.js",
            'window.InsectData=window.InsectData||{};window.InsectData.manifest={"schemaVersion":1,'
            f'"captureChunks":[{chunks}],"lastCommittedCaptureCount":{self.closed_captures}}};\n')
        self._write_summary()

    def _write_summary(self) -> None:
        self.storage.write_atomic(
            "summary.js",
            'window.InsectData=window.InsectData||{};window.InsectData.summary={"schemaVersion":1,'
            f'"committedCaptures":{self.closed_captures},'
            '"note":"Closed chunks plus captures_current.js are shown; raw CSV is authoritative."};\n')


# --------------------------------------------------------------------------- session

@dataclass
class Session:
    storage: Storage
    config: Config
    sensor_id: str
    boot_id: str
    run_id: str = ""
    sequence: int = 0
    dashboard: DashboardWriter | None = None
    started: float = field(default_factory=time.monotonic)

    def begin(self) -> list[str]:
        notes = []
        active = self.storage.read_text("system/active_run.txt")
        if active:
            manifest_path = f"raw/runs/{active}.json"
            manifest = self.storage.read_text(manifest_path)
            if manifest:
                self.storage.write_atomic(
                    manifest_path, manifest.replace('"state": "running"', '"state": "interrupted_power_removed"') + "\n")
            self.storage.path("system/active_run.txt").unlink(missing_ok=True)
            notes.append(f"previous run {active} marked interrupted_power_removed")
        previous = self.storage.read_text("system/next_run.txt")
        counter = (int(previous) + 1) if previous.isdigit() else 1
        self.storage.write_atomic("system/next_run.txt", str(counter))
        self.run_id = f"run_{counter:06d}"
        self.storage.ensure_dir(f"images/{self.run_id}")
        self.storage.ensure_dir("raw/runs")
        if not self.storage.path("raw/captures.csv").is_file():
            self.storage.append_line("raw/captures.csv", CAPTURE_HEADER)
        if not self.storage.path("raw/detections.csv").is_file():
            self.storage.append_line("raw/detections.csv", DETECTION_HEADER)
        self.dashboard = DashboardWriter(self.storage)
        self.write_manifest("running")
        self.storage.write_atomic("system/active_run.txt", self.run_id)
        notes.append(f"session started: {self.run_id}")
        return notes

    def uptime_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def next_capture_id(self) -> str:
        self.sequence += 1
        return f"{self.run_id}_img_{self.sequence}"

    def image_path(self, capture_id: str) -> str:
        # Leading slash, exactly as the ESP32 records it (main.cpp imagePathFor):
        # the dashboard and tools/audit_card.py compare these paths as text.
        shard = (self.sequence - 1) // SHARD_SIZE + 1
        return f"/images/{self.run_id}/shard_{shard:04d}/{capture_id}.jpg"

    def record(self, *, capture_id: str, uptime_ms: int, scheduled_ms: int, outcome: str, width: int, height: int,
               jpeg_bytes: int, capture_ms: int, image_path: str, save_outcome: str, error_code: str = "") -> tuple[int, int]:
        row = ",".join([
            str(SCHEMA_VERSION), "device_000001", csv_escape(self.run_id), self.boot_id, csv_escape(capture_id), "",
            str(uptime_ms), str(scheduled_ms), outcome, str(width), str(height), str(jpeg_bytes), str(capture_ms),
            "0", csv_escape(self.config.model_id), "0", "0.0000", csv_escape(image_path), "every_frame",
            save_outcome, "-1.000", "0", csv_escape(error_code)])
        started = time.monotonic()
        self.storage.append_line("raw/captures.csv", row)
        raw_ms = int((time.monotonic() - started) * 1000)
        started = time.monotonic()
        assert self.dashboard is not None
        self.dashboard.append({
            "runId": self.run_id, "captureId": capture_id, "uptimeMs": uptime_ms, "outcome": outcome,
            "imagePath": image_path, "width": width, "height": height, "jpegBytes": jpeg_bytes,
            "captureMs": capture_ms, "inferenceMs": 0, "inferenceOutcome": "model_unavailable",
            "motionScore": -1.0, "motionThreshold": 0.0})
        return raw_ms, int((time.monotonic() - started) * 1000)

    def finish(self) -> None:
        if self.dashboard:
            self.dashboard.finish()
        self.write_manifest("finished")
        self.storage.path("system/active_run.txt").unlink(missing_ok=True)

    def write_manifest(self, state: str) -> None:
        c = self.config
        manifest = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "state": state, "sensor": self.sensor_id,
            "model_id": c.model_id, "capture_mode": c.capture_mode, "camera_preset": c.camera_preset,
            "capture_fps": 1, "capture_interval_ms": c.capture_interval_ms,
            "max_session_seconds": c.max_session_seconds, "motion_trigger_enabled": False, "motion_threshold": 5,
            "frame_size": c.frame_size, "jpeg_quality": c.jpeg_quality, "time_source": "session_relative",
            "platform": "raspberry_pi_zero_2_w", "firmware": FIRMWARE_VERSION, "sensor_fps": c.sensor_fps}
        # Key order and "key": value spacing match the ESP32's manifests, which
        # markPreviousRunInterrupted() relies on for its text replacement.
        self.storage.write_atomic(f"raw/runs/{self.run_id}.json", json.dumps(manifest, indent=2) + "\n")


# --------------------------------------------------------------------------- camera

class Camera:
    def __init__(self, config: Config) -> None:
        from libcamera import controls  # imported here so --help works without a camera stack
        from picamera2 import Picamera2
        self.picam = Picamera2()
        self.size = FRAME_SIZES[config.frame_size]
        frame_us = int(1_000_000 / config.sensor_fps)
        camera_config = self.picam.create_still_configuration(
            main={"size": self.size, "format": "RGB888"},
            buffer_count=2,
            controls={"FrameDurationLimits": (frame_us, frame_us),
                      "AfMode": controls.AfModeEnum.Continuous})
        self.picam.configure(camera_config)
        self.picam.options["quality"] = config.jpeg_quality
        self.picam.start()
        model = self.picam.camera_properties.get("Model", "unknown")
        self.sensor_id = str(model).upper()

    def warm_up(self, seconds: float) -> dict:
        deadline = time.monotonic() + seconds
        metadata = {}
        while time.monotonic() < deadline:
            metadata = self.picam.capture_metadata()
        return metadata

    def capture_jpeg(self) -> tuple[bytes, int, int]:
        """Returns (jpeg bytes, capture_ms, encode_ms)."""
        started = time.monotonic()
        request = self.picam.capture_request()
        captured = time.monotonic()
        try:
            buffer = io.BytesIO()
            request.save("main", buffer, format="jpeg")
        finally:
            request.release()
        encoded = time.monotonic()
        return buffer.getvalue(), int((captured - started) * 1000), int((encoded - captured) * 1000)

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
        import subprocess
        throttled = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True,
                                   timeout=2).stdout.strip().split("=")[-1]
    except (OSError, subprocess.SubprocessError):
        throttled = ""
    return temperature, throttled


# --------------------------------------------------------------------------- main loop

def report(message: str) -> None:
    print(f"[insect-logger] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pi Zero 2 W insect camera capture service")
    parser.add_argument("--data-root", type=Path, default=Path("/srv/insectcam"))
    parser.add_argument("--warmup-s", type=float, default=3.0, help="let AF/AE/AWB settle before the first capture")
    args = parser.parse_args()

    stop = {"requested": False}

    def request_stop(signum, frame):  # noqa: ARG001 - signal handler signature
        stop["requested"] = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    storage = Storage(args.data_root)
    storage.ensure_dir("system")
    config, note = Config.load(storage.path("config.json"))
    report(f"firmware {FIRMWARE_VERSION} starting; data root {args.data_root}")
    report(note)
    camera = Camera(config)
    report(f"camera initialised: {camera.sensor_id} {camera.size[0]}x{camera.size[1]} "
           f"q{config.jpeg_quality}, sensor {config.sensor_fps:g} fps, autofocus continuous")
    boot_id = f"boot_{int(time.time() * 1000) % 10**9}"
    session = Session(storage, config, camera.sensor_id, boot_id)
    for line in session.begin():
        report(line)
    performance_path = f"system/performance_{session.run_id}.csv"
    if not storage.path(performance_path).is_file():
        storage.append_line(performance_path, PERFORMANCE_HEADER)

    camera.warm_up(args.warmup_s)
    report(f"camera warm-up complete ({args.warmup_s:g} s): {camera.status()}")

    interval = config.capture_interval_ms / 1000
    session_start = time.monotonic()
    next_due = session_start
    try:
        while not stop["requested"]:
            if config.max_session_seconds and time.monotonic() - session_start >= config.max_session_seconds:
                report("maximum session length reached")
                break
            delay = next_due - time.monotonic()
            if delay > 0:
                time.sleep(min(delay, 0.5))
                continue
            total_start = time.monotonic()
            scheduled_ms = int((next_due - session.started) * 1000)
            start_lag_ms = int((total_start - next_due) * 1000)
            capture_id = session.next_capture_id()
            image_path = session.image_path(capture_id)
            outcome, save_outcome, error_code = "completed", "saved", ""
            jpeg, capture_ms, encode_ms, write_ms = b"", 0, 0, 0
            try:
                jpeg, capture_ms, encode_ms = camera.capture_jpeg()
            except Exception as error:  # camera faults must not stop the session
                outcome, save_outcome, error_code, image_path = "capture_error", "not_attempted", type(error).__name__, ""
                report(f"capture failed: {error}")
            if outcome == "completed":
                write_start = time.monotonic()
                try:
                    storage.write_atomic(image_path, jpeg)
                except OSError as error:
                    outcome, save_outcome, error_code, image_path = "storage_error", "failed", "image_write_failed", ""
                    report(f"image write failed: {error}")
                write_ms = int((time.monotonic() - write_start) * 1000)
            uptime_ms = session.uptime_ms()
            raw_ms = dashboard_ms = 0
            try:
                raw_ms, dashboard_ms = session.record(
                    capture_id=capture_id, uptime_ms=uptime_ms, scheduled_ms=scheduled_ms, outcome=outcome,
                    width=camera.size[0] if jpeg else 0, height=camera.size[1] if jpeg else 0,
                    jpeg_bytes=len(jpeg), capture_ms=capture_ms + encode_ms, image_path=image_path,
                    save_outcome=save_outcome, error_code=error_code)
            except OSError as error:
                report(f"capture log failure: {error}")
            total_ms = int((time.monotonic() - total_start) * 1000)
            if session.sequence % PERFORMANCE_SAMPLE_INTERVAL == 0:
                temperature, throttled = soc_health()
                storage.append_line(performance_path, ",".join(map(str, [
                    capture_id, scheduled_ms, start_lag_ms, capture_ms, encode_ms, write_ms, raw_ms, dashboard_ms,
                    total_ms, len(jpeg), outcome, temperature, throttled])))
                report(f"performance {capture_id}: total {total_ms} ms (encode {encode_ms}, write {write_ms}), "
                       f"soc {temperature} C, throttled {throttled}; {camera.status()}")
            next_due += interval
            if time.monotonic() > next_due + interval:
                report("capture cadence overrun; schedule rebased without backlog")
                next_due = time.monotonic() + interval
    finally:
        session.finish()
        camera.close()
        report(f"session complete: {session.run_id}, {session.sequence} captures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
