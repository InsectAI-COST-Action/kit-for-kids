#pragma once

#include <Arduino.h>
#include <FS.h>

class SdStorage {
 public:
  bool begin(String& diagnostic);
  // Flushes and unmounts the card so its FAT metadata is left in a clean
  // state before power is removed. Safe to call only once capture has
  // stopped; nothing else in this class may be called afterwards.
  void end();
  // SPI clock the card actually mounted at, in Hz. begin() steps down through
  // candidate speeds, so this reports what the card accepted rather than what
  // was requested. Zero before a successful begin().
  uint32_t clockHz() const;
  // Unlike clockHz(), these are live reads each call rather than cached at
  // begin() - card usage changes throughout a session. Added 29 August 2026
  // so the dashboard can show storage remaining without needing the serial
  // dev-bridge's DF command.
  uint64_t totalBytes() const;
  uint64_t usedBytes() const;
  bool ensureDirectory(const String& path, String& diagnostic);
  bool exists(const String& path) const;
  bool writeTextAtomic(const String& path, const String& content, String& diagnostic);
  bool writeBinaryAtomic(const String& path, const uint8_t* data, size_t length,
                         String& diagnostic);
  bool writeBinaryAtomicCreate(const String& path, const uint8_t* data, size_t length,
                               String& diagnostic);
  bool appendLine(const String& path, const String& line, String& diagnostic);
  String readText(const String& path, size_t max_bytes, String& diagnostic) const;
  fs::FS& fs();

 private:
  bool writeBinaryAtomicInternal(const String& path, const uint8_t* data, size_t length,
                                 bool replace_existing, String& diagnostic);
};
