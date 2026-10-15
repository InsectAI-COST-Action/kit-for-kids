"""Flash and pre-configure a micro-SD card for the Pi Zero 2 W insect camera.

No Raspberry Pi Imager GUI involved, so many cards can be prepared the same
way. Windows only for now (it drives the installed Raspberry Pi Imager in its
command-line mode to write and verify the image).

What it does:
  1. Downloads the pinned Raspberry Pi OS Lite (64-bit) image once into a local
     cache, decompresses it, and checks it against Raspberry Pi's published
     SHA-256.
  2. Writes it to the chosen card with `rpi-imager --cli` (raw write plus
     read-back verification). Windows asks once for administrator approval.
  3. Writes cloud-init `user-data` and `network-config` onto the card's boot
     partition: hostname, the `pi` user with this PC's SSH public key (no
     password login), SSH on, and Raspberry Pi's official USB gadget mode, so
     the Pi appears as a USB network adapter on the data micro-USB port.

On first boot the Pi applies that configuration by itself (allow a few
minutes), after which `ssh pi@<hostname>.local` works over the USB cable.

Examples:
  py tools\\flash_card.py --list
  py tools\\flash_card.py --disk 1
  py tools\\flash_card.py --disk 1 --hostname insectcam-02 --yes
  set INSECTCAM_WIFI_PASSWORD=...  &  py tools\\flash_card.py --disk 1 --wifi-ssid "Home"

One-off per Windows PC, before the first USB connection: install Raspberry
Pi's USB gadget driver (see ../README.md).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import lzma
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Pinned image: Raspberry Pi OS Lite (64-bit), Trixie, from Raspberry Pi's
# own Imager catalogue (downloads.raspberrypi.com/os_list_imagingutility_v4.json,
# read 14 October 2026). Its init_format is "cloudinit-rpi" and it ships
# rpi-usb-gadget, which this tool relies on. Change all three together.
IMAGE_URL = ("https://downloads.raspberrypi.com/raspios_lite_arm64/images/"
             "raspios_lite_arm64-2026-10-06/2026-10-06-raspios-trixie-arm64-lite.img.xz")
IMAGE_SHA256 = "b8a393dc1c3701450b5fffbfe74368a98fb6eab7415ce456cc0cead886ea8780"  # of the decompressed .img
IMAGE_RELEASE = "2026-10-06"

IMAGER = Path(r"C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe")
CACHE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "insectcam" / "images"
MAX_CARD_BYTES = 128 * 1024**3  # anything bigger is unlikely to be a camera card
HOSTNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def powershell_json(command: str) -> list[dict]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"@({command}) | ConvertTo-Json -Depth 3 -Compress"],
        capture_output=True, text=True, check=True)
    text = result.stdout.strip()
    if not text:
        return []
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


def candidate_disks() -> list[dict]:
    """Removable-looking disks only; the system/boot disk is never offered."""
    disks = powershell_json(
        "Get-Disk | Select-Object Number,FriendlyName,BusType,Size,IsSystem,IsBoot,OperationalStatus")
    return [d for d in disks
            if not d.get("IsSystem") and not d.get("IsBoot")
            and str(d.get("BusType")) in {"USB", "SD", "MMC", "7", "12", "13"}
            and 0 < int(d.get("Size") or 0) <= MAX_CARD_BYTES]


def describe(disk: dict) -> str:
    return f"disk {disk['Number']}: {disk['FriendlyName']} ({int(disk['Size']) / 1024**3:.1f} GB, {disk['BusType']})"


def fetch_image() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    compressed = CACHE / IMAGE_URL.rsplit("/", 1)[1]
    image = compressed.with_suffix("")  # drop .xz
    verified_marker = image.with_suffix(".img.sha256-ok")
    if image.is_file() and verified_marker.is_file() and verified_marker.read_text().strip() == IMAGE_SHA256:
        print(f"Using cached, verified image {image}")
        return image
    if not compressed.is_file():
        print(f"Downloading Raspberry Pi OS Lite {IMAGE_RELEASE} (~525 MB) ...")
        partial = compressed.with_suffix(".xz.part")
        # Windows' own curl.exe (Windows certificate store): on this PC
        # Python's urllib rejected downloads.raspberrypi.com with "certificate
        # has expired" while curl accepted it (14 October 2026). Certificate
        # checking stays on either way; the SHA-256 below is the real guard.
        result = subprocess.run(["curl.exe", "--fail", "--location", "--retry", "3", "--continue-at", "-",
                                 "--output", str(partial), IMAGE_URL])
        if result.returncode != 0:
            sys.exit(f"Download failed (curl exit code {result.returncode}); run again to resume.")
        partial.replace(compressed)
    print("Decompressing and checking SHA-256 ...")
    digest = hashlib.sha256()
    with lzma.open(compressed) as source, image.open("wb") as target:
        while chunk := source.read(4 << 20):
            digest.update(chunk)
            target.write(chunk)
    if digest.hexdigest() != IMAGE_SHA256:
        image.unlink(missing_ok=True)
        sys.exit(f"Image checksum mismatch ({digest.hexdigest()}); refusing to use it.")
    verified_marker.write_text(IMAGE_SHA256)
    print("Image verified against Raspberry Pi's published checksum.")
    return image


def run_elevated(inner: str) -> int:
    """Run PowerShell text in an elevated PowerShell (one Windows administrator prompt)."""
    encoded = base64.b64encode(inner.encode("utf-16-le")).decode("ascii")
    script = (f"$p = Start-Process powershell -Verb RunAs -Wait -PassThru "
              f"-ArgumentList '-NoProfile','-EncodedCommand','{encoded}'; exit $p.ExitCode")
    return subprocess.run(["powershell", "-NoProfile", "-Command", script]).returncode


def write_image(image: Path, disk_number: int) -> None:
    if not IMAGER.is_file():
        sys.exit(f"Raspberry Pi Imager not found at {IMAGER}")
    target = rf"\\.\PhysicalDrive{disk_number}"
    print(f"Writing {image.name} to {target} with Raspberry Pi Imager (approve the Windows prompt) ...")
    # Imager is a GUI-subsystem program that demands elevation, so everything
    # runs in one elevated PowerShell (one administrator prompt) that is waited
    # on; Imager's own output is not visible here, only its exit code.
    #
    # The card's drive letters are released first: a card previously written by
    # this tool has a Linux partition that Windows shows as an unformatted
    # volume with a drive letter, and with that letter in place Imager exits
    # after a second with code 1 and no message (14 October 2026). A blank card
    # has no such volume, which is why the first card worked.
    inner = (
        f"foreach ($part in Get-Partition -DiskNumber {disk_number} -ErrorAction SilentlyContinue) {{ "
        f"if ($part.DriveLetter) {{ Remove-PartitionAccessPath -DiskNumber {disk_number} "
        f"-PartitionNumber $part.PartitionNumber -AccessPath ($part.DriveLetter + ':\\') -ErrorAction SilentlyContinue }} }}; "
        f"Start-Sleep 2; "
        f"$p = Start-Process -FilePath '{IMAGER}' -ArgumentList '--cli','--quiet','\"{image}\"','{target}' "
        f"-WorkingDirectory '{IMAGER.parent}' -Wait -PassThru -NoNewWindow; exit $p.ExitCode")
    code = run_elevated(inner)
    if code != 0:
        sys.exit(f"Raspberry Pi Imager failed or was cancelled (exit code {code}).")
    print("Image written and verified by Imager.")


def find_boot_partition(disk_number: int, timeout_s: int = 600) -> Path:
    # Imager ejects the card when it finishes (seen 14 October 2026), so the
    # boot partition only reappears once the card is pulled out and pushed
    # back in. Wait for that rather than failing.
    print("Remove the card and push it back in, so Windows mounts its boot partition ...", flush=True)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        # Same eligibility rule as before writing: never touch a disk that is
        # not a removable card (an ejected card reports size 0 until reinserted).
        if not any(int(d["Number"]) == disk_number for d in candidate_disks()):
            time.sleep(3)
            continue
        try:
            parts = powershell_json(
                f"Get-Partition -DiskNumber {disk_number} -ErrorAction Stop | "
                "Select-Object PartitionNumber,DriveLetter,Size")
        except subprocess.CalledProcessError:
            parts = []
        if parts and not any(str(part.get("DriveLetter") or "").strip().strip("\x00") for part in parts):
            # write_image() released the card's drive letters so Imager could lock
            # it, and Windows does not hand them back by itself. Partition 1 is
            # the FAT32 boot partition. Needs administrator rights.
            print("Giving the boot partition a drive letter (approve the Windows prompt) ...", flush=True)
            run_elevated(f"Add-PartitionAccessPath -DiskNumber {disk_number} -PartitionNumber 1 -AssignDriveLetter")
            time.sleep(3)
            continue
        for part in parts:
            letter = str(part.get("DriveLetter") or "").strip()
            if letter and letter != "\u0000" and (Path(f"{letter}:/") / "cmdline.txt").is_file():
                return Path(f"{letter}:/")
        time.sleep(3)
    sys.exit("Card written, but its boot partition did not appear. Remove and reinsert the card, "
             "then run again with --configure-only.")


def public_key(path: Path | None) -> str:
    candidates = [path] if path else [Path.home() / ".ssh" / name for name in ("id_ed25519.pub", "id_rsa.pub")]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    sys.exit("No SSH public key found (looked for ~/.ssh/id_ed25519.pub and id_rsa.pub). "
             "Create one with: ssh-keygen -t ed25519")


def user_data(hostname: str, key: str) -> str:
    # Format from Raspberry Pi's "Cloud-init on Raspberry Pi OS" article and
    # the rpi-usb-gadget README. No password: login is by SSH key only.
    return f"""#cloud-config
# Written by software/pi-zero-cam/tools/flash_card.py (image {IMAGE_RELEASE}).

hostname: {hostname}
manage_etc_hosts: true
timezone: Europe/London
keyboard:
  model: pc105
  layout: gb

users:
  - name: pi
    groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - {key}
    sudo: ALL=(ALL) NOPASSWD:ALL

ssh_pwauth: false

rpi:
  enable_usb_gadget: true

enable_ssh: true
"""


def network_config(wifi_ssid: str | None, wifi_password: str | None) -> str:
    if not wifi_ssid:
        # USB only: rpi-usb-gadget manages usb0 itself; nothing else to set.
        return "network:\n  version: 2\n"
    return f"""network:
  version: 2
  wifis:
    renderer: NetworkManager
    wlan0:
      dhcp4: true
      regulatory-domain: "GB"
      access-points:
        {json.dumps(wifi_ssid)}:
          password: {json.dumps(wifi_password or "")}
      optional: true
"""


def configure(boot: Path, hostname: str, key: str, wifi_ssid: str | None, wifi_password: str | None,
              dev: bool = False) -> None:
    if not (boot / "user-data").is_file() and not (boot / "meta-data").is_file():
        print("Warning: no cloud-init files on this card's boot partition; this image may not support cloud-init.")
    (boot / "user-data").write_text(user_data(hostname, key), encoding="utf-8", newline="\n")
    (boot / "network-config").write_text(network_config(wifi_ssid, wifi_password), encoding="utf-8", newline="\n")
    # Keep the system partition at the image's own size: the image's first boot
    # would otherwise expand it to fill the card ("resize" on the kernel command
    # line), leaving no room for the separate photo partition that pi/install.sh
    # adds (so that the system partition can be read-only).
    cmdline = boot / "cmdline.txt"
    tokens = cmdline.read_text(encoding="utf-8").split()
    cmdline.write_text(" ".join(t for t in tokens if t != "resize") + "\n", encoding="utf-8", newline="\n")
    if dev:
        # Development: keep the USB network link (SSH over USB) instead of
        # presenting the photo drive at power-up. See pi/insectcam-boot.
        (boot / "insectcam-dev").write_text("", encoding="utf-8")
    print(f"Configured {boot}: hostname {hostname}, user pi (SSH key only), USB gadget on"
          + (f", Wi-Fi {wifi_ssid}" if wifi_ssid else ", no Wi-Fi") + (", development flag" if dev else "") + ".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Flash and pre-configure a Pi Zero 2 W camera card.")
    parser.add_argument("--list", action="store_true", help="list cards this tool would accept, then stop")
    parser.add_argument("--disk", type=int, help="Windows disk number of the card (see --list)")
    parser.add_argument("--hostname", default="insectcam", help="network name; reach it as <hostname>.local")
    parser.add_argument("--ssh-key", type=Path, help="public key file (default: ~/.ssh/id_ed25519.pub or id_rsa.pub)")
    parser.add_argument("--wifi-ssid", help="optional Wi-Fi for development; password from INSECTCAM_WIFI_PASSWORD")
    parser.add_argument("--dev", action="store_true", help="development card: keep SSH over USB at power-up")
    parser.add_argument("--configure-only", action="store_true", help="skip writing the image; only write cloud-init files")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation before erasing the card")
    args = parser.parse_args()

    disks = candidate_disks()
    if args.list or args.disk is None:
        print("Cards this tool would accept:" if disks else "No removable card found.")
        for disk in disks:
            print("  " + describe(disk))
        return 0 if args.list else 2

    disk = next((d for d in disks if int(d["Number"]) == args.disk), None)
    # --configure-only may start while the card is still ejected; the
    # partition wait below applies the same check once it is back.
    if disk is None and not args.configure_only:
        sys.exit(f"Disk {args.disk} is not a removable card this tool will write to. Run with --list.")
    if not HOSTNAME_PATTERN.match(args.hostname):
        sys.exit("Hostname must be lower-case letters, digits and hyphens.")
    key = public_key(args.ssh_key)
    wifi_password = os.environ.get("INSECTCAM_WIFI_PASSWORD")
    if args.wifi_ssid and not wifi_password:
        sys.exit("Set INSECTCAM_WIFI_PASSWORD for the Wi-Fi password (kept out of shell history and this repo).")

    if not args.configure_only:
        print(f"About to ERASE {describe(disk)}.")
        if not args.yes and input("Type ERASE to continue: ").strip() != "ERASE":
            print("Cancelled.")
            return 1
        write_image(fetch_image(), args.disk)
    configure(find_boot_partition(args.disk), args.hostname, key, args.wifi_ssid, wifi_password, args.dev)
    print(f"Done. Put the card in the Pi, connect the micro-USB port next to the mini-HDMI to this PC, "
          f"wait a few minutes for first boot, then: ssh pi@{args.hostname}.local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
