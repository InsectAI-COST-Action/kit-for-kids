# Browser AI assets

These are the runtime files the dashboard's **Find insects with AI** panel loads from the SD card. All four are also copied here to `<card-root>/ai/` by `tools/prepare_sd.py`, so a freshly prepared card ships with the AI helper by default - see `docs/model-card.md` for what each model is and is not validated to do, and `docs/next-session.md` for the date this became a default rather than an opt-in install.

| File | What it is | Licence |
| --- | --- | --- |
| `flatbug-n.onnx` | FlatBug v1.0.0 Nano, exported to ONNX. Third-party weights from https://github.com/darsa-group/flat-bug/ | Software MIT; weight-redistribution risk explicitly accepted by the project owner, 13 September 2026 - see `docs/model-card.md`. |
| `antai-beta.onnx` | AntAI - Beta, a one-class ant detector trained locally by this project on its own camera images. | Project's own model; no third-party redistribution question. |
| `ort.wasm.bundle.min.mjs`, `ort-wasm-simd-threaded.wasm` | ONNX Runtime Web 1.27.0, obtained from the official npm package, included unchanged. | MIT (Microsoft Corporation); see `LICENSE-onnxruntime.txt`. |

Exact byte sizes and SHA-256 hashes are recorded in `docs/model-card.md` alongside each model's own record, so a change here is easy to notice.

These are experimental, not-yet-validated prototypes (see `docs/model-card.md`'s approval template - none of these entries are approved). Never present their output as a confirmed identification.
