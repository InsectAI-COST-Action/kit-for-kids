"""Build a reproducible, image-ignored dataset for the bespoke ant detector.

Usage:
    py tools/build_ant_detector_dataset.py D:/ datasets/ant-detector-v1

The source card is never modified. Only frames from the requested session that still
exist on the card are copied. Contiguous train/validation/test time segments are
separated by short boundary gaps to avoid adjacent-frame leakage.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from pathlib import Path

TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
BOUNDARY_GAP = 15  # frames: 15 seconds at the settled 1-FPS pilot setting
DEFAULT_RUN_ID = "run_000008"


def capture_number(row: dict[str, str]) -> int:
    match = re.search(r"_img_(\d+)$", row["capture_id"])
    if not match:
        raise ValueError(f"Cannot find image number in {row['capture_id']}")
    return int(match.group(1))


def existing_session_rows(card_root: Path, run_id: str) -> list[dict[str, str]]:
    with (card_root / "raw" / "captures.csv").open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["run_id"] == run_id]
    rows = [row for row in rows if row["outcome"] == "completed" and (card_root / row["image_path"].lstrip("/")).is_file()]
    return sorted(rows, key=capture_number)


def allocate(rows: list[dict[str, str]]) -> tuple[list[tuple[str, dict[str, str]]], list[dict[str, str]]]:
    usable = len(rows) - (BOUNDARY_GAP * 2)
    if usable < 100:
        raise ValueError("Need at least 100 usable frames after boundary gaps.")
    train_count = int(usable * TRAIN_FRACTION)
    validation_count = int(usable * VALIDATION_FRACTION)
    test_count = usable - train_count - validation_count
    train_end = train_count
    validation_start = train_end + BOUNDARY_GAP
    validation_end = validation_start + validation_count
    test_start = validation_end + BOUNDARY_GAP
    assignments = (
        [("train", row) for row in rows[:train_end]]
        + [("validation", row) for row in rows[validation_start:validation_end]]
        + [("test", row) for row in rows[test_start:test_start + test_count]]
    )
    skipped = rows[train_end:validation_start] + rows[validation_end:test_start]
    return assignments, skipped


def write_project_files(destination: Path, run_id: str, assignments: list[tuple[str, dict[str, str]]], skipped: list[dict[str, str]]) -> None:
    counts = {split: sum(1 for assigned_split, _ in assignments if assigned_split == split) for split in ("train", "validation", "test")}
    (destination / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (destination / "labels" / "validation").mkdir(parents=True, exist_ok=True)
    (destination / "labels" / "test").mkdir(parents=True, exist_ok=True)
    for split in counts:
        (destination / "labels" / split / ".gitkeep").touch()
    (destination / "metadata").mkdir(parents=True, exist_ok=True)
    (destination / "dataset.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/validation\ntest: images/test\n\nnames:\n  0: ant\n",
        encoding="utf-8",
    )
    (destination / "README.md").write_text(
        f"""# Ant detector dataset v1

Source: `{run_id}` from the camera card, QXGA 2048?1536 JPEGs.

| Split | Images | Purpose |
| --- | ---: | --- |
| Train | {counts['train']} | Active-learning pool and model fitting |
| Validation | {counts['validation']} | Development tuning only |
| Test | {counts['test']} | Final untouched evaluation |
| Boundary gaps | {len(skipped)} | Intentionally excluded to separate adjacent time sequences |

Images are deliberately ignored by Git. `metadata/split_manifest.csv`, this readme,
`dataset.yaml`, and future YOLO labels are version-controlled.

## Annotation rules

- Use one class only: `ant` (class `0`). Draw a tight box around every visible ant.
- Label all visible ants in an image, including small or partly occluded ants when they
  can reasonably be recognised. Do not create a box for ambiguous dark debris.
- Empty images are valuable negatives: leave their matching label file absent or empty.
- Use images from **train** for active-learning rounds. Do not use validation or test
  images to decide architecture, confidence thresholds, tiling settings, or stopping.
- Keep the test split untouched until the detector and settings are frozen.

The split is chronological with 15-frame buffers at each split boundary. This prevents
nearly adjacent 1-FPS frames from appearing in both training and evaluation data.
""",
        encoding="utf-8",
    )
    fields = ["split", "capture_number", "capture_id", "uptime_ms", "frame_width", "frame_height", "jpeg_bytes", "source_image_path", "dataset_image_path"]
    with (destination / "metadata" / "split_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for split, row in assignments:
            source_path = row["image_path"].lstrip("/")
            writer.writerow({
                "split": split,
                "capture_number": capture_number(row),
                "capture_id": row["capture_id"],
                "uptime_ms": row["uptime_ms"],
                "frame_width": row["frame_width"],
                "frame_height": row["frame_height"],
                "jpeg_bytes": row["jpeg_bytes"],
                "source_image_path": source_path,
                "dataset_image_path": f"images/{split}/{Path(source_path).name}",
            })
    with (destination / "metadata" / "excluded_boundary_frames.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["capture_number", "capture_id", "source_image_path", "reason"])
        writer.writeheader()
        for row in skipped:
            writer.writerow({"capture_number": capture_number(row), "capture_id": row["capture_id"], "source_image_path": row["image_path"].lstrip("/"), "reason": "15-frame split boundary buffer"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card_root", type=Path, help="Mounted SD-card root, for example D:\\")
    parser.add_argument("destination", type=Path, help="New repository dataset directory")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID, help=f"Session to split (default: {DEFAULT_RUN_ID})")
    args = parser.parse_args()
    card_root = args.card_root.resolve()
    destination = args.destination.resolve()
    if not (card_root / "raw" / "captures.csv").is_file():
        parser.error(f"No raw/captures.csv under {card_root}")
    if destination.exists():
        parser.error(f"Destination already exists: {destination}. Choose a new empty directory.")
    rows = existing_session_rows(card_root, args.run_id)
    assignments, skipped = allocate(rows)
    destination.mkdir(parents=True)
    write_project_files(destination, args.run_id, assignments, skipped)
    for index, (split, row) in enumerate(assignments, start=1):
        source = card_root / row["image_path"].lstrip("/")
        target = destination / "images" / split / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if index % 250 == 0 or index == len(assignments):
            print(f"Copied {index} of {len(assignments)} images")
    counts = {split: sum(1 for assigned_split, _ in assignments if assigned_split == split) for split in ("train", "validation", "test")}
    print(f"Created {destination}")
    print(f"Train={counts['train']}, validation={counts['validation']}, test={counts['test']}, boundary excluded={len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
