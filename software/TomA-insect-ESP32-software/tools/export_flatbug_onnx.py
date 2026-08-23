"""Export a local FlatBug-style Ultralytics segmentation checkpoint to ONNX."""
from __future__ import annotations
import argparse, hashlib, json, shutil, sys, tempfile
from pathlib import Path

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): value.update(block)
    return value.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    if not args.weights.is_file(): parser.error(f"checkpoint not found: {args.weights}")
    if args.output.suffix.lower() != ".onnx": parser.error("--output must end in .onnx")
    try:
        import onnx
        import ultralytics
        from ultralytics import YOLO
    except ImportError as error:
        parser.error(f"missing export dependency: {error}; install ultralytics, onnx, onnxscript, onnxslim and onnxruntime")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flatbug-onnx-") as folder:
        copied = Path(folder) / args.weights.name
        shutil.copy2(args.weights, copied)
        exported = Path(YOLO(str(copied), task="segment").export(format="onnx", imgsz=args.imgsz, opset=18, simplify=True, dynamic=False, half=False))
        shutil.copy2(exported, args.output)
    proto = onnx.load(str(args.output)); onnx.checker.check_model(proto)
    print(json.dumps({"checkpoint_sha256": digest(args.weights), "onnx_sha256": digest(args.output), "onnx_bytes": args.output.stat().st_size, "ultralytics": ultralytics.__version__, "onnx": onnx.__version__, "opsets": [item.version for item in proto.opset_import]}, indent=2))
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error: print(f"export failed: {error}", file=sys.stderr); raise SystemExit(1)
