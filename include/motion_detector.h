#pragma once

#include <Arduino.h>

constexpr uint16_t kMotionPreviewWidth = 160;
constexpr uint16_t kMotionPreviewHeight = 120;
constexpr size_t kMotionPreviewPixels = static_cast<size_t>(kMotionPreviewWidth) * kMotionPreviewHeight;

struct MotionPreview {
  uint8_t pixels[kMotionPreviewPixels]{};
};

// A local tile mean of brightness-adjusted grayscale differences. It deliberately
// ignores whole-frame brightness drift and matches the offline spike's score family.
float motionLocalScore(const MotionPreview& previous, const MotionPreview& current);
