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

| Command | Effect |
|---|---|
| `PING` | Liveness check |
| `LS <path>` | List a directory |
| `CAT <path>` | Read a file (hex-encoded) |
| `PUT <path> <bytes>` | Write a file (hex-encoded payload follows) |
| `RM <path>` | Delete a file |
| `DF` | Card total/used bytes |
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
py tools\dev_bridge_client.py --port COM4 put config.local.json /config.json
py tools\dev_bridge_client.py --port COM4 stop
py tools\dev_bridge_client.py --port COM4 mount
```

Each invocation opens a fresh connection and closes it afterward - there is no persistent session to keep alive between commands.

## Two problems found and fixed while building this, worth knowing about

**Opening the serial port used to reboot the board.** This board's native USB-CDC wires DTR/RTS to the same reset circuit esptool pulses to reset it for flashing, and pyserial asserts both by default the moment a port opens. The first version of this client silently rebooted the board — and restarted capture - on every single command, which defeated the purpose entirely (each "inspect a file" call would wipe out whatever `STOP` had just achieved). Fixed by constructing the port with `dtr`/`rts` cleared before opening. If this bridge is ever ported to different hardware or a different OS driver, re-verify this — the fix depends on how the specific USB-CDC/reset wiring responds to those lines, not on anything protocol-level.

**Bulk writes silently dropped bytes.** `PUT` originally sent the whole hex payload in a handful of ~1 KB bursts. The ESP32-S3's native USB-CDC has a small receive ring buffer and no hardware flow control, so bytes were lost between bursts with no error on either side - the firmware just waited out its full timeout for a payload that would never complete, and the transfer failed silently rather than loudly. Fixed by pacing the client to 64-byte writes with a 10 ms gap. This is empirical, tuned against one 3 KB test file, not derived from a documented buffer size - if `PUT` ever fails on a larger file, this pacing is the first thing to revisit.

## Scope: small files only

`kMaxWriteBytes` caps writes at 256 KB in firmware, and the paced send makes anything near that slow (at 64 bytes/10 ms, roughly a minute for 256 KB). This is sized for `config.json`, run manifests, `captures.csv` excerpts, and performance logs - not for pulling JPEGs or bulk image sets off the card. Images stay on the card; use the normal card-in-a-reader workflow for those.

## Verified 27 August 2026

Live against real hardware, card in the board throughout: `ping`, session-active refusal on `ls`, `stop` (observed ~12 s, matching the dashboard-chunk-promotion cost already measured in [performance-experiment.md](performance-experiment.md)), `mount`, `ls /` against the real card contents, `cat /config.json` against the real file, `df`, and a `put`/`get` round trip verified byte-for-byte via SHA-256. Not yet exercised: `rm` on anything but the round-trip test file, `reboot` (see risk below), and behaviour if a command arrives while `poll()` is mid-transfer on a previous one.

## Known risks, left deliberately as risks rather than papered over

- **`REBOOT` is unverified in practice.** A software restart may cause Windows to briefly drop and re-enumerate the COM port; if it comes back under a different number, the next command would need the new port. `STOP` + leaving the board running is the safer choice for routine unattended work; `REBOOT` exists for when a config change needs a fresh boot to take effect (see the phone app's own "Restart now" flow, which does the same thing for the same reason).
- **No collision handling if a command arrives mid-transfer.** `PUT`'s receive loop reads raw serial bytes directly rather than going through the normal line buffer; a second command sent before the first finishes would corrupt both. The client is synchronous and waits for each reply before sending the next, so this should not occur through normal use of `dev_bridge_client.py`, but nothing in the firmware itself prevents it.
- **Git Bash path conversion.** Invoking the client from Git Bash on Windows, a bare `/` or a leading-slash path gets silently rewritten to a Windows path before Python ever sees it (confirmed: `/` became `C:/Program Files/Git/`). Prefix with `MSYS_NO_PATHCONV=1` when using Git Bash; PowerShell is unaffected.
