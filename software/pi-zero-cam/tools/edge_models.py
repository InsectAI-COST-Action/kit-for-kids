"""Make faster variants of the ant detector for the Pi (run on a PC, not on the Pi).

  py tools\edge_models.py export   --weights models\YOLO26\AntModelTest.pt --out OUT_DIR
  py tools\edge_models.py quantize --models OUT_DIR --train datasets\AntTestModel\train\images

export:   PyTorch weights -> FP32 ONNX at input sizes 640, 480 and 320 (Ultralytics export; its
          YOLO26 default is end-to-end, output [1,300,6], no NMS needed). Needs `pip install ultralytics`.
          Ultralytics is AGPL-3.0: it is a build-time tool here and the camera runs the ONNX files with
          onnxruntime (MIT). The exported models still carry the weights' own licence question (see
          docs/edge-model-test.md).
quantize: FP32 ONNX at 480 and 320 -> 8-bit (static QDQ, per-channel int8 weights, uint8 activations,
          80 calibration images from the training set). The detection head (/model.23, 93 nodes) is
          left in float: quantising it collapsed every score to 0 (15 October 2026).

Evaluate any result with tools/edge_bench.py. Needs onnx and onnxruntime for `quantize`.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

SIZES_EXPORT = (640, 480, 320)
SIZES_QUANTIZE = (480, 320)
CALIBRATION_IMAGES = 80
HEAD_PREFIX = "/model.23"


def export(weights: Path, out: Path) -> None:
    from ultralytics import YOLO
    out.mkdir(parents=True, exist_ok=True)
    for size in SIZES_EXPORT:
        produced = YOLO(str(weights)).export(format="onnx", imgsz=size, opset=17, simplify=True, half=False,
                                              dynamic=False, nms=False, batch=1)
        target = out / f"fp32_{size}.onnx"
        shutil.move(produced, target)
        print(f"exported {target} ({target.stat().st_size} bytes)")


def quantize(models: Path, train_images: Path) -> None:
    import onnx
    from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from edge_bench import letterbox

    images = sorted(train_images.glob("*.jpg"))
    random.Random(3).shuffle(images)
    images = images[:CALIBRATION_IMAGES]

    class Reader(CalibrationDataReader):
        def __init__(self, size: int) -> None:
            self.size, self.paths = size, iter(images)

        def get_next(self):
            path = next(self.paths, None)
            return None if path is None else {"images": letterbox(Image.open(path).convert("RGB"), self.size)[0]}

    for size in SIZES_QUANTIZE:
        source, target = models / f"fp32_{size}.onnx", models / f"int8_{size}.onnx"
        head = [n.name for n in onnx.load(str(source)).graph.node if n.name.startswith(HEAD_PREFIX)]
        quantize_static(str(source), str(target), Reader(size), quant_format=QuantFormat.QDQ, per_channel=True,
                        weight_type=QuantType.QInt8, activation_type=QuantType.QUInt8, nodes_to_exclude=head)
        print(f"quantised {target} ({target.stat().st_size} bytes, {len(head)} head nodes kept in float)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export")
    e.add_argument("--weights", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    q = sub.add_parser("quantize")
    q.add_argument("--models", type=Path, required=True)
    q.add_argument("--train", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        export(args.weights, args.out)
    else:
        quantize(args.models, args.train)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
