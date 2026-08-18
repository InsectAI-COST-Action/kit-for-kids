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
