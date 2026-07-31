#pragma once

#include <Arduino.h>
#include <FS.h>

class SdStorage {
 public:
  bool begin(String& diagnostic);
  bool ensureDirectory(const String& path, String& diagnostic);
  bool exists(const String& path) const;
  bool writeTextAtomic(const String& path, const String& content, String& diagnostic);
  bool writeBinaryAtomic(const String& path, const uint8_t* data, size_t length,
                         String& diagnostic);
  bool appendLine(const String& path, const String& line, String& diagnostic);
  String readText(const String& path, size_t max_bytes, String& diagnostic) const;
  fs::FS& fs();
};
