(() => {
  const modal = document.querySelector('#settings-modal');
  const openButton = document.querySelector('#configure-camera');
  const closeButton = document.querySelector('#settings-close');
  const allowButton = document.querySelector('#settings-allow-card');
  const writeButton = document.querySelector('#settings-write');
  const status = document.querySelector('#settings-status');
  const current = document.querySelector('#settings-current');
  const interval = document.querySelector('#settings-interval');
  const quality = document.querySelector('#settings-quality');
  const duration = document.querySelector('#settings-duration');
  const motion = document.querySelector('#settings-motion-trigger');
  const card = window.InsectCard;
  let lastFocus;
  const QUALITY = {
    high: { frameSize: 'QXGA', jpegQuality: 12, label: 'High quality (QXGA)' },
    low: { frameSize: 'VGA', jpegQuality: 24, label: 'Low quality (VGA)' },
  };
  const intervalLabel = (milliseconds) => {
    const seconds = milliseconds / 1000;
    return seconds === 60 ? 'one picture every 1 minute' : `one picture every ${seconds} second${seconds === 1 ? '' : 's'}`;
  };
  const durationLabel = (seconds) => {
    if (seconds === 0) return 'until you switch the camera off';
    const minutes = seconds / 60;
    return `${minutes} minute${minutes === 1 ? '' : 's'}`;
  };
  const selected = () => ({
    intervalMs: Number(interval.value), qualityKey: quality.value, durationSeconds: Number(duration.value), motionTriggerEnabled: motion.checked,
  });
  const configFor = ({ intervalMs, qualityKey, durationSeconds, motionTriggerEnabled }) => {
    const image = QUALITY[qualityKey];
    const pilot = !motionTriggerEnabled && intervalMs === 1000 && qualityKey === 'high' && durationSeconds === 3600;
    const durationId = durationSeconds === 0 ? 'infinite' : `${durationSeconds}s`;
    return {
      schema_version: 1,
      capture_fps: 1,
      capture_interval_ms: intervalMs,
      max_session_seconds: durationSeconds,
      capture_mode: pilot ? 'pilot' : 'custom',
      camera_preset: pilot ? 'qxga_q12_1fps' : `custom_${qualityKey}_${intervalMs}ms_${durationId}${motionTriggerEnabled ? '_motion' : ''}`,
      motion_trigger_enabled: motionTriggerEnabled,
      motion_threshold: 5,
      frame_size: image.frameSize,
      jpeg_quality: image.jpegQuality,
      model_id: 'none',
      log_level: 'info',
    };
  };
  const intervalFor = (settings) => Number(settings.capture_interval_ms) || (Number(settings.capture_fps) ? 1000 / Number(settings.capture_fps) : 1000);
  const imageLabelFor = (settings) => {
    if (settings.frame_size === 'QXGA' && Number(settings.jpeg_quality) === 12) return QUALITY.high.label;
    if (settings.frame_size === 'VGA' && Number(settings.jpeg_quality) === 24) return QUALITY.low.label;
    return `${settings.frame_size || 'unknown'} quality ${settings.jpeg_quality ?? 'unknown'}`;
  };
  const describe = (settings) => {
    const motionDescription = settings.motion_trigger_enabled ? 'save the first picture, then only save changes (motion score 5)' : 'save every picture';
    return `${intervalLabel(intervalFor(settings))}, ${imageLabelFor(settings)}, for ${durationLabel(Number(settings.max_session_seconds))}; ${motionDescription}`;
  };
  const applyCurrentToControls = (settings) => {
    const milliseconds = intervalFor(settings);
    const durationSeconds = Number(settings.max_session_seconds);
    const qualityKey = settings.frame_size === 'VGA' && Number(settings.jpeg_quality) === 24 ? 'low' :
      (settings.frame_size === 'QXGA' && Number(settings.jpeg_quality) === 12 ? 'high' : '');
    const valid = [...interval.options].some((option) => Number(option.value) === milliseconds) &&
      [...duration.options].some((option) => Number(option.value) === durationSeconds) && Boolean(qualityKey);
    if (!valid) return false;
    interval.value = String(milliseconds);
    duration.value = String(durationSeconds);
    quality.value = qualityKey;
    motion.checked = settings.motion_trigger_enabled === true;
    return true;
  };
  const renderAccess = () => {
    if (card.canWrite()) {
      allowButton.hidden = true;
      writeButton.disabled = false;
      status.textContent = 'Camera card ready. Choose your three settings, then save them to the card.';
      return;
    }
    allowButton.hidden = false;
    writeButton.disabled = true;
    if (!card.writeSupported()) {
      allowButton.disabled = true;
      status.textContent = 'This browser cannot safely change camera-card files. Use current Chrome or Edge for this experimental tool.';
    } else if (card.loaded) {
      allowButton.disabled = false;
      status.textContent = 'Your pictures are loaded. To change settings, choose the same camera-card folder once more and allow changes.';
    } else {
      allowButton.disabled = false;
      status.textContent = 'Choose the top INSECT-AI camera-card folder and allow changes.';
    }
  };
  const showCurrent = async () => {
    try {
      const value = JSON.parse(await card.readText('config.json'));
      const controlsMatch = applyCurrentToControls(value);
      current.textContent = controlsMatch ?
        `Current setting on this card: ${describe(value)}. The choices below match it.` :
        `Current setting on this card: ${describe(value)}. Choose one of the safe settings below to replace it.`;
    } catch (error) {
      current.textContent = 'Current setting: not available until the camera card is chosen.';
    }
  };
  const open = async () => {
    lastFocus = document.activeElement;
    modal.hidden = false;
    renderAccess();
    await showCurrent();
    (card.canWrite() ? writeButton : allowButton).focus();
  };
  const close = () => {
    modal.hidden = true;
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  };
  const allowCard = async () => {
    allowButton.disabled = true;
    status.textContent = 'Choose the top INSECT-AI camera-card folder, then allow changes when your browser asks.';
    await card.requestWrite();
    renderAccess();
    if (!card.canWrite() && card.writeError) status.textContent = `The camera card was not changed: ${card.writeError}`;
    await showCurrent();
  };
  const writeSettings = async () => {
    if (!card.canWrite()) return;
    const settings = configFor(selected());
    const description = describe(settings);
    const extraWarning = settings.max_session_seconds === 0 ? '\n\nInfinite means the camera keeps taking pictures until it is switched off or the card fills up.' : '';
    if (!window.confirm(`Save this camera setting?\n\n${description}${extraWarning}\n\nIt will replace config.json and take effect after the board is restarted.`)) return;
    writeButton.disabled = true;
    status.textContent = 'Saving the camera setting safely...';
    try {
      await card.writeText('config.json', `${JSON.stringify(settings, null, 2)}\n`);
      status.textContent = `Saved! The next camera session will use ${description}. Safely disconnect the card, then restart the board.`;
      current.textContent = `Current setting on this card: ${description}. Saved to config.json; the choices above now match it.`;
    } catch (error) {
      status.textContent = `The camera card was not changed: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      renderAccess();
    }
  };
  openButton.addEventListener('click', open);
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  allowButton.addEventListener('click', allowCard);
  writeButton.addEventListener('click', writeSettings);
  window.addEventListener('insect-card-write-ready', async () => { if (!modal.hidden) { renderAccess(); await showCurrent(); } });
  window.addEventListener('insect-card-loaded', async () => { if (!modal.hidden) { renderAccess(); await showCurrent(); } });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) close(); });
})();
