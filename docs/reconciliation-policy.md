# SD-card cleanup and reconciliation policy

## Purpose

This project retains every captured frame and treats the raw capture log as the source of truth. Cleanup must therefore make storage easier to understand without silently deleting evidence or making the dashboard appear healthier than the underlying data.

The policy applies after the camera has been powered off and the SD card has been transferred to a computer. It is a host-side maintenance policy; the firmware does not delete old observations.

## Authority and disposition

| Artifact | Authority | Default action | Why |
| --- | --- | --- | --- |
| `/raw/captures.csv` | Authoritative capture-attempt log | Preserve; back up before maintenance | One row exists for every capture attempt, including failures. |
| `/raw/detections.csv` | Authoritative prediction log when a model exists | Preserve; currently header-only | Never infer predictions from dashboard files. |
| `/raw/runs/*.json` | Authoritative run state/configuration records | Preserve | Run state explains normal stops and interrupted power removal. |
| `/images/<run>/<capture>.jpg` referenced by CSV | Complete retained observation | Preserve | The pilot retention policy is every frame. |
| Unreferenced complete JPEG | Unreconciled evidence | Preserve and report | It may come from a CSV write failure, an older card state, or a manual copy. Do not delete automatically. |
| `.tmp`/`.part` image or chunk | Incomplete candidate | Report; quarantine only after backup and review | It is not a valid observation until promoted, but it may help diagnose a failed write. |
| Listed `data/captures_*.js` chunk | Derived dashboard index | Preserve if parseable | It is rebuildable, but useful for offline browsing and recovery evidence. |
| Unlisted dashboard chunk | Derived but stale/unindexed | Report; do not delete automatically | It may contain records missing from the current manifest. |
| `manifest.js` / `summary.js` | Derived index/summary | Rebuild or restore from valid chunks; never treat as authority | A missing or stale index must not cause raw data deletion. |

## Required workflow

1. Make a read-only backup or card image before changing anything.
2. Run `py tools\audit_card.py <card-root>` and save the report beside the backup.
3. Resolve errors first: missing raw files, missing CSV-referenced images, invalid run manifests, or manifest entries pointing to missing chunks.
4. Preserve all complete images. Review unreferenced JPEGs against the CSV before deciding whether they belong to a separate experiment.
5. For `.tmp`/`.part` files, keep the original until the audit and backup are complete. If space or usability requires cleanup, move them into a dated `recovery/orphan/` folder on the copied working card, never delete them in place, and record the source path and reason.
6. Rebuild derived dashboard files only from validated raw records or valid committed chunks. After rebuilding, rerun the audit and confirm that raw counts, image links, run states, and dashboard counts reconcile or that every remaining difference is documented.
7. Only the user may permanently delete data through the computer file manager, after confirming the backup and accepting the retention decision. The dashboard remains read-only for deletion.

## Severity rules

- **Error:** a referenced or authoritative artifact is missing/corrupt, or a manifest points to a missing chunk. Stop cleanup and preserve the card unchanged.
- **Warning:** temporary files, unreferenced complete images, unlisted chunks, or raw/derived count drift. Investigate and document; do not silently remove.
- **Clean:** no findings from the audit. This means the card is internally consistent, not that the images are scientifically validated.

The audit is intentionally read-only. A future quarantine/rebuild command must require an explicit destination, refuse to operate on a camera-mounted card, create a log, and support a dry run.
