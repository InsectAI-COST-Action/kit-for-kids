// Results from a detector that ran ON the camera ("edge" results): boxes over a photo, per-photo counts, and a
// per-adventure summary. Everything here is hidden unless a card's records carry a model (`modelId` and a result),
// so XIAO cards and Pi cards recorded with detection off look exactly as before.
//
// Labelling rule (docs/project-brief.md lines 45, 94, 118, 221; docs/browser-inference-plan.md line 96): output of a
// model that has not been validated is never shown as an observation. Every surface below says "test model", derived
// from the record's `modelStatus`; anything but the literal status `validated` counts as a test model. A score is the
// model's own number, not a probability.
//
// Data: per-photo summaries (`predictionCount`, `maxConfidence`, `modelId`, `modelStatus`) ride in the ordinary
// capture chunks. The boxes live in data/detections_NNNNNN.js beside each captures chunk and are loaded only for the
// chunk of a photo that is opened. Text from data is only ever set with textContent / canvas fillText.
(() => {
  'use strict';
  const { t } = window.i18n;
  const data = window.InsectData = window.InsectData || {};
  data.captures = data.captures || [];
  data.detections = data.detections || {};
  data.addDetections = data.addDetections || ((captureId, boxes) => { data.detections[captureId] = boxes; });

  const EDGE = window.InsectEdge = {};
  const BOX_COLOUR = '#1d6fe8';        // browser-AI boxes are pink (#f32b63); these must not be mistaken for them
  const MIN_THRESHOLD = 0.2;

  const hasModel = (capture) => Boolean(capture.modelId) && capture.modelId !== 'none';
  const hasResult = (capture) => hasModel(capture) && capture.inferenceOutcome === 'ok' &&
    Number.isFinite(Number(capture.predictionCount));
  const isTest = (capture) => capture.modelStatus !== 'validated';

  let activeFor = -1;
  let activeValue = false;
  const isActive = () => {
    if (activeFor !== data.captures.length) {
      activeValue = data.captures.some(hasResult);
      activeFor = data.captures.length;
    }
    return activeValue;
  };
  EDGE.isActive = isActive;

  const percent = (value) => `${Math.round(Number(value) * 100)}%`;
  const svgEl = (tag, attrs) => {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const key in attrs) element.setAttribute(key, attrs[key]);
    return element;
  };
  const el = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const rerender = () => { if (window.InsectDashboard) window.InsectDashboard.render(); };

  // ---------------------------------------------------------------- the card note ("does the camera run AI?")
  EDGE.note = (captures) => {
    const results = captures.filter(hasResult);
    return results.length ? t('ai.hasEdgeResults', results.length, results.some(isTest)) : null;
  };

  // ---------------------------------------------------------------- frame search filters
  const filters = { onlyWithBoxes: false, minTop: 0 };
  EDGE.keep = (capture) => {
    if (!isActive()) return true;
    if (filters.onlyWithBoxes && !(hasResult(capture) && Number(capture.predictionCount) > 0)) return false;
    if (filters.minTop > 0 && !(Number(capture.maxConfidence) >= filters.minTop)) return false;
    return true;
  };
  let filterBox = null;
  const renderFilters = () => {
    const host = document.querySelector('section[aria-labelledby="filter-title"]');
    if (!host) return;
    if (!filterBox) {
      filterBox = el('div', 'edge-filters');
      const onlyLabel = el('label', 'edge-check');
      const only = el('input');
      only.type = 'checkbox';
      only.id = 'edge-only-boxes';
      only.addEventListener('change', () => { filters.onlyWithBoxes = only.checked; rerender(); });
      onlyLabel.append(only, el('span'));
      const minLabel = el('label', 'edge-min');
      minLabel.append(el('span'));
      const min = el('input');
      min.type = 'range';
      min.id = 'edge-min-top';
      min.min = '0';
      min.max = '0.95';
      min.step = '0.05';
      min.value = '0';
      min.addEventListener('input', () => { filters.minTop = Number(min.value); rerender(); });
      minLabel.append(min, el('span', 'edge-min-value'));
      filterBox.append(onlyLabel, minLabel);
      host.append(filterBox);
    }
    filterBox.hidden = !isActive();
    if (filterBox.hidden) return;
    filterBox.querySelector('.edge-check span').textContent = t('edge.filterHasBoxes');
    filterBox.querySelector('.edge-min span').textContent = t('edge.filterMinTop');
    filterBox.querySelector('.edge-min-value').textContent = filters.minTop > 0 ? percent(filters.minTop) : t('edge.anyScore');
  };

  // ---------------------------------------------------------------- table columns and gallery badge
  const renderHeader = () => {
    const head = document.querySelector('#capture-rows')?.closest('table')?.querySelector('thead tr');
    if (!head) return;
    head.querySelectorAll('th.edge-col').forEach((cellElement) => cellElement.remove());
    if (!isActive()) return;
    for (const key of ['edge.col.boxes', 'edge.col.top', 'edge.col.model']) head.append(el('th', 'edge-col', t(key)));
  };
  EDGE.decorateRow = (row, capture) => {
    if (!isActive()) return;
    const result = hasResult(capture);
    row.append(
      el('td', 'edge-col', result ? String(capture.predictionCount) : '-'),
      el('td', 'edge-col', result && Number(capture.predictionCount) > 0 ? percent(capture.maxConfidence) : '-'),
      el('td', 'edge-col', hasModel(capture) ? String(capture.modelId) : '-'));
  };
  EDGE.decorateGalleryItem = (item, capture) => {
    if (!hasResult(capture)) return;
    item.classList.add('edge-item');
    item.append(el('span', 'edge-badge', t('edge.badge', Number(capture.predictionCount))));
  };

  // ---------------------------------------------------------------- the frame viewer overlay
  const modal = document.querySelector('#image-modal');
  const modalImage = document.querySelector('#modal-image');
  let canvas = null;
  let controls = null;
  let current = null;
  let currentState = 'idle';    // idle | loading | ready | missing
  const slider = { element: null, text: null, shown: null, model: null };

  const buildViewer = () => {
    if (!modalImage || canvas) return;
    const stage = el('div', 'edge-stage');
    modalImage.parentNode.insertBefore(stage, modalImage);
    stage.append(modalImage);
    canvas = el('canvas', 'edge-overlay');
    canvas.setAttribute('aria-hidden', 'true');
    stage.append(canvas);
    controls = el('div', 'edge-controls');
    controls.id = 'edge-controls';
    controls.hidden = true;
    const label = el('label', 'edge-threshold');
    slider.text = el('span');
    slider.element = el('input');
    slider.element.type = 'range';
    slider.element.min = String(MIN_THRESHOLD);
    slider.element.max = '0.95';
    slider.element.step = '0.05';
    slider.element.value = '0.25';
    slider.element.id = 'edge-threshold';
    slider.element.addEventListener('input', () => { updateControlText(); draw(); });
    label.append(slider.text, slider.element);
    slider.shown = el('p', 'hint edge-shown');
    slider.model = el('p', 'hint edge-model-line');
    controls.append(label, slider.shown, slider.model);
    stage.after(controls);
    modalImage.addEventListener('load', draw);
  };

  const threshold = () => Number(slider.element ? slider.element.value : 0.25);
  const boxesFor = (capture) => data.detections[capture.captureId] || [];

  const updateControlText = () => {
    if (!current || !controls) return;
    slider.text.textContent = t('edge.threshold', percent(threshold()));
    if (currentState === 'loading') { slider.shown.textContent = t('edge.loadingBoxes'); }
    else if (currentState === 'missing') { slider.shown.textContent = t('edge.boxesMissing'); }
    else {
      const stored = boxesFor(current);
      const shown = stored.filter((box) => box[4] >= threshold()).length;
      slider.shown.textContent = t('edge.shown', shown, stored.length, Number(current.predictionCount) || 0);
    }
    slider.model.textContent = t('edge.modelLine', String(current.modelId), isTest(current), Number(current.inferenceMs) || 0);
  };

  const draw = () => {
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!current || !modalImage.naturalWidth) { context.clearRect(0, 0, canvas.width, canvas.height); return; }
    const scale = Math.min(1, 1600 / modalImage.naturalWidth);
    canvas.width = Math.max(1, Math.round(modalImage.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(modalImage.naturalHeight * scale));
    context.clearRect(0, 0, canvas.width, canvas.height);
    const boxes = boxesFor(current).filter((box) => box[4] >= threshold());
    context.lineWidth = Math.max(2, canvas.width / 450);
    context.strokeStyle = BOX_COLOUR;
    for (const [x, y, w, h] of boxes) context.strokeRect(x * canvas.width, y * canvas.height, w * canvas.width, h * canvas.height);
    // Scores only on the strongest few: 50 labels would cover the photo.
    const fontSize = Math.max(14, Math.round(canvas.width / 55));
    context.font = `700 ${fontSize}px system-ui, sans-serif`;
    context.textBaseline = 'alphabetic';
    boxes.slice().sort((a, b) => b[4] - a[4]).slice(0, 5).forEach(([x, y, , , score]) => {
      const label = percent(score);
      const left = x * canvas.width;
      const top = Math.max(fontSize + 4, y * canvas.height);
      const width = context.measureText(label).width + 8;
      context.fillStyle = BOX_COLOUR;
      context.fillRect(left, top - fontSize - 4, width, fontSize + 6);
      context.fillStyle = '#ffffff';
      context.fillText(label, left + 4, top - 3);
    });
    // The label that cannot be separated from the boxes: burned into the same canvas.
    if (isTest(current)) {
      const band = Math.max(26, Math.round(canvas.height / 18));
      context.fillStyle = '#b00000';
      context.fillRect(0, 0, canvas.width, band);
      context.fillStyle = '#ffffff';
      context.font = `800 ${Math.round(band * 0.62)}px system-ui, sans-serif`;
      context.fillText(t('edge.banner'), 10, Math.round(band * 0.72));
    }
  };

  // Boxes of one chunk are fetched the first time a photo from it is opened (script tag, as the capture chunks are).
  const attempts = new Map();
  const boxesPath = (capture) => {
    const chunk = capture._chunk;
    if (chunk === 'current') return 'data/detections_current.js';
    if (!Number.isInteger(chunk)) return null;
    const path = `data/detections_${String(chunk).padStart(6, '0')}.js`;
    const listed = data.manifest && data.manifest.detectionChunks;
    return listed && !listed.includes(path) ? null : path;
  };
  const loadBoxes = (capture) => {
    if (!Number(capture.predictionCount)) return Promise.resolve(true);          // nothing was found: no boxes line
    if (data.detections[capture.captureId]) return Promise.resolve(true);
    const path = boxesPath(capture);
    if (!path) return Promise.resolve(false);
    if (!attempts.has(path)) {
      attempts.set(path, new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = path;
        script.onload = () => resolve(true);
        script.onerror = () => resolve(false);
        document.head.append(script);
      }));
    }
    return attempts.get(path).then(() => Boolean(data.detections[capture.captureId]));
  };

  EDGE.onOpen = (capture) => {
    buildViewer();
    current = capture && hasModel(capture) ? capture : null;
    if (!controls) return;
    controls.hidden = !current;
    if (!current) { draw(); return; }
    currentState = 'loading';
    updateControlText();
    loadBoxes(current).then((found) => {
      if (!current || current !== capture) return;
      currentState = found ? 'ready' : 'missing';
      updateControlText();
      draw();
    });
  };
  EDGE.onClose = () => {
    current = null;
    if (controls) controls.hidden = true;
    draw();
  };
  window.i18n.onLocaleChange(() => { updateControlText(); draw(); });

  // ---------------------------------------------------------------- per-adventure summary
  const runSummaries = () => {
    const runs = new Map();
    for (const capture of data.captures) {
      if (!hasResult(capture)) continue;
      const runId = capture.runId || 'unknown_session';
      const run = runs.get(runId) || { runId, pictures: 0, withBoxes: 0, boxes: 0, top: 0, ms: 0, models: new Set(), test: false, captures: [] };
      run.pictures += 1;
      run.boxes += Number(capture.predictionCount);
      if (Number(capture.predictionCount) > 0) run.withBoxes += 1;
      run.top = Math.max(run.top, Number(capture.maxConfidence) || 0);
      run.ms += Number(capture.inferenceMs) || 0;
      run.models.add(String(capture.modelId));
      run.test = run.test || isTest(capture);
      run.captures.push(capture);
      runs.set(runId, run);
    }
    return [...runs.values()].sort((a, b) => b.runId.localeCompare(a.runId, undefined, { numeric: true }));
  };

  let panel = null;
  let chosenRun = '';
  const buildPanel = () => {
    if (panel) return panel;
    const anchor = document.querySelector('#motion-panel') || document.querySelector('.gallery-panel');
    if (!anchor) return null;
    panel = el('section', 'panel edge-panel');
    panel.id = 'edge-panel';
    panel.setAttribute('aria-labelledby', 'edge-title');
    anchor.after(panel);
    return panel;
  };

  const lineChart = (run) => {
    const W = 900, H = 220, M = { top: 14, right: 18, bottom: 28, left: 44 };
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet', role: 'img', 'aria-label': t('edge.timelineTitle'), class: 'edge-chart' });
    const points = run.captures.slice().sort((a, b) => (Number(a.uptimeMs) || 0) - (Number(b.uptimeMs) || 0));
    const t0 = Number(points[0].uptimeMs) || 0;
    const tMax = Math.max(1, ((Number(points[points.length - 1].uptimeMs) || 0) - t0) / 1000);
    const yMax = Math.max(5, ...points.map((c) => Number(c.predictionCount)));
    const x = (seconds) => M.left + (seconds / tMax) * (W - M.left - M.right);
    const y = (count) => M.top + (1 - count / yMax) * (H - M.top - M.bottom);
    for (const tick of [0, 0.5, 1]) {
      const value = Math.round(yMax * tick);
      svg.append(svgEl('line', { class: 'edge-grid', x1: M.left, x2: W - M.right, y1: y(value), y2: y(value) }));
      const label = svgEl('text', { class: 'edge-axis', x: M.left - 6, y: y(value) + 4, 'text-anchor': 'end' });
      label.textContent = String(value);
      svg.append(label);
    }
    for (const fraction of [0, 0.5, 1]) {
      const label = svgEl('text', { class: 'edge-axis', x: x(tMax * fraction), y: H - 8, 'text-anchor': fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle' });
      label.textContent = t('time.seconds', Math.round(tMax * fraction));
      svg.append(label);
    }
    svg.append(svgEl('polyline', { class: 'edge-line', fill: 'none', points: points.map((c) => `${x(((Number(c.uptimeMs) || 0) - t0) / 1000).toFixed(1)},${y(Number(c.predictionCount)).toFixed(1)}`).join(' ') }));
    return svg;
  };

  const histogram = (run) => {
    const W = 900, H = 220, M = { top: 14, right: 18, bottom: 28, left: 44 };
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet', role: 'img', 'aria-label': t('edge.histTitle'), class: 'edge-chart' });
    const bins = new Array(16).fill(0);                     // 0.20 ... 1.00 in steps of 0.05
    run.captures.filter((c) => Number(c.predictionCount) > 0).forEach((c) => {
      bins[Math.min(15, Math.max(0, Math.floor((Number(c.maxConfidence) - MIN_THRESHOLD) / 0.05)))] += 1;
    });
    const yMax = Math.max(1, ...bins);
    const slot = (W - M.left - M.right) / bins.length;
    bins.forEach((count, index) => {
      const top = M.top + (1 - count / yMax) * (H - M.top - M.bottom);
      const bar = svgEl('rect', { class: 'edge-bar', x: M.left + index * slot + 2, y: top, width: slot - 4, height: H - M.bottom - top });
      const title = svgEl('title', {});
      title.textContent = t('edge.histBar', percent(MIN_THRESHOLD + index * 0.05), count);
      bar.append(title);
      svg.append(bar);
    });
    for (const [index, label] of [[0, percent(MIN_THRESHOLD)], [8, percent(0.6)], [16, percent(1)]]) {
      const text = svgEl('text', { class: 'edge-axis', x: M.left + index * slot, y: H - 8, 'text-anchor': index === 0 ? 'start' : index === 16 ? 'end' : 'middle' });
      text.textContent = label;
      svg.append(text);
    }
    for (const tick of [0, 1]) {
      const label = svgEl('text', { class: 'edge-axis', x: M.left - 6, y: M.top + (1 - tick) * (H - M.top - M.bottom) + 4, 'text-anchor': 'end' });
      label.textContent = String(Math.round(yMax * tick));
      svg.append(label);
    }
    return svg;
  };

  const renderPanel = () => {
    const host = buildPanel();
    if (!host) return;
    const runs = isActive() ? runSummaries() : [];
    host.hidden = !runs.length;
    if (!runs.length) return;
    if (!runs.some((run) => run.runId === chosenRun)) chosenRun = runs[0].runId;
    const run = runs.find((candidate) => candidate.runId === chosenRun);
    host.replaceChildren();

    const heading = el('div', 'section-heading');
    const titles = el('div');
    titles.append(el('p', 'eyebrow warm', t('edge.panelEyebrow')));
    const title = el('h2', undefined, t('edge.panelTitle'));
    title.id = 'edge-title';
    titles.append(title);
    heading.append(titles, el('span', 'section-count', t('edge.panelCount', runs.reduce((sum, r) => sum + r.pictures, 0))));
    host.append(heading);
    if (runs.some((r) => r.test)) host.append(el('p', 'edge-test-note', t('edge.testNote')));
    host.append(el('p', 'hint', t('edge.hint')));

    const table = el('table', 'edge-runs');
    const head = el('tr');
    ['edge.runs.run', 'edge.runs.pictures', 'edge.runs.withBoxes', 'edge.runs.meanBoxes', 'edge.runs.top', 'edge.runs.ms', 'edge.runs.model']
      .forEach((key) => head.append(el('th', undefined, t(key))));
    const thead = el('thead');
    thead.append(head);
    const tbody = el('tbody');
    for (const row of runs.slice(0, 12)) {
      const tr = el('tr', row.runId === chosenRun ? 'edge-run-chosen' : undefined);
      const nameCell = el('td');
      const pick = el('button', 'inline-button', row.runId);
      pick.type = 'button';
      pick.addEventListener('click', () => { chosenRun = row.runId; renderPanel(); });
      nameCell.append(pick);
      tr.append(nameCell, el('td', undefined, String(row.pictures)), el('td', undefined, String(row.withBoxes)),
        el('td', undefined, (row.boxes / row.pictures).toFixed(1)), el('td', undefined, row.withBoxes ? percent(row.top) : '-'),
        el('td', undefined, String(Math.round(row.ms / row.pictures))), el('td', undefined, [...row.models].join(', ')));
      tbody.append(tr);
    }
    table.append(thead, tbody);
    const wrap = el('div', 'table-wrap');
    wrap.append(table);
    host.append(wrap);
    if (runs.length > 12) host.append(el('p', 'hint', t('edge.runs.more', runs.length - 12)));

    host.append(el('h3', 'edge-chart-title', t('edge.timelineTitle', run.runId)));
    host.append(lineChart(run));
    host.append(el('h3', 'edge-chart-title', t('edge.histTitle', run.runId)));
    host.append(histogram(run));
    host.append(el('p', 'hint', t('edge.scoreNote')));
  };

  EDGE.afterRender = () => {
    renderFilters();
    renderHeader();
    renderPanel();
  };
})();
