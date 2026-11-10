// Shows which control scheme this device will use. The real controls arrive with gameplay.
export function showControlsHint(el, mobile) {
  el.textContent = mobile
    ? 'Touch: left joystick to move · right buttons: Attack, Shakti, Burst, Tool, Dodge'
    : 'Keyboard + mouse: WASD to move · mouse to look · 1-5 for Shaktis';
}
