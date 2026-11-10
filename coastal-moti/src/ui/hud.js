import { SHAKTIS, SHAKTI_ICONS } from '../engine/shaktis.js';

const hex = (n) => `#${n.toString(16).padStart(6, '0')}`;

// Reads game state every frame and updates the DOM only when a value changed.
export function createHud(game) {
  const $ = (id) => document.getElementById(id);
  const hpFill = $('health').firstElementChild, hpLabel = $('health-label');
  const burstEl = $('burst'), burstFill = burstEl.firstElementChild;
  const objective = $('objective'), objText = $('objective-text'), objDist = $('objective-dist');
  const compass = $('compass'), arrow = compass.firstElementChild;
  const flash = $('damage-flash');
  const btnShakti = $('btn-shakti'), btnBurst = $('btn-burst');
  const stealth = $('stealth'), stealthFill = stealth.querySelector('i'), stealthLabel = $('stealth-label');
  const last = {};
  const set = (key, value, apply) => { if (last[key] !== value) { last[key] = value; apply(value); } };

  // Shakti icons: tap/click to select. Locked until a mission unlocks them.
  const icons = SHAKTIS.map((s, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'shakti';
    b.style.setProperty('--c', hex(s.color));
    b.setAttribute('aria-label', s.name);
    b.innerHTML = `<svg viewBox="0 0 24 24"><path d="${SHAKTI_ICONS[s.id]}"/></svg><span class="cd"></span><span class="key">${i + 1}</span>`;
    b.addEventListener('pointerdown', (e) => { e.stopPropagation(); game.player.selectShakti(i); });
    $('shaktis').appendChild(b);
    return b;
  });

  $('pause-btn').addEventListener('click', () => game.pauseMenu.toggle());
  game.events.on('tool', () => { compass.classList.remove('ping'); void compass.offsetWidth; compass.classList.add('ping'); });

  function update() {
    const { player, progress, rig } = game;
    const h = player.health;
    set('hp', Math.max(0, h.ratio).toFixed(3), (v) => { hpFill.style.transform = `scaleX(${v})`; });
    set('hpLabel', `${Math.ceil(h.hp)} / ${h.max} · LV ${progress.playerLevel}`, (v) => { hpLabel.textContent = v; });
    set('burst', (player.burst / 100).toFixed(2), (v) => { burstFill.style.transform = `scaleX(${v})`; });
    set('burstReady', player.burst >= 100, (v) => { burstEl.classList.toggle('ready', v); btnBurst.classList.toggle('ready', v); });

    icons.forEach((el, i) => {
      const s = SHAKTIS[i];
      const locked = !progress.unlockedShaktis.includes(s.id);
      set(`lock${i}`, locked, (v) => el.classList.toggle('locked', v));
      set(`sel${i}`, !locked && player.currentShakti === i, (v) => el.classList.toggle('selected', v));
      set(`cd${i}`, (player.shaktiCooldowns[i] / s.cooldown).toFixed(2), (v) => el.style.setProperty('--cd', v));
    });
    const cur = SHAKTIS[player.currentShakti];
    const curLocked = !progress.unlockedShaktis.includes(cur.id);
    set('btnShakti', `${cur.id}|${curLocked}`, () => {
      btnShakti.textContent = curLocked ? 'Shakti' : cur.name;
      btnShakti.classList.toggle('locked', curLocked);
      btnShakti.style.setProperty('--c', curLocked ? '' : hex(cur.color));
    });

    // Stealth meter (only while a stealth mission sets game.stealth).
    const st = game.stealth;
    set('stealthOn', !!st, (v) => { stealth.hidden = !v; });
    if (st) {
      const mode = st.level > 0.02 ? 'seen' : st.lit ? 'lit' : 'hidden';
      set('stealthMode', mode, (v) => {
        stealth.classList.toggle('seen', v === 'seen');
        stealth.classList.toggle('lit', v === 'lit');
        stealthLabel.textContent = v === 'seen' ? 'SEEN' : v === 'lit' ? 'IN LIGHT' : 'HIDDEN';
      });
      set('stealthLevel', st.level.toFixed(2), (v) => { stealthFill.style.transform = `scaleX(${v})`; });
    }

    // Objective text + compass arrow (points at the objective relative to where the camera looks).
    const text = game.missions.objectiveText;
    set('obj', text, (v) => { objText.textContent = v; objective.classList.toggle('empty', !v); });
    const t = game.objectiveTarget;
    set('hasTarget', !!t, (v) => compass.classList.toggle('none', !v));
    if (t) {
      const dx = t.x - player.pos.x, dz = t.z - player.pos.z;
      const f = rig.forward(), r = rig.right();
      const angle = Math.atan2(dx * r.x + dz * r.z, dx * f.x + dz * f.z);
      set('arrow', angle.toFixed(2), (v) => { arrow.style.transform = `rotate(${v}rad)`; });
      set('dist', `${Math.round(Math.hypot(dx, dz))} m`, (v) => { objDist.textContent = v; });
    } else set('dist', '', (v) => { objDist.textContent = v; });
  }

  return {
    update,
    flashDamage() {
      flash.classList.add('on');
      requestAnimationFrame(() => requestAnimationFrame(() => flash.classList.remove('on')));
    },
    setFps(fps) { $('fps').textContent = `${fps} FPS`; },
  };
}
