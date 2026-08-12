(() => {
  const data = window.InsectData = window.InsectData || {};
  data.captures = data.captures || [];
  data.addCapture = data.addCapture || ((capture) => data.captures.push(capture));
  const initialLimit = 10;
  let showAllFrames = false;
  let showAllImages = false;

  const status = document.querySelector('#status');
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

  const loadScript = (source) => new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = source;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${source}`));
    document.head.append(script);
  });

  const relativeTime = (milliseconds) => `${(milliseconds / 1000).toFixed(1)} s`;
  const filteredCaptures = () => {
    const query = search.value.trim().toLowerCase();
    return data.captures.filter((capture) => !query ||
      capture.captureId.toLowerCase().includes(query) || capture.outcome.toLowerCase().includes(query));
  };
  const cell = (row, value) => {
    const element = document.createElement('td');
    element.textContent = value;
    row.append(element);
  };
  const openImage = (path, caption) => {
    modalImage.src = path;
    modalImage.alt = caption;
    modalCaption.textContent = caption;
    modal.hidden = false;
    modalClose.focus();
  };
  const closeImage = () => {
    modal.hidden = true;
    modalImage.removeAttribute('src');
  };

  const render = () => {
    const captures = filteredCaptures();
    const images = captures.filter((capture) => capture.imagePath);
    const averageCaptureMs = captures.length
      ? Math.round(captures.reduce((total, capture) => total + capture.captureMs, 0) / captures.length) : 0;
    const inferenceOutcomes = new Set(captures.map((capture) => capture.inferenceOutcome));
    document.querySelector('#capture-count').textContent = String(data.captures.length);
    document.querySelector('#image-count').textContent = String(images.length);
    document.querySelector('#capture-time').textContent = captures.length ? `${averageCaptureMs} ms` : '-';
    document.querySelector('#inference-status').textContent = inferenceOutcomes.size ? [...inferenceOutcomes].join(', ') : 'No data';

    const visibleCaptures = showAllFrames ? captures : captures.slice(-initialLimit);
    rows.replaceChildren();
    visibleCaptures.reverse().forEach((capture) => {
      const row = document.createElement('tr');
      cell(row, capture.captureId);
      cell(row, relativeTime(capture.uptimeMs));
      cell(row, capture.outcome);
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
    frameToggle.hidden = captures.length === 0;
    frameToggle.disabled = captures.length <= initialLimit;
    frameToggle.textContent = showAllFrames ? 'Show fewer frames' : (captures.length <= initialLimit ? 'All frames shown' : `Show all ${captures.length} frames`);

    const visibleImages = showAllImages ? images : images.slice(-initialLimit);
    gallery.replaceChildren();
    galleryEmpty.hidden = images.length > 0;
    const template = document.querySelector('#gallery-item-template');
    visibleImages.reverse().forEach((capture) => {
      const item = template.content.firstElementChild.cloneNode(true);
      const image = item.querySelector('img');
      image.src = capture.imagePath;
      image.alt = `Frame ${capture.captureId}`;
      item.querySelector('span').textContent = capture.captureId;
      item.addEventListener('click', () => openImage(capture.imagePath, `Frame ${capture.captureId}`));
      gallery.append(item);
    });
    galleryToggle.hidden = images.length === 0;
    galleryToggle.disabled = images.length <= initialLimit;
    galleryToggle.textContent = showAllImages ? 'Show fewer images' : (images.length <= initialLimit ? 'All images shown' : `Show all ${images.length} images`);
  };

  const load = async () => {
    const chunks = data.manifest?.captureChunks || [];
    const failures = [];
    let currentLoaded = false;
    try { await loadScript('data/captures_current.js'); currentLoaded = true; } catch (error) { /* optional */ }
    for (const chunk of chunks) {
      try { await loadScript(chunk); } catch (error) { failures.push(error.message); }
    }
    status.textContent = failures.length ? `Loaded data with ${failures.length} unavailable closed chunk(s).`
      : (!chunks.length && !currentLoaded ? 'No dashboard data chunks are available yet.'
      : currentLoaded ? `Loaded ${chunks.length} closed chunk(s) and the current open chunk.`
      : `Loaded ${chunks.length} closed data chunk(s).`);
    render();
  };

  frameToggle.addEventListener('click', () => { showAllFrames = !showAllFrames; render(); });
  galleryToggle.addEventListener('click', () => { showAllImages = !showAllImages; render(); });
  modalClose.addEventListener('click', closeImage);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeImage(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) closeImage(); });
  search.addEventListener('input', render);
  load();
})();



