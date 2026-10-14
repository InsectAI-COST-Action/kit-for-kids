# Pi Zero 2 W insect camera (exploratory)

Branch `Pi-zero-cam3`, started 14 October 2026. An alternative to the XIAO ESP32S3 Sense camera in [`../TomA-insect-ESP32-software`](../TomA-insect-ESP32-software): a Raspberry Pi Zero 2 W with a Raspberry Pi Camera Module 3.

**Why:** the OV5640 on the XIAO Sense board overheats (it melted a rubber band through its heatsink, even at a 5 s capture interval). The XIAO Sense board supplies the OV5640 core from a 1.3 V regulator, below the sensor's 1.425-1.575 V range, so the sensor falls back on its internal regulator, which OmniVision's datasheet warns causes "a potential heat issue". That is a hardware problem, not fixable in firmware. See `../TomA-insect-ESP32-software/docs/hardware-validation.md` on branch `wip/camera-ov5640`.

**Status:** setting up. The plan is: (1) connect to the board, (2) confirm the camera works, (3) port the ESP32 camera's behaviour (1 FPS capture to card, run manifests, phone control app with peek, offline dashboard) to the Pi.

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
