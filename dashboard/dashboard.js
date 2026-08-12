(() => {
  const data = window.InsectData = window.InsectData || {};
  data.captures = data.captures || [];
  data.addCapture = data.addCapture || ((capture) => data.captures.push(capture));

  const status = document.querySelector('#status');
  const rows = document.querySelector('#capture-rows');
  const gallery = document.querySelector('#gallery');
  const galleryEmpty = document.querySelector('#gallery-empty');
  const search = document.querySelector('#search');

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

  const render = () => {
    const captures = filteredCaptures();
    const images = captures.filter((capture) => capture.imagePath);
    const averageCaptureMs = captures.length
      ? Math.round(captures.reduce((total, capture) => total + capture.captureMs, 0) / captures.length)
      : 0;
    const inferenceOutcomes = new Set(captures.map((capture) => capture.inferenceOutcome));

    document.querySelector('#capture-count').textContent = String(data.captures.length);
    document.querySelector('#image-count').textContent = String(images.length);
    document.querySelector('#capture-time').textContent = captures.length ? `${averageCaptureMs} ms` : '-';
    document.querySelector('#inference-status').textContent = inferenceOutcomes.size
      ? [...inferenceOutcomes].join(', ') : 'No data';

    rows.replaceChildren();
    captures.slice(-100).reverse().forEach((capture) => {
      const row = document.createElement('tr');
      cell(row, capture.captureId);
      cell(row, relativeTime(capture.uptimeMs));
      cell(row, capture.outcome);
      const imageCell = document.createElement('td');
      if (capture.imagePath) {
        const link = document.createElement('a');
        link.href = capture.imagePath;
        link.textContent = 'Open image';
        imageCell.append(link);
      } else {
        imageCell.textContent = 'Unavailable';
      }
      row.append(imageCell);
      rows.append(row);
    });

    gallery.replaceChildren();
    galleryEmpty.hidden = images.length > 0;
    const template = document.querySelector('#gallery-item-template');
    images.slice(-120).reverse().forEach((capture) => {
      const item = template.content.firstElementChild.cloneNode(true);
      const image = item.querySelector('img');
      item.href = capture.imagePath;
      image.src = capture.imagePath;
      image.alt = `Frame ${capture.captureId}`;
      item.querySelector('span').textContent = capture.captureId;
      gallery.append(item);
    });
  };

  const load = async () => {
    const chunks = data.manifest?.captureChunks || [];
    const failures = [];
    let currentLoaded = false;
    try {
      await loadScript('data/captures_current.js');
      currentLoaded = true;
    } catch (error) {
      // A card with no open chunk is valid; closed chunks are still useful.
    }
    for (const chunk of chunks) {
      try { await loadScript(chunk); } catch (error) { failures.push(error.message); }
    }
    if (failures.length) {
      status.textContent = `Loaded data with ${failures.length} unavailable closed chunk(s).`;
    } else if (!chunks.length && !currentLoaded) {
      status.textContent = 'No dashboard data chunks are available yet.';
    } else if (currentLoaded) {
      status.textContent = `Loaded ${chunks.length} closed chunk(s) and the current open chunk.`;
    } else {
      status.textContent = `Loaded ${chunks.length} closed data chunk(s).`;
    }
    render();
  };

  search.addEventListener('input', render);
  load();
})();
