#include "camera_service.h"

#include <cstring>

#include <esp32-hal-psram.h>
#include <sensor.h>

#include "vendor/ov5640_af_firmware.h"

namespace {
constexpr int kPwdnPin = -1;
constexpr int kResetPin = -1;
constexpr int kXclkPin = 10;
constexpr int kSccbSdaPin = 40;
constexpr int kSccbSclPin = 39;
constexpr int kY2Pin = 15;
constexpr int kY3Pin = 17;
constexpr int kY4Pin = 18;
constexpr int kY5Pin = 16;
constexpr int kY6Pin = 14;
constexpr int kY7Pin = 12;
constexpr int kY8Pin = 11;
constexpr int kY9Pin = 48;
constexpr int kVsyncPin = 38;
constexpr int kHrefPin = 47;
constexpr int kPclkPin = 13;

// OV3660 seed measured 31 August 2026 (run_000078, this room, daylight): AWB
// converges to approximately this gain and produces a visually neutral image
// within ~10 s of continuous pumping with no sensor reset. If the camera
// moves to very different lighting the seed may need remeasuring - see
// docs/hardware-validation.md "Seeded white balance" for how it was found
// and how to redo it.
//
// OV5640 (supported from 17 September 2026, see docs/hardware-validation.md
// "Camera swap"): the register mechanism is identical, but no seed has been
// measured on this sensor yet, so it borrows the OV3660 values as a starting
// point and is marked unmeasured. Replace with a measured value using the
// same method once a daylight session on an OV5640 board is available.
//
// Autofocus: the OV5640 module has a voice-coil lens; the OV3660 is
// fixed-focus. Continuous rather than single-shot because children may pick
// the camera up and move it mid-session (owner decision, 1 October 2026).
//
// XCLK: OV3660 keeps the 20 MHz all its validation ran at. OV5640 at 20 MHz
// streamed ~2.3 QXGA frames/s and its module got hot enough to melt a rubber
// band with a heatsink fitted (2 October 2026), so it runs at 10 MHz to
// stream roughly half as many frames - see docs/hardware-validation.md
// "OV5640 heat".
constexpr SensorProfile kSensorProfiles[] = {
    {OV3660_PID, "OV3660", 1055, 1024, 2100, true, false, 20000000},
    {OV5640_PID, "OV5640", 1055, 1024, 2100, false, true, 10000000},
};

const SensorProfile* findSensorProfile(uint16_t pid) {
  for (const SensorProfile& profile : kSensorProfiles) {
    if (profile.pid == pid) return &profile;
  }
  return nullptr;
}
}

framesize_t CameraService::captureFrameSize() const {
  if (config_.frame_size == "QXGA") return FRAMESIZE_QXGA;
  if (config_.frame_size == "SVGA") return FRAMESIZE_SVGA;
  return FRAMESIZE_VGA;
}

bool CameraService::initialiseCamera(pixformat_t pixel_format, framesize_t frame_size, String& diagnostic) {
  // The ESP32 camera driver allocates DMA/frame buffers at esp_camera_init time.
  // Changing only sensor registers left JPEG-sized buffers active for a
  // grayscale QQVGA preview, causing fb_get timeouts on the XIAO. Recreate the
  // driver at each mode boundary so capture format and driver buffers agree.
  if (sensor_ != nullptr) {
    esp_camera_deinit();
    sensor_ = nullptr;
  }

  camera_config_t camera_config{};
  camera_config.ledc_channel = LEDC_CHANNEL_0;
  camera_config.ledc_timer = LEDC_TIMER_0;
  camera_config.pin_d0 = kY2Pin;
  camera_config.pin_d1 = kY3Pin;
  camera_config.pin_d2 = kY4Pin;
  camera_config.pin_d3 = kY5Pin;
  camera_config.pin_d4 = kY6Pin;
  camera_config.pin_d5 = kY7Pin;
  camera_config.pin_d6 = kY8Pin;
  camera_config.pin_d7 = kY9Pin;
  camera_config.pin_xclk = kXclkPin;
  camera_config.pin_pclk = kPclkPin;
  camera_config.pin_vsync = kVsyncPin;
  camera_config.pin_href = kHrefPin;
  camera_config.pin_sccb_sda = kSccbSdaPin;
  camera_config.pin_sccb_scl = kSccbSclPin;
  camera_config.pin_pwdn = kPwdnPin;
  camera_config.pin_reset = kResetPin;
  camera_config.xclk_freq_hz = xclk_hz_;
  camera_config.pixel_format = pixel_format;
  camera_config.frame_size = frame_size;
  camera_config.jpeg_quality = config_.jpeg_quality;
  camera_config.fb_count = 1;
  camera_config.fb_location = CAMERA_FB_IN_PSRAM;
  camera_config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  const esp_err_t err = esp_camera_init(&camera_config);
  if (err != ESP_OK) {
    diagnostic = "esp_camera_init failed while changing capture mode: " + String(static_cast<int>(err));
    return false;
  }
  sensor_ = esp_camera_sensor_get();
  if (sensor_ == nullptr) {
    diagnostic = "camera reinitialised but sensor descriptor is unavailable";
    return false;
  }
  profile_ = findSensorProfile(sensor_->id.PID);
  sensor_id_ = profile_ != nullptr ? String(profile_->name) : "unexpected_pid_" + String(sensor_->id.PID);
  // The sensor can only be identified after an init, so the first init uses
  // the default clock; if its profile wants another, start again once at
  // that clock. Every later init (motion mode re-inits per frame) already
  // uses the right one.
  if (profile_ != nullptr && profile_->xclk_hz != xclk_hz_) {
    xclk_hz_ = profile_->xclk_hz;
    return initialiseCamera(pixel_format, frame_size, diagnostic);
  }
  motion_preview_mode_ = pixel_format == PIXFORMAT_GRAYSCALE;
  // Explicit rather than trusting the driver's defaults: a green colour
  // cast that persists for the first ~30 minutes of a session (28 August
  // 2026, see docs/hardware-validation.md) is consistent with auto white
  // balance either not actually running or converging very slowly. This
  // doesn't change AWB's behaviour if the defaults were already correct -
  // it just makes the intended state explicit and gives setup() a known
  // state to warm up from. wb_mode 0 is auto (not a fixed sunny/cloudy/
  // office/home preset).
  if (sensor_->set_whitebal) sensor_->set_whitebal(sensor_, 1);
  if (sensor_->set_awb_gain) sensor_->set_awb_gain(sensor_, 1);
  if (sensor_->set_wb_mode) sensor_->set_wb_mode(sensor_, 0);
  return true;
}

bool CameraService::configureCaptureSensor(String& diagnostic) {
  if (!initialiseCamera(PIXFORMAT_JPEG, captureFrameSize(), diagnostic)) return false;
  autofocus_running_ = false;
  if (profile_ == nullptr || !profile_->has_autofocus) {
    autofocus_note_ = "fixed focus";
  } else if (config_.motion_trigger_enabled) {
    // Motion-trigger mode reinitialises the sensor for every retained frame,
    // which clears the AF firmware; reloading it each time (several hundred
    // ms plus refocusing) would break the capture cadence. Left off here and
    // said so, rather than half-working.
    autofocus_note_ = "off in motion-trigger mode";
  } else {
    // Never fatal: a camera that fails to start AF still captures, at
    // whatever lens position the module rests at.
    String af_diagnostic;
    startAutofocus(af_diagnostic);
    autofocus_note_ = af_diagnostic;
  }
  diagnostic = sensor_id_ + " ready for retained JPEG capture";
  return true;
}

bool CameraService::configurePreviewSensor(String& diagnostic) {
  if (!initialiseCamera(PIXFORMAT_GRAYSCALE, FRAMESIZE_QQVGA, diagnostic)) return false;
  autofocus_running_ = false;
  autofocus_note_ = profile_ != nullptr && profile_->has_autofocus ? "off in motion-trigger mode" : "fixed focus";
  diagnostic = sensor_id_ + " ready for grayscale motion preview";
  return true;
}

// A fast, low-res, still-colour warm-up mode (configureWarmupSensor()) that
// switched back to the real capture mode afterwards (restoreOperatingMode())
// was tried and removed 31 August 2026: every initialiseCamera() call resets
// manual AWB gain to 1024/1024/1024, so the switch back threw away whatever
// the warm-up had converged to. See docs/hardware-validation.md "Seeded
// white balance" for the full investigation - main.cpp now seeds the real
// capture sensor directly via seedWhiteBalance() instead, no mode switch.

bool CameraService::begin(const AppConfig& config, String& diagnostic) {
  if (!psramFound()) {
    diagnostic = "PSRAM unavailable; camera capture is disabled";
    return false;
  }
  config_ = config;
  const bool ready = config_.motion_trigger_enabled ? configurePreviewSensor(diagnostic) : configureCaptureSensor(diagnostic);
  if (ready) {
    diagnostic = "camera initialised: " + sensor_id_ + (config_.motion_trigger_enabled ? " (motion preview ready)" : "") +
                 ", xclk " + String(xclk_hz_ / 1000000) + " MHz, autofocus " + autofocus_note_;
  }
  return ready;
}

camera_fb_t* CameraService::capture(String& diagnostic) {
  camera_fb_t* frame = esp_camera_fb_get();
  if (frame == nullptr) diagnostic = "camera frame buffer unavailable";
  return frame;
}

bool CameraService::captureMotionPreview(MotionPreview& preview, String& diagnostic) {
  if (!config_.motion_trigger_enabled || !motion_preview_mode_) {
    diagnostic = "motion preview requested while camera is not in preview mode";
    return false;
  }
  camera_fb_t* frame = capture(diagnostic);
  if (frame == nullptr) return false;
  const bool valid = frame->format == PIXFORMAT_GRAYSCALE &&
                     frame->width == kMotionPreviewWidth && frame->height == kMotionPreviewHeight &&
                     frame->len >= kMotionPreviewPixels;
  if (valid) {
    std::memcpy(preview.pixels, frame->buf, kMotionPreviewPixels);
  } else {
    diagnostic = "unexpected motion-preview frame: format=" + String(frame->format) +
                 " width=" + String(frame->width) + " height=" + String(frame->height) +
                 " bytes=" + String(static_cast<unsigned long>(frame->len));
  }
  release(frame);
  return valid;
}

bool CameraService::prepareRetainedCapture(String& diagnostic) {
  return !config_.motion_trigger_enabled || configureCaptureSensor(diagnostic);
}

bool CameraService::restoreMotionPreview(String& diagnostic) {
  return !config_.motion_trigger_enabled || configurePreviewSensor(diagnostic);
}

void CameraService::release(camera_fb_t* frame) {
  if (frame != nullptr) esp_camera_fb_return(frame);
}

const String& CameraService::sensorId() const { return sensor_id_; }

const SensorProfile* CameraService::sensorProfile() const { return profile_; }

String CameraService::whiteBalanceStatus() const {
  if (sensor_ == nullptr) return "no sensor";
  return "awb=" + String(sensor_->status.awb) + " awb_gain=" + String(sensor_->status.awb_gain) +
         " wb_mode=" + String(sensor_->status.wb_mode);
}

namespace {
// Confirmed from the driver sources in espressif/esp32-camera - not
// guessed: sensors/ov3660.c (31 August 2026, see docs/hardware-validation.md
// "Seeded white balance") and sensors/ov5640.c (17 September 2026,
// re-checked 1 October 2026), which use the identical layout.
// 0x3400/0x3402/0x3404 are 16-bit R/G/B manual gain registers;
// set_wb_mode()'s fixed presets (sunny/cloudy/office/home) write these same
// three. 0x3406 is the manual/auto latch: bit 0 set means "use the manual
// values below", clear means auto AWB drives them. Only ever written when
// the attached sensor matched a profile above.
constexpr int kRedGainReg = 0x3400;
constexpr int kGreenGainReg = 0x3402;
constexpr int kBlueGainReg = 0x3404;
constexpr int kManualLatchReg = 0x3406;
// mask > 0xFF routes CameraService's get_reg/set_reg calls through the
// driver's 16-bit register path (write_reg16/read_reg16) rather than an
// 8-bit single-register access - see set_reg's own mask-width branching,
// the same in ov3660.c and ov5640.c.
constexpr int kGain16Mask = 0xFFFF;
}  // namespace

String CameraService::manualGainStatus() const {
  if (sensor_ == nullptr || sensor_->get_reg == nullptr) return "no register access";
  const int r = sensor_->get_reg(sensor_, kRedGainReg, kGain16Mask);
  const int g = sensor_->get_reg(sensor_, kGreenGainReg, kGain16Mask);
  const int b = sensor_->get_reg(sensor_, kBlueGainReg, kGain16Mask);
  return "gain r=" + String(r) + " g=" + String(g) + " b=" + String(b);
}

bool CameraService::seedWhiteBalance(String& diagnostic) {
  if (sensor_ == nullptr || sensor_->set_reg == nullptr) {
    diagnostic = "no register access available to seed white balance";
    return false;
  }
  if (profile_ == nullptr) {
    diagnostic = "no white-balance seed for " + sensor_id_ + "; not writing its registers";
    return false;
  }
  // Manual mode just long enough to latch the seed values - mirrors
  // exactly what set_wb_mode()'s own presets do internally, confirmed
  // from source rather than assumed.
  sensor_->set_reg(sensor_, kManualLatchReg, 0xFF, 1);
  sensor_->set_reg(sensor_, kRedGainReg, kGain16Mask, profile_->seed_red_gain);
  sensor_->set_reg(sensor_, kGreenGainReg, kGain16Mask, profile_->seed_green_gain);
  sensor_->set_reg(sensor_, kBlueGainReg, kGain16Mask, profile_->seed_blue_gain);
  // Straight back to auto: the seed is a starting point for AWB to adjust
  // from, not a locked value - the point is to walk from here to whatever
  // is actually correct for the current light, not to fix a single gain
  // forever regardless of conditions.
  if (sensor_->set_wb_mode) sensor_->set_wb_mode(sensor_, 0);
  if (sensor_->set_whitebal) sensor_->set_whitebal(sensor_, 1);
  if (sensor_->set_awb_gain) sensor_->set_awb_gain(sensor_, 1);
  diagnostic = "seeded " + sensor_id_ + " " + manualGainStatus() +
               (profile_->seed_measured ? " (measured seed)" : " (provisional seed, not yet measured on this sensor)");
  return true;
}

namespace {
// OV5640 autofocus MCU registers and sequence, ported from
// sensors/ov5640_af.c in espressif/esp32-camera at commit 1d73d881b (Apache
// 2.0, see include/vendor/README.md). The pinned framework's prebuilt
// camera driver predates that feature, but the sequence needs only the
// public get_reg/set_reg calls already used for white balance above.
constexpr int kAfMcuResetReg = 0x3000;
constexpr int kAfFirmwareBase = 0x8000;
constexpr int kAfCmdMainReg = 0x3022;
constexpr int kAfCmdAckReg = 0x3023;
constexpr int kAfCmdPara0Reg = 0x3024;  // through 0x3028 (PARA4)
constexpr int kAfFwStatusReg = 0x3029;
constexpr int kAfCmdRelease = 0x08;
constexpr int kAfCmdContinuous = 0x04;
constexpr int kAfStatusIdle = 0x70;
constexpr int kAfStatusFocused = 0x10;
constexpr uint32_t kAfTimeoutMs = 2000;

bool waitForRegister(sensor_t* sensor, int reg, int wanted, uint32_t timeout_ms, int& last) {
  const uint32_t started = millis();
  while (true) {
    last = sensor->get_reg(sensor, reg, 0xFF);
    if (last < 0) return false;
    if (last == wanted) return true;
    if (millis() - started > timeout_ms) return false;
    delay(5);
  }
}

// 0x00-0x0F and 0x80-0x8F are the firmware's "focusing" states.
bool isFocusingOrFocused(int status) {
  return status == kAfStatusFocused || (status & 0x70) == 0x00;
}

String hexByte(int value) {
  return "0x" + String(value & 0xFF, HEX);
}
}  // namespace

bool CameraService::startAutofocus(String& diagnostic) {
  if (sensor_ == nullptr || sensor_->set_reg == nullptr || sensor_->get_reg == nullptr) {
    diagnostic = "unavailable: no register access";
    return false;
  }
  const uint32_t started = millis();
  // Hold the AF MCU in reset, write its firmware, clear the command
  // registers, then release it and wait for it to report idle.
  if (sensor_->set_reg(sensor_, kAfMcuResetReg, 0xFF, 0x20) < 0) {
    diagnostic = "unavailable: MCU reset write failed";
    return false;
  }
  for (size_t index = 0; index < sizeof(ov5640_af_firmware); ++index) {
    if (sensor_->set_reg(sensor_, kAfFirmwareBase + static_cast<int>(index), 0xFF, ov5640_af_firmware[index]) < 0) {
      diagnostic = "unavailable: firmware write failed at byte " + String(static_cast<unsigned>(index));
      return false;
    }
  }
  sensor_->set_reg(sensor_, kAfCmdMainReg, 0xFF, 0x00);
  sensor_->set_reg(sensor_, kAfCmdAckReg, 0xFF, 0x00);
  for (int reg = kAfCmdPara0Reg; reg < kAfFwStatusReg; ++reg) sensor_->set_reg(sensor_, reg, 0xFF, 0x00);
  sensor_->set_reg(sensor_, kAfFwStatusReg, 0xFF, 0x7F);
  sensor_->set_reg(sensor_, kAfMcuResetReg, 0xFF, 0x00);
  int last = 0;
  if (!waitForRegister(sensor_, kAfFwStatusReg, kAfStatusIdle, kAfTimeoutMs, last)) {
    diagnostic = "unavailable: AF firmware did not start (status " + hexByte(last) + ")";
    return false;
  }
  const uint32_t loaded_ms = millis() - started;

  // Release any held lens position, then start continuous AF. Each command
  // uses the full handshake: set ACK, write the command, wait for the MCU to
  // clear ACK. Espressif's sequence sends the release without setting ACK
  // first, so its wait passes immediately and the continuous command can
  // arrive while the MCU is still busy - on the first hardware boot (1
  // October 2026) that left the continuous command unacknowledged.
  for (const int command : {kAfCmdRelease, kAfCmdContinuous}) {
    sensor_->set_reg(sensor_, kAfCmdAckReg, 0xFF, 0x01);
    sensor_->set_reg(sensor_, kAfCmdMainReg, 0xFF, command);
    if (!waitForRegister(sensor_, kAfCmdAckReg, 0x00, kAfTimeoutMs, last)) {
      const int fw_status = sensor_->get_reg(sensor_, kAfFwStatusReg, 0xFF);
      // Observed on this module (1 October 2026): the continuous command
      // leaves ACK set while the MCU reports 0x00 "focusing" - it accepted
      // the command and is running, it just does not clear ACK in
      // continuous mode. Accept a focusing/focused status as proof instead.
      if (command == kAfCmdContinuous && fw_status >= 0 && isFocusingOrFocused(fw_status)) {
        autofocus_running_ = true;
        diagnostic = "continuous (firmware loaded in " + String(loaded_ms) + " ms; running without ack, status " +
                     hexByte(fw_status) + ")";
        return true;
      }
      diagnostic = "unavailable: command " + hexByte(command) + " not acknowledged (ack " + hexByte(last) +
                   ", status " + hexByte(fw_status) + ", firmware loaded in " + String(loaded_ms) + " ms)";
      return false;
    }
  }
  autofocus_running_ = true;
  diagnostic = "continuous (firmware loaded in " + String(loaded_ms) + " ms)";
  return true;
}

String CameraService::autofocusStatus() const {
  if (!autofocus_running_ || sensor_ == nullptr) return autofocus_note_;
  const int status = sensor_->get_reg(sensor_, kAfFwStatusReg, 0xFF);
  if (status < 0) return "continuous, status unreadable";
  if (status == kAfStatusFocused) return "continuous, focused";
  if (status == kAfStatusIdle) return "continuous, idle";
  return "continuous, focusing (status " + hexByte(status) + ")";
}
