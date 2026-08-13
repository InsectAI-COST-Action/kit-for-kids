# Next session checklist

Start with the SD card disconnected from the camera and mounted on the development computer.

1. Create a read-only backup or card image, then rerun `py tools\audit_card.py <card-root>`. Record the run-000012 result: 2,384 raw rows, 2,384 dashboard records, 2,384 JPEGs, and one final `.tmp` image. The card-wide count mismatch and older stale manifests predate this run; preserve them for later reconciliation rather than deleting files.
2. With the card in the powered-off board, perform one brief boot and then disconnect power. This should mark run 000012 as `interrupted_power_removed` and promote any remaining current dashboard chunk. Mount the card again and audit it; do not treat the final interrupted `.tmp` file as data loss.
3. Fix and validate the performance instrument before another rate experiment. Add an independent monotonic-duration measurement and a clear per-frame elapsed-time sanity check, then compare it with run-relative timestamps. Do not claim 2-FPS acceptance until these agree.
4. After the timer check passes, run a copied-card, controlled capture at the configured 2 FPS. Compare the first, middle, and final `image_write_ms`, `raw_csv_ms`, `dashboard_ms`, logger, and independent elapsed-time samples. Confirm image shards remain capped at 100 JPEGs.
5. Run the repository checks (`py tests\check_project.py`) and a clean PlatformIO build before hardware work. Keep the hardware firmware version and the test-card backup with the recorded results.
6. Run the one-hour battery profile only after cadence validation. Record battery voltage, temperature, frame count, image count, SD errors, and whether final power removal is recovered cleanly.
7. Test the offline dashboard on Windows 10/11 and a current macOS release in Chrome, Edge, Firefox, and Safari. Confirm full capture counts, expand/collapse controls, and image-modal loading from local files.
8. Test the manual reset workflow on a copied card image, keeping the original card data intact until counts and backups are confirmed.
9. Continue SD endurance testing toward 7,200 retained captures, then review whether a cleanup/reconciliation utility is needed before model integration.
10. Keep the null inference adapter in place until a production model, model card, licence, input/output contract, and 2-FPS benchmark are approved.
