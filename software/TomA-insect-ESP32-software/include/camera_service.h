#pragma once

#include <Arduino.h>
#include <esp_camera.h>

#include "app_config.h"
#include "motion_detector.h"

class CameraService {
 public:
  bool begin(const AppConfig& config, String& diagnostic);
  camera_fb_t* capture(String& diagnostic);
  bool captureMotionPreview(MotionPreview& preview, String& diagnostic);
  bool prepareRetainedCapture(String& diagnostic);
  bool restoreMotionPreview(String& diagnostic);
  void release(camera_fb_t* frame);
  const String& sensorId() const;
  // Current AWB-related register state, for the boot diagnostic - added
  // alongside the 28 August 2026 white-balance fix so the trial run can
  // confirm what was actually applied, not just what was intended.
  String whiteBalanceStatus() const;
  // Direct read of the OV3660's live manual-gain registers (0x3400 R,
  // 0x3402 G, 0x3404 B - confirmed from the actual driver source,
  // sensors/ov3660.c in espressif/esp32-camera, not guessed; these are the
  // same registers set_wb_mode()'s fixed presets write, and AWB itself
  // writes here continuously while in auto mode). Added 31 August 2026 to
  // find a real seed value from actual converged conditions, rather than
  // inferring one from JPEG output.
  String manualGainStatus() const;
  // Writes a starting R/G/B gain (same 3 registers as above) then
  // immediately re-enables auto AWB - the seed becomes AWB's starting
  // point to adjust from, not a locked value. Briefly toggles the manual/
  // auto latch at 0x3406 so the written values actually take; see
  // docs/hardware-validation.md "Seeded white balance" for why this
  // sequence (manual write, then auto) rather than writing while already
  // in auto mode.
  bool seedWhiteBalance(uint16_t r_gain, uint16_t g_gain, uint16_t b_gain, String& diagnostic);

 private:
  bool initialiseCamera(pixformat_t pixel_format, framesize_t frame_size, String& diagnostic);
  bool configureCaptureSensor(String& diagnostic);
  bool configurePreviewSensor(String& diagnostic);
  framesize_t captureFrameSize() const;

  AppConfig config_;
  sensor_t* sensor_ = nullptr;
  bool motion_preview_mode_ = false;
  String sensor_id_ = "uninitialised";
};
