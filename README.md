# Insect camera logger

Firmware and an offline dashboard for the Seeed Studio XIAO ESP32S3 Sense with an OV3660 camera. The pilot captures and stores every frame at 2 FPS for no more than one hour. Computer vision is deliberately a null adapter on the camera while an offline, browser-side inference path is evaluated.

## Development status

The firmware has been built and uploaded to the physical XIAO ESP32S3 Sense. Boot evidence confirms PSRAM, the OV3660 camera, SD configuration loading, and the null inference adapter. The SD-card recovery path has also been exercised: removing battery power marks the previous run as `interrupted_power_removed`, promotes the open dashboard chunk on the next boot, and keeps the current chunk visible to the offline dashboard.

Performance run `run_000012` is an important storage milestone. Its 2,384 completed captures used 24 bounded image directories, with all 2,384 JPEGs and derived dashboard records present. Image-write times stayed effectively flat from 530 ms at frame 100 to 546 ms at frame 2,300; the earlier single-directory runs climbed above 1.7 seconds. The next development task is to validate the absolute timing telemetry: run-relative timestamps imply a much faster cadence than the individual stage-duration samples, so the instrument must be checked before claiming 2-FPS acceptance.

The dashboard is working as a local file on the SD card. It loads closed chunks plus the current open chunk, shows a compact ten-item preview with working expand/collapse controls, and opens images in an in-page modal. The runtime-generated `manifest.js` and `summary.js` are preserved when `py tools\prepare_sd.py` updates static dashboard files. Host-side contract checks pass.

The next development path has two strands: redesign the dashboard for young children, including a clear full-page loading state and guided actions, and prototype post-session insect detection entirely in the offline dashboard. FlatBug is the preferred first model candidate, but adoption is gated on model size, browser export, performance, licence compatibility, and representative-image validation. See `docs/browser-inference-plan.md`.

Remaining device acceptance work is timing-instrument validation, SD endurance testing, cross-browser verification on Windows 10/11 and current macOS, and a final review of data integrity after repeated power removal. A formal battery-capacity test is deprioritised; a short stability and clean-power-removal smoke test with the intended USB battery pack remains appropriate. These are tracked in `docs/hardware-validation.md` and `docs/next-session.md`.

## Toolchain

Install PlatformIO Core, then run:

```powershell
pio run
py tests\check_project.py
```

The pinned target is `espressif32@7.0.1`, board ID `seeed_xiao_esp32s3`, Arduino framework. Before a device flash, copy `config.example.json` to the SD-card root as `config.json` and use `py tools\prepare_sd.py <card-root>` to install or update the static dashboard files. Existing runtime `manifest.js` and `summary.js` are intentionally left untouched.

## Operating flow

1. Insert a FAT32 microSD card containing the dashboard files and `config.json`.
2. Power the battery-operated camera; it captures for a maximum one hour.
3. Disconnect power before removing the SD card. This is the normal stop method.
4. Insert the SD card into a computer and open `dashboard.html` in a supported browser.
5. Delete data manually with the computer's file manager when starting a new experiment.

Do not remove the SD card while the camera is powered. Previous committed records remain recoverable after an unexpected power loss; the device promotes the prior open chunk on the next boot.

## Project map

- `src/` and `include/`: firmware modules.
- `dashboard/`: self-contained HTML/CSS/JavaScript installed on the SD card.
- `dashboard/fixtures/`: synthetic local-file data for dashboard testing.
- `tests/check_project.py`: dependency-free contract/static test harness.
- `tools/audit_card.py`: read-only SD-card integrity audit.
- `docs/performance-experiment.md`: staged performance-instrumentation protocol.
- `docs/browser-inference-plan.md`: child-first dashboard direction and gated local-model experiment.
- `docs/`: architecture, operations, and hardware-validation evidence.

## Model status

No production CV model has been chosen. `NullInferenceEngine` reports `model_unavailable` and writes no predictions. The current hypothesis is to leave capture on the ESP32 and analyse every retained image later in the local dashboard, protecting capture rate and keeping data offline. FlatBug is the preferred candidate to investigate, not an approved dependency. The browser spike and model gates are defined in `docs/browser-inference-plan.md` and `docs/model-card.md`.
