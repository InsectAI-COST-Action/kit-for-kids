#include "camera_service.h"

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

bool CameraService::begin(const AppConfig& config, String& diagnostic) {
  if (!psramFound()) {
    diagnostic = "PSRAM unavailable; camera capture is disabled";
    return false;
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
  camera_config.pixel_format = PIXFORMAT_JPEG;
  if (config.frame_size == "QXGA") {
    camera_config.frame_size = FRAMESIZE_QXGA;
  } else if (config.frame_size == "SVGA") {
    camera_config.frame_size = FRAMESIZE_SVGA;
  } else {
    camera_config.frame_size = FRAMESIZE_VGA;
  }
  camera_config.jpeg_quality = config.jpeg_quality;
  camera_config.fb_count = 1;
  camera_config.fb_location = CAMERA_FB_IN_PSRAM;
  camera_config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  const esp_err_t err = esp_camera_init(&camera_config);
  if (err != ESP_OK) {
    diagnostic = "esp_camera_init failed: " + String(static_cast<int>(err));
    return false;
  }
  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor == nullptr) {
    diagnostic = "camera initialised but sensor descriptor is unavailable";
    return false;
  }
  sensor_id_ = sensor->id.PID == OV3660_PID ? "OV3660" : "unexpected_pid_" + String(sensor->id.PID);
  diagnostic = "camera initialised: " + sensor_id_;
  return true;
}

camera_fb_t* CameraService::capture(String& diagnostic) {
  camera_fb_t* frame = esp_camera_fb_get();
  if (frame == nullptr) diagnostic = "camera frame buffer unavailable";
  return frame;
}

void CameraService::release(camera_fb_t* frame) {
  if (frame != nullptr) esp_camera_fb_return(frame);
}

const String& CameraService::sensorId() const { return sensor_id_; }


