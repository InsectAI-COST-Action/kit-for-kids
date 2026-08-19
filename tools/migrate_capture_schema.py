"""Safely add motion-score columns to an existing camera captures.csv file.

Usage:
  py tools\\migrate_capture_schema.py D:\\

The tool preserves every row. Existing legacy rows receive empty score fields,
because the scores were not collected at the time. A timestamped backup remains
on the card until manually removed after verification.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

LEGACY_HEADER = [
    "schema_version", "device_id", "run_id", "boot_id", "capture_id", "captured_at_utc", "uptime_ms", "scheduled_ms",
    "outcome", "frame_width", "frame_height", "jpeg_bytes", "capture_ms", "inference_ms", "model_id", "prediction_count",
    "max_confidence", "image_path", "save_policy", "save_outcome", "error_code",
]
CURRENT_HEADER = LEGACY_HEADER[:-1] + ["motion_score", "motion_threshold", "error_code"]


def migrate(card_root: Path) -> tuple[int, int, Path]:
    capture_path = card_root / "raw" / "captures.csv"
    if not capture_path.is_file():
        raise FileNotFoundError(f"missing authoritative capture log: {capture_path}")
    temporary_path = capture_path.with_suffix(".csv.schema-migration.tmp")
    backup_path = capture_path.with_name(f"captures.pre-motion-schema-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv")
    with capture_path.open("r", newline="", encoding="utf-8") as source:
        reader = csv.reader(source)
        header = next(reader, None)
        if header == CURRENT_HEADER:
            return 0, 0, capture_path
        if header != LEGACY_HEADER:
            raise ValueError("captures.csv has an unknown header; no changes made")
        legacy_rows = current_rows = 0
        with temporary_path.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.writer(destination, lineterminator="\n")
            writer.writerow(CURRENT_HEADER)
            for row_number, row in enumerate(reader, start=2):
                if len(row) == len(LEGACY_HEADER):
                    writer.writerow(row[:-1] + ["", "", row[-1]])
                    legacy_rows += 1
                elif len(row) == len(CURRENT_HEADER):
                    writer.writerow(row)
                    current_rows += 1
                else:
                    raise ValueError(f"row {row_number} has {len(row)} columns; no changes made")
    shutil.copy2(capture_path, backup_path)
    temporary_path.replace(capture_path)
    return legacy_rows, current_rows, backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Add motion-score columns to an existing insect-camera captures.csv.")
    parser.add_argument("card_root", type=Path, help="Mounted card root, for example D:\\")
    args = parser.parse_args()
    legacy_rows, current_rows, backup = migrate(args.card_root.resolve())
    if legacy_rows == current_rows == 0:
        print("captures.csv already uses the current motion-score schema; no change made.")
    else:
        print(f"Migrated {legacy_rows} legacy rows and preserved {current_rows} current-format rows.")
        print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
