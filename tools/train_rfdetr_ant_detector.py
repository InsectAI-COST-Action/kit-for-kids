#!/usr/bin/env python3
"""Fine-tune RF-DETR Small on a prepared one-class ant COCO dataset."""
from __future__ import annotations
import argparse, json, platform, sys
from datetime import UTC, datetime
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"): sys.stderr.reconfigure(encoding="utf-8")
import torch
from rfdetr import RFDETRSmall

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--num-workers", type=int, default=0)
    args = parser.parse_args()
    dataset, output = args.dataset.resolve(), args.output.resolve()
    required = [dataset / split / "_annotations.coco.json" for split in ("train", "valid", "test")]
    if not all(path.is_file() for path in required): raise SystemExit("Dataset must contain train/valid/test _annotations.coco.json files")
    output.mkdir(parents=True, exist_ok=True)
    request = {"created_at_utc": datetime.now(UTC).isoformat(), "architecture": "RF-DETR Small", "dataset": str(dataset), "epochs": args.epochs, "batch_size": args.batch_size, "resolution": args.resolution, "device": args.device, "num_workers": args.num_workers, "torch": torch.__version__, "cuda_available": torch.cuda.is_available(), "platform": platform.platform(), "class_mapping": {"ant": 1}}
    (output / "run_request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    model = RFDETRSmall()
    model.train(dataset_dir=str(dataset), output_dir=str(output), epochs=args.epochs, batch_size=args.batch_size, resolution=args.resolution, device=args.device, num_workers=args.num_workers, tensorboard=False, notes=request)
    print(f"Training completed. Outputs: {output}")
if __name__ == "__main__": main()
