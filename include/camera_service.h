#pragma once

#include <Arduino.h>
#include <esp_camera.h>

#include "app_config.h"

class CameraService {
 public:
  bool begin(const AppConfig& config, String& diagnostic);
  camera_fb_t* capture(String& diagnostic);
  void release(camera_fb_t* frame);
  const String& sensorId() const;

 private:
  String sensor_id_ = "uninitialised";
};
