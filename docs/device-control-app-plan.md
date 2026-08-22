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

**Follow-up (22 August 2026): daylight retest, not yet a full control test.** A daylight session with Wi-Fi on (`run_000006`, 586 checks, safe-stopped via the phone) showed normal-looking motion discrimination — ~10% save rate, wide score spread 0.39–16.8 — unlike the two dark-scene 100%-trigger runs from the night before. This points toward the interaction being light/gain-dependent rather than a fixed effect of Wi-Fi, which would make it a more attackable problem. Not yet confirmed: there is no daylight run with Wi-Fi *off* to complete the comparison, so daylight-has-less-to-trigger-on hasn't been ruled out as an alternative explanation. Owner has accepted Phases 1–2 as complete for now regardless, treating the remaining controlled test as a nice-to-have rather than blocking further work.

### Phase 3 — Peek and live motion — BUILT (22 August 2026)

PSRAM double-buffered last frame, `GET /api/peek`, `motionRecent` in status. Implemented in the same files as Phases 1–2. The "fresh photo" queued command (forcing an out-of-band capture rather than showing the last one taken) was **not** built this pass — peek currently only ever shows the most recently *actually* captured frame, which in motion mode can go stale between motion events. Documented in the UI copy rather than solved.

Tested live: both peek and the motion meter work. One finding, not a blocker: the motion meter's updates are visibly uneven — a delay, then several bars appear to update at once. Root cause: `WebServer::handleClient()` and capture share one task, so the device can't respond to a status poll while it's mid-capture — and a real motion *save* (the moments the meter is most interesting) includes an SD write that can take several hundred ms, right when the client is most likely to be polling for a fresh value. The poll catches up afterward with several new ring-buffer entries at once. Mitigated for now with a CSS transition on the bar heights so a multi-step catch-up animates smoothly instead of snapping; the underlying cause (HTTP blocked during capture/SD-write) is unfixed and would need real concurrency to address properly — out of scope for this phase.

**Gate:** peeks during an active session cause no cadence disruption, no storage errors, and no false motion triggers — observed clean. Motion meter matches values later found in `captures.csv` — not yet cross-checked. "No cadence disruption" specifically needs re-confirming given the blocking behaviour just described; nothing observed so far suggests it affects capture timing itself, only HTTP responsiveness.

### Phase 4 — Configuration — DONE for `GET`/`POST /api/config` (22 August 2026)

`GET`/`POST /api/config` implemented and confirmed live on hardware, including surviving a real power cycle (saved setting via phone, restarted the board, new setting was in effect). `POST /api/start` (arm/idle state, starting a new run without a physical reboot) **deferred, not built** — see below.

Implementation note: the plan originally said to reject config writes "while capturing." On reflection that was overcautious and has been relaxed. `config.json` is read exactly once, at boot; nothing else touches it during a session, and the SD storage layer's atomic-write pattern already makes concurrent-ish writes safe. The actual constraint is simply **the card being mounted** — writes are accepted throughout a normal capturing session and rejected only once a safe stop has unmounted the card (`sd_mounted: false`), which matches the existing SD-dashboard settings tool's "takes effect after restart" model. The handler validates and queues; the main loop performs the actual `writeTextAtomic()` between captures, same pattern as the stop command.

The phone UI offers the same four fixed combinations as the SD-card dashboard's settings tool (1/2/30/60 s interval; high/low quality; 1/5/30/60 min or infinite duration; motion toggle), tucked into a collapsible "Grown-up helper" section so it doesn't clutter the child-facing screen.

**`POST /api/start` deferred, but the design is now settled (22 August 2026) and should be cheap to build next time.** Originally scoped as re-running the SD/camera/logger bring-up sequence at runtime from the main loop — rejected on reflection as needlessly risky: `AppConfig`, `SessionLogger` (which itself owns a `DashboardWriter` with its own chunk-tracking state), `CameraService`, the motion-baseline pair, the motion-history ring buffer, and several more globals in `main.cpp` would all need correctly resetting by hand, in a second code path that has never been exercised, duplicating logic that `setup()` already gets right.

**Simpler, safer alternative, implemented same day: `POST /api/start` just calls `ESP.restart()`** after flushing the HTTP response, when `state` is anything except `capturing`/`warming_up` (`409` while those, so an accidental tap can't interrupt a live session — the phone should hit Finish first). Reuses the exact boot sequence already proven for weeks instead of a fresh, untested one. Added a "Start another adventure" button to the safe screen, and fixed a real gap this exposed while building it: `poll()` had no path back to the main screen once the device restarted (it would sit on "safe to unplug" forever) — added an `awaitingRestart` flag so the first successful poll after the reboot returns the UI to the main screen automatically.

**Follow-up (22 August 2026, first live test): saving a setting had no reachable way to apply it.** `POST /api/start` existed but only "Start another adventure" on the post-finish safe screen could call it — there was no path from the settings panel itself, so a saved setting had nowhere to go without a physical power cycle. Fixed: a "Restart now to use this setting" button appears in the settings panel after a successful save. If the device is idle/finished, it calls `/api/start` directly. If a session is actively running, it first asks for confirmation (this ends the current session early), then chains `POST /api/stop` → wait for `safe_to_remove` → `POST /api/start` automatically, client-side — reusing the two already-proven endpoints rather than adding a new "restart while capturing" path in firmware. `handleStart()`'s own validation is unchanged and still rejects a raw restart attempt during `capturing`/`warming_up`.

Built and flashed without a phone to test against — logic reuses already-proven pieces (the stop/start endpoints, the existing `awaitingRestart` recovery path), but the live chained flow itself needs confirming on hardware.

**Bug found on first live test of the restart-now flow (22 August 2026): saved settings were not taking effect after restart.** `GET /api/config` after the reboot showed the old value, not the saved one. Found one real, concrete bug: `main.cpp`'s config-write consumption called `storage.writeTextAtomic("config.json", ...)` — missing the leading slash that `ConfigLoader::load()`'s read path (`"/config.json"`) and every other atomic write in the codebase uses. Fixed and reflashed.

**Confirmed fixed on retest (22 August 2026).** The missing leading slash genuinely was the bug — settings now correctly take effect via the "Restart now" software-restart path. Resolves the earlier open question: the ESP32 SD library does not silently normalize a relative path to root here, so this was a real correctness bug, not a red herring. Worth remembering as a general lesson for this codebase: `fs::FS` paths need the leading slash to match `SD.open()`'s behaviour, and it can fail in a way that's easy to miss (no crash, no fatal error — it silently writes to a location boot-time loading never reads).

**Gate: met, confirmed live.** Config writes round-trip via `GET /api/config`, survive the software-restart (`POST /api/start`) path, and take effect on the next boot as intended. Invalid combinations rejected with `400`; writes rejected with `409` once the card is unmounted. `POST /api/start` and the restart-now flow are built and confirmed working end to end.

### Phase 5 — Access and enclosure integration — FIRMWARE HALF BUILT (22 August 2026)

**Decision (22 August 2026, owner call): fixed, shared Wi-Fi credentials across every device, not per-device.** Originally built as MAC-derived per-device SSID/password; revised same day. Rationale: this ships in quantity to schools, the SD card's contents are not sensitive, and unique-per-device credentials add real manufacturing/support cost (a distinct QR sticker per unit) for no meaningful security benefit in this context. The password is kept — not for confidentiality, but so a teacher can control who joins the network. One shared QR design now works for the entire product line.

- **Network**: SSID `InsectCam`, password `antcamera` (reusing the original Phase 1 placeholder as the permanent value — already exercised through every phase's testing so far). Fixed constants in `control_server.cpp`, no longer derived from the MAC.
- **Known, accepted trade-off**: multiple kits running in the same room broadcast an identical network name. A phone may need to pick the right access point manually if more than one is nearby (they'll differ by signal strength/BSSID even with the same SSID, but iOS/Android don't always surface that clearly). Not mitigated; acceptable for now.
- **Captive-portal DNS redirect**: `DNSServer` (bundled with the Arduino-ESP32 core, no new dependency) answers every DNS query with the device's own IP, and any unrecognised HTTP path also lands on the control app (`server_.onNotFound`). This is what should make a phone's own connectivity-check request (`connectivitycheck.gstatic.com`, `captive.apple.com`) resolve back to the device and trigger an automatic captive-portal pop-up, instead of the phone reporting "no internet" and going no further.
- **QR payload logged at boot**: `WIFI:S:InsectCam;T:WPA;P:antcamera;;`, printed to serial alongside the existing SSID/IP diagnostic.
- **A real QR code has been generated** (`qrcode` Python library, error-correction level M, encoding the exact payload above) and sent to the owner to scan-test directly, ahead of any physical sticker.

**Confirmed working on Android (22 August 2026):** scanning the QR joined the network, and the captive-portal redirect worked — Android showed its standard "Sign in" notification, and tapping it opened the control app without anyone typing an IP address. Note this is Android's normal captive-portal behaviour (notification rather than an automatic browser pop-up); the goal of "never needs to know the IP" is met.

**iPhone/Safari: blocked, no device available.** The project owner does not have an iPhone, so this cannot be tested in-house. iOS handles captive portals differently from Android (it typically auto-opens a restricted mini-browser rather than posting a notification), and that mini-browser has known limitations — it is not full Safari, and can behave differently around JavaScript, `fetch`, and page lifecycle. **This is an untested platform, not a working one**, and needs either borrowed hardware or an external tester before any claim of iOS support. Until then, treat the browser matrix for the control app as Android-only.

**Not yet done, and not attempted without a phone/enclosure:**
- Printing the QR code onto the physical enclosure.
- Confirming the captive-portal auto-open behaviour actually fires on real Android and iPhone hardware — this varies a lot by OS/browser and is exactly the kind of thing that looks correct in code and still doesn't work in practice.
- The printed fallback-IP label for when captive-portal detection doesn't fire.

**Gate: half met.** The Android half is satisfied — QR scan to working control app, no IP address needed. The iPhone half is **blocked on hardware availability**, not on implementation, and must not be assumed to pass by analogy with Android. The physical sticker is also still outstanding.

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
