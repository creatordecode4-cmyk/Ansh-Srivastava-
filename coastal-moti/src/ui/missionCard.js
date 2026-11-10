// Full-screen cards.
//   show(mission): "23:40 · Seepgaon Diya-Ghar" + mission name, then fade to gameplay.
//   line(text):    fade to black with one line of text (used at the end of a mission). Stays up.
const HOLD_MS = 2600, FADE_MS = 700, LINE_HOLD_MS = 3400;

export function createMissionCard(mobile) {
  const el = document.getElementById('mission-card');
  const meta = document.getElementById('card-meta');
  const name = document.getElementById('card-name');
  document.getElementById('card-skip').textContent = mobile ? 'Tap to continue' : 'Click or press any key';
  let finish = null;

  const skip = () => finish?.();
  el.addEventListener('pointerdown', skip);
  window.addEventListener('keydown', skip);

  // Resolves when the hold time is over (or the player skips); the card then fades out.
  function show(mission) {
    finish?.();
    el.classList.remove('line');
    meta.textContent = `${mission.time} · ${mission.location}`;
    name.textContent = mission.name;
    el.hidden = false;
    el.style.transition = 'none';
    el.classList.add('on');
    void el.offsetWidth; // apply instantly: the card covers the world while it is set up
    el.style.transition = '';
    return new Promise((resolve) => {
      let timer = setTimeout(() => finish(), HOLD_MS);
      finish = () => {
        finish = null;
        clearTimeout(timer);
        hide();
        resolve(); // gameplay starts while the card fades
      };
    });
  }

  function hide() {
    el.classList.remove('on');
    setTimeout(() => { if (!el.classList.contains('on')) el.hidden = true; }, FADE_MS);
  }

  // Fades in, holds, and resolves with the card still covering the screen.
  function line(text) {
    finish?.();
    el.classList.add('line');
    meta.textContent = '';
    name.textContent = text;
    el.hidden = false;
    void el.offsetWidth;
    el.classList.add('on');
    return new Promise((resolve) => {
      const timer = setTimeout(() => finish(), FADE_MS + LINE_HOLD_MS);
      finish = () => { finish = null; clearTimeout(timer); resolve(); };
    });
  }

  return { show, line, hide, get visible() { return !el.hidden; } };
}
