"""Import an inspected Roboflow COCO export into the local ant-detector dataset.

Usage:
    py tools/import_roboflow_coco.py <coco-export-root> datasets/ant-detector-v1 --source-version 1

The command never calls Roboflow and never needs an API key. It maps the original capture
identifier embedded in each Roboflow filename, verifies that each source image is already in
the local training split, then writes one-class YOLO labels and an audit manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

CAPTURE_PATTERN = re.compile(r"^(run_\d+_img_\d+)_jpg\.rf\.[^.]+\.jpg$")
SUPPORTED_CLASS_NAMES = {"ant", "ants"}


def coco_export_root(source: Path, temporary_directory: tempfile.TemporaryDirectory[str] | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if source.is_dir():
        return source, temporary_directory
    if source.is_file() and source.suffix.lower() == ".zip":
        temporary_directory = tempfile.TemporaryDirectory(prefix="insect-ai-coco-")
        with zipfile.ZipFile(source) as archive:
            archive.extractall(temporary_directory.name)
        return Path(temporary_directory.name), temporary_directory
    raise ValueError(f"COCO source must be a directory or .zip file: {source}")


def load_export(coco_root: Path) -> tuple[dict[str, tuple[int, int]], dict[str, list[tuple[float, float, float, float]]], list[dict[str, str]]]:
    image_sizes: dict[str, tuple[int, int]] = {}
    boxes: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    provenance: list[dict[str, str]] = []
    annotation_files = sorted(coco_root.rglob("_annotations.coco.json"))
    if not annotation_files:
        raise ValueError(f"No COCO annotation files below {coco_root}")
    for annotation_file in annotation_files:
        payload = json.loads(annotation_file.read_text(encoding="utf-8"))
        categories = {category["id"]: str(category["name"]).strip().lower() for category in payload["categories"]}
        images = {image["id"]: image for image in payload["images"]}
        capture_by_image: dict[int, str] = {}
        for image_id, image in images.items():
            match = CAPTURE_PATTERN.match(image["file_name"])
            if not match:
                raise ValueError(f"Unexpected Roboflow image filename: {image['file_name']}")
            capture_id = match.group(1)
            if capture_id in image_sizes:
                raise ValueError(f"Duplicate capture in export: {capture_id}")
            image_sizes[capture_id] = (int(image["width"]), int(image["height"]))
            capture_by_image[image_id] = capture_id
            provenance.append({"capture_id": capture_id, "roboflow_file_name": image["file_name"], "coco_split": annotation_file.parent.name})
        for annotation in payload["annotations"]:
            category_name = categories.get(annotation["category_id"], "")
            if category_name not in SUPPORTED_CLASS_NAMES:
                raise ValueError(f"Unsupported annotation class {category_name!r}")
            capture_id = capture_by_image[annotation["image_id"]]
            x, y, width, height = map(float, annotation["bbox"])
            image_width, image_height = image_sizes[capture_id]
            if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image_width or y + height > image_height:
                raise ValueError(f"Invalid bounding box for {capture_id}: {annotation['bbox']}")
            boxes[capture_id].append((x, y, width, height))
    return image_sizes, boxes, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coco_root", type=Path, help="Downloaded Roboflow COCO export directory or ZIP")
    parser.add_argument("dataset_root", type=Path, help="Local ant-detector dataset root")
    parser.add_argument("--source-version", required=True, help="Roboflow dataset version or export identifier, for provenance")
    parser.add_argument("--replace-import-version", help="Replace labels and provenance from this earlier import identifier")
    args = parser.parse_args()
    source = args.coco_root.resolve()
    dataset_root = args.dataset_root.resolve()
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        coco_root, temporary_directory = coco_export_root(source, temporary_directory)
        image_sizes, boxes, provenance = load_export(coco_root)
        label_directory = dataset_root / "labels" / "train"
        image_directory = dataset_root / "images" / "train"
        if not label_directory.is_dir() or not image_directory.is_dir():
            parser.error("Dataset must have training images and a training label directory")
        previous_capture_ids: set[str] = set()
        previous_paths: list[Path] = []
        previous_metadata: list[Path] = []
        if args.replace_import_version:
            stem = f"roboflow_import_v{args.replace_import_version}"
            manifest_path = dataset_root / "metadata" / f"{stem}.csv"
            summary_path = dataset_root / "metadata" / f"{stem}.json"
            if not manifest_path.is_file():
                parser.error(f"Previous import manifest is missing: {manifest_path}")
            with manifest_path.open(newline="", encoding="utf-8") as handle:
                previous_rows = list(csv.DictReader(handle))
            previous_capture_ids = {row["capture_id"] for row in previous_rows}
            if not previous_capture_ids <= set(image_sizes):
                parser.error("Replacement export does not contain every image from the previous import")
            previous_paths = [label_directory / f"{capture_id}.txt" for capture_id in previous_capture_ids]
            if not all(path.is_file() for path in previous_paths):
                parser.error("A previous-import label file is missing; refusing replacement")
            previous_metadata = [path for path in (manifest_path, summary_path) if path.exists()]
        for capture_id, (width, height) in image_sizes.items():
            image_path = image_directory / f"{capture_id}.jpg"
            if not image_path.is_file():
                parser.error(f"Roboflow image is not in the local training pool: {capture_id}")
            label_path = label_directory / f"{capture_id}.txt"
            if label_path.exists() and capture_id not in previous_capture_ids:
                parser.error(f"Refusing to overwrite existing local annotation: {label_path}")
        for capture_id, (width, height) in image_sizes.items():
            label_path = label_directory / f"{capture_id}.txt"
            lines = []
            for x, y, box_width, box_height in boxes.get(capture_id, []):
                centre_x = (x + box_width / 2) / width
                centre_y = (y + box_height / 2) / height
                normal_width = box_width / width
                normal_height = box_height / height
                lines.append(f"0 {centre_x:.8f} {centre_y:.8f} {normal_width:.8f} {normal_height:.8f}")
            label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        metadata_directory = dataset_root / "metadata"
        metadata_directory.mkdir(exist_ok=True)
        with (metadata_directory / f"roboflow_import_v{args.source_version}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["capture_id", "roboflow_file_name", "coco_split", "box_count", "local_label_path"])
            writer.writeheader()
            for row in sorted(provenance, key=lambda item: item["capture_id"]):
                capture_id = row["capture_id"]
                writer.writerow({**row, "box_count": len(boxes.get(capture_id, [])), "local_label_path": f"labels/train/{capture_id}.txt"})
        summary = {
        "source": "Roboflow COCO export",
        "source_version": str(args.source_version),
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "class_mapping": {"roboflow": ["ant", "ants"], "local_yolo_class": 0, "local_name": "ant"},
        "images": len(image_sizes),
        "annotations": sum(len(value) for value in boxes.values()),
        "local_split": "train",
        }
        (metadata_directory / f"roboflow_import_v{args.source_version}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        for path in previous_metadata:
            path.unlink()
        print(f"Imported {summary['annotations']} ant boxes from {summary['images']} images into {label_directory}")
        return 0
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
