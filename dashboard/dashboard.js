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
  const movieModal = document.querySelector('#movie-modal');
  const movieClose = document.querySelector('#movie-close');
  const movieSetup = document.querySelector('#movie-setup');
  const movieProgress = document.querySelector('#movie-progress');
  const movieInfo = document.querySelector('#movie-info');
  const movieLoadCard = document.querySelector('#movie-load-card');
  const movieCardStatus = document.querySelector('#movie-card-status');
  const movieSessionLabel = document.querySelector('#movie-session-label');
  const movieSession = document.querySelector('#movie-session');
  const movieSupport = document.querySelector('#movie-support');
  const movieStart = document.querySelector('#movie-start');
  const movieCancel = document.querySelector('#movie-cancel');
  const movieCanvas = document.querySelector('#movie-canvas');
  const movieProgressBar = document.querySelector('#movie-progress-bar');
  const movieProgressText = document.querySelector('#movie-progress-text');
  const movieMessage = document.querySelector('#movie-message');
  const movieDownload = document.querySelector('#movie-download');
  const movie = { active: false, cancelled: false, downloadUrl: undefined, output: undefined };
  const MOVIE_FPS = 60;
  const MOVIE_WIDTH = 1024;
  const MOVIE_HEIGHT = 768;

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

  const card = window.InsectCard;
  const movieCaptures = () => data.captures.filter((capture) => capture.imagePath).map((capture) => ({ capture, file: card.fileFor(capture.imagePath) }));
  const availableMovieCaptures = () => movieCaptures().filter((entry) => entry.file);
  const movieSessions = () => {
    const sessions = new Map();
    for (const entry of availableMovieCaptures()) {
      const runId = entry.capture.runId || String(entry.capture.imagePath).split('/')[2] || 'unknown_session';
      const group = sessions.get(runId) || [];
      group.push(entry);
      sessions.set(runId, group);
    }
    return [...sessions.entries()].sort(([first], [second]) => second.localeCompare(first, undefined, { numeric: true }));
  };
  const selectedMovieCaptures = () => movieSessions().find(([runId]) => runId === movieSession.value)?.[1] || [];
  const movieDuration = (count) => `${Math.max(1, Math.round(count / MOVIE_FPS))} seconds`;
  const movieEncoderReady = () => Boolean(
    window.Mediabunny && window.VideoEncoder &&
    window.Mediabunny.Output && window.Mediabunny.Mp4OutputFormat &&
    window.Mediabunny.BufferTarget && window.Mediabunny.CanvasSource
  );
  const clearMovieDownload = () => {
    if (movie.downloadUrl) URL.revokeObjectURL(movie.downloadUrl);
    movie.downloadUrl = undefined;
    movieDownload.hidden = true;
    movieDownload.removeAttribute('href');
  };
  const loadMovieImage = (file) => new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error(`Could not open ${file.name}`)); };
    image.src = url;
  });
  const drawMovieImage = (image) => {
    const context = movieCanvas.getContext('2d');
    context.fillStyle = '#15324d';
    context.fillRect(0, 0, MOVIE_WIDTH, MOVIE_HEIGHT);
    const scale = Math.min(MOVIE_WIDTH / image.naturalWidth, MOVIE_HEIGHT / image.naturalHeight);
    const width = Math.round(image.naturalWidth * scale), height = Math.round(image.naturalHeight * scale);
    context.drawImage(image, Math.round((MOVIE_WIDTH - width) / 2), Math.round((MOVIE_HEIGHT - height) / 2), width, height);
  };
  const cancelMovie = () => {
    if (!movie.active) return;
    movie.active = false;
    movie.cancelled = true;
    // Cancelling releases the local encoder. The running export catches its cancellation error.
    movie.output?.cancel().catch(() => {});
  };
  const yieldMovieWork = () => new Promise((resolve) => window.setTimeout(resolve, 0));
  const drawMovieUnavailable = () => {
    const context = movieCanvas.getContext('2d');
    context.fillStyle = '#15324d';
    context.fillRect(0, 0, MOVIE_WIDTH, MOVIE_HEIGHT);
    context.fillStyle = '#fff';
    context.font = 'bold 38px system-ui';
    context.fillText('Picture unavailable', 300, 380);
  };
  const makeMovie = async () => {
    const captures = selectedMovieCaptures();
    if (!card.loaded) {
      movieSupport.textContent = 'Press Load camera card first.';
      return;
    }
    if (!captures.length) {
      movieSupport.textContent = 'There are no saved picture files to make into a movie yet.';
      return;
    }
    if (!movieEncoderReady()) {
      movieSupport.textContent = 'Movie making needs current Chrome or Edge with its local video tools enabled.';
      return;
    }
    clearMovieDownload();
    movie.active = true;
    movie.cancelled = false;
    movieSetup.hidden = true;
    movieProgress.hidden = false;
    movieStart.disabled = true;
    movieCancel.hidden = false;
    movieMessage.textContent = 'Starting a properly timed MP4 movie.';
    movieProgressBar.style.width = '0%';
    movieProgressText.textContent = `Picture 0 of ${captures.length}`;
    try {
      const target = new window.Mediabunny.BufferTarget();
      const output = new window.Mediabunny.Output({
        format: new window.Mediabunny.Mp4OutputFormat(),
        target,
      });
      const source = new window.Mediabunny.CanvasSource(movieCanvas, {
        codec: 'avc',
        bitrate: 2500000,
        keyFrameInterval: 2,
      });
      output.addVideoTrack(source, { frameRate: MOVIE_FPS });
      movie.output = output;
      await output.start();
      for (let index = 0; index < captures.length; index += 1) {
        if (!movie.active) break;
        try {
          drawMovieImage(await loadMovieImage(captures[index].file));
        } catch (error) {
          drawMovieUnavailable();
        }
        if (!movie.active) break;
        // These timestamps define the movie clock. Image decoding speed cannot stretch the video.
        await source.add(index / MOVIE_FPS, 1 / MOVIE_FPS);
        const completed = index + 1;
        movieProgressBar.style.width = `${Math.round(completed / captures.length * 100)}%`;
        movieProgressText.textContent = `Picture ${completed} of ${captures.length}`;
        movieMessage.textContent = completed === captures.length
          ? 'Finishing your MP4 movie...'
          : `Adding picture ${completed} to your speedy insect story.`;
        await yieldMovieWork();
      }
      if (movie.cancelled) {
        movieMessage.textContent = 'Movie cancelled. No file was made.';
        return;
      }
      await output.finalize();
      if (movie.cancelled || !target.buffer) {
        movieMessage.textContent = 'Movie cancelled. No file was made.';
        return;
      }
      movie.downloadUrl = URL.createObjectURL(new Blob([target.buffer], { type: 'video/mp4' }));
      movieDownload.href = movie.downloadUrl;
      movieDownload.download = 'insect-camera-timelapse.mp4';
      movieDownload.hidden = false;
      movieMessage.textContent = `Your 60 pictures-per-second MP4 insect movie is ready! Download it to keep it.`;
    } catch (error) {
      if (movie.cancelled) movieMessage.textContent = 'Movie cancelled. No file was made.';
      else {
        movieMessage.textContent = 'We could not make this movie on this computer. Try current Chrome or Edge, then try again.';
        movieSupport.textContent = `Movie maker detail: ${error.message}`;
      }
    } finally {
      movie.active = false;
      movie.output = undefined;
      movieStart.disabled = false;
      movieCancel.hidden = true;
    }
  };
  const updateMovieCardStatus = () => {
    const allCaptures = movieCaptures();
    const captures = allCaptures.filter((entry) => entry.file);
    const missing = allCaptures.length - captures.length;
    const sessions = movieSessions();
    const previous = movieSession.value;
    movieSession.replaceChildren();
    sessions.forEach(([runId, entries], index) => {
      const option = document.createElement('option');
      option.value = runId;
      option.textContent = `${index === 0 ? 'Newest session ? ' : ''}${runId} (${entries.length} pictures)`;
      movieSession.append(option);
    });
    if (sessions.some(([runId]) => runId === previous)) movieSession.value = previous;
    movieSessionLabel.hidden = !sessions.length;
    movieSession.disabled = !sessions.length;
    const chosen = selectedMovieCaptures();
    movieInfo.textContent = chosen.length ? `${movieSession.selectedOptions[0].textContent} is selected. At 60 pictures each second, your movie will be about ${movieDuration(chosen.length)} long.` : 'There are no saved pictures to turn into a movie yet.';
    movieCardStatus.textContent = card.loaded ? `Camera card ready! I found ${captures.length} saved picture${captures.length === 1 ? '' : 's'} in ${sessions.length} session${sessions.length === 1 ? '' : 's'}.${missing ? ` ${missing} older record${missing === 1 ? '' : 's'} without image files will be skipped.` : ''}` : 'Press Load camera card, then choose the INSECT-AI drive in the next window.';
    movieLoadCard.hidden = card.loaded && captures.length > 0;
    movieStart.disabled = !chosen.length || !movieEncoderReady();
  };
  const openMovie = () => {
    lastFocus = document.activeElement;
    movieModal.hidden = false;
    movieSetup.hidden = false;
    movieProgress.hidden = true;
    movieSupport.textContent = movieEncoderReady() ? '' : 'Movie making needs current Chrome or Edge with its local video tools enabled.';
    updateMovieCardStatus();
    movieStart.focus();
  };
  const closeMovie = () => {
    cancelMovie();
    movieModal.hidden = true;
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
  document.querySelector('#make-movie').addEventListener('click', openMovie);
  movieClose.addEventListener('click', closeMovie);
  movieCancel.addEventListener('click', cancelMovie);
  movieModal.addEventListener('click', (event) => { if (event.target === movieModal && !movie.active) closeMovie(); });
  movieLoadCard.addEventListener('click', () => card.request());
  movieSession.addEventListener('change', updateMovieCardStatus);
  window.addEventListener('insect-card-loaded', () => { if (!movieModal.hidden) updateMovieCardStatus(); });
  movieStart.addEventListener('click', makeMovie);
  modelModalClose.addEventListener('click', closeModelMessage);
  modelModalOk.addEventListener('click', closeModelMessage);
  modelModal.addEventListener('click', (event) => { if (event.target === modelModal) closeModelMessage(); });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!modal.hidden) closeImage();
    else if (!movieModal.hidden) closeMovie();
    else if (!modelModal.hidden) closeModelMessage();
  });
  search.addEventListener('input', render);
  loadingRetry.addEventListener('click', () => window.location.reload());
  load();
})();
