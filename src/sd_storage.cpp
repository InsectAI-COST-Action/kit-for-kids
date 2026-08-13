#include "sd_storage.h"

#include <SD.h>

namespace {
constexpr int kSdChipSelectPin = 21;
}

bool SdStorage::begin(String& diagnostic) {
  if (!SD.begin(kSdChipSelectPin)) {
    diagnostic = "SD mount failed on GPIO21";
    return false;
  }
  if (SD.cardType() == CARD_NONE) {
    diagnostic = "no microSD card present";
    return false;
  }
  diagnostic = "SD mounted";
  return ensureDirectory("/system", diagnostic) && ensureDirectory("/raw", diagnostic) &&
         ensureDirectory("/images", diagnostic) && ensureDirectory("/data", diagnostic);
}

bool SdStorage::ensureDirectory(const String& path, String& diagnostic) {
  if (SD.exists(path)) return true;
  if (!SD.mkdir(path)) {
    diagnostic = "failed to create directory " + path;
    return false;
  }
  return true;
}

bool SdStorage::exists(const String& path) const { return SD.exists(path); }

bool SdStorage::writeTextAtomic(const String& path, const String& content, String& diagnostic) {
  return writeBinaryAtomic(path, reinterpret_cast<const uint8_t*>(content.c_str()), content.length(),
                           diagnostic);
}

bool SdStorage::writeBinaryAtomic(const String& path, const uint8_t* data, size_t length,
                                  String& diagnostic) {
  return writeBinaryAtomicInternal(path, data, length, true, diagnostic);
}

bool SdStorage::writeBinaryAtomicCreate(const String& path, const uint8_t* data, size_t length,
                                        String& diagnostic) {
  return writeBinaryAtomicInternal(path, data, length, false, diagnostic);
}

bool SdStorage::writeBinaryAtomicInternal(const String& path, const uint8_t* data, size_t length,
                                          bool replace_existing, String& diagnostic) {
  const String temporary_path = path + ".tmp";
  SD.remove(temporary_path);
  File file = SD.open(temporary_path, FILE_WRITE);
  if (!file) {
    diagnostic = "cannot open temporary file " + temporary_path;
    return false;
  }
  const size_t written = file.write(data, length);
  file.flush();
  file.close();
  if (written != length) {
    SD.remove(temporary_path);
    diagnostic = "short write for " + path;
    return false;
  }
  if (replace_existing) SD.remove(path);
  if (!SD.rename(temporary_path, path)) {
    diagnostic = "cannot promote temporary file " + path;
    return false;
  }
  return true;
}

bool SdStorage::appendLine(const String& path, const String& line, String& diagnostic) {
  File file = SD.open(path, FILE_APPEND);
  if (!file) {
    diagnostic = "cannot append " + path;
    return false;
  }
  const size_t expected = line.length() + 1;
  size_t written = file.print(line);
  written += file.write('\n');
  file.flush();
  file.close();
  if (written != expected) {
    diagnostic = "short append " + path;
    return false;
  }
  return true;
}

String SdStorage::readText(const String& path, size_t max_bytes, String& diagnostic) const {
  File file = SD.open(path, FILE_READ);
  if (!file) {
    diagnostic = "cannot read " + path;
    return String();
  }
  if (file.size() > max_bytes) {
    file.close();
    diagnostic = "file exceeds read safety limit " + path;
    return String();
  }
  const String content = file.readString();
  file.close();
  return content;
}

fs::FS& SdStorage::fs() { return SD; }
