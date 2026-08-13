#pragma once

#include <Arduino.h>

#include "inference.h"
#include "sd_storage.h"

struct DashboardCapture {
  String run_id;
  String capture_id;
  uint32_t uptime_ms = 0;
  String outcome;
  String image_path;
  uint16_t width = 0;
  uint16_t height = 0;
  size_t jpeg_bytes = 0;
  uint32_t capture_ms = 0;
  uint32_t inference_ms = 0;
  InferenceOutcome inference_outcome = InferenceOutcome::ModelUnavailable;
};

class DashboardWriter {
 public:
  bool begin(SdStorage& storage, String& diagnostic);
  bool appendCapture(const DashboardCapture& capture, String& diagnostic);
  bool finish(String& diagnostic);

 private:
  static constexpr uint16_t kChunkSize = 100;
  bool openCurrentChunk(String& diagnostic);
  bool promoteCurrentChunk(String& diagnostic);
  bool recoverCurrentChunk(String& diagnostic);
  uint32_t countCurrentRecords(String& diagnostic) const;
  bool writeManifest(String& diagnostic);
  bool writeSummary(String& diagnostic);
  bool loadState(String& diagnostic);
  bool saveState(String& diagnostic);
  String currentChunkPath() const;
  String escapeJavaScript(const String& value) const;

  SdStorage* storage_ = nullptr;
  File current_file_;
  uint32_t closed_chunk_count_ = 0;
  uint32_t closed_capture_count_ = 0;
  uint32_t current_chunk_count_ = 0;
  uint32_t current_chunk_id_ = 1;
  String current_part_path_;
};
