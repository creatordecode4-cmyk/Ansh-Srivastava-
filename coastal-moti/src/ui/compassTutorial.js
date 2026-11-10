// Dadaji's brass compass. The player turns the case; the needle is dragged along, swings,
// and always settles on the same fixed direction (the island). Three settles finish the tutorial.
const NEED = 3;            // settles required
const MIN_TURN = 90;       // degrees the case must be turned before a settle counts
const SPRING = 42, DAMPING = 3.4;

const wrap = (d) => ((((d + 180) % 360) + 360) % 360) - 180;

export function createCompassTutorial(game) {
  const $ = (id) => document.getElementById(id);
  const el = $('compass-ui'), stage = $('cz-stage'), caseEl = $('cz-case'), needle = $('cz-needle');
  const mark = $('cz-mark'), pips = [...$('cz-pips').children], text = $('cz-text'), done = $('cz-done');

  // Draw the brass dial once: rim, tick marks and N / E / S / W.
  let dial = '<circle r="104" fill="#8a6a2a"/><circle r="96" fill="#d9b25a"/><circle r="84" fill="#f0deb0"/>';
  for (let a = 0; a < 360; a += 15) {
    const long = a % 90 === 0;
    dial += `<line x1="0" y1="-84" x2="0" y2="${long ? -68 : -76}" stroke="#5a431a" stroke-width="${long ? 3 : 1.5}" transform="rotate(${a})"/>`;
  }
  ['N', 'E', 'S', 'W'].forEach((l, i) => {
    dial += `<text y="-50" text-anchor="middle" font-size="17" font-weight="700" fill="#5a431a" transform="rotate(${i * 90})">${l}</text>`;
  });
  caseEl.innerHTML = dial;

  let resolve = null, raf = 0, last = 0;
  let fixed = 0;                 // screen angle the needle settles on (degrees, clockwise from up)
  let caseAngle = 0, needleAngle = 0, vel = 0;
  let turned = 0, settles = 0, dragging = false, dragLast = 0, keyDir = 0, sinceTurn = 1;

  const pointerAngle = (e) => {
    const r = stage.getBoundingClientRect();
    return Math.atan2(e.clientX - (r.left + r.width / 2), -(e.clientY - (r.top + r.height / 2))) * 180 / Math.PI;
  };
  function turn(delta) {
    caseAngle += delta;
    needleAngle += delta * 0.85; // the needle is dragged along with the case...
    turned += Math.abs(delta);
    if (delta) sinceTurn = 0;
  }
  stage.addEventListener('pointerdown', (e) => {
    dragging = true; dragLast = pointerAngle(e);
    try { stage.setPointerCapture(e.pointerId); } catch { /* synthetic */ }
  });
  stage.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const a = pointerAngle(e);
    turn(wrap(a - dragLast));
    dragLast = a;
  });
  const up = () => { dragging = false; };
  stage.addEventListener('pointerup', up);
  stage.addEventListener('pointercancel', up);
  const onKey = (e) => {
    if (el.hidden) return;
    const dir = (e.code === 'KeyD' || e.code === 'ArrowRight') ? 1 : (e.code === 'KeyA' || e.code === 'ArrowLeft') ? -1 : 0;
    if (dir) keyDir = e.type === 'keydown' ? dir : (keyDir === dir ? 0 : keyDir);
    if (e.type === 'keydown' && (e.code === 'Enter' || e.code === 'Space') && !done.hidden) finish();
  };
  window.addEventListener('keydown', onKey);
  window.addEventListener('keyup', onKey);
  done.addEventListener('click', () => finish());

  const LINES = [
    'Turn the compass. Watch the needle.',
    'It swings back. Turn it the other way.',
    'Same place again. Once more.',
    'It never points north. It always points out to sea.',
  ];

  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.1, (now - last) / 1000 || 0.016);
    last = now;
    if (keyDir) turn(keyDir * 150 * dt);
    // ...then a damped spring pulls it back to the island. While the case is still turning the pull
    // is weak, so the needle visibly goes along before it swings home.
    sinceTurn += dt;
    const pull = sinceTurn < 0.15 ? SPRING * 0.12 : SPRING;
    vel += (-pull * wrap(needleAngle - fixed) - DAMPING * vel) * dt;
    needleAngle += vel * dt;
    caseEl.style.transform = `rotate(${caseAngle}deg)`;
    needle.style.transform = `rotate(${needleAngle}deg)`;

    const still = Math.abs(wrap(needleAngle - fixed)) < 2.5 && Math.abs(vel) < 6;
    mark.classList.toggle('hit', still);
    if (still && !dragging && !keyDir && turned >= MIN_TURN && settles < NEED) {
      settles++; turned = 0;
      pips.forEach((p, i) => p.classList.toggle('on', i < settles));
      text.textContent = LINES[settles];
      game.audio.play(settles === NEED ? 'unlock' : 'objective');
      if (settles === NEED) { mark.classList.add('named'); done.hidden = false; }
    }
  }

  function finish() {
    if (!resolve) return;
    const r = resolve;
    close();
    r();
  }
  function close() {
    cancelAnimationFrame(raf);
    el.hidden = true;
    resolve = null; dragging = false; keyDir = 0;
  }

  // bearingDeg: where the island is, relative to where the camera looks (clockwise).
  function run(bearingDeg) {
    fixed = bearingDeg;
    caseAngle = 0; needleAngle = fixed + 140; vel = 0; turned = 0; settles = 0; // starts with a swing
    mark.style.transform = `rotate(${fixed}deg)`;
    mark.classList.remove('named', 'hit');
    pips.forEach((p) => p.classList.remove('on'));
    text.textContent = LINES[0];
    $('cz-hint').textContent = game.mobile ? 'Drag around the compass to turn it.' : 'Drag around the compass, or hold A / D.';
    done.hidden = true;
    el.hidden = false;
    last = performance.now();
    raf = requestAnimationFrame(frame);
    return new Promise((r) => { resolve = r; });
  }

  return { run, close, get open() { return !el.hidden; }, get settles() { return settles; }, get needle() { return wrap(needleAngle - fixed); } };
}
