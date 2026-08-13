# Data schema v1

## Time and identifiers

Calendar time is intentionally unavailable in this pilot. `uptime_ms` is milliseconds since boot and `scheduled_ms` is the intended monotonic capture deadline. `run_id` is a persisted incrementing session identifier; `capture_id` is unique within its run.

## Raw capture log

`/raw/captures.csv` is the authoritative record. A row exists for every capture attempt, including capture and storage failures.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer schema version, currently `1`. |
| `device_id` | Placeholder stable device identifier pending device provisioning. |
| `run_id`, `boot_id`, `capture_id` | Correlation identifiers. |
| `captured_at_utc` | Empty for this session-relative-time pilot. |
| `uptime_ms`, `scheduled_ms` | Actual and intended monotonic times. |
| `outcome` | `completed`, `capture_error`, `storage_error`, or later `skipped`. |
| `frame_width`, `frame_height`, `jpeg_bytes`, `capture_ms` | Camera facts; zero where capture failed. |
| `inference_ms`, `model_id`, `prediction_count`, `max_confidence` | Model facts. The null model records `model_unavailable` in dashboard chunks. |
| `image_path` | Card-relative JPEG path, empty unless the write succeeded. |
| `save_policy`, `save_outcome`, `error_code` | Retention and failure facts. |

`/raw/detections.csv` is reserved for one row per prediction once a production model exists. It remains header-only while the null model is active.

## Derived dashboard data

The dashboard reads `manifest.js`, `summary.js`, and closed JavaScript chunks under `/data/`. The raw CSV remains authoritative. A `.part` chunk is not listed in the manifest and must not be shown by the dashboard after an unexpected power loss. Run `py tools\audit_card.py <card-root>` after transfer to compare raw rows, image links, run manifests, and derived chunks. The audit never modifies the card.

## Images

Every successful capture uses `/images/<run-id>/<capture-id>.jpg`. Image presence is confirmed only after a complete write and promotion; a CSV row must leave `image_path` empty after an image write error.
