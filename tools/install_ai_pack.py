r"""Add the browser AI pack to an existing camera SD card without a full re-prepare.

Usage: py tools\install_ai_pack.py D:\

As of 13 September 2026 a freshly prepared card already gets these files from
`tools\prepare_sd.py` - see docs/model-card.md for the redistribution decision
and docs/next-session.md for why this used to be a separate, opt-in step. This
script remains for adding the pack to an older card that predates that change,
without touching anything else prepare_sd.py would (config.json, manifest.js,
summary.js, captured data).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dashboard" / "ai"
FILES = ("flatbug-n.onnx", "antai-beta.onnx", "ort.wasm.bundle.min.mjs", "ort-wasm-simd-threaded.wasm", "LICENSE-onnxruntime.txt", "README.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add the browser AI pack (FlatBug Nano and AntAI - Beta) to a camera SD card.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example D:\\")
    parser.add_argument("--dry-run", action="store_true", help="Show planned copies without writing")
    parser.add_argument("--include-antai-beta", action="store_true", help="Deprecated: AntAI - Beta now installs unconditionally, kept only so existing scripts do not break")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")
    missing = [SOURCE / name for name in FILES if not (SOURCE / name).is_file()]
    if missing:
        parser.error("required local AI asset is missing: " + ", ".join(str(path) for path in missing))
    for name in FILES:
        source = SOURCE / name
        target = destination / "ai" / name
        print(f"{'Would copy' if args.dry_run else 'Copying'} {source.name} -> {target}")
        if not args.dry_run:
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source, target)
    print("AI package ready. Select the top camera-card folder in the dashboard; do not select the ai folder alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
