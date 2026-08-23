(() => {
  const picker = document.querySelector('#card-picker');
  const normalisePath = (value) => String(value || '').replaceAll('\\', '/').replace(/^\.\//, '').replace(/^\/+/, '').toLowerCase();
  const card = window.InsectCard = window.InsectCard || { files: new Map(), loaded: false };
  card.normalisePath = normalisePath;
  card.directoryHandle = undefined;
  card.writePermission = 'prompt';
  card.writeError = '';
  card.fileByName = (name) => {
    const wanted = String(name || '').toLowerCase();
    for (const [path, file] of card.files) if (path === wanted || path.endsWith(`/${wanted}`)) return file;
    return undefined;
  };
  card.fileFor = (path) => card.files.get(normalisePath(path)) || card.fileByName(normalisePath(path));
  card.request = () => {
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
      card.writeError = 'This browser cannot ask for permission to change a folder.';
      window.dispatchEvent(new CustomEvent('insect-card-write-ready'));
      return false;
    }
    try {
      // This is deliberately separate from the read-only FileList picker. The browser
      // must obtain a writable directory handle from a clear, user-initiated action.
      const handle = await window.showDirectoryPicker({ id: 'insect-ai-card', mode: 'readwrite' });
      const permission = await handle.requestPermission({ mode: 'readwrite' });
      if (permission !== 'granted') throw new Error('Permission to change this camera card was not granted.');
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
    if (!safeName || safeName.includes('/') || safeName.includes('\\')) throw new Error('Only a card-root filename may be read.');
    if (card.directoryHandle) {
      try {
        const handle = await card.directoryHandle.getFileHandle(safeName);
        return (await handle.getFile()).text();
      } catch (error) {
        if (error?.name !== 'NotFoundError') throw error;
      }
    }
    const file = card.fileByName(safeName);
    if (!file) throw new Error(`${safeName} was not found on the selected camera card.`);
    return file.text();
  };
  card.writeText = async (name, text) => {
    const safeName = String(name || '').replace(/^\/+/, '');
    if (!safeName || safeName.includes('/') || safeName.includes('\\')) throw new Error('Only a card-root filename may be changed.');
    if (!card.directoryHandle) throw new Error('Choose the camera card and allow changes first.');
    const permission = await card.directoryHandle.requestPermission({ mode: 'readwrite' });
    if (permission !== 'granted') throw new Error('Permission to change this camera card was not granted.');
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
  picker.addEventListener('change', () => {
    card.files = new Map();
    for (const file of picker.files) {
      card.files.set(normalisePath(file.webkitRelativePath || file.name), file);
      card.files.set(normalisePath(file.name), file);
    }
    card.loaded = card.files.size > 0;
    window.dispatchEvent(new CustomEvent('insect-card-loaded'));
  });
})();
