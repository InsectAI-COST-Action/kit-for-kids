r"""Install the local FlatBug Nano browser package beneath a mounted camera card.

Usage: py tools\install_ai_pack.py D:\

The model remains local and ignored by Git pending redistribution approval.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "spikes" / "flatbug-browser"
ANTAI_BETA = ROOT / "artifacts" / "antai-beta-round-1" / "runs" / "train" / "weights" / "best.onnx"

FILES = {
    SOURCE / "assets" / "flatbug-n.onnx": Path("ai/flatbug-n.onnx"),
    SOURCE / "vendor" / "onnxruntime" / "ort.wasm.bundle.min.mjs": Path("ai/ort.wasm.bundle.min.mjs"),
    SOURCE / "vendor" / "onnxruntime" / "ort-wasm-simd-threaded.wasm": Path("ai/ort-wasm-simd-threaded.wasm"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the local FlatBug Nano AI package on a camera SD card.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example D:\\")
    parser.add_argument("--dry-run", action="store_true", help="Show planned copies without writing")
    parser.add_argument("--include-antai-beta", action="store_true", help="Also install the locally trained experimental AntAI - Beta model")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")
    files = dict(FILES)
    if args.include_antai_beta:
        files[ANTAI_BETA] = Path("ai/antai-beta.onnx")
    missing = [source for source in files if not source.is_file()]
    if missing:
        parser.error("required local AI asset is missing: " + ", ".join(str(path) for path in missing))
    for source, relative_target in files.items():
        target = destination / relative_target
        print(f"{'Would copy' if args.dry_run else 'Copying'} {source.name} -> {target}")
        if not args.dry_run:
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
    print("Local AI package ready. Select the top camera-card folder in the dashboard; do not select the ai folder alone.")
    if args.include_antai_beta: print("AntAI - Beta installed as an experimental ant-only option.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
