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
  while (file.available()) {
    const size_t read = file.read(chunk, kChunkBytes);
    encoded = "";
    for (size_t index = 0; index < read; ++index) {
      encoded += kHexDigits[(chunk[index] >> 4) & 0x0F];
      encoded += kHexDigits[chunk[index] & 0x0F];
    }
    Serial.println(encoded);
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
