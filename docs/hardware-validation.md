# Hardware validation record

Update this record as evidence is collected. SD endurance and final cadence validation remain outstanding. A formal one-hour battery-capacity profile is no longer required for this pilot because the expected one-hour load is comfortably within a standard USB battery pack; retain a short stability and clean-power-removal smoke test using the intended pack.

| Check | Required evidence | Result |
| --- | --- | --- |
| Board | ESP32-S3R8 XIAO ESP32S3 Sense; clean PlatformIO build and upload | Verified on physical board (COM4) |
| Camera | OV3660 PID reported at boot | Verified at boot |
| PSRAM | `psramFound()` succeeds | Verified at boot |
| SD | FAT32 card mounts and survives 3,600 QXGA writes | Mount and sustained capture verified. Historical run 000012 retained 2,384 smaller JPEGs in 24 bounded shards; completed QXGA run 000004 retained 120 images. One-hour 3,600-write endurance remains pending. |
| Capture | QXGA/JPEG-quality-12 frame every 1,000 ms | Completed QXGA run 000004 captured 120 images at a 1,000 ms median interval. QXGA/2-FPS was rejected (171/240 images; write time exceeded its budget). One-hour QXGA cadence acceptance remains pending. |
| Battery | Intended USB pack powers a representative capture run without reset, unsafe heating, or storage corruption; normal cable removal recovers cleanly | Short stability smoke test pending; formal capacity profiling deprioritised by owner |
| Recovery | Power interruption preserves prior CSV/chunks and marks the run interrupted | Verified with battery disconnect and subsequent reboot. Run 000012 awaits its next card-in-board boot to receive its normal `interrupted_power_removed` state. |
| Dashboard | Opens offline in Chrome, Edge, Firefox, Safari; images and full chunk index load | Verified locally in the SD-card dashboard; full browser matrix pending |

The detailed component specification is in `docs/camera-spec.md`. The next validation actions are listed in `docs/next-session.md`.
