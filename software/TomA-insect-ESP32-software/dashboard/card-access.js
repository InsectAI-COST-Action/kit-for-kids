(() => {
  const { t } = window.i18n;
  const picker = document.querySelector('#card-picker');
  const normalisePath = (value) => String(value || '').replaceAll('\\', '/').replace(/^\.\//, '').replace(/^\/+/, '').toLowerCase();
  const card = window.InsectCard = window.InsectCard || { files: new Map(), loaded: false };
  card.normalisePath = normalisePath;
  card.directoryHandle = undefined;
  card.writePermission = 'prompt';
  card.writeError = '';
  // One shared loading state for every part of the page. The card is chosen
  // once; the AI section, the movie maker and the front-page picture check all
  // read the same progress from here rather than each asking for the folder
  // again (reported 12 September 2026: choosing the card twice felt broken).
  card.busy = false;
  card.progress = { percent: 0, message: '' };
  const announce = (percent, message) => {
    card.progress = { percent, message };
    window.dispatchEvent(new CustomEvent('insect-card-progress', { detail: card.progress }));
  };
  card.fileByName = (name) => {
    const wanted = String(name || '').toLowerCase();
    // Indexed lookup first; the scan is the rare fallback, not the normal path.
    const direct = card.files.get(wanted);
    if (direct) return direct;
    for (const [path, file] of card.files) if (path === wanted || path.endsWith(`/${wanted}`)) return file;
    return undefined;
  };
  // Deliberately does NOT fall through to fileByName's scan. A capture's
  // imagePath always has the fixed "images/<run>/shard/<file>.jpg" shape
  // (docs/data-schema.md), and the batch load below already indexes that
  // exact form plus the bare filename - both O(1) hits. Reported 13 September
  // 2026: the movie and AI panels felt slow to open on a card whose record
  // count (28,717) far exceeds its surviving images (1,036) after
  // reconciliation. Every one of those ~27,000 "genuinely deleted" lookups
  // used to miss the index and then scan every indexed key looking for
  // something that provably isn't there - the scan is dead weight for this
  // path, not a safety net, so it is skipped here. fileByName keeps its scan
  // for its own rare, genuinely by-name callers (config.json, model files).
  card.fileFor = (path) => {
    const key = normalisePath(path);
    return card.files.get(key) || card.files.get(key.slice(key.lastIndexOf('/') + 1));
  };
  // Session names and picture counts, read straight from the file listing the
  // picker already gave us - no need to touch a single capture record. Every
  // real image lives at "images/<run-id>/shard_<nnnn>/<capture-id>.jpg"
  // (docs/data-schema.md), so the run id and a genuine picture both fall out
  // of the path alone. Added 13 September 2026: the movie and AI panels used
  // to build this same list by walking every capture record and checking
  // each one's file - correct, but its cost scaled with how many pictures
  // were ever recorded, not with what is actually on the card now. On a
  // reconciled card those can be tens of thousands apart. Each physical file
  // is indexed under 2-3 keys (see the batch loader below); dedupe by the
  // File object itself so a picture is never counted twice.
  const SESSION_PATH_PATTERN = /(?:^|\/)images\/([^/]+)\/.*\.jpg$/;
  card.sessionCounts = () => {
    const counted = new Set();
    const counts = new Map();
    for (const [path, file] of card.files) {
      if (counted.has(file)) continue;
      const match = path.match(SESSION_PATH_PATTERN);
      if (!match) continue;
      counted.add(file);
      counts.set(match[1], (counts.get(match[1]) || 0) + 1);
    }
    return counts;
  };
  card.request = () => {
    card.busy = true;
    announce(6, t('card.chooseFolderPrompt'));
    try {
      if (typeof picker.showPicker === 'function') picker.showPicker();
      else picker.click();
    } catch (error) {
      picker.click();
    }
  };
  card.writeSupported = () => typeof window.showDirectoryPicker === 'function';
  card.canWrite = () => Boolean(card.directoryHandle && card.writePermission === 'granted');
  card.requestWrite = async () => {
    card.writeError = '';
    if (!card.writeSupported()) {
      card.writePermission = 'denied';
      card.writeError = t('card.cannotAskPermission');
      window.dispatchEvent(new CustomEvent('insect-card-write-ready'));
      return false;
    }
    try {
      // This is deliberately separate from the read-only FileList picker. The browser
      // must obtain a writable directory handle from a clear, user-initiated action.
      const handle = await window.showDirectoryPicker({ id: 'insect-ai-card', mode: 'readwrite' });
      const permission = await handle.requestPermission({ mode: 'readwrite' });
      if (permission !== 'granted') throw new Error(t('card.permissionNotGranted'));
      card.directoryHandle = handle;
      card.writePermission = permission;
      window.dispatchEvent(new CustomEvent('insect-card-write-ready'));
      return true;
    } catch (error) {
      card.writePermission = 'denied';
      card.writeError = error instanceof Error ? error.message : String(error);
      window.dispatchEvent(new CustomEvent('insect-card-write-ready'));
      return false;
    }
  };
  card.readText = async (name) => {
    const safeName = String(name || '').replace(/^\/+/, '');
    if (!safeName || safeName.includes('/') || safeName.includes('\\')) throw new Error(t('card.onlyRootFilenameRead'));
    if (card.directoryHandle) {
      try {
        const handle = await card.directoryHandle.getFileHandle(safeName);
        return (await handle.getFile()).text();
      } catch (error) {
        if (error?.name !== 'NotFoundError') throw error;
      }
    }
    const file = card.fileByName(safeName);
    if (!file) throw new Error(t('card.fileNotFound', safeName));
    return file.text();
  };
  card.writeText = async (name, text) => {
    const safeName = String(name || '').replace(/^\/+/, '');
    if (!safeName || safeName.includes('/') || safeName.includes('\\')) throw new Error(t('card.onlyRootFilenameWrite'));
    if (!card.directoryHandle) throw new Error(t('card.chooseAndAllowFirst'));
    const permission = await card.directoryHandle.requestPermission({ mode: 'readwrite' });
    if (permission !== 'granted') throw new Error(t('card.permissionNotGranted'));
    card.writePermission = permission;
    const handle = await card.directoryHandle.getFileHandle(safeName, { create: true });
    const writable = await handle.createWritable();
    try {
      await writable.write(String(text));
      await writable.close();
    } catch (error) {
      try { await writable.abort(); } catch (ignored) { }
      throw error;
    }
    const file = await handle.getFile();
    card.files.set(normalisePath(safeName), file);
    window.dispatchEvent(new CustomEvent('insect-card-written', { detail: { name: safeName } }));
  };
  const yieldToPaint = () => new Promise((resolve) => window.setTimeout(resolve, 0));
  // Chrome and Edge fire this when the folder window is dismissed. Without it a
  // cancelled choice would leave every section showing a stalled progress bar.
  picker.addEventListener('cancel', () => {
    card.busy = false;
    announce(0, '');
    window.dispatchEvent(new CustomEvent('insect-card-cancelled'));
  });
  picker.addEventListener('change', async () => {
    card.busy = true;
    const files = [...picker.files];
    announce(12, t('card.readingProgress', 0, files.length));
    // Built in batches with a paint between them. A full card can hold many
    // thousands of files, and one synchronous pass froze the page with no sign
    // that anything was happening.
    const next = new Map();
    const batchSize = 400;
    for (let index = 0; index < files.length; index += batchSize) {
      for (const file of files.slice(index, index + batchSize)) {
        const relative = normalisePath(file.webkitRelativePath || file.name);
        next.set(relative, file);
        // The picker reports paths under the chosen folder ("insect-ai/images/
        // ..."), but a capture records its path from the card root
        // ("images/..."). Indexing the root-stripped form too makes every
        // lookup a single Map hit; without it each one fell through to
        // fileByName's linear scan. Added 12 September 2026 when the live card
        // turned out to hold 28,717 capture records against 1,576 files, so
        // one card check performs 28,717 lookups. Honest caveat: at that size
        // both forms measured too fast to tell apart (headless timers are
        // clamped), so this is insurance against O(n) per lookup on a bigger
        // card, not a fix for an observed freeze.
        const stripped = relative.slice(relative.indexOf('/') + 1);
        if (relative.includes('/') && !next.has(stripped)) next.set(stripped, file);
        next.set(normalisePath(file.name), file);
      }
      const done = Math.min(index + batchSize, files.length);
      announce(12 + Math.round((done / Math.max(1, files.length)) * 83), t('card.readingProgress', done, files.length));
      await yieldToPaint();
    }
    card.files = next;
    card.loaded = next.size > 0;
    card.busy = false;
    announce(100, card.loaded ? t('card.ready') : t('card.emptyFolder'));
    window.dispatchEvent(new CustomEvent('insect-card-loaded'));
  });
})();
