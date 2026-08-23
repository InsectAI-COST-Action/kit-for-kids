# Operation guide

## Prepare a card

1. Format a supported microSD card as FAT32. Formatting removes existing data.
2. On a development computer, run `py tools\prepare_sd.py <card-root>`.
3. Inspect `config.json`. Normal `pilot` mode is fixed to QXGA (2048?1536), JPEG quality 12, 1 FPS, and sessions no longer than 3,600 seconds. Install that normal setting with `py tools\configure_camera_trial.py <card-root> --install-pilot-default`. The separate, short `quality_trial` mode is retained only as historical/diagnostic tooling; see [camera-quality-trial.md](camera-quality-trial.md).
4. The preparation tool updates static dashboard files but preserves the runtime-generated `manifest.js` and `summary.js` when they already exist.
5. For a transferred card, run `py tools\audit_card.py <card-root>` before changing or deleting anything.
6. Save the audit output with a read-only backup or card image.
7. Safely eject the card and insert it into the powered-off camera.

## Collect a session

1. Connect the battery power cable.
2. The unit is configured to capture and retain every QXGA/JPEG-quality-12 frame at a 1-FPS target for up to one hour (3,600 images). A production model has not yet been installed, so all inference outcomes are `model_unavailable`. The one-hour QXGA cadence/endurance acceptance run remains outstanding.
3. Disconnect the battery cable to stop the device. This is the normal stop method; never remove the microSD card while powered.
4. The firmware flushes each image and raw CSV row as it is captured. Dashboard records are written in bounded closed chunks plus `data/captures_current.js`; the current chunk is loaded by the dashboard so a normal power removal remains visible.

## Review and delete data

1. Remove the card only after power is disconnected.
2. Insert it into a normal computer and open `dashboard.html` in Chrome, Edge, Firefox, or Safari while offline.
3. The dashboard shows the total number of loaded captures, while the recent frames and image gallery initially show at most ten items. Use `Show all frames` or `Show all images` to expand the lists; the buttons then change to `Show fewer frames` or `Show fewer images`.
4. To try experimental browser AI in Chrome or Edge, install FlatBug with `py tools\install_ai_pack.py <card-root>`; add AntAI - Beta with `py tools\install_ai_pack.py <card-root> --include-antai-beta`. Select **Find insects with AI**, choose one option: **AntAI - Beta** (ant-only), **FlatBug - Quick look** (faster) or **FlatBug - Look closely** (slower, 12 tiles). Select **Load images and AI**, choose the clearly labelled **INSECT-AI** drive, then choose the desired saved session and press **Start looking**. The dashboard analyses only that session; it never mixes image records from separate experiments. The same selected card can be reused by the movie maker until the tab closes. Pictures are analysed locally, one at a time, with live possible-insect clues and pause/stop controls. These are predictions, not validated identifications, and nothing is uploaded or written back to the card.

5. Select **Make my insect movie** to create a raw-picture time-lapse. If the card is not already loaded, select **Load camera card** and choose the **INSECT-AI** drive. The movie maker uses only image files that still remain on the card, defaults to the newest available session, and lets an adult choose another available session. In current Chrome or Edge, it creates a finalized 1024x768 MP4 download locally at exactly 60 pictures per second. The encoder assigns each picture its intended timestamp, so image-reading time does not stretch the movie; the dashboard shows progress and provides a cancel control. Nothing is uploaded, changed on the card, or automatically written back to it. AI-overlay movies are not yet implemented.
6. Select an image to open it in the page modal; use the `x` control, Escape, or the backdrop to close it.
7. For a safe, colourful synthetic demonstration, run `py tools\install_dashboard_demo.py <card-root>`, open `<card-root>\demo\demo.html`, choose the `demo` folder itself, then select **Start looking**. This is visibly separate from real captures. The demo also includes its own practice copies of **Make my insect movie** and **Camera settings** for risk-free rehearsal; the settings tool writes only to the demo folder's own `config.json`, never to a real camera card.
8. Use the computer's file manager, not the dashboard, to delete data when starting a new experiment. Do not delete files during collection.
9. Preserve `/raw/captures.csv` when analysis matters: it is the authoritative record.

## Recovery

- Missing or corrupt `config.json`: restore `config.example.json` as `config.json`.
- A missing or empty `manifest.js` means only the current open chunk can be loaded. Do not overwrite a runtime manifest with the starter dashboard file; `py tools\prepare_sd.py` now preserves it automatically.
- On the next boot, the firmware promotes the previous open chunk and marks its run `interrupted_power_removed` before starting a new run.
- Run `py tools\audit_card.py <card-root>` before cleanup. The audit is read-only and reports missing CSV-referenced images, temporary files, unlisted chunks, stale run states, and raw/dashboard count drift.
- Camera/SD fault: record the serial diagnostic, firmware version, card type, and run identifier before retrying.

## Experimental direct dashboard configuration

The dashboard now includes a **Camera settings** tool for use only while the board is switched off and its card is mounted. In current Chrome or Edge, choose **Camera settings**, grant the browser explicit write permission to the top camera-card folder, choose each safe setting, and confirm the write. The choices are: one picture every 1 second, 2 seconds, 30 seconds, or 1 minute; high-quality QXGA or low-quality VGA; a 1-minute, 5-minute, 30-minute, one-hour, or infinite session; and an experimental **Save pictures only when something moves** option. Infinite means collection continues until power is disconnected or the card fills. When the modal opens, it reads the card-root `config.json`, displays the exact current setting, and aligns the offered controls with it when it is one of the supported safe combinations. After saving, it confirms the same setting has been written. The default remains to retain every image. With the motion option enabled, the camera waits five seconds after power-on, always saves its first image, then checks each scheduled low-resolution preview and saves a configured-quality JPEG only where its local change score reaches 5. It still logs every check, so the dashboard count can be larger than the image count. The tool replaces only the card-root `config.json`; the configuration takes effect after the board is restarted and firmware still validates it.

For an older card whose `captures.csv` predates motion mode, run `py tools\migrate_capture_schema.py <card-root>` before collecting a score-tuning run. The tool preserves every row, adds blank motion columns to rows whose scores were never collected, and leaves a timestamped backup on the card.

The existing image/AI picker remains read-only. Browser file objects cannot be upgraded to write access, so the settings tool deliberately asks once for a writable card-folder handle. If the browser declines or does not support that permission, it must leave the card unchanged. Mobile-browser support is not yet accepted; it is an explicit next feasibility test.
