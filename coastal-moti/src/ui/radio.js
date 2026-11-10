// Radio-dialogue overlay: one subtitle line + the speaker's callsign.
// Story rule: every line is at most 12 words. Longer lines are cut and reported in the console.
export const MAX_WORDS = 12;

export function createRadio(game) {
  const el = document.getElementById('radio');
  const who = document.getElementById('radio-callsign');
  const line = document.getElementById('radio-text');
  const queue = [];
  let busy = false, held = false, timer = 0;

  function pump() {
    if (busy || held || !queue.length) return;
    busy = true;
    const next = queue.shift();
    who.textContent = next.callsign;
    line.textContent = next.text;
    el.hidden = false;
    game.audio.play('radio');
    game.events.emit('radio', next);
    const words = next.text.split(/\s+/).length;
    timer = setTimeout(() => {
      el.hidden = true;
      busy = false;
      timer = setTimeout(pump, 250);
    }, 1500 + words * 330);
  }

  return {
    say(callsign, text) {
      const words = text.trim().split(/\s+/);
      if (words.length > MAX_WORDS) {
        console.warn(`Radio line is over ${MAX_WORDS} words and was cut: "${text}"`);
        text = words.slice(0, MAX_WORDS).join(' ');
      }
      queue.push({ callsign, text: text.trim() });
      pump();
    },
    hold(v) { held = v; if (!v) pump(); },
    clear() { queue.length = 0; clearTimeout(timer); busy = false; el.hidden = true; },
    get current() { return el.hidden ? null : { callsign: who.textContent, text: line.textContent }; },
  };
}
