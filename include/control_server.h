#pragma once

#include <Arduino.h>
#include <WebServer.h>

// Phase 1 (docs/device-control-app-plan.md): a status-only control app served
// over the device's own Wi-Fi access point. Handlers never touch the SD card
// or the camera; they only read the ControlStatus snapshot the main loop
// publishes each cycle. Commands, configuration, and preview frames are later
// phases and are not implemented here.
struct ControlStatus {
  String state = "starting";
  String run_id;
  uint32_t capture_count = 0;
  uint32_t saved_count = 0;
  uint32_t elapsed_ms = 0;
  bool sd_mounted = false;
  String error;
};

class ControlServer {
 public:
  bool begin(String& diagnostic);
  void update(const ControlStatus& status);
  void handleClient();
  const String& apSsid() const;

  // The HTTP handler only sets a flag and returns; it never touches the SD
  // card or the camera. The main loop is the sole reader, and only acts on
  // it between captures, so a stop can never land mid-write. Consuming the
  // flag on read means a request is only ever acted on once.
  bool consumeStopRequest();

 private:
  void handleRoot();
  void handleStatus();
  void handleStop();

  WebServer server_{80};
  ControlStatus status_;
  String ap_ssid_;
  bool started_ = false;
  volatile bool stop_requested_ = false;
};
