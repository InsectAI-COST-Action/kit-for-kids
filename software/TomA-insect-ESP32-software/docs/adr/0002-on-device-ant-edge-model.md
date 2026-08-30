# ADR 0002: On-device ant edge model

- **Status:** Accepted for prototyping. Production adoption is gated on the acceptance criteria in this ADR's Phase 3.
- **Date:** 30 August 2026
- **Decision owner:** project owner (Tom August)
- **Supersedes:** nothing. Amends the exclusion in [ADR 0001](0001-device-hosted-control-app.md), which named on-device inference as "a separate future decision and is not authorised by this ADR." This is that decision.

## Context

The project brief and `docs/next-session.md` have stated since the AntAI-Beta evaluation that device capture must stay model-free: AntAI-Beta is a 10 MB float ONNX model with a 1024px input, which exceeds the XIAO ESP32-S3's 8 MB flash and 8 MB PSRAM outright. That conclusion is correct for that model and remains true today - it is not being revisited here.

A collaborator has independently been developing a **different, purpose-built model** for exactly this hardware: ESPDet-Pico, Espressif's own lightweight single-class detector architecture (0.36M parameters, 224×224 input, published as achieving >7 FPS on ESP32-S3 at that resolution). Their ant-specific model (`models/ESPDet-Pico/AntTestModel.espdl` in the upstream `kit-for-kids` monorepo) was an empty placeholder as recently as 28 August 2026; as of 30 August 2026 it has been populated with real weights (~498 KB) and shows active recent iteration. This is new feasibility evidence, not a change of mind about AntAI-Beta - a 0.36M-parameter, 224px model and a full-precision 1024px model are not comparable on memory footprint.

`include/inference.h` already anticipates this: `IInferenceEngine` (`begin()`/`run()`) is the abstraction point, `NullInferenceEngine` is the current implementation, and `AppConfig.model_id` already exists as a config field (default `"none"`). The capture pipeline already logs `inferenceOutcome`/`prediction_count`/`max_confidence`/`inferenceMs` per frame into `captures.csv` and the dashboard - these have shown `model_unavailable` for every capture on every card produced so far, by design, not by omission.

## Decision

Add an **on-device ant edge model**, selected via `config.model_id`, implementing the existing `IInferenceEngine` interface. Scoped narrowly:

### Explicitly in scope

- Loading and running the collaborator's `AntTestModel.espdl` (ESPDet-Pico architecture) via Espressif's ESP-DL runtime, on a low-resolution preview frame captured alongside (not instead of) the existing QXGA retained image.
- Populating the *existing* `inferenceOutcome`/`prediction_count`/`max_confidence`/`inferenceMs` fields with real values when this model is selected. No schema change.
- A feasibility spike (`spikes/edge-ant-model/`) validating the ESP-DL/PlatformIO/Arduino-framework build integration in isolation before any change to `main.cpp` - this project's established pattern (`spikes/motion-detection/`, `spikes/flatbug-browser/`) for exactly this kind of technical risk.
- `model_id` opt-in only. The pilot default (`config.example.json`, `"none"`) is unchanged; this ships disabled unless explicitly selected.

### Explicitly out of scope (for this ADR)

- Changing capture or retention policy based on detection results (e.g. "only save when an ant is detected"). This ADR only makes existing logging fields real; behavioural changes based on them are a separate future decision.
- AntAI-Beta or any browser-side model - unaffected, unchanged, and this ADR does not revisit the earlier infeasibility finding for that model.
- Making the edge model the pilot default. It remains opt-in until it has passed the physical acceptance criteria below.
- Redistributing or committing the model weight file into this repository's git history.

## Alternatives considered

**Wait for the collaborator's own integration/demo path.** Their `models/deploy/` artifact is a complete standalone flash image (bootloader + partition table + app at fixed offsets) - a demo, not a library, with no available source showing how it invokes the model. Rejected for now: it would mean overwriting this project's entire firmware with theirs, losing every capability built so far (dev bridge, control app, dashboard writer, motion detection). Revisit only if this project's own ESP-DL integration proves infeasible.

**Do nothing; treat "model-free" as still closed.** Rejected: the owner has explicitly requested this be tried, citing new feasibility evidence from a real collaborator model that the original constraint did not anticipate.

## Consequences

**Positive**

- If the spike succeeds, this project gains real on-device detection using existing, already-wired logging infrastructure - a small, well-contained addition rather than a redesign.
- Keeps AntAI-Beta/browser-side analysis and device-side detection as clearly separate, independently-evolvable tracks.

**Negative / accepted costs**

- Genuine, unresolved technical risk: ESP-DL's own documentation describes it as ESP-IDF-only, with no confirmed PlatformIO/Arduino-framework compatibility. This may require a build-system change (`framework = arduino, espidf` mixed mode, or similar) that isn't needed by anything else in this firmware today.
- Inference cost is additive to an already-thin per-frame cadence budget (`docs/performance-experiment.md`). Must be measured, not assumed acceptable.
- A second capture-mode branch (alongside retain-all and motion-trigger) in an already fairly branchy `main.cpp` capture loop.
- Risk of the pilot's critical path slipping - the one-hour endurance test, cross-browser verification, and battery smoke test remain the route to a working pilot and must not be displaced by this track, matching the same caution ADR 0001 recorded for the control app.

**Neutral**

- No change to the SD card's data schema or the offline dashboard's reading logic - both already handle real `inferenceOutcome` values (the "AI results are ready to explore" branch already exists and has simply never been exercised by real device data).

## Compliance and review

This ADR authorises the feasibility spike and, contingent on its success, a first working integration - not production adoption. Phase 3 acceptance (a live run with real ants, results reviewed by eye, timing/memory headroom confirmed, recorded in `docs/hardware-validation.md`) gates whether this becomes an offered, documented feature rather than an experimental branch. If the ESP-DL/PlatformIO integration proves genuinely infeasible under `framework = arduino`, that finding is recorded here and the decision is revisited - not silently worked around.

**Status update, 30 August 2026: blocked on a machine-specific policy, not a technical dead end.** The spike (`spikes/edge-ant-model/`) found no architectural incompatibility - PlatformIO successfully resolves and downloads the full ESP-IDF toolchain for a mixed `arduino, espidf` build on this project's exact platform/board. It is currently blocked by this development machine's Device Guard policy refusing to run the downloaded `cmake.exe`, the same class of restriction already known to affect the `pio.exe` launcher stub (`docs/next-session.md`), but a different binary that the pure-Arduino build never needed. See `spikes/edge-ant-model/README.md` for the exact error and three unactioned options (an IT exception, WSL2, or building on a different machine and transferring only the compiled firmware). This ADR's authorisation stands; Phase 1 is paused on this environmental blocker, not concluded.
