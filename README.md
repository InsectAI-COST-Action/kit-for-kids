# Insect camera logger

Firmware and an offline dashboard for the Seeed Studio XIAO ESP32S3 Sense with an OV3660 camera. The settled pilot captures and stores every QXGA (2048?1536), JPEG-quality-12 frame at 1 FPS for no more than one hour (3,600 images). Computer vision is deliberately a null adapter on the camera while an offline, browser-side inference path is evaluated.

## Development status

The firmware has been built and uploaded to the physical XIAO ESP32S3 Sense. Boot evidence confirms PSRAM, the OV3660 camera, SD configuration loading, and the null inference adapter. The SD-card recovery path has also been exercised: removing battery power marks the previous run as `interrupted_power_removed`, promotes the open dashboard chunk on the next boot, and keeps the current chunk visible to the offline dashboard.

Historical performance run `run_000012` is an important directory-sharding milestone. Its 2,384 smaller VGA captures used 24 bounded image directories, with all JPEGs and derived dashboard records present. Image-write times stayed effectively flat from 530 ms at frame 100 to 546 ms at frame 2,300; the earlier single-directory runs climbed above 1.7 seconds. It is retained as storage-design evidence, not as acceptance evidence for the settled QXGA/1-FPS pilot.

The dashboard is working as a local file on the SD card. It loads closed chunks plus the current open chunk, shows a compact ten-item preview with working expand/collapse controls, and opens images in an in-page modal. The child-facing shell adds a full-page loading dialogue, a friendly welcome/count, gallery-first exploration, and an experimental local AI journey: the top camera-card folder is selected once, supplying both local pictures and an installed FlatBug Nano package; pictures are then scanned one at a time with live provisional discoveries and pause/stop controls. This prototype has passed isolated Chrome/Edge model loading, but remains unvalidated and requires dashboard/batch testing. The runtime-generated `manifest.js` and `summary.js` are preserved when `py tools\prepare_sd.py` updates static dashboard files. Host-side contract checks pass.

The QXGA/quality-12/1-FPS setting was selected after controlled card trials: QXGA ran cleanly at 1 FPS, while its 2-FPS stress test delivered only 171 of 240 expected images because JPEG writing alone exceeds the 500 ms budget. See `docs/camera-quality-trial.md`.

The next development path has two strands: child-friendly dashboard/model work and a one-hour QXGA pilot acceptance run. Remaining device acceptance work is the full 3,600-image endurance run, cross-browser verification on Windows 10/11 and current macOS, and a final review of data integrity after repeated power removal. A formal battery-capacity test is deprioritised; a short stability and clean-power-removal smoke test with the intended USB battery pack remains appropriate. These are tracked in `docs/hardware-validation.md` and `docs/next-session.md`.

## Documentation

[Documentation guide](docs/README.md) is the entry point for operators, developers, browser-model work, and engineering evidence. The detailed [project brief](docs/project-brief.md) remains the implementation-scope contract; [next-session.md](docs/next-session.md) is the current development hand-off.

## Toolchain

Install PlatformIO Core, then run:

```powershell
pio run
py tests\check_project.py
```

The pinned target is `espressif32@7.0.1`, board ID `seeed_xiao_esp32s3`, Arduino framework. Before a device flash, copy `config.example.json` to the SD-card root as `config.json` and use `py tools\prepare_sd.py <card-root>` to install or update the static dashboard files. Existing runtime `manifest.js` and `summary.js` are intentionally left untouched. For a separate synthetic presentation, run `py tools\install_dashboard_demo.py <card-root>` and open `<card-root>\\demo\\demo.html`.

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
- `tools/install_ai_pack.py`: install the local, untracked Nano/WASM prototype package on a card.
- `tools/install_dashboard_demo.py`: install a separate synthetic presentation demo (not real capture data).
- `tools/configure_camera_trial.py`: install or restore a named, short OV3660 quality-trial configuration.
- `tools/camera_trial_report.py`: compare labelled trial-run image sizes, timing, and run state.
- `docs/camera-quality-trial.md`: controlled OV3660 resolution/JPEG/rate comparison.
- `docs/performance-experiment.md`: staged performance-instrumentation protocol.
- `docs/README.md`: documentation map and role-based starting points.
- `docs/`: operations, architecture, model work, and validation evidence.

## Model status

No production CV model has been chosen. `NullInferenceEngine` reports `model_unavailable` and writes no predictions. The current hypothesis is to leave capture on the ESP32 and analyse every retained image later in the local dashboard, protecting capture rate and keeping data offline. FlatBug is the preferred candidate to investigate, not an approved dependency. The browser spike and model gates are defined in `docs/browser-inference-plan.md` and `docs/model-card.md`.
