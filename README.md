# Insect camera logger

Firmware and an offline dashboard for the Seeed Studio XIAO ESP32S3 Sense with an OV3660 camera. The pilot captures and stores every frame at 2 FPS for no more than one hour. Computer vision is deliberately a null adapter until a production model is selected.

## Development status

The repository currently provides the project skeleton, camera/SD integration boundary, session logging, derived dashboard data format, a local-file dashboard, and host-side contract checks. Hardware flash and acceptance testing remain pending because PlatformIO and the physical board are not available in this workspace.

## Toolchain

Install PlatformIO Core, then run:

```powershell
pio run
py tests\check_project.py
```

The pinned target is `espressif32@7.0.1`, board ID `seeed_xiao_esp32s3`, Arduino framework. Before a device flash, copy `config.example.json` to the SD-card root as `config.json` and copy the `dashboard/` contents to the SD-card root.

## Operating flow

1. Insert a FAT32 microSD card containing the dashboard files and `config.json`.
2. Power the battery-operated camera; it captures for a maximum one hour.
3. Disconnect power before removing the SD card.
4. Insert the SD card into a computer and open `dashboard.html` in a supported browser.
5. Delete data manually with the computer's file manager when required.

Do not remove the SD card while the camera is powered. Previous committed records remain recoverable after an unexpected power loss; the final in-progress chunk may not appear in the dashboard until a later successful session finalises it.

## Project map

- `src/` and `include/`: firmware modules.
- `dashboard/`: self-contained HTML/CSS/JavaScript installed on the SD card.
- `dashboard/fixtures/`: synthetic local-file data for dashboard testing.
- `tests/check_project.py`: dependency-free contract/static test harness.
- `docs/`: architecture and hardware-validation evidence.

## Model status

No production CV model has been chosen. `NullInferenceEngine` reports `model_unavailable` and writes no predictions. It must be replaced only after a model card, licence, input/output contract, and 2-FPS benchmark have been approved.
