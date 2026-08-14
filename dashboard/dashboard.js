(() => {
  const data = window.InsectData = window.InsectData || {};
  data.captures = data.captures || [];
  data.addCapture = data.addCapture || ((capture) => data.captures.push(capture));

  const initialLimit = 10;
  let showAllFrames = false;
  let showAllImages = false;
  let lastFocus = null;

  const status = document.querySelector('#status');
  const main = document.querySelector('#dashboard-main');
  const loadingScreen = document.querySelector('#loading-screen');
  const loadingMessage = document.querySelector('#loading-message');
  const loadingDetail = document.querySelector('#loading-detail');
  const loadingProgress = document.querySelector('#loading-progress');
  const loadingError = document.querySelector('#loading-error');
  const loadingRetry = document.querySelector('#loading-retry');
  const rows = document.querySelector('#capture-rows');
  const gallery = document.querySelector('#gallery');
  const galleryEmpty = document.querySelector('#gallery-empty');
  const search = document.querySelector('#search');
  const frameToggle = document.querySelector('#capture-toggle');
  const galleryToggle = document.querySelector('#gallery-toggle');
  const modal = document.querySelector('#image-modal');
  const modalImage = document.querySelector('#modal-image');
  const modalCaption = document.querySelector('#modal-caption');
  const modalClose = document.querySelector('#modal-close');
  const modelModal = document.querySelector('#model-modal');
  const modelModalClose = document.querySelector('#model-modal-close');
  const modelModalOk = document.querySelector('#model-modal-ok');

  const setLoading = (message, detail, progress) => {
    loadingMessage.textContent = message;
    loadingDetail.textContent = detail;
    loadingProgress.style.width = `${Math.max(8, Math.min(100, progress))}%`;
  };

  const loadScript = (source) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = source;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${source}`));
    document.head.append(script);
  });

  const relativeTime = (milliseconds) => `${((Number(milliseconds) || 0) / 1000).toFixed(1)} seconds`;
  const filteredCaptures = () => {
    const query = search.value.trim().toLowerCase();
    return data.captures.filter((capture) => !query ||
      String(capture.captureId || '').toLowerCase().includes(query) ||
      String(capture.outcome || '').toLowerCase().includes(query));
  };
  const cell = (row, value) => {
    const element = document.createElement('td');
    element.textContent = value;
    row.append(element);
  };
  const openImage = (path, caption) => {
    lastFocus = document.activeElement;
    modalImage.src = path;
    modalImage.alt = caption;
    modalCaption.textContent = caption;
    modal.hidden = false;
    modalClose.focus();
  };
  const closeImage = () => {
    modal.hidden = true;
    modalImage.removeAttribute('src');
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  };
  const openModelMessage = () => {
    lastFocus = document.activeElement;
    modelModal.hidden = false;
    modelModalClose.focus();
  };
  const closeModelMessage = () => {
    modelModal.hidden = true;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  };

  const render = () => {
    const captures = filteredCaptures();
    const allImages = data.captures.filter((capture) => capture.imagePath);
    const images = captures.filter((capture) => capture.imagePath);
    const averageCaptureMs = captures.length
      ? Math.round(captures.reduce((total, capture) => total + (Number(capture.captureMs) || 0), 0) / captures.length) : 0;
    const averageCaptureSeconds = (averageCaptureMs / 1000).toFixed(2);
    const inferenceOutcomes = new Set(data.captures.map((capture) => capture.inferenceOutcome).filter(Boolean));
    const inferenceText = !data.captures.length ? 'No data'
      : inferenceOutcomes.size === 1 && inferenceOutcomes.has('model_unavailable') ? 'Coming soon'
      : [...inferenceOutcomes].join(', ') || 'Ready';

    document.querySelector('#welcome-count').textContent = String(data.captures.length);
    document.querySelector('#capture-count').textContent = String(data.captures.length);
    document.querySelector('#image-count').textContent = String(allImages.length);
    document.querySelector('#gallery-count').textContent = `${allImages.length} picture${allImages.length === 1 ? '' : 's'}`;
    document.querySelector('#capture-time').textContent = captures.length ? `${averageCaptureSeconds} seconds` : '-';
    document.querySelector('#inference-status').textContent = inferenceText;

    const visibleCaptures = (showAllFrames ? captures : captures.slice(-initialLimit)).slice().reverse();
    rows.replaceChildren();
    visibleCaptures.forEach((capture) => {
      const row = document.createElement('tr');
      cell(row, capture.captureId || 'Unknown capture');
      cell(row, relativeTime(capture.uptimeMs));
      cell(row, capture.outcome || 'Unknown');
      const imageCell = document.createElement('td');
      if (capture.imagePath) {
        const link = document.createElement('button');
        link.className = 'inline-button';
        link.type = 'button';
        link.textContent = 'Open image';
        link.addEventListener('click', () => openImage(capture.imagePath, `Frame ${capture.captureId}`));
        imageCell.append(link);
      } else imageCell.textContent = 'Unavailable';
      row.append(imageCell);
      rows.append(row);
    });
    frameToggle.hidden = captures.length <= initialLimit;
    frameToggle.textContent = showAllFrames ? 'Show fewer frames' : 'Show all frames';

    const visibleImages = (showAllImages ? images : images.slice(-initialLimit)).slice().reverse();
    gallery.replaceChildren();
    galleryEmpty.hidden = images.length > 0;
    galleryEmpty.textContent = images.length ? '' : (search.value.trim() ? 'No pictures match that search.' : 'No committed images are available yet.');
    const template = document.querySelector('#gallery-item-template');
    visibleImages.forEach((capture) => {
      const item = template.content.firstElementChild.cloneNode(true);
      const image = item.querySelector('img');
      image.src = capture.imagePath;
      image.alt = `Frame ${capture.captureId}`;
      item.querySelector('span').textContent = capture.captureId;
      item.addEventListener('click', () => openImage(capture.imagePath, `Frame ${capture.captureId}`));
      gallery.append(item);
    });
    galleryToggle.hidden = images.length <= initialLimit;
    galleryToggle.textContent = showAllImages ? 'Show fewer images' : 'Show all images';
    document.querySelector('#model-note').textContent = inferenceOutcomes.has('model_unavailable')
      ? 'The AI model is not connected yet. Your pictures are safe and ready for the next step.'
      : 'AI results are ready to explore.';
    document.title = `Camera adventure - ${data.captures.length} pictures`;
  };

  const finishLoading = () => {
    loadingProgress.style.width = '100%';
    window.setTimeout(() => {
      loadingScreen.hidden = true;
      loadingScreen.setAttribute('aria-busy', 'false');
      main.setAttribute('aria-busy', 'false');
    }, 180);
  };

  const load = async () => {
    const chunks = data.manifest?.captureChunks || [];
    const failures = [];
    let currentLoaded = false;
    const totalSteps = Math.max(1, chunks.length + 1);
    setLoading('Finding your pictures on the card.', 'Reading the current session', 12);
    try {
      await loadScript('data/captures_current.js');
      currentLoaded = true;
    } catch (error) {
      // The current chunk is optional when the camera finished cleanly.
    }
    setLoading('Finding your pictures on the card.', currentLoaded ? 'Found the newest pictures' : 'Checking saved picture groups', 100 / totalSteps);
    for (const [index, chunk] of chunks.entries()) {
      try {
        await loadScript(chunk);
      } catch (error) {
        failures.push(error.message);
      }
      setLoading('Putting your pictures in order.', `Picture group ${index + 1} of ${chunks.length}`, ((index + 2) / totalSteps) * 100);
    }
    if (failures.length) {
      status.textContent = `Some picture groups could not be opened (${failures.length}). The pictures that loaded are still available.`;
      status.classList.add('status-warning');
      if (!data.captures.length) {
        loadingMessage.textContent = 'Your pictures need a little help to open.';
        loadingDetail.textContent = 'No picture groups could be read from this card.';
        loadingProgress.style.width = '100%';
        loadingError.hidden = false;
        return;
      }
    } else if (data.captures.length) {
      status.textContent = `Ready! Your camera saved ${data.captures.length} picture${data.captures.length === 1 ? '' : 's'}.`;
    } else {
      status.textContent = 'No pictures are on this card yet. Try another camera card or run.';
    }
    render();
    finishLoading();
  };

  frameToggle.addEventListener('click', () => { showAllFrames = !showAllFrames; render(); });
  galleryToggle.addEventListener('click', () => { showAllImages = !showAllImages; render(); });
  modalClose.addEventListener('click', closeImage);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeImage(); });
  document.querySelector('#find-insects').addEventListener('click', openModelMessage);
  modelModalClose.addEventListener('click', closeModelMessage);
  modelModalOk.addEventListener('click', closeModelMessage);
  modelModal.addEventListener('click', (event) => { if (event.target === modelModal) closeModelMessage(); });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!modal.hidden) closeImage();
    else if (!modelModal.hidden) closeModelMessage();
  });
  search.addEventListener('input', render);
  loadingRetry.addEventListener('click', () => window.location.reload());
  load();
})();
