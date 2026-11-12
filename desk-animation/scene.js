// Cozy desk — deterministic cinematic shot.
// Everything on screen is a pure function of t (seconds): call renderAt(t).
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export const W = 960, H = 540, FPS = 24, DURATION = 6;

// ---------- helpers ----------
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(1337);
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const lerp = (a, b, k) => a + (b - a) * k;
const ease = (a, b, x) => { x = clamp01((x - a) / (b - a)); return x * x * x * (x * (x * 6 - 15) + 10); };
const deg = (d) => (d * Math.PI) / 180;
const fract = (x) => x - Math.floor(x);

const matte = (color, roughness = 0.82, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness: 0, ...extra });

function shadowed(mesh) { mesh.castShadow = true; mesh.receiveShadow = true; return mesh; }
function rbox(w, h, d, r, material, seg = 5) {
  return shadowed(new THREE.Mesh(new RoundedBoxGeometry(w, h, d, seg, r), material));
}

// ---------- renderer ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.NoToneMapping; // tone mapping happens in the final pass

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x2a1a10);
const NEAR = 0.1, FAR = 30;
const camera = new THREE.PerspectiveCamera(32, W / H, NEAR, FAR);

// ---------- light ----------
const sunDir = new THREE.Vector3(2.5, -2.0, -0.7).normalize(); // direction the light travels
const sun = new THREE.DirectionalLight(0xffc48a, 4.2);
sun.position.copy(sunDir).multiplyScalar(-8);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -3.2, right: 3.2, top: 3.2, bottom: -3.2, near: 0.5, far: 16 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.006;
sun.shadow.radius = 2.5;
scene.add(sun, sun.target);

scene.add(new THREE.HemisphereLight(0xffe6c8, 0x8a5a3c, 1.25)); // soft ambient fill
const coolFill = new THREE.DirectionalLight(0x9db6d6, 0.35);    // faint cool kicker from the right
coolFill.position.set(2.5, 1.6, 2.2);
scene.add(coolFill);

// Window blinds: real slats far up the light path, so the stripes are true shadows.
{
  const blinds = new THREE.Group();
  blinds.position.copy(sunDir).multiplyScalar(-5);
  blinds.lookAt(0, 0, 0);
  const m = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const winW = 2.7, winH = 2.4, pitch = 0.06, slat = 0.033;
  for (let y = -winH / 2; y <= winH / 2; y += pitch) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(winW + 0.2, slat, 0.004), m);
    s.position.y = y; s.castShadow = true; blinds.add(s);
  }
  const bars = [
    [0.05, winH, 0, 0],                         // mullion
    [8, 6, 0, winH / 2 + 3], [8, 6, 0, -winH / 2 - 3],   // wall above / below window
    [6, 14, -winW / 2 - 3, 0], [6, 14, winW / 2 + 3, 0], // wall left / right
  ];
  for (const [w, h, x, y] of bars) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.004), m);
    b.position.set(x, y, 0); b.castShadow = true; blinds.add(b);
  }
  scene.add(blinds);
}

// ---------- room ----------
function woodTexture(base, dark, seed) {
  const r = mulberry32(seed);
  const c = document.createElement('canvas'); c.width = 1024; c.height = 512;
  const g = c.getContext('2d');
  g.fillStyle = base; g.fillRect(0, 0, 1024, 512);
  for (let i = 0; i < 900; i++) {
    const y = r() * 512, x = r() * 1024, len = 80 + r() * 500;
    g.globalAlpha = 0.03 + r() * 0.09;
    g.strokeStyle = r() > 0.35 ? dark : '#f3c68a';
    g.lineWidth = 0.6 + r() * 2.2;
    g.beginPath(); g.moveTo(x, y);
    g.bezierCurveTo(x + len * 0.3, y + (r() - 0.5) * 6, x + len * 0.7, y + (r() - 0.5) * 6, x + len, y + (r() - 0.5) * 4);
    g.stroke();
  }
  g.globalAlpha = 0.22; g.strokeStyle = dark; g.lineWidth = 2;
  for (const y of [128, 256, 384]) { g.beginPath(); g.moveTo(0, y); g.lineTo(1024, y); g.stroke(); }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}

const deskMat = matte(0xffffff, 0.62, { map: woodTexture('#c2925c', '#6b4220', 7) });
const desk = rbox(1.7, 0.06, 0.85, 0.022, deskMat);
desk.position.y = -0.03;
scene.add(desk);
const legMat = matte(0x7a4b26, 0.7);
for (const [x, z] of [[-0.77, -0.35], [0.77, -0.35], [-0.77, 0.35], [0.77, 0.35]]) {
  const leg = rbox(0.07, 0.72, 0.07, 0.016, legMat);
  leg.position.set(x, -0.42, z); scene.add(leg);
}
const apron = rbox(1.5, 0.08, 0.03, 0.01, legMat); apron.position.set(0, -0.1, 0.35); scene.add(apron);

const floorTex = woodTexture('#7b5233', '#3a2212', 21);
floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping; floorTex.repeat.set(5, 8);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), matte(0xffffff, 0.85, { map: floorTex }));
floor.rotation.x = -Math.PI / 2; floor.position.y = -0.78; floor.receiveShadow = true; scene.add(floor);
const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), matte(0xecd3b0, 0.95));
wall.position.set(0, 2.0, -0.48); wall.receiveShadow = true; scene.add(wall);
const skirting = rbox(14, 0.11, 0.025, 0.008, matte(0xf3e6d0, 0.8));
skirting.position.set(0, -0.725, -0.468); scene.add(skirting);

// ---------- retro computer ----------
const beige = matte(0xdcc9a3, 0.8), beigeDark = matte(0xb9a37c, 0.85), plasticDark = matte(0x3a3029, 0.7);
const screenCanvas = document.createElement('canvas'); screenCanvas.width = 512; screenCanvas.height = 384;
const screenTex = new THREE.CanvasTexture(screenCanvas);
screenTex.colorSpace = THREE.SRGBColorSpace;
const SCREEN_LINES = ['> HELLO, WORLD', '> RUN COFFEE.EXE', '  BREWING ########', '  GOLDEN HOUR: ON', '> READY'];
function drawScreen(t) {
  const g = screenCanvas.getContext('2d');
  const bg = g.createRadialGradient(256, 192, 30, 256, 192, 330);
  bg.addColorStop(0, '#0b3b3a'); bg.addColorStop(1, '#062423');
  g.fillStyle = bg; g.fillRect(0, 0, 512, 384);
  g.font = 'bold 34px monospace'; g.textBaseline = 'top';
  g.fillStyle = '#b8ffe0'; g.shadowColor = '#7dffd0'; g.shadowBlur = 10;
  let budget = Math.floor(18 + t * 11), last = [44, 44];
  SCREEN_LINES.forEach((line, i) => {
    if (budget <= 0) return;
    const s = line.slice(0, budget); budget -= line.length;
    g.fillText(s, 44, 44 + i * 58);
    last = [44 + g.measureText(s).width + 6, 44 + i * 58];
  });
  if (fract(t * 1.5) < 0.6) g.fillRect(last[0], last[1], 20, 32); // cursor
  g.shadowBlur = 0; g.fillStyle = 'rgba(0,0,0,0.16)';
  for (let y = 0; y < 384; y += 4) g.fillRect(0, y, 512, 1.5);     // scanlines
  screenTex.needsUpdate = true;
}
const computer = new THREE.Group();
{
  const base = rbox(0.44, 0.07, 0.36, 0.02, beige); base.position.y = 0.035;
  const mon = rbox(0.37, 0.3, 0.33, 0.04, beige); mon.position.y = 0.225;
  const bezel = rbox(0.31, 0.25, 0.03, 0.022, beigeDark); bezel.position.set(0, 0.228, 0.156);
  const sw = 0.25, sh = 0.19, sr = 0.028, shape = new THREE.Shape();
  shape.moveTo(-sw / 2 + sr, -sh / 2); shape.lineTo(sw / 2 - sr, -sh / 2);
  shape.quadraticCurveTo(sw / 2, -sh / 2, sw / 2, -sh / 2 + sr); shape.lineTo(sw / 2, sh / 2 - sr);
  shape.quadraticCurveTo(sw / 2, sh / 2, sw / 2 - sr, sh / 2); shape.lineTo(-sw / 2 + sr, sh / 2);
  shape.quadraticCurveTo(-sw / 2, sh / 2, -sw / 2, sh / 2 - sr); shape.lineTo(-sw / 2, -sh / 2 + sr);
  shape.quadraticCurveTo(-sw / 2, -sh / 2, -sw / 2 + sr, -sh / 2);
  screenTex.repeat.set(1 / sw, 1 / sh); screenTex.offset.set(0.5, 0.5);
  const screen = new THREE.Mesh(new THREE.ShapeGeometry(shape, 8),
    new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.35, emissive: 0xffffff, emissiveMap: screenTex, emissiveIntensity: 1.5 }));
  screen.position.set(0, 0.228, 0.1716); screen.receiveShadow = true;
  const slot = rbox(0.13, 0.009, 0.01, 0.003, plasticDark, 2); slot.position.set(0.1, 0.042, 0.178);
  const led = new THREE.Mesh(new THREE.SphereGeometry(0.0055, 16, 12),
    new THREE.MeshStandardMaterial({ color: 0x331500, emissive: 0xff8a2a, emissiveIntensity: 3 }));
  led.position.set(-0.17, 0.036, 0.18);
  const badge = rbox(0.034, 0.009, 0.004, 0.002, matte(0xd6603a, 0.6), 2); badge.position.set(-0.12, 0.118, 0.171);
  computer.add(base, mon, bezel, screen, slot, led, badge);
  for (let i = 0; i < 6; i++) { // top vents
    const v = rbox(0.2, 0.004, 0.012, 0.002, beigeDark, 1); v.position.set(0, 0.3755, -0.1 + i * 0.026); computer.add(v);
  }
  const glow = new THREE.PointLight(0x66ffd0, 0.012, 0.9, 2); glow.position.set(0, 0.22, 0.3); computer.add(glow);
}
computer.position.set(-0.22, 0, -0.14); computer.rotation.y = 0.2; scene.add(computer);

// keyboard
const keyboard = new THREE.Group();
{
  const body = rbox(0.42, 0.022, 0.15, 0.009, beige); body.position.y = 0.011; keyboard.add(body);
  const keyGeo = new RoundedBoxGeometry(0.022, 0.012, 0.022, 2, 0.004);
  const rows = 4, cols = 14;
  const keys = new THREE.InstancedMesh(keyGeo, matte(0xffffff, 0.75), rows * cols);
  const m4 = new THREE.Matrix4(), col = new THREE.Color();
  let n = 0;
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    if (r === 3 && c >= 4 && c <= 9) { m4.makeScale(0, 0, 0); keys.setMatrixAt(n, m4); keys.setColorAt(n++, col.set(0)); continue; }
    m4.makeTranslation(-0.1755 + c * 0.027, 0.026, -0.0405 + r * 0.027);
    keys.setMatrixAt(n, m4);
    const accent = c === 0 || c === cols - 1 || (r === 3 && (c < 2 || c > 11));
    keys.setColorAt(n++, col.set(accent ? 0x8d7b62 : (c === 13 && r === 1 ? 0xd6603a : 0xf1e6cd)));
  }
  keys.castShadow = keys.receiveShadow = true; keyboard.add(keys);
  const space = rbox(0.157, 0.012, 0.022, 0.004, matte(0xf1e6cd, 0.75), 2); space.position.set(0, 0.026, 0.0405); keyboard.add(space);
}
keyboard.position.set(-0.2, 0, 0.22); keyboard.rotation.set(0.06, 0.12, 0); scene.add(keyboard);
const mouse = rbox(0.055, 0.03, 0.085, 0.014, beige); mouse.position.set(0.1, 0.015, 0.24); mouse.rotation.y = -0.2; scene.add(mouse);
const mouseBtn = rbox(0.04, 0.006, 0.03, 0.003, beigeDark, 2); mouseBtn.position.set(0, 0.014, -0.022); mouse.add(mouseBtn);

// books
[[0xd9a441, 0.21, 0.04, 0.28, 0.08], [0xb5533c, 0.19, 0.032, 0.26, -0.12], [0x7f9a78, 0.17, 0.028, 0.24, 0.2]].reduce((y, [c, w, h, d, ry]) => {
  const b = rbox(w, h, d, 0.007, matte(c, 0.85)); b.position.set(-0.64, y + h / 2, -0.12); b.rotation.y = ry; scene.add(b);
  const pages = rbox(w - 0.012, h - 0.012, d - 0.004, 0.003, matte(0xf4ead6, 0.9), 1); pages.position.x = 0.008; b.add(pages);
  return y + h;
}, 0);

// ---------- mug ----------
const MUG = new THREE.Vector3(0.38, 0, 0.2), MUG_H = 0.092;
const mug = new THREE.Group();
{
  const R = 0.043, th = 0.005, Hm = MUG_H;
  const P = [[0, 0], [R - 0.009, 0], [R - 0.003, 0.002], [R, 0.009], [R, Hm - 0.004], [R - 0.0012, Hm - 0.001], [R - th / 2, Hm],
    [R - th + 0.0012, Hm - 0.001], [R - th, Hm - 0.004], [R - th, 0.013], [R - th - 0.005, 0.007], [0, 0.007]];
  const body = shadowed(new THREE.Mesh(new THREE.LatheGeometry(P.map(([x, y]) => new THREE.Vector2(x, y)), 64),
    matte(0x2c7a7b, 0.7, { side: THREE.DoubleSide })));
  const coffee = new THREE.Mesh(new THREE.CircleGeometry(R - th, 48), matte(0x3a2011, 0.22));
  coffee.rotation.x = -Math.PI / 2; coffee.position.y = Hm - 0.013; coffee.receiveShadow = true;
  const handle = shadowed(new THREE.Mesh(new THREE.TorusGeometry(0.025, 0.0075, 16, 32, Math.PI), body.material));
  handle.rotation.z = -Math.PI / 2; handle.position.set(R - 0.003, Hm * 0.5, 0);
  const coaster = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.058, 0.006, 48), matte(0xc9a06a, 0.95)));
  coaster.position.y = 0.003; // mug sits on the coaster
  mug.add(coaster, body, coffee, handle);
  body.position.y = 0.006; coffee.position.y += 0.006; handle.position.y = Hm * 0.5 + 0.006;
}
mug.position.copy(MUG); mug.rotation.y = -0.55; scene.add(mug);

// steam: analytic wisps (position/opacity are functions of t only)
const steamTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.4, 'rgba(255,255,255,0.45)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
})();
const steam = [], steamScene = new THREE.Scene(); // drawn after the DOF pass so it stays crisp
for (let w = 0; w < 3; w++) for (let k = 0; k < 30; k++) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: steamTex, color: 0xfff0dc, transparent: true, depthWrite: false, depthTest: false, opacity: 0 }));
  steam.push({ s, w, k }); steamScene.add(s);
}
function updateSteam(t) {
  for (const { s, w, k } of steam) {
    const u = fract(t * 0.2 + k / 30 + w * 0.137);
    const x = (w - 1) * 0.011 + Math.sin(u * 7 + w * 2.1 + t * 0.9) * 0.02 * u + u * u * 0.03;
    const z = Math.cos(u * 5 + w * 1.3 + t * 0.7) * 0.013 * u;
    s.position.set(MUG.x + x, MUG_H + u * 0.25, MUG.z + z);
    s.scale.setScalar(0.018 + u * 0.04);
    s.material.opacity = Math.sin(Math.PI * Math.pow(u, 0.55)) * 0.085;
  }
}

// ---------- plant ----------
const plant = new THREE.Group(); const leaves = [];
{
  const terracotta = matte(0xc2643c, 0.9, { side: THREE.DoubleSide });
  const P = [[0, 0], [0.05, 0], [0.056, 0.004], [0.069, 0.088], [0.074, 0.092], [0.075, 0.108], [0.071, 0.113], [0.064, 0.109], [0.062, 0.095], [0, 0.095]];
  const pot = shadowed(new THREE.Mesh(new THREE.LatheGeometry(P.map(([x, y]) => new THREE.Vector2(x, y)), 48), terracotta));
  pot.position.y = 0.008;
  const saucer = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.062, 0.01, 48), terracotta)); saucer.position.y = 0.005;
  const soil = new THREE.Mesh(new THREE.CircleGeometry(0.063, 32), matte(0x3b2617, 1)); soil.rotation.x = -Math.PI / 2; soil.position.y = 0.104;
  plant.add(pot, saucer, soil);
  const leafGeo = new THREE.SphereGeometry(1, 20, 14);
  const stemMat = matte(0x5d7a3a, 0.8), greens = [0x4f8a4b, 0x3f7a45, 0x6a9d52, 0x35683e];
  for (let i = 0; i < 13; i++) {
    const tilt = 0.12 + rand() * 0.85, len = 0.09 + rand() * 0.13, size = 0.7 + rand() * 0.6;
    const yaw = new THREE.Group(); yaw.position.y = 0.1; yaw.rotation.y = i * 2.39996;
    const lean = new THREE.Group(); yaw.add(lean);
    const stem = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.0022, 0.0032, len, 8), stemMat)); stem.position.y = len / 2;
    const bend = new THREE.Group(); bend.position.y = len; bend.rotation.z = -0.35 - rand() * 0.4;
    const leaf = shadowed(new THREE.Mesh(leafGeo, matte(greens[i % 4], 0.72)));
    leaf.scale.set(0.0035, 0.05 * size, 0.03 * size); leaf.position.y = 0.046 * size;
    bend.add(leaf); lean.add(stem, bend); plant.add(yaw);
    leaves.push({ lean, tilt, phase: rand() * 6.28 });
  }
}
plant.position.set(0.6, 0, -0.2); scene.add(plant);
function updatePlant(t) {
  for (const { lean, tilt, phase } of leaves) lean.rotation.z = -tilt + Math.sin(t * 1.4 + phase) * 0.018;
}

// ---------- camera: the shot list ----------
// 0-2s push-in toward the mug · 2-4s orbit left with a slight roll · 4-6s pull back to reveal the desk
const MUG_TARGET = new THREE.Vector3(MUG.x, 0.1, MUG.z);
const START_TARGET = new THREE.Vector3(0.2, 0.12, 0.08);
const DESK_TARGET = new THREE.Vector3(-0.03, 0.1, 0);
const target = new THREE.Vector3(), fwd = new THREE.Vector3();
function updateCamera(t) {
  const push = ease(0, 2.3, t), orbit = ease(1.7, 4.3, t), pull = ease(3.7, 6, t);
  const dist = lerp(1.2, 0.56, push) + pull * 1.9;
  const az = deg(16) - orbit * deg(40) + pull * deg(15);
  const el = deg(11) + push * deg(4) + pull * deg(9);
  const roll = ease(1.8, 3.5, t) * (1 - ease(3.8, 5.4, t)) * deg(-4.5);
  target.lerpVectors(START_TARGET, MUG_TARGET, push).lerp(DESK_TARGET, pull);
  camera.position.set(
    target.x + dist * Math.sin(az) * Math.cos(el),
    target.y + dist * Math.sin(el),
    target.z + dist * Math.cos(az) * Math.cos(el));
  camera.lookAt(target);
  camera.rotateZ(roll);
  camera.updateMatrixWorld();
  camera.getWorldDirection(fwd);
  const focus = MUG_TARGET.clone().sub(camera.position).dot(fwd); // keep the mug sharp
  return { focus, aperture: lerp(lerp(15, 26, push), 10, pull) };
}

// ---------- post: depth of field, grade, vignette, film grain ----------
const rtScene = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4, depthTexture: new THREE.DepthTexture(W, H) });
const rtDof = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType });
const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const quadGeo = new THREE.PlaneGeometry(2, 2);
const VERT = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
const dofMat = new THREE.ShaderMaterial({
  uniforms: { tColor: { value: rtScene.texture }, tDepth: { value: rtScene.depthTexture }, uFocus: { value: 1 }, uAperture: { value: 20 },
    uPx: { value: new THREE.Vector2(1 / W, 1 / H) }, uNear: { value: NEAR }, uFar: { value: FAR } },
  vertexShader: VERT,
  fragmentShader: `
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D tColor, tDepth;
    uniform float uFocus, uAperture, uNear, uFar;
    uniform vec2 uPx;
    const float MAX_BLUR = 13.0, RAD_SCALE = 0.55, GOLDEN = 2.39996323;
    float dist(vec2 uv){ float z = texture2D(tDepth, uv).x * 2.0 - 1.0; return 2.0 * uNear * uFar / (uFar + uNear - z * (uFar - uNear)); }
    float coc(float d){ return clamp(abs(d - uFocus) / d * uAperture, 0.0, MAX_BLUR); }
    void main(){
      float cd = dist(vUv), cs = coc(cd);
      vec3 col = texture2D(tColor, vUv).rgb; float tot = 1.0, radius = RAD_SCALE;
      for (int i = 0; i < 200; i++) {
        if (radius >= MAX_BLUR) break;
        float a = float(i) * GOLDEN;
        vec2 uv = vUv + vec2(cos(a), sin(a)) * uPx * radius;
        float sd = dist(uv), ss = coc(sd);
        if (sd > cd) ss = clamp(ss, 0.0, cs * 2.0);
        float m = smoothstep(radius - 0.5, radius + 0.5, ss);
        col += mix(col / tot, texture2D(tColor, uv).rgb, m); tot += 1.0;
        radius += RAD_SCALE / radius;
      }
      gl_FragColor = vec4(col / tot, 1.0);
    }`,
  depthTest: false, depthWrite: false,
});
const finalMat = new THREE.ShaderMaterial({
  uniforms: { tColor: { value: rtDof.texture }, uFrame: { value: 0 }, uExposure: { value: 1.0 } },
  vertexShader: VERT,
  fragmentShader: `
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D tColor; uniform float uFrame, uExposure;
    float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
    vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
    void main(){
      vec3 c = texture2D(tColor, vUv).rgb * uExposure;
      vec2 q = vUv - 0.5; c *= mix(1.0, 0.38, smoothstep(0.25, 0.95, length(q * vec2(1.0, 0.8)) * 1.5)); // vignette
      c = aces(c);
      c = pow(c, vec3(1.0 / 2.2));
      float l = dot(c, vec3(0.299, 0.587, 0.114));
      c = mix(c, c * vec3(1.05, 1.0, 0.92), 0.6);                       // golden-hour warmth
      c += vec3(0.02, 0.008, 0.0) * (1.0 - l);                          // lifted warm blacks
      c = mix(vec3(l), c, 0.96);
      vec2 p = gl_FragCoord.xy;
      float g = hash(p + uFrame * vec2(37.0, 17.0)) + hash(p * 1.37 + uFrame * vec2(11.0, 53.0) + 91.0) - 1.0;
      c += g * 0.05 * (1.0 - 0.55 * l);                                 // film grain, seeded per frame
      gl_FragColor = vec4(c, 1.0);
    }`,
  depthTest: false, depthWrite: false,
});
const dofScene = new THREE.Scene(); dofScene.add(new THREE.Mesh(quadGeo, dofMat));
const finalScene = new THREE.Scene(); finalScene.add(new THREE.Mesh(quadGeo, finalMat));

// ---------- the one entry point ----------
export function renderAt(t) {
  t = Math.min(Math.max(t, 0), DURATION);
  drawScreen(t); updateSteam(t); updatePlant(t);
  const { focus, aperture } = updateCamera(t);
  dofMat.uniforms.uFocus.value = focus;
  dofMat.uniforms.uAperture.value = aperture;
  finalMat.uniforms.uFrame.value = Math.round(t * FPS);
  renderer.setRenderTarget(rtScene); renderer.render(scene, camera);
  renderer.setRenderTarget(rtDof); renderer.render(dofScene, quadCam);
  renderer.autoClear = false; renderer.render(steamScene, camera); renderer.autoClear = true;
  renderer.setRenderTarget(null); renderer.render(finalScene, quadCam);
}

window.renderAt = renderAt;
window.SHOT = { W, H, FPS, DURATION };
renderAt(new URLSearchParams(location.search).get('t') * 1 || 0);
window.READY = true;
