#pragma once

#include <Arduino.h>

#include "app_config.h"
#include "dashboard_writer.h"
#include "inference.h"
#include "sd_storage.h"

struct CaptureRecord {
  String capture_id;
  uint32_t uptime_ms = 0;
  uint32_t scheduled_ms = 0;
  String outcome;
  uint16_t width = 0;
  uint16_t height = 0;
  size_t jpeg_bytes = 0;
  uint32_t capture_ms = 0;
  InferenceResult inference;
  String image_path;
  String save_outcome;
  String error_code;
};

class SessionLogger {
 public:
  bool begin(SdStorage& storage, const AppConfig& config, const String& sensor_id,
             String& diagnostic);
  String nextCaptureId();
  bool recordCapture(const CaptureRecord& capture, String& diagnostic);
  bool finish(String& diagnostic);
  const String& runId() const;
  uint32_t captureCount() const;

 private:
  bool initialiseRunCounter(String& diagnostic);
  bool markPreviousRunInterrupted(String& diagnostic);
  bool writeRunManifest(const String& state, String& diagnostic);
  String csvEscape(const String& value) const;

  SdStorage* storage_ = nullptr;
  DashboardWriter dashboard_;
  AppConfig config_;
  String run_id_;
  String sensor_id_;
  uint32_t run_counter_ = 0;
  uint32_t capture_sequence_ = 0;
  uint32_t started_ms_ = 0;
};
