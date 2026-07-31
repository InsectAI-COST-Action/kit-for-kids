# Architecture

The main loop owns session timing. It takes one camera frame every 500 ms, passes it to the inference interface, writes the original JPEG, appends an authoritative capture CSV row, and returns the frame buffer on every outcome path.

`CameraService` owns `esp_camera`; `SdStorage` owns the SD filesystem; `SessionLogger` owns IDs, CSV rows, and run manifests; `DashboardWriter` owns only derived JavaScript chunks and summaries; and `IInferenceEngine` hides model-specific code. No module other than `CameraService` can call `esp_camera_fb_get`.

Raw CSV is authoritative. Dashboard chunks are immutable after promotion from `.part` to `.js`; `manifest.js` lists only promoted chunks. An interrupted partial chunk is deliberately unreferenced, so it cannot break `dashboard.html`.
