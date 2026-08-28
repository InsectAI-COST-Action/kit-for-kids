#include "dev_bridge.h"

#include <FS.h>
#include <SD.h>

namespace {
constexpr size_t kChunkBytes = 512;        // bounded so large files never sit in RAM
constexpr uint32_t kWriteTimeoutMs = 20000;
constexpr uint32_t kMaxWriteBytes = 256 * 1024;

const char kHexDigits[] = "0123456789abcdef";

void reply(const String& message) { Serial.println("<DEV " + message + ">"); }
void replyOk() { reply("OK"); }
void replyError(const String& message) { reply("ERR " + message); }
// A distinct frame type recognised by the client's wait loops (both the
// single-reply path and the multi-line-payload path) and printed without
// being mistaken for the actual reply/payload. For commands slow enough
// that "no output yet" is genuinely ambiguous between "working" and
// "stalled" - see the AUDIT/CAT investigation in docs/dev-bridge.md.
void progress(const String& message) { Serial.println("<DEV PROGRESS " + message + ">"); }

int hexValue(char character) {
  if (character >= '0' && character <= '9') return character - '0';
  if (character >= 'a' && character <= 'f') return character - 'a' + 10;
  if (character >= 'A' && character <= 'F') return character - 'A' + 10;
  return -1;
}

// Paths are always absolute and must not escape the card root. The bridge is
// a development aid, but it should still be impossible to walk out of the
// filesystem by accident.
bool pathAcceptable(const String& path) {
  return path.startsWith("/") && path.indexOf("..") < 0 && path.length() < 200;
}

// run_id is interpolated into a path (/images/<run_id>) rather than taken as
// one, so it gets its own, stricter check.
bool identifierAcceptable(const String& value) {
  if (value.length() == 0 || value.length() > 64) return false;
  for (size_t index = 0; index < value.length(); ++index) {
    const char character = value[index];
    if (!isAlphaNumeric(character) && character != '_' && character != '-') return false;
  }
  return true;
}

String stripCr(const String& line) {
  return line.endsWith("\r") ? line.substring(0, line.length() - 1) : line;
}

int csvColumnIndex(const String& header, const String& name) {
  int start = 0;
  int column = 0;
  while (true) {
    const int comma = header.indexOf(',', start);
    const String field = (comma < 0) ? header.substring(start) : header.substring(start, comma);
    if (field == name) return column;
    if (comma < 0) return -1;
    start = comma + 1;
    ++column;
  }
}

// Allocates a substring - only meant for the rare matching row, once a
// cheaper check (csvFieldEquals) has already confirmed it's wanted.
String csvField(const String& row, int index) {
  if (index < 0) return String();
  int start = 0;
  for (int column = 0; column < index; ++column) {
    const int comma = row.indexOf(',', start);
    if (comma < 0) return String();
    start = comma + 1;
  }
  const int comma = row.indexOf(',', start);
  return (comma < 0) ? row.substring(start) : row.substring(start, comma);
}

// Compares a CSV field in place via strncmp rather than allocating a
// substring for every row - this runs once per row in captures.csv (which
// can hold thousands of rows across a card's lifetime), so avoiding a
// per-row heap allocation here matters. See the CAT stall note in
// commandRead: a large captures.csv is exactly what triggers it, and
// repeated small-String churn is one of the suspected mechanisms.
bool csvFieldEquals(const String& row, int index, const String& target) {
  if (index < 0) return false;
  int start = 0;
  for (int column = 0; column < index; ++column) {
    const int comma = row.indexOf(',', start);
    if (comma < 0) return false;
    start = comma + 1;
  }
  const int comma = row.indexOf(',', start);
  const int end = (comma < 0) ? static_cast<int>(row.length()) : comma;
  const int field_length = end - start;
  if (field_length != static_cast<int>(target.length())) return false;
  return strncmp(row.c_str() + start, target.c_str(), field_length) == 0;
}

// Lightweight extraction for this firmware's own small, trusted,
// pretty-printed JSON manifests (see ConfigLoader/logger) - not a general
// JSON parser. Matches `"key": "value"` with the space after the colon
// optional.
String jsonStringField(const String& json, const String& key) {
  const int key_at = json.indexOf("\"" + key + "\"");
  if (key_at < 0) return String();
  const int colon = json.indexOf(':', key_at);
  if (colon < 0) return String();
  const int quote_start = json.indexOf('"', colon + 1);
  if (quote_start < 0) return String();
  const int quote_end = json.indexOf('"', quote_start + 1);
  if (quote_end < 0) return String();
  return json.substring(quote_start + 1, quote_end);
}
}  // namespace

void DevBridge::poll(const DevBridgeContext& context) {
  while (Serial.available() > 0) {
    const char character = static_cast<char>(Serial.read());
    if (character == '\r') continue;
    if (character == '\n') {
      const String line = buffer_;
      buffer_ = "";
      if (line.startsWith("DEV ")) {
        execute(line.substring(4), context);
        return;  // one command per poll, so capture cadence is never starved
      }
      continue;
    }
    if (buffer_.length() < 512) buffer_ += character;
  }
}

void DevBridge::execute(const String& line, const DevBridgeContext& context) {
  String command = line;
  command.trim();
  const int space = command.indexOf(' ');
  const String verb = (space < 0) ? command : command.substring(0, space);
  const String argument = (space < 0) ? String("") : command.substring(space + 1);

  if (verb == "PING") {
    replyOk();
    return;
  }
  if (verb == "STOP") {
    if (!context.stop_session) {
      replyError("no session control available");
      return;
    }
    context.stop_session();
    replyOk();
    return;
  }
  if (verb == "REBOOT") {
    replyOk();
    Serial.flush();
    delay(200);
    ESP.restart();
    return;
  }
  if (verb == "MOUNT") {
    String diagnostic;
    if (context.storage == nullptr || !context.storage->begin(diagnostic)) {
      replyError(diagnostic.isEmpty() ? "mount failed" : diagnostic);
      return;
    }
    reply("OK " + diagnostic);
    return;
  }

  // Everything below touches the card. Refuse while a session is writing:
  // the main loop owns the card during capture, and a multi-second transfer
  // would wreck cadence.
  if (context.capturing) {
    replyError("session active; send DEV STOP first");
    return;
  }
  if (context.storage == nullptr) {
    replyError("storage unavailable");
    return;
  }

  if (verb == "LS") { commandList(argument, context); return; }
  if (verb == "CAT") { commandRead(argument, context); return; }
  if (verb == "RM") { commandRemove(argument, context); return; }
  if (verb == "DF") { commandFree(context); return; }
  if (verb == "AUDIT") { commandAudit(argument, context); return; }
  if (verb == "RUNS") { commandRuns(context); return; }
  if (verb == "PUT") {
    const int split = argument.lastIndexOf(' ');
    if (split < 0) { replyError("usage: DEV PUT <path> <bytes>"); return; }
    commandWrite(argument.substring(0, split), argument.substring(split + 1).toInt(), context);
    return;
  }
  replyError("unknown command " + verb);
}

void DevBridge::commandList(const String& path, const DevBridgeContext& context) {
  if (!pathAcceptable(path)) { replyError("bad path"); return; }
  File directory = context.storage->fs().open(path);
  if (!directory || !directory.isDirectory()) {
    if (directory) directory.close();
    replyError("not a directory");
    return;
  }
  // Counted first so the reader knows exactly how many lines to expect.
  uint32_t entries = 0;
  for (File entry = directory.openNextFile(); entry; entry = directory.openNextFile()) {
    ++entries;
    entry.close();
  }
  directory.close();

  directory = context.storage->fs().open(path);
  reply("OK " + String(entries));
  for (File entry = directory.openNextFile(); entry; entry = directory.openNextFile()) {
    Serial.println(String(entry.isDirectory() ? "d " : "f ") + String(entry.size()) + " " + String(entry.name()));
    entry.close();
  }
  directory.close();
  reply("END");
}

void DevBridge::commandRead(const String& path, const DevBridgeContext& context) {
  if (!pathAcceptable(path)) { replyError("bad path"); return; }
  File file = context.storage->fs().open(path, FILE_READ);
  if (!file || file.isDirectory()) {
    if (file) file.close();
    replyError("not a readable file");
    return;
  }
  const size_t total = file.size();
  const uint32_t lines = (total + kChunkBytes - 1) / kChunkBytes;
  reply("OK " + String(lines) + " bytes " + String(total));

  uint8_t chunk[kChunkBytes];
  String encoded;
  encoded.reserve(kChunkBytes * 2 + 1);
  uint32_t chunk_index = 0;
  while (file.available()) {
    const size_t read = file.read(chunk, kChunkBytes);
    encoded = "";
    for (size_t index = 0; index < read; ++index) {
      encoded += kHexDigits[(chunk[index] >> 4) & 0x0F];
      encoded += kHexDigits[chunk[index] & 0x0F];
    }
    Serial.println(encoded);
    // Large CAT transfers (multi-thousand chunks) have been observed to
    // decelerate and then stall completely partway through - reproduced
    // with Wi-Fi/control-app fully disabled, so that is not the cause.
    // Root cause not confirmed; this periodic yield is a plausible,
    // low-risk mitigation (an unbroken multi-second loop never otherwise
    // yields to any background task) rather than a verified fix. See
    // docs/dev-bridge.md Known risks.
    ++chunk_index;
    if ((chunk_index % 32) == 0) yield();
    // Visible progress so a slow transfer is distinguishable from a stalled
    // one without guessing - see docs/dev-bridge.md. Deliberately frequent:
    // testing 28 August 2026 showed the degradation this exists to surface
    // can begin well before chunk 500, so a coarser interval would still
    // leave a long silent gap in the worst case.
    if ((chunk_index % 64) == 0) progress(String(chunk_index) + " " + String(lines));
  }
  file.close();
  reply("END");
}

void DevBridge::commandWrite(const String& path, uint32_t byte_count, const DevBridgeContext& context) {
  if (!pathAcceptable(path)) { replyError("bad path"); return; }
  if (byte_count > kMaxWriteBytes) { replyError("too large"); return; }

  // Ready first, so the sender only starts transmitting once we can receive.
  reply("OK send " + String(byte_count));

  String payload;
  payload.reserve(byte_count * 2 + 8);
  const uint32_t deadline = millis() + kWriteTimeoutMs;
  while (payload.length() < byte_count * 2) {
    if (static_cast<int32_t>(millis() - deadline) >= 0) { replyError("timeout receiving payload"); return; }
    while (Serial.available() > 0) {
      const char character = static_cast<char>(Serial.read());
      if (character == '\n' || character == '\r') continue;
      payload += character;
    }
    delay(1);
  }

  uint8_t* bytes = static_cast<uint8_t*>(malloc(byte_count > 0 ? byte_count : 1));
  if (bytes == nullptr) { replyError("out of memory"); return; }
  for (uint32_t index = 0; index < byte_count; ++index) {
    const int high = hexValue(payload[index * 2]);
    const int low = hexValue(payload[index * 2 + 1]);
    if (high < 0 || low < 0) { free(bytes); replyError("bad hex payload"); return; }
    bytes[index] = static_cast<uint8_t>((high << 4) | low);
  }

  String diagnostic;
  const bool written = context.storage->writeBinaryAtomic(path, bytes, byte_count, diagnostic);
  free(bytes);
  if (!written) { replyError(diagnostic.isEmpty() ? "write failed" : diagnostic); return; }
  replyOk();
}

void DevBridge::commandRemove(const String& path, const DevBridgeContext& context) {
  if (!pathAcceptable(path)) { replyError("bad path"); return; }
  if (!context.storage->exists(path)) { replyError("does not exist"); return; }
  if (!context.storage->fs().remove(path)) { replyError("remove failed"); return; }
  replyOk();
}

void DevBridge::commandFree(const DevBridgeContext& context) {
  reply("OK total " + String(static_cast<unsigned long>(SD.totalBytes())) +
        " used " + String(static_cast<unsigned long>(SD.usedBytes())));
}

// Remote equivalent of the checks tools/audit_card.py and
// tools/camera_trial_report.py make from a mounted card, scoped to one run.
// Everything is computed here, on-device, against the SD card directly -
// the only thing that crosses serial is this one summary line, which
// sidesteps the large-CAT-transfer stall entirely rather than fixing it.
// Deliberately narrower than the Python scripts (mean, not median; no
// manifest/chunk cross-check, no performance_run_<id>.csv correlation) -
// see docs/dev-bridge.md for exact scope. Use those scripts for the full
// audit once the card is in a reader.
void DevBridge::commandAudit(const String& run_id, const DevBridgeContext& context) {
  if (!identifierAcceptable(run_id)) { replyError("bad run id"); return; }

  // --- Image tree: directory metadata only (sizes from openNextFile),
  // no file content is ever read. ---
  File run_dir = context.storage->fs().open("/images/" + run_id);
  const bool found_run_dir = run_dir && run_dir.isDirectory();
  uint32_t shard_count = 0, image_count = 0, temp_count = 0;
  uint32_t min_bytes = 0, max_bytes = 0, last_shard_images = 0;
  uint64_t total_bytes = 0;
  if (found_run_dir) {
    int32_t highest_shard_number = -1;
    uint32_t entries_scanned = 0;  // across every shard, for progress only
    for (File shard = run_dir.openNextFile(); shard; shard = run_dir.openNextFile()) {
      if (shard.isDirectory()) {
        ++shard_count;
        const String shard_name = String(shard.name());
        const int underscore = shard_name.lastIndexOf('_');
        const int32_t shard_number = (underscore >= 0) ? shard_name.substring(underscore + 1).toInt() : -1;
        uint32_t this_shard_images = 0;
        for (File entry = shard.openNextFile(); entry; entry = shard.openNextFile()) {
          if (!entry.isDirectory()) {
            const String name = String(entry.name());
            if (name.endsWith(".tmp") || name.endsWith(".part")) {
              ++temp_count;
            } else {
              ++image_count;
              ++this_shard_images;
              const uint32_t size = entry.size();
              if (image_count == 1 || size < min_bytes) min_bytes = size;
              if (size > max_bytes) max_bytes = size;
              total_bytes += size;
            }
          }
          entry.close();
          // This directory-tree walk was found 28 August 2026 to be a
          // second plausible site for the same unexplained slowdown as the
          // captures.csv scan below - it was previously uninstrumented,
          // which meant a stall here looked identical to one in the CSV
          // scan. See docs/dev-bridge.md.
          ++entries_scanned;
          if ((entries_scanned % 64) == 0) yield();
          if ((entries_scanned % 64) == 0) progress(String(entries_scanned) + " image-tree entries scanned (shard " + String(shard_count) + ")");
        }
        // Tracked by parsed shard number, not iteration order, so this is
        // right even if the filesystem doesn't return entries in creation
        // order.
        if (shard_number > highest_shard_number) {
          highest_shard_number = shard_number;
          last_shard_images = this_shard_images;
        }
      }
      shard.close();
    }
  }
  if (run_dir) run_dir.close();

  // --- captures.csv restricted to this run_id, streamed line by line (never
  // held whole in RAM, never sent whole over serial). ---
  uint32_t csv_completed = 0, csv_other = 0;
  uint32_t jpeg_min = 0, jpeg_max = 0, interval_max = 0;
  uint64_t jpeg_sum = 0, interval_sum = 0;
  uint32_t interval_count = 0;
  int32_t last_uptime = -1;
  bool csv_found = false;

  File csv = context.storage->fs().open("/raw/captures.csv", FILE_READ);
  if (csv && !csv.isDirectory()) {
    csv_found = true;
    const String header = stripCr(csv.readStringUntil('\n'));
    const int run_id_col = csvColumnIndex(header, "run_id");
    const int outcome_col = csvColumnIndex(header, "outcome");
    const int jpeg_col = csvColumnIndex(header, "jpeg_bytes");
    const int uptime_col = csvColumnIndex(header, "uptime_ms");
    uint32_t row_index = 0;
    while (csv.available()) {
      const String row = stripCr(csv.readStringUntil('\n'));
      if (row.length() > 0 && csvFieldEquals(row, run_id_col, run_id)) {
        if (csvFieldEquals(row, outcome_col, "completed")) {
          ++csv_completed;
          const uint32_t jpeg_bytes = static_cast<uint32_t>(csvField(row, jpeg_col).toInt());
          if (csv_completed == 1 || jpeg_bytes < jpeg_min) jpeg_min = jpeg_bytes;
          if (jpeg_bytes > jpeg_max) jpeg_max = jpeg_bytes;
          jpeg_sum += jpeg_bytes;
          const int32_t uptime = csvField(row, uptime_col).toInt();
          if (last_uptime >= 0 && uptime >= last_uptime) {
            const uint32_t interval = static_cast<uint32_t>(uptime - last_uptime);
            interval_sum += interval;
            ++interval_count;
            if (interval > interval_max) interval_max = interval;
          }
          last_uptime = uptime;
        } else {
          ++csv_other;
        }
      }
      // captures.csv accumulates across the card's whole lifetime (multi-MB,
      // thousands of rows) - yield periodically so a long scan never blocks
      // other firmware duties, same reasoning as the CAT loop above.
      ++row_index;
      if ((row_index % 64) == 0) yield();
      // Visible progress: this scan has been observed taking anywhere from
      // ~2 minutes to apparently stalling outright, which is indistinguishable
      // from a genuine hang without this - see docs/dev-bridge.md. Same
      // 64-row interval as the yield above (not the coarser 500 first
      // tried): testing 28 August 2026 showed a stall can begin before row
      // 500, so a heartbeat that infrequent can still leave a long silent
      // gap in the worst case.
      if ((row_index % 64) == 0) progress(String(row_index) + " rows scanned, " + String(csv_completed) + " matched");
    }
  }
  if (csv) csv.close();

  reply("OK run=" + run_id +
        " found=" + String(found_run_dir ? 1 : 0) +
        " images=" + String(image_count) +
        " shards=" + String(shard_count) +
        " last_shard_images=" + String(last_shard_images) +
        " temp_or_partial=" + String(temp_count) +
        " min_bytes=" + String(min_bytes) +
        " max_bytes=" + String(max_bytes) +
        " mean_bytes=" + String(image_count ? static_cast<uint32_t>(total_bytes / image_count) : 0) +
        " csv_found=" + String(csv_found ? 1 : 0) +
        " csv_completed=" + String(csv_completed) +
        " csv_other=" + String(csv_other) +
        " jpeg_min=" + String(jpeg_min) +
        " jpeg_max=" + String(jpeg_max) +
        " jpeg_mean=" + String(csv_completed ? static_cast<uint32_t>(jpeg_sum / csv_completed) : 0) +
        " interval_mean_ms=" + String(interval_count ? static_cast<uint32_t>(interval_sum / interval_count) : 0) +
        " interval_max_ms=" + String(interval_max));
}

// Remote equivalent of audit_card.py's run_states check: one line per run
// manifest (run_id + state), so a stale "running" state or an unexpected
// run count is visible without pulling every manifest individually.
void DevBridge::commandRuns(const DevBridgeContext& context) {
  File directory = context.storage->fs().open("/raw/runs");
  if (!directory || !directory.isDirectory()) {
    if (directory) directory.close();
    replyError("no /raw/runs directory");
    return;
  }
  uint32_t entries = 0;
  for (File entry = directory.openNextFile(); entry; entry = directory.openNextFile()) {
    if (!entry.isDirectory()) ++entries;
    entry.close();
  }
  directory.close();

  directory = context.storage->fs().open("/raw/runs");
  reply("OK " + String(entries));
  for (File entry = directory.openNextFile(); entry; entry = directory.openNextFile()) {
    if (!entry.isDirectory()) {
      String content;
      content.reserve(entry.size() + 1);
      while (entry.available()) content += static_cast<char>(entry.read());
      const String run_id = jsonStringField(content, "run_id");
      const String state = jsonStringField(content, "state");
      Serial.println((run_id.length() ? run_id : String(entry.name())) + " " + (state.length() ? state : String("unknown")));
    }
    entry.close();
  }
  directory.close();
  reply("END");
}
