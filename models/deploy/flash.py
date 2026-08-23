import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def find_esptool_base():
    """Return the command list to run esptool (python -m esptool preferred)."""
    # If esptool is installed as a Python package in this environment, use it.
    if importlib.util.find_spec("esptool"):
        return [sys.executable, "-m", "esptool"]

    # Otherwise, look for the esptool console script on PATH.
    exe = shutil.which("esptool")
    if exe:
        return [exe]

    return None


def main():
    parser = argparse.ArgumentParser(description="Flash AntTestModel to ESP32-S3")
    parser.add_argument("--port", default="COM4", help="Serial port (default: COM4)")
    parser.add_argument("--baud", default="460800", help="Baud rate (default: 460800)")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    base = find_esptool_base()
    if base is None:
        print("esptool is not installed. Run: python -m pip install -r requirements.txt")
        sys.exit(1)

    cmd = base + [
        "--chip", "esp32s3",
        "-p", args.port,
        "--baud", args.baud,
        "--before", "default-reset",
        "--after", "hard-reset",
        "write-flash",
        "-z",
        "--flash-mode", "dio",
        "--flash-freq", "80m",
        "--flash-size", "8MB",
        "0x0", str(script_dir / "bootloader.bin"),
        "0x10000", str(script_dir / "AntTestModel.bin"),
        "0x8000", str(script_dir / "partition-table.bin"),
    ]

    print("Flashing AntTestModel...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Done.")


if __name__ == "__main__":
    main()
