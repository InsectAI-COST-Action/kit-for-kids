(() => {
  const { t } = window.i18n;
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
    high: { frameSize: 'QXGA', jpegQuality: 12, labelKey: 'settings.quality.highLabel' },
    low: { frameSize: 'VGA', jpegQuality: 24, labelKey: 'settings.quality.lowLabel' },
  };
  const intervalLabel = (milliseconds) => t('settings.intervalPhrase', milliseconds / 1000);
  const durationLabel = (seconds) => t('settings.durationPhrase', seconds);
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
    if (settings.frame_size === 'QXGA' && Number(settings.jpeg_quality) === 12) return t(QUALITY.high.labelKey);
    if (settings.frame_size === 'VGA' && Number(settings.jpeg_quality) === 24) return t(QUALITY.low.labelKey);
    return t('settings.unknownQuality', settings.frame_size, settings.jpeg_quality);
  };
  const describe = (settings) => {
    const motionDescription = t(settings.motion_trigger_enabled ? 'settings.motionOnDescription' : 'settings.motionOffDescription');
    return t('settings.describeComposed', intervalLabel(intervalFor(settings)), imageLabelFor(settings), durationLabel(Number(settings.max_session_seconds)), motionDescription);
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
      status.textContent = t('settings.cardReadyChoose');
      return;
    }
    allowButton.hidden = false;
    writeButton.disabled = true;
    if (!card.writeSupported()) {
      allowButton.disabled = true;
      status.textContent = t('settings.browserCannotWrite');
    } else if (card.loaded) {
      allowButton.disabled = false;
      status.textContent = t('settings.pleaseAllowAgain');
    } else {
      allowButton.disabled = false;
      status.textContent = t('settings.chooseAndAllow');
    }
  };
  const showCurrent = async () => {
    try {
      const value = JSON.parse(await card.readText('config.json'));
      const controlsMatch = applyCurrentToControls(value);
      current.textContent = controlsMatch ?
        t('settings.currentMatches', describe(value)) :
        t('settings.currentNoMatch', describe(value));
    } catch (error) {
      current.textContent = t('settings.currentUnavailable');
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
    status.textContent = t('settings.chooseAndAllowBrowserPrompt');
    await card.requestWrite();
    renderAccess();
    if (!card.canWrite() && card.writeError) status.textContent = t('settings.cardNotChanged', card.writeError);
    await showCurrent();
  };
  const writeSettings = async () => {
    if (!card.canWrite()) return;
    const settings = configFor(selected());
    const description = describe(settings);
    const extraWarning = settings.max_session_seconds === 0 ? t('settings.infiniteWarning') : '';
    if (!window.confirm(t('settings.confirmPrompt', description, extraWarning))) return;
    writeButton.disabled = true;
    status.textContent = t('settings.saving');
    try {
      await card.writeText('config.json', `${JSON.stringify(settings, null, 2)}\n`);
      status.textContent = t('settings.savedMessage', description);
      current.textContent = t('settings.currentSaved', description);
    } catch (error) {
      status.textContent = t('settings.cardNotChanged', error instanceof Error ? error.message : String(error));
    } finally {
      renderAccess();
    }
  };
  if (!modal || !openButton) return;
  openButton.addEventListener('click', open);
  closeButton.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  allowButton.addEventListener('click', allowCard);
  writeButton.addEventListener('click', writeSettings);
  window.addEventListener('insect-card-write-ready', async () => { if (!modal.hidden) { renderAccess(); await showCurrent(); } });
  window.addEventListener('insect-card-loaded', async () => { if (!modal.hidden) { renderAccess(); await showCurrent(); } });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) close(); });
  window.i18n.onLocaleChange(async () => { if (!modal.hidden) { renderAccess(); await showCurrent(); } });
})();
