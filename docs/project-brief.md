# Project Brief: Autonomous OV3660 Insect Camera, Logger, and Offline Analysis Dashboard

Status: active pilot implementation; scope authority and lower-level-agent task contract
Reviewed: 13 August 2026
Audience: project owner, lead agent, bounded implementation agents, and reviewers

## Current implementation status

The XIAO ESP32S3 Sense firmware has built, uploaded, and captured data on the physical OV3660/PSRAM/SD hardware. The null inference engine remains in place because no production model has been selected. The offline `file://` dashboard, recovery path, raw CSV log, atomic JPEG persistence, and card audit tool are implemented and tested.

Run `run_000012` verified the current JPEG-directory sharding design: 2,384 completed raw records, dashboard entries, and JPEGs were present, with image-write time remaining near 0.55 seconds through frame 2,300. This is evidence that sharding mitigates the earlier progressive FAT directory slowdown; it is not yet acceptance evidence for 2 FPS because the stage-duration telemetry conflicts with run-relative elapsed time. Remaining device work is a bounded timer/cadence check, endurance, recovery, and browser-matrix validation. A formal one-hour battery-capacity profile is deprioritised; retain a short stability and power-removal smoke test with the intended USB battery pack.

The next development tranche is a child-first dashboard redesign and a decision-gated experiment in post-session, offline browser inference. The ESP32 continues to capture and store every frame with the null inference adapter. The dashboard will load the session first, then let the user explicitly start local analysis. FlatBug is the preferred model candidate to investigate, but it is not selected: its exact weights, licence chain, ONNX export parity, tiling requirements, package size, memory use, performance, and accuracy on enclosure images must be measured. `docs/browser-inference-plan.md` is the controlling plan for this tranche. The initial dashboard shell is implemented without model integration: loading, welcome, gallery, no-model messaging, modal images, adult details, and local-file data loading are now the active UI baseline.

## 1. Purpose and authority

Build firmware and a removable-microSD data product for an insect-enclosure pilot. A Seeed Studio XIAO ESP32S3 Sense captures and safely stores OV3660 frames at 2 FPS. A non-technical user powers off the device, removes the SD card, inserts it into a computer, and opens the offline dashboard on Windows or macOS without installing software, running a server, using a command line, or having internet access. The provisional model path analyses every retained image locally in that browser after the user explicitly starts it; this must pass the gates in `docs/browser-inference-plan.md` before it becomes production architecture.

This file is the scope authority. Lower-level agents must not silently fill product gaps, broaden features, or change shared schemas. Items marked **decision gate** require owner/lead resolution before dependent work. Defaults permit safe platform development but do not turn an unresolved model into a real detector.

The repository now contains a built and device-tested pilot firmware, offline dashboard, SD preparation/audit tools, and host-side contract checks. Hardware facts are authoritatively recorded in `docs/camera-spec.md`: ESP32-S3R8 (dual-core Xtensa LX7, up to 240 MHz), OV3660, 8 MB PSRAM, 8 MB flash, onboard FAT microSD support up to 32 GB, and battery operation through the BAT input. The assembled case/heatsink is out of scope for this software project.

Manufacturer references:

- Board/setup: https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- Camera: https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/
- Hardware files: https://github.com/Seeed-Studio/OSHW-XIAO-Series

`docs/camera-spec.md` is the authority for this project’s hardware and power figures. It records battery input at 4.2 V, ready-state operation at 3.8 V/43.2 mA with the expansion board, and webcam operation at approximately 3.8 V/154 mA average and 304 mA peak. These figures are sufficient to deprioritise a formal one-hour battery-capacity profile for this pilot. Validate the completed 2-FPS capture/store workload with a short stability, temperature, and clean-power-removal smoke test using the intended USB battery pack; browser-side inference does not add to the device power load. Older OV2640 examples are reference material only; do not copy their maximum resolution or tuning assumptions.

## 2. Product outcome and users

The primary user is a non-technical ecologist, teacher, workshop facilitator, or supervised child. A user should be able to:

1. power on the battery-powered device and leave it collecting unattended for up to one hour;
2. power it off by disconnecting its power cable;
3. remove the SD card only after power is disconnected and insert it into a computer;
4. access its files through the computer's ordinary file manager;
5. double-click `dashboard.html`; and
6. explore images and simple session information, then deliberately start entertaining, clearly explained local AI analysis; and
7. let an adult open predictions, charts, exports, and detailed device/run health entirely offline.

The pilot succeeds only if data remains intelligible after ordinary faults, real detections are clearly distinguishable from test data, and the dashboard does not require browser permissions beyond opening local files.

## 3. Scope and priorities

### Must — pilot platform

- Pinned, reproducible Arduino-ESP32/PlatformIO firmware for the confirmed XIAO ESP32S3 Sense and OV3660.
- Autonomous boot, fixed 2-FPS capture and retention of every frame, structured logging, summary generation, and offline dashboard. During the current feasibility phase, the device records null inference and the dashboard may analyse every retained frame only after an explicit user action.
- PSRAM detection and explicit failure/degraded behaviour.
- Versioned configuration, event/data schemas, and migration policy.
- Direct `file://` dashboard operation in Chrome, Edge, Firefox, and Safari on Windows 10/11 and current macOS, with no `fetch()`, CDN, server, installation, or internet.
- Power-loss-aware writes: previously committed data stays usable; incomplete tail records/files are detected and recovered or ignored.
- Graceful missing/full/corrupt SD, camera-init failure, bad config, model failure, and image-write failure.
- Meaningful serial diagnostics with firmware/config/model/run identifiers and no secrets.
- Host-side tests for pure logic, dashboard tests with representative data, and physical-device tests in the enclosure.
- Complete setup, deployment, operation, safe-removal, data interpretation, recovery, and maintenance documentation.

### Must — real field detection release

These become mandatory only after the model decision gate is satisfied:

- A licensed production model artifact, label map, preprocessing/postprocessing specification, measured accuracy evidence, and supported input resolution.
- Clear validation on representative enclosure imagery, including empty frames and likely confounders.
- Measured browser load/inference time, memory, package size, output parity, and responsiveness using that exact model, plus independent device capture-cadence evidence.
- No test/stub detection may be shown or exported as a real observation.

### Should

- Classification and object-detection result support in the versioned inference contract.
- Efficient handling of the fixed every-frame retention policy, including bounded gallery pagination and optional thumbnails.
- Responsive overview, class table, timeline, charts, gallery, search, filters, and run/health view.
- Incremental dashboard loading from bounded data chunks; one corrupt chunk must not prevent all other data being viewed.
- Optional thumbnails distinct from full images to keep the gallery responsive.

### Could — later ADR and separate acceptance criteria

- Segmentation, multiple model backends, motion pre-trigger, environmental sensors, battery telemetry, signed OTA, or network time synchronisation.

### Won’t — pilot scope

- Cloud storage/accounts, telemetry, remote viewing, native apps, live streaming, public web service, facial recognition, audio recording, or editing the physical enclosure/camera-case assets.
- Claiming species-level ecological accuracy unless the selected model and validation support it. The UI should use “class” or “label” until that evidence exists.

## 4. Resolved decisions and remaining gates

The following are confirmed project decisions:

1. **Hardware:** ESP32-S3R8 XIAO ESP32S3 Sense with 8 MB PSRAM/flash, OV3660, onboard FAT microSD support, and battery power. Source: `docs/camera-spec.md`.
2. **Model:** no production model exists yet. The device provides only the model interface and a `MODEL_UNAVAILABLE` null engine. FlatBug is the preferred candidate for the first browser feasibility test, not an approved production dependency. A deterministic fake engine is test-build-only and visibly marked `TEST DATA`.
3. **Capture/inference:** capture and store every frame at 2 FPS for a maximum one-hour session, or 7,200 retained frames. The provisional browser path offers post-session inference for every retained frame after an explicit user action. Browser analysis need not run at 2 FPS, but its measured wait time must be acceptable for the child-facing journey and it must never silently skip images. The ESP32 capture requirement remains independent of model speed.
4. **Time:** session-relative only. `boot_id + monotonic_ms` is authoritative; date, hour, and “today” controls are unavailable rather than fabricated.
5. **Power/stop/transfer:** battery powered; disconnecting the power cable stops collection. The user then removes the SD card and inserts it into a computer for transfer. The SD card must not be removed while the device is powered.
6. **Retention/privacy:** keep every captured frame; people may appear in view; anyone may use the transferred data; real images may be used in demonstrations. Repository samples still require appropriate permission and licensing. Users delete data manually through the computer's file manager; the dashboard has no deletion feature.
7. **Distribution:** open source. The owner must select a specific project licence and ensure compatibility with every later model, library, icon, and sample-data licence.
8. **Dashboard support:** Windows 10/11 and current macOS using Chrome, Edge, Firefox, and Safari, tested offline from `file://`.
9. **Terminology:** use “label”, “class”, and “prediction”; do not claim species identification or ecological accuracy before model validation.

Remaining future gates: prove or reject the browser-inference architecture; select, license, export, benchmark, and validate a production model before field-detection claims; and select the project's open-source licence before public release. Transfer and deletion require no additional software feature: users work directly with the removable SD card in the computer's file manager.

## 5. Required system behaviour

### Boot and run lifecycle

1. Generate/persist a unique device ID and generate a new `boot_id` for each boot.
2. Initialise serial diagnostics, validate PSRAM/hardware identity, and load configuration using documented defaults if missing.
3. Mount and health-check SD. Never auto-format a card. Missing/unusable storage enters a visible error/retry state, not a reboot loop.
4. Recover incomplete temporary files and malformed CSV tail records without discarding earlier committed data.
5. Initialise OV3660 using a tested preset. Initialise the null inference adapter; do not require a production model to boot or capture during the browser feasibility phase.
6. Create a run/session record containing firmware, schema, config, model, board, sensor, and time-source facts.
7. Start the monotonic capture schedule. Each due frame moves through capture, null-inference status, retention policy, image write, raw log, and summary/chunk update with explicit outcomes. Post-session browser inference is a separate user-initiated workflow.
8. Periodically flush/commit within a documented data-loss window. On power-cable disconnection, files must be recoverable within the documented loss window. The user removes the SD card only after the device has lost power.

If the camera cannot initialise, the system must record/indicate the fault and retry only with bounded backoff. A missing production model must not prevent capture during the browser feasibility phase; the device records `model_unavailable`. Neither device nor dashboard may generate plausible fake detections to appear healthy.

### Scheduling and resource ownership

- Use monotonic deadlines from a baseline to capture every frame at fixed 2 FPS. The null adapter must not delay the device loop. Browser inference runs later in bounded, cancellable batches and yields to the UI; it must report progress/errors and never quietly reduce the capture rate, skip analyses, or create an unbounded memory backlog.
- One component owns the camera and frame-buffer lifecycle. Define who releases each buffer on every success/error path.
- Use bounded queues. Define overflow policy and report dropped work.
- Serialize SD writes or otherwise prove filesystem safety. Dashboard maintenance must not block capture indefinitely.
- Avoid unbounded heap growth, recursive full-card scans, and loading full-resolution galleries/datasets into RAM.

### Inference contract

Keep the device's narrow interface such as `InferenceEngine::run(const FrameView&, InferenceResult&)`; do not couple capture or storage modules to any model backend. Add a separately versioned browser adapter that maps model outputs into the same normalised result concepts without pretending browser results were produced during capture. The versioned result must support:

- outcome: `ok`, `model_unavailable`, `invalid_input`, `runtime_error`, or `timeout`;
- task type: classification or object detection;
- zero or more predictions with stable label ID, display label, confidence, and optional normalised bounding box;
- capture/model IDs, inference duration, and optional bounded numeric metadata;
- segmentation only through a future schema version/ADR, not an unused memory-heavy field in the pilot.

Preprocessing and postprocessing belong to the applicable device or browser model adapter. Other components consume normalised results. A deterministic fake engine is allowed only in tests/builds visibly marked `TEST DATA`; a null engine returns no observations and a health error. Browser exports must include analysis ID, model version/hash, settings, source capture ID, runtime, and outcome so later analysis is distinguishable from the capture-time log.

### Retention policy

The pilot saves every captured frame: 2 FPS for no more than one hour (7,200 images). There are no detection-only, threshold, cooldown, burst, or automatic deletion modes in this release. One original JPEG links to zero or more predictions; never duplicate a JPEG for each box. Capacity planning must measure actual OV3660 JPEG size and reserve enough free space to close the run safely. If the card becomes full, record the failure and stop collection rather than overwrite/delete retained observations.

## 6. Authoritative data model

Use stable ASCII/UTF-8 names and RFC 4180-compatible CSV quoting. Raw CSV is authoritative; JavaScript dashboard files are derived and rebuildable. To avoid ambiguous multi-object rows, use two related tables rather than overloading one `detections.csv` row.

### `captures.csv` — one row per scheduled analysis outcome

Required columns:

```text
schema_version,device_id,run_id,boot_id,capture_id,
captured_at_utc,uptime_ms,scheduled_ms,outcome,
frame_width,frame_height,jpeg_bytes,capture_ms,inference_ms,
model_id,prediction_count,max_confidence,image_path,
save_policy,save_outcome,error_code
```

`captured_at_utc` is empty unless the time source is valid. `outcome` distinguishes completed, skipped, capture error, inference error, and storage error. `image_path` is a relative safe path or empty.

### `detections.csv` — one row per prediction

Required columns:

```text
schema_version,run_id,capture_id,prediction_index,
label_id,label,confidence,bbox_x,bbox_y,bbox_w,bbox_h,
model_id,metadata_json
```

Bounding boxes are normalised to `[0,1]` and empty for classification. JSON inside CSV must be correctly escaped, bounded, and schema-documented. Labels are untrusted display data in the dashboard and must be rendered with text APIs, not injected as HTML.

### Run/configuration records

Each run has a small versioned manifest with start/end or interrupted state, firmware/build, board revision, OV3660 PID, config hash/snapshot, model ID/hash, time-source status, counters, and fatal/degraded errors. Credentials or personal identity never belong in any record.

Use sortable collision-free IDs independent of calendar time, for example persisted device/run counters plus boot-local capture sequence. Do not rely on an unset clock or assume atomic counter writes; use checksum/dual-slot or equivalent recovery.

Images should follow a bounded layout such as `/images/<run-id>/<capture-id>.jpg`, with optional `/thumbs/...`. Sanitize paths, use temporary-write/close/flush/rename where FAT/library semantics allow, and record the precise durability limitations. A valid log entry must never claim an image exists until the image commit succeeds.

## 7. Offline dashboard data and UI contract

The original idea of indefinitely appending `window.detections.push(...)` to one `data.js` is unsafe: a torn final JavaScript statement can prevent the entire file parsing. Use bounded immutable committed chunks plus a small manifest, for example:

```text
/
  dashboard.html
  dashboard.css
  dashboard.js
  manifest.js             # atomically replaced derived index
  summary.js              # atomically replaced derived summaries
  data/
    captures_000001.js    # closed immutable chunks
    detections_000001.js
  raw/
    captures.csv          # authoritative append log
    detections.csv
    runs/
  images/<run-id>/
  thumbs/<run-id>/
  config.json
```

Exact names/schema are frozen by WP1. Closed chunks assign data to a namespaced global; they do not contain executable user-derived text. `manifest.js` lists only committed chunks, schemas, summary version, and health/staleness data. Build it to a temporary file and replace the prior valid manifest only after closing. If replacement atomicity cannot be demonstrated on the chosen FAT stack, use alternating A/B manifests with sequence/checksum and a fixed loader that chooses the newest valid copy.

The dashboard may load local `<script src>` files because `fetch()` is commonly blocked under `file://`. Test static and dynamically added local scripts in every supported browser. If any target browser forbids the chosen loader, resolve with a documented packaging approach; do not ask non-technical users to disable browser security or run a server.

The dashboard must:

- present a child-first landing experience with large touch targets, short directions, fun accessible colours, and a large full-page data-loading state with useful progress/error/retry messaging;
- load the session before offering analysis, never start AI work automatically, and provide an explicit **Find insects with AI** action;
- keep long analysis responsive and engaging with current-image/progress feedback, honest uncertainty, and obvious pause/cancel controls, while preserving reduced-motion and keyboard support;

- open from `dashboard.html` and visibly report dataset/schema compatibility, last committed update, incomplete run, model/test-data identity, clock validity, and degraded device states;
- remain useful if an image is missing or one nonessential chunk is invalid;
- load bounded pages/chunks and thumbnails rather than all records/full images;
- show total analysed frames, detections/predictions, images saved, errors/skips, storage use, inference/capture performance, and run duration;
- provide class table, session-relative timeline, charts, gallery/lightbox, search, and filters by label, confidence, run, and image availability;
- distinguish captures from predictions so multiple boxes in one image do not inflate image counts;
- explain confidence as model score, not probability or ecological certainty;
- make calendar-dependent “today/hour/date” views conditional on valid wall time;
- use semantic HTML, keyboard operation, visible focus, non-colour cues, reduced-motion support, and a responsive 320 px layout;
- use safe DOM construction (`textContent`, validated attributes) for label/metadata content; and
- contain no CDN, analytics, external fonts, network calls, or runtime dependency outside the card.

Embedded Chart.js is acceptable only if its exact version, licence, minified source, flash/card cost, and local-file behaviour are recorded. Prefer a lightweight custom chart implementation if it meets accessibility and performance needs more simply.

Provide synthetic, prominently labelled sample data with empty, small, large, multi-label, missing-image, invalid-clock, interrupted-run, and corrupt-chunk fixtures. Real pilot images may be used in demonstrations or releases only when the project owner holds the necessary permissions, privacy approval, and licences; never represent generated samples as field observations.

## 8. Configuration contract

Use versioned `config.json` with documented defaults and bounds. At minimum:

- fixed device capture cadence: 2 FPS, every frame, maximum one-hour session; browser analysis still targets every retained frame but runs post-session;
- frame size and JPEG quality using tested presets;
- model ID/backend and label-map version;
- global/per-label confidence threshold for future model interpretation only; it does not alter the every-frame retention policy;
- flush/chunk/summary cadence and storage reserve;
- optional time-source settings; and
- log level/device display name.

Never blindly deserialize into runtime state. Validate types, ranges, combinations, enum values, maximum strings/labels, and resource implications. Unknown fields follow a documented forward-compatibility rule. Missing config uses a known default snapshot; corrupt config is quarantined/reported and falls back safely. The effective config and hash are stored with each run. Configuration changes apply on the next documented boundary (normally reboot), not halfway through a capture without audit.

## 9. Power-loss, storage, and error guarantees

“Power failures must not corrupt the system” means:

- firmware/dashboard assets are not modified during ordinary logging;
- previously closed raw records and dashboard chunks remain parseable after interruption;
- a torn last CSV row is detected and truncated/ignored at next boot without losing earlier rows;
- incomplete image/temp/chunk/manifest files are ignored or recovered deterministically;
- summary/dashboard data may lag by no more than the documented commit window and disclose that lag;
- authoritative CSV and derived dashboard counters can be reconciled by a supplied desktop rebuild/validation tool; and
- no promise of impossible absolute durability is made beyond measured FAT/SD/power behaviour.

Errors use a stable catalogue with severity, component, retryability, user consequence, and counters. Required cases include missing/unmountable/full/removed SD, read/write/rename failure, corrupt config/manifest/tail, camera init/capture failure, PSRAM absence, model missing/incompatible/runtime error, queue overflow, missed deadline, invalid time, and dashboard schema mismatch.

Serial logs must be bounded/rate-limited and include IDs needed for correlation. Users need a visible way to distinguish starting, collecting, degraded/fault, and fatal states without a serial console.

## 10. Technical baseline and repository

Use PlatformIO with Arduino-ESP32 and exact versions pinned; “latest” is not reproducible. An ESP-IDF change requires an ADR with concrete benefit and migration cost. Use modern C++ appropriate to the pinned embedded toolchain, explicit ownership, small modules, and comments explaining hardware constraints/trade-offs rather than restating code. Doxygen-compatible public interfaces are useful; “extensive comments” is not a substitute for tests and clear names.

Suggested source boundaries: application/state machine, OV3660 camera adapter, inference interface/backends, capture policy, storage/raw logger, dashboard chunk/summary writer, configuration, time/IDs, health/diagnostics, and utilities. Hardware calls must sit behind interfaces so scheduling, policies, schemas, recovery, and summaries can be host-tested. Every dependency needs version, licence, purpose, maintenance status, and measured flash/RAM/card impact.

Suggested repository:

```text
platformio.ini
README.md
LICENSE                    # owner decision
docs/
  architecture.md
  data-schema.md
  hardware-validation.md
  model-card.md
  operations.md
  decisions/
include/
src/
  app/ camera/ inference/ policy/ storage/ config/ time/ health/
dashboard/
  src/ fixtures/ tests/
test/
  native/ device/
tools/
  validate_or_rebuild_dataset/
```

Do not commit credentials, generated firmware/build directories, copied model files without licence, or large generated card datasets. Real pilot imagery may be committed only with documented permission, privacy approval, and licence; otherwise distribute it separately or use synthetic fixtures. Work only inside this software directory unless scope is explicitly expanded. Preserve unrelated changes and record shared-contract changes before downstream agents proceed.

## 11. Work packages for lower-level agents

The lead owns integration and shared contracts. Agents must read this brief plus relevant ADRs, update tests/docs with behaviour, and not bypass module ownership.

### WP0 — Physical feasibility and decisions (first)

Confirm board revision, OV3660 PID, flash/PSRAM, pin map, supported SD cards/filesystems, battery supply/cable, camera focus/field of view, SD/button/LED access, and stable camera/SD examples. Produce `docs/hardware-validation.md`, measurement method, photos/identifiers where appropriate, and initial ADRs. Do not change physical assets.

### WP1 — Architecture, states, and schemas

Freeze component ownership, event/state/error model, config, CSV, run manifest, dashboard chunk/manifest, IDs, durability window, and migration rules. Produce `docs/architecture.md` and `docs/data-schema.md` plus contract tests/fixtures. No full drivers or polished UI.

### WP2 — Camera and scheduler

Own OV3660 lifecycle/presets, monotonic scheduling, frame-buffer ownership, rate/skip counters, and bounded delivery to inference. Provide host-testable scheduler logic and device tests. Do not implement model, SD schema, or UI.

### WP3 - Device and browser inference adapters

Own the device null/test interface plus the decision-gated browser backend, preprocessing/postprocessing, model identity, predictions, export parity, package/memory/timing metrics, and model-card evidence. Evaluate FlatBug first. Never leak backend types into WP2/WP4 or add unlicensed weights. Do not claim field accuracy without the model gate.

### WP4 — Persistence and recovery

Own SD lifecycle, IDs, images/thumbnails, authoritative CSV, run records, atomic-style commit/A-B manifest, dashboard chunks/summaries, capacity reserve, tail recovery, and reconciliation tool. Test against filesystem faults. Do not access camera/model directly.

### WP5 — Offline dashboard

Build against frozen WP1 fixtures before device data exists. Own the child-first local-file loader; full-page loading and guided analysis states; schema checks; overview/table/timeline/charts/gallery/search/filters/health; pagination; responsive accessibility; and safe rendering. Coordinate browser-model execution through the WP3 adapter and keep adult details available without dominating the child journey. Do not redefine schemas or require a server/network.

### WP6 — Configuration, health, and physical UX

Own validation/defaults/migration, effective-config snapshots, error catalogue, serial diagnostics, health counters, and approved safe-stop/status indication. Coordinate pin use with WP0/WP2.

### WP7 — Integration, verification, and operations

Wire modules, pin builds, run end-to-end/fault/soak/power/thermal/browser tests, validate/rebuild sample cards, write user/developer docs, and produce checksummed release artifacts plus known issues. Do not waive Must criteria without owner approval.

Dependency order: **WP0 → WP1 → WP2/WP3/WP4/WP6 in parallel → WP5 against WP1 fixtures → WP7.** WP3 production work waits for the model gate; its interface/null/test work may proceed.

## 12. Verification matrix and measurable budgets

Every physical result records board revision, firmware commit/build, OV3660 PID/settings, model ID/hash, effective config hash, SD make/capacity/filesystem, supply/cable, enclosure state, ambient/case temperature, run ID, client OS/browser, and test result.

Required scenarios:

- clean/missing/corrupt/out-of-range configuration;
- empty, typical, and nearly/full SD; removal/write/rename failure where safely testable;
- camera/model/PSRAM init failure and inference runtime failure;
- rate overrun, queue overflow, 7,200-frame session, multiple predictions, and no detections;
- session-relative time without a valid wall clock;
- power interruption during image, CSV, chunk, summary, and manifest updates;
- recovery across at least 10 forced power cycles without losing earlier committed records;
- at least 100 consecutive device capture/null-inference cycles without leak, collision, or corrupt image, plus a separate 100-image browser inference responsiveness/memory test after model export;
- at least one complete one-hour, 7,200-frame session with zero uncontrolled reboot; capture, storage, and error counts must reconcile exactly; after model approval, a separate browser analysis must account for every retained frame with explicit success/error outcomes;
- raw-to-dashboard counts and image links reconcile for empty/small/large/interrupted datasets;
- one missing image, corrupt optional chunk, stale summary, incompatible schema, and test-data marker;
- `dashboard.html` opened from SD/local copy in every supported OS/browser with network disabled;
- 320 px, keyboard-only, visible focus, non-colour state, reduced motion, and large-dataset responsiveness; and
- final-device focus/lighting/reflections, Wi-Fi disabled unless required, thermal margin, battery/supply voltage drop, and SD/button/indicator access.

Performance budgets are established in WP0/WP3 and then frozen in an ADR. Initial measurement goals, not unsupported promises:

- boot to collecting or visible fault ≤30 seconds;
- fixed 2-FPS device capture with achieved capture FPS reported; post-session browser analysis covers every retained frame and reports load time, first-result time, analysed FPS, total time, memory, and errors separately;
- no unbounded backlog or silent skipped analysis;
- dashboard first useful view ≤3 seconds for the agreed typical dataset and bounded memory on reference computers;
- documented maximum tested card duration/record count/chunk size; and
- temperatures remain within manufacturer limits with an agreed margin during the soak.

## 13. Deliverables and acceptance

Deliver:

- complete pinned firmware source and build configuration;
- offline dashboard sources/assets and synthetic fixtures;
- dataset validation/rebuild tool usable through a documented non-technical distribution path where required;
- versioned schemas, architecture diagram, ADRs, model card, hardware/power/thermal evidence, and test reports;
- setup, SD preparation, deployment, operation, indicator, safe-stop/removal, dashboard, troubleshooting, recovery, maintenance, and developer guides;
- sample card image/archive containing only clearly marked synthetic data; and
- checksummed release artifacts, licences/notices, and known limitations.

The pilot platform is accepted only when a clean machine reproduces the build; actual board/OV3660 facts are recorded; autonomous collection and all fault states work in the enclosure; committed CSV survives the power-cycle tests; derived dashboard data reconciles to raw records; the offline dashboard passes the browser matrix without network/server; test data cannot be mistaken for observations; power/thermal/storage limits are documented; and a new facilitator can complete the primary journey from the guides.

A real field-detection release additionally requires acceptance of the browser architecture (or a documented replacement), the model gate, reference-output parity, representative validation, measured model package/memory/throughput, and owner-approved accuracy/label claims. Until then the deliverable is an instrumented logging/dashboard platform, not a scientifically validated species detector.

Every subtask is done only when it traces to a requirement/ADR; interfaces, ownership, limits, schemas, and errors are documented; relevant automated/physical tests pass; commands reproduce; failure and cleanup paths were reviewed; no secret, unbounded resource use, warning, undocumented dependency, or false detection claim was introduced; shared-contract changes were communicated; and the lead can integrate without reverse-engineering unstated assumptions.
