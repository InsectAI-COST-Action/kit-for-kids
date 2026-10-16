#pragma once

#include <Arduino.h>
#include <esp_camera.h>

#include "app_config.h"
#include "motion_detector.h"

// Per-sensor facts for each camera module this firmware supports. Both the
// XIAO's stock OV3660 and the OV5640 replacement module fit the same
// connector and answer on the same pins; they differ only in identity and in
// the white-balance starting gain measured for each one's colour response.
// The table lives in camera_service.cpp.
struct SensorProfile {
  uint16_t pid;
  const char* name;
  uint16_t seed_red_gain;
  uint16_t seed_green_gain;
  uint16_t seed_blue_gain;
  // false = the seed is borrowed from another sensor as a starting point and
  // has not yet been measured on this one (reported at boot so trial runs
  // can tell the difference).
  bool seed_measured;
  // true = the module has a voice-coil lens and the firmware runs the
  // sensor's continuous autofocus (OV5640 only; the OV3660 is fixed-focus).
  bool has_autofocus;
  // Master clock (XCLK) fed to the sensor. It paces readout, so it sets how
  // many frames per second the sensor streams - and the sensor streams
  // continuously whether or not a frame is kept, so it also sets how much
  // heat it makes. Must leave comfortably more than 1 frame/s for the 1 FPS
  // schedule. OV5640 datasheet input range is about 6-27 MHz.
  uint32_t xclk_hz;
};

class CameraService {
 public:
  bool begin(const AppConfig& config, String& diagnostic);
  camera_fb_t* capture(String& diagnostic);
  bool captureMotionPreview(MotionPreview& preview, String& diagnostic);
  bool prepareRetainedCapture(String& diagnostic);
  bool restoreMotionPreview(String& diagnostic);
  void release(camera_fb_t* frame);
  const String& sensorId() const;
  // nullptr until begin() succeeds, or when the attached sensor is not one
  // of the supported modules.
  const SensorProfile* sensorProfile() const;
  // Current AWB-related register state, for the boot diagnostic - added
  // alongside the 28 August 2026 white-balance fix so the trial run can
  // confirm what was actually applied, not just what was intended.
  String whiteBalanceStatus() const;
  // Direct read of the sensor's live manual-gain registers (0x3400 R,
  // 0x3402 G, 0x3404 B - confirmed from the actual driver sources,
  // sensors/ov3660.c and sensors/ov5640.c in espressif/esp32-camera, not
  // guessed; both use this identical layout, the same registers
  // set_wb_mode()'s fixed presets write, and AWB itself writes here
  // continuously while in auto mode). Added 31 August 2026 to find a real
  // seed value from actual converged conditions, rather than inferring one
  // from JPEG output.
  String manualGainStatus() const;
  // Writes the attached sensor's profile seed R/G/B gain (same 3 registers
  // as above) then immediately re-enables auto AWB - the seed becomes AWB's
  // starting point to adjust from, not a locked value. Briefly toggles the
  // manual/auto latch at 0x3406 so the written values actually take; see
  // docs/hardware-validation.md "Seeded white balance" for why this
  // sequence (manual write, then auto) rather than writing while already
  // in auto mode. Refuses on an unrecognised sensor rather than writing
  // registers whose meaning on that part is unknown.
  bool seedWhiteBalance(String& diagnostic);
  // One-line autofocus state for the boot report: "fixed focus",
  // "continuous, focused", "continuous, focusing", "off in motion-trigger
  // mode", or why starting it failed.
  String autofocusStatus() const;

 private:
  bool initialiseCamera(pixformat_t pixel_format, framesize_t frame_size, String& diagnostic);
  bool configureCaptureSensor(String& diagnostic);
  bool configurePreviewSensor(String& diagnostic);
  bool startAutofocus(String& diagnostic);
  framesize_t captureFrameSize() const;

  AppConfig config_;
  sensor_t* sensor_ = nullptr;
  bool motion_preview_mode_ = false;
  String sensor_id_ = "uninitialised";
  const SensorProfile* profile_ = nullptr;
  // XCLK for the next init: the default until the sensor is identified,
  // then its profile's value.
  uint32_t xclk_hz_ = 20000000;
  bool autofocus_running_ = false;
  String autofocus_note_ = "fixed focus";
};
