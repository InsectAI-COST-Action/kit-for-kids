#include "session_logger.h"

namespace {
String paddedId(const char* prefix, uint32_t value) {
  char buffer[32];
  snprintf(buffer, sizeof(buffer), "%s_%06lu", prefix, static_cast<unsigned long>(value));
  return String(buffer);
}

const char* kCaptureHeader =
    "schema_version,device_id,run_id,boot_id,capture_id,captured_at_utc,uptime_ms,scheduled_ms,"
    "outcome,frame_width,frame_height,jpeg_bytes,capture_ms,inference_ms,model_id,prediction_count,"
    "max_confidence,image_path,save_policy,save_outcome,error_code";
const char* kDetectionHeader =
    "schema_version,run_id,capture_id,prediction_index,label_id,label,confidence,bbox_x,bbox_y,"
    "bbox_w,bbox_h,model_id,metadata_json";
const char* kActiveRunPath = "/system/active_run.txt";
}

bool SessionLogger::begin(SdStorage& storage, const AppConfig& config, const String& sensor_id,
                          String& diagnostic) {
  storage_ = &storage;
  config_ = config;
  sensor_id_ = sensor_id;
  started_ms_ = millis();
  if (!markPreviousRunInterrupted(diagnostic) || !initialiseRunCounter(diagnostic)) return false;
  run_id_ = paddedId("run", run_counter_);
  if (!storage_->ensureDirectory("/images/" + run_id_, diagnostic) ||
      !storage_->ensureDirectory("/raw/runs", diagnostic)) return false;
  if (!storage_->exists("/raw/captures.csv") &&
      !storage_->appendLine("/raw/captures.csv", kCaptureHeader, diagnostic)) return false;
  if (!storage_->exists("/raw/detections.csv") &&
      !storage_->appendLine("/raw/detections.csv", kDetectionHeader, diagnostic)) return false;
  if (!dashboard_.begin(storage, diagnostic) || !writeRunManifest("running", diagnostic)) return false;
  if (!storage_->writeTextAtomic(kActiveRunPath, run_id_, diagnostic)) return false;
  diagnostic = "session started: " + run_id_;
  return true;
}

String SessionLogger::nextCaptureId() {
  ++capture_sequence_;
  return run_id_ + "_img_" + String(capture_sequence_);
}

bool SessionLogger::recordCapture(const CaptureRecord& capture, String& diagnostic, LoggerTiming* timing) {
  const String row =
      String(INSECT_LOGGER_SCHEMA_VERSION) + ",device_000001," + csvEscape(run_id_) + ",boot_" +
      String(started_ms_) + "," + csvEscape(capture.capture_id) + ",," + String(capture.uptime_ms) +
      "," + String(capture.scheduled_ms) + "," + csvEscape(capture.outcome) + "," +
      String(capture.width) + "," + String(capture.height) + "," +
      String(static_cast<unsigned long>(capture.jpeg_bytes)) + "," + String(capture.capture_ms) + "," +
      String(capture.inference.elapsed_ms) + "," + csvEscape(capture.inference.model_id) + "," +
      String(capture.inference.prediction_count) + "," + String(capture.inference.max_confidence, 4) +
      "," + csvEscape(capture.image_path) + ",every_frame," + csvEscape(capture.save_outcome) + "," +
      csvEscape(capture.error_code);
  const uint32_t raw_started = millis();
  if (!storage_->appendLine("/raw/captures.csv", row, diagnostic)) return false;
  if (timing != nullptr) timing->raw_csv_ms = millis() - raw_started;

  DashboardCapture dashboard_capture;
  dashboard_capture.run_id = run_id_;
  dashboard_capture.capture_id = capture.capture_id;
  dashboard_capture.uptime_ms = capture.uptime_ms;
  dashboard_capture.outcome = capture.outcome;
  dashboard_capture.image_path = capture.image_path;
  dashboard_capture.width = capture.width;
  dashboard_capture.height = capture.height;
  dashboard_capture.jpeg_bytes = capture.jpeg_bytes;
  dashboard_capture.capture_ms = capture.capture_ms;
  dashboard_capture.inference_ms = capture.inference.elapsed_ms;
  dashboard_capture.inference_outcome = capture.inference.outcome;
  const uint32_t dashboard_started = millis();
  const bool dashboard_ok = dashboard_.appendCapture(dashboard_capture, diagnostic);
  if (timing != nullptr) timing->dashboard_ms = millis() - dashboard_started;
  return dashboard_ok;
}

bool SessionLogger::finish(String& diagnostic) {
  if (!dashboard_.finish(diagnostic) || !writeRunManifest("finished", diagnostic)) return false;
  if (storage_->exists(kActiveRunPath) && !storage_->fs().remove(kActiveRunPath)) {
    diagnostic = "cannot clear active run marker";
    return false;
  }
  return true;
}

const String& SessionLogger::runId() const { return run_id_; }
uint32_t SessionLogger::captureCount() const { return capture_sequence_; }

bool SessionLogger::initialiseRunCounter(String& diagnostic) {
  const String previous = storage_->readText("/system/next_run.txt", 32, diagnostic);
  run_counter_ = previous.isEmpty() ? 1 : static_cast<uint32_t>(previous.toInt() + 1);
  if (run_counter_ == 0) run_counter_ = 1;
  return storage_->writeTextAtomic("/system/next_run.txt", String(run_counter_), diagnostic);
}

bool SessionLogger::markPreviousRunInterrupted(String& diagnostic) {
  if (!storage_->exists(kActiveRunPath)) return true;
  const String previous = storage_->readText(kActiveRunPath, 64, diagnostic);
  if (previous.isEmpty()) return false;
  const String manifest_path = "/raw/runs/" + previous + ".json";
  if (storage_->exists(manifest_path)) {
    String manifest = storage_->readText(manifest_path, 512, diagnostic);
    if (manifest.isEmpty()) return false;
    manifest.replace("\"state\": \"running\"", "\"state\": \"interrupted_power_removed\"");
    if (!storage_->writeTextAtomic(manifest_path, manifest, diagnostic)) return false;
  }
  if (!storage_->fs().remove(kActiveRunPath)) {
    diagnostic = "cannot clear stale active run marker";
    return false;
  }
  diagnostic = "previous run marked interrupted_power_removed";
  return true;
}

bool SessionLogger::writeRunManifest(const String& state, String& diagnostic) {
  const String content =
      "{\n  \"schema_version\": 1,\n  \"run_id\": \"" + run_id_ +
      "\",\n  \"state\": \"" + state + "\",\n  \"sensor\": \"" + sensor_id_ +
      "\",\n  \"model_id\": \"" + config_.model_id +
      "\",\n  \"capture_fps\": 2,\n  \"time_source\": \"session_relative\"\n}\n";
  return storage_->writeTextAtomic("/raw/runs/" + run_id_ + ".json", content, diagnostic);
}

String SessionLogger::csvEscape(const String& value) const {
  String escaped = value;
  escaped.replace("\"", "\"\"");
  if (escaped.indexOf(',') >= 0 || escaped.indexOf('"') >= 0 || escaped.indexOf('\n') >= 0) {
    return "\"" + escaped + "\"";
  }
  return escaped;
}
