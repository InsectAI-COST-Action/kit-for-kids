r"""Install the self-contained synthetic dashboard demo beneath a mounted camera card.

Usage: py tools\install_dashboard_demo.py D:\

The demo is deliberately stored in <card-root>\demo and never alters real capture data.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
FILES = {
    DASHBOARD / "demo.html": Path("demo/demo.html"),
    DASHBOARD / "dashboard.css": Path("demo/dashboard.css"),
    DASHBOARD / "dashboard.js": Path("demo/dashboard.js"),
    DASHBOARD / "analysis.js": Path("demo/analysis.js"),
    DASHBOARD / "settings.js": Path("demo/settings.js"),
    DASHBOARD / "card-access.js": Path("demo/card-access.js"),
    DASHBOARD / "config.json": Path("demo/config.json"),
    DASHBOARD / "vendor" / "mediabunny.min.cjs": Path("demo/vendor/mediabunny.min.cjs"),
    DASHBOARD / "fixtures" / "demo-manifest.js": Path("demo/fixtures/demo-manifest.js"),
    DASHBOARD / "fixtures" / "demo-summary.js": Path("demo/fixtures/demo-summary.js"),
    DASHBOARD / "fixtures" / "demo-captures.js": Path("demo/fixtures/demo-captures.js"),
}
for image in sorted((DASHBOARD / "fixtures" / "images").glob("*.png")):
    FILES[image] = Path("demo/fixtures/images") / image.name

AI_SOURCE = ROOT / "spikes" / "flatbug-browser"
FILES.update({
    AI_SOURCE / "assets" / "flatbug-n.onnx": Path("demo/ai/flatbug-n.onnx"),
    AI_SOURCE / "vendor" / "onnxruntime" / "ort.wasm.bundle.min.mjs": Path("demo/ai/ort.wasm.bundle.min.mjs"),
    AI_SOURCE / "vendor" / "onnxruntime" / "ort-wasm-simd-threaded.wasm": Path("demo/ai/ort-wasm-simd-threaded.wasm"),
})


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the synthetic insect dashboard demo on a camera SD card.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example D:\\")
    parser.add_argument("--dry-run", action="store_true", help="Show planned copies without writing")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")
    for source, relative_target in FILES.items():
        if not source.is_file():
            parser.error(f"required demo source is missing: {source}")
        target = destination / relative_target
        print(f"{'Would copy' if args.dry_run else 'Copying'} {source.name} -> {target}")
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print("Synthetic demo ready. Open demo\\demo.html, choose the demo folder itself, then start looking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
