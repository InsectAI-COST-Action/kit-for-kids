r"""Install the self-contained rehearsal dashboard demo beneath a mounted camera card.

Usage: py tools\install_dashboard_demo.py D:\

The demo is deliberately stored in <card-root>\demo and never alters real capture data.
Its photos are real reference ant images (datasets/ant-example-images), but the capture
timings and run structure around them are fabricated for rehearsal purposes - not a real
session. See demo-summary.js's own "note" field for the same disclosure in-app.

Images and AI models are also embedded as base64 into a generated demo-embedded-files.js
(not tracked in git - regenerated fresh on every install from the real files below) so the
whole demo works immediately on open with no "choose a folder" step: browsers refuse to let
a page read local files under file:// without a real folder-picker user gesture, and there
is no separate real card to point that picker at in a demo, so demo-autoload.js decodes this
fixture straight into window.InsectCard instead. See dashboard/demo-autoload.js.
"""
from __future__ import annotations

import argparse
import base64
import json
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
    DASHBOARD / "demo-autoload.js": Path("demo/demo-autoload.js"),
    DASHBOARD / "i18n.js": Path("demo/i18n.js"),
    DASHBOARD / "config.json": Path("demo/config.json"),
    DASHBOARD / "vendor" / "mediabunny.min.cjs": Path("demo/vendor/mediabunny.min.cjs"),
    DASHBOARD / "fixtures" / "demo-manifest.js": Path("demo/fixtures/demo-manifest.js"),
    DASHBOARD / "fixtures" / "demo-summary.js": Path("demo/fixtures/demo-summary.js"),
    DASHBOARD / "fixtures" / "demo-captures.js": Path("demo/fixtures/demo-captures.js"),
}
# Sourced from - and installed at - the same images/<run-id>/<shard>/<file>.jpg
# shape a real card uses (docs/data-schema.md), not a fixtures/images/ shortcut,
# because dashboard.js's gallery sets `image.src = capture.imagePath` directly (a
# plain <img> fetch, bypassing window.InsectCard entirely), so whatever imagePath
# dashboard/fixtures/demo-captures.js records must be a real, fetchable path on
# disk - this must stay in sync with demo-captures.js's own imagePath values.
# Kept at this same relative path in the source tree too (not just the installed
# copy) so dashboard/demo.html can also be opened directly without running the
# installer first, exactly like the old fixtures/images/ synthetic PNGs could.
DEMO_IMAGE_PREFIX = "images/demo_run_000001/shard_0001"
for image in sorted((DASHBOARD / DEMO_IMAGE_PREFIX).glob("*.jpg")):
    FILES[image] = Path("demo") / DEMO_IMAGE_PREFIX / image.name

# Sourced from dashboard/ai/, the same canonical AI pack tools/prepare_sd.py
# installs on a real card (AI_FILES) - this used to point at the older
# spikes/flatbug-browser spike, which only ever had FlatBug and had drifted
# out of sync with the real AI lineup (missing both AntAI models entirely).
AI_SOURCE = DASHBOARD / "ai"
FILES.update({
    AI_SOURCE / "flatbug-n.onnx": Path("demo/ai/flatbug-n.onnx"),
    AI_SOURCE / "antai-test.onnx": Path("demo/ai/antai-test.onnx"),
    AI_SOURCE / "ort.wasm.bundle.min.mjs": Path("demo/ai/ort.wasm.bundle.min.mjs"),
    AI_SOURCE / "ort-wasm-simd-threaded.wasm": Path("demo/ai/ort-wasm-simd-threaded.wasm"),
    AI_SOURCE / "LICENSE-onnxruntime.txt": Path("demo/ai/LICENSE-onnxruntime.txt"),
})

# The subset of FILES that window.InsectCard.fileByName()/fileFor() actually reads at
# runtime (dashboard/analysis.js) - these are the ones that need embedding so the demo
# works with zero folder-picker interaction. LICENSE/README files are just plain copies
# for inspection, never read by app code, so they stay out of the embedded fixture.
# Image names here match DEMO_IMAGE_PREFIX exactly - the same path imagePath records -
# so card.fileFor() resolves them by direct hit, not just its bare-filename fallback.
MIME_TYPES = {".jpg": "image/jpeg", ".onnx": "application/octet-stream", ".wasm": "application/wasm", ".mjs": "text/javascript"}
EMBED_FILES = [
    (image, f"{DEMO_IMAGE_PREFIX}/{image.name}")
    for image in sorted((DASHBOARD / DEMO_IMAGE_PREFIX).glob("*.jpg"))
] + [
    (AI_SOURCE / name, f"ai/{name}")
    for name in ("flatbug-n.onnx", "antai-test.onnx", "ort.wasm.bundle.min.mjs", "ort-wasm-simd-threaded.wasm")
]


def generate_embedded_files_js(destination: Path, dry_run: bool) -> None:
    target = destination / "demo" / "fixtures" / "demo-embedded-files.js"
    print(f"{'Would generate' if dry_run else 'Generating'} {target} from {len(EMBED_FILES)} real files")
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("window.InsectDemoFiles = window.InsectDemoFiles || [];\n")
        for source, relative_name in EMBED_FILES:
            record = {
                "name": relative_name,
                "type": MIME_TYPES.get(source.suffix.lower(), "application/octet-stream"),
                "base64": base64.b64encode(source.read_bytes()).decode("ascii"),
            }
            handle.write(f"window.InsectDemoFiles.push({json.dumps(record)});\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the rehearsal insect dashboard demo on a camera SD card.")
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
    generate_embedded_files_js(destination, args.dry_run)
    print("Rehearsal demo ready. Open demo\\demo.html - it opens already loaded, no folder to choose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
