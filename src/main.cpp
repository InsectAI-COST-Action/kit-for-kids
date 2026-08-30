#include <Arduino.h>
#include <esp_heap_caps.h>

#include "app_config.h"
#include "camera_service.h"
#include "control_server.h"
#include "dev_bridge.h"
#include "inference.h"
#include "motion_detector.h"
#include "sd_storage.h"
#include "session_logger.h"

namespace {
AppConfig config;
SdStorage storage;
CameraService camera;
NullInferenceEngine inference;
SessionLogger logger;
ControlServer control_server;
DevBridge dev_bridge;

bool ready = false;
bool finished = false;
uint32_t next_capture_due_ms = 0;
uint32_t session_started_ms = 0;
uint32_t saved_image_count = 0;
String fatal_error;
MotionPreview previous_motion_preview;
MotionPreview current_motion_preview;
bool motion_baseline_ready = false;
// Deliberately prime and not 100: DashboardWriter::kChunkSize is 100, and an
// equal interval meant every performance sample landed exactly on a chunk
// promotion (a rename plus saveState/writeManifest/writeSummary), so every
// figure ever recorded was worst-case rather than typical. See
// docs/performance-experiment.md.
constexpr uint32_t kPerformanceSampleInterval = 97;
// Was 5000 and a bare delay(). A green colour cast persisting for the first
// ~30 minutes of a session (28 August 2026, see docs/hardware-validation.md)
// is consistent with auto white balance/exposure never actually converging
// during warm-up, because a bare delay() gives them no captured frames to
// iterate on - AWB/AEC adjust per-frame, not per elapsed millisecond. Now an
// active frame-pump (see setup()) rather than an idle wait, so lengthening
// it buys real AWB iterations instead of just a longer pause; extended
// accordingly. Costs nothing against the 3,600 s capture budget - it runs
// before session_started_ms is set. Unverified until the 29 August 2026
// daylight trial confirms it actually shortens or removes the cast.
constexpr uint32_t kCameraWarmupMs = 15000;

struct CaptureTiming {
  uint32_t scheduled_ms = 0;
  uint32_t start_lag_ms = 0;
  uint32_t capture_ms = 0;
  uint32_t image_write_ms = 0;
  uint32_t raw_csv_ms = 0;
  uint32_t dashboard_ms = 0;
  uint32_t logger_ms = 0;
  uint32_t total_ms = 0;
  size_t jpeg_bytes = 0;
  String outcome;
};

String performance_path;

float motion_history[ControlStatus::kMotionHistoryCapacity] = {};
uint8_t motion_history_count = 0;
uint8_t motion_history_next = 0;

void recordMotionScore(float score) {
  motion_history[motion_history_next] = score;
  motion_history_next = (motion_history_next + 1) % ControlStatus::kMotionHistoryCapacity;
  if (motion_history_count < ControlStatus::kMotionHistoryCapacity) ++motion_history_count;
}

void report(const String& message) { Serial.println("[insect-logger] " + message); }

String imageDirectoryFor(uint32_t sequence) {
  char shard[16];
  snprintf(shard, sizeof(shard), "shard_%04lu", static_cast<unsigned long>(((sequence - 1) / 100) + 1));
  return "/images/" + logger.runId() + "/" + String(shard);
}

String imagePathFor(const String& capture_id, uint32_t sequence) {
  return imageDirectoryFor(sequence) + "/" + capture_id + ".jpg";
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

bool refreshMotionBaseline(String& diagnostic) {
  // Reinitialising the OV3660 after a JPEG changes auto exposure for its first
  // grayscale frames. Discard two of them, then compare future scheduled checks
  // against the settled preview rather than the pre-JPEG image.
  if (!camera.captureMotionPreview(current_motion_preview, diagnostic)) return false;
  if (!camera.captureMotionPreview(previous_motion_preview, diagnostic)) return false;
  motion_baseline_ready = true;
  return true;
}

void ensurePerformanceLog() {
  if (performance_path.isEmpty() || storage.exists(performance_path)) return;
  String diagnostic;
  const String header =
      "capture_id,scheduled_ms,start_lag_ms,capture_ms,image_write_ms,raw_csv_ms,dashboard_ms,logger_ms,total_ms,jpeg_bytes," \
      "outcome,free_heap,largest_free_heap,min_free_heap,free_psram,largest_free_psram,sd_clock_hz";
  if (!storage.appendLine(performance_path, header, diagnostic)) report("performance log unavailable: " + diagnostic);
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
      String(timing.image_write_ms) + "," + String(timing.raw_csv_ms) + "," +
      String(timing.dashboard_ms) + "," + String(timing.logger_ms) + "," +
      String(timing.total_ms) + "," + String(static_cast<unsigned long>(timing.jpeg_bytes)) + "," +
      timing.outcome + "," + String(free_heap) + "," + String(largest_free_heap) + "," +
      String(min_free_heap) + "," + String(free_psram) + "," + String(largest_free_psram) + "," +
      String(storage.clockHz());
  String diagnostic;
  if (!storage.appendLine(performance_path, line, diagnostic)) report("performance sample write failed: " + diagnostic);
  report("performance sample " + line);
}

CaptureTiming captureOnce(uint32_t scheduled_ms) {
  CaptureTiming timing;
  timing.scheduled_ms = scheduled_ms;
  const uint32_t capture_sequence = logger.captureCount() + 1;
  const String capture_id = logger.nextCaptureId();
  String diagnostic;
  const uint32_t total_started = millis();
  timing.start_lag_ms = total_started - scheduled_ms;
  float motion_score = -1.0F;

  if (config.motion_trigger_enabled) {
    const uint32_t preview_started = millis();
    if (!camera.captureMotionPreview(current_motion_preview, diagnostic)) {
      report(diagnostic);
      recordCaptureFailure(capture_id, scheduled_ms, "motion_preview_unavailable");
      timing.capture_ms = millis() - preview_started;
      timing.total_ms = millis() - total_started;
      timing.outcome = "capture_error";
      writePerformanceSample(capture_id, timing);
      return timing;
    }

    const bool retain = !motion_baseline_ready ||
                        ((motion_score = motionLocalScore(previous_motion_preview, current_motion_preview)) >= config.motion_threshold);
    previous_motion_preview = current_motion_preview;
    motion_baseline_ready = true;
    if (motion_score >= 0.0F) recordMotionScore(motion_score);
    if (!retain) {
      CaptureRecord record;
      record.capture_id = capture_id;
      record.uptime_ms = millis();
      record.scheduled_ms = scheduled_ms;
      record.outcome = "motion_not_detected";
      record.width = kMotionPreviewWidth;
      record.height = kMotionPreviewHeight;
      record.capture_ms = millis() - preview_started;
      record.save_outcome = "not_saved";
      record.motion_score = motion_score;
      record.motion_threshold = config.motion_threshold;
      timing.capture_ms = record.capture_ms;
      const uint32_t logger_started = millis();
      LoggerTiming logger_timing;
      if (!logger.recordCapture(record, diagnostic, &logger_timing)) report("motion log failure: " + diagnostic);
      timing.raw_csv_ms = logger_timing.raw_csv_ms;
      timing.dashboard_ms = logger_timing.dashboard_ms;
      timing.logger_ms = millis() - logger_started;
      timing.total_ms = millis() - total_started;
      timing.outcome = record.outcome;
      writePerformanceSample(capture_id, timing);
      return timing;
    }
    if (!camera.prepareRetainedCapture(diagnostic)) {
      report(diagnostic);
      recordCaptureFailure(capture_id, scheduled_ms, "motion_capture_mode_unavailable");
      timing.capture_ms = millis() - preview_started;
      timing.total_ms = millis() - total_started;
      timing.outcome = "capture_error";
      writePerformanceSample(capture_id, timing);
      return timing;
    }
  }

  const uint32_t capture_started = millis();
  camera_fb_t* frame = camera.capture(diagnostic);
  if (frame == nullptr) {
    report(diagnostic);
    if (config.motion_trigger_enabled) {
      String restore_diagnostic;
      if (!camera.restoreMotionPreview(restore_diagnostic)) report(restore_diagnostic);
    }
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
  record.motion_score = motion_score;
  record.motion_threshold = config.motion_trigger_enabled ? config.motion_threshold : 0;
  timing.capture_ms = record.capture_ms;
  timing.jpeg_bytes = frame->len;
  record.inference = inference.run(*frame);
  record.image_path = imagePathFor(capture_id, capture_sequence);
  if (!storage.ensureDirectory(imageDirectoryFor(capture_sequence), diagnostic)) report(diagnostic);
  record.outcome = "completed";
  record.save_outcome = "saved";

  const uint32_t image_write_started = millis();
  const bool image_saved = storage.writeBinaryAtomicCreate(record.image_path, frame->buf, frame->len, diagnostic);
  timing.image_write_ms = millis() - image_write_started;
  control_server.updatePeek(frame->buf, frame->len);
  camera.release(frame);
  if (config.motion_trigger_enabled) {
    String restore_diagnostic;
    if (!camera.restoreMotionPreview(restore_diagnostic)) {
      report(restore_diagnostic);
      record.error_code = "motion_preview_restore_failed";
    } else if (!refreshMotionBaseline(restore_diagnostic)) {
      report(restore_diagnostic);
      record.error_code = "motion_preview_settle_failed";
    }
  }
  if (!image_saved) {
    record.outcome = "storage_error";
    record.save_outcome = "failed";
    record.image_path = "";
    record.error_code = "image_write_failed";
    report(diagnostic);
  } else {
    ++saved_image_count;
  }
  const uint32_t logger_started = millis();
  LoggerTiming logger_timing;
  if (!logger.recordCapture(record, diagnostic, &logger_timing)) report("capture log failure: " + diagnostic);
  timing.raw_csv_ms = logger_timing.raw_csv_ms;
  timing.dashboard_ms = logger_timing.dashboard_ms;
  timing.logger_ms = millis() - logger_started;
  timing.total_ms = millis() - total_started;
  timing.outcome = record.outcome;
  writePerformanceSample(capture_id, timing);
  return timing;
}

void finishSession() {
  if (finished) return;
  String diagnostic;
  if (!logger.finish(diagnostic)) report("session finalisation failed: " + diagnostic);
  // Unmount unconditionally: even a finaliser failure leaves earlier
  // committed data more likely to survive a clean FAT unmount than none.
  storage.end();
  report("session complete; card unmounted, safe to remove");
  finished = true;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(250);
  report(String("firmware ") + INSECT_LOGGER_FIRMWARE_VERSION + " starting");
  String diagnostic;
  // Wi-Fi starts before any SD/camera/logger step so the control app can
  // still report what went wrong if one of them fails; capture is the
  // primary mission and none of those steps depend on Wi-Fi succeeding.
#ifndef WIFI_CONTROL_DISABLED_FOR_TEST
  if (!control_server.begin(diagnostic)) report("control app unavailable: " + diagnostic);
  else report(diagnostic);
#else
  report("control app disabled for this build: motion-detection control test");
#endif
  if (!storage.begin(diagnostic)) { report("fatal storage failure: " + diagnostic); fatal_error = "No SD card found: " + diagnostic; return; }
  // storage.begin()'s own diagnostic (mount clock) was previously silently
  // discarded here - the next report() below overwrote it before it was
  // ever printed. Surfacing it now while investigating a totalBytes()
  // discrepancy between this boot-time mount and a later dev-bridge MOUNT
  // (29 August 2026, see docs/hardware-validation.md).
  report(diagnostic + " total=" + String(static_cast<unsigned long long>(storage.totalBytes())) +
         " used=" + String(static_cast<unsigned long long>(storage.usedBytes())));
  config = ConfigLoader::defaults();
  if (!ConfigLoader::load(storage.fs(), config, diagnostic)) { report("fatal configuration failure: " + diagnostic); fatal_error = "Bad configuration: " + diagnostic; return; }
  control_server.setEffectiveConfig(
      "{\"schema_version\":1,\"capture_fps\":" + String(config.capture_fps) +
      ",\"capture_interval_ms\":" + String(config.capture_interval_ms) +
      ",\"max_session_seconds\":" + String(config.max_session_seconds) +
      ",\"capture_mode\":\"" + config.capture_mode + "\",\"camera_preset\":\"" + config.camera_preset +
      "\",\"motion_trigger_enabled\":" + String(config.motion_trigger_enabled ? "true" : "false") +
      ",\"motion_threshold\":" + String(config.motion_threshold) +
      ",\"frame_size\":\"" + config.frame_size + "\",\"jpeg_quality\":" + String(config.jpeg_quality) +
      ",\"model_id\":\"" + config.model_id + "\",\"log_level\":\"" + config.log_level + "\"}");
  report(diagnostic);
  if (!camera.begin(config, diagnostic)) { report("fatal camera failure: " + diagnostic); fatal_error = "Camera failure: " + diagnostic; return; }
  report(diagnostic);
  if (!inference.begin(diagnostic)) { report("fatal inference failure: " + diagnostic); fatal_error = "Inference setup failure: " + diagnostic; return; }
  report(diagnostic);
  if (!logger.begin(storage, config, camera.sensorId(), diagnostic)) { report("fatal session setup failure: " + diagnostic); fatal_error = "Session setup failure: " + diagnostic; return; }
  report(diagnostic);
  performance_path = "/system/performance_" + logger.runId() + ".csv";
  ensurePerformanceLog();
  report("camera warm-up: " + camera.whiteBalanceStatus() + ", pumping frames for " +
         String(kCameraWarmupMs / 1000) + "s so AWB/AEC converge before the first retained frame");
  {
    const uint32_t warmup_deadline = millis() + kCameraWarmupMs;
    uint32_t warmup_frames = 0;
    while (static_cast<int32_t>(millis() - warmup_deadline) < 0) {
      String warmup_diagnostic;
      camera_fb_t* warmup_frame = camera.capture(warmup_diagnostic);
      if (warmup_frame != nullptr) {
        camera.release(warmup_frame);
        ++warmup_frames;
      } else {
        delay(50);  // avoid a tight spin if a frame is briefly unavailable
      }
    }
    report("camera warm-up complete: " + String(warmup_frames) + " frames pumped, " + camera.whiteBalanceStatus());
  }
  session_started_ms = millis();
  next_capture_due_ms = session_started_ms;
  ready = true;
}

void loop() {
  control_server.handleClient();
  // Only acted on here, between captures, so a stop can never land mid-write.
  if (ready && !finished && control_server.consumeStopRequest()) finishSession();
  // config.json is only ever read once at boot, so writing it mid-session
  // has no effect on the current run - safe any time the card is mounted.
  String pending_config_json;
  if (!finished && fatal_error.isEmpty() && control_server.consumePendingConfigWrite(pending_config_json)) {
    String diagnostic;
    if (!storage.writeTextAtomic("/config.json", pending_config_json, diagnostic)) report("config write failed: " + diagnostic);
    else report("camera settings updated; takes effect after the board is restarted");
  }

  // Serial development bridge: only touches the card when capture is not
  // about to run this cycle (ready && !finished mirrors exactly the
  // condition that gates captureOnce() below), so it can never race a write.
  DevBridgeContext dev_context;
  dev_context.storage = &storage;
  dev_context.capturing = ready && !finished;
  dev_context.stop_session = []() { finishSession(); };
  dev_bridge.poll(dev_context);

  ControlStatus status;
  status.run_id = logger.runId();
  status.capture_count = logger.captureCount();
  status.saved_count = saved_image_count;
  status.sd_mounted = fatal_error.isEmpty() && !finished;
  status.error = fatal_error;
  status.elapsed_ms = ready ? (millis() - session_started_ms) : 0;
  status.state = !fatal_error.isEmpty() ? "error" : (!ready ? "warming_up" : (finished ? "safe_to_remove" : "capturing"));
  status.motion_recent_count = motion_history_count;
  const uint8_t oldest_offset = (motion_history_next + ControlStatus::kMotionHistoryCapacity - motion_history_count) %
                                 ControlStatus::kMotionHistoryCapacity;
  for (uint8_t index = 0; index < motion_history_count; ++index) {
    status.motion_recent[index] = motion_history[(oldest_offset + index) % ControlStatus::kMotionHistoryCapacity];
  }
  control_server.update(status);

  if (!ready || finished) { delay(100); return; }
  const uint32_t now = millis();
  if (config.max_session_seconds > 0 && now - session_started_ms >= config.max_session_seconds * 1000UL) { finishSession(); return; }
  if (static_cast<int32_t>(now - next_capture_due_ms) < 0) { delay(5); return; }
  const uint32_t scheduled_ms = next_capture_due_ms;
  next_capture_due_ms += config.capture_interval_ms;
  if (static_cast<int32_t>(now - next_capture_due_ms) >= 0) {
    report("capture cadence overrun; schedule rebased without backlog");
    next_capture_due_ms = now + config.capture_interval_ms;
  }
  captureOnce(scheduled_ms);
}
