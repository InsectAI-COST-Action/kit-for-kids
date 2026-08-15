(() => {
  const modal = document.querySelector('#analysis-modal');
  const openButton = document.querySelector('#find-insects');
  const closeButton = document.querySelector('#analysis-close');
  const cardInput = document.querySelector('#analysis-card');
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
  const MODEL_FILE = 'flatbug-n.onnx';
  const RUNTIME_FILES = ['ort.wasm.bundle.min.mjs', 'ort-wasm-simd-threaded.wasm'];
  const INPUT_SIZE = 640;
  const SCORE_THRESHOLD = .20;
  const IOU_THRESHOLD = .20;
  const MINIMUM_BOX_SIZE = 32;
  let ort;
  let session;
  let lastFocus;
  let selectedFiles = new Map();
  const state = { active: false, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries: [] };

  const say = (text) => { story.textContent = text; };
  const normalisePath = (value) => String(value || '').replaceAll('\\', '/').replace(/^\.\//, '').toLowerCase();
  const fileByName = (name) => {
    const wanted = name.toLowerCase();
    for (const [path, file] of selectedFiles) if (path === wanted || path.endsWith(`/${wanted}`)) return file;
    return undefined;
  };
  const fileForCapture = (capture) => {
    const wanted = normalisePath(capture.imagePath);
    return selectedFiles.get(wanted) || fileByName(wanted);
  };
  const expectedEntries = () => (window.InsectData?.captures || [])
    .filter((capture) => capture.imagePath)
    .map((capture) => ({ capture, file: fileForCapture(capture) }));
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
  const decode = (output, scale, padX, padY, imageWidth, imageHeight) => {
    const stride = 8400, candidates = [];
    for (let index = 0; index < stride; index += 1) {
      const score = output[4 * stride + index];
      const width = output[2 * stride + index], height = output[3 * stride + index];
      if (score < SCORE_THRESHOLD || Math.sqrt(width * height) < MINIMUM_BOX_SIZE) continue;
      const x = output[index] - width / 2, y = output[stride + index] - height / 2;
      const left = clip((x - padX) / scale, 0, imageWidth), top = clip((y - padY) / scale, 0, imageHeight);
      const right = clip((x + width - padX) / scale, 0, imageWidth), bottom = clip((y + height - padY) / scale, 0, imageHeight);
      if (right > left && bottom > top) candidates.push({ score, x: left, y: top, width: right - left, height: bottom - top });
    }
    return suppress(candidates);
  };
  const makeInput = (image, scale, padX, padY, width, height) => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = INPUT_SIZE;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    context.fillStyle = 'rgb(114,114,114)';
    context.fillRect(0, 0, INPUT_SIZE, INPUT_SIZE);
    context.drawImage(image, padX, padY, width, height);
    const pixels = context.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE).data;
    const input = new Float32Array(3 * INPUT_SIZE * INPUT_SIZE);
    for (let index = 0; index < INPUT_SIZE * INPUT_SIZE; index += 1) {
      input[index] = pixels[index * 4] / 255;
      input[index + INPUT_SIZE * INPUT_SIZE] = pixels[index * 4 + 1] / 255;
      input[index + 2 * INPUT_SIZE * INPUT_SIZE] = pixels[index * 4 + 2] / 255;
    }
    return input;
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
    currentCaption.textContent = `Looking at ${capture.captureId}`;
    say(['Looking carefully...', 'Searching the shapes...', 'Checking for tiny wings and legs...', 'Being a brilliant bug detective...'][state.index % 4]);
    let image;
    try {
      image = await createImageBitmap(file);
      const scale = Math.min(INPUT_SIZE / image.width, INPUT_SIZE / image.height);
      const width = Math.round(image.width * scale), height = Math.round(image.height * scale);
      const padX = Math.round((INPUT_SIZE - width) / 2), padY = Math.round((INPUT_SIZE - height) / 2);
      const input = makeInput(image, scale, padX, padY, width, height);
      const output = await session.run({ images: new ort.Tensor('float32', input, [1, 3, INPUT_SIZE, INPUT_SIZE]) });
      const boxes = decode(output.output0.data, scale, padX, padY, image.width, image.height);
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
    const entries = expectedEntries();
    const missing = entries.filter((entry) => !entry.file);
    if (!session) return say('Choose your camera card first.');
    if (!entries.length) return say('There are no saved pictures for the AI to look at yet.');
    if (missing.length) return say(`Please choose the whole camera card again. ${missing.length} saved picture${missing.length === 1 ? ' is' : 's are'} missing.`);
    Object.assign(state, { active: true, paused: false, index: 0, inspected: 0, errors: 0, discoveries: 0, entries });
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
    inspectNext();
  };
  const loadCard = async () => {
    selectedFiles = new Map();
    for (const file of cardInput.files) {
      const relative = normalisePath(file.webkitRelativePath || file.name);
      selectedFiles.set(relative, file);
      selectedFiles.set(normalisePath(file.name), file);
    }
    session = undefined;
    startButton.disabled = true;
    const model = fileByName(MODEL_FILE);
    const runtime = RUNTIME_FILES.map(fileByName);
    const missingRuntime = RUNTIME_FILES.filter((name, index) => !runtime[index]);
    if (!model || missingRuntime.length) {
      cardStatus.textContent = `This folder needs the AI files in ai/: ${[!model ? MODEL_FILE : '', ...missingRuntime].filter(Boolean).join(', ')}.`;
      return;
    }
    try {
      cardStatus.textContent = 'Opening the camera card and waking up the AI helper...';
      const urls = [];
      const blobUrl = (file) => { const url = URL.createObjectURL(file); urls.push(url); return url; };
      ort = await import(blobUrl(fileByName('ort.wasm.bundle.min.mjs')));
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.proxy = false;
      ort.env.wasm.wasmPaths = { wasm: blobUrl(fileByName('ort-wasm-simd-threaded.wasm')) };
      session = await ort.InferenceSession.create(new Uint8Array(await model.arrayBuffer()), { executionProviders: ['wasm'] });
      const entries = expectedEntries();
      const missingPictures = entries.filter((entry) => !entry.file).length;
      if (missingPictures) {
        cardStatus.textContent = `The AI helper is ready, but ${missingPictures} saved picture${missingPictures === 1 ? ' is' : 's are'} missing. Choose the top camera-card folder.`;
        return;
      }
      cardStatus.textContent = `Camera card ready! I found ${entries.length} saved picture${entries.length === 1 ? '' : 's'}. Press Start looking.`;
      startButton.disabled = false;
    } catch (error) {
      cardStatus.textContent = `The AI helper could not start: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  const open = () => { lastFocus = document.activeElement; modal.hidden = false; setup.hidden = false; scanner.hidden = true; cardInput.focus(); };
  const close = () => { state.active = false; modal.hidden = true; if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus(); };
  openButton.addEventListener('click', (event) => { event.stopImmediatePropagation(); open(); }, true);
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  cardInput.addEventListener('change', loadCard);
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
