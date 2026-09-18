// Demo-only: populates window.InsectCard from the base64 fixture
// tools/install_dashboard_demo.py generates (demo-embedded-files.js), instead of
// requiring the native folder-picker card-access.js otherwise depends on. There is
// no separate "card" to point that picker at in a demo, and browsers refuse to let
// a file:// page read local files any other way (no fetch() fallback - see the
// install script's own docstring for why). Loaded last, after card-access.js,
// dashboard.js, settings.js and analysis.js have all registered their own
// window.addEventListener('insect-card-loaded', ...) handlers, so dispatching the
// event here reaches every one of them exactly as a real picker choice would.
(() => {
  const entries = window.InsectDemoFiles;
  if (!entries || !entries.length) return;
  const card = window.InsectCard;
  if (!card) return;

  const toFile = (entry) => {
    const binary = atob(entry.base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const name = entry.name.slice(entry.name.lastIndexOf('/') + 1);
    return new File([bytes], name, { type: entry.type });
  };

  const files = new Map();
  for (const entry of entries) {
    const file = toFile(entry);
    // Both keys mirror exactly what the real picker's change handler indexes
    // (card-access.js): the file's own relative path, and its bare filename -
    // the two forms card.fileFor()/card.fileByName() already look up.
    files.set(card.normalisePath(entry.name), file);
    files.set(card.normalisePath(file.name), file);
  }
  card.files = files;
  card.loaded = true;
  window.dispatchEvent(new CustomEvent('insect-card-loaded'));
})();
