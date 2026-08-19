# Next session checklist

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

## Motion-triggered capture: physical acceptance required

The implementation is complete in firmware and the Camera settings dashboard. The default is still retain-every-image. When **Save pictures only when something moves** is enabled, the board waits five seconds, retains the first configured-quality image, then assesses 160 x 120 grayscale previews. A local 8 x 6 tile score of 5 or more retains the next full image; quieter checks are logged as `motion_not_detected` without a JPEG.

1. On a disposable test card, collect at least five minutes in retain-all mode and motion mode at the same interval. Confirm the five-second warm-up, a saved baseline first image, valid manifests/configuration, and that motion mode records every check but saves fewer images.
2. Deliberately introduce an ant/object movement and a whole-scene brightness change. Inspect false saves/misses and compare the recorded `motion_score` distribution with the offline spike before changing the fixed threshold.
3. Confirm repeated JPEG/grayscale sensor switching does not cause camera faults, frame-buffer leaks, cadence backlogs, corrupt images, or SD recovery failures.
4. Record the result in [hardware-validation.md](hardware-validation.md). Do not present motion mode as a validated data-reduction method until this passes.

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
