# Operation guide

## Prepare a card

1. Format a supported microSD card as FAT32. Formatting removes existing data.
2. On a development computer, run `py tools\prepare_sd.py <card-root>`.
3. Inspect `config.json`. The pilot only accepts 2 FPS and sessions no longer than 3,600 seconds.
4. The preparation tool updates static dashboard files but preserves the runtime-generated `manifest.js` and `summary.js` when they already exist.
5. For a transferred card, run `py tools\audit_card.py <card-root>` before changing or deleting anything.
6. Save the audit output with a read-only backup or card image.
7. Safely eject the card and insert it into the powered-off camera.

## Collect a session

1. Connect the battery power cable.
2. The unit is configured to capture and retain every frame at a 2-FPS target for up to one hour. A production model has not yet been installed, so all inference outcomes are `model_unavailable`. Absolute cadence acceptance remains a development validation item; it does not change the retention policy.
3. Disconnect the battery cable to stop the device. This is the normal stop method; never remove the microSD card while powered.
4. The firmware flushes each image and raw CSV row as it is captured. Dashboard records are written in bounded closed chunks plus `data/captures_current.js`; the current chunk is loaded by the dashboard so a normal power removal remains visible.

## Review and delete data

1. Remove the card only after power is disconnected.
2. Insert it into a normal computer and open `dashboard.html` in Chrome, Edge, Firefox, or Safari while offline.
3. The dashboard shows the total number of loaded captures, while the recent frames and image gallery initially show at most ten items. Use `Show all frames` or `Show all images` to expand the lists; the buttons then change to `Show fewer frames` or `Show fewer images`.
4. Select an image to open it in the page modal; use the `x` control, Escape, or the backdrop to close it.
5. Use the computer's file manager, not the dashboard, to delete data when starting a new experiment. Do not delete files during collection.
6. Preserve `/raw/captures.csv` when analysis matters: it is the authoritative record.

## Recovery

- Missing or corrupt `config.json`: restore `config.example.json` as `config.json`.
- A missing or empty `manifest.js` means only the current open chunk can be loaded. Do not overwrite a runtime manifest with the starter dashboard file; `py tools\prepare_sd.py` now preserves it automatically.
- On the next boot, the firmware promotes the previous open chunk and marks its run `interrupted_power_removed` before starting a new run.
- Run `py tools\audit_card.py <card-root>` before cleanup. The audit is read-only and reports missing CSV-referenced images, temporary files, unlisted chunks, stale run states, and raw/dashboard count drift.
- Camera/SD fault: record the serial diagnostic, firmware version, card type, and run identifier before retrying.
