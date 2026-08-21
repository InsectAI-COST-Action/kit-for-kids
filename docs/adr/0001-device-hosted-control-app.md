# ADR 0001: Device-hosted control app over Wi-Fi

- **Status:** Accepted for prototyping. Production adoption is gated on the phase gates in [device-control-app-plan.md](../device-control-app-plan.md).
- **Date:** 21 August 2026
- **Decision owner:** project owner (Tom August)
- **Supersedes:** nothing. First ADR in this repository.

## Context

Three things converged to reopen a question the project brief had closed.

**1. Card corruption is now an observed failure, not a theoretical one.** On 21 August 2026 a card was corrupted at the FAT32 root-directory level after a normal battery-cable stop, losing a completed motion-mode run. The incident is recorded in [hardware-validation.md](../hardware-validation.md). The firmware's per-frame atomic writes protected individual images and CSV rows correctly; the damage was one level up, in filesystem metadata that firmware write discipline cannot protect. The documented stop method — disconnect the battery cable — gives the device no opportunity to flush and unmount.

**2. The firmware already contains a correct safe-shutdown path with no trigger.** `finishSession()` in `src/main.cpp` promotes the open dashboard chunk, writes the manifest and summary, marks the run `finished`, and clears the active-run marker. It is only reachable by reaching `max_session_seconds`. There is no way for an operator to invoke it.

**3. On-device compute is more capable than this project assumed.** A colleague demonstrated a quantised YOLO ant detector running at 12 FPS on the same ESP32-S3 hardware while serving a view of it over Wi-Fi. Our own documentation states that on-device inference is impossible, but that conclusion was specific to AntAI-Beta (10 MB float ONNX, 1024px input) and does not generalise to small quantised models on preview-sized frames.

The project brief's **Won't — pilot scope** list names *remote viewing, live streaming, and public web service*, and its **Must** list specifies `file://` dashboard operation with no server and no `fetch()`. A device-hosted interface therefore requires an explicit owner decision rather than incremental drift.

## Decision

Add a **device-hosted control app**, served by the camera over its own Wi-Fi access point, scoped strictly to the **control plane**.

The system splits along the data-volume boundary:

| Plane | Runs on | Carries | Status |
| --- | --- | --- | --- |
| **Control** | Device, over SoftAP | Setup, live status, safe stop, occasional single preview frame | New |
| **Data** | SD card dashboard, on a PC | Gallery, movie maker, AI analysis, motion plots, adult records | Unchanged |

The control app is **additive**. The SD-card dashboard remains fully functional, fully offline, and independent of Wi-Fi. Nothing about the existing card workflow is removed or made conditional on the network.

### Explicitly in scope

- Device state and progress (pictures taken, elapsed time, recent motion scores).
- **Safe stop:** invoke the existing `finishSession()` and then explicitly unmount the card, giving the operator a positive "safe to unplug" signal.
- Reading and writing `config.json`, with firmware remaining the final validator on boot.
- **On-demand single preview frame** ("take a peek"), served from the most recent captured frame held in PSRAM.

### Explicitly out of scope

- Continuous video or MJPEG streaming.
- Serving the gallery, the image set, or capture chunk files over Wi-Fi.
- Remote viewing over any network the device does not itself host. No internet, no cloud, no accounts.
- Replacing or deprecating the `file://` SD-card dashboard.
- On-device inference. That is a separate future decision and is not authorised by this ADR.

## Alternatives considered

**Physical stop button.** A BOOT-button press invoking `finishSession()` would address corruption for roughly twenty lines of code and no network at all. Rejected by the owner for this iteration: the enclosure design does not currently accommodate it, and a button gives no confirmation that the stop actually succeeded. Worth revisiting as a complementary safety net, since it depends on nothing.

**Full port of the dashboard to the device.** Serving the entire dashboard — gallery included — over Wi-Fi. Rejected: it puts hundreds of megabytes and all SD contention onto the network path, which is where nearly all the technical risk lives, in exchange for convenience the SD workflow already provides adequately on a PC.

**Do nothing; accept the corruption risk.** Rejected: the failure is now observed, destroys real data, and falls on a child-operated workflow where the unsafe action is the only available action.

## Consequences

**Positive**

- The unsafe stop stops being the *only* stop. The corruption failure mode gains a real remedy rather than a caveat in documentation.
- The phone becomes the setup and monitoring surface without the SD workflow losing offline independence.
- Recent motion scores become visible live, which directly serves the outstanding motion-threshold tuning work.

**Negative / accepted costs**

- This is a documented departure from the brief's **Won't** list. The brief must be updated to record that a device-hosted *control* interface is now in scope while remote viewing and streaming remain excluded.
- New firmware complexity: an HTTP server, a command queue, and a Wi-Fi radio all sharing a device whose capture cadence is already budgeted.
- Power and thermal cost of an active radio in a sealed enclosure, currently unmeasured.
- A new attack surface. The AP must be WPA2-protected; an open AP would let any nearby device stop a run.
- Risk of the pilot's critical path slipping. The one-hour endurance test, cross-browser verification, and battery smoke test remain the route to a working pilot and must not be displaced by this track.

**Neutral**

- The existing chunked `captures_*.js` data format works unchanged over HTTP, so no data-format change is required by this decision.

## Compliance and review

This ADR authorises prototyping only. Each phase in the plan carries an acceptance gate; failing a gate returns the decision here for revision rather than permitting a workaround. In particular, if measured power or thermal behaviour makes an active radio unsafe in the sealed enclosure, this decision is revisited rather than downgraded silently.
