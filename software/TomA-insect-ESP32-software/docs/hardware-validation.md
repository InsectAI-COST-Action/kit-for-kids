# Hardware validation record

Update this record as evidence is collected. SD endurance and final cadence validation remain outstanding. A formal one-hour battery-capacity profile is no longer required for this pilot because the expected one-hour load is comfortably within a standard USB battery pack; retain a short stability and clean-power-removal smoke test using the intended pack.

| Check | Required evidence | Result |
| --- | --- | --- |
| Board | ESP32-S3R8 XIAO ESP32S3 Sense; clean PlatformIO build and upload | Verified on physical board (COM4) |
| Camera | OV3660 PID reported at boot | Verified at boot |
| PSRAM | `psramFound()` succeeds | Verified at boot |
| SD | FAT32 card mounts and survives 3,600 QXGA writes | Mount and sustained capture verified. Historical run 000012 retained 2,384 smaller JPEGs in 24 bounded shards; completed QXGA run 000004 retained 120 images. One-hour 3,600-write endurance remains pending. Card corruption observed once after normal battery-cable removal; see incident below. |
| Capture | QXGA/JPEG-quality-12 frame every 1,000 ms | Completed QXGA run 000004 captured 120 images at a 1,000 ms median interval. QXGA/2-FPS was rejected (171/240 images; write time exceeded its budget). One-hour QXGA cadence acceptance remains pending. |
| Battery | Intended USB pack powers a representative capture run without reset, unsafe heating, or storage corruption; normal cable removal recovers cleanly | Short stability smoke test pending; formal capacity profiling deprioritised by owner |
| Recovery | Power interruption preserves prior CSV/chunks and marks the run interrupted | Verified with battery disconnect and subsequent reboot. Run 000012 awaits its next card-in-board boot to receive its normal `interrupted_power_removed` state. |
| Dashboard | Opens offline in Chrome, Edge, Firefox, Safari; images and full chunk index load | Verified locally in the SD-card dashboard; full browser matrix pending |

## Incident: FAT32 root-directory corruption after normal power-off (21 August 2026)

After a successful motion-mode test run (`run_000002`, the shard-directory fix validation — 299 checks, 31 saved images, 0 storage errors during capture), the card was stopped normally by disconnecting the battery cable and moved to a card reader. On the next mount, Windows reported the volume as a healthy FAT32 filesystem (correct size, no dirty bit), but the root directory itself was corrupted: every real file and folder (`dashboard.html`, `config.json`, `raw/`, `images/`, `data/`, `system/`) had been replaced by a single garbled, zero-length pseudo-entry that both `attrib` and PowerShell's file APIs treated as a broken symbolic link.

This is first-hand confirmation of the FAT32 write-safety risk already flagged in `docs/next-session.md` and the project brief: the filesystem's own directory/FAT metadata is not written atomically, and the documented stop method (disconnect the battery cable) gives no opportunity for a controlled unmount. The firmware's per-frame atomic-rename writes protected individual images and CSV rows during the session itself (no corruption was ever observed while captures were running, across today's session or the prior one), but this incident shows the risk sits one level up, in the filesystem's own directory table, which firmware-level write discipline cannot fully protect against.

Recovery attempted: `chkdsk /f` repaired the volume and recovered 2,007 orphaned cluster fragments (275 MB) into `FOUND.000`. 1,913 of those fragments began with a valid JPEG signature, so most of the recovered data was genuine photo content, but the recovery was fragment-level (unordered ~32 KB clusters, most JPEGs span several), carried no filenames or session metadata, and only one fragment retained readable `captures.csv` header text. Given the run was this week's test data rather than irreplaceable field data, reconstruction was not attempted; the card was reformatted clean instead.

**Open follow-up:** this remains an unresolved hardware-level gap, not something firmware alone can fully close (see the physical power hold-up circuit note in the project brief). It also means a corrupted card is a real, observed failure mode for the pilot, not just a theoretical one — worth factoring into the one-hour endurance test and any operator-facing guidance on stopping the camera safely.

## Finding: Wi-Fi radio activity breaks motion detection (21 August 2026)

While prototyping the device control app ([ADR 0001](adr/0001-device-hosted-control-app.md)), two live motion-mode sessions with the SoftAP running showed a 100% save rate — every scheduled motion check triggered a save, with scores clustering just above the threshold of 5 (5.8–12) rather than the wide, mostly-sub-threshold spread seen in earlier motion-mode testing. A same-scene control run with Wi-Fi disabled (`WIFI_CONTROL_DISABLED_FOR_TEST` build flag) and everything else identical showed normal discrimination: 131 of 132 checks correctly returned `motion_not_detected`, scores maxing at 3.57. Only Wi-Fi differed between the two conditions, so this is a confirmed effect, not a lighting or environmental confound (an initial lighting hypothesis was raised and specifically ruled out by this control test).

Suspected mechanism: SoftAP TX current draw introducing exposure micro-flicker that the motion score's whole-frame brightness correction does not fully cancel. Not yet confirmed at the electrical level. See [device-control-app-plan.md](device-control-app-plan.md) Phase 1 for mitigation options and current status — this blocks running Wi-Fi and motion-triggered capture concurrently until resolved. Retain-every-frame capture is unaffected.

The detailed component specification is in `docs/camera-spec.md`. The next validation actions are listed in `docs/next-session.md`.
