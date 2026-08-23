#!/usr/bin/env python3
"""Stage a one-class RF-DETR COCO dataset from a Roboflow COCO ZIP export."""
from __future__ import annotations
import argparse, json, shutil, tempfile, zipfile
from collections import Counter
from pathlib import Path

SPLITS = ("train", "valid", "test")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    source, output = args.zip.resolve(), args.output.resolve()
    if not source.is_file(): raise SystemExit(f"COCO ZIP not found: {source}")
    if output.exists():
        if not args.replace: raise SystemExit(f"Destination exists: {output} (pass --replace)")
        shutil.rmtree(output)
    with tempfile.TemporaryDirectory(prefix="rfdetr_coco_") as temp:
        root = Path(temp)
        with zipfile.ZipFile(source) as archive: archive.extractall(root)
        totals = Counter()
        for split in SPLITS:
            annotation_path = root / split / "_annotations.coco.json"
            if not annotation_path.is_file(): raise SystemExit(f"Missing annotations: {annotation_path}")
            document = json.loads(annotation_path.read_text(encoding="utf-8"))
            images = document.get("images", [])
            document["annotations"] = [{**item, "category_id": 1} for item in document.get("annotations", [])]
            document["categories"] = [{"id": 1, "name": "ant", "supercategory": "insect"}]
            image_destination = output / split
            image_destination.mkdir(parents=True, exist_ok=True)
            for image in images:
                source_image = root / split / image["file_name"]
                if not source_image.is_file(): raise SystemExit(f"Missing exported image: {source_image}")
                shutil.copy2(source_image, image_destination / image["file_name"])
            (image_destination / "_annotations.coco.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
            totals[f"{split}_images"] = len(images)
            totals[f"{split}_annotations"] = len(document["annotations"])
    provenance = {"source_zip": str(source), "class_mapping": {"ant": "ant", "ants": "ant"}, "splits": dict(totals)}
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(provenance, indent=2))
if __name__ == "__main__": main()
