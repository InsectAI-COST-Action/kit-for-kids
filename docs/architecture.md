# Architecture

By default, the main loop targets one QXGA/JPEG-quality-12 frame every 1,000 ms, passes it to the inference interface, writes the original JPEG, appends an authoritative capture CSV row, and returns the frame buffer on every outcome path. The optional experimental motion policy waits five seconds after boot, retains its first full JPEG, then captures 160 x 120 grayscale previews on each scheduled attempt. It subtracts global brightness drift, scores the strongest of 8 x 6 tiles, and retains a full configured JPEG only at score 5 or higher; every preview still receives an authoritative CSV row. During the browser-inference feasibility phase, the on-device interface remains the null adapter and records `model_unavailable`; it must not delay capture. A complete one-hour QXGA/1-FPS endurance acceptance run remains pending.

`CameraService` owns `esp_camera`; `SdStorage` owns the SD filesystem; `SessionLogger` owns IDs, CSV rows, and run manifests; `DashboardWriter` owns only derived JavaScript chunks and summaries; and `IInferenceEngine` hides model-specific code. No module other than `CameraService` can call `esp_camera_fb_get`.

Raw CSV is authoritative. JPEGs are atomically written beneath `/images/<run>/shard_<nnnn>/`, with a new shard every 100 captures to bound FAT directory growth. Dashboard chunks are immutable after promotion from `.part` to `.js`; `manifest.js` lists only promoted chunks. An interrupted partial chunk is deliberately unreferenced, so it cannot break `dashboard.html`.

## Provisional inference split

The next technical spike moves production-model execution out of the ESP32 capture loop and into the offline dashboard after the SD card is inserted into a computer. This is a provisional architecture, not an accepted model implementation:

1. The ESP32 captures and safely stores every frame at the configured cadence.
2. The dashboard loads the session without starting inference, so the user can explore the pictures immediately.
3. A large, explicit child-friendly action starts local analysis of retained images.
4. A locally bundled browser runtime and model process images without network access. The UI reports progress, remains cancellable and responsive, and makes model uncertainty clear.
5. Results use the existing versioned prediction contract where possible. The first portable implementation may offer a download rather than write back to the SD card, because cross-browser local-file write access is not assumed.

ONNX Runtime Web with WebAssembly is the baseline runtime to test across Chrome, Edge, Firefox, and Safari. WebGPU may be an optional acceleration path where supported, but must not be required. `file://` loading of the model, WebAssembly assets, workers, and image files must be proven in the full browser matrix before this architecture is accepted. See `docs/browser-inference-plan.md`.
