# Hardware validation record

Update this record as evidence is collected. The full one-hour and endurance tests remain outstanding.

| Check | Required evidence | Result |
| --- | --- | --- |
| Board | ESP32-S3R8 XIAO ESP32S3 Sense; clean PlatformIO build and upload | Verified on physical board (COM4) |
| Camera | OV3660 PID reported at boot | Verified at boot |
| PSRAM | `psramFound()` succeeds | Verified at boot |
| SD | FAT32 card mounts and survives 7,200 writes | Mount and sustained capture verified; 7,200-write endurance pending |
| Capture | VGA/JPEG-quality-12 frame every 500 ms | Short physical captures verified; one-hour profile pending |
| Battery | One-hour capture/store profile, voltage and temperature recorded | Pending |
| Recovery | Power interruption preserves prior CSV/chunks and marks the run interrupted | Verified with battery disconnect and subsequent reboot |
| Dashboard | Opens offline in Chrome, Edge, Firefox, Safari; images and full chunk index load | Verified locally in the SD-card dashboard; full browser matrix pending |

The detailed component specification is in `camera-spec.txt`. The next validation actions are listed in `docs/next-session.md`.
