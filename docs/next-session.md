# Next session checklist

The SD card has been reset for rapid pilot iteration and a clean camera test is under way. Do not spend the next session reconstructing discarded early test data.

1. Power down normally by removing the cable, mount the card, and run `py tools\audit_card.py <card-root>`. Confirm the clean-card run has matching raw, dashboard, and JPEG counts and that the interrupted-run recovery path remains sound.
2. Preserve the existing firmware/null inference boundary. The ESP32 should capture and store frames; do not add a production model to its capture loop during the browser feasibility phase.
3. Review and refine the implemented child-first dashboard shell described in `docs/browser-inference-plan.md`: test the full-page loading state, large guided actions, clear instructions, fun accessible colours, and adult details using empty, loading, success, partial-data, and error fixtures.
4. Keep initial dashboard loading separate from AI analysis. Add the **Find insects with AI** journey as a non-functional/prototype state first, including progress, current image, pause/cancel, uncertainty language, and an honest no-model state.
5. Investigate FlatBug as the preferred candidate. Obtain the smallest relevant official weights and record version, hash, source, licence, byte size, task, labels, input, and reference runtime. Do not add copied weights to Git until redistribution is confirmed.
6. Run a narrow export experiment outside the dashboard: compare the reference FlatBug Python output with an ONNX export on a small fixed image set, and determine which parts of its pyramid/tiling and merging pipeline must be reproduced.
7. Only if export parity is credible, build the offline browser spike with locally packaged ONNX Runtime Web. Prove `file://` model/WASM/JPEG loading before investing in the polished analysis UI.
8. Benchmark at least 100 representative enclosure images in WebAssembly, then optional WebGPU, recording the measures in `docs/browser-inference-plan.md`. Extrapolate to 7,200 images and agree an acceptable post-session wait target; do not silently skip frames.
9. Test the child dashboard and inference spike on Windows 10/11 and current macOS in Chrome, Edge, Firefox, and Safari. Treat WebAssembly as mandatory and WebGPU as optional.
10. Complete one bounded performance-timer/cadence validation and continue SD endurance toward 7,200 retained captures. Run only a short actual-battery-pack stability/power-removal smoke test, not a formal capacity profile.
11. Run `py tests\check_project.py`, `git diff --check`, and a clean PlatformIO build before committing a completed tranche.

Decision gates for the next tranche: FlatBug model artefact/licence availability, ONNX export parity, acceptable browser package size/memory/time, safe cross-browser result persistence, and the precise claims validated by enclosure data.
