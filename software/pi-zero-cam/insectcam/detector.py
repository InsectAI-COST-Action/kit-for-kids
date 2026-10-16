"""On-device ant detection for the Pi camera: ONNX YOLO detector, worker thread, drawing.

Pure inference plumbing with no camera or web code, so it can be unit-tested on
a PC. The model is a swappable file: input size, class names and output layout
are read from the model itself, so a retrained detector drops in. Pre- and
post-processing are written here (letterbox, decode, NMS) rather than taken
from Ultralytics, so the camera needs only onnxruntime (MIT).

The only model available today (upstream `AntTestModel`, see
docs/edge-model-test.md) is a PLACEHOLDER: it finds dark specks on the Pi's
photos, not ants. Everything produced from it is labelled as such: the live
view burns PLACEHOLDER_BANNER into every frame, and recorded rows carry
`model_status: placeholder_unvalidated` (project brief: a stand-in must be
visibly marked and never pass for observations).

Output layouts understood:
  [1, 4+nc, N]  centre x/y, w, h, class scores (needs NMS)  - the provided ONNX
  [1, K, 6]     x1, y1, x2, y2, score, class (end-to-end)   - YOLO26's default export
"""

from __future__ import annotations

import ast
import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTCOME_OK = "ok"
OUTCOME_UNAVAILABLE = "model_unavailable"
OUTCOME_INVALID = "invalid_input"
OUTCOME_ERROR = "runtime_error"
OUTCOME_TIMEOUT = "timeout"

PLACEHOLDER_BANNER = "PLACEHOLDER MODEL - boxes are not reliable"
MODEL_STATUS = "placeholder_unvalidated"
DEFAULT_CONFIDENCE = 0.25
NMS_IOU = 0.7


# --------------------------------------------------------------------------- geometry and decoding

def letterbox(image: Image.Image, size: int) -> tuple[np.ndarray, float, int, int]:
    """Resize keeping aspect ratio onto a grey size x size canvas. Returns (1x3xSxS float32 0..1, scale, pad_x, pad_y)."""
    width, height = image.size
    scale = min(size / width, size / height)
    new_w, new_h = round(width * scale), round(height * scale)
    resized = image.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))
    array = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1) / 255.0
    return array[None], scale, pad_x, pad_y


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def nms(boxes: np.ndarray, scores: np.ndarray, threshold: float = NMS_IOU) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        order = np.array([j for j in order[1:] if iou(boxes[i], boxes[j]) < threshold], dtype=int)
    return keep


def _to_image_box(x1: float, y1: float, x2: float, y2: float, scale: float, pad_x: int, pad_y: int,
                  width: int, height: int) -> np.ndarray:
    box = np.array([(x1 - pad_x) / scale, (y1 - pad_y) / scale, (x2 - pad_x) / scale, (y2 - pad_y) / scale])
    box[[0, 2]] = box[[0, 2]].clip(0, width)
    box[[1, 3]] = box[[1, 3]].clip(0, height)
    return box


def decode(output: np.ndarray, conf: float, scale: float, pad_x: int, pad_y: int,
           width: int, height: int) -> list[tuple[np.ndarray, float, int]]:
    """Model output -> [(xyxy box in original image pixels, score, class id)] at or above `conf`."""
    if output.ndim == 3 and output.shape[2] == 6 and output.shape[1] > output.shape[2]:
        rows = output[0]
        rows = rows[rows[:, 4] >= conf]
        return [(_to_image_box(x1, y1, x2, y2, scale, pad_x, pad_y, width, height), float(score), int(cls))
                for x1, y1, x2, y2, score, cls in rows]
    predictions = output[0].T  # N x (4+nc)
    class_scores = predictions[:, 4:]
    scores = class_scores.max(axis=1)
    mask = scores >= conf
    if not mask.any():
        return []
    predictions, scores, classes = predictions[mask], scores[mask], class_scores[mask].argmax(axis=1)
    cx, cy, w, h = predictions[:, 0], predictions[:, 1], predictions[:, 2], predictions[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    return [(_to_image_box(*boxes[i], scale, pad_x, pad_y, width, height), float(scores[i]), int(classes[i]))
            for i in nms(boxes, scores)]


def yuv420_to_rgb(yuv: np.ndarray, width: int, height: int) -> Image.Image:
    """libcamera planar YUV420 (full-range BT.601, as JPEG uses) -> RGB.

    PIL does the colour maths in C (about 3 ms at 640x360); the equivalent numpy
    float version took 90-150 ms on the Pi Zero 2 W.
    """
    stride = yuv.shape[1]
    quarter = (height // 2) * (stride // 2)
    chroma = np.ascontiguousarray(yuv[height:]).reshape(-1)
    u = chroma[:quarter].reshape(height // 2, stride // 2)[:, : width // 2]
    v = chroma[quarter: 2 * quarter].reshape(height // 2, stride // 2)[:, : width // 2]
    luma = Image.fromarray(np.ascontiguousarray(yuv[:height, :width]), "L")
    cb = Image.fromarray(np.ascontiguousarray(u), "L").resize((width, height), Image.BILINEAR)
    cr = Image.fromarray(np.ascontiguousarray(v), "L").resize((width, height), Image.BILINEAR)
    return Image.merge("YCbCr", (luma, cb, cr)).convert("RGB")


# --------------------------------------------------------------------------- results

@dataclass
class Prediction:
    class_id: int
    label: str
    confidence: float
    x: float  # normalised 0..1, top-left corner of the box
    y: float
    w: float  # normalised width / height
    h: float


@dataclass
class DetectionResult:
    outcome: str = OUTCOME_OK
    elapsed_ms: int = 0
    predictions: list[Prediction] = field(default_factory=list)

    @property
    def max_confidence(self) -> float:
        return max((p.confidence for p in self.predictions), default=0.0)


# --------------------------------------------------------------------------- detector

class Detector:
    def __init__(self, model_path: Path, threads: int = 3, confidence: float = DEFAULT_CONFIDENCE) -> None:
        import onnxruntime as ort  # imported here so the rest of the module works without it
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.path = Path(model_path)
        self.session = ort.InferenceSession(str(self.path), options, providers=["CPUExecutionProvider"])
        shape = self.session.get_inputs()[0].shape
        self.input_name = self.session.get_inputs()[0].name
        self.size = int(shape[2])
        self.confidence = confidence
        metadata = self.session.get_modelmeta().custom_metadata_map
        try:
            names = ast.literal_eval(metadata.get("names", "{}"))
            self.names = {int(k): str(v) for k, v in names.items()}
        except (ValueError, SyntaxError, AttributeError):
            self.names = {}
        self.model_id = self.path.stem
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        # One throwaway run so the first real frame is not slower (graph optimisation, memory).
        self.session.run(None, {self.input_name: np.zeros((1, 3, self.size, self.size), dtype=np.float32)})

    def label(self, class_id: int) -> str:
        return self.names.get(class_id, f"class_{class_id}")

    def detect(self, image: Image.Image) -> DetectionResult:
        """Run the model on an RGB image. Never raises: a failure is an outcome, as on the XIAO."""
        started = time.monotonic()
        try:
            if image.mode != "RGB" or min(image.size) < 32:
                return DetectionResult(OUTCOME_INVALID)
            tensor, scale, pad_x, pad_y = letterbox(image, self.size)
            output = self.session.run(None, {self.input_name: tensor})[0]
            width, height = image.size
            predictions = []
            for box, score, class_id in decode(output, self.confidence, scale, pad_x, pad_y, width, height):
                x1, y1, x2, y2 = (float(v) for v in box)
                predictions.append(Prediction(class_id, self.label(class_id), round(score, 4),
                                              x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height))
            predictions.sort(key=lambda p: -p.confidence)
            return DetectionResult(OUTCOME_OK, int((time.monotonic() - started) * 1000), predictions)
        except Exception:  # onnxruntime / numpy errors must not stop a session
            return DetectionResult(OUTCOME_ERROR, int((time.monotonic() - started) * 1000))


# --------------------------------------------------------------------------- worker

class _Ticket:
    def __init__(self, image: Image.Image) -> None:
        self.image = image
        self.done = threading.Event()
        self.result: DetectionResult | None = None
        self.cancelled = False


class DetectorWorker(threading.Thread):
    """Runs one inference at a time, so recording and live view never oversubscribe the cores.

    Two kinds of job: capture jobs (the frame of a photo being recorded; the
    caller waits for the answer) always run first; live-view jobs are best-effort
    and are refused whenever the worker is busy or anything is waiting.
    """

    def __init__(self, detector: Detector) -> None:
        super().__init__(name="detector", daemon=True)
        self.detector = detector
        self._condition = threading.Condition()
        self._capture_job: _Ticket | None = None
        self._live_job: _Ticket | None = None
        self._busy = False
        self._stopping = False

    def submit_for_capture(self, image: Image.Image) -> _Ticket:
        """Start the inference for a photo's frame; collect it with wait_for_capture (lets the caller write the
        photo while the model runs)."""
        ticket = _Ticket(image)
        with self._condition:
            self._capture_job = ticket
            self._condition.notify()
        return ticket

    @staticmethod
    def wait_for_capture(ticket: _Ticket, timeout: float = 1.5) -> DetectionResult:
        if not ticket.done.wait(timeout):
            ticket.cancelled = True
            return DetectionResult(OUTCOME_TIMEOUT, int(timeout * 1000))
        assert ticket.result is not None
        return ticket.result

    def detect_for_capture(self, image: Image.Image, timeout: float = 1.5) -> DetectionResult:
        return self.wait_for_capture(self.submit_for_capture(image), timeout)

    def idle(self) -> bool:
        """True when a live-view frame would be accepted right now (lets a producer skip grabbing frames)."""
        with self._condition:
            return not (self._busy or self._capture_job is not None or self._live_job is not None)

    def try_detect_live(self, image: Image.Image) -> _Ticket | None:
        with self._condition:
            if self._busy or self._capture_job is not None or self._live_job is not None:
                return None
            ticket = _Ticket(image)
            self._live_job = ticket
            self._condition.notify()
            return ticket

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify()

    def run(self) -> None:
        while True:
            with self._condition:
                while not self._stopping and self._capture_job is None and self._live_job is None:
                    self._condition.wait()
                if self._stopping:
                    return
                if self._capture_job is not None:
                    ticket, self._capture_job = self._capture_job, None
                else:
                    ticket, self._live_job = self._live_job, None
                self._busy = True
            if ticket is not None and not ticket.cancelled:
                ticket.result = self.detector.detect(ticket.image)
                ticket.done.set()
            with self._condition:
                self._busy = False


# --------------------------------------------------------------------------- drawing (live view)

def draw_detections(image: Image.Image, result: DetectionResult, banner: str = PLACEHOLDER_BANNER) -> Image.Image:
    """Burn boxes, confidences and the placeholder banner into a copy of the frame."""
    frame = image.copy()
    draw = ImageDraw.Draw(frame)
    width, height = frame.size
    font = ImageFont.load_default(size=max(16, height // 15))   # shown at about half size on a phone
    for prediction in result.predictions:
        x1, y1 = prediction.x * width, prediction.y * height
        x2, y2 = x1 + prediction.w * width, y1 + prediction.h * height
        draw.rectangle([x1, y1, x2, y2], outline=(60, 255, 60), width=max(2, width // 320))
        draw.text((x1 + 2, max(0, y1 - font.size - 2)), f"{prediction.confidence:.2f}", fill=(60, 255, 60), font=font)
    bar = font.size + 8
    draw.rectangle([0, 0, width, bar], fill=(170, 0, 0))
    draw.text((6, 3), banner, fill=(255, 255, 255), font=font)
    status = f"{len(result.predictions)} found | {result.elapsed_ms} ms"
    draw.rectangle([0, height - bar, width, height], fill=(0, 0, 0))
    draw.text((6, height - bar + 3), status, fill=(255, 255, 255), font=font)
    return frame
