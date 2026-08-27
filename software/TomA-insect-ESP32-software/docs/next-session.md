# Next session checklist

## Remote/unattended working arrangement (27 August 2026)

The owner is away for a while, with the board left powered over USB and the SD card inside it (not in a reader). A serial development bridge (`include/dev_bridge.h`, `src/dev_bridge.cpp`, `tools/dev_bridge_client.py`) was built and verified live for exactly this: inspecting and changing the card without physical access. Full protocol, safety model, and the two real bugs found while building it (a silent reboot-on-connect, and silently dropped bytes on bulk writes) are in [dev-bridge.md](dev-bridge.md) - read that before using it.

In short: `py tools\dev_bridge_client.py --port COM4 stop` before any file command, `mount` to remount afterward, `reboot` to apply a config change or start a fresh run. File commands are refused outright while a session is capturing, so there is no way to race a write by mistake.

Remember commits made in this repo are **not** automatically visible on GitHub — see [CLAUDE.md](../CLAUDE.md) for the subtree publish step, which needs to be run separately from `C:\k4k\kit-for-kids`.

Status at hand-off (18 August 2026): image-quality trials are concluded. The settled pilot setting is QXGA (2048?1536), JPEG quality 12, 1 FPS, with a maximum 3,600-second session. The firmware and `config.example.json` enforce this normal `pilot` setting; the mounted deployment card must be prepared with `py tools\configure_camera_trial.py <card-root> --install-pilot-default`. Earlier trial captures are retained as evidence and must not be deleted automatically.

## First: one-hour QXGA pilot acceptance

1. Confirm the card uses the pilot default, safely eject it, and collect for just over one hour. Disconnect power only after the session has completed normally.
2. Mount the card and run `py tools\audit_card.py <card-root>` and `py tools\camera_trial_report.py <card-root>`. Require 3,600 completed 2048?1536 JPEGs, matching raw/dashboard/image counts, no uncontrolled reboot/storage error, and a documented power-removal recovery result.
3. Record card capacity/free space, USB battery pack/cable, enclosure state, temperature observations, browser/OS, and firmware commit/build with the result in [hardware-validation.md](hardware-validation.md).
4. Review representative source images in the dashboard for focus, lighting, exposure, colour, and small-insect detail.

## Then: browser-model evidence

5. In Chrome and Edge, open the deployed `dashboard.html`, choose the top card folder once, and verify each of the three analysis choices on actual QXGA imagery: **AntAI - Beta**, **FlatBug - Quick look**, and **FlatBug - Look closely**. For cards with multiple runs, confirm that selecting a session changes the picture count and that analysis never includes another session.
6. Treat all current predictions as experimental. In particular, re-check FlatBug after the repaired segmentation decoder: its confidence must remain 0?100%, and empty images must no longer produce coefficient-driven false positives. Record browser version, model-load time, first-result time, false positives, misses, and errors.
7. Benchmark at least 100 representative enclosure frames per candidate/mode. Record median/p95 image time, total time, memory symptoms, cancellation behaviour, and results stratified by empty images, ants, other insects, blur, reflections, and people. Extrapolate honestly to a 3,600-image session; do not skip frames silently.
8. AntAI - Beta is an initial baseline trained on 34/10/5 images (fit/validation/held-out test), with a five-image test mAP50 of 0.632. Expand and diversify annotations before making comparative accuracy decisions or adding tracking. The model cannot run on the XIAO ESP32-S3 as-is: its 10 MB ONNX file exceeds the 8 MB flash and its 1024px float input alone exceeds 8 MB PSRAM. Keep device capture model-free.
9. Continue the short intended-battery-pack stability/temperature/clean-power-removal smoke test.

## Model and distribution gates

8. Record the official FlatBug Nano weight provenance and redistribution position. Do not add weights to Git or make species/identification claims.
9. Compare the browser single-pass 640?640 output against the reference FlatBug pipeline on a labelled enclosure set. Decide later whether limited tiling, a bespoke detector, or a research-only workflow is appropriate.
10. Treat Firefox, Safari, result export/persistence, and broad cross-browser accessibility as open work; current working evidence is Chrome and Edge only.

Before the next commit, run `py tests\check_project.py`, `git diff --check`, the relevant SD audit, and a clean PlatformIO build when firmware changes.

## Toolchain note: invoking PlatformIO on this Windows machine

Windows Device Guard blocks the `pio.exe`/`platformio.exe` launcher stubs directly (`ApplicationFailedException: Your organization used Device Guard to block this app`), whichever Python installed them. Always invoke PlatformIO as a Python module through the signed `py` launcher instead:

```powershell
py -m platformio run
py -m platformio run -e xiao_esp32s3 -t upload --upload-port COM4
```

This already matches the command form used in [performance-experiment.md](performance-experiment.md); the gotcha is that plain `pio ...` or `platformio ...` will fail on this machine even though `py -m platformio --version` and `py -m platformio run` work normally. `py --version` (Python 3.13) already has PlatformIO Core installed, so no extra setup is required.

If `py -m platformio` is ever unavailable in a fresh environment, the PlatformIO VS Code extension's bundled portable Python can bootstrap a working copy without admin rights: extract `<extension-dir>\assets\predownloaded\python-portable-*.tar.gz` to `%USERPROFILE%\.platformio\python3`, run that `python.exe -m ensurepip`, then `python.exe -m venv %USERPROFILE%\.platformio\penv`. The resulting `penv\Scripts\python.exe -m platformio` works the same way (module invocation, not the `.exe` stub, which is blocked the same way).

## Motion-triggered capture: physical acceptance required

The implementation is complete in firmware and the Camera settings dashboard. The default is still retain-every-image. When **Save pictures only when something moves** is enabled, the board waits five seconds, retains the first configured-quality image, then assesses 160 x 120 grayscale previews. A local 8 x 6 tile score of 5 or more retains the next full image; quieter checks are logged as `motion_not_detected` without a JPEG.

1. On a disposable test card, collect at least five minutes in retain-all mode and motion mode at the same interval. Confirm the five-second warm-up, a saved baseline first image, valid manifests/configuration, and that motion mode records every check but saves fewer images.
2. Deliberately introduce an ant/object movement and a whole-scene brightness change. Inspect false saves/misses and compare the recorded `motion_score` distribution with the offline spike before changing the fixed threshold.
3. Confirm repeated JPEG/grayscale sensor switching does not cause camera faults, frame-buffer leaks, cadence backlogs, corrupt images, or SD recovery failures.
4. Record the result in [hardware-validation.md](hardware-validation.md). Do not present motion mode as a validated data-reduction method until this passes.

## SD write performance (in progress, 27 August 2026)

The SD SPI clock now steps 25 → 20 → 10 → 4 MHz and keeps the first that mounts; the card in use accepts 25 MHz. Image write time roughly halved (758–777 ms → 382–405 ms). Full measurements and reasoning in [performance-experiment.md](performance-experiment.md).

**Resume here:**

1. `kPerformanceSampleInterval` (100, `src/main.cpp`) collides with `DashboardWriter::kChunkSize` (100), so every performance sample lands on a chunk promotion and reports worst-case timings. Change to a prime such as 97 and re-measure before trusting any steady-state figure.
2. Then reduce the write path. Metadata now costs more per frame than the JPEG: chunk promotion does four file operations at once; each frame opens, flushes and closes three separate files; and the atomic write does `remove` → `open` → `write` → `flush` → `close` → `rename`.
3. exFAT was suggested by a collaborator for write throughput. The reasoning is sound but it is unavailable in our toolchain (`FF_FS_EXFAT 0` in the shipped ESP-IDF), and adopting it means rebuilding ESP-IDF or replacing `SD.h` with SdFat. Revisit only if metadata still dominates after step 2.

Note `total_ms` sits at 983–1030 ms against the 1,000 ms budget at 1 FPS, so cadence headroom is currently thin on promotion frames.

## Device control app over Wi-Fi (new track, 21 August 2026)

A device-hosted control app has been accepted for prototyping in [ADR 0001](adr/0001-device-hosted-control-app.md), with a phased plan and acceptance gates in [device-control-app-plan.md](device-control-app-plan.md). It is scoped to the control plane only — status, safe stop, configuration, and single-frame preview. The SD-card dashboard remains the data plane and stays fully offline and independent.

Its first purpose is to retire the card-corruption failure recorded in [hardware-validation.md](hardware-validation.md) by giving the operator a way to invoke the existing `finishSession()` path and unmount the card before power is removed. Phase 2 of that plan is where the risk is actually retired; later phases are convenience.

**Status (22 August 2026):** Phases 1–4 are built and confirmed working live on hardware — `include/control_server.h` / `src/control_server.cpp`. That covers the status page, safe stop, peek + live motion meter, and camera settings (read/write, plus a "Restart now" flow that applies a saved setting without a physical power cycle). Phase 5's firmware half is done too: fixed shared credentials (`InsectCam` / `antcamera`), a captive-portal redirect confirmed working on Android, and a generated QR code. Phases 1 and 2 have not completed their full acceptance-cycle counts (see the plan doc).

**Blocked on hardware availability: iPhone/Safari testing of the control app.** The owner has no iPhone. iOS handles captive portals differently from Android (auto-opening a restricted mini-browser rather than posting a notification), and that mini-browser has known limitations around JavaScript and page lifecycle. **Treat the control app's browser support as Android-only until someone tests it on iOS** — do not infer iOS support from the working Android result. Needs borrowed hardware or an external tester.

**Blocking finding, not yet resolved:** Wi-Fi (SoftAP) running at the same time as motion-triggered capture breaks motion detection — confirmed via a same-scene controlled test, 100% false-trigger rate with Wi-Fi on vs. normal discrimination with it off. Full detail in [device-control-app-plan.md](device-control-app-plan.md) Phase 1 and [hardware-validation.md](hardware-validation.md). A daytime repeat of the same control test is planned next, then a decision between three mitigation directions (electrical isolation, retuning motion tolerance, or not running Wi-Fi and motion capture concurrently). Retain-every-frame capture is unaffected.

**This track runs alongside pilot acceptance, not instead of it.** The one-hour QXGA endurance run, the browser matrix, and the battery smoke test remain the critical path to a working pilot and should stay ahead of this work.

Note that this supersedes the earlier parked "plug the board into a phone as SD storage" direction below for the near term: the control app addresses the same low-touch goal with far less risk, and USB-MSC remains unstarted.

## New next-session feasibility tracks

### 1. Direct-write camera configuration

The first **Camera settings** implementation is complete: it requests an explicit writable camera-card folder handle in Chrome/Edge, offers only validated values, confirms before replacing `config.json`, and the firmware remains the final validator. A download/manual-copy workflow is not the intended product route.

1. First prove that the dashboard can obtain a user-approved writable handle to the mounted card folder, validate a generated `config.json`, and write it back only after an explicit confirmation.
2. The first implementation now offers only firmware-validated choices: 1/2/30/60-second capture intervals; high-quality QXGA or low-quality VGA images; and 1/5/30/60-minute or infinite sessions. Its default remains the settled pilot setting: QXGA (2048x1536), JPEG quality 12, one image each second, maximum 3,600 seconds. Do not expose arbitrary values outside these combinations.
3. Show the recorded/effective configuration and explain that a changed configuration applies after the board is restarted. The firmware remains the final validator, and the next session manifest must record effective settings.
4. Define and test the browser/phone matrix before implementation is accepted. Direct write access from a local dashboard is a hard feasibility gate: desktop Chrome/Edge evidence does not prove that a phone browser can safely grant the required folder write permission.
5. Add static/schema tests, write/read round-trip tests, and physical reboot tests for every offered preset.

If the required mobile browser cannot support a safe direct-write flow, stop and return for an architecture decision; do not silently downgrade the product to manual file copying.

### 2. Plug board directly into phone as SD storage

The intended next-generation workflow is low-touch: plug the powered-off camera board into a phone, let the board expose its physical SD card as USB storage, open the dashboard, approve access/write once, then choose safe configuration or analysis actions. The external-card-reader route is not a product direction.

1. **ESP32-S3 board-as-storage feasibility spike:** implement or prototype native USB Mass Storage Class (MSC) presenting the physical SD card to the phone. The board must enter an explicit USB-storage mode: stop capture, flush and unmount the card, then expose it. On disconnect it must remount, reconcile, and record an intentional hand-off/recovery event. Never allow capture and USB-host access to the filesystem at the same time.
2. **Integrated child journey:** minimise steps to connect the board, open the dashboard, approve storage access/write, choose a safe preset, and safely disconnect. Automatic browser launching on USB attachment may be investigated, but cannot be assumed until demonstrated on target phones.
3. **Acceptance testing:** test named Android/Chrome and iPhone/Safari devices; normal and interrupted disconnects; at least 50 USB hand-offs; phone power/brown-out behaviour; SD-card integrity; configuration survival after board reboot; and dashboard write/read round trips.

If direct browser writing or the USB-storage hand-off cannot pass on the required phone/browser combination, stop rather than reverting to a high-user-involvement workflow. Consider a native companion application or board-hosted configuration interface only through a later product decision.
