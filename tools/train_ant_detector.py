"""Train and evaluate a small reproducible ant-detector baseline.

Usage:
    py tools/train_ant_detector.py datasets/ant-detector-v1

This uses the Roboflow-export split recorded in the local provenance manifest only
within the chronological training pool: 32 images fit the model, 2 validate it,
and 3 remain a small seed test. It never uses the project's held-out validation
or final test partitions for model fitting.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

MODEL_NAME = "yolo26n.pt"
IMAGE_SIZE = 1024
EPOCHS = 40
BATCH = 2
SEED = 20260818
SOURCE_SPLIT_MAP = {"train": "train", "valid": "val", "test": "test"}


def prepare_data(dataset_root: Path, run_root: Path) -> Path:
    metadata_files = sorted((dataset_root / "metadata").glob("roboflow_import_v*.csv"))
    if len(metadata_files) != 1:
        raise ValueError(f"Expected one active Roboflow import manifest, found {metadata_files}")
    with metadata_files[0].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {"train": 32, "valid": 2, "test": 3}
    actual = {split: sum(row["coco_split"] == split for row in rows) for split in expected}
    if actual != expected:
        raise ValueError(f"Unexpected seed import split: {actual}")
    for row in rows:
        source_split = row["coco_split"]
        target_split = SOURCE_SPLIT_MAP[source_split]
        capture_id = row["capture_id"]
        source_image = dataset_root / "images" / "train" / f"{capture_id}.jpg"
        source_label = dataset_root / "labels" / "train" / f"{capture_id}.txt"
        if not source_image.is_file() or not source_label.is_file():
            raise ValueError(f"Missing reviewed image or label for {capture_id}")
        image_target = run_root / "data" / "images" / target_split / source_image.name
        label_target = run_root / "data" / "labels" / target_split / source_label.name
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_image, image_target)
        shutil.copy2(source_label, label_target)
    yaml_path = run_root / "data" / "dataset.yaml"
    yaml_path.write_text(
        f"path: {(run_root / 'data').resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\n\nnames:\n  0: ant\n",
        encoding="utf-8",
    )
    return yaml_path


def metric_values(metrics: object) -> dict[str, float]:
    values = getattr(metrics, "results_dict", {})
    return {str(key): float(value) for key, value in values.items() if isinstance(value, (float, int))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path, help="Local ant-detector dataset root")
    parser.add_argument("--run-root", type=Path, default=Path("artifacts/ant-detector-round-1"), help="Ignored output directory")
    args = parser.parse_args()
    dataset_root = args.dataset_root.resolve()
    run_root = args.run_root.resolve()
    if run_root.exists():
        parser.error(f"Run output already exists: {run_root}. Preserve it as evidence and choose a new --run-root.")
    run_root.mkdir(parents=True)
    try:
        yaml_path = prepare_data(dataset_root, run_root)
        from ultralytics import YOLO
        pretrained_path = run_root.parent / "pretrained" / MODEL_NAME
        pretrained_path.parent.mkdir(parents=True, exist_ok=True)
        if not pretrained_path.is_file():
            downloaded = Path(MODEL_NAME)
            if downloaded.is_file():
                shutil.move(str(downloaded), pretrained_path)
            else:
                YOLO(MODEL_NAME)
                shutil.move(MODEL_NAME, pretrained_path)
        model = YOLO(str(pretrained_path))
        train_metrics = model.train(
            data=str(yaml_path),
            imgsz=IMAGE_SIZE,
            epochs=EPOCHS,
            batch=BATCH,
            device="cpu",
            workers=0,
            patience=10,
            seed=SEED,
            deterministic=True,
            pretrained=True,
            optimizer="auto",
            cos_lr=True,
            degrees=180,
            fliplr=0.5,
            mosaic=0.5,
            mixup=0.0,
            project=str(run_root / "runs"),
            name="train",
            exist_ok=False,
            verbose=True,
        )
        best_weights = Path(model.trainer.best)
        best_model = YOLO(str(best_weights))
        test_metrics = best_model.val(
            data=str(yaml_path),
            split="test",
            imgsz=IMAGE_SIZE,
            batch=BATCH,
            device="cpu",
            workers=0,
            project=str(run_root / "runs"),
            name="seed_test",
            exist_ok=False,
            verbose=True,
        )
        onnx_path = Path(best_model.export(format="onnx", imgsz=IMAGE_SIZE, dynamic=False, simplify=False))
        summary = {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "status": "completed",
            "model": MODEL_NAME,
            "image_size": IMAGE_SIZE,
            "epochs_requested": EPOCHS,
            "batch": BATCH,
            "device": "cpu",
            "seed": SEED,
            "data_split": {"fit": 32, "validation": 2, "seed_test": 3},
            "best_weights": str(best_weights),
            "onnx_export": str(onnx_path),
            "train_metrics": metric_values(train_metrics),
            "seed_test_metrics": metric_values(test_metrics),
        }
        (run_root / "training_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except Exception:
        (run_root / "training_failed.txt").write_text("Training did not complete; inspect the terminal output and preserve this run directory.\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
