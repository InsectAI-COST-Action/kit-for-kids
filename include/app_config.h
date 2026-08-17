#pragma once

#include <Arduino.h>
#include <FS.h>

struct AppConfig {
  uint32_t capture_fps = 1;
  uint32_t max_session_seconds = 3600;
  String capture_mode = "pilot";
  String camera_preset = "qxga_q12_1fps";
  String frame_size = "QXGA";
  uint8_t jpeg_quality = 12;
  String model_id = "none";
  String log_level = "info";
};

class ConfigLoader {
 public:
  static AppConfig defaults();
  static bool load(fs::FS& fs, AppConfig& config, String& diagnostic);
};
