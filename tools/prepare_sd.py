r"""Copy the dashboard starter files to an already formatted SD-card directory.

Usage: py tools\prepare_sd.py E:\
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRECTORY = ROOT / "dashboard"


def copy_file(source: Path, destination: Path, dry_run: bool) -> None:
    print(f"{'Would copy' if dry_run else 'Copying'} {source.name} -> {destination}")
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a FAT32 SD-card directory for the insect camera.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example E:\\")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")

    for filename in ("dashboard.html", "dashboard.css", "dashboard.js", "analysis.js", "card-access.js", "favicon.svg", "site.webmanifest"):
        copy_file(ASSET_DIRECTORY / filename, destination / filename, args.dry_run)
    for filename in ("mediabunny.min.cjs", "mediabunny-LICENSE.txt", "README.md"):
        copy_file(ASSET_DIRECTORY / "vendor" / filename, destination / "vendor" / filename, args.dry_run)
    for filename in ("manifest.js", "summary.js"):
        runtime_file = destination / filename
        if runtime_file.exists():
            print(f"Leaving existing runtime {filename} unchanged")
        else:
            copy_file(ASSET_DIRECTORY / filename, runtime_file, args.dry_run)
    if not (destination / "config.json").exists():
        copy_file(ROOT / "config.example.json", destination / "config.json", args.dry_run)
    else:
        print("Leaving existing config.json unchanged")
    for directory in ("images", "raw", "data", "system"):
        target = destination / directory
        print(f"{'Would create' if args.dry_run else 'Ensuring'} {target}")
        if not args.dry_run:
            target.mkdir(exist_ok=True)
    print("SD-card preparation complete. Eject the card safely before inserting it in the camera.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
