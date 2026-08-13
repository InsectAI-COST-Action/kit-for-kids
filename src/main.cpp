#include <Arduino.h>

#include <esp_heap_caps.h>

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
constexpr uint32_t kPerformanceSampleInterval = 100;

struct CaptureTiming {
  uint32_t scheduled_ms = 0;
  uint32_t start_lag_ms = 0;
  uint32_t capture_ms = 0;
  uint32_t image_write_ms = 0;
  uint32_t logger_ms = 0;
  uint32_t total_ms = 0;
  size_t jpeg_bytes = 0;
  String outcome;
};

String performance_path;

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

void ensurePerformanceLog() {
  if (performance_path.isEmpty()) return;
  if (storage.exists(performance_path)) return;
  String diagnostic;
  const String header =
      "capture_id,scheduled_ms,start_lag_ms,capture_ms,image_write_ms,logger_ms,total_ms,jpeg_bytes," \
      "outcome,free_heap,largest_free_heap,min_free_heap,free_psram,largest_free_psram";
  if (!storage.appendLine(performance_path, header, diagnostic)) {
    report("performance log unavailable: " + diagnostic);
  }
}

void writePerformanceSample(const String& capture_id, const CaptureTiming& timing) {
  if (logger.captureCount() % kPerformanceSampleInterval != 0) return;
  const uint32_t free_heap = ESP.getFreeHeap();
  const uint32_t largest_free_heap = heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
  const uint32_t min_free_heap = ESP.getMinFreeHeap();
  const uint32_t free_psram = ESP.getFreePsram();
  const uint32_t largest_free_psram = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
  const String line = capture_id + "," + String(timing.scheduled_ms) + "," +
      String(timing.start_lag_ms) + "," + String(timing.capture_ms) + "," +
      String(timing.image_write_ms) + "," + String(timing.logger_ms) + "," +
      String(timing.total_ms) + "," + String(static_cast<unsigned long>(timing.jpeg_bytes)) + "," +
      timing.outcome + "," + String(free_heap) + "," + String(largest_free_heap) + "," +
      String(min_free_heap) + "," + String(free_psram) + "," + String(largest_free_psram);
  String diagnostic;
  if (!storage.appendLine(performance_path, line, diagnostic)) {
    report("performance sample write failed: " + diagnostic);
  }
  report("performance sample " + line);
}

CaptureTiming captureOnce(uint32_t scheduled_ms) {
  CaptureTiming timing;
  timing.scheduled_ms = scheduled_ms;
  const String capture_id = logger.nextCaptureId();
  String diagnostic;
  const uint32_t total_started = millis();
  timing.start_lag_ms = total_started - scheduled_ms;
  const uint32_t capture_started = millis();
  camera_fb_t* frame = camera.capture(diagnostic);
  if (frame == nullptr) {
    report(diagnostic);
    recordCaptureFailure(capture_id, scheduled_ms, "camera_frame_unavailable");
    timing.capture_ms = millis() - capture_started;
    timing.total_ms = millis() - total_started;
    timing.outcome = "capture_error";
    writePerformanceSample(capture_id, timing);
    return timing;
  }

  CaptureRecord record;
  record.capture_id = capture_id;
  record.uptime_ms = millis();
  record.scheduled_ms = scheduled_ms;
  record.width = frame->width;
  record.height = frame->height;
  record.jpeg_bytes = frame->len;
  record.capture_ms = millis() - capture_started;
  timing.capture_ms = record.capture_ms;
  timing.jpeg_bytes = frame->len;
  record.inference = inference.run(*frame);
  record.image_path = imagePathFor(capture_id);
  record.outcome = "completed";
  record.save_outcome = "saved";

  const uint32_t image_write_started = millis();
  const bool image_saved = storage.writeBinaryAtomicCreate(record.image_path, frame->buf, frame->len, diagnostic);
  timing.image_write_ms = millis() - image_write_started;
  camera.release(frame);
  if (!image_saved) {
    record.outcome = "storage_error";
    record.save_outcome = "failed";
    record.image_path = "";
    record.error_code = "image_write_failed";
    report(diagnostic);
  }
  const uint32_t logger_started = millis();
  if (!logger.recordCapture(record, diagnostic)) report("capture log failure: " + diagnostic);
  timing.logger_ms = millis() - logger_started;
  timing.total_ms = millis() - total_started;
  timing.outcome = record.outcome;
  writePerformanceSample(capture_id, timing);
  return timing;
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

  performance_path = "/system/performance_" + logger.runId() + ".csv";
  ensurePerformanceLog();
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
