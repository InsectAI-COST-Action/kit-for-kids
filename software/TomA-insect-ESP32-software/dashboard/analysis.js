(() => {
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
  let lastFocus;
  const card = window.InsectCard;
  const state = { active: false, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries: [] };

  const say = (text) => { story.textContent = text; };
  const fileForCapture = (capture) => card.fileFor(capture.imagePath);
  const expectedEntries = () => (window.InsectData?.captures || [])
    .filter((capture) => capture.imagePath)
    .map((capture) => ({ capture, file: fileForCapture(capture) }));
  const availableEntries = (entries) => entries.filter((entry) => entry.file);
  const sessionId = (entry) => entry.capture.runId || String(entry.capture.imagePath).split('/')[2] || 'unknown_session';
  const analysisSessions = () => {
    const sessions = new Map();
    for (const entry of availableEntries(expectedEntries())) {
      const runId = sessionId(entry), group = sessions.get(runId) || [];
      group.push(entry);
      sessions.set(runId, group);
    }
    return [...sessions.entries()].sort(([first], [second]) => second.localeCompare(first, undefined, { numeric: true }));
  };
  const selectedAnalysisEntries = () => expectedEntries().filter((entry) => sessionId(entry) === analysisSession.value);
  const selectedSessionLabel = () => analysisSession.selectedOptions[0]?.textContent || 'No session selected';
  const refreshAnalysisSessions = () => {
    const sessions = analysisSessions(), previous = analysisSession.value;
    analysisSession.replaceChildren();
    sessions.forEach(([runId, entries], index) => {
      const option = document.createElement('option');
      option.value = runId;
      option.textContent = `${index === 0 ? 'Newest session - ' : ''}${runId} (${entries.length} pictures)`;
      analysisSession.append(option);
    });
    if (sessions.some(([runId]) => runId === previous)) analysisSession.value = previous;
    analysisSessionLabel.hidden = !sessions.length;
    analysisSession.disabled = !sessions.length;
    analysisSessionNote.textContent = sessions.length ? `${selectedSessionLabel()} is selected. The AI will only look at these pictures.` : 'There are no saved picture sessions available on this card.';
  };
  const ANALYSIS_CHOICES = {
    antai: { model: MODELS.antai, mode: 'quick', note: 'AntAI - Beta is selected: it only looks for ants, and its clues can still be wrong.' },
    'flatbug-quick': { model: MODELS.flatbug, mode: 'quick', note: 'FlatBug Quick look is selected: one fast check of each whole picture.' },
    'flatbug-close': { model: MODELS.flatbug, mode: 'close', note: 'FlatBug Look closely is selected: 12 zoomed-in checks for each picture, so it takes longer.' },
  };
  const selectedChoice = () => ANALYSIS_CHOICES[analysisChoiceInputs.find((input) => input.checked)?.value || 'antai'];
  const selectedAnalysisMode = () => selectedChoice().mode;
  const selectedModel = () => selectedChoice().model;
  const updateChoiceNote = () => { analysisChoiceNote.textContent = selectedChoice().note; };
  const updateProgress = () => {
    const total = state.entries.length;
    const percent = total ? Math.round((state.inspected / total) * 100) : 0;
    progressBar.style.width = `${percent}%`;
    progressText.textContent = `Picture ${Math.min(state.inspected + 1, total)} of ${total}`;
    discoveryCount.textContent = `${state.discoveries} possible insect${state.discoveries === 1 ? '' : 's'} found`;
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
      context.fillText(`${Math.round(box.score * 100)}% possible insect`, box.x + 4, Math.max(22, box.y - 5));
    }
  };
  const addDiscovery = (capture, boxes) => {
    state.discoveries += 1;
    discoveries.querySelector('.empty-discoveries')?.remove();
    const card = document.createElement('article');
    card.className = 'discovery-card';
    const thumbnail = document.createElement('img');
    thumbnail.src = capture.imagePath;
    thumbnail.alt = `Picture ${capture.captureId}`;
    const heading = document.createElement('h4');
    heading.textContent = 'A possible insect!';
    const detail = document.createElement('p');
    detail.textContent = `${capture.captureId} - ${boxes.length} possible insect${boxes.length === 1 ? '' : 's'} - strongest clue ${Math.round(boxes[0].score * 100)}%`;
    card.append(thumbnail, heading, detail);
    discoveries.prepend(card);
    discoveryCount.textContent = `${state.discoveries} possible insect${state.discoveries === 1 ? '' : 's'} found`;
  };
  const finish = (message) => {
    state.active = false;
    state.paused = false;
    pauseButton.disabled = true;
    stopButton.disabled = true;
    startButton.disabled = !session;
    say(message);
    summary.hidden = false;
    summary.textContent = `${state.inspected} picture${state.inspected === 1 ? '' : 's'} checked. ${state.discoveries} possible insect${state.discoveries === 1 ? '' : 's'} found.${state.errors ? ` ${state.errors} picture${state.errors === 1 ? '' : 's'} could not be checked.` : ''} These are experimental predictions and AI can make mistakes.`;
    const metric = document.querySelector('#inference-status');
    if (metric) metric.textContent = state.discoveries ? `${state.discoveries} possible` : 'Checked';
  };
  const inspectNext = async () => {
    if (!state.active || state.paused) return;
    const entry = state.entries[state.index];
    if (!entry) return finish('That is every picture. What a careful search!');
    const { capture, file } = entry;
    let image;
    try {
      image = await createImageBitmap(file);
      const tiles = makeTiles(image, state.mode), candidates = [];
      for (let tileIndex = 0; tileIndex < tiles.length; tileIndex += 1) {
        if (!state.active || state.paused) return;
        const tile = tiles[tileIndex];
        currentCaption.textContent = `Looking at ${capture.captureId} - piece ${tileIndex + 1} of ${tiles.length}`;
        say(['Looking carefully...', 'Searching the shapes...', 'Checking for tiny wings and legs...', 'Being a brilliant bug detective...'][(state.index + tileIndex) % 4]);
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
    if (state.paused) return say('Paused. Your discoveries are safe on this page.');
    window.setTimeout(inspectNext, 0);
  };
  const start = () => {
    const entries = selectedAnalysisEntries();
    const available = availableEntries(entries);
    const missingPictures = entries.length - available.length;
    if (!session) return say('Load images and AI first.');
    if (!entries.length) return say('There are no saved pictures for the AI to look at yet.');
    if (!available.length) return say('There are no saved picture files available for the AI to look at yet.');
    const mode = selectedAnalysisMode();
    Object.assign(state, { active: true, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries: available, mode });
    discoveries.replaceChildren();
    const empty = document.createElement('p');
    empty.className = 'empty-discoveries';
    empty.textContent = 'No clues yet - the AI is still looking carefully.';
    discoveries.append(empty);
    summary.hidden = true;
    setup.hidden = true;
    scanner.hidden = false;
    pauseButton.disabled = false;
    stopButton.disabled = false;
    startButton.disabled = true;
    document.querySelector('#inference-status').textContent = 'Looking...';
    updateProgress();
    if (missingPictures) say(`Looking at ${available.length} available pictures. ${missingPictures} older record${missingPictures === 1 ? '' : 's'} without image files will be skipped.`);
    else say(mode === 'close' ? 'Looking closely in 12 picture pieces for tiny possible insects...' : 'Taking a quick look through each whole picture...');
    inspectNext();
  };
  const loadCard = async () => {
    session = undefined;
    startButton.disabled = true;
    if (!card.loaded) {
      loadCardButton.hidden = false;
      cardStatus.textContent = 'Press Load images and AI, then choose the INSECT-AI drive in the next window.';
      return;
    }
    const activeModel = selectedModel();
    const model = card.fileByName(activeModel.file);
    const runtime = RUNTIME_FILES.map(card.fileByName);
    const missingRuntime = RUNTIME_FILES.filter((name, index) => !runtime[index]);
    if (!model || missingRuntime.length) {
      cardStatus.textContent = `This folder needs the ${activeModel.name} file and AI runtime in ai/: ${[!model ? activeModel.file : '', ...missingRuntime].filter(Boolean).join(', ')}.`;
      return;
    }
    try {
      cardStatus.textContent = `Opening ${activeModel.name} and waking up the AI helper...`;
      const urls = [];
      const blobUrl = (file) => { const url = URL.createObjectURL(file); urls.push(url); return url; };
      ort = await import(blobUrl(card.fileByName('ort.wasm.bundle.min.mjs')));
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
      ort.env.wasm.wasmPaths = { wasm: blobUrl(card.fileByName('ort-wasm-simd-threaded.wasm')) };
      session = await ort.InferenceSession.create(new Uint8Array(await model.arrayBuffer()), { executionProviders: ['wasm'] });
      refreshAnalysisSessions();
      const entries = selectedAnalysisEntries();
      const available = availableEntries(entries);
      const missingPictures = entries.length - available.length;
      if (!available.length) {
        cardStatus.textContent = `No saved picture files are available. ${missingPictures} record${missingPictures === 1 ? '' : 's'} refer to images that are no longer on this card.`;
        return;
      }
      cardStatus.textContent = `${activeModel.name} is ready! I found ${available.length} saved picture${available.length === 1 ? '' : 's'}. ${missingPictures ? `${missingPictures} older record${missingPictures === 1 ? '' : 's'} without image files will be skipped. ` : ''}Press Start looking.`;
      loadCardButton.hidden = true;
      startButton.disabled = false;
    } catch (error) {
      cardStatus.textContent = `The AI helper could not start: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  const open = () => { lastFocus = document.activeElement; modal.hidden = false; setup.hidden = false; scanner.hidden = true; if (card.loaded) loadCard(); else loadCardButton.focus(); };
  const close = () => { state.active = false; modal.hidden = true; if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus(); };
  if (!modal || !openButton || !loadCardButton) return;
  openButton.addEventListener('click', (event) => { event.stopImmediatePropagation(); open(); }, true);
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  analysisChoiceInputs.forEach((input) => input.addEventListener('change', () => { updateChoiceNote(); session = undefined; startButton.disabled = true; if (card.loaded) loadCard(); }));
  analysisSession.addEventListener('change', () => {
    const entries = selectedAnalysisEntries(), available = availableEntries(entries), missing = entries.length - available.length;
    analysisSessionNote.textContent = `${selectedSessionLabel()} is selected. The AI will only look at these pictures.`;
    if (session) {
      cardStatus.textContent = `${selectedModel().name} is ready! ${selectedSessionLabel()} is selected.${missing ? ` ${missing} older record${missing === 1 ? '' : 's'} without image files will be skipped.` : ''} Press Start looking.`;
      startButton.disabled = !available.length;
    }
  });
  updateChoiceNote();
  loadCardButton.addEventListener('click', () => card.request());
  window.addEventListener('insect-card-loaded', () => { if (!modal.hidden) loadCard(); });
  startButton.addEventListener('click', start);
  pauseButton.addEventListener('click', () => {
    if (!state.active) return;
    state.paused = !state.paused;
    pauseButton.textContent = state.paused ? 'Keep looking' : 'Pause search';
    if (state.paused) say('Finishing this picture, then pausing...');
    else inspectNext();
  });
  stopButton.addEventListener('click', () => { if (state.active) finish('Search stopped. You can start a new search whenever you like.'); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) { event.stopImmediatePropagation(); close(); } }, true);
})();
