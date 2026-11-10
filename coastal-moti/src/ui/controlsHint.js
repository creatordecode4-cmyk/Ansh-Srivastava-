// A short reminder of the controls for this device. It fades out after a few seconds;
// the full list is in the pause menu.
export function showControlsHint(mobile) {
  const el = document.getElementById('hint');
  if (mobile) return; // the touch buttons are labelled already
  el.textContent = 'Click to capture the mouse · WASD move · Shift run · Space dodge · Click attack · Q Shakti · Esc pause';
  setTimeout(() => el.classList.add('gone'), 9000);
}
