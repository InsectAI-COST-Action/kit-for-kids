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

This module holds the storage formats and session bookkeeping; the camera,
service loop and entry point are in service.py, the phone app in control.py.
Run:  python3 -m insectcam.service --data-root /srv/insectcam
"""

from __future__ import annotations

import json
import os
import re
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

FRAME_SIZES = {"1MP": (1536, 864), "3MP": (2304, 1296), "12MP": (4608, 2592)}
# The phone app's two quality choices (its page is shared with the XIAO, where
# they mean QXGA/q12 and VGA/q24).
QUALITY_PRESETS = {"high": ("3MP", 85), "low": ("1MP", 70)}
PEEK_SIZE = (640, 360)


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
    model_id: str = "none"                # "none" = no detection; otherwise the file name (without .onnx) of an installed model
    detection_confidence: float = 0.25    # minimum score for a recorded prediction
    motion_trigger_enabled: bool = False  # save only when the scene changes (see motion.py)
    motion_threshold: int = 5             # fixed at 5, as on the XIAO

    @property
    def detection_enabled(self) -> bool:
        return self.model_id not in ("", "none")

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
        if "detection_confidence" in data:
            config.detection_confidence = float(data["detection_confidence"])
        if "motion_trigger_enabled" in data:
            config.motion_trigger_enabled = bool(data["motion_trigger_enabled"])
        if "motion_threshold" in data:
            config.motion_threshold = int(data["motion_threshold"])
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
        if config.motion_threshold != 5:
            problems.append("motion_threshold")
        # model_id becomes a file name, so it must be a plain identifier (no paths).
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", config.model_id) or config.model_id.startswith("."):
            problems.append("model_id")
        if not 0.05 <= config.detection_confidence <= 0.95:
            problems.append("detection_confidence")
        if problems:
            return cls(), f"config.json has unsupported {', '.join(problems)}; using defaults"
        return config, f"config.json loaded: {config.capture_mode}/{config.camera_preset}"


# --------------------------------------------------------------------------- storage

# FAT "hidden" attribute, set through the kernel's FAT ioctls. Windows and macOS
# hide such entries by default, so the INSECT-AI drive shows a child only what
# they should open. Nothing is moved: the dashboard loads its support files by
# the same paths on a Pi card as on a XIAO card.
FAT_IOCTL_GET_ATTRIBUTES = 0x80047210
FAT_IOCTL_SET_ATTRIBUTES = 0x40047211
FAT_ATTR_HIDDEN = 0x02
VISIBLE_AT_ROOT = {"dashboard.html", "images", "System Volume Information"}


def fat_hidden(path: Path) -> bool | None:
    """True/False for a FAT file or directory, None if this is not a FAT filesystem."""
    try:
        import fcntl
        import struct
        fd = os.open(path, os.O_RDONLY)
        try:
            raw = fcntl.ioctl(fd, FAT_IOCTL_GET_ATTRIBUTES, struct.pack("I", 0))
        finally:
            os.close(fd)
        return bool(struct.unpack("I", raw)[0] & FAT_ATTR_HIDDEN)
    except (OSError, ImportError):
        return None


def set_fat_hidden(path: Path, hidden: bool = True) -> bool:
    try:
        import fcntl
        import struct
        fd = os.open(path, os.O_RDONLY)
        try:
            current = struct.unpack("I", fcntl.ioctl(fd, FAT_IOCTL_GET_ATTRIBUTES, struct.pack("I", 0)))[0]
            wanted = (current | FAT_ATTR_HIDDEN) if hidden else (current & ~FAT_ATTR_HIDDEN)
            if wanted != current:
                fcntl.ioctl(fd, FAT_IOCTL_SET_ATTRIBUTES, struct.pack("I", wanted))
        finally:
            os.close(fd)
        return True
    except (OSError, ImportError):
        return False


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def tidy_root(self) -> str:
        """Keep the top of the drive uncluttered for a child or teacher.

        Deletes FSCK####.REC files (fragments of photos cut off mid-save, which
        fsck.vfat salvages after every unclean stop) and hides everything at the
        root except the dashboard page and the photos folder.
        """
        removed = 0
        for leftover in self.root.glob("FSCK[0-9][0-9][0-9][0-9].REC"):
            try:
                leftover.unlink()
                removed += 1
            except OSError:
                pass
        hidden = 0
        for entry in self.root.iterdir():
            if entry.name not in VISIBLE_AT_ROOT and fat_hidden(entry) is False and set_fat_hidden(entry):
                hidden += 1
        return f"drive tidied: {removed} recovered fragment(s) removed, {hidden} support item(s) hidden"

    def path(self, relative: str) -> Path:
        return self.root / relative.lstrip("/")

    def ensure_dir(self, relative: str) -> None:
        self.path(relative).mkdir(parents=True, exist_ok=True)

    def write_atomic(self, relative: str, data: bytes | str) -> None:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        payload = data.encode("utf-8") if isinstance(data, str) else data
        # Replacing a file creates a new directory entry, which would lose the
        # hidden attribute of the manifest.js/summary.js/config.json being replaced.
        was_hidden = fat_hidden(target) if target.exists() else False
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        if was_hidden:
            set_fat_hidden(target)
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
    model_sha256: str = ""       # of the installed model file, when detection is enabled
    model_status: str = ""       # e.g. placeholder_unvalidated; copied into every prediction row

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
               jpeg_bytes: int, capture_ms: int, image_path: str, save_outcome: str, error_code: str = "",
               motion_score: float = -1.0, detection=None) -> tuple[int, int]:
        """`detection`: None when no model ran for this check (disabled, or a frame that was not kept),
        else an object with outcome, elapsed_ms, predictions (class_id, label, confidence, x, y, w, h) and
        max_confidence (insectcam.detector.DetectionResult)."""
        motion_on = self.config.motion_trigger_enabled
        threshold = self.config.motion_threshold if motion_on else 0
        inference_outcome = "model_unavailable"   # no model, or no inference for this check (as on the XIAO)
        inference_ms, predictions, max_confidence = 0, [], 0.0
        if detection is not None:
            inference_outcome = detection.outcome
            inference_ms = detection.elapsed_ms
            predictions = list(detection.predictions)
            max_confidence = detection.max_confidence
        row = ",".join([
            str(SCHEMA_VERSION), "device_000001", csv_escape(self.run_id), self.boot_id, csv_escape(capture_id), "",
            str(uptime_ms), str(scheduled_ms), outcome, str(width), str(height), str(jpeg_bytes), str(capture_ms),
            str(inference_ms), csv_escape(self.config.model_id), str(len(predictions)), f"{max_confidence:.4f}",
            csv_escape(image_path),
            "motion_trigger" if motion_on else "every_frame",
            save_outcome, f"{motion_score:.3f}", str(threshold), csv_escape(error_code)])
        started = time.monotonic()
        self.storage.append_line("raw/captures.csv", row)
        # Predictions after the capture row: a power cut can then lose predictions but never leave a
        # prediction for a capture that has no row.
        metadata = csv_escape(json.dumps({"model_status": self.model_status or "unspecified",
                                          "model_sha256": self.model_sha256}, separators=(",", ":")))
        for index, prediction in enumerate(predictions):
            self.storage.append_line("raw/detections.csv", ",".join([
                str(SCHEMA_VERSION), csv_escape(self.run_id), csv_escape(capture_id), str(index),
                str(prediction.class_id), csv_escape(prediction.label), f"{prediction.confidence:.4f}",
                f"{prediction.x:.5f}", f"{prediction.y:.5f}", f"{prediction.w:.5f}", f"{prediction.h:.5f}",
                csv_escape(self.config.model_id), metadata]))
        raw_ms = int((time.monotonic() - started) * 1000)
        started = time.monotonic()
        assert self.dashboard is not None
        self.dashboard.append({
            "runId": self.run_id, "captureId": capture_id, "uptimeMs": uptime_ms, "outcome": outcome,
            "imagePath": image_path, "width": width, "height": height, "jpegBytes": jpeg_bytes,
            "captureMs": capture_ms, "inferenceMs": inference_ms, "inferenceOutcome": inference_outcome,
            "motionScore": round(motion_score, 3), "motionThreshold": float(threshold)})
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
            "model_id": c.model_id, "model_sha256": self.model_sha256, "model_status": self.model_status,
            "detection_confidence": c.detection_confidence, "capture_mode": c.capture_mode, "camera_preset": c.camera_preset,
            "capture_fps": 1, "capture_interval_ms": c.capture_interval_ms,
            "max_session_seconds": c.max_session_seconds, "motion_trigger_enabled": c.motion_trigger_enabled,
            "motion_threshold": c.motion_threshold,
            "frame_size": c.frame_size, "jpeg_quality": c.jpeg_quality, "time_source": "session_relative",
            "platform": "raspberry_pi_zero_2_w", "firmware": FIRMWARE_VERSION, "sensor_fps": c.sensor_fps}
        # Key order and "key": value spacing match the ESP32's manifests, which
        # markPreviousRunInterrupted() relies on for its text replacement.
        self.storage.write_atomic(f"raw/runs/{self.run_id}.json", json.dumps(manifest, indent=2) + "\n")


