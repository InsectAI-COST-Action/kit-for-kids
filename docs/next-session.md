# Next session checklist

Status at hand-off (15 August 2026): the physical SD card has been reset to a clean deployment state. It retains the current dashboard, `config.json`, blank runtime starters, and the locally installed Nano/WASM package beneath `ai/`; old captures and the synthetic SD-card demo were removed. The firmware still uses `NullInferenceEngine` during capture.

## First: documentation and project presentation

1. Review the documentation set for duplication, stale history, and audience. Agree a small canonical navigation structure before adding more material.
2. Assess publishing the documentation through GitHub Pages in the main repository, with a simple landing page and links for teachers/facilitators, operators, and developers. This is a navigation/presentation task only; do not publish model weights, real captures, secrets, or machine-local artefacts.

## Then: deployment and browser-model evidence

3. Run a fresh camera collection from the clean card. After normal cable-power removal, mount the card and run `py tools\audit_card.py <card-root>`. Confirm raw, dashboard, and JPEG counts reconcile and the interrupted-power recovery path remains sound.
4. In Chrome and Edge, open the deployed `dashboard.html`, select **Find insects with AI**, choose the top camera-card folder once, and verify the live scan, pause/continue, stop, current image, and possible-insect cards on actual saved pictures. Record browser version, model-load time, first-result time, and any errors.
5. Benchmark at least 100 representative enclosure frames in the browser. Record median/p95 image time, total time, memory symptoms, cancellation behaviour, false positives, and misses. Extrapolate honestly to a 7,200-frame session; do not skip frames silently.
6. Keep the ESP32 capture loop model-free. Continue the bounded cadence/timer validation and a short battery-pack stability/clean-power-removal smoke test.

## Model and distribution gates

7. Record the official FlatBug Nano weight provenance and redistribution position. Do not add weights to Git or make species/identification claims.
8. Compare the browser single-pass 640x640 output against the reference FlatBug pipeline on a labelled enclosure set. Decide later whether limited tiling, a bespoke detector, or a research-only workflow is appropriate.
9. Treat Firefox, Safari, result export/persistence, and broad cross-browser accessibility as open work; current working evidence is Chrome and Edge only.

Before the next commit, run `py tests\check_project.py`, `git diff --check`, the relevant SD audit, and a clean PlatformIO build when firmware changes.
