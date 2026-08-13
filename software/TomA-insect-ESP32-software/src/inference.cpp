#include "inference.h"

const char* inferenceOutcomeName(InferenceOutcome outcome) {
  switch (outcome) {
    case InferenceOutcome::Ok: return "ok";
    case InferenceOutcome::ModelUnavailable: return "model_unavailable";
    case InferenceOutcome::InvalidInput: return "invalid_input";
    case InferenceOutcome::RuntimeError: return "runtime_error";
    case InferenceOutcome::Timeout: return "timeout";
  }
  return "unknown";
}

bool NullInferenceEngine::begin(String& diagnostic) {
  diagnostic = "no production model configured; null inference active";
  return true;
}

InferenceResult NullInferenceEngine::run(const camera_fb_t& frame) {
  InferenceResult result;
  result.model_id = "none";
  if (frame.buf == nullptr || frame.len == 0) {
    result.outcome = InferenceOutcome::InvalidInput;
    return result;
  }
  result.outcome = InferenceOutcome::ModelUnavailable;
  return result;
}
