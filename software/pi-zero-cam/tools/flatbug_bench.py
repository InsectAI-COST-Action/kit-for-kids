"""Benchmark FlatBug Nano the way the dashboard's "Find insects with AI" panel runs it: speed and accuracy.

Reproduces dashboard/analysis.js of the ESP32 project: 640 x 640 input, letterbox with grey 114 padding, RGB
0..1, the box + score of output0 ([1, 37, 8400]: 4 box values, 1 insect score, 32 mask coefficients - masks
are never read, but every output is still computed, as in the dashboard), score threshold 0.20, overlap
(IoU) suppression 0.20, and two modes:

  quick  whole picture in one pass
  close  4 x 3 grid of 640 x 640 pieces cut from the full-size picture (one pass each, 12 for a 2304 x 1296
         photo), results merged; a picture no larger than the input is a single piece, so the same as quick

  python3 flatbug_bench.py --model flatbug-n.onnx --images DIR [--labels DIR] [--photo FILE ...]
                           [--threads 4] [--runs 3] [--out results.json] [--draw DIR]

Needs numpy, onnxruntime, Pillow; runs the same on a PC and on the Pi. Accuracy uses the same rule as
edge_bench.py (a box is correct if its IoU with a still-unmatched label is >= 0.5). FlatBug is a general insect
model and the labels are ants only, so "wrong" boxes on other insects would count against it; the labelled
images contain ants only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw

SCORE_THRESHOLD = 0.20
OVERLAP_THRESHOLD = 0.20
TILE_COLUMNS, TILE_ROWS = 4, 3
FLOOR = 0.05          # lower threshold used only to draw the precision-recall curve


def positions(length: int, tile: int, count: int) -> list[int]:
    n = count if length > tile else 1
    return [0] if n == 1 else [round(i * (length - tile) / (n - 1)) for i in range(n)]


def make_tiles(width: int, height: int, mode: str, size: int) -> list[tuple[int, int, int, int]]:
    if mode == "quick":
        return [(0, 0, width, height)]
    tw, th = min(size, width), min(size, height)
    return [(x, y, tw, th) for y in positions(height, th, TILE_ROWS) for x in positions(width, tw, TILE_COLUMNS)]


def prepare(image: Image.Image, tile: tuple[int, int, int, int], size: int):
    x, y, w, h = tile
    scale = min(size / w, size / h)
    nw, nh = round(w * scale), round(h * scale)
    pad_x, pad_y = round((size - nw) / 2), round((size - nh) / 2)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(image.crop((x, y, x + w, y + h)).resize((nw, nh), Image.BILINEAR), (pad_x, pad_y))
    array = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
    return np.ascontiguousarray(array), scale, pad_x, pad_y


def decode(output: np.ndarray, floor: float, scale: float, pad_x: int, pad_y: int, tile) -> list[list[float]]:
    """Boxes [x, y, w, h, score] in full-picture pixels, clipped to the piece, score >= floor."""
    tx, ty, tw, th = tile
    data = output[0]                                   # [37, N]
    score = np.clip(data[4], 0, 1)
    keep = np.nonzero(score >= floor)[0]
    found = []
    for i in keep:
        cx, cy, w, h = data[0, i], data[1, i], data[2, i], data[3, i]
        left = min(max((cx - w / 2 - pad_x) / scale + tx, tx), tx + tw)
        top = min(max((cy - h / 2 - pad_y) / scale + ty, ty), ty + th)
        right = min(max((cx + w / 2 - pad_x) / scale + tx, tx), tx + tw)
        bottom = min(max((cy + h / 2 - pad_y) / scale + ty, ty), ty + th)
        if right > left and bottom > top:
            found.append([left, top, right - left, bottom - top, float(score[i])])
    return found


def overlap(a, b) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    shared = max(0.0, right - left) * max(0.0, bottom - top)
    return shared / ((a[2] * a[3] + b[2] * b[3] - shared) or 1.0)


def suppress(candidates: list[list[float]]) -> list[list[float]]:
    kept: list[list[float]] = []
    for c in sorted(candidates, key=lambda b: -b[4]):
        if all(overlap(c, k) < OVERLAP_THRESHOLD for k in kept):
            kept.append(c)
    return kept


def detect(session, image: Image.Image, mode: str, size: int, floor: float) -> tuple[list, dict]:
    name = session.get_inputs()[0].name
    tiles = make_tiles(*image.size, mode, size)
    candidates, pre, inf = [], 0.0, []
    for tile in tiles:
        t0 = time.monotonic()
        tensor, scale, pad_x, pad_y = prepare(image, tile, size)
        t1 = time.monotonic()
        output = session.run(None, {name: tensor})[0]
        t2 = time.monotonic()
        candidates += decode(output, floor, scale, pad_x, pad_y, tile)
        pre += t1 - t0
        inf.append(t2 - t1)
    t3 = time.monotonic()
    boxes = suppress(candidates)
    return boxes, {"tiles": len(tiles), "pre_s": pre, "inf_s": inf, "post_s": time.monotonic() - t3}


def read_labels(path: Path, width: int, height: int) -> list[list[float]]:
    boxes = []
    if path.is_file():
        for line in path.read_text().splitlines():
            p = line.split()
            if len(p) >= 5:
                _, cx, cy, w, h = map(float, p[:5])
                boxes.append([(cx - w / 2) * width, (cy - h / 2) * height, w * width, h * height])
    return boxes


def corner_iou(a, b) -> float:
    return overlap(a, b)    # same arithmetic: boxes are [x, y, w, h]


def average_precision(detections: list[tuple[float, bool]], total: int) -> float:
    if total == 0:
        return float("nan")
    detections = sorted(detections, key=lambda d: -d[0])
    tp = np.cumsum([1 if hit else 0 for _, hit in detections])
    fp = np.cumsum([0 if hit else 1 for _, hit in detections])
    recall = np.concatenate([[0.0], tp / total, [1.0]])
    precision = np.concatenate([[1.0], tp / np.maximum(tp + fp, 1), [0.0]])
    for i in range(len(precision) - 2, -1, -1):
        precision[i] = max(precision[i], precision[i + 1])
    changes = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[changes + 1] - recall[changes]) * precision[changes + 1]))


def peak_rss_mb() -> float:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:
        return 0.0


def soc_temp() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def draw(image: Image.Image, boxes, path: Path) -> None:
    canvas = image.copy()
    pen = ImageDraw.Draw(canvas)
    width = max(2, image.width // 400)
    for x, y, w, h, score in boxes:
        pen.rectangle([x, y, x + w, y + h], outline=(0, 255, 0), width=width)
    canvas.save(path, quality=85)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--photo", type=Path, nargs="*", default=[])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--runs", type=int, default=3, help="timed repeats per photo and mode")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--draw", type=Path)
    args = parser.parse_args()

    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    t0 = time.monotonic()
    session = ort.InferenceSession(str(args.model), options, providers=["CPUExecutionProvider"])
    size = int(session.get_inputs()[0].shape[2])
    result = {"model": args.model.name, "model_mb": round(args.model.stat().st_size / 1e6, 2), "input": size,
              "threads": args.threads, "load_s": round(time.monotonic() - t0, 2), "ort": ort.__version__,
              "score_threshold": SCORE_THRESHOLD, "overlap_threshold": OVERLAP_THRESHOLD,
              "temp_start_c": soc_temp(), "modes": {}}
    session.run(None, {session.get_inputs()[0].name: np.zeros((1, 3, size, size), np.float32)})   # warm-up

    paths = sorted(p for p in args.images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for mode in ("quick", "close"):
        entry: dict = {}
        # ---- accuracy on the labelled images
        if args.labels:
            detections, truth_total, tp, fp, pieces, per_image = [], 0, 0, 0, [], []
            for path in paths:
                image = Image.open(path).convert("RGB")
                found, timing = detect(session, image, mode, size, FLOOR)
                truth = read_labels(args.labels / (path.stem + ".txt"), *image.size)
                matched: set[int] = set()
                at_threshold = hits = 0
                for box in found:                       # already sorted by score
                    best, best_j = 0.0, -1
                    for j, label in enumerate(truth):
                        if j not in matched and corner_iou(box, label) > best:
                            best, best_j = corner_iou(box, label), j
                    hit = best >= 0.5
                    if hit:
                        matched.add(best_j)
                    detections.append((box[4], hit))
                    if box[4] >= SCORE_THRESHOLD:
                        at_threshold += 1
                        tp += hit
                        fp += not hit
                        hits += hit
                truth_total += len(truth)
                pieces.append(timing["tiles"])
                per_image.append({"image": path.name[:24], "size": list(image.size), "labels": len(truth),
                                  "found": at_threshold, "matched": int(hits)})
            result_acc = {"images": len(paths), "labels": truth_total, "tp": int(tp), "fp": int(fp),
                          "precision": round(tp / max(tp + fp, 1), 3), "recall": round(tp / max(truth_total, 1), 3),
                          "ap50": round(average_precision(detections, truth_total), 3),
                          "pieces_per_image": sorted(set(pieces)), "per_image": per_image}
            entry["accuracy"] = result_acc
        # ---- speed and detections on the photos
        entry["photos"] = []
        for photo in args.photo:
            image = Image.open(photo).convert("RGB")
            totals, per_pass, counts = [], [], 0
            for _ in range(args.runs):
                t0 = time.monotonic()
                found, timing = detect(session, image, mode, size, SCORE_THRESHOLD)
                totals.append(time.monotonic() - t0)
                per_pass += timing["inf_s"]
                counts = len(found)
            if args.draw:
                args.draw.mkdir(parents=True, exist_ok=True)
                draw(image, found, args.draw / f"{photo.stem}_{mode}.jpg")
            entry["photos"].append({"photo": photo.name, "size": list(image.size), "pieces": timing["tiles"],
                                    "found": counts, "total_ms": round(1000 * statistics.median(totals)),
                                    "total_ms_max": round(1000 * max(totals)),
                                    "per_pass_ms": round(1000 * statistics.median(per_pass)),
                                    "preprocess_ms": round(1000 * timing["pre_s"]),
                                    "temp_c": soc_temp()})
        result["modes"][mode] = entry
    result["peak_rss_mb"] = round(peak_rss_mb(), 1)
    result["temp_end_c"] = soc_temp()
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
