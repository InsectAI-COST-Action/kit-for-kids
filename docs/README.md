# Documentation guide

This directory separates everyday operation from technical design and historical evidence. Start with the shortest document that fits your role; do not treat every document as a current task list.

## Start here

| If you are... | Read | Purpose |
| --- | --- | --- |
| Preparing, running, or collecting from the camera | [Operations guide](operations.md) | SD-card preparation, normal operation, browser dashboard, AI prototype, recovery, and cleanup. |
| Returning to development | [Next session checklist](next-session.md) | Current hand-off state and the prioritised next tasks. |
| Looking for the project overview | [Repository README](../README.md) | What exists, current status, basic commands, and project map. |

## System reference

| Document | Authority |
| --- | --- |
| [Project brief](project-brief.md) | Detailed scope contract and requirements for implementation agents. It is not the day-to-day operating guide. |
| [Architecture](architecture.md) | Component boundaries and data-flow decisions. |
| [Data schema](data-schema.md) | Capture, run, and derived-dashboard record formats. |
| [Camera specification](camera-spec.md) | Confirmed OV3660/XIAO hardware and power facts. |
| [Operations guide](operations.md) | Human operating procedure; use this for SD-card handling. |

## Browser AI and model work

| Document | Purpose |
| --- | --- |
| [Browser inference plan](browser-inference-plan.md) | Architecture, child-facing behaviour, technical evidence, and acceptance gates for offline browser analysis. |
| [Model card](model-card.md) | Candidate/prototype record and the evidence required before model approval. |

The current FlatBug Nano route is a browser prototype only. It must be described as a **possible-insect prediction**, not species identification or a validated detection result.

## Engineering evidence and history

| Document | Purpose |
| --- | --- |
| [Hardware validation](hardware-validation.md) | Board, card, and browser verification record. |
| [Performance experiment](performance-experiment.md) | Storage/capture timing investigation and the run-000012 sharding milestone. |
| [Reconciliation policy](reconciliation-policy.md) | Rules for auditing, rebuilding, and manually cleaning SD-card data. |

## Documentation rules

- Keep the README short and link here rather than repeating detailed requirements.
- Update `next-session.md` at the end of a development session; it is the current hand-off, not a permanent specification.
- Record decisions and acceptance criteria in the relevant design document rather than copying them into several status sections.
- Preserve measured results in their evidence document. Do not delete historical tests merely because the current approach has moved on.
- A future GitHub Pages site should use this file as its landing-page structure, but publishing is deliberately deferred until the documentation review is complete.
