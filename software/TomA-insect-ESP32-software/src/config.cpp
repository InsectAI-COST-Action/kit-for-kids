#include "app_config.h"

namespace {

bool readUnsigned(const String& document, const char* key, uint32_t& value) {
  const String needle = String("\"") + key + "\"";
  const int key_at = document.indexOf(needle);
  if (key_at < 0) return true;
  const int colon = document.indexOf(':', key_at + needle.length());
  if (colon < 0) return false;
  int start = colon + 1;
  while (start < document.length() && isspace(document[start])) ++start;
  int end = start;
  while (end < document.length() && isDigit(document[end])) ++end;
  if (end == start) return false;
  value = static_cast<uint32_t>(document.substring(start, end).toInt());
  return true;
}

bool readBool(const String& document, const char* key, bool& value) {
  const String needle = String("\"") + key + "\"";
  const int key_at = document.indexOf(needle);
  if (key_at < 0) return true;
  const int colon = document.indexOf(':', key_at + needle.length());
  if (colon < 0) return false;
  String remainder = document.substring(colon + 1);
  remainder.trim();
  if (remainder.startsWith("true")) { value = true; return true; }
  if (remainder.startsWith("false")) { value = false; return true; }
  return false;
}

bool readString(const String& document, const char* key, String& value) {
  const String needle = String("\"") + key + "\"";
  const int key_at = document.indexOf(needle);
  if (key_at < 0) return true;
  const int colon = document.indexOf(':', key_at + needle.length());
  if (colon < 0) return false;
  const int first_quote = document.indexOf('"', colon + 1);
  if (first_quote < 0) return false;
  const int second_quote = document.indexOf('"', first_quote + 1);
  if (second_quote < 0) return false;
  value = document.substring(first_quote + 1, second_quote);
  return true;
}

bool isSafeIdentifier(const String& value) {
  if (value.isEmpty() || value.length() > 48) return false;
  for (size_t index = 0; index < value.length(); ++index) {
    const char character = value[index];
    const bool allowed = (character >= 'a' && character <= 'z') ||
                         (character >= '0' && character <= '9') || character == '_';
    if (!allowed) return false;
  }
  return true;
}

bool isCustomInterval(uint32_t milliseconds) {
  return milliseconds == 1000 || milliseconds == 2000 || milliseconds == 30000 || milliseconds == 60000;
}

bool isCustomDuration(uint32_t seconds) {
  return seconds == 0 || seconds == 60 || seconds == 300 || seconds == 1800 || seconds == 3600;
}

}  // namespace

AppConfig ConfigLoader::defaults() { return AppConfig{}; }

bool ConfigLoader::load(fs::FS& fs, AppConfig& config, String& diagnostic) {
  File file = fs.open("/config.json", FILE_READ);
  if (!file) {
    diagnostic = "config.json missing; using compiled defaults";
    return true;
  }

  const String document = file.readString();
  file.close();
  if (document.length() > 2048) {
    diagnostic = "config.json exceeds 2048-byte safety limit";
    return false;
  }

  uint32_t fps = config.capture_fps;
  uint32_t interval_ms = config.capture_interval_ms;
  uint32_t session_seconds = config.max_session_seconds;
  uint32_t quality = config.jpeg_quality;
  uint32_t motion_threshold = config.motion_threshold;
  bool motion_trigger_enabled = config.motion_trigger_enabled;
  if (!readUnsigned(document, "capture_fps", fps) ||
      !readUnsigned(document, "capture_interval_ms", interval_ms) ||
      !readUnsigned(document, "max_session_seconds", session_seconds) ||
      !readUnsigned(document, "jpeg_quality", quality) ||
      !readUnsigned(document, "motion_threshold", motion_threshold) ||
      !readBool(document, "motion_trigger_enabled", motion_trigger_enabled) ||
      !readString(document, "capture_mode", config.capture_mode) ||
      !readString(document, "camera_preset", config.camera_preset) ||
      !readString(document, "frame_size", config.frame_size) ||
      !readString(document, "model_id", config.model_id) ||
      !readString(document, "log_level", config.log_level)) {
    diagnostic = "config.json has an unsupported value";
    return false;
  }

  // Legacy quality-trial cards did not record an interval. Preserve their 1/2 FPS cadence.
  if (document.indexOf("\"capture_interval_ms\"") < 0) interval_ms = fps == 0 ? 0 : 1000UL / fps;
  const bool pilot_mode = config.capture_mode == "pilot";
  const bool quality_trial_mode = config.capture_mode == "quality_trial";
  const bool custom_mode = config.capture_mode == "custom";
  const bool known_frame_size = config.frame_size == "VGA" || config.frame_size == "SVGA" || config.frame_size == "QXGA";
  const bool safe_custom_quality =
      (config.frame_size == "QXGA" && quality == 12) || (config.frame_size == "VGA" && quality == 24);

  if ((fps != 1 && fps != 2) || session_seconds > 3600 || quality > 63 || motion_threshold != 5 ||
      !isSafeIdentifier(config.camera_preset) || !known_frame_size ||
      (!pilot_mode && !quality_trial_mode && !custom_mode) ||
      (pilot_mode && (fps != 1 || interval_ms != 1000 || session_seconds != 3600 ||
                      config.frame_size != "QXGA" || quality != 12)) ||
      (quality_trial_mode && (session_seconds == 0 || session_seconds > 600 ||
                              interval_ms != 1000UL / fps)) ||
      (custom_mode && (fps != 1 || !isCustomInterval(interval_ms) ||
                       !isCustomDuration(session_seconds) || !safe_custom_quality))) {
    diagnostic = "config.json conflicts with pilot, custom, or quality-trial safety bounds";
    return false;
  }
  config.capture_fps = fps;
  config.capture_interval_ms = interval_ms;
  config.max_session_seconds = session_seconds;
  config.jpeg_quality = static_cast<uint8_t>(quality);
  config.motion_trigger_enabled = motion_trigger_enabled;
  config.motion_threshold = static_cast<uint8_t>(motion_threshold);
  diagnostic = "config.json loaded: " + config.capture_mode + "/" + config.camera_preset;
  return true;
}
