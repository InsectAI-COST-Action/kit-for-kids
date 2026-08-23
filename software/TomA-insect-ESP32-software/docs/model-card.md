# Production model card and candidate record

No production model is approved. Do not replace `NullInferenceEngine` or present predictions as observations until the applicable form is complete and approved.

## Preferred candidate for feasibility testing: FlatBug

FlatBug is the project owner's preferred first candidate because it is an established general insect/arthropod detection and segmentation system. Its published implementation combines YOLOv8 models with multi-scale/pyramid tiling intended for large images. The software repository is MIT licensed, but model-weight, training-data, transitive-dependency, and distribution compatibility still require an explicit review.

FlatBug is not yet selected as the production model. The official workflow assumes Python 3.11+, PyTorch and a consumer NVIDIA GPU; its published guidance recommends more than 2 GB VRAM for the smallest model and more than 12 GB for the largest. That makes direct offline-browser use uncertain and rules out assuming that the reference pipeline will fit unchanged.

Official sources:

- Project overview: https://asgersvenning.com/flat-bug/
- Source and licence: https://github.com/darsa-group/flat-bug/

Before adoption, the feasibility spike must:

- obtain the smallest relevant official weight and record its exact version, hash, licence, byte size, parameters, input size, labels, and task;
- determine whether its core model exports correctly to ONNX and whether browser outputs match the reference Python outputs on fixed images;
- determine how much accuracy is lost if FlatBug's custom pyramid/tiling and merging pipeline is simplified or omitted;
- measure initial load time, first-result time, median/p95 per-image time, total session time, peak memory, and UI responsiveness with WebAssembly and optional WebGPU;
- test quantisation or a smaller derivative only as a separately identified model;
- validate on representative images from the actual enclosure, including empty images, people, reflections, blur, partial insects, and non-insect confounders; and
- record the decision: adopt, adapt/distil, or reject. If rejected for size or speed, evaluate a smaller one-class detector without silently calling it FlatBug.


## Current browser prototype record (not approval)

The dashboard contains a local, child-facing feasibility prototype. It does not change the firmware's `NullInferenceEngine`, write predictions to the card, or establish a production model.

- Candidate: FlatBug v1.0.0 Nano (`flat_bug_N.pt` exported locally to ONNX).
- Browser artefact: `flatbug-n.onnx`, 11,906,627 bytes, SHA-256 `ec75aeb85b42c86663b006f650681a2d5728d89cff096deaefc09ef371bd9d71`.
- Runtime: ONNX Runtime Web 1.27.0 WebAssembly, one thread, no WebGPU requirement.
- Input route: one 640x640 letterboxed RGB pass per selected image, score threshold 0.20, IoU suppression threshold 0.20, no minimum-box-size filter (small candidates are retained).
- Offline packaging: the adult selects the top camera-card folder once. The package resides locally under `ai/`; images and model assets are read as browser File objects. This avoids the `file://` canvas-read restriction encountered when loading image paths directly.
- Browser evidence: the isolated File-object loader and the child dashboard prototype have been exercised in Chrome and Edge. The user reported Nano as suitably fast on individual test images. Firefox and Safari remain untested.
- Sanity evidence only: a supplied bee image yielded a high raw Nano score (about 0.89); a supplied empty camera image yielded a low raw score (about 0.09); synthetic beetle, cricket, and moth fixtures yielded high raw scores. These are technical checks, not accuracy validation.

The reference FlatBug package's multi-scale tiled/pyramid workflow is **not** reproduced. This prototype uses a single pass, so it must never be described as equivalent to reference FlatBug detection or as validated insect identification.

## Approval template

- Model name, version, hash, source, and licence:
- Task: classification, object detection, or segmentation:
- Class/label map and plain-language labels:
- Input width, height, colour order, normalisation, and JPEG/RGB conversion path:
- Output tensor/decode rules, confidence threshold, and NMS rules:
- Runtime, model format, browser/runtime versions, and offline packaging method:
- Model and runtime bytes on the SD card; measured peak browser memory:
- Measured load, first-result, average/p95/worst inference, and full-session times on reference computers:
- Chrome, Edge, Firefox, and Safari results on required Windows/macOS versions:
- Comparison with reference-framework outputs and any tiling/quantisation accuracy change:
- Validation data, representative enclosure conditions, empty-frame/confounder results:
- Known failure modes and prohibited claims:
- Privacy/retention implications:
- Approval date and owner:

## AntAI - Beta record (experimental; not approval)

AntAI - Beta is a separate one-class YOLO26 Nano detector trained locally from the updated Roboflow export. It is an evaluation aid, not a production model and must never be presented as a confirmed ant count or identification.

- Task and class: object detection, one class (`ant`). Source labels `ant` and `ants` were intentionally merged.
- Training evidence: 34 images / 468 boxes fit; 10 images / 147 boxes validation; 5 images / 58 boxes held-out test. All originate from the current camera domain, but this is far too little and too homogeneous for a reliable performance claim.
- Training: YOLO26 Nano, 1024x1024 letterbox RGB, 40 requested CPU epochs with early stopping at epoch 23; held-out test precision 0.530, recall 0.721, mAP50 0.632, mAP50-95 0.273. These figures are unstable because the test set has only five images.
- Browser artefact: `antai-beta.onnx`, 10,019,578 bytes, SHA-256 `be6e8f10971385e9fad5b72e7e7e02ab17d969f7014793d213d37115a73681e0`. ONNX input `images` is `[1,3,1024,1024]`; output `output0` is end-to-end `[1,300,6]` x1/y1/x2/y2/score/class candidates.
- Runtime and packaging: the existing offline ONNX Runtime Web WebAssembly package, one thread, read-only top-card-folder picker. Install with `py tools\install_ai_pack.py D:\ --include-antai-beta`.
- Dashboard behaviour: selectable as **AntAI - Beta** (whole-picture only, threshold 0.15) beside **FlatBug - Quick look** and **FlatBug - Look closely** (threshold 0.20); only FlatBug offers the 4x3 tiled search. IoU suppression is 0.20. The user selects one available run/session, so analyses do not mix experiments.
- Known limitations: no independent experiment/session split, no empty-frame evaluation, no cross-browser timing evidence, no tracking, and no validation beyond five held-out annotated images.
