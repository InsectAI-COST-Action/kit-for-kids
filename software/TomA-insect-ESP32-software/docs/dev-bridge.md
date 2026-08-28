# Serial development bridge

A line-based command channel over the same USB serial link used for flashing, so the SD card can be inspected and changed while it stays inside the board. Built on 27 August 2026 specifically for unattended/remote development: normally a card change means physically moving the card to a reader, which is not possible without someone present.

Deliberately not USB mass storage or Wi-Fi. Serial is the one channel already proven reliable for this board, and reconfiguring the USB stack for MSC risks losing the ability to flash — exactly the wrong failure mode to introduce right before working unattended.

## Safety model

**The main loop is the sole owner of the SD card, same as everywhere else in this firmware.** `DevBridge::poll()` is called once per `loop()` iteration, gated on `ready && !finished` exactly mirroring the condition that gates `captureOnce()` — so a file command can never execute in the same cycle a capture write could happen.

While a session is actively running, `LS`/`CAT`/`PUT`/`RM`/`DF` are refused outright (`"session active; send DEV STOP first"`). Only `PING`, `STOP`, `REBOOT`, and `MOUNT` work at any time. `STOP` reuses the same `finishSession()` → `SD.end()` path the phone app's "Finish" button uses — not a separate shutdown routine, so it inherits whatever safety work has already gone into that path.

Paths must be absolute and may not contain `..`, refused before any filesystem call.

## Protocol

Commands are plain text lines beginning with `DEV `. Replies are framed so they can be picked out of ordinary log output:

```
<DEV OK>            success, no payload
<DEV OK ...>         success, with a short payload
<DEV ERR message>   failure
```

Multi-line responses (`LS`, `CAT`) end with `<DEV END>`. File contents are hex-encoded — this survives any serial line-ending or control-character handling, at the cost of being unsuitable for anything large.

Slow commands (`CAT`, `AUDIT`) may emit `<DEV PROGRESS ...>` frames while working. The client recognises these in both its single-reply and multi-line-payload wait loops, prints them, and resets its own timeout on each one — so a genuinely slow command stays distinguishable from a stalled one instead of the two looking identical while waiting. Added 28 August 2026; see "On-device progress visibility" below for why.

| Command | Effect |
|---|---|
| `PING` | Liveness check |
| `LS <path>` | List a directory |
| `CAT <path>` | Read a file (hex-encoded) |
| `PUT <path> <bytes>` | Write a file (hex-encoded payload follows) |
| `RM <path>` | Delete a file |
| `DF` | Card total/used bytes |
| `AUDIT <run_id>` | On-device summary of one run: image/shard counts, size stats, `captures.csv` row cross-check, capture-interval stats |
| `RUNS` | One line per run manifest: `<run_id> <state>` |
| `MOUNT` | Retry `storage.begin()` |
| `STOP` | Safe stop: `finishSession()` then `SD.end()` |
| `REBOOT` | `ESP.restart()` |

## Client

`tools/dev_bridge_client.py` (needs `pyserial`):

```powershell
py tools\dev_bridge_client.py --port COM4 ping
py tools\dev_bridge_client.py --port COM4 ls /
py tools\dev_bridge_client.py --port COM4 cat /config.json
py tools\dev_bridge_client.py --port COM4 get /raw/captures.csv captures.local.csv
py tools\dev_bridge_client.py --port COM4 get /images/run_000040/shard_0001/run_000040_img_1.jpg sample.jpg
py tools\dev_bridge_client.py --port COM4 put config.local.json /config.json
py tools\dev_bridge_client.py --port COM4 stop
py tools\dev_bridge_client.py --port COM4 mount
py tools\dev_bridge_client.py --port COM4 runs
py tools\dev_bridge_client.py --port COM4 audit run_000041
```

Each invocation opens a fresh connection and closes it afterward - there is no persistent session to keep alive between commands.

## Two problems found and fixed while building this, worth knowing about

**Opening the serial port used to reboot the board.** This board's native USB-CDC wires DTR/RTS to the same reset circuit esptool pulses to reset it for flashing, and pyserial asserts both by default the moment a port opens. The first version of this client silently rebooted the board — and restarted capture - on every single command, which defeated the purpose entirely (each "inspect a file" call would wipe out whatever `STOP` had just achieved). Fixed by constructing the port with `dtr`/`rts` cleared before opening. If this bridge is ever ported to different hardware or a different OS driver, re-verify this — the fix depends on how the specific USB-CDC/reset wiring responds to those lines, not on anything protocol-level.

**Bulk writes silently dropped bytes.** `PUT` originally sent the whole hex payload in a handful of ~1 KB bursts. The ESP32-S3's native USB-CDC has a small receive ring buffer and no hardware flow control, so bytes were lost between bursts with no error on either side - the firmware just waited out its full timeout for a payload that would never complete, and the transfer failed silently rather than loudly. Fixed by pacing the client to 64-byte writes with a 10 ms gap. This is empirical, tuned against one 3 KB test file, not derived from a documented buffer size - if `PUT` ever fails on a larger file, this pacing is the first thing to revisit.

## Scope: small uploads, occasional single-image downloads

The two directions are not symmetric, because only one of them hit the USB-CDC buffer problem above.

**Uploads (`PUT`) stay small.** `kMaxWriteBytes` caps writes at 256 KB in firmware, and the pacing needed to avoid dropping bytes makes anything near that slow (64 bytes/10 ms, roughly a minute for 256 KB). Sized for `config.json`, run manifests, `captures.csv` excerpts, and performance logs.

**Downloads (`GET`/`CAT`) are not paced, fast for single images, and unreliable past roughly a thousand chunks.** An 86,728-byte QXGA JPEG (`run_000040_img_1.jpg`, 170 chunks) transferred in 1.4 s and decoded and rendered correctly, confirmed by eye as well as by checking the JPEG start/end markers. Pulling a single frame off the card for diagnostics - "what is the camera actually seeing right now" without moving the card to a reader - is a legitimate, verified use of this bridge. What it is still not for is bulk retrieval or large single files: see the `captures.csv` stall below - this is a real firmware-side limit, not just a client timeout to tune.

## Remote audit: `AUDIT`/`RUNS` compute on-device rather than transfer raw data

Added 28 August 2026, directly because of the `CAT` stall below: `tools/audit_card.py` and `tools/camera_trial_report.py` both need a mounted local card path and read `raw/captures.csv`/`raw/runs/*.json`/the image tree directly - none of that is available remotely, and pulling those files over the bridge to run the same analysis on the PC is exactly what triggers the stall. `AUDIT`/`RUNS` instead do the equivalent computation **on the ESP32, against the SD card directly** (fast local SPI access, no serial bottleneck) and return only a short summary line - sidestepping the transfer problem rather than fixing it.

**Scope, deliberately narrower than the Python scripts:** `AUDIT <run_id>` reports image/shard counts from directory metadata alone (sizes via `openNextFile()`, no file content read), plus a `captures.csv` scan restricted to that run's rows for a completed-count cross-check and jpeg-size/capture-interval stats (mean, not median - a true median would need buffering every value). It does **not** check `manifest.js`/`data/captures_*.js` chunk consistency or correlate `performance_run_<id>.csv` - use the real scripts against a mounted card for the full audit. `RUNS` lists every run manifest's `run_id`/`state` in one call, directly surfacing the `run_still_marked_running` condition `audit_card.py` also checks for.

**`AUDIT` is slow - budget minutes, not seconds.** Scanning `captures.csv` line-by-line (client needs `timeout=240` in `tools/dev_bridge_client.py`) took roughly two minutes against a ~4,500-row file on 28 August 2026, despite avoiding a per-row heap allocation for the common non-matching-row case (`csvFieldEquals` compares in place via `strncmp` rather than calling `String::substring`). This file only grows across the card's lifetime, so this will get slower on every future run - worth revisiting with raw buffered parsing (no `Stream::readStringUntil` per row) if it becomes impractical. Confirmed correct against `run_000041`: `images=3589 shards=36 last_shard_images=89` exactly matches the manual dev-bridge audit already on record in [hardware-validation.md](hardware-validation.md), and additionally surfaced `interval_max_ms=2085` against a `1003` mean - the first per-frame timing evidence for that run's cadence-drift theory. It also immediately found a real, previously-unknown issue: `run_000027` is stuck at `state: "running"` with zero images and zero `captures.csv` rows - an empty run that never got past its first capture before being interrupted, whose manifest was never reconciled to `interrupted_power_removed` on a later boot. Worth a look at the reconciliation path's handling of a "running with nothing captured yet" run, but low priority - no data loss, just a stale label.

**Notably, `AUDIT`'s scan is also slow, but recovers rather than stalling** - see the `CAT` entry below; the difference between the two is itself informative.

## On-device progress visibility: `<DEV PROGRESS ...>`

Added 28 August 2026, directly in response to a fair complaint: while investigating the `CAT`/`AUDIT` slowdown, every long wait looked identical whether the board was slowly-but-genuinely working or had actually stalled - the only way to tell was to wait it out and see. `commandRead` (`CAT`) and `commandAudit` (`AUDIT`, both its image-tree scan and its `captures.csv` scan) now emit a `<DEV PROGRESS ...>` frame every 64 items processed. The client (`Bridge._expect_frame` and `Bridge.read_lines_until_end` in `tools/dev_bridge_client.py`) recognises this frame type in both its wait loops, prints it, and resets its own timeout on receipt - so `cmd_audit`'s timeout could be cut from a flat 240 s (had to cover the whole worst-case scan) down to 60 s (only needs to cover the gap *between* heartbeats).

**64 items, not something coarser, because testing found the degradation can begin very early.** An initial 500-row/250-chunk interval was tried first and repeatedly showed *zero* output before failing - meaning the slowdown was already underway before the first heartbeat could fire, which defeated the purpose. The image-tree scan (walking `/images/<run_id>` before ever touching `captures.csv`) was also found to be a second, previously-uninstrumented site for the same kind of stall - a silent 60-90 s wait could have been happening there instead of in the CSV scan, and there was no way to tell which without this.

**One clean, fully-instrumented run on 28 August 2026** (`audit run_000041`, after all the above was in place) completed end to end with continuous, readable progress the whole way - 56 heartbeats through the 3,589-entry image tree, then 211 through the by-then ~13,500-row `captures.csv` (it keeps growing every time a session is tested) - with no slowdown or stall at all, and the exact same final numbers as every previous successful audit. This is itself informative: it reinforces that whatever triggers the slowdown is genuinely intermittent, not a deterministic function of file size or a fixed row/chunk offset - the same operation can be either full-speed or badly degraded depending on some condition not yet identified.

**Ruled out along the way: cumulative degradation across repeated dev-bridge commands within one boot.** A `REBOOT` issued after a stuck `AUDIT` produced a fresh session (`run_000046`) that captured at a perfect 1,000 ms cadence - initially read as support for a "heap fragmentation accumulates across commands" theory. That conclusion was wrong: it compared the wrong two things (normal *capture* speed, an unrelated code path, vs. dev-bridge command speed). A follow-up `AUDIT` run as the very first command on that same fresh boot stalled for 90+ s with zero output anyway, disproving it directly. Recorded here specifically so this dead end isn't re-investigated next time - it looked promising, and it was tested and it didn't hold up.

## Verified 27 August 2026

Live against real hardware, card in the board throughout: `ping`, session-active refusal on `ls`, `stop` (observed ~12 s, matching the dashboard-chunk-promotion cost already measured in [performance-experiment.md](performance-experiment.md)), `mount`, `ls /` against the real card contents, `cat /config.json` against the real file, `df`, a `put`/`get` round trip verified byte-for-byte via SHA-256, and a single real JPEG pulled from `/images/` and confirmed to render correctly. Not yet exercised: `rm` on anything but the round-trip test file, `reboot` (see risk below), and behaviour if a command arrives while `poll()` is mid-transfer on a previous one.

## Known risks, left deliberately as risks rather than papered over

- **`REBOOT` is now verified, with one caveat still open.** Used live on 27-28 August 2026 to apply a corrected config and start a fresh session: the board re-enumerated as COM4 (same port) and responded to `ping` within 3 s, both times. Not yet exercised: a re-enumeration under a *different* COM port number, which would still require manual recovery (the client has no auto-detect).
- **Large `CAT`/`GET` transfers degrade and then fail - a real firmware bug, still open after real investigation, not a timeout to tune.** First observed pulling `/raw/captures.csv` (2.29 MB, ~4,470 chunks) after the 27-28 August one-hour pilot run: throughput starts around 150-160 chunks/s and decelerates to ~40-50 chunks/s by roughly chunk 1,200-1,300 (~650 KB in) - consistent across every attempt below - then fails one of two ways: a **silent stall** (no further data ever arrives, client times out) in three attempts (0/4,469, 2,223/4,469, 1,974/4,512 chunks), or, once, a **corrupted/premature `<DEV END>`** at 2,086/4,521 chunks with invalid hex data partway through (`ValueError: non-hexadecimal number found in fromhex()`). The board is fully responsive to `ping` and small `cat` calls immediately after every failure - this is not a crash or reboot.
  - **Wi-Fi/SoftAP ruled out, with a real test, not just an inference.** This project has a documented precedent (see the 21 August motion-detection finding below) of Wi-Fi activity causing exactly this kind of timing interference elsewhere, and the `CAT` loop never yields back to `control_server.handleClient()` for the whole transfer - a strong, testable lead. Built and flashed a diagnostic firmware with the existing `WIFI_CONTROL_DISABLED_FOR_TEST` flag (confirmed via a fresh Windows Wi-Fi scan that the `InsectCam` SoftAP was genuinely off, not just a stale scan result), then reran the same pull: it stalled again, at almost the same chunk count (1,974/4,512) as with Wi-Fi on. **Wi-Fi is not the cause.**
  - **A periodic `yield()` was added to the chunk loop** (every 32 chunks) as a plausible, low-risk mitigation for an unbroken multi-second loop that otherwise never yields to anything - shipped in firmware regardless of outcome, since it's good practice independent of this bug. It changed the *symptom* (produced the corrupted-END failure once, where every prior attempt had been a silent stall) but did not fix the underlying issue.
  - **A second, independently-added command (`AUDIT`) does a comparably heavy line-by-line scan of the same `captures.csv` file and also decelerates around the same point - but recovers and completes (~2 minutes) rather than stalling.** `AUDIT` allocates a fresh `String` per row (`readStringUntil('\n')`) but sends only one reply line; `CAT` allocates less per chunk but calls `Serial.println()` thousands of times. Both slow down at a similar file offset, but only the one with heavy *repeated serial output* ever fails outright. That points more specifically at the USB-CDC TX path under sustained high-throughput output as the likely mechanism, in the same class as the already-documented `PUT`-direction bug (small ring buffer, no hardware flow control) - just manifesting on the read/output side as corruption or a stall instead of silently dropped input bytes. Not proven; the true fix would need live heap/timing instrumentation, which needs either physical access or a further remote iteration this session didn't reach.
  - **Practical guidance until fixed:** don't `CAT`/`GET` anything much past the ~170-chunk (~87 KB) precedent that's actually been proven reliable. For per-run diagnostics, use `AUDIT`/`RUNS` (above) instead of pulling `/raw/captures.csv` at all - they were built specifically because this bug makes that pull unreliable, and they get the same underlying data without needing a large transfer.
- **A firmware log line can merge with a `<DEV ERR>` reply on the wire, causing a client-side timeout instead of a clean error.** Observed repeatedly calling `df` while a session was actively capturing: the firmware's own housekeeping log (`remove(): /images/run_000041/shard_.../...`) and the `<DEV ERR session active; send DEV STOP first>` frame arrived concatenated on one line with no separating newline, which `_expect_frame`'s line-based parser can't recognise as a frame - it falls through to printing the whole mess as an ordinary log line and then times out waiting for a frame that already went by. The refusal is still working correctly (file commands remain safely blocked during a session); only the client's reporting of that fact is unreliable in this specific overlap.
- **No collision handling if a command arrives mid-transfer.** `PUT`'s receive loop reads raw serial bytes directly rather than going through the normal line buffer; a second command sent before the first finishes would corrupt both. The client is synchronous and waits for each reply before sending the next, so this should not occur through normal use of `dev_bridge_client.py`, but nothing in the firmware itself prevents it.
- **Git Bash path conversion.** Invoking the client from Git Bash on Windows, a bare `/` or a leading-slash path gets silently rewritten to a Windows path before Python ever sees it (confirmed: `/` became `C:/Program Files/Git/`). Prefix with `MSYS_NO_PATHCONV=1` when using Git Bash; PowerShell is unaffected.

## Verified 27-28 August 2026: one full unattended cycle

Used end-to-end, unattended, to run the one-hour QXGA pilot acceptance session: `put` a corrected `config.json` (the card had drifted to a stale 5-minute trial config), `cat` to confirm it byte-for-byte, `reboot` to apply it and start a fresh run, repeated `ping` to confirm the board came back on the same port, `df`/`mount` to inspect state after the session self-finished at `max_session_seconds`, `ls` through the image tree to verify shard structure, and `cat` on the small per-run manifest for authoritative completion state (`"state": "finished"`). This is the first time the bridge has been used for a task longer than a few minutes rather than isolated one-off commands, and it worked - see [hardware-validation.md](hardware-validation.md) for the capture-side results.
