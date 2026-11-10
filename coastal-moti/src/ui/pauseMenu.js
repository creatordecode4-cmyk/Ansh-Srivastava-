import { saveSettings } from '../save/settings.js';

// Pause menu: resume, graphics quality (Low/Medium/High), sound, restart, reset progress.
export function createPauseMenu(game) {
  const $ = (id) => document.getElementById(id);
  const el = $('pause-menu');
  const qualityBtns = [...$('pm-quality').children];
  const soundBtns = [...$('pm-sound').children];
  const resetBtn = $('pm-reset');
  let confirmReset = false;

  $('pm-help').innerHTML = game.mobile
    ? 'Left thumb: move (push to the edge to run). Right side: drag to look. Tap a Shakti icon to select it.'
    : 'WASD move · Shift run · Space dodge · Mouse look · Left click or J attack · Right click or Q Shakti · ' +
      '1-5 select Shakti · F Burst · E Tool · Esc or P pause';

  function refresh() {
    qualityBtns.forEach((b) => b.classList.toggle('on', b.dataset.quality === game.settings.quality));
    soundBtns.forEach((b) => b.classList.toggle('on', (b.dataset.muted === 'true') === !!game.settings.muted));
    confirmReset = false;
    resetBtn.textContent = 'Reset all progress';
  }

  function open() {
    if (game.paused) return;
    game.paused = true;
    game.input.releasePointer();
    refresh();
    el.hidden = false;
    game.audio.play('ui');
  }
  function close(recapture = false) {
    if (!game.paused) return;
    game.paused = false;
    el.hidden = true;
    if (recapture && !game.mobile) game.input.capturePointer();
  }

  $('pm-resume').addEventListener('click', () => close(true));
  $('pm-restart').addEventListener('click', () => { close(true); game.missions.restart(); });
  resetBtn.addEventListener('click', () => {
    if (!confirmReset) { confirmReset = true; resetBtn.textContent = 'Tap again to erase progress'; return; }
    close(true);
    game.resetProgress();
  });
  qualityBtns.forEach((b) => b.addEventListener('click', () => {
    game.settings.quality = b.dataset.quality;
    game.engine.setQuality(b.dataset.quality);
    saveSettings(game.settings);
    refresh();
  }));
  soundBtns.forEach((b) => b.addEventListener('click', () => {
    game.settings.muted = b.dataset.muted === 'true';
    saveSettings(game.settings);
    refresh();
    game.audio.refresh();
    game.audio.play('ui');
  }));

  return { open, close, toggle() { game.paused ? close() : open(); } };
}
