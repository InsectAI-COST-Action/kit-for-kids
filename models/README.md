# Models

Detection models are currently provided in three formats for testing, [YOLO26](https://github.com/ultralytics/yolo26) as the base format for conversion, [ONNX](https://github.com/onnx/onnx) for browser-based [dashboard](software/TomA-insect-ESP32-software) inference, and [ESPDet-Pico](https://github.com/espressif/esp-detection) for edge deployment on an ESP32-S3. Models are named based upon their corresponding training [dataset](https://github.com/InsectAI-COST-Action/kit-for-kids/tree/main/datasets/) to ensure reproducibility and enable retraining with additional architectures.

## Installation

For simplicity, the YOLO26 and ONNX models can be tested through the standard Ultralytics CLI, however the ESPDet-Pico model must be deployed to an ESP32-S3 via the [deploy](/models/deploy) pipeline. These frameworks are provided for testing rather than integration, and thus should primarily be used for model evaluation. A [test video](/models/test) is provided for this purpose, however additional videos can be uploaded for further validation.

## Usage

### YOLO26

Install Ultralytics.

```bash
python -m pip install ultralytics
```

Run inference on the test video.

```bash
yolo predict model=AntTest.pt source="/models/test/AntTest.mp4"
```

### ONNX

Install Ultralytics.

```bash
python -m pip install ultralytics
```

Run inference on the test video.

```bash
yolo predict model=AntTest.onnx source="/models/test/AntTest.mp4"
```

### ESPDet-Pico

Clone repository.

```bash
git clone https://github.com/InsectAI-COST-Action/kit-for-kids.git
```

Create and activate virtual environment.

```bash
cd kit-for-kids\models\deploy
python -m venv .venv
.\.venv\Scripts\activate
```

Install required packages.

```bash
python -m pip install -r requirements.txt
```

Run script to flash model to ESP32-S3, specifying the port via the `--port` argument.

```bash
python flash.py --port COM4
```
