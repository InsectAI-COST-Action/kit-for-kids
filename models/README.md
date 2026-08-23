# Models

Detection models are currently provided in three formats for testing, [YOLO26](https://github.com/ultralytics/yolo26) as the base format for conversion, [ONNX](https://github.com/onnx/onnx) for browser-based [dashboard](software/TomA-insect-ESP32-software) inference, and [ESPDet-Pico](https://github.com/espressif/esp-detection) for edge deployment on an ESP32-S3. Models are named based upon their corresponding training dataset to ensure reproducibility enable retraining with additional architectures.

## Usage

### YOLO26

```bash
yolo predict model=AntTest.pt source="path/to/video.mp4"
```

### ONNX

```bash
yolo predict model=AntTest.onnx source="path/to/video.mp4"
```

### ESPDet-Pico

Clone repository.

```bash
git clone https://github.com/InsectAI-COST-Action/kit-for-kids.git
```

Create and activate virtual environment.

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

Install required packages.

```bash
python -m pip install -r requirements.txt
```

Run script to flash model to ESP32-S3.

```bash
python flash.py
```
