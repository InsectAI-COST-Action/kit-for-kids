#pragma once

#include <Arduino.h>
#include <functional>

#include "sd_storage.h"

// A line-based command interface over the existing USB serial link, so the
// SD card can be inspected and modified while it stays in the board. This
// exists for unattended/remote development: without it, every card change
// needs someone physically present to move the card to a reader.
//
// Deliberately built on serial rather than USB mass storage or Wi-Fi: serial
// is the one channel already proven to work here, and it cannot interfere
// with flashing. Losing the ability to flash during unattended work would
// strand the board entirely.
//
// Commands are plain text lines beginning with "DEV ". Replies are framed so
// they can be picked out of ordinary log output:
//
//   <DEV OK>            success, no payload
//   <DEV OK n>          success, n payload lines follow, then <DEV END>
//   <DEV ERR message>   failure
//
// File payloads are hex-encoded, which survives any serial filtering and is
// trivial to decode. Files stream in bounded chunks so a large capture log
// never has to fit in RAM.
struct DevBridgeContext {
  SdStorage* storage = nullptr;
  bool capturing = false;                 // a session is actively writing
  std::function<void()> stop_session;     // finish + unmount, safely
};

class DevBridge {
 public:
  // Reads any pending serial input and executes at most one command per
  // call. Intended to be polled from the main loop between captures, so
  // card access never overlaps a capture write.
  void poll(const DevBridgeContext& context);

 private:
  void execute(const String& line, const DevBridgeContext& context);
  void commandList(const String& path, const DevBridgeContext& context);
  void commandRead(const String& path, const DevBridgeContext& context);
  void commandWrite(const String& path, uint32_t byte_count, const DevBridgeContext& context);
  void commandRemove(const String& path, const DevBridgeContext& context);
  void commandFree(const DevBridgeContext& context);
  // Computed on-device so a remote audit never needs to pull captures.csv or
  // the image tree itself over serial - only a small summary crosses the
  // wire. Sized for the checks audit_card.py/camera_trial_report.py make
  // from a mounted card; see docs/dev-bridge.md for exact scope/parity.
  void commandAudit(const String& run_id, const DevBridgeContext& context);
  void commandRuns(const DevBridgeContext& context);

  String buffer_;
};
