#include "motion_detector.h"

#include <cstdlib>

namespace {
constexpr uint8_t kTileColumns = 8;
constexpr uint8_t kTileRows = 6;
constexpr uint16_t kTileWidth = kMotionPreviewWidth / kTileColumns;
constexpr uint16_t kTileHeight = kMotionPreviewHeight / kTileRows;
constexpr size_t kTileCount = static_cast<size_t>(kTileColumns) * kTileRows;
}

float motionLocalScore(const MotionPreview& previous, const MotionPreview& current) {
  int32_t brightness_delta_total = 0;
  for (size_t index = 0; index < kMotionPreviewPixels; ++index) {
    brightness_delta_total += static_cast<int16_t>(current.pixels[index]) - previous.pixels[index];
  }
  const int16_t brightness_delta = brightness_delta_total / static_cast<int32_t>(kMotionPreviewPixels);
  uint32_t tile_totals[kTileCount]{};
  for (uint16_t y = 0; y < kMotionPreviewHeight; ++y) {
    for (uint16_t x = 0; x < kMotionPreviewWidth; ++x) {
      const size_t index = static_cast<size_t>(y) * kMotionPreviewWidth + x;
      const int16_t adjusted = static_cast<int16_t>(current.pixels[index]) - previous.pixels[index] - brightness_delta;
      const size_t tile = static_cast<size_t>(y / kTileHeight) * kTileColumns + (x / kTileWidth);
      tile_totals[tile] += static_cast<uint32_t>(abs(adjusted));
    }
  }
  uint32_t strongest = 0;
  for (const uint32_t total : tile_totals) strongest = max(strongest, total);
  return static_cast<float>(strongest) / static_cast<float>(kTileWidth * kTileHeight);
}
