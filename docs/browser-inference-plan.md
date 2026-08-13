# Child dashboard and offline browser inference plan

Status: proposed development path and decision-gated technical spike  
Recorded: 13 August 2026

## Outcome

Keep the ESP32 focused on reliable two-frame-per-second capture and SD-card persistence. After collection, let the user open `dashboard.html` and deliberately start insect analysis on the computer. All inference must remain local and offline; images must not be uploaded.

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

Extrapolate the measured batch time and memory behaviour to a maximum 7,200-image session. Do not require analysis to match the camera's real-time 2 FPS capture rate; instead, agree a child-appropriate post-session wait-time target after the first benchmark. Do not auto-skip frames to meet it.

## Acceptance gate

Browser inference becomes the production direction only when:

- the offline `file://` package works without security-setting changes in the required browser matrix;
- the complete package size and analysis time are practical for the SD card and reference computers;
- the UI stays responsive, cancellable and understandable;
- results are reproducible, versioned, privacy-preserving and exportable;
- the model/dependencies/data are legally redistributable in the open-source project; and
- representative-image validation supports the exact claims shown to users.

Until then, firmware continues to record `model_unavailable`, and the dashboard must not display synthetic or unvalidated predictions as real observations.
