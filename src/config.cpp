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
  uint32_t session_seconds = config.max_session_seconds;
  uint32_t quality = config.jpeg_quality;
  if (!readUnsigned(document, "capture_fps", fps) ||
      !readUnsigned(document, "max_session_seconds", session_seconds) ||
      !readUnsigned(document, "jpeg_quality", quality) ||
      !readString(document, "capture_mode", config.capture_mode) ||
      !readString(document, "camera_preset", config.camera_preset) ||
      !readString(document, "frame_size", config.frame_size) ||
      !readString(document, "model_id", config.model_id) ||
      !readString(document, "log_level", config.log_level)) {
    diagnostic = "config.json has an unsupported value";
    return false;
  }

  const bool pilot_mode = config.capture_mode == "pilot";
  const bool quality_trial_mode = config.capture_mode == "quality_trial";
  if ((fps != 1 && fps != 2) || session_seconds == 0 || session_seconds > 3600 || quality > 63 ||
      !isSafeIdentifier(config.camera_preset) ||
      (config.frame_size != "VGA" && config.frame_size != "SVGA" && config.frame_size != "QXGA") ||
      (!pilot_mode && !quality_trial_mode) ||
      (pilot_mode && (fps != 1 || config.frame_size != "QXGA" || quality != 12)) ||
      (quality_trial_mode && session_seconds > 600)) {
    diagnostic = "config.json conflicts with pilot or quality-trial safety bounds";
    return false;
  }
  config.capture_fps = fps;
  config.max_session_seconds = session_seconds;
  config.jpeg_quality = static_cast<uint8_t>(quality);
  diagnostic = "config.json loaded: " + config.capture_mode + "/" + config.camera_preset;
  return true;
}
