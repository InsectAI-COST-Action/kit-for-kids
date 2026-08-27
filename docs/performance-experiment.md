# Performance experiment

> Historical record: the 2-FPS/VGA experiments below led to the current directory-sharding implementation. On 17 August 2026 the pilot setting was changed to QXGA/JPEG-quality-12/1-FPS after the dedicated quality trials: QXGA at 1 FPS completed cleanly, while QXGA at 2 FPS captured only 171 of 240 expected images. The active acceptance protocol is now in [camera-quality-trial.md](camera-quality-trial.md).

## SD clock speed raised to 25 MHz (27 August 2026)

Prompted by a collaborator suggesting exFAT for write throughput. Investigating that surfaced a cheaper lever first: `SD.begin(pin)` uses the arduino-esp32 default of **4 MHz SPI**, which we had never overridden.

`SdStorage::begin()` now tries **25 → 20 → 10 → 4 MHz** and keeps the first clock the card mounts at. The ladder matters because a kit shipped to schools meets cards of unknown age; a card that will not take 25 MHz still works, only slower, rather than failing to mount. The achieved clock is reported in the boot diagnostic and recorded in a new `sd_clock_hz` column in the performance CSV, so runs document their own conditions.

**Measured effect** — `run_000032`, QXGA/quality-12/1-FPS, retain every frame, ~98 KB frames. Baseline is runs 000001–000003 at the 4 MHz default:

| | 4 MHz (baseline) | 25 MHz (`run_000032`) |
| --- | --- | --- |
| `image_write_ms` | 758–777 | **382–405** |
| Effective throughput | ~129 KB/s | **~244 KB/s** |

Image write time roughly halved. The card accepted the top rung, so no fallback occurred.

### The bottleneck has moved from the bus to metadata

244 KB/s against a 25 MHz bus is roughly 8% utilisation, so further clock increases have little left to give. Per-frame cost at the sampled frames:

- image write **405 ms**
- raw CSV append **112 ms**
- dashboard chunk **447 ms**
- **total 983–1030 ms** against a 1,000 ms budget at 1 FPS

Metadata logging now costs more than writing the JPEG itself: a ~250-byte text line is more expensive than a 99 KB image, because every append is a separate open/write/flush/close and FAT must update the directory entry, the FAT, and the data cluster each time.

**On exFAT:** the original suggestion has merit — exFAT's allocation bitmap and single FAT would reduce exactly this metadata cost. It is not available in our toolchain, though: the arduino-esp32 prebuilt ESP-IDF ships with `FF_FS_EXFAT 0` and no exFAT symbols in `libfatfs.a`, so an exFAT card would not mount. Adopting it means either rebuilding ESP-IDF (an ADR-level change per the project brief) or replacing `SD.h` with SdFat. Worth revisiting only after the leaner write path, since the measurements say our own write pattern is the larger share.

### Measurement artifact: sampling aligns with chunk promotion

`kPerformanceSampleInterval` is 100 and `DashboardWriter::kChunkSize` is also 100, so **every performance sample lands exactly on a chunk promotion** — a rename plus `saveState`, `writeManifest` and `writeSummary`. The `dashboard_ms` figures above are therefore worst-case, not typical, and we have never sampled an ordinary frame. Change the sample interval to a prime such as 97 to decorrelate the two before drawing further conclusions.

### Also observed

`capture_ms` fell from ~224 ms to **1 ms**. Retain-every-frame mode leaves the camera streaming, whereas motion mode reinitialises the sensor at each grayscale/JPEG switch. That ~224 ms is a previously unisolated cost of motion mode.

### Next steps

1. Decorrelate the performance sampling interval from the chunk size, then re-measure to get honest steady-state figures.
2. Reduce the write path, in likely order of payoff: chunk promotion performing four file operations at once; three separate files opened and closed per frame; and the atomic write's `remove` → `open` → `write` → `flush` → `close` → `rename`.
3. Reconsider exFAT only if metadata cost still dominates afterwards.

## Purpose

The first one-hour run completed safely but slowed from roughly 0.9 seconds per frame at the beginning to roughly 5.5 seconds per frame at the end. This experiment identifies whether the growth comes from camera capture, image writes, raw/dashboard logging, or heap fragmentation.

The default capture behavior is unchanged: every scheduled attempt is retained in `/raw/captures.csv`, every successful JPEG is retained, and the null inference adapter remains active.

## Instrumentation

The firmware writes one bounded diagnostic sample for every 100 capture attempts to:

```text
/system/performance_<run-id>.csv
```

It records:

- capture ID and scheduled time;
- start lateness;
- camera capture duration;
- JPEG write duration;
- separate raw CSV and dashboard stage durations;
- total frame-processing duration;
- JPEG size and outcome;
- free heap, largest free heap block, minimum free heap;
- free PSRAM and largest free PSRAM block.

The diagnostic file is not authoritative and is not loaded by the dashboard. It is retained for the experiment and can be removed manually after backup.

## Run protocol

1. Back up the SD card or create a read-only card image before testing.
2. Confirm the card contains `config.json`, and set `max_session_seconds` to a short test duration such as 600 seconds for development runs. Keep `capture_fps` at `2`.
3. Upload the instrumented firmware:

   ```powershell
   py -m platformio run -e xiao_esp32s3 -t upload --upload-port COM4
   ```

4. Insert the backed-up card into the powered-off camera and run one controlled test. Disconnect the battery cable to stop it; never remove the card while powered.
5. Run the read-only audit after transfer:

   ```powershell
   py tools\audit_card.py D:\
   ```

6. Copy `/system/performance_<run-id>.csv` off the card and compare the first, middle, and final samples. Do not use the dashboard count alone to judge throughput.
7. Repeat with a fresh copied card if a second run is needed. Keep the original experiment card unchanged.

## Interpretation

- If `image_write_ms` grows while capture and logger times stay stable, investigate FAT directory growth, file fragmentation, card quality, and the atomic image-write sequence.
- If `logger_ms` grows, investigate raw CSV append, dashboard append, repeated open/flush/close, and `String` allocation.
- If free heap or largest free heap block declines steadily, investigate heap fragmentation and temporary `String` objects.
- If camera `capture_ms` grows while storage timings remain stable, investigate camera buffering, sensor state, or thermal behavior.
- If all stage times remain stable but intervals still grow, inspect scheduler lateness and delay/rebase behavior.

## Follow-up isolation tests

Only after the instrumented full-pipeline run is backed up should we create test-only firmware variants that omit one derived output at a time. These variants must never be used for field data collection:

1. image plus raw CSV, dashboard chunks disabled;
2. image plus dashboard chunks, raw CSV disabled;
3. image write only.

Each variant must retain serial warnings that it is test-only and must be run on a copied card. The full-pipeline firmware remains the acceptance configuration.
## First instrumented result: run_000010

The ten-minute diagnostic run was stopped by the normal battery disconnect, so its run manifest remains `running` and one final `.tmp` image is expected. The run produced 483 completed image records before removal.

| Sample | Image write | Logger | Total | Start lateness |
| --- | ---: | ---: | ---: | ---: |
| Frame 100 | 560 ms | 703 ms | 1,263 ms | 294 ms |
| Frame 200 | 924 ms | 709 ms | 1,633 ms | 510 ms |
| Frame 300 | 1,300 ms | 739 ms | 2,040 ms | 880 ms |
| Frame 400 | 1,705 ms | 749 ms | 2,454 ms | 1,268 ms |

Camera capture remained below the millisecond resolution of the current timer, and free heap/free PSRAM stayed constant. The evidence therefore localises the progressive slowdown to the JPEG write path, not camera capture or accumulating heap allocations. The next isolation test should compare the current atomic image write against a direct final-path write on a copied card, then compare one large run directory with sharded image directories. Direct-write firmware is test-only and must not be used for retained field data.
## Optimized run result: run_000011

The logger/JPEG optimization was tested on the same card. The run was stopped after approximately ten minutes by battery removal and produced 608 completed records.

| Sample | Previous image write | Optimized image write | Previous logger | Optimized logger | Previous total | Optimized total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frame 100 | 560 ms | 498 ms | 703 ms | 1,120 ms | 1,263 ms | 1,637 ms |
| Frame 200 | 924 ms | 796 ms | 709 ms | 1,107 ms | 1,633 ms | 1,945 ms |
| Frame 300 | 1,300 ms | 1,182 ms | 739 ms | 1,108 ms | 2,040 ms | 2,488 ms |
| Frame 400 | 1,705 ms | 1,442 ms | 749 ms | 1,125 ms | 2,454 ms | 2,588 ms |
| Frame 600 | ??? | 2,055 ms | ??? | 1,122 ms | ??? | 3,226 ms |

The average interval changed only from 1,292 ms in run_000010 to 1,265 ms in run_000011, despite the logger changes. Image writes were modestly faster at comparable early samples but still grew with accumulation. Logger time increased to about 1.1 seconds, so keeping the files open with a flush on every row is not an improvement on this SD/FAT stack. The optimization should not be treated as accepted.

Because only one card is available, this is not a clean isolated A/B test: the card contains more files than during run_000010, and JPEG sizes vary. The next implementation should revert or redesign the open-handle logger path, then instrument raw CSV append, dashboard append, and chunk promotion as separate sub-stages. The image path needs a directory-sharding experiment or a preallocation/append design rather than more metadata checks around the same per-image atomic write.

## Next diagnostic build: run_000012 preparation

The open-handle logger change from run_000011 was rejected: logger time rose to about 1.1 seconds per frame. The next build restores the safer per-row append behaviour and records the two logger sub-stages separately as `raw_csv_ms` and `dashboard_ms` in `/system/performance_<run-id>.csv`.

New JPEGs are written beneath `/images/<run-id>/shard_0001/`, then `shard_0002/` after each 100-frame boundary. This keeps each FAT directory bounded while preserving the authoritative raw CSV and dashboard paths. The atomic create-and-rename write is retained for power-loss safety.

For the next test, use the same ten-minute, 2 FPS protocol on the available card. After disconnecting the battery and mounting the card, compare `image_write_ms`, `raw_csv_ms`, `dashboard_ms`, and `logger_ms` at frames 100, 200, 300, and 400. Also check that each shard contains no more than 100 JPEGs, every raw row points to an existing image or an explicitly recorded save failure, and the dashboard count includes all closed chunks plus the recovered current chunk.

## Storage milestone: run_000012

Run 000012 tested the revised per-row logger together with 100-image JPEG directory shards. It produced 2,384 completed captures before the normal battery disconnect. The run-relative records, dashboard data, and retained JPEGs all agree: 2,384 records, 2,384 dashboard entries, and 2,384 JPEGs across `shard_0001` through `shard_0024`. The one final `.tmp` file is the interrupted atomic write expected at power removal.

| Sample | Image write | Raw CSV | Dashboard | Logger | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frame 100 | 530 ms | 55 ms | 802 ms | 857 ms | 1,387 ms |
| Frame 1,000 | 652 ms | 64 ms | 1,305 ms | 1,370 ms | 2,023 ms |
| Frame 2,300 | 546 ms | 73 ms | 814 ms | 888 ms | 1,435 ms |

This accepts directory sharding as the effective mitigation for the progressive JPEG-write slowdown: comparable earlier runs rose from about 500 ms to more than 1.7 or 2.0 seconds, whereas this run remained close to 0.55 seconds across 2,300 samples. Raw CSV and dashboard times were also broadly stable, aside from the isolated frame-1,000 dashboard outlier.

Do not yet treat the absolute capture cadence as accepted. The final raw row is at 1,340,538 ms for capture 2,384, which suggests roughly 1.78 frames per second, but the sampled `total_ms` values are usually about 1.4 seconds and cannot coexist with that elapsed time. The next firmware change must validate duration measurement with an independent monotonic source and record a per-frame consistency check before another rate conclusion is made.
