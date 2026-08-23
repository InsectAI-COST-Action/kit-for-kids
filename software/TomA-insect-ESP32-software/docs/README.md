# Documentation guide

This directory separates everyday operation from technical design and historical evidence. Start with the shortest document that fits your role; do not treat every document as a current task list.

## Start here

| If you are... | Read | Purpose |
| --- | --- | --- |
| Setting a camera up for the first time | [Setup guide](setup-guide.md) | Complete step-by-step from installing software to viewing pictures, written for a non-specialist (teacher-level) audience. |
| Preparing, running, or collecting from the camera | [Operations guide](operations.md) | SD-card preparation, normal operation, browser dashboard, AI prototype, recovery, and cleanup. |
| Returning to development | [Next session checklist](next-session.md) | Current hand-off state and the prioritised next tasks. |
| Looking for the project overview | [Repository README](../README.md) | What exists, current status, basic commands, and project map. |

## System reference

| Document | Authority |
| --- | --- |
| [Project brief](project-brief.md) | Detailed scope contract and requirements for implementation agents. It is not the day-to-day operating guide. |
| [Architecture](architecture.md) | Component boundaries and data-flow decisions. |
| [Decision records](adr/) | Numbered ADRs. A decision that changes scope or a shared contract is recorded here before the work starts. |
| [Data schema](data-schema.md) | Capture, run, and derived-dashboard record formats. |
| [Camera specification](camera-spec.md) | Confirmed OV3660/XIAO hardware and power facts. |
| [OV3660 image-quality trial](camera-quality-trial.md) | Controlled resolution/JPEG/rate comparison and decision rule. |
| [Operations guide](operations.md) | Human operating procedure; use this for SD-card handling. |

## Browser AI and model work

| Document | Purpose |
| --- | --- |
| [Browser inference plan](browser-inference-plan.md) | Architecture, child-facing behaviour, technical evidence, and acceptance gates for offline browser analysis. |
| [Model card](model-card.md) | Candidate/prototype record and the evidence required before model approval. |

The current FlatBug Nano and AntAI - Beta routes are browser prototypes only. It must be described as a **possible-insect prediction**, not species identification or a validated detection result.

## Engineering evidence and history

| Document | Purpose |
| --- | --- |
| [Device control app plan](device-control-app-plan.md) | Phased implementation plan and acceptance gates for the Wi-Fi control app ([ADR 0001](adr/0001-device-hosted-control-app.md)). |
| [Hardware validation](hardware-validation.md) | Board, card, and browser verification record. |
| [Performance experiment](performance-experiment.md) | Storage/capture timing investigation and the run-000012 sharding milestone. |
| [Reconciliation policy](reconciliation-policy.md) | Rules for auditing, rebuilding, and manually cleaning SD-card data. |

## Experiment files and generated evidence

- `spikes/` holds small, tracked, reproducible technical experiments and their instructions. It must not contain camera photos, model weights, or generated reports.
- `artifacts/` is Git-ignored and holds local generated evidence: reports, contact sheets, model downloads, training output, and abandoned trial output. It may be safely recreated from the relevant source workflow when appropriate.
- The motion-trigger experiment is documented in [`../spikes/motion-detection/`](../spikes/motion-detection/README.md). Its 19 August 2026 sample evidence is local-only under `artifacts/motion-detection/`.

## Documentation rules

- Keep the README short and link here rather than repeating detailed requirements.
- Update `next-session.md` at the end of a development session; it is the current hand-off, not a permanent specification.
- Record decisions and acceptance criteria in the relevant design document rather than copying them into several status sections.
- Preserve measured results in their evidence document. Do not delete historical tests merely because the current approach has moved on.
- A future GitHub Pages site should use this file as its landing-page structure, but publishing is deliberately deferred until the documentation review is complete.
