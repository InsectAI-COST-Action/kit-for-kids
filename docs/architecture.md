# Architecture

The main loop targets one camera frame every 500 ms, passes it to the inference interface, writes the original JPEG, appends an authoritative capture CSV row, and returns the frame buffer on every outcome path. Actual 2-FPS acceptance remains pending validation of the performance timer.

`CameraService` owns `esp_camera`; `SdStorage` owns the SD filesystem; `SessionLogger` owns IDs, CSV rows, and run manifests; `DashboardWriter` owns only derived JavaScript chunks and summaries; and `IInferenceEngine` hides model-specific code. No module other than `CameraService` can call `esp_camera_fb_get`.

Raw CSV is authoritative. JPEGs are atomically written beneath `/images/<run>/shard_<nnnn>/`, with a new shard every 100 captures to bound FAT directory growth. Dashboard chunks are immutable after promotion from `.part` to `.js`; `manifest.js` lists only promoted chunks. An interrupted partial chunk is deliberately unreferenced, so it cannot break `dashboard.html`.
