// Touch controls: virtual joystick (left half of the screen), drag-to-look (right half),
// and five action buttons. Everything writes into the shared input object.
const STICK_RADIUS = 52;
const LOOK_SENS = 0.006; // radians per CSS pixel

export function enableTouchControls(input) {
  const layer = document.getElementById('touch-layer');
  const ui = document.getElementById('touch-ui');
  const stick = document.getElementById('stick');
  const knob = document.getElementById('stick-knob');
  if (!layer.hidden) return; // already on
  layer.hidden = false;
  ui.hidden = false;
  document.body.classList.add('touch');

  let stickId = null, lookId = null;
  let ox = 0, oy = 0, lx = 0, ly = 0;
  const home = stick.getBoundingClientRect();

  function placeStick(cx, cy) {
    stick.style.left = `${cx - home.width / 2}px`;
    stick.style.top = `${cy - home.height / 2}px`;
    stick.style.bottom = 'auto';
  }
  function resetStick() {
    stickId = null;
    input.setMove(0, 0);
    knob.style.transform = '';
    stick.style.left = stick.style.top = stick.style.bottom = '';
  }

  layer.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    try { layer.setPointerCapture(e.pointerId); } catch { /* synthetic events */ }
    if (stickId === null && e.clientX < window.innerWidth / 2) {
      stickId = e.pointerId; ox = e.clientX; oy = e.clientY;
      placeStick(ox, oy); // the stick appears under the thumb
    } else if (lookId === null) {
      lookId = e.pointerId; lx = e.clientX; ly = e.clientY;
    }
  });
  layer.addEventListener('pointermove', (e) => {
    if (e.pointerId === stickId) {
      let dx = e.clientX - ox, dy = e.clientY - oy;
      const d = Math.hypot(dx, dy);
      if (d > STICK_RADIUS) { dx *= STICK_RADIUS / d; dy *= STICK_RADIUS / d; }
      knob.style.transform = `translate(${dx}px, ${dy}px)`;
      input.setMove(dx / STICK_RADIUS, -dy / STICK_RADIUS);
    } else if (e.pointerId === lookId) {
      input.addLook((e.clientX - lx) * LOOK_SENS, (e.clientY - ly) * LOOK_SENS);
      lx = e.clientX; ly = e.clientY;
    }
  });
  const end = (e) => {
    if (e.pointerId === stickId) resetStick();
    if (e.pointerId === lookId) lookId = null;
  };
  layer.addEventListener('pointerup', end);
  layer.addEventListener('pointercancel', end);

  for (const btn of ui.querySelectorAll('.tbtn')) {
    btn.addEventListener('pointerdown', (e) => {
      e.preventDefault(); e.stopPropagation();
      input.press(btn.dataset.action);
      btn.classList.add('down');
    });
    const up = () => btn.classList.remove('down');
    btn.addEventListener('pointerup', up);
    btn.addEventListener('pointercancel', up);
    btn.addEventListener('pointerleave', up);
    btn.addEventListener('contextmenu', (e) => e.preventDefault());
  }
}
