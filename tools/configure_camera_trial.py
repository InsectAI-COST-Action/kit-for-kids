"""Create a short, labelled OV3660 image-quality trial configuration on an SD card.

Examples:
  py tools\\configure_camera_trial.py E:\\ --list
  py tools\\configure_camera_trial.py E:\\ --preset high_svga_q6_1fps
  py tools\\configure_camera_trial.py E:\\ --restore-pilot
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_NAME = "config.before-camera-quality-trial.json"
PRESETS = {
    "max_qxga_q12_2fps": {"capture_fps": 2, "frame_size": "QXGA", "jpeg_quality": 12},
    "max_qxga_q12_1fps": {"capture_fps": 1, "frame_size": "QXGA", "jpeg_quality": 12},
    "high_svga_q6_1fps": {"capture_fps": 1, "frame_size": "SVGA", "jpeg_quality": 6},
    "high_svga_q10_1fps": {"capture_fps": 1, "frame_size": "SVGA", "jpeg_quality": 10},
    "svga_q12_2fps": {"capture_fps": 2, "frame_size": "SVGA", "jpeg_quality": 12},
    "high_vga_q6_2fps": {"capture_fps": 2, "frame_size": "VGA", "jpeg_quality": 6},
    "baseline_vga_q12_2fps": {"capture_fps": 2, "frame_size": "VGA", "jpeg_quality": 12},
    "low_vga_q24_2fps": {"capture_fps": 2, "frame_size": "VGA", "jpeg_quality": 24},
}


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure a short OV3660 image-quality trial.")
    parser.add_argument("destination", type=Path, help="Mounted SD-card root, for example E:\\")
    parser.add_argument("--preset", choices=PRESETS, help="Named camera preset to install")
    parser.add_argument("--seconds", type=int, default=120, help="Trial duration: 30-600 seconds (default: 120)")
    parser.add_argument("--list", action="store_true", help="List presets without changing the card")
    parser.add_argument("--restore-pilot", action="store_true", help="Restore the saved pre-trial configuration (legacy helper)")
    parser.add_argument("--install-pilot-default", action="store_true", help="Install the current repository one-hour pilot default")
    args = parser.parse_args()

    if args.list:
        for name, value in PRESETS.items():
            print(f"{name:24} {value['frame_size']:4}  quality {value['jpeg_quality']:2}  {value['capture_fps']} FPS")
        return 0
    selected_actions = sum(value is not None for value in (args.preset,)) + int(args.restore_pilot) + int(args.install_pilot_default)
    if selected_actions != 1:
        parser.error("choose exactly one of --preset, --restore-pilot, or --install-pilot-default (use --list to see names)")
    if not 30 <= args.seconds <= 600:
        parser.error("--seconds must be between 30 and 600")

    destination = args.destination.resolve()
    if not destination.is_dir():
        parser.error(f"destination is not an existing directory: {destination}")
    config_path = destination / "config.json"
    backup_path = destination / BACKUP_NAME

    if args.install_pilot_default:
        shutil.copy2(ROOT / "config.example.json", config_path)
        print("Installed the repository one-hour pilot default.")
        return 0

    if args.restore_pilot:
        if backup_path.exists():
            shutil.copy2(backup_path, config_path)
            print(f"Restored {config_path.name} from {backup_path.name}.")
        else:
            shutil.copy2(ROOT / "config.example.json", config_path)
            print("No pre-trial backup found; installed the repository pilot default.")
        return 0

    if config_path.exists() and not backup_path.exists():
        shutil.copy2(config_path, backup_path)
        print(f"Saved the existing config as {backup_path.name}.")
    elif not config_path.exists():
        print("No existing config.json found; a trial config will be created.")

    preset = PRESETS[args.preset]
    trial_config: dict[str, object] = {
        "schema_version": 1,
        "capture_fps": preset["capture_fps"],
        "capture_interval_ms": 1000 // preset["capture_fps"],
        "max_session_seconds": args.seconds,
        "capture_mode": "quality_trial",
        "camera_preset": args.preset,
        "frame_size": preset["frame_size"],
        "jpeg_quality": preset["jpeg_quality"],
        "motion_trigger_enabled": False,
        "motion_threshold": 5,
        "model_id": "none",
        "log_level": "info",
    }
    write_json(config_path, trial_config)
    print(f"Installed {args.preset} for {args.seconds} seconds at {destination}.")
    print("Power off only after the session-complete serial message, then inspect the run and use camera_trial_report.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
