# Third-party firmware asset

`ov5640_af_firmware.h` is the OV5640 autofocus microcontroller firmware (4,077 bytes) from Espressif's official camera driver, `espressif/esp32-camera` at commit `1d73d881b` ("New feature: Added OV5640 Auto-Focus", 13 February 2026), path `sensors/private_include/ov5640_af_firmware.h`. Obtained on 2026-10-01 and included unchanged (firmware payload SHA-256 `439245623bc99f3b0d8c44d47baed3cc17cad01b9191509c89bb8d92a98949c9`, pinned by `tests/check_project.py`). The repository is licensed under the Apache License 2.0; see `esp32-camera-LICENSE.txt`.

`CameraService::startAutofocus()` writes it to the sensor's internal MCU after each camera init. The control sequence there is ported from the same commit's `sensors/ov5640_af.c`, because the pinned framework's prebuilt camera driver predates that feature.

Source: https://github.com/espressif/esp32-camera
