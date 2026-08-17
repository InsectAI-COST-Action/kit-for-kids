# Next session checklist

Status at hand-off (17 August 2026): image-quality trials are concluded. The settled pilot setting is QXGA (2048?1536), JPEG quality 12, 1 FPS, with a maximum 3,600-second session. The firmware and `config.example.json` enforce this normal `pilot` setting; the mounted deployment card must be prepared with `py tools\configure_camera_trial.py <card-root> --install-pilot-default`. Earlier trial captures are retained as evidence and must not be deleted automatically.

## First: one-hour QXGA pilot acceptance

1. Confirm the card uses the pilot default, safely eject it, and collect for just over one hour. Disconnect power only after the session has completed normally.
2. Mount the card and run `py tools\audit_card.py <card-root>` and `py tools\camera_trial_report.py <card-root>`. Require 3,600 completed 2048?1536 JPEGs, matching raw/dashboard/image counts, no uncontrolled reboot/storage error, and a documented power-removal recovery result.
3. Record card capacity/free space, USB battery pack/cable, enclosure state, temperature observations, browser/OS, and firmware commit/build with the result in [hardware-validation.md](hardware-validation.md).
4. Review representative source images in the dashboard for focus, lighting, exposure, colour, and small-insect detail.

## Then: browser-model evidence

5. In Chrome and Edge, open the deployed `dashboard.html`, select **Find insects with AI**, choose the top camera-card folder once, and verify live scanning, pause/continue, stop, current image, and possible-insect cards on actual QXGA images. Record browser version, model-load time, first-result time, and errors.
6. Benchmark at least 100 representative enclosure frames in the browser. Record median/p95 image time, total time, memory symptoms, cancellation behaviour, false positives, and misses. Extrapolate honestly to a 3,600-image session; do not skip frames silently.
7. Keep the ESP32 capture loop model-free. Continue the short intended-battery-pack stability/temperature/clean-power-removal smoke test.

## Model and distribution gates

8. Record the official FlatBug Nano weight provenance and redistribution position. Do not add weights to Git or make species/identification claims.
9. Compare the browser single-pass 640?640 output against the reference FlatBug pipeline on a labelled enclosure set. Decide later whether limited tiling, a bespoke detector, or a research-only workflow is appropriate.
10. Treat Firefox, Safari, result export/persistence, and broad cross-browser accessibility as open work; current working evidence is Chrome and Edge only.

Before the next commit, run `py tests\check_project.py`, `git diff --check`, the relevant SD audit, and a clean PlatformIO build when firmware changes.
