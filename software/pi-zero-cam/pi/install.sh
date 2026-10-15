#!/bin/sh
# Install or update the insect camera on a Pi Zero 2 W prepared by
# tools/flash_card.py. Run on the Pi as root from a copy of this folder:
#
#   sudo sh pi/install.sh               (from software/pi-zero-cam)
#   sudo sh pi/install.sh --read-only   same, then make the system read-only
#
# Idempotent: safe to re-run after changing the code. Needs internet the first
# time (packages). Leaves existing photos alone.
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
log() { echo "[install] $*"; }

READ_ONLY=no
[ "${1:-}" = "--read-only" ] && READ_ONLY=yes

# --- card layout: boot | system (ROOT_GIB, read-only capable) | INSECT-AI photos (rest of the card)
# tools/flash_card.py removes the image's "resize" boot option, so the system
# partition has not been grown to fill the card. Grow it to a fixed size and
# put a FAT32 photo partition after it. Online, with partx telling the kernel;
# only runs once (when no INSECT-AI partition exists yet).
DISK=/dev/mmcblk0
ROOT_GIB=4
if ! blkid -L INSECT-AI >/dev/null 2>&1; then
  total=$(cat /sys/class/block/mmcblk0/size)
  start2=$(cat /sys/class/block/mmcblk0p2/start)
  size2=$(cat /sys/class/block/mmcblk0p2/size)
  want=$(( ROOT_GIB * 1024 * 1024 * 1024 / 512 ))
  data_start=$(( start2 + want ))
  [ $(( total - data_start )) -gt $(( 2 * 1024 * 1024 * 1024 / 512 )) ] || { log "card too small for ${ROOT_GIB} GB system + 2 GB photos"; exit 1; }
  [ "$size2" -le "$want" ] || { log "system partition is already larger than ${ROOT_GIB} GB; re-flash with tools/flash_card.py"; exit 1; }
  log "growing the system partition to ${ROOT_GIB} GB and adding the photo partition"
  echo ",${want}" | sfdisk --no-reread --no-tell-kernel -N 2 "$DISK" >/dev/null
  partx -u "$DISK"
  resize2fs /dev/mmcblk0p2 >/dev/null 2>&1
  echo "start=${data_start}, type=0c" | sfdisk --no-reread --no-tell-kernel --append "$DISK" >/dev/null
  partx -a --nr 3 "$DISK"
  udevadm settle
  mkfs.vfat -F 32 -n INSECT-AI /dev/mmcblk0p3 >/dev/null
  udevadm settle
  log "photo partition ready: $(lsblk -no SIZE /dev/mmcblk0p3 | tr -d ' ') FAT32 INSECT-AI"
fi

# --- packages (python3-picamera2 is not in the Lite image)
if ! python3 -c "import picamera2, simplejpeg" 2>/dev/null || ! command -v mkfs.vfat >/dev/null; then
  log "installing packages"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends python3-picamera2 dosfstools
fi

# --- application
install -d -o pi -g pi /opt/insectcam/insectcam
install -m 644 -o pi -g pi "$HERE"/insectcam/*.py "$HERE"/insectcam/control_app.html /opt/insectcam/insectcam/
install -m 755 "$HERE"/pi/insectcam-drive /usr/local/sbin/insectcam-drive
install -m 755 "$HERE"/pi/insectcam-boot /usr/local/sbin/insectcam-boot
log "application installed in /opt/insectcam"

# --- photo drive
/usr/local/sbin/insectcam-drive mount
if [ -d "$HERE/card" ]; then
  # Dashboard files staged by prepare_card() (see README); never overwrites photos or config.
  cp -r --update=none "$HERE"/card/. /srv/insectcam/
  log "dashboard files copied onto the drive"
fi

# --- phone hotspot: InsectCam-XXXX / antcamera, the same scheme as the XIAO
# (XXXX = last 4 hex digits of the Pi's serial; one shared password by owner decision).
serial=$(awk '/^Serial/ {print $3}' /proc/cpuinfo)
suffix=$(echo "$serial" | tail -c 5 | tr 'a-f' 'A-F')
ssid="InsectCam-$suffix"
raspi-config nonint do_wifi_country GB          # Wi-Fi stays off until a country is set
nmcli -t -f NAME connection show | grep -qx insectcam-hotspot && nmcli connection delete insectcam-hotspot >/dev/null
nmcli connection add type wifi ifname wlan0 con-name insectcam-hotspot autoconnect yes \
  ssid "$ssid" 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  ipv4.method shared ipv4.addresses 192.168.4.1/24 ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk antcamera wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp wifi-sec.group ccmp wifi-sec.pmf disable >/dev/null
# WPA2 only, protected management frames off: NetworkManager otherwise adds
# WPA3 (SAE) alongside, and on 14 October 2026 a Pixel 8 joined and dropped
# off again within ~3 s until the network was WPA2-only.
# Captive portal, as on the XIAO: every name resolves to the camera, so a
# phone joining the network is sent straight to the control app.
install -d /etc/NetworkManager/dnsmasq-shared.d
echo "address=/#/192.168.4.1" > /etc/NetworkManager/dnsmasq-shared.d/insectcam-captive.conf
nmcli connection up insectcam-hotspot >/dev/null 2>&1 || log "hotspot will start at next boot"
echo "$ssid" > /etc/insectcam-ssid
log "hotspot $ssid (password antcamera) at 192.168.4.1"

# --- services
cat > /etc/systemd/system/insectcam.service <<'UNIT'
[Unit]
Description=Insect camera capture service and phone app
After=network.target

[Service]
User=pi
WorkingDirectory=/opt/insectcam
ExecStart=/usr/bin/python3 -m insectcam.service --data-root /srv/insectcam --http-port 80
AmbientCapabilities=CAP_NET_BIND_SERVICE
# SIGINT lets the session finish cleanly (run manifest "finished").
KillSignal=SIGINT
TimeoutStopSec=20
Restart=on-failure
RestartSec=3
UNIT
cat > /etc/systemd/system/insectcam-boot.service <<'UNIT'
[Unit]
Description=Insect camera: choose drive or capture mode at power-up
After=systemd-modules-load.service local-fs.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/insectcam-boot
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable insectcam-boot.service >/dev/null 2>&1
log "services installed (insectcam-boot enabled; it starts insectcam.service in capture mode)"
if [ "$READ_ONLY" = yes ]; then
  # Overlay file system: the system partition is never written (changes live in
  # RAM and vanish at power-off) and the boot partition is mounted read-only,
  # so pulling the plug cannot corrupt the system. Only INSECT-AI is written.
  raspi-config nonint enable_overlayfs
  raspi-config nonint enable_bootro
  log "read-only system enabled; takes effect at the next boot"
fi
log "done"
