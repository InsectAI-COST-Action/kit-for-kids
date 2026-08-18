#!/usr/bin/env python3
"""Train the experimental AntAI Beta YOLO26 Nano detector from the Roboflow COCO export.

The prepared dataset preserves the Roboflow train/valid/test split (34/10/5).
Both ``ant`` and ``ants`` source labels have already been normalized to one
``ant`` class by tools/prepare_rfdetr_ant_dataset.py.  Images and weights are
local ignored artefacts; the source annotations remain reviewable in Git.
"""
from __future__ import annotations
import argparse, json, shutil
from datetime import UTC, datetime
from pathlib import Path

MODEL_NAME = "yolo26n.pt"
IMAGE_SIZE = 1024
EPOCHS = 40
BATCH = 2
SEED = 20260818
SOURCE_SPLIT_MAP = {"train": "train", "valid": "val", "test": "test"}


def yolo_label(box, width, height):
    x, y, box_width, box_height = box
    return f"0 {(x + box_width / 2) / width:.8f} {(y + box_height / 2) / height:.8f} {box_width / width:.8f} {box_height / height:.8f}"


def prepare_data(dataset_root: Path, run_root: Path) -> tuple[Path, dict[str, int]]:
    totals: dict[str, int] = {}
    for source_split, target_split in SOURCE_SPLIT_MAP.items():
        source_dir = dataset_root / source_split
        annotation_path = source_dir / "_annotations.coco.json"
        if not annotation_path.is_file():
            raise ValueError(f"Missing COCO annotation file: {annotation_path}")
        document = json.loads(annotation_path.read_text(encoding="utf-8"))
        images = {image["id"]: image for image in document.get("images", [])}
        grouped = {image_id: [] for image_id in images}
        for annotation in document.get("annotations", []):
            if annotation["image_id"] not in images:
                raise ValueError(f"Annotation references an unknown image: {annotation['image_id']}")
            grouped[annotation["image_id"]].append(annotation["bbox"])
        for image_id, image in images.items():
            source_image = source_dir / image["file_name"]
            if not source_image.is_file():
                raise ValueError(f"Missing image: {source_image}")
            image_target = run_root / "data" / "images" / target_split / source_image.name
            label_target = run_root / "data" / "labels" / target_split / f"{source_image.stem}.txt"
            image_target.parent.mkdir(parents=True, exist_ok=True)
            label_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_image, image_target)
            labels = [yolo_label(box, image["width"], image["height"]) for box in grouped[image_id]]
            label_target.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
        totals[target_split] = len(images)
    yaml_path = run_root / "data" / "dataset.yaml"
    yaml_path.write_text(
        f"path: {(run_root / 'data').resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\n\nnames:\n  0: ant\n",
        encoding="utf-8",
    )
    return yaml_path, totals


def metrics(metrics: object) -> dict[str, float]:
    return {str(key): float(value) for key, value in getattr(metrics, "results_dict", {}).items() if isinstance(value, (int, float))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path, help="Normalized Roboflow COCO dataset root")
    parser.add_argument("--run-root", type=Path, default=Path("artifacts/antai-beta-round-1"), help="Ignored output directory")
    parser.add_argument("--resume", action="store_true", help="Resume a stopped run from its saved last.pt checkpoint")
    args = parser.parse_args()
    dataset_root, run_root = args.dataset_root.resolve(), args.run_root.resolve()
    if run_root.exists() and not args.resume: parser.error(f"Run output already exists: {run_root}; choose a new --run-root or pass --resume.")
    run_root.mkdir(parents=True, exist_ok=args.resume)
    try:
        if args.resume:
            yaml_path = run_root / "data" / "dataset.yaml"
            if not yaml_path.is_file(): raise ValueError(f"Cannot resume without prepared data: {yaml_path}")
            splits = {"train": len(list((run_root / "data" / "images" / "train").glob("*"))), "val": len(list((run_root / "data" / "images" / "val").glob("*"))), "test": len(list((run_root / "data" / "images" / "test").glob("*")))}
        else:
            yaml_path, splits = prepare_data(dataset_root, run_root)
        from ultralytics import YOLO
        pretrained = run_root.parent / "pretrained" / MODEL_NAME
        pretrained.parent.mkdir(parents=True, exist_ok=True)
        if not pretrained.is_file():
            YOLO(MODEL_NAME)
            shutil.move(MODEL_NAME, pretrained)
        last = run_root / "runs" / "train" / "weights" / "last.pt"
        if args.resume:
            if not last.is_file(): raise ValueError(f"Cannot resume without checkpoint: {last}")
            model = YOLO(str(last))
            train_result = model.train(resume=True)
        else:
            model = YOLO(str(pretrained))
            train_result = model.train(data=str(yaml_path), imgsz=IMAGE_SIZE, epochs=EPOCHS, batch=BATCH, device="cpu", workers=0, patience=10, seed=SEED, deterministic=True, pretrained=True, optimizer="auto", cos_lr=True, degrees=180, fliplr=0.5, mosaic=0.5, mixup=0.0, project=str(run_root / "runs"), name="train", exist_ok=False, verbose=True)
        best = Path(model.trainer.best)
        best_model = YOLO(str(best))
        test_result = best_model.val(data=str(yaml_path), split="test", imgsz=IMAGE_SIZE, batch=BATCH, device="cpu", workers=0, project=str(run_root / "runs"), name="test", exist_ok=False, verbose=True)
        exported = Path(best_model.export(format="onnx", imgsz=IMAGE_SIZE, dynamic=False, simplify=False))
        summary = {"created_at_utc": datetime.now(UTC).isoformat(), "status": "completed", "model": MODEL_NAME, "model_display_name": "AntAI - Beta", "image_size": IMAGE_SIZE, "epochs_requested": EPOCHS, "batch": BATCH, "device": "cpu", "seed": SEED, "data_split": splits, "best_weights": str(best), "onnx_export": str(exported), "validation_metrics": metrics(train_result), "held_out_test_metrics": metrics(test_result)}
        (run_root / "training_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except Exception:
        (run_root / "training_failed.txt").write_text("Training did not complete; preserve this output directory and inspect the terminal log.\n", encoding="utf-8")
        raise
if __name__ == "__main__": raise SystemExit(main())
