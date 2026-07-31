#include "dashboard_writer.h"

namespace {
String chunkFileName(uint32_t id, const char* suffix) {
  char buffer[48];
  snprintf(buffer, sizeof(buffer), "/data/captures_%06lu.%s", static_cast<unsigned long>(id), suffix);
  return String(buffer);
}
}

bool DashboardWriter::begin(SdStorage& storage, String& diagnostic) {
  storage_ = &storage;
  if (!loadState(diagnostic)) return false;
  current_chunk_id_ = closed_chunk_count_ + 1;
  current_part_path_ = chunkFileName(current_chunk_id_, "part");
  storage_->fs().remove(current_part_path_);
  diagnostic = "dashboard writer ready";
  return true;
}

bool DashboardWriter::appendCapture(const DashboardCapture& capture, String& diagnostic) {
  if (storage_ == nullptr) {
    diagnostic = "dashboard writer not initialised";
    return false;
  }
  const String line =
      "window.InsectData=window.InsectData||{captures:[],addCapture:function(c){this.captures.push(c);}};" +
      String("window.InsectData.addCapture({\"runId\":\"") + escapeJavaScript(capture.run_id) +
      "\",\"captureId\":\"" + escapeJavaScript(capture.capture_id) + "\",\"uptimeMs\":" +
      String(capture.uptime_ms) + ",\"outcome\":\"" + escapeJavaScript(capture.outcome) +
      "\",\"imagePath\":\"" + escapeJavaScript(capture.image_path) + "\",\"width\":" +
      String(capture.width) + ",\"height\":" + String(capture.height) + ",\"jpegBytes\":" +
      String(static_cast<unsigned long>(capture.jpeg_bytes)) + ",\"captureMs\":" +
      String(capture.capture_ms) + ",\"inferenceMs\":" + String(capture.inference_ms) +
      ",\"inferenceOutcome\":\"" + inferenceOutcomeName(capture.inference_outcome) + "\"});";
  if (!storage_->appendLine(current_part_path_, line, diagnostic)) return false;
  ++current_chunk_count_;
  if (current_chunk_count_ >= kChunkSize) return promoteCurrentChunk(diagnostic);
  return true;
}

bool DashboardWriter::finish(String& diagnostic) {
  if (current_chunk_count_ > 0 && !promoteCurrentChunk(diagnostic)) return false;
  return writeSummary(diagnostic);
}

bool DashboardWriter::promoteCurrentChunk(String& diagnostic) {
  const String final_path = chunkFileName(current_chunk_id_, "js");
  storage_->fs().remove(final_path);
  if (!storage_->fs().rename(current_part_path_, final_path)) {
    diagnostic = "cannot promote dashboard chunk " + current_part_path_;
    return false;
  }
  ++closed_chunk_count_;
  closed_capture_count_ += current_chunk_count_;
  current_chunk_count_ = 0;
  if (!saveState(diagnostic) || !writeManifest(diagnostic) || !writeSummary(diagnostic)) return false;
  ++current_chunk_id_;
  current_part_path_ = chunkFileName(current_chunk_id_, "part");
  return true;
}

bool DashboardWriter::writeManifest(String& diagnostic) {
  String chunks;
  for (uint32_t index = 1; index <= closed_chunk_count_; ++index) {
    if (index > 1) chunks += ',';
    chunks += "\"data/captures_";
    char id[8];
    snprintf(id, sizeof(id), "%06lu", static_cast<unsigned long>(index));
    chunks += id;
    chunks += ".js\"";
  }
  const String content =
      "window.InsectData=window.InsectData||{};window.InsectData.manifest={\"schemaVersion\":1,"
      "\"captureChunks\":[" + chunks + "],\"lastCommittedCaptureCount\":" +
      String(closed_capture_count_) + "};\n";
  return storage_->writeTextAtomic("/manifest.js", content, diagnostic);
}

bool DashboardWriter::writeSummary(String& diagnostic) {
  const String content =
      "window.InsectData=window.InsectData||{};window.InsectData.summary={\"schemaVersion\":1,"
      "\"committedCaptures\":" + String(closed_capture_count_) +
      ",\"note\":\"Only closed chunks are shown; raw CSV is authoritative.\"};\n";
  return storage_->writeTextAtomic("/summary.js", content, diagnostic);
}

bool DashboardWriter::loadState(String& diagnostic) {
  const String state = storage_->readText("/system/dashboard_state.txt", 128, diagnostic);
  if (state.isEmpty()) {
    closed_chunk_count_ = 0;
    closed_capture_count_ = 0;
    diagnostic = "dashboard state starts empty";
    return true;
  }
  const int separator = state.indexOf(',');
  if (separator < 1) {
    diagnostic = "dashboard state corrupt";
    return false;
  }
  closed_chunk_count_ = static_cast<uint32_t>(state.substring(0, separator).toInt());
  closed_capture_count_ = static_cast<uint32_t>(state.substring(separator + 1).toInt());
  return true;
}

bool DashboardWriter::saveState(String& diagnostic) {
  return storage_->writeTextAtomic("/system/dashboard_state.txt",
                                   String(closed_chunk_count_) + "," + String(closed_capture_count_),
                                   diagnostic);
}

String DashboardWriter::escapeJavaScript(const String& value) const {
  String escaped;
  escaped.reserve(value.length());
  for (size_t index = 0; index < value.length(); ++index) {
    const char character = value[index];
    if (character == '\\' || character == '"') escaped += '\\';
    if (character == '\n' || character == '\r') {
      escaped += ' ';
    } else {
      escaped += character;
    }
  }
  return escaped;
}
