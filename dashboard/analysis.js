(() => {
  const { t } = window.i18n;
  const modal = document.querySelector('#analysis-modal');
  const openButton = document.querySelector('#find-insects');
  const closeButton = document.querySelector('#analysis-close');
  const loadCardButton = document.querySelector('#analysis-load-card');
  const analysisChoiceInputs = [...document.querySelectorAll('input[name="analysis-choice"]')];
  const analysisChoiceNote = document.querySelector('#analysis-choice-note');
  const analysisSessionLabel = document.querySelector('#analysis-session-label');
  const analysisSession = document.querySelector('#analysis-session');
  const analysisSessionNote = document.querySelector('#analysis-session-note');
  const cardStatus = document.querySelector('#analysis-card-status');
  const cardTrack = document.querySelector('#analysis-card-track');
  const cardProgress = document.querySelector('#analysis-card-progress');
  const startButton = document.querySelector('#analysis-start');
  const pauseButton = document.querySelector('#analysis-pause');
  const stopButton = document.querySelector('#analysis-stop');
  const setup = document.querySelector('#analysis-setup');
  const scanner = document.querySelector('#analysis-scanner');
  const currentCanvas = document.querySelector('#analysis-current-image');
  const currentCaption = document.querySelector('#analysis-current-caption');
  const progressBar = document.querySelector('#analysis-progress');
  const progressText = document.querySelector('#analysis-progress-text');
  const story = document.querySelector('#analysis-story');
  const discoveryCount = document.querySelector('#analysis-discovery-count');
  const discoveries = document.querySelector('#analysis-discoveries');
  const summary = document.querySelector('#analysis-summary');
  const MODELS = {
    flatbug: { file: 'flatbug-n.onnx', name: 'FlatBug Nano', inputSize: 640, scoreThreshold: .20 },
    antai: { file: 'antai-beta.onnx', name: 'AntAI - Beta', inputSize: 1024, scoreThreshold: .15 },
  };
  const RUNTIME_FILES = ['ort.wasm.bundle.min.mjs', 'ort-wasm-simd-threaded.wasm'];
  const TILE_COLUMNS = 4;
  const TILE_ROWS = 3;
  const IOU_THRESHOLD = .20;
  let ort;
  let session;
  let loadedModelFile;
  let lastFocus;
  const card = window.InsectCard;
  const state = { active: false, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries: [] };

  const say = (text) => { story.textContent = text; };
  const availableEntries = (entries) => entries.filter((entry) => entry.file);
  const runIdOf = (capture) => capture.runId || String(capture.imagePath).split('/')[2] || 'unknown_session';
  // Session names and counts come straight from card.sessionCounts() - the
  // file listing the picker already gave us - not from walking every capture
  // record. Reported 13 September 2026, after fixing fileFor's per-lookup
  // cost: listing sessions still touched every one of 28,717 capture records
  // on the real card just to populate a dropdown, when the file list alone
  // (1,576 entries) already answers "which sessions exist and how many
  // pictures does each have."
  const analysisSessions = () => [...card.sessionCounts()].sort(([first], [second]) => second.localeCompare(first, undefined, { numeric: true }));
  // The capture-to-file match (and the "N older records will be skipped"
  // count it enables) only actually needs doing for the one session in use.
  const entriesForSession = (runId) => (window.InsectData?.captures || [])
    .filter((capture) => capture.imagePath && runIdOf(capture) === runId)
    .map((capture) => ({ capture, file: card.fileFor(capture.imagePath) }));
  const selectedAnalysisEntries = () => entriesForSession(analysisSession.value);
  const selectedSessionLabel = () => analysisSession.selectedOptions[0]?.textContent || t('analysis.noSessionSelected');
  const refreshAnalysisSessions = () => {
    const sessions = analysisSessions(), previous = analysisSession.value;
    analysisSession.replaceChildren();
    sessions.forEach(([runId, count], index) => {
      const option = document.createElement('option');
      option.value = runId;
      option.textContent = t('session.optionLabel', runId, count, index === 0);
      analysisSession.append(option);
    });
    if (sessions.some(([runId]) => runId === previous)) analysisSession.value = previous;
    analysisSessionLabel.hidden = !sessions.length;
    analysisSession.disabled = !sessions.length;
    analysisSessionNote.textContent = sessions.length ? t('analysis.sessionSelected', selectedSessionLabel()) : t('analysis.noSessionsAvailable');
  };
  const ANALYSIS_CHOICES = {
    antai: { model: MODELS.antai, mode: 'quick', noteKey: 'analysisModal.choiceNoteDefault' },
    'flatbug-quick': { model: MODELS.flatbug, mode: 'quick', noteKey: 'analysis.flatbugQuickNote' },
    'flatbug-close': { model: MODELS.flatbug, mode: 'close', noteKey: 'analysis.flatbugCloseNote' },
  };
  const selectedChoice = () => ANALYSIS_CHOICES[analysisChoiceInputs.find((input) => input.checked)?.value || 'antai'];
  const selectedAnalysisMode = () => selectedChoice().mode;
  const selectedModel = () => selectedChoice().model;
  const updateChoiceNote = () => { analysisChoiceNote.textContent = t(selectedChoice().noteKey); };
  const updateProgress = () => {
    const total = state.entries.length;
    const percent = total ? Math.round((state.inspected / total) * 100) : 0;
    progressBar.style.width = `${percent}%`;
    progressText.textContent = t('progress.text', Math.min(state.inspected + 1, total), total);
    discoveryCount.textContent = t('discoveries.count', state.discoveries);
  };
  const clip = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
  const overlap = (first, second) => {
    const left = Math.max(first.x, second.x), top = Math.max(first.y, second.y);
    const right = Math.min(first.x + first.width, second.x + second.width), bottom = Math.min(first.y + first.height, second.y + second.height);
    const shared = Math.max(0, right - left) * Math.max(0, bottom - top);
    return shared / (first.width * first.height + second.width * second.height - shared || 1);
  };
  const suppress = (candidates) => {
    const retained = [];
    for (const candidate of candidates.sort((first, second) => second.score - first.score)) {
      if (retained.every((kept) => overlap(candidate, kept) < IOU_THRESHOLD)) retained.push(candidate);
    }
    return retained;
  };
  const decode = (tensor, scale, padX, padY, tileWidth, tileHeight, offsetX = 0, offsetY = 0) => {
    const output = tensor.data, dimensions = tensor.dims, candidates = [];
    // AntAI Beta's YOLO26 export is end-to-end: [batch, 300, x1/y1/x2/y2/score/class].
    if (dimensions.length === 3 && dimensions[2] === 6) {
      for (let index = 0; index < dimensions[1]; index += 1) {
        const base = index * 6, score = output[base + 4];
        if (score < selectedModel().scoreThreshold) continue;
        const left = clip((output[base] - padX) / scale + offsetX, offsetX, offsetX + tileWidth), top = clip((output[base + 1] - padY) / scale + offsetY, offsetY, offsetY + tileHeight);
        const right = clip((output[base + 2] - padX) / scale + offsetX, offsetX, offsetX + tileWidth), bottom = clip((output[base + 3] - padY) / scale + offsetY, offsetY, offsetY + tileHeight);
        if (right > left && bottom > top) candidates.push({ score, x: left, y: top, width: right - left, height: bottom - top });
      }
      return suppress(candidates);
    }
    // FlatBug Nano is a segmentation export: [batch, 4 box values + 1 insect
    // score + 32 mask coefficients, candidates].  Only channel 4 is a score;
    // coefficients may legitimately be greater than 1 or negative.
    const stride = dimensions.length >= 3 ? dimensions[dimensions.length - 1] : output.length / 5;
    for (let index = 0; index < stride; index += 1) {
      const score = clip(output[4 * stride + index] || 0, 0, 1);
      const width = output[2 * stride + index], height = output[3 * stride + index];
      if (score < selectedModel().scoreThreshold) continue;
      const x = output[index] - width / 2, y = output[stride + index] - height / 2;
      const left = clip((x - padX) / scale + offsetX, offsetX, offsetX + tileWidth), top = clip((y - padY) / scale + offsetY, offsetY, offsetY + tileHeight);
      const right = clip((x + width - padX) / scale + offsetX, offsetX, offsetX + tileWidth), bottom = clip((y + height - padY) / scale + offsetY, offsetY, offsetY + tileHeight);
      if (right > left && bottom > top) candidates.push({ score, x: left, y: top, width: right - left, height: bottom - top });
    }
    return suppress(candidates);
  };
  const positionsForTiles = (length, tileLength, count) => {
    const actualCount = length > tileLength ? count : 1;
    return Array.from({ length: actualCount }, (_, index) => actualCount === 1 ? 0 : Math.round(index * (length - tileLength) / (actualCount - 1)));
  };
  const makeTiles = (image, mode) => {
    if (mode === 'quick') return [{ x: 0, y: 0, width: image.width, height: image.height }];
    const inputSize = selectedModel().inputSize;
    const width = Math.min(inputSize, image.width), height = Math.min(inputSize, image.height);
    return positionsForTiles(image.height, height, TILE_ROWS).flatMap((y) => positionsForTiles(image.width, width, TILE_COLUMNS).map((x) => ({ x, y, width, height })));
  };
  const makeInput = (image, tile) => {
    const inputSize = selectedModel().inputSize;
    const scale = Math.min(inputSize / tile.width, inputSize / tile.height);
    const width = Math.round(tile.width * scale), height = Math.round(tile.height * scale);
    const padX = Math.round((inputSize - width) / 2), padY = Math.round((inputSize - height) / 2);
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = inputSize;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    context.fillStyle = 'rgb(114,114,114)';
    context.fillRect(0, 0, inputSize, inputSize);
    context.drawImage(image, tile.x, tile.y, tile.width, tile.height, padX, padY, width, height);
    const pixels = context.getImageData(0, 0, inputSize, inputSize).data;
    const input = new Float32Array(3 * inputSize * inputSize);
    for (let index = 0; index < inputSize * inputSize; index += 1) {
      input[index] = pixels[index * 4] / 255;
      input[index + inputSize * inputSize] = pixels[index * 4 + 1] / 255;
      input[index + 2 * inputSize * inputSize] = pixels[index * 4 + 2] / 255;
    }
    return { input, scale, padX, padY, width, height, inputSize };
  };
  const drawPicture = (image, boxes) => {
    currentCanvas.width = image.width;
    currentCanvas.height = image.height;
    const context = currentCanvas.getContext('2d');
    context.drawImage(image, 0, 0);
    for (const box of boxes) {
      context.strokeStyle = '#f32b63';
      context.lineWidth = Math.max(3, image.width / 180);
      context.strokeRect(box.x, box.y, box.width, box.height);
      context.fillStyle = '#f32b63';
      context.font = `900 ${Math.max(16, image.width / 30)}px system-ui`;
      context.fillText(t('analysis.possibleInsectLabel', Math.round(box.score * 100)), box.x + 4, Math.max(22, box.y - 5));
    }
  };
  const addDiscovery = (capture, boxes) => {
    state.discoveries += 1;
    discoveries.querySelector('.empty-discoveries')?.remove();
    const card = document.createElement('article');
    card.className = 'discovery-card';
    const thumbnail = document.createElement('img');
    thumbnail.src = capture.imagePath;
    thumbnail.alt = t('analysis.pictureCaption', capture.captureId);
    const heading = document.createElement('h4');
    heading.textContent = t('analysis.possibleInsectHeading');
    const detail = document.createElement('p');
    detail.textContent = t('analysis.discoveryDetail', capture.captureId, boxes.length, Math.round(boxes[0].score * 100));
    card.append(thumbnail, heading, detail);
    discoveries.prepend(card);
    discoveryCount.textContent = t('discoveries.count', state.discoveries);
  };
  const finish = (message) => {
    state.active = false;
    state.paused = false;
    pauseButton.disabled = true;
    stopButton.disabled = true;
    startButton.disabled = !session;
    say(message);
    summary.hidden = false;
    summary.textContent = t('analysis.summaryText', state.inspected, state.discoveries, state.errors);
    const metric = document.querySelector('#inference-status');
    if (metric) metric.textContent = state.discoveries ? t('analysis.metricPossible', state.discoveries) : t('analysis.metricChecked');
  };
  const inspectNext = async () => {
    if (!state.active || state.paused) return;
    const entry = state.entries[state.index];
    if (!entry) return finish(t('analysis.allDone'));
    const { capture, file } = entry;
    let image;
    try {
      image = await createImageBitmap(file);
      const tiles = makeTiles(image, state.mode), candidates = [];
      for (let tileIndex = 0; tileIndex < tiles.length; tileIndex += 1) {
        if (!state.active || state.paused) return;
        const tile = tiles[tileIndex];
        currentCaption.textContent = t('analysis.lookingAtPiece', capture.captureId, tileIndex + 1, tiles.length);
        say(t('analysis.thinkingMessages')[(state.index + tileIndex) % 4]);
        const prepared = makeInput(image, tile);
        const output = await session.run({ [session.inputNames[0]]: new ort.Tensor('float32', prepared.input, [1, 3, prepared.inputSize, prepared.inputSize]) });
        candidates.push(...decode(output[session.outputNames[0]], prepared.scale, prepared.padX, prepared.padY, tile.width, tile.height, tile.x, tile.y));
      }
      const boxes = suppress(candidates);
      drawPicture(image, boxes);
      if (boxes.length) addDiscovery(capture, boxes);
    } catch (error) {
      state.errors += 1;
    } finally {
      image?.close();
    }
    state.index += 1;
    state.inspected += 1;
    updateProgress();
    if (!state.active) return;
    if (state.paused) return say(t('analysis.pausedMessage'));
    window.setTimeout(inspectNext, 0);
  };
  const start = async () => {
    const entries = selectedAnalysisEntries();
    const available = availableEntries(entries);
    const missingPictures = entries.length - available.length;
    if (!card.loaded || !entries.length) return say(t('analysis.noPicturesAtAll'));
    if (!available.length) return say(t('analysis.noAvailableFiles'));
    // The model is fetched here, not on every choice change - see loadCard()
    // and the choice-change handler below for why.
    if (!session || loadedModelFile !== selectedModel().file) {
      startButton.disabled = true;
      say(t('analysis.wakingUp'));
      await loadModel();
      if (!session) return;
    }
    const mode = selectedAnalysisMode();
    Object.assign(state, { active: true, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries: available, mode });
    discoveries.replaceChildren();
    const empty = document.createElement('p');
    empty.className = 'empty-discoveries';
    empty.textContent = t('discoveries.empty');
    discoveries.append(empty);
    summary.hidden = true;
    setup.hidden = true;
    scanner.hidden = false;
    pauseButton.disabled = false;
    stopButton.disabled = false;
    startButton.disabled = true;
    const startMetric = document.querySelector('#inference-status');
    if (startMetric) startMetric.textContent = t('analysis.metricLooking');
    updateProgress();
    if (missingPictures) say(t('analysis.lookingAtAvailable', available.length, missingPictures));
    else say(mode === 'close' ? t('analysis.modeCloseMessage') : t('analysis.modeQuickMessage'));
    inspectNext();
  };
  const setCardProgress = (percent, message) => {
    if (cardTrack && cardProgress) {
      cardTrack.hidden = percent <= 0 || percent >= 100;
      cardProgress.style.width = `${Math.max(4, Math.min(100, percent))}%`;
    }
    if (message) cardStatus.textContent = message;
  };
  const readyMessage = (modelName) => {
    const entries = selectedAnalysisEntries(), available = availableEntries(entries), missing = entries.length - available.length;
    startButton.disabled = !session || !available.length;
    return t('analysis.modelReady', modelName, selectedSessionLabel(), available.length, missing);
  };
  // Shown the whole time the panel is open but no model has been fetched yet
  // (it only loads once Start looking is pressed). Deliberately reads the
  // picture count from card.sessionCounts() - the free, file-based session
  // list - rather than resolving this session's capture records the way
  // readyMessage does. A session only appears in that list because it has at
  // least one real file, so the button-enable decision needs nothing more;
  // the precise "N older records will be skipped" figure is still shown, just
  // by start() right before scanning begins, not repeated here. Found 13
  // September 2026: without this, simply opening the panel resolved the
  // default session's entire capture record set just to print this line -
  // scoped to one session rather than the whole card, but still needless
  // work before the user has asked for anything.
  const cardReadyStatus = () => {
    const count = card.sessionCounts().get(analysisSession.value) || 0;
    startButton.disabled = !count;
    return t('analysis.cardReadyWithSession', selectedSessionLabel(), count);
  };
  const loadModel = async () => {
    const activeModel = selectedModel();
    // Re-opening the panel used to rebuild the whole runtime every time. The
    // model is unchanged unless the AI choice changed, so keep it.
    if (session && loadedModelFile === activeModel.file) {
      setCardProgress(0, readyMessage(activeModel.name));
      return;
    }
    session = undefined;
    loadedModelFile = undefined;
    startButton.disabled = true;
    const model = card.fileByName(activeModel.file);
    const runtime = RUNTIME_FILES.map(card.fileByName);
    const missingRuntime = RUNTIME_FILES.filter((name, index) => !runtime[index]);
    if (!model || missingRuntime.length) {
      setCardProgress(0, t('analysis.missingHelper', activeModel.name, [!model ? activeModel.file : '', ...missingRuntime].filter(Boolean).join(', ')));
      return;
    }
    try {
      setCardProgress(25, t('analysis.openingModel', activeModel.name));
      const urls = [];
      const blobUrl = (file) => { const url = URL.createObjectURL(file); urls.push(url); return url; };
      ort = await import(blobUrl(card.fileByName('ort.wasm.bundle.min.mjs')));
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
      ort.env.wasm.wasmPaths = { wasm: blobUrl(card.fileByName('ort-wasm-simd-threaded.wasm')) };
      setCardProgress(55, t('analysis.readingModel', activeModel.name));
      const weights = new Uint8Array(await model.arrayBuffer());
      setCardProgress(80, t('analysis.startingModel', activeModel.name));
      session = await ort.InferenceSession.create(weights, { executionProviders: ['wasm'] });
      loadedModelFile = activeModel.file;
      setCardProgress(0, readyMessage(activeModel.name));
    } catch (error) {
      session = undefined;
      loadedModelFile = undefined;
      setCardProgress(0, t('analysis.couldNotStart', error instanceof Error ? error.message : String(error)));
    }
  };
  const loadCard = async () => {
    startButton.disabled = true;
    if (!card.loaded) {
      loadCardButton.hidden = false;
      setCardProgress(0, t('analysis.cardStatusShort'));
      return;
    }
    loadCardButton.hidden = true;
    // Sessions come from the pictures alone and are listed before the AI helper
    // is touched. Loading them inside the model step meant a card with no ai/
    // folder showed an empty session list, which looked like the session
    // chooser itself was broken (reported 12 September 2026).
    refreshAnalysisSessions();
    if (!analysisSessions().length) {
      session = undefined;
      loadedModelFile = undefined;
      loadCardButton.hidden = false;
      setCardProgress(0, t('analysis.noSavedPicturesInFolder'));
      return;
    }
    // The AI helper itself is deliberately not touched here - it loads only
    // when Start looking is pressed (see start()). Reported 13 September
    // 2026: switching between AI choices felt laggy because every switch used
    // to trigger a full model fetch and WebAssembly runtime start
    // immediately, before the user had asked to run anything.
    setCardProgress(0, cardReadyStatus());
  };
  const open = () => { lastFocus = document.activeElement; modal.hidden = false; setup.hidden = false; scanner.hidden = true; if (card.loaded) loadCard(); else loadCardButton.focus(); };
  const close = () => { state.active = false; modal.hidden = true; if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus(); };
  if (!modal || !openButton || !loadCardButton) return;
  openButton.addEventListener('click', (event) => { event.stopImmediatePropagation(); open(); }, true);
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  analysisChoiceInputs.forEach((input) => input.addEventListener('change', () => {
    updateChoiceNote();
    // No model fetch here - only Start looking loads one (see start()). If a
    // different model was already loaded from an earlier search, session
    // still refers to it; start() compares loadedModelFile against the newly
    // selected one and reloads only if they actually differ.
    if (card.loaded) setCardProgress(0, cardReadyStatus());
    else startButton.disabled = true;
  }));
  analysisSession.addEventListener('change', () => {
    analysisSessionNote.textContent = t('analysis.sessionSelected', selectedSessionLabel());
    cardStatus.textContent = session && loadedModelFile === selectedModel().file ? readyMessage(selectedModel().name) : cardReadyStatus();
  });
  updateChoiceNote();
  loadCardButton.addEventListener('click', () => card.request());
  window.addEventListener('insect-card-progress', (event) => { if (!modal.hidden) setCardProgress(event.detail.percent, event.detail.message); });
  window.addEventListener('insect-card-cancelled', () => { if (!modal.hidden) setCardProgress(0, t('analysis.noFolderChosen')); });
  // The card is chosen once for the whole page. When the movie maker or the
  // front-page picture check loaded it, this section must already know.
  window.addEventListener('insect-card-loaded', () => {
    if (!modal.hidden) { loadCard(); return; }
    loadCardButton.hidden = card.loaded;
    refreshAnalysisSessions();
    if (card.loaded) cardStatus.textContent = t('analysis.cardReadyBackground');
  });
  startButton.addEventListener('click', start);
  pauseButton.addEventListener('click', () => {
    if (!state.active) return;
    state.paused = !state.paused;
    pauseButton.textContent = state.paused ? t('analysis.keepLooking') : t('analysisScanner.pause');
    if (state.paused) say(t('analysis.finishingThenPausing'));
    else inspectNext();
  });
  stopButton.addEventListener('click', () => { if (state.active) finish(t('analysis.searchStopped')); });
  window.i18n.onLocaleChange(() => {
    updateChoiceNote();
    pauseButton.textContent = state.paused ? t('analysis.keepLooking') : t('analysisScanner.pause');
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) { event.stopImmediatePropagation(); close(); } }, true);
})();
