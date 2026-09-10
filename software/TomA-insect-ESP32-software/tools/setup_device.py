r"""One-command setup for a new insect camera.

This does the two device-specific steps in order:

1. Build and upload the firmware to a connected XIAO ESP32S3 Sense board.
2. Install the dashboard, folders and default ``config.json`` on the camera's
   microSD card (the card must already be formatted FAT32 and mounted).

Typical use, fully interactive -- it finds the board, asks before flashing, then
asks for the card's drive letter::

    py tools\setup_device.py

Non-interactive / scripted::

    py tools\setup_device.py --port COM5 --card E:\ --yes
    py tools\setup_device.py --flash-only --port COM5
    py tools\setup_device.py --skip-flash --card E:\

The firmware step is a thin wrapper around
``py -m platformio run -e xiao_esp32s3 -t upload``; the card step calls
``prepare_card`` from ``prepare_sd.py`` so there is one source of truth for what
a prepared card contains.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sd import ROOT, prepare_card  # noqa: E402

PIO_ENV = "xiao_esp32s3"
ESPRESSIF_USB_VID = "303A"


def run_platformio(args: list[str]) -> None:
    command = [sys.executable, "-m", "platformio", *args]
    print(f"\n$ {' '.join(command)}\n")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"PlatformIO exited with code {result.returncode}")


def list_serial_ports() -> list[dict]:
    command = [sys.executable, "-m", "platformio", "device", "list", "--json-output"]
    try:
        output = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return json.loads(output)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def looks_like_board(entry: dict) -> bool:
    hwid = (entry.get("hwid") or "").upper()
    return f"VID:PID={ESPRESSIF_USB_VID}" in hwid or f"{ESPRESSIF_USB_VID}:" in hwid


def choose_port(explicit: str | None, assume_yes: bool) -> str:
    if explicit:
        return explicit
    ports = list_serial_ports()
    candidates = [entry for entry in ports if looks_like_board(entry)] or ports
    if not candidates:
        raise SystemExit(
            "No serial ports found. Connect the board with a DATA USB-C cable, then retry.\n"
            "If it still does not appear, hold BOOT, tap RESET, release BOOT and retry."
        )
    if len(candidates) == 1:
        port = candidates[0]["port"]
        print(f"Found board on {port} ({candidates[0].get('description', 'unknown')}).")
        if not assume_yes and not _confirm(f"Flash the board on {port}?"):
            raise SystemExit("Stopped at user request.")
        return port
    print("More than one serial port found:")
    for index, entry in enumerate(candidates, start=1):
        print(f"  {index}. {entry['port']}  {entry.get('description', '')}")
    if assume_yes:
        raise SystemExit("Multiple ports found; re-run with --port COMx.")
    choice = input("Choose the board's number (or press Enter to cancel): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
        raise SystemExit("No port chosen.")
    return candidates[int(choice) - 1]["port"]


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        raise SystemExit(
            f"'{question}' needs an answer, but this terminal is non-interactive. "
            "Re-run with --yes, or answer the prompt directly."
        )


def choose_card(explicit: str | None, assume_yes: bool) -> Path:
    if explicit:
        raw = explicit.strip()
    else:
        try:
            raw = input(
                "\nMounted SD-card drive (for example E:\\), or press Enter to skip the card step: "
            ).strip()
        except EOFError:
            raw = ""
    if not raw:
        raise SystemExit("No card drive given; skipping card preparation.")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a mounted drive/folder: {root}")
    _warn_if_not_fat32(root, assume_yes)
    return root


def _warn_if_not_fat32(root: Path, assume_yes: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        filesystem = ctypes.create_unicode_buffer(64)
        drive = f"{root.drive}\\" if root.drive else str(root)
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive), None, 0, None, None, None, filesystem, ctypes.sizeof(filesystem)
        )
        label = filesystem.value.upper()
        if label and label != "FAT32":
            print(
                f"\nWARNING: {drive} is formatted {filesystem.value}, not FAT32.\n"
                "The camera can only read FAT32 cards of 32 GB or less. Format it FAT32 first\n"
                "(File Explorer -> right-click the drive -> Format), then re-run this step."
            )
            if not assume_yes and not _confirm("Continue anyway?"):
                raise SystemExit("Stopped so the card can be reformatted FAT32.")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flash a new insect-camera board and prepare its SD card in one step.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", help="Serial port of the board, e.g. COM5. Auto-detected if omitted.")
    parser.add_argument("--card", help="Mounted SD-card root, e.g. E:\\. Prompted for if omitted.")
    parser.add_argument("--flash-only", action="store_true", help="Flash the firmware, skip the card step.")
    parser.add_argument("--skip-flash", action="store_true", help="Prepare the card only, skip flashing.")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation before flashing.")
    parser.add_argument("--dry-run", action="store_true", help="Card step only: show planned changes.")
    args = parser.parse_args()

    if args.flash_only and args.skip_flash:
        parser.error("--flash-only and --skip-flash are mutually exclusive")

    if not args.skip_flash:
        print("== Step 1 of 2: firmware ==")
        port = choose_port(args.port, args.yes)
        run_platformio(["run", "-e", PIO_ENV, "-t", "upload", "--upload-port", port])
        print("\nFirmware uploaded. The board restarts on its own.")

    if not args.flash_only:
        print("\n== Step 2 of 2: SD card ==")
        card = choose_card(args.card, args.yes)
        prepare_card(card, args.dry_run)

    print(
        "\nDone. To start a capture session:\n"
        "  1. Disconnect the board from power.\n"
        "  2. Safely eject the card and insert it into the board's slot.\n"
        "  3. Connect the battery pack. Capture begins after a short warm-up.\n"
        "Never insert or remove the card while the board has power."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
