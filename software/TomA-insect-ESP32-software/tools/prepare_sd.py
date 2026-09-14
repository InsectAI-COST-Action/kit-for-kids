r"""Copy the dashboard starter files to an already formatted SD-card directory.

Usage: py tools\prepare_sd.py E:\

For a full new-device walkthrough (flash the board, then prepare the card in one
step), use ``py tools\setup_device.py`` instead; it calls ``prepare_card`` below.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = ROOT / "dashboard"

# The dashboard's folder picker (Load camera card) tells the child which drive to
# choose by name - see the "INSECT-AI" wording in dashboard.html, dashboard.js,
# analysis.js and settings.js - so the card actually needs to be named that.
CARD_VOLUME_LABEL = "INSECT-AI"

STATIC_DASHBOARD_FILES = (
    "dashboard.html",
    "dashboard.css",
    "dashboard.js",
    "settings.js",
    "analysis.js",
    "card-access.js",
    "i18n.js",
    "favicon.svg",
    "site.webmanifest",
)
VENDOR_FILES = ("mediabunny.min.cjs", "mediabunny-LICENSE.txt", "README.md")
# AI models ship by default as of 13 September 2026 - see docs/model-card.md for
# the redistribution decision and docs/next-session.md for why this used to be
# a separate opt-in step (tools/install_ai_pack.py still works, for adding the
# pack to an older card without a full re-prepare).
AI_FILES = ("flatbug-n.onnx", "antai-beta.onnx", "ort.wasm.bundle.min.mjs", "ort-wasm-simd-threaded.wasm", "LICENSE-onnxruntime.txt", "README.md")
RUNTIME_FILES = ("manifest.js", "summary.js")
CARD_DIRECTORIES = ("images", "raw", "data", "system")


def copy_file(source: Path, destination: Path, dry_run: bool) -> None:
    print(f"{'Would copy' if dry_run else 'Copying'} {source.name} -> {destination}")
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def set_volume_label(root: Path, label: str) -> bool:
    """Best-effort: name the drive so it matches what the dashboard tells the child to look for.

    Windows only for now - this never raises, so a failed rename does not stop the
    rest of card preparation; the caller prints manual instructions if it returns False.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        drive = f"{root.drive}\\" if root.drive else str(root)
        return bool(ctypes.windll.kernel32.SetVolumeLabelW(ctypes.c_wchar_p(drive), ctypes.c_wchar_p(label)))
    except OSError:
        return False


def prepare_card(destination: Path, dry_run: bool = False) -> None:
    """Install the dashboard, folders and default config on a mounted card root.

    Existing pictures, ``config.json`` and the runtime ``manifest.js`` /
    ``summary.js`` are left untouched, so this is safe to re-run on a card that
    already holds a session.
    """
    for filename in STATIC_DASHBOARD_FILES:
        copy_file(ASSET_DIRECTORY / filename, destination / filename, dry_run)
    for filename in VENDOR_FILES:
        copy_file(ASSET_DIRECTORY / "vendor" / filename, destination / "vendor" / filename, dry_run)
    for filename in AI_FILES:
        copy_file(ASSET_DIRECTORY / "ai" / filename, destination / "ai" / filename, dry_run)
    for filename in RUNTIME_FILES:
        runtime_file = destination / filename
        if runtime_file.exists():
            print(f"Leaving existing runtime {filename} unchanged")
        else:
            copy_file(ASSET_DIRECTORY / filename, runtime_file, dry_run)
    if not (destination / "config.json").exists():
        copy_file(ROOT / "config.example.json", destination / "config.json", dry_run)
    else:
        print("Leaving existing config.json unchanged")
    for directory in CARD_DIRECTORIES:
        target = destination / directory
        print(f"{'Would create' if dry_run else 'Ensuring'} {target}")
        if not dry_run:
            target.mkdir(exist_ok=True)
    if dry_run:
        print(f"Would name the drive '{CARD_VOLUME_LABEL}'")
    elif set_volume_label(destination, CARD_VOLUME_LABEL):
        print(f"Named the drive '{CARD_VOLUME_LABEL}'")
    else:
        print(
            f"Could not rename the drive automatically - name it '{CARD_VOLUME_LABEL}' yourself\n"
            "(Windows: File Explorer -> right-click the drive -> Rename; macOS: Finder -> select\n"
            "the drive -> press Return to rename) so it's the one the dashboard tells you to pick."
        )
    print("SD-card preparation complete. Eject the card safely before inserting it in the camera.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a FAT32 SD-card directory for the insect camera.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example E:\\")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")
    prepare_card(destination, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
