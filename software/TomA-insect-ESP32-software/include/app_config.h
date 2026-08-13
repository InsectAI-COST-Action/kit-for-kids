#pragma once

#include <Arduino.h>
#include <FS.h>

struct AppConfig {
  uint32_t capture_fps = 2;
  uint32_t max_session_seconds = 3600;
  String frame_size = "VGA";
  uint8_t jpeg_quality = 12;
  String model_id = "none";
  String log_level = "info";
};

class ConfigLoader {
 public:
  static AppConfig defaults();
  static bool load(fs::FS& fs, AppConfig& config, String& diagnostic);
};
