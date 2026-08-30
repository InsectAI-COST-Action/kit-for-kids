# Edge ant model spike

Feasibility spike for [ADR 0002](../../docs/adr/0002-on-device-ant-edge-model.md): can this project's firmware build ESP-DL (Espressif's on-device deep-learning library) alongside the existing Arduino-framework capture pipeline, to run a collaborator's ESPDet-Pico ant model (`AntTestModel.espdl`, `models/ESPDet-Pico/` in the upstream `kit-for-kids` monorepo) on-device?

## Status, 30 August 2026: blocked on a machine-specific policy, not a technical dead end

Step 1 (does `framework = arduino, espidf` even build for this board, before adding ESP-DL) hit two issues, in order:

**1. ESP-IDF's CMake/ninja build tooling does not tolerate spaces in the project path.** This project's real path (`G:\My Drive\InsectAI - Core Group\WG 2\...`) has several. The pure-`arduino`-framework main firmware has never hit this because its SCons-based build doesn't need external CMake at all - this is specific to the ESP-IDF side of a mixed build. **Fixed** by mirroring the spike to a clean path, `C:\k4k\edge-ant-model-spike\` (same reasoning as the existing subtree publishing clone at `C:\k4k\kit-for-kids`).

**2. From the clean path, PlatformIO successfully resolved and downloaded the full ESP-IDF toolchain** (tool-idf, tool-cmake, tool-ninja, toolchain-xtensa-esp32s3, etc.) - real, positive evidence that this project's exact platform/board (`espressif32 @ 7.0.1`, `seeed_xiao_esp32s3`) supports the mixed `arduino, espidf` framework combination in principle. It then failed invoking `tool-cmake`'s `cmake.exe` (`C:\Users\tomaug\.platformio\packages\tool-cmake\bin\cmake.exe`) with `OSError: [WinError 4551] Your organization used Device Guard to block this app.` This is the **same class of restriction** already documented in `docs/next-session.md`'s PlatformIO toolchain note (which blocks the `pio.exe`/`platformio.exe` launcher stubs) - but a *different* binary, newly encountered because the pure-Arduino build never needed a standalone CMake before. `py -m platformio` (the existing workaround for the launcher-stub case) does not help here; the block is on `cmake.exe` itself, not on how PlatformIO is invoked.

**This means the ESP-DL/Arduino integration question itself remains open** - genuinely promising so far (no architecture incompatibility found; the toolchain resolves and downloads cleanly), but unproven, because the build cannot get past this machine's security policy to actually compile anything yet.

## Options, not yet acted on

1. **Request an IT/Device Guard exception** for `C:\Users\tomaug\.platformio\packages\tool-cmake\bin\cmake.exe` specifically (and likely other binaries under `tool-idf`/`tool-ninja`/the toolchain packages, once this one is past) - the same category of request that presumably already exists for the signed `py` launcher.
2. **WSL2 with a Linux distro.** Device Guard is a Windows-native code-signing/execution policy; it would not apply inside a Linux subsystem. Checked 30 August 2026: `wsl.exe` is present but no distro appears installed - this is a real setup task (likely needs admin rights to enable), not a quick win, but would probably sidestep this entire class of restriction for good, not just this one binary.
3. **Build on a different, unrestricted machine and transfer the compiled firmware.** The colleague who built `AntTestModel.espdl`/`AntTestModel.bin` has *already* solved an ESP-DL toolchain setup, on some machine. Flashing the resulting `firmware.bin` here only needs `esptool.py`, already proven working all day over the dev bridge/direct upload - no CMake involved at all on this machine for that step.

## Files

- `platformio.ini` / `src/main.cpp` - the minimal step-1 test (mixed framework, no ESP-DL yet). Kept as the starting point for whichever option above unblocks the build.
- Not committed: the mirrored clean-path copy at `C:\k4k\edge-ant-model-spike\` (outside this repo, local-only) and the model weight itself (`AntTestModel.espdl`, fetched from the upstream `kit-for-kids` clone when needed - not tracked in this repo, matching the existing FlatBug asset convention).
