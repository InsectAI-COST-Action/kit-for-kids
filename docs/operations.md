# Operation guide

## Prepare a card

1. Format a supported microSD card as FAT32. Formatting removes existing data.
2. On a development computer, run `py tools\prepare_sd.py <card-root>`.
3. Inspect `config.json`. The pilot only accepts 2 FPS and sessions no longer than 3,600 seconds.
4. Safely eject the card and insert it into the powered-off camera.

## Collect a session

1. Connect the battery power cable.
2. The unit records all frames at 2 FPS for up to one hour. A production model has not yet been installed, so all inference outcomes are `model_unavailable`.
3. Disconnect the battery cable to stop the device. An unexpected power loss can leave only the most recent uncommitted dashboard chunk absent; previously committed data remains available.
4. Never remove the microSD card while the device is powered.

## Review and delete data

1. Remove the card only after power is disconnected.
2. Insert it into a normal computer and open `dashboard.html` in Chrome, Edge, Firefox, or Safari while offline.
3. Use the computer's file manager—not the dashboard—to delete data. Do not delete files during collection.
4. Preserve `/raw/captures.csv` when analysis matters: it is the authoritative record.

## Recovery

- Missing/corrupt `config.json`: restore `config.example.json` as `config.json`.
- Dashboard has fewer frames than expected: inspect `/raw/captures.csv`; the final `.part` dashboard chunk is intentionally omitted after an interrupted session.
- Camera/SD fault: record the serial diagnostic, firmware version, card type, and run identifier before retrying.
