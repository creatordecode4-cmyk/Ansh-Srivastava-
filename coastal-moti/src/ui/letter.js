// Dadaji's tin box: shows the half map and one letter. Letters are not radio lines,
// so the 12-word radio rule does not apply to them.
export function createLetter() {
  const el = document.getElementById('letter');
  const text = document.getElementById('lt-text');
  const done = document.getElementById('lt-done');
  let resolve = null;

  function finish() { if (!resolve) return; const r = resolve; close(); r(); }
  function close() { el.hidden = true; resolve = null; }
  done.addEventListener('click', finish);
  window.addEventListener('keydown', (e) => { if (!el.hidden && (e.code === 'Enter' || e.code === 'Space')) finish(); });

  return {
    show(letterText) {
      text.textContent = `“${letterText}”`;
      el.hidden = false;
      return new Promise((r) => { resolve = r; });
    },
    close,
    get open() { return !el.hidden; },
  };
}
