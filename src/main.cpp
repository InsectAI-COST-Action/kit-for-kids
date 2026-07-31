#include <Arduino.h>

#include "app_config.h"
#include "camera_service.h"
#include "inference.h"
#include "sd_storage.h"
#include "session_logger.h"

namespace {
AppConfig config;
SdStorage storage;
CameraService camera;
NullInferenceEngine inference;
SessionLogger logger;

bool ready = false;
bool finished = false;
uint32_t next_capture_due_ms = 0;
uint32_t session_started_ms = 0;

void report(const String& message) {
  Serial.println("[insect-logger] " + message);
}

String imagePathFor(const String& capture_id) {
  return "/images/" + logger.runId() + "/" + capture_id + ".jpg";
}

void recordCaptureFailure(const String& capture_id, uint32_t scheduled_ms, const String& error_code) {
  CaptureRecord record;
  record.capture_id = capture_id;
  record.uptime_ms = millis();
  record.scheduled_ms = scheduled_ms;
  record.outcome = "capture_error";
  record.save_outcome = "not_attempted";
  record.error_code = error_code;
  String diagnostic;
  if (!logger.recordCapture(record, diagnostic)) report("failed to log capture error: " + diagnostic);
}

void captureOnce(uint32_t scheduled_ms) {
  const String capture_id = logger.nextCaptureId();
  String diagnostic;
  const uint32_t capture_started = millis();
  camera_fb_t* frame = camera.capture(diagnostic);
  if (frame == nullptr) {
    report(diagnostic);
    recordCaptureFailure(capture_id, scheduled_ms, "camera_frame_unavailable");
    return;
  }

  CaptureRecord record;
  record.capture_id = capture_id;
  record.uptime_ms = millis();
  record.scheduled_ms = scheduled_ms;
  record.width = frame->width;
  record.height = frame->height;
  record.jpeg_bytes = frame->len;
  record.capture_ms = millis() - capture_started;
  record.inference = inference.run(*frame);
  record.image_path = imagePathFor(capture_id);
  record.outcome = "completed";
  record.save_outcome = "saved";

  const bool image_saved = storage.writeBinaryAtomic(record.image_path, frame->buf, frame->len, diagnostic);
  camera.release(frame);
  if (!image_saved) {
    record.outcome = "storage_error";
    record.save_outcome = "failed";
    record.image_path = "";
    record.error_code = "image_write_failed";
    report(diagnostic);
  }
  if (!logger.recordCapture(record, diagnostic)) report("capture log failure: " + diagnostic);
}

void finishSession() {
  if (finished) return;
  String diagnostic;
  if (!logger.finish(diagnostic)) {
    report("session finalisation failed: " + diagnostic);
  } else {
    report("session complete; power off before removing SD card");
  }
  finished = true;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(250);
  report(String("firmware ") + INSECT_LOGGER_FIRMWARE_VERSION + " starting");

  String diagnostic;
  if (!storage.begin(diagnostic)) {
    report("fatal storage failure: " + diagnostic);
    return;
  }
  config = ConfigLoader::defaults();
  if (!ConfigLoader::load(storage.fs(), config, diagnostic)) {
    report("fatal configuration failure: " + diagnostic);
    return;
  }
  report(diagnostic);
  if (!camera.begin(config, diagnostic)) {
    report("fatal camera failure: " + diagnostic);
    return;
  }
  report(diagnostic);
  if (!inference.begin(diagnostic)) {
    report("fatal inference setup failure: " + diagnostic);
    return;
  }
  report(diagnostic);
  if (!logger.begin(storage, config, camera.sensorId(), diagnostic)) {
    report("fatal session setup failure: " + diagnostic);
    return;
  }
  report(diagnostic);

  session_started_ms = millis();
  next_capture_due_ms = session_started_ms;
  ready = true;
}

void loop() {
  if (!ready || finished) {
    delay(100);
    return;
  }
  const uint32_t now = millis();
  if (now - session_started_ms >= config.max_session_seconds * 1000UL) {
    finishSession();
    return;
  }
  if (static_cast<int32_t>(now - next_capture_due_ms) < 0) {
    delay(5);
    return;
  }

  const uint32_t scheduled_ms = next_capture_due_ms;
  next_capture_due_ms += 1000UL / config.capture_fps;
  if (static_cast<int32_t>(now - next_capture_due_ms) >= 0) {
    report("capture cadence overrun; schedule rebased without backlog");
    next_capture_due_ms = now + 1000UL / config.capture_fps;
  }
  captureOnce(scheduled_ms);
}
