// Full-screen mission card: "23:40 · Seepgaon Diya-Ghar" + mission name, then fade to gameplay.
const HOLD_MS = 2600, FADE_MS = 700;

export function createMissionCard(mobile) {
  const el = document.getElementById('mission-card');
  const meta = document.getElementById('card-meta');
  const name = document.getElementById('card-name');
  document.getElementById('card-skip').textContent = mobile ? 'Tap to continue' : 'Click or press any key';
  let finish = null;

  const skip = () => finish?.();
  el.addEventListener('pointerdown', skip);
  window.addEventListener('keydown', skip);

  // Resolves when the card has fully faded out.
  function show(mission) {
    finish?.();
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
        el.classList.remove('on');
        timer = setTimeout(() => { if (!el.classList.contains('on')) el.hidden = true; }, FADE_MS);
        resolve(); // gameplay starts while the card fades
      };
    });
  }
  return { show, get visible() { return !el.hidden; } };
}
