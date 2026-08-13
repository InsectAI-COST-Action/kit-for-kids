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
