// One input state for every device. Keyboard/mouse write into it here;
// the touch UI (src/ui/touchControls.js) writes into it through setMove / addLook / press.
//
// Actions (edge-triggered, read with take()):
//   attack, shakti, burst, tool, dodge, pause, lockLost, shakti1..shakti5

const KEY_ACTIONS = {
  Space: 'dodge', KeyQ: 'shakti', KeyF: 'burst', KeyE: 'tool', KeyJ: 'attack',
  Escape: 'pause', KeyP: 'pause',
  Digit1: 'shakti1', Digit2: 'shakti2', Digit3: 'shakti3', Digit4: 'shakti4', Digit5: 'shakti5',
};
const MOUSE_SENS = 0.0025; // radians per pixel
const MAX_MOUSE_STEP = 120; // pixels per mouse event

export function createInput(canvas) {
  const keys = new Set();
  const pressed = new Set();
  const touchMove = { x: 0, y: 0 };
  let lookX = 0, lookY = 0;
  let dragging = false, wasLocked = false, skipMove = false;

  const locked = () => document.pointerLockElement === canvas;

  window.addEventListener('keydown', (e) => {
    if (e.repeat) return;
    keys.add(e.code);
    const action = KEY_ACTIONS[e.code];
    if (action) pressed.add(action);
    if (action || e.code.startsWith('Arrow')) e.preventDefault();
  });
  window.addEventListener('keyup', (e) => keys.delete(e.code));
  window.addEventListener('blur', () => { keys.clear(); dragging = false; });

  canvas.addEventListener('mousedown', (e) => {
    if (locked()) {
      if (e.button === 0) pressed.add('attack');
      if (e.button === 2) pressed.add('shakti');
      return;
    }
    // First click captures the mouse. Until then (or if the browser refuses) hold-and-drag looks around.
    dragging = true;
    try { canvas.requestPointerLock?.()?.catch?.(() => {}); } catch { /* unsupported */ }
  });
  window.addEventListener('mouseup', () => { dragging = false; });
  window.addEventListener('mousemove', (e) => {
    if (!locked() && !dragging) return;
    if (skipMove) { skipMove = false; return; } // first event after capture can carry a bogus jump
    // Some browsers report one huge jump right after the mouse is captured: clamp it.
    lookX += Math.max(-MAX_MOUSE_STEP, Math.min(MAX_MOUSE_STEP, e.movementX)) * MOUSE_SENS;
    lookY += Math.max(-MAX_MOUSE_STEP, Math.min(MAX_MOUSE_STEP, e.movementY)) * MOUSE_SENS;
  });
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  document.addEventListener('pointerlockchange', () => {
    if (wasLocked && !locked()) pressed.add('lockLost'); // Esc released the mouse
    wasLocked = locked();
    if (wasLocked) skipMove = true;
  });

  return {
    // Movement on a unit disc: x = right, y = forward.
    move() {
      let x = touchMove.x, y = touchMove.y;
      if (keys.has('KeyD') || keys.has('ArrowRight')) x += 1;
      if (keys.has('KeyA') || keys.has('ArrowLeft')) x -= 1;
      if (keys.has('KeyW') || keys.has('ArrowUp')) y += 1;
      if (keys.has('KeyS') || keys.has('ArrowDown')) y -= 1;
      const len = Math.hypot(x, y);
      return len > 1 ? { x: x / len, y: y / len } : { x, y };
    },
    // PC: hold Shift. Touch: push the stick to its edge.
    run() {
      return keys.has('ShiftLeft') || keys.has('ShiftRight') || Math.hypot(touchMove.x, touchMove.y) > 0.85;
    },
    take(action) { return pressed.delete(action); },
    lookDelta() { const d = { x: lookX, y: lookY }; lookX = lookY = 0; return d; },
    endFrame() { pressed.clear(); },
    // --- used by the touch UI ---
    press(action) { pressed.add(action); },
    setMove(x, y) { touchMove.x = x; touchMove.y = y; },
    addLook(dx, dy) { lookX += dx; lookY += dy; },
    isLocked: locked,
    capturePointer() { try { canvas.requestPointerLock?.()?.catch?.(() => {}); } catch { /* ignore */ } },
    releasePointer() { if (locked()) document.exitPointerLock?.(); },
  };
}
