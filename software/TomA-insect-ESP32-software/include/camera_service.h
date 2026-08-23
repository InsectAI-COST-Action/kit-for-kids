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
