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
  // Stable, translatable identifier for the subset of fatal_error cases the
  // phone app's own translation table knows how to render (see main.cpp's
  // storage-mount-failure branch) - empty for every other fatal_error, which
  // still shows via `error` as raw, untranslated diagnostic text.
  String error_code;
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
  // The WPA2 password for the AP. Fixed and shared across every device by
  // deliberate decision (see ADR 0001) - not a per-device secret. Printed to
  // serial at boot; the same value the enclosure's QR-code sticker encodes.
  const String& apPassword() const;

  // The HTTP handler only sets a flag and returns; it never touches the SD
  // card or the camera. The main loop is the sole reader, and only acts on
  // it between captures, so a stop can never land mid-write. Consuming the
  // flag on read means a request is only ever acted on once.
  bool consumeStopRequest();

  // Copies a JPEG into a PSRAM frame slot that is neither the latest frame
  // nor the one the preview worker is decoding, then publishes it as the
  // latest. The copy happens before publishing, so the worker only ever sees
  // complete frames. No SD access, no camera reconfiguration. Returns false
  // when the frame is larger than a slot (the peek keeps the older frame),
  // so the caller can say so rather than the peek going stale silently.
  bool updatePeek(const uint8_t* data, size_t length, uint16_t width, uint16_t height);

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
  static void previewTaskEntry(void* self);
  void previewTaskLoop();
  bool buildPeekPreview(int slot, uint8_t*& jpeg_out, size_t& length_out, String& error);

  // Holds a full retained frame. 250 KB was enough for OV3660 QXGA (~100 KB)
  // but not for OV5640 in daylight, measured 105-445 KB (run_000019, 2
  // October 2026): larger frames were silently skipped and the peek looked
  // intermittent. Three slots in PSRAM (~7 MB free): the latest frame, the
  // one being decoded, and the one being written.
  static constexpr size_t kPeekBufferCapacity = 512 * 1024;
  static constexpr int kPeekSlots = 3;
  // The peek sends a downscaled re-encode of the latest frame, not the full
  // JPEG: a 300-450 KB transfer over the SoftAP blocks the main loop for its
  // whole duration and timed out on phones. Decoding a QXGA frame takes ~2.1
  // s, which in the request handler cost ~2 retained frames per tap (2
  // October 2026, run_000024), so a low-priority task on core 0 builds it in
  // the background instead, only while someone has asked for a peek
  // recently. The handler just copies out the newest finished preview.
  static constexpr uint32_t kPeekActiveWindowMs = 30000;
  // A preview of an older frame than this is not shown as "what the camera
  // sees right now"; the page retries until a fresher one is ready.
  static constexpr uint32_t kPeekMaxAgeMs = 6000;
  // Decode scale is the largest of 1/2, 1/4, 1/8 that keeps at least this
  // many pixels across (QXGA -> 512x384).
  static constexpr uint16_t kPeekPreviewMinWidth = 400;
  static constexpr uint8_t kPeekPreviewQuality = 80;

  WebServer server_{80};
  DNSServer dns_server_;
  ControlStatus status_;
  String ap_ssid_;
  String ap_password_;
  bool started_ = false;
  volatile bool stop_requested_ = false;
  // Frame slots. latest/pinned and every field below them are guarded by
  // peek_mutex_; slot contents are written only while a slot is neither
  // latest nor pinned, so the 0.5 MB copy itself runs outside the lock.
  struct PeekFrame {
    uint8_t* data = nullptr;
    size_t length = 0;
    uint16_t width = 0;
    uint16_t height = 0;
    uint32_t sequence = 0;
    uint32_t captured_ms = 0;
  };
  PeekFrame peek_frames_[kPeekSlots];
  int peek_latest_slot_ = -1;
  int peek_pinned_slot_ = -1;
  uint32_t peek_next_sequence_ = 1;
  SemaphoreHandle_t peek_mutex_ = nullptr;
  TaskHandle_t preview_task_ = nullptr;
  volatile uint32_t peek_last_request_ms_ = 0;
  // Newest finished preview (owned here, replaced by the worker).
  uint8_t* preview_jpeg_ = nullptr;
  size_t preview_jpeg_length_ = 0;
  uint32_t preview_sequence_ = 0;
  uint32_t preview_captured_ms_ = 0;
  // Worker-only scratch (RGB565 decode target) and handler-only send copy.
  uint8_t* preview_rgb_ = nullptr;
  size_t preview_rgb_capacity_ = 0;
  uint8_t* peek_send_buffer_ = nullptr;
  size_t peek_send_capacity_ = 0;
  String effective_config_json_ = "{}";
  String pending_config_write_;
  volatile bool config_write_pending_ = false;
};
