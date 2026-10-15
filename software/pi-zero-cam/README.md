# Pi Zero 2 W insect camera (exploratory)

Branch `Pi-zero-cam3`, started 14 October 2026. An alternative to the XIAO ESP32S3 Sense camera in [`../TomA-insect-ESP32-software`](../TomA-insect-ESP32-software): a Raspberry Pi Zero 2 W with a Raspberry Pi Camera Module 3.

**Why:** the OV5640 on the XIAO Sense board overheats (it melted a rubber band through its heatsink, even at a 5 s capture interval). The XIAO Sense board supplies the OV5640 core from a 1.3 V regulator, below the sensor's 1.425-1.575 V range, so the sensor falls back on its internal regulator, which OmniVision's datasheet warns causes "a potential heat issue". That is a hardware problem, not fixable in firmware. See `../TomA-insect-ESP32-software/docs/hardware-validation.md` on branch `wip/camera-ov5640`.

**Status (15 October 2026):** working end to end on one Pi. Capture, phone hotspot and control app (peek, finish, start again, settings), the INSECT-AI USB drive, automatic mode choice at power-up, and a read-only system partition are all built and tested. Not built: the master image for batch setup, one-click flashing.

### First results

10-minute run, 1 photo/s, 2304x1296 JPEG q85, sensor streaming at 5 fps with continuous autofocus, bare board in open air:

- **606/606 photos**, interval mean 1,000 ms, max 1,154 ms; run `finished`.
- **~140 ms of work per photo** (JPEG encode ~99 ms, card write ~33 ms) - against 600-690 ms on the XIAO/OV5640.
- **Processor 39.7 -> 40.8 C, flat after 4 minutes; camera sensor 28 -> 37 C**, levelling off; never throttled; CPU load ~0. The OV5640 melted a rubber band.
- Photos 284-306 KB; autofocus held focused (`AfState 2`) throughout.
- The ESP32 project's `tools/audit_card.py`, run on Windows against the Pi's data, reports CLEAN. (Run it on Windows: it converts paths with backslashes, so on Linux it cannot find the dashboard chunks.)

Full 12 MP (4608x2592) is available (`"frame_size": "12MP"` in `config.json`): ~400 ms encode, ~950 KB per photo.

### Card layout and getting photos off

```
boot (512 MB, FAT32, read-only)  |  system (4 GB, ext4, read-only overlay)  |  INSECT-AI (rest of the card, FAT32, writable)
```

Owner decisions (14-15 October 2026): plugging the Pi into a computer makes it show up as a drive named **INSECT-AI** holding the dashboard and photos - the same files and drive name as a XIAO card, opened the same way, with no card to remove; and the system must survive the plug being pulled.

- **The photo partition is the drive.** `pi/insectcam-drive` mounts it at `/srv/insectcam` for capture, or unmounts it and hands the raw partition to a computer over USB (Linux `g_mass_storage`). **Never both at once**: two writers on one FAT filesystem corrupt it. It refuses transfer mode while the capture service runs and runs `fsck.vfat` before every mount.
- **Read-only system.** `sudo sh pi/install.sh --read-only` turns on Raspberry Pi's overlay file system (`raspi-config nonint enable_overlayfs` and `enable_bootro`): the system partition is mounted read-only underneath a RAM overlay (208 MB) whose changes vanish at power-off, and `/boot/firmware` is read-only. Only INSECT-AI is ever written, and the capture service writes every file atomically (temporary file, fsync, rename).
- **Automatic mode at power-up** (`pi/insectcam-boot`): it presents the drive and waits 12 s for a computer to configure it. A computer on the data port: the Pi stays a drive and does not capture. Otherwise (power bank, PWR socket): it mounts the photos and starts the camera service. An `insectcam-dev` file on the boot partition (or at the top of INSECT-AI) skips this and keeps the USB network link for SSH.
- **To change the software on a read-only Pi:** `sudo raspi-config nonint disable_overlayfs; sudo raspi-config nonint disable_bootro; sudo reboot`, run `install.sh`, then `install.sh --read-only` and reboot.

Verified 15 October 2026 on a fresh card: layout built by `install.sh` (boot 512 MB / system 4 GB / INSECT-AI 3 GB on an 8 GB card); capture starts by itself at power-up; with the overlay on, the real system partition is mounted `ro`, `/boot/firmware` is `ro`, writes land in tmpfs and INSECT-AI is writable; a clean reboot mid-capture marks the run `finished`; an immediate reboot with no sync (`echo b > /proc/sysrq-trigger`, equivalent to pulling the plug as far as the software is concerned) mid-capture kept all 62 photos of that run, left no `.tmp` files, passed `fsck.vfat`, marked the run `interrupted_power_removed` and started a new one; `audit_card.py` on Windows over the USB drive reported CLEAN for 3,959 photos across 6 runs. (That check counted photos; a later one that opens them found a bug, fixed 15 October: each photo is now fsynced again after the rename. A literal cable pull has not yet been tested on the read-only build: the one attempt shut down gracefully.)

### The drive looks tidy

Only `dashboard.html` and `images` are visible at the top of INSECT-AI; the dashboard's support files, `data`, `raw` and `system` carry the FAT hidden attribute (`insectcam.capture.Storage.tidy_root`, run at every mount, before the drive is handed to a computer, and at each session start; the attribute survives atomic rewrites). The same tidy deletes `FSCK####.REC` files: `fsck.vfat -a` salvages photos cut off mid-save into them after every unclean stop, and 33 (9.7 MB) had piled up during power-cut testing. Nothing is moved, so the dashboard loads its files by the same paths as on a XIAO card.

Verified 15 October 2026: dashboard opened from the Pi's drive and checked by the owner - works, including after hiding; on the read-only Pi, tidy removed a planted fragment, hid a stray file, and a rewritten `manifest.js` stayed hidden.

### Motion mode

`insectcam/motion.py` is the XIAO firmware's motion score on the Pi's own frames: grayscale difference between consecutive checks, minus the whole-frame brightness change, scored as the strongest tile of an 8 x 6 grid (mean absolute difference per pixel), threshold 5 (fixed). The first check is the baseline (kept, score -1); later checks are kept when the score is at least 5, otherwise they are recorded as `motion_not_detected` rows with no photo. The same row format, `motion_trigger` save policy and dashboard fields as the XIAO; the phone app's "Save pictures only when something moves" switch and its motion meter work. The Pi uses the camera's 640x360 luma stream block-averaged to 160x90, so nothing is re-initialised between checks and autofocus, exposure and white balance never reset (the XIAO re-initialises its sensor for every check, which is why motion mode switches autofocus off there). A check costs ~7 ms; the ~100 ms JPEG encode only happens for a kept frame. 11 unit tests: `tests/test_motion.py`.

Verified 15 October 2026 (test copy run from RAM on the read-only Pi, motion switched on through the phone app's settings call): 68 checks over 68 s gave 18 saved photos - the baseline plus the 17 checks while the owner waved a hand in front of the camera - and 50 `motion_not_detected` rows. Still-scene scores 0.3-0.5 (maximum 4.0, just after the wave, probably autofocus re-settling - a thin margin to watch in long runs); wave scores 6.8-114.

### Running the capture service by hand

On a read-write Pi: `cd /opt/insectcam && python3 -m insectcam.service --data-root /srv/insectcam --http-port 8080` (`--once` runs a single session). Stop the systemd service first (`sudo systemctl stop insectcam`) if it is running.

Needs `python3-picamera2` (the Lite image does not include it; `install.sh` installs it). For internet on the Pi during development, Windows Internet Connection Sharing from Wi-Fi to the Pi's USB adapter works and the Pi switches to it automatically.

### Ant detection and live view (experimental)

Needs the detector installed (`pi/install.sh`, with a model staged in the gitignored `models/` folder; without one the controls say "no model installed"). The only model so far is a **placeholder** that finds dark specks, not ants, and everything it produces is labelled as such. **Live view** (button beside Take a peek) shows annotated frames, about 2 per second, only after the detector has run. **Ant detection** (settings) records predictions for each saved photo in `raw/detections.csv`; it is off by default and never changes which photos are kept. Details and measurements: `docs/edge-model-test.md`.

### Phone hotspot

`InsectCam-<last 4 hex digits of the Pi's serial>` / `antcamera`, the same scheme as the XIAO cameras. WPA2 only on channel 6: NetworkManager's default adds WPA3, and a Pixel 8 then joined and dropped within about 3 s. Address-assignment and name resolution are NetworkManager's shared mode plus a catch-all DNS entry, so phones are sent straight to the control app. `insectcam/control_app.html` is extracted from the ESP32 firmware (`tools/extract_control_app.py`), so both cameras serve the same page and translations.

## Preparing a card without the Imager GUI

`tools/flash_card.py` writes the pinned Raspberry Pi OS Lite (64-bit, Trixie) image and configures it, so many cards can be prepared identically:

```
py tools\flash_card.py --list
py tools\flash_card.py --disk 1 --hostname insectcam
```

It downloads and checksum-verifies the image once (cached in `%LOCALAPPDATA%\insectcam\images`), writes it with Raspberry Pi Imager's command-line mode (Windows administrator prompts: one to write, one to give the boot partition a drive letter afterwards; Imager re-reads the card to verify), then writes cloud-init `user-data` and `network-config` onto the card's boot partition:

- hostname (`<hostname>.local` on the USB link);
- user `pi`, **SSH key only**, no password (the key is this PC's `~/.ssh/id_ed25519.pub` or `id_rsa.pub`);
- SSH enabled;
- Raspberry Pi's official USB gadget mode (`rpi: enable_usb_gadget: true`, package [`rpi-usb-gadget`](https://github.com/raspberrypi/rpi-usb-gadget), Apache-2.0, preinstalled in the image).

No Wi-Fi password goes on the card unless `--wifi-ssid` is given (password from the `INSECTCAM_WIFI_PASSWORD` environment variable). This keeps the Pi's own Wi-Fi free for the children's phone hotspot later.

Things learned flashing a second card: Imager exits after a second with code 1 and no message if Windows has given the card's Linux partition a drive letter (a card from an earlier flash), so the tool releases the card's drive letters first; Imager ejects the card when it finishes, so the card must be taken out and put back before its boot partition is visible again; and the tool removes `resize` from the kernel command line, because the image otherwise expands the system partition over the whole card on first boot, leaving no room for the photo partition.

Formats follow Raspberry Pi's [Cloud-init on Raspberry Pi OS](https://www.raspberrypi.com/news/cloud-init-on-raspberry-pi-os/) and the `rpi-usb-gadget` README. The installed Imager (1.8) has no cloud-init options on its command line, which is why the tool writes those files itself after the image.

## Connecting over USB

1. **Once per Windows PC:** install Raspberry Pi's USB gadget driver, `rpi-usb-gadget-driver-setup.exe` from the [rpi-usb-gadget releases](https://github.com/raspberrypi/rpi-usb-gadget/releases) (v1.0.6). Windows has no built-in driver for this device. Needs administrator rights.
2. Plug the cable into the Pi's micro-USB port **next to the mini-HDMI** (labelled USB), not the one labelled PWR. That one cable powers the Pi and carries the network.
3. Wait a few minutes on first boot (cloud-init applies the settings, then the USB network starts).
4. `ssh pi@insectcam.local`

The Pi hands this PC an address on its own small network (`10.12.194.0/28`, Pi at `10.12.194.1`). For internet on the Pi (installing packages), turn on Windows Internet Connection Sharing from the Wi-Fi adapter to the Raspberry Pi USB adapter; the Pi notices and switches to using it.
