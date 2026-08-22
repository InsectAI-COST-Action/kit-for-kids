#pragma once

#include <Arduino.h>
#include <DNSServer.h>
#include <WebServer.h>

// Phase 1 (docs/device-control-app-plan.md): a status-only control app served
// over the device's own Wi-Fi access point. Handlers never touch the SD card
// or the camera; they only read the ControlStatus snapshot the main loop
// publishes each cycle. Commands, configuration, and preview frames are later
// phases and are not implemented here.
struct ControlStatus {
  static constexpr uint8_t kMotionHistoryCapacity = 20;

  String state = "starting";
  String run_id;
  uint32_t capture_count = 0;
  uint32_t saved_count = 0;
  uint32_t elapsed_ms = 0;
  bool sd_mounted = false;
  String error;
  // Most recent motion scores, oldest first. Costs nothing extra to compute
  // since the value already exists per check; drives a live "is anything
  // moving?" view without exposing any image data.
  float motion_recent[kMotionHistoryCapacity] = {};
  uint8_t motion_recent_count = 0;
};

class ControlServer {
 public:
  bool begin(String& diagnostic);
  void update(const ControlStatus& status);
  void handleClient();
  const String& apSsid() const;
  // The WPA2 password for this device's AP, derived from its MAC address at
  // begin(). Printed to serial at boot; the same value is what the QR-code
  // sticker on the enclosure needs to encode (Phase 5, not yet printed).
  const String& apPassword() const;

  // The HTTP handler only sets a flag and returns; it never touches the SD
  // card or the camera. The main loop is the sole reader, and only acts on
  // it between captures, so a stop can never land mid-write. Consuming the
  // flag on read means a request is only ever acted on once.
  bool consumeStopRequest();

  // Copies a JPEG into the inactive PSRAM buffer and swaps it live. Safe to
  // call from the main loop right after a capture; readers (handlePeek())
  // only ever see a buffer that is either fully written or not yet swapped
  // in, never a half-written one, since the index only moves after the copy
  // completes. No SD access, no camera reconfiguration.
  bool updatePeek(const uint8_t* data, size_t length);

  // Called once after the effective configuration is known (post-validation,
  // not the raw file), so GET /api/config reports what firmware actually
  // loaded rather than what a malformed file on disk might have said.
  void setEffectiveConfig(const String& json);

  // Same pattern as consumeStopRequest(): the handler only validates and
  // queues; the main loop performs the actual SD write between captures.
  // config.json is never touched by anything else during a session (only
  // read once at boot), so this is safe to consume any time the card is
  // still mounted, including throughout an active capturing session.
  bool consumePendingConfigWrite(String& json_out);

 private:
  void handleRoot();
  void handleStatus();
  void handleStop();
  void handlePeek();
  void handleConfigRead();
  void handleConfigWrite();
  void handleStart();

  static constexpr size_t kPeekBufferCapacity = 250 * 1024;

  WebServer server_{80};
  DNSServer dns_server_;
  ControlStatus status_;
  String ap_ssid_;
  String ap_password_;
  bool started_ = false;
  volatile bool stop_requested_ = false;
  uint8_t* peek_buffers_[2] = {nullptr, nullptr};
  size_t peek_lengths_[2] = {0, 0};
  volatile int peek_active_index_ = -1;
  String effective_config_json_ = "{}";
  String pending_config_write_;
  volatile bool config_write_pending_ = false;
};
