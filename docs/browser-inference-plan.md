# Child dashboard and offline browser inference plan

Status: child dashboard and FlatBug Nano browser-analysis prototype implemented; production acceptance remains decision-gated
Recorded: 13 August 2026

## Outcome

Keep the ESP32 focused on reliable one-frame-per-second QXGA/JPEG-quality-12 capture and SD-card persistence. After collection, let the user open `dashboard.html` and deliberately start insect analysis on the computer. All inference must remain local and offline; images must not be uploaded.

This path is provisional. It supersedes the earlier assumption that the first production model must execute after each capture on the ESP32, but it does not yet approve a browser runtime or model. Every retained frame remains eligible for analysis.

## Child-first dashboard direction

The main experience is for a supervised young child, while technical details remain available to an adult:

- show a large, friendly full-page loading panel while session data is being read, with plain-language progress and a useful error/retry state;
- make the primary choices obvious, such as **Explore pictures** and **Find insects with AI**;
- use large touch targets, strong contrast, fun but restrained colours, short instructions, keyboard support, visible focus, non-colour status cues, and reduced-motion support;
- do not start model analysis during initial page loading;
- while analysing, show the current picture, progress through the session, discoveries so far, elapsed/estimated time only when trustworthy, and obvious pause/cancel controls;
- make the process engaging without disguising waiting, errors, or uncertainty; and
- consistently say **label**, **class**, **prediction**, or **possible insect**. Explain that AI can make mistakes and do not imply species identification.

The existing compact frame/gallery views, expand controls, modal image viewer, session-relative time, and adult health information should be retained or improved rather than removed.
## Implemented browser-analysis prototype (15 August 2026)

`dashboard/analysis.js` now provides the first child-facing analysis journey in the dashboard. It is a prototype, not validated detection or a production release:

1. The child selects **Find insects with AI** and sees a short explanation that predictions can be wrong.
2. An adult chooses the **top camera-card folder** once. The browser reads both its saved pictures and the FlatBug Nano ONNX/ONNX Runtime Web assets from that selected folder as File objects; it does not upload pictures, use a server, or make a network request.
3. The child presses **Start looking**. The dashboard processes saved images one at a time, yields between pictures, shows the current image with a moving scanner, changes friendly explanatory text, and immediately adds a card whenever a provisional possible-insect box appears.
4. Clear **Pause search** / **Keep looking** and **Stop search** controls remain available. The summary reports checked images, possible-insect image count, and any read/inference failures. Results remain in browser memory only and do not alter the authoritative SD-card records.

The current offline package contains ONNX Runtime Web WebAssembly with one thread plus two experimental models. The child makes one clear choice before starting:

- **AntAI - Beta**: a one-class ant detector, one 1024x1024 whole-picture pass.
- **FlatBug - Quick look**: FlatBug Nano, one 640x640 whole-picture pass for larger or clearer insects.
- **FlatBug - Look closely**: FlatBug Nano, 12 overlapping native-scale 640x640 tiles for a normal QXGA image, 4 across by 3 down, for tiny insects.

The FlatBug output is a segmentation tensor with four box channels, one insect-confidence channel, and 32 mask-coefficient channels. The browser must read only the insect-confidence channel; interpreting the coefficients as scores caused an August 2026 false-positive/over-100-percent display defect and is now covered by a regression check. All three paths merge duplicate boxes, retain small candidates, and remain experimental. The selected top camera-card folder must contain `ai/flatbug-n.onnx`, the runtime files, and, for AntAI, `ai/antai-beta.onnx`. `py tools\install_ai_pack.py <card-root> --include-antai-beta` installs both models. Chrome/Edge folder-picker evidence exists; Firefox/Safari, redistribution, representative-image validation, batch performance, persistence/export, and the 3,600-image feasibility gate remain open.


## Technical hypothesis

- Package the model, runtime and all UI assets on the SD card. No CDN, server, installation, account, analytics, or internet connection is allowed.
- Prototype ONNX Runtime Web with WebAssembly as the portable baseline. Treat WebGPU as optional acceleration, never as the only route.
- Continue supporting direct `file://` use in current Chrome, Edge, Firefox, and Safari on Windows 10/11 and current macOS.
- Prove local loading of model/WASM/worker assets and JPEGs in every target browser; do not assume behaviour that only works over HTTP.
- Process images incrementally in bounded batches, yield to the UI between batches, avoid retaining decoded full-resolution images, and provide pause/cancel and recoverable failure states.
- Keep camera data local. The first cross-browser result persistence method may be a clearly named CSV/JSON download. Direct write-back to the SD card is optional and cannot be required unless it is proven safe and simple across all target browsers.
- Version browser-produced predictions and preserve model ID/hash, settings and source capture IDs. Never alter the authoritative capture log in place.

## Preferred candidate: FlatBug

Evaluate FlatBug first if its official model artefacts can be obtained and licensed for this distribution. FlatBug is designed for general terrestrial arthropod detection and segmentation and uses YOLOv8 plus a custom pyramid/tiling workflow. The reference software is Python/PyTorch oriented and its published hardware guidance begins above 2 GB VRAM, so browser feasibility cannot be assumed. Exact weight size, supported export, tiling cost and accuracy on enclosure imagery must be measured.

Sources:

- https://asgersvenning.com/flat-bug/
- https://github.com/darsa-group/flat-bug/

If the full reference pipeline is too large or slow, make an explicit decision among:

1. use a smaller official FlatBug variant;
2. export/quantise or adapt it, with a new identity and measured accuracy change;
3. train or fine-tune a smaller one-class insect detector using appropriately licensed data; or
4. reject browser inference if it cannot meet the user journey.

Do not label a derived or replacement model as FlatBug without permission and accurate provenance.

## Feasibility experiment

Use a fixed representative set of at least 100 enclosure images, including empty frames and difficult conditions. Record:

- model/runtime bytes and browser peak memory;
- dashboard data-load time separately from model-load time;
- time to first prediction, median/p95 per-image time, total batch time, errors, and cancellation behaviour;
- agreement with the reference Python pipeline on the same images;
- detection quality before and after any export, quantisation, resizing, or tiling change;
- UI responsiveness and child-facing comprehensibility; and
- results for each required OS/browser combination, with WebAssembly results mandatory and WebGPU results supplementary.

Extrapolate the measured batch time and memory behaviour to a maximum 3,600-image session. Do not require analysis to match the camera's real-time 1 FPS capture rate; instead, agree a child-appropriate post-session wait-time target after the first benchmark. Do not auto-skip frames to meet it.

## Acceptance gate

Browser inference becomes the production direction only when:

- the offline `file://` package works without security-setting changes in the required browser matrix;
- the complete package size and analysis time are practical for the SD card and reference computers;
- the UI stays responsive, cancellable and understandable;
- results are reproducible, versioned, privacy-preserving and exportable;
- the model/dependencies/data are legally redistributable in the open-source project; and
- representative-image validation supports the exact claims shown to users.

Until then, firmware continues to record `model_unavailable`, and the dashboard must not display synthetic or unvalidated predictions as real observations.

## FlatBug `file://` loading result (14 August 2026)

A reproducible isolated spike is at `spikes/flatbug-browser/`. The official FlatBug v1.0.0 medium checkpoint was exported locally to a structurally valid 98.5 MB ONNX segmentation model (opset 18). The model remains ignored by Git pending confirmation that its weights may be redistributed.

The `file://` compatibility gate **did not pass in current Microsoft Edge**. The page, local ONNX model, and all ONNX Runtime Web 1.27.0 WebAssembly assets were present. However, ONNX Runtime Web dynamically imports its `.mjs` helper from its classic browser bundle, and Edge rejects that dynamic local module import from a direct local-file page. Explicit absolute `file://` asset paths and the WASM-only classic bundle produced the same failure. The ESM bundle also did not execute from the direct local-file page.

The direct-import route remains a regression diagnostic, but it is no longer the chosen architecture. The successful replacement is the single top-camera-card folder selection: it supplies both the local `ai/` assets and saved image File objects, which are loaded through Blob URLs and `createImageBitmap()`. This path is implemented in `dashboard/analysis.js` and has working Chrome/Edge evidence. It remains a prototype, not a production acceptance result.

## AntAI - Beta (in progress)

AntAI - Beta is a one-class, locally trained YOLO26 Nano ant detector, separate from FlatBug Nano. It is trained from the updated 49-image Roboflow COCO export (34 train, 10 validation, 5 held-out test images), with the source labels `ant` and `ants` deliberately merged into one `ant` class. It must be described as experimental until it has a substantially larger independent evaluation set.

When `artifacts/antai-beta-round-1/runs/train/weights/best.onnx` exists, install it alongside the existing runtime and FlatBug assets with:

```powershell
py tools\install_ai_pack.py D:\ --include-antai-beta
```

The dashboard presents AntAI - Beta as an ant-only choice and uses model-provided ONNX input/output names so it can coexist with FlatBug's 640px format. The card remains read-only in the browser.
When a card contains multiple saved runs, both the movie maker and AI dialogue default to the newest available session and provide a session selector. AI analysis reads only the selected run; it does not silently mix pictures from different experiments.
