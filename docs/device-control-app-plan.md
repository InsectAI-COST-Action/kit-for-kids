# Device control app: technical plan

Implementation plan for the device-hosted control app authorised by [ADR 0001](adr/0001-device-hosted-control-app.md). Read that first for scope boundaries and what this deliberately excludes.

This is a working plan with acceptance gates, not a specification of finished behaviour. Update it as phases complete.

## Design principles

1. **The control app carries control data only.** Status, configuration, lifecycle commands, and at most one still frame at a time. Bulk image data never crosses Wi-Fi.
2. **The capture loop owns the SD card.** HTTP handlers never touch the card, the camera, or the logger directly.
3. **The card workflow never depends on the network.** If Wi-Fi fails entirely, the device still captures and the SD dashboard still works.
4. **The firmware remains the final validator.** The app may only offer configurations the firmware accepts, and the firmware re-validates on boot regardless.

## Architecture

### Concurrency: command queue, single SD owner

HTTP handlers run in the web-server task; capture runs in the main loop. Rather than guarding the SD card with mutexes — where lock ordering is easy to get wrong and the cost of an error is a corrupted card — handlers **enqueue a command and return immediately**. The main loop drains the queue *between* captures, so commands can only take effect at points already known to be safe.

```
HTTP task                     Main loop (single SD owner)
---------                     ---------------------------
POST /api/stop
  push CMD_STOP  ----------->  ... finish in-flight capture
  return 202 Accepted          drain queue
                               CMD_STOP -> finishSession() -> SD.end()
                               state = SAFE_TO_REMOVE
GET /api/status
  read status struct <-------  main loop publishes status each cycle
  return JSON
```

Status is a small struct the main loop republishes each cycle; handlers only read it. The one shared buffer needing care is the peek frame (below).

**Implementation note (Phase 2):** with a synchronous single-task `WebServer` (see Network, below), the HTTP handler and the main loop already never run concurrently, so the "queue" for the one command implemented so far (`CMD_STOP`) is a single `volatile bool` set by the handler and consumed once by the main loop between captures — no actual FreeRTOS queue was needed. Revisit if a real queue becomes necessary once multiple command types exist.

### The UI lives in flash, not on the card

The control app is embedded in the firmware binary and served from flash. This matters for a specific reason: **after a safe stop the card is unmounted**, and that is exactly the moment the UI must still be able to say "safe to unplug now". Serving it from the card would make the interface disappear at its most important moment. It also removes SD reads from the serving path entirely.

Budget: the current build uses 11.2% of a 3.67 MB application partition, so there is ample room. Target under 30 KB uncompressed, served gzipped.

**Hard constraint:** a phone joined to the camera's AP has **no internet**. No web fonts, no CDN, no external resources of any kind — the same discipline the SD dashboard already follows. System fonts only.

### Preview frames from PSRAM

"Take a peek" serves **the most recent captured frame, retained in PSRAM** — not a fresh capture. This costs no SD read and no camera reconfiguration; at a one- or two-second interval it is effectively live. The frame is copied to a PSRAM buffer immediately after capture (roughly 100 KB at QXGA, a few milliseconds against a 1,000 ms budget).

Use **double buffering** with an atomic index swap so a peek request cannot read a buffer the capture loop is overwriting.

An explicit **"fresh photo"** action remains available for long capture intervals, but it is a queued command, not a direct handler action, and carries two rules:

- A peek is **never written to the card and never logged as a capture.** `captures.csv` remains the record of scheduled captures only.
- If motion mode is enabled, a fresh capture **must re-baseline the motion preview afterwards** (the existing `refreshMotionBaseline()` settle path). Skipping this causes a false motion trigger on the very next check — the failure mode already documented in the motion-detection work.

### Network

- **SoftAP**, WPA2-protected. An open AP would let any nearby device stop a run.
- SSID derived from the device MAC: `InsectCam-XXXX`, so multiple kits in one classroom do not collide.
- Fixed IP `192.168.4.1`. Do **not** depend on mDNS/`.local` — unreliable on Windows without Bonjour.
- **Implemented with `WebServer` from the Arduino-ESP32 core** (synchronous, single-task), not raw `esp_http_server` as originally planned. No new PlatformIO dependency either way; `WebServer` was simpler to reach for in the Arduino framework and its synchronous, one-request-at-a-time model is exactly what the single-SD-owner design wants — handlers run to completion on the same task as capture, so a plain flag does the job a command queue was planned for. Revisit only if concurrent-request handling becomes a real need.

### Access via QR code

The enclosure carries a printed QR code encoding Wi-Fi credentials in the standard format, which both iOS and Android join directly from the camera app:

```
WIFI:S:InsectCam-A7B3;T:WPA;P:<device-password>;;
```

A captive-portal DNS responder then redirects the phone's automatic connectivity check to the control app, so the page opens without anyone typing an IP address. Captive-portal behaviour varies across platforms, so `192.168.4.1` must remain documented as the fallback and be printed alongside the QR code.

## HTTP interface

Small, boring, and stable. All responses JSON except `/` and `/api/peek`.

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| `GET` | `/` | Control app | From flash, gzipped |
| `GET` | `/api/status` | State, counts, elapsed time, recent motion scores | Polled every ~2 s |
| `GET` | `/api/peek` | Most recent frame as JPEG | From PSRAM; no SD access |
| `POST` | `/api/peek/fresh` | Queue a fresh capture for preview | Not saved, not logged |
| `GET` | `/api/config` | Current effective configuration | |
| `POST` | `/api/config` | Replace `config.json` | Rejected while capturing; validated set only |
| `POST` | `/api/stop` | Safe stop | `202 Accepted`; poll status for completion |
| `POST` | `/api/start` | Begin a new run | Only from an idle/finished state |

`/api/status` returns roughly:

```json
{
  "state": "capturing",
  "runId": "run_000003",
  "captureCount": 312,
  "savedCount": 47,
  "elapsedMs": 624000,
  "sdMounted": true,
  "motionRecent": [0.6, 1.2, 5.8, 0.4],
  "freeHeap": 210000
}
```

`motionRecent` is a short ring buffer of recent motion scores. It costs nothing — the values are already computed — and it drives the live "is anything moving?" meter in the UI, which doubles as a real tuning instrument for the outstanding motion-threshold work.

## Safe-stop sequence

The reason this project exists. Each step is already implemented except the unmount.

1. Phone `POST /api/stop`; handler enqueues `CMD_STOP`, returns `202`.
2. Main loop completes any in-flight capture — commands never land mid-write.
3. `logger.finish()`: promote the open dashboard chunk, write manifest and summary, mark the run `finished`, clear `active_run.txt`. *(existing, proven path)*
4. **`SD.end()`** — explicit unmount, forcing the final FAT flush. *(new; this is the step whose absence caused the 21 August corruption)*
5. State becomes `SAFE_TO_REMOVE`; the UI shows an unmistakable "safe to unplug" confirmation.
6. Operator disconnects power and removes the card.

**Honest limitation:** this does not make corruption impossible, because a child can still pull the cable at any moment. It makes the safe path available, easy, and more rewarding than the unsafe one. Atomic-write discipline and the hardware hold-up-capacitor question in the project brief both still stand.

## Phases and gates

Each gate must pass before the next phase begins. A failed gate returns to [ADR 0001](adr/0001-device-hosted-control-app.md) for revision rather than being worked around.

### Phase 1 — Serve a status page — DONE (21 August 2026)

SoftAP with WPA2, `WebServer` (Arduino-ESP32 core, no new dependency), UI from flash, `GET /api/status`. No SD interaction, no camera interaction, no commands.

Implemented in `include/control_server.h` / `src/control_server.cpp`, wired into `src/main.cpp`. Wi-Fi starts before any SD/camera/logger step, so the control app stays reachable and reports what failed even if the card is missing or a fatal setup error occurs (`state: "error"` with a message) — this was found and fixed during Phase 1 testing; the original ordering made Wi-Fi depend on the card, which defeated the point of having a status page.

**Gate: NOT fully met — reopened 21 August 2026.** Page load, live status, cadence, and heat all checked out. But a card audit after two live Wi-Fi test sessions (`run_000002`, `run_000003`, both post-reformat) showed **100% of motion checks triggered a save in both runs — zero `motion_not_detected` outcomes**, with scores clustering just above threshold (5.8–12) rather than the wide spread seen in the pre-Wi-Fi acceptance run (`run_000002` from the 21 August motion-mode fix, ~10% save rate, scores up to 89).

Two candidate explanations, and the comparison above does **not** distinguish them because both variables changed at once between the "before" and "after" runs:

1. **Environmental confound.** Testing moved from daylight to dark-outside-with-indoor-lighting between the two comparisons. Flickering indoor lighting (LED PWM dimming in particular) is a well-known false-trigger source for frame-differencing motion detectors and has nothing to do with Wi-Fi.
2. **Wi-Fi/radio interference.** SoftAP TX bursts draw meaningful current spikes; if that shows up as exposure micro-flicker, the motion score's whole-frame brightness correction may not fully cancel it.

**Resolved 21 August 2026: confirmed Wi-Fi, not lighting.** A same-scene control test (`run_000004`) with `control_server.begin()` disabled via a temporary `WIFI_CONTROL_DISABLED_FOR_TEST` build flag, everything else identical, showed 131 of 132 checks correctly returning `motion_not_detected`, scores maxing at 3.57 — well under threshold 5, and consistent in character with the original clean pre-Wi-Fi acceptance run. Same dark/indoor-lit scene as the two 100%-trigger runs; only Wi-Fi differed. This rules out the lighting-confound hypothesis and confirms **Wi-Fi/SoftAP radio activity measurably degrades motion-detection accuracy** on this hardware, most likely via power-rail noise showing up as exposure micro-flicker that the motion score's whole-frame brightness correction does not fully cancel.

**This gate cannot close as originally scoped.** Wi-Fi and motion-triggered capture cannot currently run together without breaking the motion detector. Before Phase 1 can be considered done, one of the following needs to happen:

- **Isolate the interference** — investigate power supply filtering/decoupling near the camera, reduce Wi-Fi TX power, enable modem sleep between HTTP polls, or move preview-frame timing away from TX bursts. Unproven whether any of this is sufficient without further hardware-level investigation.
- **Retune the motion detector to tolerate it** — widen the brightness-correction tolerance or threshold while Wi-Fi is active. Risks masking real motion along with the noise.
- **Don't run them together** — restrict Wi-Fi to a non-capturing review/setup window (device boots normally, capture-only; Wi-Fi and control only available in an explicit non-motion "review mode" between sessions). This changes the always-available "stop at any time" design goal and needs an owner decision if pursued.

Retain-every-frame sessions are unaffected by this finding, since they have no motion comparison to disturb. The safe-stop mechanism (Phase 2) itself is unaffected and remains validated independently — this finding is specific to motion-triggered capture running *concurrently* with Wi-Fi, not to the control app generally.

Not yet tested: iPhone/Safari. Not yet measured: current draw (hand-feel-warm check only so far).

### Phase 2 — Safe stop — BUILT, gate partially exercised (21 August 2026)

Implemented: a `volatile bool` flag set by the `POST /api/stop` handler and consumed only by the main loop between captures (no FreeRTOS queue needed — `WebServer::handleClient()` and capture already run on the same task, so a flag alone gives the same "only at safe points" guarantee the plan called for). `SdStorage::end()` added (`SD.end()`) and now called unconditionally from `finishSession()`, both on a phone-triggered stop and on the existing `max_session_seconds` timeout path, since the timeout path had the same unmount gap. New `safe_to_remove` status state drives the phone UI's confirmation screen.

**Gate:** exercised twice live (not yet the full 20 cycles) — both stops produced `state: "finished"` manifests (`run_000002`, `run_000003`), `py tools\audit_card.py` clean (730/730 images accounted for, only pre-existing warning was an orphaned `.tmp` from the earlier `run_000001` crash, predating this work), zero storage errors. Remaining before this gate is formally closed: run the rest of the 20-cycle count, and confirm behaviour when the phone disconnects/sleeps mid-stop (fire-and-forget from the client side, believed safe since the device acts on the request regardless of whether the response is received, but not yet deliberately tested).

*This phase is where the corruption risk is actually retired. Everything after it is convenience.* The UI's "Packing up…" wait (observed ~10s, dominated by dashboard-chunk promotion and unmount) has no real progress signal yet since the device can't serve HTTP while `finishSession()` blocks the loop — an indeterminate spinner was added for now; real incremental progress would need `finishSession()` broken into steps that yield back to `handleClient()`, not yet done.

**Known blocker carried from Phase 1:** motion-triggered capture cannot currently run at the same time as Wi-Fi (see Phase 1 above). Phase 2's safe-stop mechanism itself is unaffected by that finding and works correctly in both motion and retain-every-frame sessions; it's specifically motion *scoring accuracy* that breaks when Wi-Fi is active.

### Phase 3 — Peek and live motion

PSRAM double-buffered last frame, `GET /api/peek`, `motionRecent` in status, queued fresh capture.

**Gate:** peeks during an active session cause no cadence disruption, no storage errors, and no false motion triggers; motion meter matches the values later found in `captures.csv`.

### Phase 4 — Configuration

`GET`/`POST /api/config`, `POST /api/start`, arm/idle state.

**Gate:** every offered preset round-trips and survives a reboot; invalid configurations are rejected by firmware; the manifest records effective settings.

### Phase 5 — Access and enclosure integration

QR code, captive portal, device-specific password, printed fallback IP.

**Gate:** a person who has not seen the device before gets from QR scan to a working control app on both a named Android and a named iPhone, without being told an IP address.

## Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Concurrent SD access corrupting the card | High | Command queue; main loop is sole SD owner; handlers never touch the card |
| Wi-Fi radio activity breaks motion detection (100% false-trigger rate, confirmed 21 Aug via same-scene control test) | High, confirmed | Not yet mitigated. See Phase 1 write-up for options: isolate the interference, retune detection tolerance, or don't run Wi-Fi and motion capture concurrently |
| Thermal build-up from an active radio in a sealed enclosure | Medium | Measure in Phase 1 before building further; consider modem sleep or reduced TX power |
| Phone drops the AP for having "no internet" | Medium | Captive portal; documented fallback IP; test on named devices |
| Peek buffer read during overwrite | Medium | Double buffer with atomic index swap |
| Fresh capture triggering false motion save | Medium | Mandatory re-baseline after any out-of-band capture |
| Wi-Fi work displacing the pilot critical path | Medium | Endurance test, browser matrix, and battery smoke test stay ahead of this track |
| Open AP allowing a stranger to stop a run | Low | WPA2 with per-device password |

## Open questions

- Should Wi-Fi be on for the whole session, or only for a window after boot? Always-on is required for stop-at-any-time to work, which argues for always-on unless thermal measurements say otherwise.
- Should the device auto-start capture on power-up (current behaviour, and what the brief's "power on and walk away" requires), or wait to be armed from the phone? Default should stay auto-start, with manual arm as an option.
- Does the peek frame need downscaling before entering the PSRAM buffer, or is a full QXGA JPEG acceptable over Wi-Fi to a phone?

## Related

- [ADR 0001](adr/0001-device-hosted-control-app.md) — the decision and its scope boundary
- [hardware-validation.md](hardware-validation.md) — the corruption incident that motivated this
- [project-brief.md](project-brief.md) — must be updated to record the scope change
- [next-session.md](next-session.md) — current priorities; this track runs alongside, not instead of, pilot acceptance
