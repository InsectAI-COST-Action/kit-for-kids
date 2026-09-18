(() => {
  const { t } = window.i18n;
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
  const motionPanel = document.querySelector('#motion-panel');
  const motionCount = document.querySelector('#motion-count');
  const motionChart = document.querySelector('#motion-chart');
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
  const movieCardTrack = document.querySelector('#movie-card-track');
  const movieCardProgress = document.querySelector('#movie-card-progress');
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
  const cardCheck = document.querySelector('#card-check');
  const cardCheckNote = document.querySelector('#card-check-note');
  const cardCheckButton = document.querySelector('#card-check-button');
  const cardCheckTrack = document.querySelector('#card-check-track');
  const cardCheckProgress = document.querySelector('#card-check-progress');
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

  const relativeTime = (milliseconds) => t('time.seconds', ((Number(milliseconds) || 0) / 1000).toFixed(1));
  const formatDuration = (totalSeconds) => {
    if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '-';
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = Math.floor(totalSeconds % 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
  };
  // Picture availability. The camera's own record is the authority for what it
  // observed, but a person can tidy JPEGs off the card afterwards and the
  // record cannot know (reported 12 September 2026: the front page claimed far
  // more pictures than the card actually held). Until the card has been
  // checked, every record with an image path is assumed present - exactly the
  // old behaviour. Once checked, the page shows what is really there. Nothing
  // on the card is rewritten; see docs/reconciliation-policy.md.
  const cardState = { checked: false, mismatch: false, referenced: 0, present: 0 };
  const hasImage = (capture) => Boolean(capture.imagePath) && (!cardState.checked || capture.imageOnCard === true);
  // Total time recorded: first-to-last image within each session, added up
  // across every session on the card. Sessions are independent uptime clocks,
  // so they can only be summed per session, never compared to each other.
  const totalRecordedSeconds = () => {
    const spans = new Map();
    for (const capture of data.captures) {
      if (!hasImage(capture)) continue;
      const runId = capture.runId || 'unknown_session';
      const uptime = Number(capture.uptimeMs);
      if (!Number.isFinite(uptime)) continue;
      const span = spans.get(runId) || { first: uptime, last: uptime, count: 0 };
      span.first = Math.min(span.first, uptime);
      span.last = Math.max(span.last, uptime);
      span.count += 1;
      spans.set(runId, span);
    }
    let total = 0;
    // A single-image session has no measurable span, not a zero-length one.
    for (const span of spans.values()) if (span.count >= 2) total += (span.last - span.first) / 1000;
    return total;
  };
  // Newest session's own captures - reused by the front-page duration metric
  // and the motion panel, so both agree on what "last session" means.
  const lastSessionCaptures = () => {
    const runIds = [...new Set(data.captures.map((capture) => capture.runId).filter(Boolean))]
      .sort((first, second) => second.localeCompare(first, undefined, { numeric: true }));
    const lastRunId = runIds[0];
    return lastRunId ? data.captures.filter((capture) => capture.runId === lastRunId) : [];
  };
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
  const runIdOf = (capture) => capture.runId || String(capture.imagePath).split('/')[2] || 'unknown_session';
  // Session names and counts come straight from card.sessionCounts() - the
  // file listing the picker already gave us - not from walking every capture
  // record. Reported 13 September 2026, after fixing fileFor's per-lookup
  // cost: listing sessions still touched every one of 28,717 capture records
  // on the real card just to populate a dropdown, when the file list alone
  // (1,576 entries) already answers "which sessions exist and how many
  // pictures does each have."
  const movieSessions = () => [...card.sessionCounts()].sort(([first], [second]) => second.localeCompare(first, undefined, { numeric: true }));
  // The capture-to-file match only actually needs doing for the one session
  // in use - the movie itself needs each frame's real file, but no other
  // session's records are touched to get there.
  const movieCapturesFor = (runId) => data.captures
    .filter((capture) => capture.imagePath && runIdOf(capture) === runId)
    .map((capture) => ({ capture, file: card.fileFor(capture.imagePath) }))
    .filter((entry) => entry.file);
  const selectedMovieCaptures = () => movieCapturesFor(movieSession.value);
  const movieDuration = (count) => t('time.seconds', Math.max(1, Math.round(count / MOVIE_FPS)));
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
    context.fillText(t('movie.pictureUnavailable'), 300, 380);
  };
  const makeMovie = async () => {
    const captures = selectedMovieCaptures();
    if (!card.loaded) {
      movieSupport.textContent = t('movie.pressLoadFirst');
      return;
    }
    if (!captures.length) {
      movieSupport.textContent = t('movie.noSavedFiles');
      return;
    }
    if (!movieEncoderReady()) {
      movieSupport.textContent = t('movie.needsModernBrowser');
      return;
    }
    clearMovieDownload();
    movie.active = true;
    movie.cancelled = false;
    movieSetup.hidden = true;
    movieProgress.hidden = false;
    movieStart.disabled = true;
    movieCancel.hidden = false;
    movieMessage.textContent = t('movie.startingMessage');
    movieProgressBar.style.width = '0%';
    movieProgressText.textContent = t('progress.text', 0, captures.length);
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
        movieProgressText.textContent = t('progress.text', completed, captures.length);
        movieMessage.textContent = completed === captures.length
          ? t('movie.finishing')
          : t('movie.addingPicture', completed);
        await yieldMovieWork();
      }
      if (movie.cancelled) {
        movieMessage.textContent = t('movie.cancelledMessage');
        return;
      }
      await output.finalize();
      if (movie.cancelled || !target.buffer) {
        movieMessage.textContent = t('movie.cancelledMessage');
        return;
      }
      movie.downloadUrl = URL.createObjectURL(new Blob([target.buffer], { type: 'video/mp4' }));
      movieDownload.href = movie.downloadUrl;
      movieDownload.download = 'insect-camera-timelapse.mp4';
      movieDownload.hidden = false;
      movieMessage.textContent = t('movie.readyMessage');
    } catch (error) {
      if (movie.cancelled) movieMessage.textContent = t('movie.cancelledMessage');
      else {
        movieMessage.textContent = t('movie.failedMessage');
        movieSupport.textContent = t('movie.detailPrefix', error.message);
      }
    } finally {
      movie.active = false;
      movie.output = undefined;
      movieStart.disabled = false;
      movieCancel.hidden = true;
    }
  };
  const updateMovieCardStatus = () => {
    // sessions is [runId, fileCount] pairs, read from the card's file listing
    // (see movieSessions() above) - no per-capture lookups here at all. The
    // one remaining full-card pass is a plain length count (referenced vs.
    // actually present), not a lookup, so it stays cheap even at tens of
    // thousands of records.
    const sessions = movieSessions();
    const totalFiles = sessions.reduce((sum, [, count]) => sum + count, 0);
    const totalReferenced = data.captures.filter((capture) => capture.imagePath).length;
    const missing = Math.max(0, totalReferenced - totalFiles);
    const previous = movieSession.value;
    movieSession.replaceChildren();
    sessions.forEach(([runId, count], index) => {
      const option = document.createElement('option');
      option.value = runId;
      option.textContent = t('session.optionLabel', runId, count, index === 0);
      movieSession.append(option);
    });
    if (sessions.some(([runId]) => runId === previous)) movieSession.value = previous;
    movieSessionLabel.hidden = !sessions.length;
    movieSession.disabled = !sessions.length;
    const chosenCount = sessions.find(([runId]) => runId === movieSession.value)?.[1] || 0;
    movieInfo.textContent = chosenCount ? t('movie.infoSelected', movieSession.selectedOptions[0].textContent, movieDuration(chosenCount)) : t('movie.infoEmpty');
    // While the card is being read, the shared progress message owns this line.
    if (!card.busy) movieCardStatus.textContent = card.loaded ? t('movie.cardReady', totalFiles, sessions.length, missing) : t('movieModal.cardStatusDefault');
    movieLoadCard.hidden = card.loaded && totalFiles > 0;
    movieStart.disabled = !chosenCount || !movieEncoderReady();
  };
  const openMovie = () => {
    lastFocus = document.activeElement;
    movieModal.hidden = false;
    movieSetup.hidden = false;
    movieProgress.hidden = true;
    movieSupport.textContent = movieEncoderReady() ? '' : t('movie.needsModernBrowser');
    updateMovieCardStatus();
    movieStart.focus();
  };
  const closeMovie = () => {
    cancelMovie();
    movieModal.hidden = true;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  };

  const svgEl = (tag, attrs) => {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const key in attrs) element.setAttribute(key, attrs[key]);
    return element;
  };

  const renderMotionPanel = () => {
    if (!motionPanel || !motionCount || !motionChart) return;
    const motionCaptures = lastSessionCaptures().filter((capture) => Number(capture.motionThreshold) > 0)
      .slice().sort((first, second) => (Number(first.uptimeMs) || 0) - (Number(second.uptimeMs) || 0));
    if (motionCaptures.length < 2) { motionPanel.hidden = true; return; }

    const saved = motionCaptures.filter((capture) => capture.imagePath);
    const scored = motionCaptures.filter((capture) => Number(capture.motionScore) >= 0);
    const baseline = motionCaptures.find((capture) => Number(capture.motionScore) < 0);
    if (!scored.length) { motionPanel.hidden = true; return; }

    motionPanel.hidden = false;
    motionCount.textContent = t('motion.count', saved.length);

    const t0 = motionCaptures[0].uptimeMs;
    const threshold = scored[0].motionThreshold;
    const W = 900, H = 260;
    const M = { top: 14, right: 18, bottom: 30, left: 40 };
    const plotW = W - M.left - M.right;
    const plotH = H - M.top - M.bottom;
    const tMax = Math.max(...scored.map((capture) => (capture.uptimeMs - t0) / 1000), 1);
    const xScale = (seconds) => M.left + (seconds / tMax) * plotW;
    const scoreMin = 0.3;
    const scoreMax = Math.max(10, Math.ceil(Math.max(...scored.map((capture) => capture.motionScore)) / 10) * 10);
    const yScale = (score) => {
      const clamped = Math.max(score, scoreMin);
      const frac = (Math.log10(clamped) - Math.log10(scoreMin)) / (Math.log10(scoreMax) - Math.log10(scoreMin));
      return M.top + plotH - frac * plotH;
    };

    motionChart.replaceChildren();
    [0.3, 1, 3, 10, 30, 100].filter((value) => value <= scoreMax * 1.01).forEach((value) => {
      const y = yScale(value);
      motionChart.append(svgEl('line', { class: 'motion-grid', x1: M.left, x2: W - M.right, y1: y, y2: y }));
      const label = svgEl('text', { class: 'motion-axis-label', x: M.left - 6, y: y + 3, 'text-anchor': 'end' });
      label.textContent = value;
      motionChart.append(label);
    });
    const thresholdY = yScale(threshold);
    motionChart.append(svgEl('line', { class: 'motion-threshold-line', x1: M.left, x2: W - M.right, y1: thresholdY, y2: thresholdY }));
    const thresholdLabel = svgEl('text', { class: 'motion-threshold-label', x: W - M.right, y: thresholdY - 6, 'text-anchor': 'end' });
    thresholdLabel.textContent = t('motion.saveLine', threshold);
    motionChart.append(thresholdLabel);
    const tMaxMin = Math.max(1, Math.ceil(tMax / 60));
    for (let minute = 0; minute <= tMaxMin; minute += Math.max(1, Math.ceil(tMaxMin / 6))) {
      const x = xScale(minute * 60);
      const label = svgEl('text', { class: 'motion-axis-label', x, y: H - M.bottom + 16, 'text-anchor': 'middle' });
      label.textContent = `${minute}m`;
      motionChart.append(label);
    }

    const addDot = (capture, isSaved) => {
      const title = t('motion.dotTitle', capture.captureId, isSaved, capture.motionScore.toFixed(2));
      const dot = svgEl('circle', {
        class: isSaved ? 'motion-dot-saved' : 'motion-dot-quiet',
        cx: xScale((capture.uptimeMs - t0) / 1000),
        cy: yScale(capture.motionScore),
        r: isSaved ? 4.5 : 2.4,
      });
      const dotTitle = svgEl('title', {});
      dotTitle.textContent = title;
      dot.append(dotTitle);
      motionChart.append(dot);
    };
    scored.filter((capture) => !capture.imagePath).forEach((capture) => addDot(capture, false));
    scored.filter((capture) => capture.imagePath).forEach((capture) => addDot(capture, true));

    if (baseline) {
      const bx = xScale((baseline.uptimeMs - t0) / 1000);
      const by = H - M.bottom - 8;
      const diamond = svgEl('path', {
        d: `M ${bx} ${by - 6} L ${bx + 6} ${by} L ${bx} ${by + 6} L ${bx - 6} ${by} Z`,
        fill: 'var(--coral)', stroke: 'var(--paper)', 'stroke-width': 1.5,
      });
      const diamondTitle = svgEl('title', {});
      diamondTitle.textContent = t('motion.baselineTitle', baseline.captureId);
      diamond.append(diamondTitle);
      motionChart.append(diamond);
    }
  };

  const setCardProgress = (percent, message) => {
    for (const [track, bar] of [[cardCheckTrack, cardCheckProgress], [movieCardTrack, movieCardProgress]]) {
      if (!track || !bar) continue;
      track.hidden = percent <= 0 || percent >= 100;
      bar.style.width = `${Math.max(4, Math.min(100, percent))}%`;
    }
    if (!message) return;
    if (cardCheckNote) cardCheckNote.textContent = message;
    if (movieCardStatus && movieModal && !movieModal.hidden) movieCardStatus.textContent = message;
  };

  const renderCardCheck = () => {
    if (!cardCheck || !cardCheckNote || !cardCheckButton) return;
    const referenced = data.captures.filter((capture) => capture.imagePath).length;
    if (!referenced) { cardCheck.hidden = true; return; }
    cardCheck.hidden = false;
    if (cardState.mismatch) {
      cardCheck.className = 'card-check card-check-drift';
      cardCheckButton.hidden = false;
      cardCheckButton.textContent = t('cardCheck.tryAnotherFolder');
      return;
    }
    if (!cardState.checked) {
      cardCheck.className = 'card-check';
      cardCheckButton.hidden = false;
      cardCheckButton.textContent = t('cardCheck.button');
      cardCheckNote.textContent = t('cardCheck.note');
      return;
    }
    const missing = cardState.referenced - cardState.present;
    cardCheckButton.hidden = true;
    cardCheck.className = missing ? 'card-check card-check-drift' : 'card-check card-check-clean';
    cardCheckNote.textContent = missing
      ? t('cardCheck.mismatchDrift', cardState.present, cardState.referenced, missing)
      : t('cardCheck.allPresent', cardState.present);
  };

  // Compares the camera's record against the files actually in the chosen
  // folder and adjusts only what this page displays. The card is never written
  // to: rebuilding the on-card record belongs in a host-side tool with a
  // backup, a dry run and a log (docs/reconciliation-policy.md).
  const checkCard = () => {
    if (!card.loaded) return;
    const referenced = data.captures.filter((capture) => capture.imagePath);
    if (!referenced.length) { cardState.mismatch = false; renderCardCheck(); return; }
    // Worked out in full before anything is applied, so a folder that turns out
    // to be the wrong one cannot damage an earlier good result.
    const presence = data.captures.map((capture) => Boolean(capture.imagePath) && Boolean(card.fileFor(capture.imagePath)));
    const present = presence.filter(Boolean).length;
    // None of this card's pictures in the chosen folder almost always means the
    // wrong folder was picked, not that every picture vanished. Saying so is
    // far more useful than showing a page reporting zero pictures.
    if (!present) {
      cardState.mismatch = true;
      renderCardCheck();
      cardCheckNote.textContent = t('cardCheck.wrongFolder');
      return;
    }
    data.captures.forEach((capture, index) => { capture.imageOnCard = presence[index]; });
    cardState.mismatch = false;
    cardState.checked = true;
    cardState.referenced = referenced.length;
    cardState.present = present;
    render();
  };

  const render = () => {
    const captures = filteredCaptures();
    const allImages = data.captures.filter(hasImage);
    const images = captures.filter(hasImage);
    const inferenceOutcomes = new Set(data.captures.map((capture) => capture.inferenceOutcome).filter(Boolean));

    // Counts the pictures, not the capture attempts. In motion mode most rows
    // are "nothing moved" checks that never produced an image, and after a card
    // check the rows whose JPEG is gone are excluded too.
    if (!status.classList.contains('status-warning')) {
      status.textContent = data.captures.length
        ? t('hero.readyStatus', allImages.length)
        : t('hero.noPicturesYet');
    }
    document.querySelector('#welcome-count').textContent = String(allImages.length);
    document.querySelector('#image-count').textContent = String(allImages.length);
    document.querySelector('#gallery-count').textContent = t('gallery.count', allImages.length);

    // Last adventure: how long the newest session actually ran for, from its
    // first captured frame to its last - not the configured session limit,
    // which may not have been reached (a short test, or a stopped session).
    const lastCaptures = lastSessionCaptures().filter(hasImage);
    const lastTimes = lastCaptures.map((capture) => Number(capture.uptimeMs) || 0);
    document.querySelector('#session-duration').textContent = lastTimes.length >= 2
      ? formatDuration((Math.max(...lastTimes) - Math.min(...lastTimes)) / 1000) : '-';

    // Picture size: dimensions from the most recent capture that has them.
    // Reads newest-first since older cards may mix presets between runs.
    const withDimensions = data.captures.filter((capture) => Number(capture.width) > 0 && Number(capture.height) > 0);
    const latestDimensioned = withDimensions[withDimensions.length - 1];
    document.querySelector('#image-resolution').textContent = latestDimensioned
      ? `${latestDimensioned.width} x ${latestDimensioned.height}` : '-';

    // Total time recorded replaced a "Memory card" space-remaining tile on 12
    // September 2026. That tile could only ever read "Soon": the firmware never
    // writes the storage fields, because SdStorage::totalBytes() was found 29
    // August 2026 to report a reproducibly wrong value on every normal (cold)
    // boot (see src/dashboard_writer.cpp). A permanent placeholder was worse
    // than a real number, so the tile now reports something the capture record
    // already knows for certain.
    const recorded = totalRecordedSeconds();
    document.querySelector('#total-recorded').textContent = recorded > 0 ? formatDuration(recorded) : '-';

    const visibleCaptures = (showAllFrames ? captures : captures.slice(-initialLimit)).slice().reverse();
    rows.replaceChildren();
    visibleCaptures.forEach((capture) => {
      const row = document.createElement('tr');
      cell(row, capture.captureId || t('table.unknownCapture'));
      cell(row, relativeTime(capture.uptimeMs));
      cell(row, capture.outcome || t('table.unknownOutcome'));
      const imageCell = document.createElement('td');
      if (hasImage(capture)) {
        const link = document.createElement('button');
        link.className = 'inline-button';
        link.type = 'button';
        link.textContent = t('table.openImage');
        link.addEventListener('click', () => openImage(capture.imagePath, t('table.frameCaption', capture.captureId)));
        imageCell.append(link);
      } else if (capture.imagePath) imageCell.textContent = t('table.noLongerOnCard');
      else imageCell.textContent = t('table.unavailable');
      row.append(imageCell);
      rows.append(row);
    });
    frameToggle.hidden = captures.length <= initialLimit;
    frameToggle.textContent = showAllFrames ? t('adult.showFewerFrames') : t('adult.showAllFrames');

    const visibleImages = (showAllImages ? images : images.slice(-initialLimit)).slice().reverse();
    gallery.replaceChildren();
    galleryEmpty.hidden = images.length > 0;
    galleryEmpty.textContent = images.length ? '' : (search.value.trim() ? t('gallery.noSearchMatch') : t('gallery.empty'));
    const template = document.querySelector('#gallery-item-template');
    visibleImages.forEach((capture) => {
      const item = template.content.firstElementChild.cloneNode(true);
      const image = item.querySelector('img');
      image.src = capture.imagePath;
      image.alt = t('table.frameCaption', capture.captureId);
      item.querySelector('span').textContent = capture.captureId;
      item.addEventListener('click', () => openImage(capture.imagePath, t('table.frameCaption', capture.captureId)));
      gallery.append(item);
    });
    galleryToggle.hidden = images.length <= initialLimit;
    galleryToggle.textContent = showAllImages ? t('gallery.showFewer') : t('gallery.showAll');
    renderMotionPanel();
    // The camera itself never runs AI - that is deliberate, not missing (see
    // docs/next-session.md). model_unavailable on every capture just means
    // no on-device results are baked in yet; it does not mean AI is
    // unavailable - the interactive helper below genuinely works. Fixed 29
    // August 2026: the previous wording here wrongly implied no AI existed
    // at all.
    document.querySelector('#model-note').textContent = inferenceOutcomes.has('model_unavailable')
      ? t('ai.noAIYet')
      : t('ai.hasResults');
    document.title = t('pageTitle.cameraAdventure', allImages.length);
    renderCardCheck();
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
    setLoading(t('loading.message'), t('loading.readingCurrent'), 12);
    try {
      await loadScript('data/captures_current.js');
      currentLoaded = true;
    } catch (error) {
      // The current chunk is optional when the camera finished cleanly.
    }
    setLoading(t('loading.message'), currentLoaded ? t('loading.foundNewest') : t('loading.checkingGroups'), 100 / totalSteps);
    for (const [index, chunk] of chunks.entries()) {
      try {
        await loadScript(chunk);
      } catch (error) {
        failures.push(error.message);
      }
      setLoading(t('loading.puttingInOrder'), t('loading.groupProgress', index + 1, chunks.length), ((index + 2) / totalSteps) * 100);
    }
    if (failures.length) {
      status.textContent = t('loading.someGroupsFailed', failures.length);
      status.classList.add('status-warning');
      if (!data.captures.length) {
        loadingMessage.textContent = t('loading.needsHelp');
        loadingDetail.textContent = t('loading.noGroupsReadable');
        loadingProgress.style.width = '100%';
        loadingError.hidden = false;
        return;
      }
    }
    // The "Ready!" line is written by render() so that it keeps agreeing with
    // the tiles after a card check changes the picture count.
    render();
    finishLoading();
  };

  frameToggle.addEventListener('click', () => { showAllFrames = !showAllFrames; render(); });
  galleryToggle.addEventListener('click', () => { showAllImages = !showAllImages; render(); });
  modalClose.addEventListener('click', closeImage);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeImage(); });
  document.querySelector('#find-insects').addEventListener('click', openModelMessage);
  const makeMovieButton = document.querySelector('#make-movie');
  if (makeMovieButton && movieModal) {
    makeMovieButton.addEventListener('click', openMovie);
    movieClose.addEventListener('click', closeMovie);
    movieCancel.addEventListener('click', cancelMovie);
    movieModal.addEventListener('click', (event) => { if (event.target === movieModal && !movie.active) closeMovie(); });
    movieLoadCard.addEventListener('click', () => card.request());
    movieSession.addEventListener('change', updateMovieCardStatus);
    movieStart.addEventListener('click', makeMovie);
  }
  // One camera card, one choice. Whichever part of the page asked for it, every
  // other part picks the same folder up without asking again.
  window.addEventListener('insect-card-progress', (event) => setCardProgress(event.detail.percent, event.detail.message));
  window.addEventListener('insect-card-cancelled', () => {
    setCardProgress(0, '');
    renderCardCheck();
    if (movieModal && movieSession) updateMovieCardStatus();
  });
  window.addEventListener('insect-card-loaded', () => {
    setCardProgress(0, '');
    checkCard();
    renderCardCheck();
    if (movieModal && movieSession) updateMovieCardStatus();
  });
  if (cardCheckButton) cardCheckButton.addEventListener('click', () => card.request());
  modelModalClose.addEventListener('click', closeModelMessage);
  modelModalOk.addEventListener('click', closeModelMessage);
  modelModal.addEventListener('click', (event) => { if (event.target === modelModal) closeModelMessage(); });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!modal.hidden) closeImage();
    else if (movieModal && !movieModal.hidden) closeMovie();
    else if (!modelModal.hidden) closeModelMessage();
  });
  search.addEventListener('input', render);
  loadingRetry.addEventListener('click', () => window.location.reload());
  // Re-run the render paths that already exist, rather than a second update
  // mechanism just for locale changes - they already recompute every dynamic
  // string from current state.
  window.i18n.onLocaleChange(() => {
    if (data.captures.length || cardState.checked) render();
    if (movieModal && movieSession) updateMovieCardStatus();
  });
  // i18n.js's own DOMContentLoaded handler blindly resets every [data-i18n]
  // element (including #status) to its static base string - normally
  // harmless, since load()'s data usually isn't ready until well after
  // DOMContentLoaded fires and render() runs later still. When data is
  // already available synchronously at parse time (the demo's embedded
  // fixtures), render() can finish before that reset runs and gets silently
  // undone by it. Re-running the same guarded render once DOMContentLoaded
  // fires - the exact same condition onLocaleChange above already uses -
  // guarantees the dynamic text wins regardless of which one landed first.
  document.addEventListener('DOMContentLoaded', () => {
    if (data.captures.length || cardState.checked) render();
  });
  load();
})();
