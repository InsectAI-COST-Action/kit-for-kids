(() => {
  "use strict";
  const button = document.querySelector("#run-check");
  const status = document.querySelector("#status");
  const model = window.FlatBugSpikeModel;
  const setStatus = (message, state) => { status.textContent = message; status.dataset.loadState = state; };
  const explainError = (error) => {
    const detail = error instanceof Error ? error.message : String(error);
    return `The local load check did not complete: ${detail}`;
  };
  button.addEventListener("click", async () => {
    if (location.protocol !== "file:") { setStatus("This experiment must be opened from file://, not a web server.", "error"); return; }
    if (!window.ort) { setStatus("ONNX Runtime Web did not load from the local vendor folder.", "error"); return; }
    button.disabled = true;
    setStatus("Loading local WebAssembly files and FlatBug modelâ€¦", "loading");
    try {
      window.ort.env.wasm.numThreads = 1;
      window.ort.env.wasm.proxy = false;
      const vendorUrl = new URL("./vendor/onnxruntime/", window.location.href);
      const runtimeFiles = [
        "ort-wasm-simd-threaded.wasm", "ort-wasm-simd-threaded.mjs",
        "ort-wasm-simd-threaded.asyncify.wasm", "ort-wasm-simd-threaded.asyncify.mjs",
        "ort-wasm-simd-threaded.jsep.wasm", "ort-wasm-simd-threaded.jsep.mjs",
        "ort-wasm-simd-threaded.jspi.wasm", "ort-wasm-simd-threaded.jspi.mjs",
      ];
      window.ort.env.wasm.wasmPaths = Object.fromEntries(
        runtimeFiles.map((file) => [file, new URL(file, vendorUrl).href]),
      );
      const session = await window.ort.InferenceSession.create(new URL(model.onnxPath, window.location.href).href, { executionProviders: ["wasm"], graphOptimizationLevel: "all" });
      const inputs = session.inputNames.join(", ");
      const outputs = session.outputNames.join(", ");
      await session.release();
      setStatus(`Success. Local WebAssembly runtime and FlatBug model loaded from file://. Inputs: ${inputs}. Outputs: ${outputs}.`, "success");
    } catch (error) { setStatus(explainError(error), "error"); } finally { button.disabled = false; }
  });
})();

if (new URLSearchParams(location.search).has('autorun')) { document.querySelector('#run-check').click(); }
