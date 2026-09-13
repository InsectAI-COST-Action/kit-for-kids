#include "camera_service.h"

#include <cstring>

#include <esp32-hal-psram.h>
#include <sensor.h>

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
}

framesize_t CameraService::captureFrameSize() const {
  if (config_.frame_size == "QXGA") return FRAMESIZE_QXGA;
  if (config_.frame_size == "SVGA") return FRAMESIZE_SVGA;
  return FRAMESIZE_VGA;
}

bool CameraService::initialiseCamera(pixformat_t pixel_format, framesize_t frame_size, String& diagnostic) {
  // The ESP32 camera driver allocates DMA/frame buffers at esp_camera_init time.
  // Changing only OV3660 sensor registers left JPEG-sized buffers active for a
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
  camera_config.xclk_freq_hz = 20000000;
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
  sensor_id_ = sensor_->id.PID == OV3660_PID ? "OV3660" : "unexpected_pid_" + String(sensor_->id.PID);
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
  diagnostic = "OV3660 ready for retained JPEG capture";
  return true;
}

bool CameraService::configurePreviewSensor(String& diagnostic) {
  if (!initialiseCamera(PIXFORMAT_GRAYSCALE, FRAMESIZE_QQVGA, diagnostic)) return false;
  diagnostic = "OV3660 ready for grayscale motion preview";
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
  if (ready) diagnostic = "camera initialised: " + sensor_id_ + (config_.motion_trigger_enabled ? " (motion preview ready)" : "");
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

String CameraService::whiteBalanceStatus() const {
  if (sensor_ == nullptr) return "no sensor";
  return "awb=" + String(sensor_->status.awb) + " awb_gain=" + String(sensor_->status.awb_gain) +
         " wb_mode=" + String(sensor_->status.wb_mode);
}

namespace {
// Confirmed from sensors/ov3660.c in espressif/esp32-camera (31 August
// 2026) - not guessed. 0x3400/0x3402/0x3404 are 16-bit R/G/B manual gain
// registers; set_wb_mode()'s fixed presets (sunny/cloudy/office/home)
// write these same three. 0x3406 is the manual/auto latch: bit 0 set
// means "use the manual values below", clear means auto AWB drives them.
constexpr int kRedGainReg = 0x3400;
constexpr int kGreenGainReg = 0x3402;
constexpr int kBlueGainReg = 0x3404;
constexpr int kManualLatchReg = 0x3406;
// mask > 0xFF routes CameraService's get_reg/set_reg calls through the
// driver's 16-bit register path (write_reg16/read_reg16) rather than an
// 8-bit single-register access - see set_reg's own mask-width branching
// in ov3660.c.
constexpr int kGain16Mask = 0xFFFF;
}  // namespace

String CameraService::manualGainStatus() const {
  if (sensor_ == nullptr || sensor_->get_reg == nullptr) return "no register access";
  const int r = sensor_->get_reg(sensor_, kRedGainReg, kGain16Mask);
  const int g = sensor_->get_reg(sensor_, kGreenGainReg, kGain16Mask);
  const int b = sensor_->get_reg(sensor_, kBlueGainReg, kGain16Mask);
  return "gain r=" + String(r) + " g=" + String(g) + " b=" + String(b);
}

bool CameraService::seedWhiteBalance(uint16_t r_gain, uint16_t g_gain, uint16_t b_gain, String& diagnostic) {
  if (sensor_ == nullptr || sensor_->set_reg == nullptr) {
    diagnostic = "no register access available to seed white balance";
    return false;
  }
  // Manual mode just long enough to latch the seed values - mirrors
  // exactly what set_wb_mode()'s own presets do internally, confirmed
  // from source rather than assumed.
  sensor_->set_reg(sensor_, kManualLatchReg, 0xFF, 1);
  sensor_->set_reg(sensor_, kRedGainReg, kGain16Mask, r_gain);
  sensor_->set_reg(sensor_, kGreenGainReg, kGain16Mask, g_gain);
  sensor_->set_reg(sensor_, kBlueGainReg, kGain16Mask, b_gain);
  // Straight back to auto: the seed is a starting point for AWB to adjust
  // from, not a locked value - the point is to walk from here to whatever
  // is actually correct for the current light, not to fix a single gain
  // forever regardless of conditions.
  if (sensor_->set_wb_mode) sensor_->set_wb_mode(sensor_, 0);
  if (sensor_->set_whitebal) sensor_->set_whitebal(sensor_, 1);
  if (sensor_->set_awb_gain) sensor_->set_awb_gain(sensor_, 1);
  diagnostic = "seeded " + manualGainStatus();
  return true;
}
