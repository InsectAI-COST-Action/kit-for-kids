# FlatBug browser feasibility spike

This folder records the offline browser-model feasibility work. It is not a validated detector and is not part of the ESP32 firmware.

## Active route: `picker.html`

Open `picker.html` with `file://` in Chrome or Edge, choose this folder, then choose one test image. The page loads ONNX Runtime Web through browser File objects and Blob URLs, using WebAssembly only. It runs a single 640x640 letterboxed FlatBug Nano ONNX pass, applies provisional box filtering, and labels results as **possible insects**.

The associated dashboard implementation uses the same technique, but asks an adult to select the top camera-card folder once. This supplies both the saved images and the local `ai/` package without uploading data or running a server.

## Local model policy

Model weights and ONNX exports are intentionally ignored by Git. The current local technical artefact is FlatBug v1.0.0 Nano exported as `assets/flatbug-n.onnx` (11,906,627 bytes; SHA-256 `ec75aeb85b42c86663b006f650681a2d5728d89cff096deaefc09ef371bd9d71`). Confirm weight redistribution rights before including any model bytes in an open-source release.

The bundled runtime files retained in Git come from the MIT-licensed `onnxruntime-web` 1.27.0 package. Other downloaded runtime variants remain ignored because the current WASM route does not use them.

## Historical direct-load diagnostic

`spike.html` records the earlier direct `file://` loading attempt. It failed in Edge because the runtime's dynamic module import was blocked. The failure and its replacement architecture are recorded in `docs/browser-inference-plan.md`; the folder-selection route is the active one.

Sources: https://github.com/darsa-group/flat-bug/ and https://onnxruntime.ai/docs/get-started/with-javascript/web.html
