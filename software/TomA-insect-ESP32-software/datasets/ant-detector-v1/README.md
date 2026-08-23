# Ant detector dataset v1

Source: `run_000008` from the camera card, QXGA 2048?1536 JPEGs.

| Split | Images | Purpose |
| --- | ---: | --- |
| Train | 2484 | Active-learning pool and model fitting |
| Validation | 532 | Development tuning only |
| Test | 533 | Final untouched evaluation |
| Boundary gaps | 30 | Intentionally excluded to separate adjacent time sequences |

Images are deliberately ignored by Git. `metadata/split_manifest.csv`, this readme,
`dataset.yaml`, and future YOLO labels are version-controlled.

## Annotation rules

- Use one class only: `ant` (class `0`). Draw a tight box around every visible ant.
- Label all visible ants in an image, including small or partly occluded ants when they
  can reasonably be recognised. Do not create a box for ambiguous dark debris.
- Empty images are valuable negatives: leave their matching label file absent or empty.
- Use images from **train** for active-learning rounds. Do not use validation or test
  images to decide architecture, confidence thresholds, tiling settings, or stopping.
- Keep the test split untouched until the detector and settings are frozen.

The split is chronological with 15-frame buffers at each split boundary. This prevents
nearly adjacent 1-FPS frames from appearing in both training and evaluation data.
## Seed annotations

A full Roboflow COCO UI export supplied 37 full-QXGA images and 492 reviewed ant boxes. They were mapped back to the local **training** pool and converted to one-class YOLO labels in `labels/train/`; import provenance is recorded in `metadata/roboflow_import_vui-2026-08-18.*`. This supersedes the incomplete 15-image API version-1 export. Roboflow?s internal `ant`/`ants` categories are both normalised to local class `0` (`ant`).
