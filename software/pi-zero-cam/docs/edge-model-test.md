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

## Not done

- **Live test of the camera's own view with an ant under it:** the room light was off, so the frame was black (lux 0.1, mean pixel 1.6). Stand-in: earlier saved photos.
- onnxruntime from Debian (`python3-onnxruntime`, 1.21) instead of the PyPI wheel; accuracy and speed there are unmeasured.
- Detections are not yet written anywhere (`raw/detections.csv` stays header-only); no `insectcam` integration.
