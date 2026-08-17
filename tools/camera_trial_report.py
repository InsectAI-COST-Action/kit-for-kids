"""Summarise labelled OV3660 pilot and image-quality trial runs from a mounted card.

Usage: py tools\\camera_trial_report.py E:\\
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def median(values: list[float]) -> str:
    return f"{statistics.median(values):.1f}" if values else "-"


def maximum(values: list[float]) -> str:
    return f"{max(values):.1f}" if values else "-"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise OV3660 pilot and quality-trial runs on an SD card.")
    parser.add_argument("card_root", type=Path, help="Mounted SD-card root, for example E:\\")
    args = parser.parse_args()
    root = args.card_root.resolve()
    runs_directory = root / "raw" / "runs"
    captures_path = root / "raw" / "captures.csv"
    if not runs_directory.is_dir() or not captures_path.is_file():
        parser.error("expected raw/runs and raw/captures.csv on the card")

    runs: dict[str, dict[str, object]] = {}
    for path in sorted(runs_directory.glob("*.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if manifest.get("capture_mode") in {"quality_trial", "pilot"}:
            runs[str(manifest.get("run_id", ""))] = manifest
    if not runs:
        print("No labelled pilot or quality-trial manifests found.")
        return 0

    captures: dict[str, list[dict[str, str]]] = defaultdict(list)
    with captures_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("run_id") in runs:
                captures[row["run_id"]].append(row)

    performance: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in sorted((root / "system").glob("performance_run_*.csv")):
        run_id = path.stem.removeprefix("performance_")
        if run_id not in runs:
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            performance[run_id].extend(csv.DictReader(handle))

    columns = ["run", "preset", "fps", "configured_size", "captured_px", "jpeg_q", "completed", "median_kib", "median_interval_ms", "max_interval_ms", "median_write_ms", "max_write_ms", "max_start_lag_ms", "state"]
    rows: list[list[str]] = []
    for run_id, manifest in sorted(runs.items()):
        completed = [row for row in captures[run_id] if row.get("outcome") == "completed"]
        jpeg_kib = [int(row["jpeg_bytes"]) / 1024 for row in completed if row.get("jpeg_bytes", "").isdigit()]
        dimensions = sorted({f"{row['frame_width']}x{row['frame_height']}" for row in completed
                             if row.get("frame_width", "").isdigit() and row.get("frame_height", "").isdigit()})
        times = [int(row["uptime_ms"]) for row in completed if row.get("uptime_ms", "").isdigit()]
        intervals = [later - earlier for earlier, later in zip(times, times[1:]) if later >= earlier]
        write_ms = [float(row["image_write_ms"]) for row in performance[run_id] if row.get("image_write_ms", "").isdigit()]
        lag_ms = [float(row["start_lag_ms"]) for row in performance[run_id] if row.get("start_lag_ms", "").isdigit()]
        rows.append([
            run_id,
            str(manifest.get("camera_preset", "-")),
            str(manifest.get("capture_fps", "-")),
            str(manifest.get("frame_size", "-")),
            "/".join(dimensions) if dimensions else "-",
            str(manifest.get("jpeg_quality", "-")),
            str(len(completed)), median(jpeg_kib), median(intervals), maximum(intervals),
            median(write_ms), maximum(write_ms), maximum(lag_ms), str(manifest.get("state", "-")),
        ])

    widths = [len(column) for column in columns]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]
    print("  ".join(column.ljust(width) for column, width in zip(columns, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))
    print("\nLower JPEG-quality numbers usually mean less compression and larger files. Choose visual quality first, then reject any preset with unreliable cadence, unacceptable write time, or excessive storage use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
