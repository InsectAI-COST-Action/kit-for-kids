(() => {
  const picker = document.querySelector('#card-picker');
  const normalisePath = (value) => String(value || '').replaceAll('\\', '/').replace(/^\.\//, '').replace(/^\/+/, '').toLowerCase();
  const card = window.InsectCard = window.InsectCard || { files: new Map(), loaded: false };
  card.normalisePath = normalisePath;
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
