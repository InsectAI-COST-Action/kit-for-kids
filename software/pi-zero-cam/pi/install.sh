#!/bin/sh
# Install or update the insect camera on a Pi Zero 2 W prepared by
# tools/flash_card.py. Run on the Pi as root from a copy of this folder:
#
#   sudo sh pi/install.sh            (from software/pi-zero-cam)
#
# Idempotent: safe to re-run after changing the code. Needs internet the first
# time (packages). Leaves existing photos alone.
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
log() { echo "[install] $*"; }

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

# --- photo drive (a FAT32 image named INSECT-AI; see pi/insectcam-drive)
if [ ! -e /srv/insectcam-card.img ]; then
  free_mb=$(df -m --output=avail /srv | tail -n1)
  size_mb=$(( free_mb - 512 ))      # leave room for the system
  [ "$size_mb" -gt 1024 ] || { log "not enough space for a photo drive (${free_mb} MB free)"; exit 1; }
  /usr/local/sbin/insectcam-drive create "$size_mb"
fi
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
  ssid "$ssid" 802-11-wireless.mode ap 802-11-wireless.band bg \
  ipv4.method shared ipv4.addresses 192.168.4.1/24 ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk antcamera wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp wifi-sec.group ccmp >/dev/null
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
log "done"
