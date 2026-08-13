# Hardware validation record

Update this record as evidence is collected. SD endurance and final cadence validation remain outstanding. A formal one-hour battery-capacity profile is no longer required for this pilot because the expected one-hour load is comfortably within a standard USB battery pack; retain a short stability and clean-power-removal smoke test using the intended pack.

| Check | Required evidence | Result |
| --- | --- | --- |
| Board | ESP32-S3R8 XIAO ESP32S3 Sense; clean PlatformIO build and upload | Verified on physical board (COM4) |
| Camera | OV3660 PID reported at boot | Verified at boot |
| PSRAM | `psramFound()` succeeds | Verified at boot |
| SD | FAT32 card mounts and survives 7,200 writes | Mount and sustained capture verified. Run 000012 retained 2,384 JPEGs in 24 bounded shards with flat image-write time; 7,200-write endurance pending. |
| Capture | VGA/JPEG-quality-12 frame every 500 ms | Camera capture verified. Run 000012 has stable storage behaviour, but absolute cadence acceptance is pending because its stage-duration telemetry conflicts with run-relative elapsed time. |
| Battery | Intended USB pack powers a representative capture run without reset, unsafe heating, or storage corruption; normal cable removal recovers cleanly | Short stability smoke test pending; formal capacity profiling deprioritised by owner |
| Recovery | Power interruption preserves prior CSV/chunks and marks the run interrupted | Verified with battery disconnect and subsequent reboot. Run 000012 awaits its next card-in-board boot to receive its normal `interrupted_power_removed` state. |
| Dashboard | Opens offline in Chrome, Edge, Firefox, Safari; images and full chunk index load | Verified locally in the SD-card dashboard; full browser matrix pending |

The detailed component specification is in `docs/camera-spec.md`. The next validation actions are listed in `docs/next-session.md`.
