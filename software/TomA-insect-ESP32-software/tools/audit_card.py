"""Read-only integrity audit for a transferred insect-camera SD card."""
from __future__ import annotations
import argparse
import csv
import json
import re
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg"}
TEMP_SUFFIXES = {".tmp", ".part"}
CHUNK_PATTERN = re.compile(r'"(data/captures_[0-9]{6}\.js)"')


def card_path(root: Path, value: str) -> Path:
    return root / value.lstrip("/").replace("/", "\\")


def rel_path(root: Path, path: Path) -> str:
    return "/" + path.relative_to(root).as_posix()


def nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def audit(root: Path) -> dict:
    findings = []
    csv_path = root / "raw" / "captures.csv"
    rows = []
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            rows = list(csv.DictReader(handle))
    else:
        findings.append({"severity": "error", "code": "missing_raw_csv", "path": "/raw/captures.csv"})
    referenced = {row.get("image_path", "").strip() for row in rows if row.get("image_path", "").strip()}
    missing_images = sorted(path for path in referenced if not card_path(root, path).is_file())
    for path in missing_images:
        findings.append({"severity": "error", "code": "missing_referenced_image", "path": path})
    image_files = {rel_path(root, path): path for path in (root / "images").rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES}
    orphan_images = sorted(set(image_files) - referenced)
    for path in orphan_images:
        findings.append({"severity": "warning", "code": "unreferenced_complete_image", "path": path})
    temporary = sorted(rel_path(root, path) for path in (root / "images").rglob("*") if path.is_file() and path.suffix.lower() in TEMP_SUFFIXES)
    for path in temporary:
        findings.append({"severity": "warning", "code": "temporary_or_partial_file", "path": path})
    manifest_path = root / "manifest.js"
    listed = []
    if manifest_path.exists():
        listed = [path.lstrip("/") for path in CHUNK_PATTERN.findall(manifest_path.read_text(encoding="utf-8-sig", errors="replace"))]
    else:
        findings.append({"severity": "error", "code": "missing_manifest", "path": "/manifest.js"})
    available = sorted(rel_path(root, path).lstrip("/") for path in (root / "data").glob("captures_[0-9][0-9][0-9][0-9][0-9][0-9].js") if path.is_file())
    for path in sorted(set(listed) - set(available)):
        findings.append({"severity": "error", "code": "missing_manifest_chunk", "path": path})
    for path in sorted(set(available) - set(listed)):
        findings.append({"severity": "warning", "code": "unlisted_chunk", "path": path})
    closed_records = sum(nonempty_lines(card_path(root, path)) for path in listed)
    current_records = nonempty_lines(root / "data" / "captures_current.js")
    derived_records = closed_records + current_records
    if rows and derived_records != len(rows):
        findings.append({"severity": "warning", "code": "raw_derived_count_mismatch", "detail": f"raw={len(rows)} dashboard={derived_records}"})
    states = {}
    runs_dir = root / "raw" / "runs"
    for path in sorted(runs_dir.glob("run_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            run_id = record.get("run_id", path.stem)
            state = record.get("state", "unknown")
            states[run_id] = state
            if state == "running":
                findings.append({"severity": "warning", "code": "run_still_marked_running", "path": rel_path(root, path), "detail": run_id})
        except (OSError, json.JSONDecodeError) as exc:
            findings.append({"severity": "error", "code": "invalid_run_manifest", "path": rel_path(root, path), "detail": str(exc)})
    return {"card": str(root), "raw_capture_rows": len(rows), "referenced_images": len(referenced), "image_files": len(image_files), "missing_referenced_images": missing_images, "unreferenced_complete_images": orphan_images, "temporary_or_partial_files": temporary, "listed_chunks": listed, "available_chunks": available, "closed_chunk_records": closed_records, "current_chunk_records": current_records, "derived_dashboard_records": derived_records, "run_states": states, "findings": findings}


def print_report(report: dict) -> None:
    print(f"Card: {report['card']}")
    print(f"Raw capture rows: {report['raw_capture_rows']}")
    print(f"Referenced images: {report['referenced_images']} (files present: {report['image_files']})")
    print(f"Dashboard records: {report['derived_dashboard_records']} ({len(report['listed_chunks'])} listed chunks + current)")
    print(f"Temporary/partial files: {len(report['temporary_or_partial_files'])}")
    print(f"Run states: {', '.join(f'{run}={state}' for run, state in report['run_states'].items()) or 'none'}")
    if report["findings"]:
        print("Findings:")
        for finding in report["findings"]:
            print(f"- {finding['severity'].upper()} {finding['code']}: {finding.get('path', finding.get('detail', ''))}")
    else:
        print("Result: CLEAN")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an insect-camera SD card without changing it")
    parser.add_argument("card", type=Path, help="mounted SD-card root")
    parser.add_argument("--json", action="store_true", dest="as_json", help="write JSON")
    parser.add_argument("--strict", action="store_true", help="return 1 when findings exist")
    args = parser.parse_args()
    root = args.card.resolve()
    if not root.is_dir():
        parser.error(f"card root is not an existing directory: {root}")
    report = audit(root)
    print(json.dumps(report, indent=2) if args.as_json else "")
    if not args.as_json:
        print_report(report)
    return 1 if args.strict and report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
