#pragma once

#include <Arduino.h>
#include <esp_camera.h>

enum class InferenceOutcome {
  Ok,
  ModelUnavailable,
  InvalidInput,
  RuntimeError,
  Timeout,
};

struct InferenceResult {
  InferenceOutcome outcome = InferenceOutcome::ModelUnavailable;
  uint32_t elapsed_ms = 0;
  uint8_t prediction_count = 0;
  float max_confidence = 0.0F;
  String model_id = "none";
};

const char* inferenceOutcomeName(InferenceOutcome outcome);

class IInferenceEngine {
 public:
  virtual ~IInferenceEngine() = default;
  virtual bool begin(String& diagnostic) = 0;
  virtual InferenceResult run(const camera_fb_t& frame) = 0;
};

class NullInferenceEngine final : public IInferenceEngine {
 public:
  bool begin(String& diagnostic) override;
  InferenceResult run(const camera_fb_t& frame) override;
};
