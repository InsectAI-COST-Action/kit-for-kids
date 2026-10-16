"""Benchmark an ONNX YOLO ant detector: speed, memory, heat and accuracy.

Runs the same on a PC and on the Pi Zero 2 W (needs numpy, onnxruntime, Pillow):

  python3 edge_bench.py --model AntTestModel.onnx --images DIR [--labels DIR]
                        [--threads 4] [--runs 15] [--conf 0.25] [--out results.json]

Pre- and post-processing are written here directly (letterbox, decode, NMS), not
taken from Ultralytics, so a model can run on the camera with onnxruntime (MIT)
alone. Expected model: YOLO26/YOLOv8-style detector, input [1,3,S,S] float32 in
0..1 RGB, output [1,4+nc,N] with box centre-x/y, width, height (pixels of the S x S
input) followed by class scores, no built-in NMS.

Accuracy needs YOLO-format labels (one .txt per image: class cx cy w h, normalised).
A prediction is a true positive if its IoU with a still-unmatched label is at least
0.5; precision and recall are reported at the given confidence, and AP50 over all
confidences.
"""

from __future__ import annotations

import argparse
import json
import sys
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from insectcam.detector import decode, iou, letterbox  # noqa: E402 - one copy of the pre/post-processing


def read_labels(path: Path, width: int, height: int) -> list[np.ndarray]:
    boxes = []
    if path.is_file():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                _, cx, cy, w, h = map(float, parts[:5])
                boxes.append(np.array([(cx - w / 2) * width, (cy - h / 2) * height,
                                       (cx + w / 2) * width, (cy + h / 2) * height]))
    return boxes


def average_precision(detections: list[tuple[float, bool]], total_labels: int) -> float:
    """AP at IoU 0.5: area under the precision-recall curve, detections sorted by score."""
    if total_labels == 0:
        return float("nan")
    detections = sorted(detections, key=lambda d: -d[0])
    tp = np.cumsum([1 if hit else 0 for _, hit in detections])
    fp = np.cumsum([0 if hit else 1 for _, hit in detections])
    recall = tp / total_labels
    precision = tp / np.maximum(tp + fp, 1)
    recall = np.concatenate([[0.0], recall, [1.0]])
    precision = np.concatenate([[1.0], precision, [0.0]])
    for i in range(len(precision) - 2, -1, -1):
        precision[i] = max(precision[i], precision[i + 1])
    changes = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[changes + 1] - recall[changes]) * precision[changes + 1]))


def peak_rss_mb() -> float:
    """Peak resident memory of this process (Linux); 0 where the platform has no resource module."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        return 0.0


def soc_state() -> dict:
    state = {}
    try:
        state["temp_c"] = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
        state["throttled"] = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True,
                                            timeout=2).stdout.strip().split("=")[-1]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--runs", type=int, default=15, help="timed inferences on the first image")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    started = time.monotonic()
    session = ort.InferenceSession(str(args.model), options, providers=["CPUExecutionProvider"])
    load_s = time.monotonic() - started
    shape = session.get_inputs()[0].shape
    size = int(shape[2])
    input_name = session.get_inputs()[0].name
    rss_after_load_mb = peak_rss_mb()

    paths = sorted(p for p in args.images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    result = {"model": args.model.name, "model_mb": round(args.model.stat().st_size / 1e6, 2), "input": size,
              "threads": args.threads, "load_s": round(load_s, 2), "images": len(paths), "conf": args.conf,
              "ort": ort.__version__, "soc_start": soc_state()}

    # --- speed on the first image: preprocessing and inference timed separately
    first = Image.open(paths[0]).convert("RGB")
    pre, inf, post = [], [], []
    session.run(None, {input_name: letterbox(first, size)[0]})  # warm-up
    for _ in range(args.runs):
        t0 = time.monotonic()
        tensor, scale, pad_x, pad_y = letterbox(first, size)
        t1 = time.monotonic()
        output = session.run(None, {input_name: tensor})[0]
        t2 = time.monotonic()
        decode(output, args.conf, scale, pad_x, pad_y, *first.size)
        t3 = time.monotonic()
        pre.append(t1 - t0); inf.append(t2 - t1); post.append(t3 - t2)
    ms = lambda values: round(1000 * statistics.median(values), 1)
    result.update({"pre_ms": ms(pre), "inference_ms": ms(inf), "inference_ms_max": round(1000 * max(inf), 1),
                   "post_ms": ms(post), "total_ms": round(ms(pre) + ms(inf) + ms(post), 1),
                   "peak_rss_mb": round(peak_rss_mb(), 1),
                   "rss_after_load_mb": round(rss_after_load_mb, 1), "soc_end": soc_state()})

    # --- accuracy (optional)
    if args.labels:
        detections: list[tuple[float, bool]] = []
        labels_total = tp_at_conf = fp_at_conf = 0
        per_image = []
        for path in paths:
            image = Image.open(path).convert("RGB")
            tensor, scale, pad_x, pad_y = letterbox(image, size)
            output = session.run(None, {input_name: tensor})[0]
            found = decode(output, 0.05, scale, pad_x, pad_y, *image.size)  # low floor for AP
            truth = read_labels(args.labels / (path.stem + ".txt"), *image.size)
            matched: set[int] = set()
            hits = 0
            for box, score, _ in found:
                best, best_j = 0.0, -1
                for j, label in enumerate(truth):
                    if j in matched:
                        continue
                    value = iou(box, label)
                    if value > best:
                        best, best_j = value, j
                hit = best >= 0.5
                if hit:
                    matched.add(best_j)
                detections.append((score, hit))
                if score >= args.conf:
                    if hit:
                        tp_at_conf += 1
                    else:
                        fp_at_conf += 1
                    hits += hit
            labels_total += len(truth)
            per_image.append({"image": path.name[:28], "labels": len(truth),
                              "found_at_conf": sum(1 for _, s, _ in found if s >= args.conf), "matched": int(hits)})
        tp_at_conf, fp_at_conf = int(tp_at_conf), int(fp_at_conf)
        precision = tp_at_conf / max(tp_at_conf + fp_at_conf, 1)
        recall = tp_at_conf / max(labels_total, 1)
        result["accuracy"] = {"labels": int(labels_total), "tp": tp_at_conf, "fp": fp_at_conf,
                              "precision": round(precision, 3), "recall": round(recall, 3),
                              "ap50": round(average_precision(detections, labels_total), 3), "per_image": per_image}

    print(json.dumps({k: v for k, v in result.items() if k != "accuracy"}, indent=None))
    if "accuracy" in result:
        a = result["accuracy"]
        print(f"accuracy @conf {args.conf}: labels={a['labels']} tp={a['tp']} fp={a['fp']} "
              f"precision={a['precision']} recall={a['recall']} AP50={a['ap50']}")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
