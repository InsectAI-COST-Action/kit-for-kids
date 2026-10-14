# Pi Zero 2 W insect camera (exploratory)

Branch `Pi-zero-cam3`, started 14 October 2026. An alternative to the XIAO ESP32S3 Sense camera in [`../TomA-insect-ESP32-software`](../TomA-insect-ESP32-software): a Raspberry Pi Zero 2 W with a Raspberry Pi Camera Module 3.

**Why:** the OV5640 on the XIAO Sense board overheats (it melted a rubber band through its heatsink, even at a 5 s capture interval). The XIAO Sense board supplies the OV5640 core from a 1.3 V regulator, below the sensor's 1.425-1.575 V range, so the sensor falls back on its internal regulator, which OmniVision's datasheet warns causes "a potential heat issue". That is a hardware problem, not fixable in firmware. See `../TomA-insect-ESP32-software/docs/hardware-validation.md` on branch `wip/camera-ov5640`.

**Status (14 October 2026):** (1) connected over USB and (2) camera confirmed. (3) Porting: the capture loop is done (`insectcam/capture.py`); still to port are the phone hotspot and control app with peek, and how the photos reach the dashboard (the Pi's card is Linux-formatted, so Windows cannot just open it the way it opens the XIAO's FAT card).

### First results

10-minute run, 1 photo/s, 2304x1296 JPEG q85, sensor streaming at 5 fps with continuous autofocus, bare board in open air:

- **606/606 photos**, interval mean 1,000 ms, max 1,154 ms; run `finished`.
- **~140 ms of work per photo** (JPEG encode ~99 ms, card write ~33 ms) - against 600-690 ms on the XIAO/OV5640.
- **Processor 39.7 -> 40.8 C, flat after 4 minutes; camera sensor 28 -> 37 C**, levelling off; never throttled; CPU load ~0. The OV5640 melted a rubber band.
- Photos 284-306 KB; autofocus held focused (`AfState 2`) throughout.
- The ESP32 project's `tools/audit_card.py`, run on Windows against the Pi's data, reports CLEAN. (Run it on Windows: it converts paths with backslashes, so on Linux it cannot find the dashboard chunks.)

Full 12 MP (4608x2592) is available (`"frame_size": "12MP"` in `config.json`): ~400 ms encode, ~950 KB per photo.

### Getting photos off: the Pi appears as a USB drive

Owner decision (14 October 2026): plug the Pi into a computer and it shows up as a drive named **INSECT-AI** holding the dashboard and photos - the same files and drive name as a XIAO card, opened the same way, with no card to remove.

`pi/insectcam-drive` (install to `/usr/local/sbin/`) manages it. The photos live in a FAT32 disk image, `/srv/insectcam-card.img`. In capture mode the Pi mounts it at `/srv/insectcam`; in transfer mode it unmounts it and presents it over USB with Linux's `g_mass_storage`. **Never both at once**: two writers on one FAT filesystem corrupt it. The script refuses to switch to transfer mode while the capture service runs, and runs `fsck.vfat` before remounting in case the computer was unplugged mid-copy.

```
sudo insectcam-drive create 2048        # once
sudo insectcam-drive mount
# copy the dashboard in: prepare_card() from ../TomA-insect-ESP32-software/tools/prepare_sd.py
sudo insectcam-drive transfer-test 180  # development: drive for 3 min, then back to USB networking
```

Verified 14 October 2026: after a 56-photo capture into the image, Windows showed `D: INSECT-AI` (FAT32, 2 GB) within 11 s; `audit_card.py D:\` reported CLEAN; the Pi then returned to USB networking and remounted with all 56 photos intact.

Still to build: choosing the mode automatically at start-up (computer attached on the data port: drive; power bank or no computer: capture).

### Running the capture service by hand

```
scp -r insectcam pi@insectcam.local:/opt/insectcam/
ssh pi@insectcam.local "cd /opt/insectcam && python3 -m insectcam.capture --data-root /srv/insectcam"
```

Needs `python3-picamera2` (`sudo apt install python3-picamera2`; the Lite image does not include it). For internet on the Pi during development, Windows Internet Connection Sharing from Wi-Fi to the Pi's USB adapter works and the Pi switches to it automatically.

## Preparing a card without the Imager GUI

`tools/flash_card.py` writes the pinned Raspberry Pi OS Lite (64-bit, Trixie) image and configures it, so many cards can be prepared identically:

```
py tools\flash_card.py --list
py tools\flash_card.py --disk 1 --hostname insectcam
```

It downloads and checksum-verifies the image once (cached in `%LOCALAPPDATA%\insectcam\images`), writes it with Raspberry Pi Imager's command-line mode (one Windows administrator prompt per card; Imager re-reads the card to verify), then writes cloud-init `user-data` and `network-config` onto the card's boot partition:

- hostname (`<hostname>.local` on the USB link);
- user `pi`, **SSH key only**, no password (the key is this PC's `~/.ssh/id_ed25519.pub` or `id_rsa.pub`);
- SSH enabled;
- Raspberry Pi's official USB gadget mode (`rpi: enable_usb_gadget: true`, package [`rpi-usb-gadget`](https://github.com/raspberrypi/rpi-usb-gadget), Apache-2.0, preinstalled in the image).

No Wi-Fi password goes on the card unless `--wifi-ssid` is given (password from the `INSECTCAM_WIFI_PASSWORD` environment variable). This keeps the Pi's own Wi-Fi free for the children's phone hotspot later.

Formats follow Raspberry Pi's [Cloud-init on Raspberry Pi OS](https://www.raspberrypi.com/news/cloud-init-on-raspberry-pi-os/) and the `rpi-usb-gadget` README. The installed Imager (1.8) has no cloud-init options on its command line, which is why the tool writes those files itself after the image.

## Connecting over USB

1. **Once per Windows PC:** install Raspberry Pi's USB gadget driver, `rpi-usb-gadget-driver-setup.exe` from the [rpi-usb-gadget releases](https://github.com/raspberrypi/rpi-usb-gadget/releases) (v1.0.6). Windows has no built-in driver for this device. Needs administrator rights.
2. Plug the cable into the Pi's micro-USB port **next to the mini-HDMI** (labelled USB), not the one labelled PWR. That one cable powers the Pi and carries the network.
3. Wait a few minutes on first boot (cloud-init applies the settings, then the USB network starts).
4. `ssh pi@insectcam.local`

The Pi hands this PC an address on its own small network (`10.12.194.0/28`, Pi at `10.12.194.1`). For internet on the Pi (installing packages), turn on Windows Internet Connection Sharing from the Wi-Fi adapter to the Raspberry Pi USB adapter; the Pi notices and switches to using it.
