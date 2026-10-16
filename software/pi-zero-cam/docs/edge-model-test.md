# Edge detection on the Pi Zero 2 W: model test, 15 October 2026

Question: can the ant detector that ships with the dashboard run on the camera itself, and is it any good on the Pi's own photos? Scripts: `tools/edge_bench.py` (harness), `tools/edge_models.py` (export, 8-bit quantisation). Models are not committed (size, and the licence note below).

## What upstream has

`models/` in the kit-for-kids repository (Thomas O'Shea-Wheller, 24 August - 18 September 2026) holds one model, `AntTestModel`: a **YOLO26n, one class ("Ant"), 640 x 640**, trained 23 August 2026 on the Roboflow dataset `ant-test-project` v18 (CC BY 4.0; 879 train, 12 validation, 13 test images - mostly small ants in video frames). It exists as PyTorch weights (`YOLO26/AntModelTest.pt`), ONNX (`ONNX/AntTestModel.onnx`, **byte-identical to the dashboard's `antai-test.onnx`**), and an ESPDet-Pico `.espdl` plus a complete prebuilt ESP32-S3 firmware (`deploy/`, which replaces the logger firmware) for a XIAO. The ONNX is FP16-weight, output `[1, 5, 8400]` (centre x/y, w, h, score; no NMS). The Ultralytics export metadata says AGPL-3.0 - the weights' licence needs a decision from the model owner before shipping; the camera code here uses onnxruntime (MIT) with its own pre- and post-processing and no Ultralytics code.

## Speed and memory on the Pi Zero 2 W (4 threads, onnxruntime 1.31, median of 8-10 runs)

| Model | Input | Size | Inference | Peak RSS | Notes |
|---|---|---|---|---|---|
| provided (FP16 weights) | 640 | 5.0 MB | 906 ms | 179 MB | |
| FP32 | 640 | 9.8 MB | 874 ms | 163 MB | FP32 is no faster than the FP16-weight file |
| FP32 | 480 | 9.7 MB | 511 ms | 128 MB | |
| FP32 | 320 | 9.7 MB | 234 ms | 98 MB | |
| **int8 (head in float)** | **480** | **3.3 MB** | **313 ms** | **99 MB** | |
| int8 (head in float) | 320 | 3.3 MB | 149 ms | 87 MB | |

Provided model by thread count: 1 thread 2,495 ms, 2 threads 1,374 ms, 4 threads 913 ms. Preprocessing a full 2304x1296 photo costs 60-100 ms; the camera's own 640x360 low-resolution stream makes that ~10 ms (plus ~90-150 ms to convert its YUV to RGB in numpy, which a smarter conversion would cut).

## Accuracy on the 25 labelled images (test + validation sets, confidence 0.25, IoU 0.5)

| Model | Precision | Recall | AP50 |
|---|---|---|---|
| provided 640 | 0.965 | 0.990 | 0.989 |
| FP32 640 | 0.905 | 0.990 | 0.992 |
| FP32 480 | 0.914 | 0.990 | 0.992 |
| FP32 320 | 0.940 | 0.891 | 0.937 |
| int8 480 | 0.941 | 0.984 | 0.989 |
| int8 320 | 0.904 | 0.829 | 0.861 |

Caveat: these 25 frames come from the same videos as the training frames, so the scores are optimistic. **int8 at 480 loses nothing** and is the best speed/accuracy point; 320 loses 10-17% recall.

Quantising the whole network (including the detection head) produced all-zero scores; the head (`/model.23`, 93 nodes) has to stay float. The re-exports are end-to-end (`[1, 300, 6]`, no NMS needed), which `edge_bench.py` reads as well as the provided layout.

## On the Pi's own photos: **not usable as it stands**

Photos from the Pi camera (runs 12-17, an ant picture, soil crumbs, a CD, an empty room), 2304x1296:

| Photo | Provided 640 | int8 480 | What is really there |
|---|---|---|---|
| empty room, tubes of paint | 36 | 6 | no ant |
| plain floor | 2 | 1 | no ant |
| three real ants on white paper, soil, sugar | 76 | 52 | 3 ants |
| printed ant, CD, soil (4 photos) | 37-53 | 37-43 | 1 ant picture |

The models detect **dark specks**: crumbs, black shapes on the CD, and the head, thorax and abdomen of a large ant as separate boxes, never one box per ant. The training images have tiny ants (dozens per frame); here an ant fills a tenth of the frame. It scored 0.99 on its own kind of image and is unreliable outside it. Fixing this needs training data from the Pi camera at the real working distance, or a different approach to scale (tiling, a size filter), not a different runtime.

## Sustained load on the Pi

5 minutes with one detection per second (int8 480, 3 threads, from a 640x360 frame) **and** normal capture at 1 photo per second together: detection median 410 ms (p95 414, max 443), processor 48 -> 58 C and flat, never throttled; capture 300 photos, interval mean 999 ms, max 1,098 ms, none over 1.5 s (per-photo work rose from ~140 ms to ~440 ms from CPU sharing). Detection every second alongside capture is sustainable; running it only on photos that motion mode keeps would cost far less.

## FlatBug Nano as the dashboard runs it (16 October 2026)

`tools/flatbug_bench.py` reproduces the dashboard's two FlatBug modes (640 input, grey padding, score 0.20, overlap suppression 0.20): **Quick look** = whole picture in one pass; **Look closely** = 4 x 3 grid of 640 x 640 pieces cut from the full-size picture (12 passes for a 2304 x 1296 photo; a picture no larger than 640 would be one piece). Pi Zero 2 W, onnxruntime 1.31, 4 threads, 11.9 MB model (FP16 weights, 37-channel output incl. 32 mask coefficients; all outputs computed, as in the dashboard), peak memory 184 MB. The service was stopped for the run.

| | AntTestModel int8 480 | FlatBug Nano, Quick look | FlatBug Nano, Look closely |
|---|---|---|---|
| One pass on the Pi | 313 ms | 1,495 ms | 1,495-1,570 ms |
| One 2304 x 1296 photo | ~400 ms (with preprocessing) | **1.7 s** | **19.3-19.5 s** (12 passes) |
| 25 labelled ant frames, recall / precision (ant model at 0.25, FlatBug at its 0.20) | 0.98 / 0.94 | **0 / n/a** (0 boxes) | **0.005 / 0.10** (1 of 193 ants; 9 wrong boxes) |
| Pi photo with 4 ants (run 12, img 150) | dozens of boxes on specks | **5 boxes: all 4 ants + 1 soil clump** | **5 boxes: all 4 ants (one ant split in two) - 1 duplicate** |

- **Speed:** FlatBug Nano is ~5x slower per pass than our int8 ant model (it is bigger, 640 input, not quantised, and computes mask outputs we do not use). Look closely costs 12 passes: ~19 s per photo, and the processor went from 42 C to 80 C with frequency capping (0x20000) during the run, so it is not sustainable at 1 photo per second, nor usable for live view. Quick look at ~1.7 s per photo would run at about one photo every 2 s.
- **Accuracy on the labelled frames:** the 25 frames (800 x 600 to 2048 x 1536) hold dozens of ants a few pixels wide. In the whole-picture pass the model scores them <= 0.02 (nothing at 0.20); the 12-piece pass finds 1 of 193. These ants are far below the scale FlatBug works at, so this is a poor test of FlatBug and says nothing about larger ants.
- **On the Pi's own photos it is much better than the placeholder:** on the photo with four ants (each ~1/10 of the frame) Quick look boxes all four plus one soil clump, one pass. Look closely adds nothing here except a split ant. One photo is anecdotal; it needs a labelled set from the Pi camera.
- Timings are native onnxruntime on the Pi; the dashboard runs the same model in the browser (WebAssembly) on the user's computer.

## Built into the camera (15 October 2026)

- **Runtime:** Debian's `python3-onnxruntime` 1.21 dies with "Illegal instruction" on the Pi Zero 2 W (Cortex-A53, no asimddp). `pi/install.sh` therefore installs the benchmarked PyPI wheels (onnxruntime 1.31.0 and its three needed dependencies, hash-pinned in `pi/requirements-edge.txt`) into `/opt/insectcam/venv`, which also sees the apt packages (picamera2, numpy, Pillow); the service runs from that venv.
- **Model:** `.onnx` files are copied from a gitignored `models/` folder to `/opt/insectcam/models/` (never committed). Input size and class names come from the file's metadata, so a retrained model drops in. Everything the placeholder produces is labelled: a "PLACEHOLDER MODEL - boxes are not reliable" banner burned into live frames, `model_status: placeholder_unvalidated` and the model's SHA-256 in each run manifest and in `detections.csv` metadata.
- **Recording (opt-in, off by default):** the "Ant detection (experimental)" switch in the phone app's settings sets `model_id` in `config.json`; each saved photo is then run through the detector and the real `inference_ms`, `prediction_count`, `max_confidence` and one `raw/detections.csv` row per box are written. It never changes whether a photo is saved. 5 minutes at 1 photo per second with it on: 300 photos, interval mean 999 ms, max 1,370 ms, none over 1.5 s, inference 416 ms mean (607 max), processor peak 60.7 C, never throttled. The scene was dark, so this run wrote no detection rows; rows from a lit scene are still to be checked.
- **Live view:** the phone fetches one annotated JPEG per request (long-poll), because Edge 155 does not render `multipart/x-mixed-replace` in an `<img>`. 640x360 frames, shown only after detection; two viewers at most, ten minutes per viewing. Stages are pipelined (next frame grabbed and converted while the current one is in the detector): 1.86 -> 2.24 frames per second with capture running at the same time (median gap 419 ms against 403 ms of inference).
- **Power cut with recording on** found a data-safety bug unrelated to the model: Linux FAT writes a renamed file's directory entry with size 0 until the next inode writeback (up to ~30 s), so `echo b > /proc/sysrq-trigger` mid-capture left 33 of 36 photos as zero-length files (the earlier power-cut check counted files, not whether they opened). Fixed by fsyncing each file again under its final name; the same test afterwards: 38 of 38 photos readable, 38 capture rows, no `.tmp` files.

## Not done

- **Live test of the camera's own view with an ant under it:** the room light was off, so the frame was black (lux 0.1, mean pixel 1.6). Stand-in: earlier saved photos.
- Detection rows from a lit scene in `raw/detections.csv`, the Windows audit and the dashboard's reading of placeholder rows; live view on a phone.
