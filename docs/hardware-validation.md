# Hardware validation record

Complete this record before field use.

| Check | Required evidence | Result |
| --- | --- | --- |
| Board | ESP32-S3R8 XIAO ESP32S3 Sense | Pending |
| Camera | OV3660 PID reported at boot | Pending |
| PSRAM | `psramFound()` succeeds | Pending |
| SD | FAT32 card mounts and survives 7,200 writes | Pending |
| Capture | VGA/JPEG-quality-12 frame every 500 ms | Pending |
| Battery | One-hour capture/store profile, voltage and temperature recorded | Pending |
| Recovery | Power interruption preserves prior CSV/chunks | Pending |
| Dashboard | Opens offline in Chrome, Edge, Firefox, Safari | Pending |

The detailed component specification is in `camera-spec.txt`.
