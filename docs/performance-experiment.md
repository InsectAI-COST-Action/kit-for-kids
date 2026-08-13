# Performance experiment

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
- raw CSV/dashboard logger duration;
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
