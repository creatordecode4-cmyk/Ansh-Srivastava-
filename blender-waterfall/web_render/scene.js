// Waterfall Valley - deterministic Three.js renderer (frame-by-frame, for MP4 export).
// Geometry comes from build_waterfall_scene.py via export_scene.py (scene_data/).
// Blender coords (x, y, z) map to Three.js (x, z, -y).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const Q = new URLSearchParams(location.search);
const W = +(Q.get('w') || 1920), H = +(Q.get('h') || 1080);
const FPS = 24, FRAMES = 480;
const B = (x, y, z) => new THREE.Vector3(x, z, -y);           // blender -> three

// ------------------------------------------------------------------ seeded random
let _s = 1234567;
const rnd = () => ((_s = (_s * 1664525 + 1013904223) >>> 0) / 4294967296);
const rr = (a, b) => a + (b - a) * rnd();

// ------------------------------------------------------------------ renderer / scene
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = +(Q.get('exp') || 1.0);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const FOG_COLOR = new THREE.Color(0.50, 0.66, 0.86);
scene.fog = new THREE.FogExp2(FOG_COLOR, 0.0011);
const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 6000);
camera.filmGauge = 36;
camera.setFocalLength(24);

const U = { time: { value: 0 } };
// Visible sun (art-directed, top-right behind the leaves) and the key light that shapes the valley.
const SUN_VIS = (() => { const az = THREE.MathUtils.degToRad(20), el = THREE.MathUtils.degToRad(23);
  return B(Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el)).normalize(); })();
const KEY_DIR = B(0.45, -0.30, 0.84).normalize();

const M = await (await fetch('scene_data/manifest.json')).json();
if (M.mirror) { SUN_VIS.x *= -1; KEY_DIR.x *= -1; }

// ------------------------------------------------------------------ GLSL helpers
const NOISE = `
float hash13(vec3 p){ p = fract(p*0.3183099 + 0.1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float noise3(vec3 x){ vec3 i = floor(x); vec3 f = fract(x); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash13(i), hash13(i+vec3(1,0,0)), f.x), mix(hash13(i+vec3(0,1,0)), hash13(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash13(i+vec3(0,0,1)), hash13(i+vec3(1,0,1)), f.x), mix(hash13(i+vec3(0,1,1)), hash13(i+vec3(1,1,1)), f.x), f.y), f.z); }
float fbm3(vec3 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++){ s += a*noise3(p); p = p*2.03 + 7.1; a *= 0.5; } return s; }
float fbm2(vec2 p){ return fbm3(vec3(p, 0.37)); }
`;
const SKY = `
uniform vec3 uSunVis;
vec3 skyCol(vec3 d){
  float y = max(d.y, 0.0);
  vec3 c = mix(vec3(0.36, 0.58, 0.92), vec3(0.015, 0.11, 0.52), pow(y, 0.4));
  float s = max(dot(d, uSunVis), 0.0);
  c += vec3(1.0, 0.80, 0.50) * (pow(s, 6.0) * 0.55 + pow(s, 60.0) * 1.4);
  return c;
}`;

// Standard material + world-space colour variation, procedural bump, optional wind sway.
function detailMat({ rough = 0.9, colFreq = 0.5, colAmt = 0.15, bumpFreq = 1.0, bumpAmp = 0.1, fadeFar = 160,
                     side = THREE.FrontSide, sway = 0, color = null, vertexColors = true } = {}) {
  const m = new THREE.MeshStandardMaterial({ vertexColors, roughness: rough, metalness: 0, side });
  if (color) m.color = color;
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = U.time;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWP;\nuniform float uTime;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        ${sway ? `{ vec3 op = vec3(modelMatrix[3][0], 0.0, modelMatrix[3][2]);
          float k = position.y * position.y;
          transformed.x += (sin(uTime*0.9 + op.x*0.21 + op.z*0.13) * 0.6 + sin(uTime*2.1 + op.x) * 0.25) * ${sway.toFixed(4)} * k;
          transformed.z += sin(uTime*0.7 + op.z*0.17) * ${(sway * 0.6).toFixed(4)} * k; }` : ''}`)
      .replace('#include <project_vertex>', '#include <project_vertex>\nvWP = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vWP;\n${NOISE}`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        { float dn = fbm3(vWP * ${colFreq.toFixed(4)}); diffuseColor.rgb *= (1.0 - ${colAmt.toFixed(3)}) + ${(2 * colAmt).toFixed(3)} * dn * 1.06; }`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        { float fade = smoothstep(${fadeFar.toFixed(1)}, ${(fadeFar * 0.25).toFixed(1)}, length(vViewPosition));
          float bh = fbm3(vWP * ${bumpFreq.toFixed(4)}) * ${bumpAmp.toFixed(4)} * fade;
          vec3 dpdx = dFdx(-vViewPosition), dpdy = dFdy(-vViewPosition);
          vec3 r1 = cross(dpdy, normal), r2 = cross(normal, dpdx);
          float det = dot(dpdx, r1);
          vec3 grad = sign(det) * (dFdx(bh) * r1 + dFdy(bh) * r2);
          normal = normalize(abs(det) * normal - grad); }`);
  };
  return m;
}

// ------------------------------------------------------------------ load exported geometry
async function loadGroup(name) {
  const g = M.groups[name];
  const get = async (fn) => (await fetch('scene_data/' + fn)).arrayBuffer();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(await get(g.position)), 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(await get(g.normal)), 3));
  geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(await get(g.color)), 3));
  if (g.uv) geo.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(await get(g.uv)), 2));
  geo.setIndex(new THREE.BufferAttribute(new Uint32Array(await get(g.index)), 1));
  return geo;
}

const terrainGeo = await loadGroup('terrain');
const terrain = new THREE.Mesh(terrainGeo, detailMat({ rough: 0.95, colFreq: 0.25, colAmt: 0.18, bumpFreq: 1.6, bumpAmp: 0.06, fadeFar: 80 }));
terrain.receiveShadow = true;
scene.add(terrain);

const mountains = new THREE.Mesh(await loadGroup('mountains'),
  detailMat({ rough: 0.95, colFreq: 0.03, colAmt: 0.2, bumpFreq: 0.06, bumpAmp: 6.0, fadeFar: 5000 }));
scene.add(mountains);

const cliffs = new THREE.Mesh(await loadGroup('cliffs'),
  detailMat({ rough: 0.88, colFreq: 0.35, colAmt: 0.2, bumpFreq: 0.7, bumpAmp: 0.55, fadeFar: 260, side: THREE.DoubleSide }));
cliffs.castShadow = true; cliffs.receiveShadow = true;
scene.add(cliffs);

const rocks = new THREE.Mesh(await loadGroup('rocks'),
  detailMat({ rough: 0.8, colFreq: 1.5, colAmt: 0.15, bumpFreq: 2.2, bumpAmp: 0.07, fadeFar: 90 }));
rocks.castShadow = true; rocks.receiveShadow = true;
scene.add(rocks);

// terrain height sampler (regular grid, column-major: index = ix*ny + iy)
const TG = M.terrainGrid, TP = terrainGeo.attributes.position.array;
function groundH(bx, by) {
  const fx = (bx - TG.x0) / TG.step, fy = (by - TG.y0) / TG.step;
  const ix = Math.max(0, Math.min(TG.nx - 2, Math.floor(fx))), iy = Math.max(0, Math.min(TG.ny - 2, Math.floor(fy)));
  const tx = fx - ix, ty = fy - iy;
  const h = (i, j) => TP[(i * TG.ny + j) * 3 + 1];
  return (h(ix, iy) * (1 - tx) + h(ix + 1, iy) * tx) * (1 - ty) + (h(ix, iy + 1) * (1 - tx) + h(ix + 1, iy + 1) * tx) * ty;
}
function riverInfo(x, y) {
  let bd = 1e9, bw = 13;
  for (let i = 0; i < M.river.length - 1; i++) {
    const [ax, ay] = M.river[i], [bx, by] = M.river[i + 1];
    const dx = bx - ax, dy = by - ay;
    const s = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
    const d = Math.hypot(x - ax - dx * s, y - ay - dy * s);
    if (d < bd) { bd = d; bw = M.riverHalfW[i] + (M.riverHalfW[i + 1] - M.riverHalfW[i]) * s; }
  }
  return [bd, bw];
}

// ------------------------------------------------------------------ lights + sky
const hemi = new THREE.HemisphereLight(new THREE.Color(0.62, 0.76, 1.0), new THREE.Color(0.32, 0.36, 0.18), 1.15);
scene.add(hemi);
const key = new THREE.DirectionalLight(new THREE.Color(1.0, 0.86, 0.66), 3.4);
const keyTarget = B(5, 50, 0);
key.position.copy(keyTarget).addScaledVector(KEY_DIR, 300);
key.target.position.copy(keyTarget);
key.castShadow = true;
key.shadow.mapSize.set(4096, 4096);
Object.assign(key.shadow.camera, { left: -130, right: 130, top: 130, bottom: -130, near: 10, far: 700 });
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.05;
scene.add(key, key.target);

const skyMat = new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { uSunVis: { value: SUN_VIS }, uTime: U.time },
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize((modelMatrix*vec4(position,1.0)).xyz - cameraPosition);
    gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_Position.z = gl_Position.w; }`,
  fragmentShader: `${NOISE}${SKY}
    uniform float uTime; varying vec3 vDir;
    void main(){
      vec3 d = normalize(vDir);
      vec3 c = skyCol(d);
      if (d.y > 0.0) {                                  // a few soft clouds
        vec2 cp = d.xz / (d.y + 0.12) * 1.6 + vec2(uTime * 0.012, 0.0);
        float cl = smoothstep(0.56, 0.78, fbm2(cp * 0.9 + 3.0)) * smoothstep(0.02, 0.3, d.y);
        float lit = 0.75 + 0.5 * fbm2(cp * 2.0);
        c = mix(c, vec3(1.0, 0.96, 0.9) * 1.25 * lit, cl * 0.8);
      }
      float s = max(dot(d, uSunVis), 0.0);
      c += vec3(60.0, 52.0, 40.0) * smoothstep(0.99975, 0.99988, s) + vec3(3.0, 2.4, 1.6) * pow(s, 900.0);
      gl_FragColor = vec4(c, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(3000, 48, 24), skyMat);
sky.frustumCulled = false;
sky.renderOrder = -1;
scene.add(sky);

// ------------------------------------------------------------------ water
const riverPts = M.river.map(([x, y]) => new THREE.Vector2(x, -y));
const rocksU = [];
for (let i = 0; i < 48; i++) {
  const r = M.rocksInWater[i];
  rocksU.push(r ? new THREE.Vector3(r[0], -r[1], r[2]) : new THREE.Vector3(9999, 9999, 0));
}
const waterMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false,
  uniforms: {
    uTime: U.time, uSunVis: { value: SUN_VIS }, uKey: { value: KEY_DIR },
    uRiver: { value: riverPts }, uHalfW: { value: M.riverHalfW }, uRocks: { value: rocksU },
    uPool: { value: new THREE.Vector3(M.pool[0], -M.pool[1], M.pool[2]) },
    uFall: { value: new THREE.Vector2(M.fallBottom[0], -M.fallBottom[1]) },
    uFogColor: { value: FOG_COLOR }, uFogDensity: { value: 0.0011 },
  },
  vertexShader: `varying vec3 vW; void main(){ vW = (modelMatrix*vec4(position,1.0)).xyz; gl_Position = projectionMatrix*viewMatrix*vec4(vW,1.0); }`,
  fragmentShader: `${NOISE}${SKY}
    uniform float uTime; uniform vec3 uKey; uniform vec2 uRiver[7]; uniform float uHalfW[7]; uniform vec3 uRocks[48];
    uniform vec3 uPool; uniform vec2 uFall; uniform vec3 uFogColor; uniform float uFogDensity;
    varying vec3 vW;
    float waves(vec2 p, vec2 flow, float t){
      float ph0 = fract(t * 0.2), ph1 = fract(t * 0.2 + 0.5);
      float w0 = 1.0 - abs(2.0 * ph0 - 1.0);
      vec2 o0 = flow * ph0 * 5.0, o1 = flow * ph1 * 5.0;
      float a = 0.6 * fbm2((p - o0) * 0.45) + 0.3 * fbm2((p - o0 * 1.8) * 1.6 + 5.0);
      float b = 0.6 * fbm2((p - o1) * 0.45 + 11.0) + 0.3 * fbm2((p - o1 * 1.8) * 1.6 + 17.0);
      return mix(b, a, w0);
    }
    void main(){
      vec2 p = vW.xz;
      float bd = 1e9; float bw = 12.0; vec2 flow = vec2(0.0, 1.0);
      for (int i = 0; i < 6; i++){
        vec2 a = uRiver[i], b = uRiver[i+1], ab = b - a;
        float s = clamp(dot(p - a, ab) / dot(ab, ab), 0.0, 1.0);
        float d = length(p - a - ab * s);
        if (d < bd){ bd = d; bw = mix(uHalfW[i], uHalfW[i+1], s); flow = normalize(ab); }
      }
      float t = uTime;
      float e = 0.15;
      float h0 = waves(p, flow, t), hx = waves(p + vec2(e, 0.0), flow, t), hz = waves(p + vec2(0.0, e), flow, t);
      vec3 n = normalize(vec3(-(hx - h0) / e * 0.55, 1.0, -(hz - h0) / e * 0.55));
      vec3 V = normalize(cameraPosition - vW);
      float fres = 0.02 + 0.98 * pow(1.0 - max(dot(n, V), 0.0), 5.0);
      vec3 R = reflect(-V, n); R.y = abs(R.y);
      float pd = length(p - uPool.xy);
      float depth = clamp(1.0 - bd / bw, 0.0, 1.0);
      depth = max(depth, smoothstep(uPool.z, uPool.z * 0.3, pd));
      vec3 shallow = vec3(0.04, 0.58, 0.52), deep = vec3(0.0, 0.20, 0.27);
      vec3 col = mix(shallow, deep, depth) * (0.75 + 0.5 * max(dot(n, uKey), 0.0));
      col = mix(col, skyCol(R), fres * 0.6);
      col += vec3(1.0, 0.85, 0.6) * (pow(max(dot(R, uKey), 0.0), 220.0) * 4.0 + pow(max(dot(R, uSunVis), 0.0), 120.0) * 3.0);
      float foam = 0.0;
      for (int i = 0; i < 48; i++){
        float d = length(p - uRocks[i].xy) - uRocks[i].z * 0.9;
        foam += smoothstep(1.3, 0.0, d) * (0.45 + 0.55 * noise3(vec3((p - flow * t * 1.5) * 2.2, t * 0.7)));
      }
      float fd = length(p - uFall);
      foam += smoothstep(9.0, 1.5, fd) * (0.5 + 0.5 * noise3(vec3(p * 1.4, t * 1.3)));
      foam += smoothstep(0.88, 1.0, 1.0 - depth) * 0.35 * noise3(vec3((p - flow * t) * 1.5, t));
      foam = clamp(foam * smoothstep(0.35, 0.65, noise3(vec3((p - flow * t * 1.2) * 3.5, t * 0.5)) + 0.25), 0.0, 1.0);
      col = mix(col, vec3(0.95, 0.97, 1.0) * (0.85 + 0.3 * max(dot(n, uKey), 0.0)), foam * 0.9);
      float alpha = mix(0.55, 0.93, depth);
      alpha = max(alpha, max(fres, foam));
      float dist = length(cameraPosition - vW);
      float fogF = 1.0 - exp(-pow(uFogDensity * dist, 2.0));
      col = mix(col, uFogColor, fogF);
      gl_FragColor = vec4(col, alpha);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
});
const water = new THREE.Mesh(new THREE.PlaneGeometry(100, 140).rotateX(-Math.PI / 2), waterMat);
water.position.set(5, 0.0, -37.5);
water.renderOrder = 1;
scene.add(water);

// ------------------------------------------------------------------ waterfall: layered falling sheets, droplets, splash, mist
// Exported fall normals point AWAY from the camera, so "outward" = -normal.
const KEY_U = { value: KEY_DIR };
function fallMat(speed, layer) {        // layer 0 = darker body behind, 1 = white aerated streams in front
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
    uniforms: { uTime: U.time, uKey: KEY_U, uFogColor: { value: FOG_COLOR }, uFogDensity: { value: 0.0011 } },
    vertexShader: `varying vec2 vUv; varying vec3 vW; varying vec3 vN;
      void main(){ vUv = uv; vec3 p = position + normal * ${layer === 0 ? '0.45' : '-0.05'};
        vW = (modelMatrix * vec4(p, 1.0)).xyz; vN = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0); }`,
    fragmentShader: `${NOISE}
      uniform float uTime; uniform vec3 uKey; uniform vec3 uFogColor; uniform float uFogDensity;
      varying vec2 vUv; varying vec3 vW; varying vec3 vN;
      void main(){
        float t = uTime * ${speed.toFixed(3)};
        float v = vUv.y, sv = sqrt(max(v, 0.0));          // sqrt-space scroll = accelerating fall (gravity)
        float y1 = sv * 7.0 - t * 2.4;
        float y2 = sv * 16.0 - t * 5.4;
        float n1 = noise3(vec3(vUv.x * 46.0, y1, 0.0));
        float n2 = noise3(vec3(vUv.x * 110.0, y2, 3.0));
        float cl = fbm3(vec3(vUv.x * 9.0, sv * 4.0 - t * 1.55, 7.0));
        float streak = 0.45 * n1 + 0.3 * n2 + 0.55 * cl;
        float aer = smoothstep(0.02, 0.3, v);
        float ex = min(vUv.x, 1.0 - vUv.x);
        float edge = smoothstep(0.0, 0.10 + 0.10 * noise3(vec3(vUv.x * 7.0, y1 * 0.6, 2.0)), ex);
        float a; vec3 c;
        if (${layer} == 0) {
          a = edge * clamp(0.38 + 0.4 * streak + 0.2 * v, 0.0, 0.85);
          c = mix(vec3(0.26, 0.38, 0.39), vec3(0.78, 0.84, 0.85), aer * (0.45 + 0.55 * streak));
        } else {
          float s = streak + 0.22 * (1.0 - aer);
          a = edge * smoothstep(0.42, 0.62, s) * (0.6 + 0.4 * aer);
          c = mix(vec3(0.58, 0.73, 0.72), vec3(1.0, 1.0, 0.98), aer) * (0.85 + 0.35 * n2);
        }
        a *= smoothstep(0.0, 0.025, v);
        a = mix(a, a * 0.7, smoothstep(0.85, 1.0, v));
        c *= (0.78 + 0.32 * abs(dot(normalize(vN), uKey))) * 1.15;
        c += vec3(0.45, 0.5, 0.45) * smoothstep(0.08, 0.0, v) * n1;     // glassy lip where it pours over
        float dist = length(cameraPosition - vW);
        c = mix(c, uFogColor, 1.0 - exp(-pow(uFogDensity * dist, 2.0)));
        gl_FragColor = vec4(c, a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}
const fallGeoMain = await loadGroup('waterfall_main'), fallGeoStrand = await loadGroup('waterfall_strand');
for (const [geo, sp] of [[fallGeoMain, 1.0], [fallGeoStrand, 1.15]]) {
  const back = new THREE.Mesh(geo, fallMat(sp, 0));
  const front = new THREE.Mesh(geo, fallMat(sp * 1.1, 1));
  back.renderOrder = 2; front.renderOrder = 3;
  scene.add(back, front);
}

function fallGrid(geo, cols) {
  const P = geo.attributes.position.array, N = geo.attributes.normal.array;
  return { cols, rows: P.length / 3 / (cols + 1), P, N };
}
function sampleFall(F, u, v, oP, oN) {
  const fx = u * F.cols, i0 = Math.min(F.cols - 1, Math.floor(fx)), tx = fx - i0;
  const fy = v * (F.rows - 1), j0 = Math.min(F.rows - 2, Math.floor(fy)), ty = fy - j0;
  for (let k = 0; k < 3; k++) {
    const g = (A, i, j) => A[(i * F.rows + j) * 3 + k];
    const bil = (A) => (g(A, i0, j0) * (1 - tx) + g(A, i0 + 1, j0) * tx) * (1 - ty) + (g(A, i0, j0 + 1) * (1 - tx) + g(A, i0 + 1, j0 + 1) * tx) * ty;
    oP[k] = bil(F.P); oN[k] = -bil(F.N);
  }
}
const FALLS = [fallGrid(fallGeoMain, 24), fallGrid(fallGeoStrand, 6)];
const particleSystems = [];
function makeParticles(n, round, init) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(n * 3), al = new Float32Array(n), sz = new Float32Array(n);
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('aAlpha', new THREE.BufferAttribute(al, 1));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sz, 1));
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, uniforms: { uH: { value: H } },
    vertexShader: `attribute float aAlpha; attribute float aSize; uniform float uH; varying float vA;
      void main(){ vA = aAlpha; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = clamp(aSize * uH * 0.6 / -mv.z, 1.5, 72.0); }`,
    fragmentShader: `varying float vA;
      void main(){ vec2 c = gl_PointCoord - 0.5;
        float streak = exp(-c.x * c.x * 90.0) * smoothstep(0.5, 0.1, abs(c.y));
        float drop = smoothstep(0.5, 0.15, length(c));
        float a = vA * ${round ? 'drop' : 'streak'};
        gl_FragColor = vec4(vec3(1.0, 1.0, 0.98) * 1.35, a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false; pts.renderOrder = 4;
  scene.add(pts);
  const sys = { n, pos, al, sz, geo, seeds: [] };
  for (let i = 0; i < n; i++) sys.seeds.push(init(i));
  particleSystems.push(sys);
  return sys;
}
// falling droplets / spray streaks riding on the curtain (distance ~ t^2)
const dropsMain = makeParticles(2600, false, () => [0, rr(0.03, 0.97), rnd(), 0.42 * rr(0.85, 1.2), rnd()]);
const dropsStrand = makeParticles(450, false, () => [1, rr(0.05, 0.95), rnd(), 0.46 * rr(0.85, 1.2), rnd()]);
// splash droplets thrown up at the base (ballistic)
const splash = makeParticles(1200, true, () => [rnd() < 0.85 ? 0 : 1, rr(0.05, 0.95), rnd(), rr(0.9, 1.4), rr(1.0, 4.5), rr(-2.0, 2.0), rr(2.0, 5.5)]);
const _p = [0, 0, 0], _n = [0, 0, 0];
function updateFallParticles(t) {
  for (const sys of [dropsMain, dropsStrand]) {
    for (let i = 0; i < sys.n; i++) {
      const [fi, u, ph, rate, out] = sys.seeds[i];
      const life = (ph + t * rate) % 1, v = life * life;
      sampleFall(FALLS[fi], u, v, _p, _n);
      const o = 0.15 + out * 0.5 + v * 0.7;
      sys.pos.set([_p[0] + _n[0] * o, _p[1] + _n[1] * o + (out - 0.5) * 0.2, _p[2] + _n[2] * o], i * 3);
      sys.al[i] = Math.min(1, life * 10) * (1 - Math.max(0, (v - 0.86) / 0.14)) * 0.42;
      sys.sz[i] = 0.7 * (0.5 + 2.0 * v);
    }
  }
  for (let i = 0; i < splash.n; i++) {
    const [fi, u, ph, rate, vOut, vLat, vUp] = splash.seeds[i];
    sampleFall(FALLS[fi], u, 0.985, _p, _n);
    const nx = _n[0], nz = _n[2], ln = Math.hypot(nx, nz) || 1;
    const ox = nx / ln, oz = nz / ln, lx = -oz, lz = ox;
    const tau = ((ph + t * rate) % 1) * 1.1;
    const y = _p[1] + vUp * tau - 4.9 * tau * tau;
    splash.pos.set([_p[0] + (ox * vOut + lx * vLat) * tau, y, _p[2] + (oz * vOut + lz * vLat) * tau], i * 3);
    splash.al[i] = y > -0.05 ? (1 - tau / 1.1) * 0.45 : 0;
    splash.sz[i] = 0.45;
  }
  for (const sys of particleSystems) {
    sys.geo.attributes.position.needsUpdate = true;
    sys.geo.attributes.aAlpha.needsUpdate = true;
    sys.geo.attributes.aSize.needsUpdate = true;
  }
}

{ // mist billowing from the base of the falls
  const N = 900, geo = new THREE.BufferGeometry();
  const pos = new Float32Array(N * 3), seed = new Float32Array(N * 4);
  for (let i = 0; i < N; i++) {
    seed.set([rnd(), rnd() * Math.PI * 2, rr(0.6, 1.4), rr(2.5, 8)], i * 4);
    pos.set([0, rnd(), 0], i * 3);
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
  const fb = M.fallBottom, ft = M.fallTop;
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { uTime: U.time, uO: { value: B(fb[0], fb[1], fb[2] + 0.5) }, uTop: { value: ft[2] }, uH: { value: H } },
    vertexShader: `attribute vec4 aSeed; uniform float uTime; uniform vec3 uO; uniform float uTop; uniform float uH; varying float vA;
      void main(){
        float life = fract(uTime * aSeed.z * 0.07 + aSeed.x);
        vec3 dir = vec3(cos(aSeed.y), 0.0, sin(aSeed.y));
        float up = position.y < 0.3 ? position.y * uTop * 0.8 : 0.0;
        vec3 p = uO + dir * vec3(1.0 + life * 6.0, 0.0, 1.0 + life * 3.0) + vec3(0.0, up * 0.6 + life * 3.5, 0.0) + vec3(0.0, 0.0, 1.5);
        vA = sin(life * 3.14159) * (position.y < 0.3 ? 0.6 : 1.0);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = min(aSeed.w * (1.0 + life) * uH * 0.6 / -mv.z, 480.0);
      }`,
    fragmentShader: `varying float vA;
      void main(){ float r = length(gl_PointCoord - 0.5); float a = vA * 0.028 * (1.0 - smoothstep(0.0, 0.5, r));
        gl_FragColor = vec4(vec3(1.0, 0.98, 0.95) * 2.2, a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const mist = new THREE.Points(geo, mat);
  mist.frustumCulled = false;
  mist.renderOrder = 5;
  scene.add(mist);
}

// ------------------------------------------------------------------ leaf texture
function leafTexture() {
  const c = document.createElement('canvas'); c.width = 64; c.height = 192;
  const g = c.getContext('2d');
  g.translate(32, 0);
  const path = new Path2D();
  path.moveTo(0, 4); path.bezierCurveTo(26, 40, 22, 130, 0, 188); path.bezierCurveTo(-22, 130, -26, 40, 0, 4);
  const gr = g.createLinearGradient(0, 0, 0, 192);
  gr.addColorStop(0, '#d9e8c0'); gr.addColorStop(1, '#ffffff');
  g.fillStyle = gr; g.fill(path);
  g.strokeStyle = 'rgba(90,110,60,0.55)'; g.lineWidth = 2.2;
  g.beginPath(); g.moveTo(0, 6); g.lineTo(0, 184); g.stroke();
  g.lineWidth = 1.1;
  for (let y = 26; y < 170; y += 16) { g.beginPath(); g.moveTo(0, y); g.lineTo(15, y + 12); g.moveTo(0, y); g.lineTo(-15, y + 12); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}
const LEAF_TEX = leafTexture();

// Leaf material: translucent backlit glow toward the visible sun + per-instance wind sway.
function leafMat({ glow = 1.4, rough = 0.4, map = LEAF_TEX, alphaTest = 0.5 } = {}) {
  const m = new THREE.MeshStandardMaterial({ map, alphaTest, side: THREE.DoubleSide, roughness: rough, metalness: 0 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = U.time; sh.uniforms.uSunVis = { value: SUN_VIS };
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec2 aSway; uniform float uTime; varying vec3 vWP2;')
      .replace('#include <project_vertex>', `
        vec4 mvPosition = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
          mvPosition = instanceMatrix * mvPosition;
        #endif
        float ph = aSway.x;
        mvPosition.x += aSway.y * (sin(uTime * 1.05 + ph) * 0.6 + sin(uTime * 2.6 + ph * 1.7) * 0.22);
        mvPosition.z += aSway.y * sin(uTime * 0.85 + ph * 0.7) * 0.45;
        mvPosition.y += sin(uTime * 7.0 + ph * 5.0) * 0.015 * (transformed.y);
        vWP2 = (modelMatrix * mvPosition).xyz;
        mvPosition = modelViewMatrix * mvPosition;
        gl_Position = projectionMatrix * mvPosition;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform vec3 uSunVis; varying vec3 vWP2;')
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        { vec3 vd = normalize(vWP2 - cameraPosition);
          float back = pow(max(dot(vd, uSunVis), 0.0), 4.0);
          totalEmissiveRadiance += diffuseColor.rgb * vec3(1.0, 0.92, 0.55) * (0.18 + ${glow.toFixed(2)} * back); }`);
  };
  return m;
}

function leafMesh(count, w, h, mat) {
  const geo = new THREE.PlaneGeometry(w, h);
  geo.translate(0, -h / 2, 0);                         // stem at the origin, blade hangs along -Y
  const sway = new Float32Array(count * 2);
  geo.setAttribute('aSway', new THREE.InstancedBufferAttribute(sway, 2));
  const im = new THREE.InstancedMesh(geo, mat, count);
  im.frustumCulled = false;
  return { im, sway };
}

// ------------------------------------------------------------------ foreground weeping tree (top-right)
const LEAF_FRESH = new THREE.Color('#B5D334'), LEAF_DEEP = new THREE.Color('#4C8C2B');
{
  const bx = M.mirror ? -19 : 19, side = M.mirror ? -1 : 1;
  const g0 = groundH(bx, 20);
  const barkMat = detailMat({ vertexColors: false, color: new THREE.Color(0.30, 0.25, 0.19), rough: 0.9, colFreq: 3, colAmt: 0.25, bumpFreq: 5, bumpAmp: 0.03 });
  const trunkCurve = new THREE.CatmullRomCurve3([B(bx, 20, g0 - 0.5), B(bx - 0.5 * side, 20.4, g0 + 4), B(bx - 2 * side, 21, g0 + 8), B(bx - 4 * side, 21.5, g0 + 11)]);
  const trunk = new THREE.Mesh(new THREE.TubeGeometry(trunkCurve, 24, 0.38, 8), barkMat);
  trunk.castShadow = true;
  scene.add(trunk);

  const strands = [];          // [anchor Vector3, length]
  const branchLeafPts = [];
  const nBranch = 11;
  for (let b = 0; b < nBranch; b++) {
    const s = trunkCurve.getPoint(rr(0.55, 1.0));
    const ang = rr(-0.9, 1.0);                       // spread mostly toward the river / sky
    const len = rr(4.5, 8.0);
    const dir = new THREE.Vector3(-Math.cos(ang) * side, 0, -Math.sin(ang) * 0.9).normalize();
    const p1 = s.clone().addScaledVector(dir, len * 0.4).add(new THREE.Vector3(0, rr(1.5, 3.0), 0));
    const p2 = s.clone().addScaledVector(dir, len * 0.75).add(new THREE.Vector3(0, rr(1.0, 2.5), 0));
    const p3 = s.clone().addScaledVector(dir, len).add(new THREE.Vector3(0, rr(-0.5, 1.0), 0));
    const curve = new THREE.CatmullRomCurve3([s, p1, p2, p3]);
    const br = new THREE.Mesh(new THREE.TubeGeometry(curve, 20, rr(0.05, 0.11), 6), barkMat);
    br.castShadow = true;
    scene.add(br);
    for (let k = 0; k < 46; k++) {
      const t = rr(0.25, 1.0);
      const a = curve.getPoint(t);
      strands.push([a, rr(1.0, 2.2) + t * rr(1.5, 3.2)]);
      for (let q = 0; q < 16; q++) branchLeafPts.push(a.clone().add(new THREE.Vector3(rr(-0.7, 0.7), rr(-0.4, 0.5), rr(-0.7, 0.7))));
    }
  }
  // count leaves
  const per = 0.07;
  let total = branchLeafPts.length;
  for (const [, L] of strands) total += Math.floor(L / per) * 3;
  const { im, sway } = leafMesh(total, 0.075, 0.2, leafMat({ glow: 1.6 }));
  const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), c = new THREE.Color();
  let i = 0;
  const put = (p, tilt, yaw, s, frac, amp) => {
    e.set(tilt, yaw, rr(-0.4, 0.4)); q4.setFromEuler(e); sc.setScalar(s);
    m4.compose(p, q4, sc); im.setMatrixAt(i, m4);
    c.copy(LEAF_DEEP).lerp(LEAF_FRESH, Math.min(1, frac * 0.75 + rr(-0.15, 0.35)));
    c.multiplyScalar(rr(0.85, 1.12));
    im.setColorAt(i, c);
    sway[i * 2] = rr(0, 6.28) + p.x * 0.3; sway[i * 2 + 1] = amp;
    i++;
  };
  for (const [a, L] of strands) {
    const ph = rr(0, 6.28), drift = new THREE.Vector3(rr(-0.25, 0.25), 0, rr(-0.25, 0.25));
    const n = Math.floor(L / per);
    for (let k = 0; k < n; k++) {
      const f = k / n;
      const p = a.clone().add(new THREE.Vector3(drift.x * f * L + Math.sin(f * 4 + ph) * 0.06, -f * L, drift.z * f * L));
      for (let s2 = 0; s2 < 3; s2++) put(p.clone().add(new THREE.Vector3(rr(-0.06, 0.06), 0, rr(-0.06, 0.06))), rr(0.3, 1.0) * (s2 % 2 ? 1 : -1), rr(0, 6.28), rr(0.8, 1.4), f, 0.03 + 0.22 * f * L / 4.5);
    }
  }
  for (const p of branchLeafPts) put(p, rr(-1.2, 1.2), rr(0, 6.28), rr(0.8, 1.2), rnd() * 0.5, 0.02);
  im.instanceMatrix.needsUpdate = true;
  scene.add(im);
}

// ------------------------------------------------------------------ conifers: whorled branches carrying needle-spray cards
function sprayTexture() {
  const c = document.createElement('canvas'); c.width = 128; c.height = 256;
  const g = c.getContext('2d');
  _s = 555;
  g.lineCap = 'round';
  g.strokeStyle = '#2b2a17'; g.lineWidth = 2.4;
  g.beginPath(); g.moveTo(64, 252); g.quadraticCurveTo(60, 130, 64, 6); g.stroke();
  for (let i = 0; i < 130; i++) {
    const t = i / 130, y = 250 - t * 240, x = 64 + Math.sin(t * 3) * 2;
    const w = 46 * (1 - Math.pow(Math.abs(t - 0.45) * 1.6, 2)) + 6;
    for (const sd of [-1, 1]) {
      const len = w * rr(0.5, 1.0), ang = rr(0.3, 0.8), tone = rnd();
      g.strokeStyle = `rgb(${Math.round(28 + 34 * tone)},${Math.round(58 + 56 * tone)},${Math.round(26 + 26 * tone)})`;
      g.lineWidth = rr(1.5, 2.6);
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + sd * len * Math.cos(ang), y - len * Math.sin(ang)); g.stroke();
    }
  }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  return tex;
}
function pineVariant(seed) {
  _s = seed;
  const cards = [], wood = [], up = new THREE.Vector3(0, 1, 0);
  let y = 1.4;
  while (y < 15.4) {
    const f = y / 16, nb = 5 + Math.floor(rnd() * 3), L = 4.3 * Math.pow(1 - f, 0.9) + 0.45;
    for (let b = 0; b < nb; b++) {
      const a = b / nb * Math.PI * 2 + rr(-0.3, 0.3) + y * 1.3;
      const dir = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
      const P = (t) => dir.clone().multiplyScalar(L * t).add(new THREE.Vector3(0, y - 0.32 * L * t * t + 0.10 * L * t * f, 0));
      wood.push([P(0), P(0.8), 0.035 * (1 - f) + 0.01]);
      const steps = Math.max(2, Math.round(L / 0.42));
      for (let s = 0; s < steps; s++) {
        const t = (s + 0.3) / steps, p = P(t);
        const tan = P(Math.min(1, t + 0.05)).sub(P(Math.max(0, t - 0.05))).normalize();
        for (const k of [-1, 1, 0]) {
          if (k === 0 && s % 2) continue;
          const d = tan.clone().applyAxisAngle(up, k * rr(0.55, 0.95)).add(new THREE.Vector3(0, rr(-0.25, 0.05), 0)).normalize();
          cards.push({ p: p.clone().add(new THREE.Vector3(0, rr(-0.05, 0.05), 0)), d, roll: rr(-0.5, 0.5),
                       sc: rr(0.8, 1.2) * (1 - 0.4 * t) * (0.75 + 0.5 * (1 - f)), h: f });
        }
      }
    }
    y += rr(0.36, 0.52);
  }
  for (let i = 0; i < 16; i++)
    cards.push({ p: new THREE.Vector3(rr(-0.15, 0.15), 16 - rr(0, 1.6), rr(-0.15, 0.15)),
                 d: new THREE.Vector3(rr(-0.5, 0.5), 1, rr(-0.5, 0.5)).normalize(), roll: rr(0, 6), sc: rr(0.5, 0.8), h: 1 });
  return { cards, wood };
}
function cardMatrix(c, out) {
  const yA = c.d.clone();
  const zA = new THREE.Vector3(0, 1, 0).sub(yA.clone().multiplyScalar(yA.y));
  if (zA.lengthSq() < 1e-6) zA.set(1, 0, 0);
  zA.normalize().applyAxisAngle(yA, c.roll);
  const xA = new THREE.Vector3().crossVectors(yA, zA);
  out.makeBasis(xA, yA, zA).scale(new THREE.Vector3(c.sc, c.sc, c.sc)).setPosition(c.p);
  return out;
}
{
  const sprayTex = sprayTexture();
  const pineMat = leafMat({ map: sprayTex, alphaTest: 0.35, glow: 0.35, rough: 0.8 });
  const barkPine = detailMat({ vertexColors: false, color: new THREE.Color(0.11, 0.09, 0.07), rough: 0.9, colFreq: 3, colAmt: 0.25, bumpFreq: 6, bumpAmp: 0.03 });
  const variants = [11, 22, 33, 44].map(pineVariant);
  const groups = [[], [], [], []];
  _s = 98765;
  M.pines.forEach(([x, y, z, h], i) => {
    const tm = new THREE.Matrix4().compose(B(x, y, z), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rr(0, 6.28)),
      new THREE.Vector3(h / 16 * rr(0.9, 1.1), h / 16, h / 16 * rr(0.9, 1.1)));
    groups[i % 4].push({ tm, ph: rr(0, 6.28), h });
  });
  const cylGeo = new THREE.CylinderGeometry(1, 1, 1, 6, 1, true).translate(0, 0.5, 0);
  const trunkGeo = new THREE.CylinderGeometry(0.03, 0.34, 16.4, 8, 1, false).translate(0, 7.9, 0);
  const m = new THREE.Matrix4(), cm = new THREE.Matrix4(), local = new THREE.Matrix4(), col = new THREE.Color();
  groups.forEach((trees, vi) => {
    if (!trees.length) return;
    const V = variants[vi];
    const geo = new THREE.PlaneGeometry(0.6, 1.2).translate(0, 0.6, 0);
    const n = V.cards.length * trees.length;
    const sway = new Float32Array(n * 2);
    geo.setAttribute('aSway', new THREE.InstancedBufferAttribute(sway, 2));
    const im = new THREE.InstancedMesh(geo, pineMat, n);
    im.frustumCulled = false; im.castShadow = true; im.receiveShadow = true;
    im.customDepthMaterial = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: sprayTex, alphaTest: 0.35 });
    let k = 0;
    for (const T of trees) for (const c of V.cards) {
      m.multiplyMatrices(T.tm, cardMatrix(c, cm));
      im.setMatrixAt(k, m);
      const v = rr(0.75, 1.1);
      col.setRGB(v * rr(0.9, 1.05), v, v * rr(0.85, 1.0));
      if (c.h < 0.3) col.multiplyScalar(0.8);
      im.setColorAt(k, col);
      sway[k * 2] = T.ph; sway[k * 2 + 1] = 0.12 * c.h * c.h * T.h / 16;
      k++;
    }
    scene.add(im);
    const wim = new THREE.InstancedMesh(cylGeo, barkPine, V.wood.length * trees.length);
    let w = 0;
    for (const T of trees) {
      const trunk = new THREE.Mesh(trunkGeo, barkPine);
      trunk.applyMatrix4(T.tm); trunk.castShadow = true; scene.add(trunk);
      for (const [a, b2, r] of V.wood) {
        const d = b2.clone().sub(a), len = d.length();
        local.compose(a, new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()), new THREE.Vector3(r, len, r));
        wim.setMatrixAt(w++, m.multiplyMatrices(T.tm, local));
      }
    }
    wim.castShadow = true;
    scene.add(wim);
  });
}

// ------------------------------------------------------------------ bushes (leaf clumps)
{
  let total = 0;
  const per = M.bushes.map(([, , , r]) => Math.floor(160 * r * r + 60));
  per.forEach((n) => (total += n));
  const { im, sway } = leafMesh(total, 0.16, 0.36, leafMat({ glow: 0.6, rough: 0.55 }));
  const core = new THREE.IcosahedronGeometry(1, 1);
  const coreMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.05, 0.12, 0.04), roughness: 0.9 });
  const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), c = new THREE.Color();
  let i = 0;
  M.bushes.forEach(([x, y, z, r], b) => {
    const base = B(x, y, z);
    const cm = new THREE.Mesh(core, coreMat);
    cm.position.copy(base).add(new THREE.Vector3(0, r * 0.45, 0)); cm.scale.set(r * 0.8, r * 0.5, r * 0.8);
    cm.receiveShadow = true; scene.add(cm);
    for (let k = 0; k < per[b]; k++) {
      const u = rnd() * Math.PI * 2, v = Math.acos(rr(-0.2, 1)), rad = r * Math.cbrt(rr(0.35, 1));
      const p = base.clone().add(new THREE.Vector3(Math.cos(u) * Math.sin(v) * rad * 1.1, Math.cos(v) * rad * 0.75 + r * 0.3, Math.sin(u) * Math.sin(v) * rad * 1.1));
      e.set(rr(-2.5, 2.5), rr(0, 6.28), rr(-1, 1)); q4.setFromEuler(e); sc.setScalar(rr(0.8, 1.3));
      m4.compose(p, q4, sc); im.setMatrixAt(i, m4);
      c.setRGB(rr(0.16, 0.30), rr(0.36, 0.55), rr(0.07, 0.13)); im.setColorAt(i, c);
      sway[i * 2] = rr(0, 6.28); sway[i * 2 + 1] = 0.03 * (p.y - base.y) / (r + 0.01);
      i++;
    }
  });
  scene.add(im);
}

// ------------------------------------------------------------------ grass tufts (scattered, random scale/rotation)
{
  const blades = 4, P = [], C = [];
  for (let b = 0; b < blades; b++) {
    const a = b / blades * Math.PI * 2 + rr(-0.3, 0.3), lean = rr(0.08, 0.3), h = rr(0.6, 1.0), w = 0.035;
    const dx = Math.cos(a), dz = Math.sin(a), px = -dz * w, pz = dx * w;
    const ox = dx * rr(0, 0.05), oz = dz * rr(0, 0.05);
    const mid = [ox + dx * lean * 0.35, h * 0.55, oz + dz * lean * 0.35], tip = [ox + dx * lean, h, oz + dz * lean];
    const l = [ox - px, 0, oz - pz], r = [ox + px, 0, oz + pz];
    const ml = [mid[0] - px * 0.6, mid[1], mid[2] - pz * 0.6], mr = [mid[0] + px * 0.6, mid[1], mid[2] + pz * 0.6];
    const cb = [0.35, 0.55, 0.2], cm = [0.7, 0.9, 0.5], ct = [1.0, 1.0, 0.75];
    P.push(...l, ...r, ...mr, ...l, ...mr, ...ml, ...ml, ...mr, ...tip);
    C.push(...cb, ...cb, ...cm, ...cb, ...cm, ...cm, ...cm, ...cm, ...ct);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(C, 3));
  geo.computeVertexNormals();
  const N = 40000;
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.7 });
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = U.time;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nuniform float uTime;')
      .replace('#include <project_vertex>', `
        vec4 mvPosition = vec4(transformed, 1.0);
        mvPosition = instanceMatrix * mvPosition;
        float ph = instanceMatrix[3][0] * 0.35 + instanceMatrix[3][2] * 0.21;
        float k = transformed.y * transformed.y;
        mvPosition.x += (sin(uTime * 1.6 + ph) * 0.7 + sin(uTime * 3.7 + ph * 2.0) * 0.3) * 0.09 * k;
        mvPosition.z += sin(uTime * 1.2 + ph * 0.8) * 0.06 * k;
        mvPosition = modelViewMatrix * mvPosition;
        gl_Position = projectionMatrix * mvPosition;`)
      .replace('#include <normal_fragment_begin>', '#include <normal_fragment_begin>\nnormal = normalize(mix(normal, vec3(viewMatrix * vec4(0.0,1.0,0.0,0.0)), 0.6));');
  };
  const im = new THREE.InstancedMesh(geo, mat, N);
  im.receiveShadow = true;
  im.frustumCulled = false;
  const m4 = new THREE.Matrix4(), q4 = new THREE.Quaternion(), sc = new THREE.Vector3(), c = new THREE.Color(), up = new THREE.Vector3(0, 1, 0);
  let n = 0, guard = 0;
  _s = 4242;
  while (n < N && guard++ < N * 8) {
    const by = -4 + 100 * Math.pow(rnd(), 1.6), bx = rr(-60, 60);
    const [d, w] = riverInfo(bx, by);
    const e2 = d - w;
    const tall = e2 > 1.2 && e2 < 4.5 && rnd() < 0.5;
    if (e2 < 1.6 && !tall) continue;
    if (Math.abs(bx) > 25 + by * 0.6) continue;               // keep to what the camera sees
    const h = groundH(bx, by);
    if (h < 0.1) continue;
    const s = tall ? rr(0.9, 1.4) : rr(0.35, 0.65) * rr(0.8, 1.2);
    q4.setFromAxisAngle(up, rnd() * 6.28);
    sc.set(s * rr(0.8, 1.2), s, s * rr(0.8, 1.2));
    m4.compose(B(bx, by, h - 0.03), q4, sc);
    im.setMatrixAt(n, m4);
    const v = rnd();
    c.setRGB(0.20 + 0.25 * v, 0.42 + 0.22 * v, 0.06 + 0.06 * v);
    if (tall) c.multiplyScalar(0.8);
    im.setColorAt(n, c);
    n++;
  }
  im.count = n;
  scene.add(im);
}

// ------------------------------------------------------------------ birds
const birds = [];
{
  const mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.06, 0.05, 0.05), roughness: 0.8, side: THREE.DoubleSide });
  const wingGeo = new THREE.BufferGeometry();
  wingGeo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0.12, 0, 0, -0.1, 0.62, 0.0, -0.22, 0, 0, 0.12, 0.62, 0, -0.22, 0.45, 0, 0.0], 3));
  wingGeo.computeVertexNormals();
  const bodyGeo = new THREE.SphereGeometry(0.09, 8, 6).scale(1, 0.8, 2.6);
  const flock = (start, end, mid, t0, dur, n, spread) => {
    for (let k = 0; k < n; k++) {
      const off = new THREE.Vector3(rr(-spread, spread), rr(-spread * 0.4, spread * 0.4), rr(-spread, spread));
      const curve = new THREE.CatmullRomCurve3([start.clone().add(off), mid.clone().add(off), end.clone().add(off)]);
      const g = new THREE.Group();
      const body = new THREE.Mesh(bodyGeo, mat);
      const wl = new THREE.Mesh(wingGeo, mat), wr = new THREE.Mesh(wingGeo, mat);
      wr.scale.x = -1;
      g.add(body, wl, wr);
      g.scale.setScalar(rr(3.0, 3.8));
      scene.add(g);
      birds.push({ g, wl, wr, curve, t0: t0 + rr(-0.6, 0.6), dur: dur * rr(0.95, 1.05), ph: rr(0, 6.28), f: rr(2.6, 3.4) });
    }
  };
  flock(B(-90, 70, 30), B(110, 85, 40), B(10, 60, 46), -1, 19, 3, 3.5);
  flock(B(120, 110, 50), B(-110, 95, 36), B(0, 120, 58), 3, 18, 3, 4.0);
  flock(B(-60, 140, 70), B(80, 130, 62), B(20, 160, 80), 6, 16, 2, 3.0);
}
function updateBirds(t) {
  for (const b of birds) {
    const u = (t - b.t0) / b.dur;
    b.g.visible = u > 0 && u < 1;
    if (!b.g.visible) continue;
    const p = b.curve.getPoint(u), p2 = b.curve.getPoint(Math.min(u + 0.01, 1));
    b.g.position.copy(p);
    b.g.lookAt(p2.x + (p2.x - p.x) * 10, p2.y, p2.z + (p2.z - p.z) * 10);
    const glide = 0.5 + 0.5 * Math.sin(t * 0.7 + b.ph);
    const flap = Math.sin(t * b.f * Math.PI * 2 + b.ph) * (0.25 + 0.55 * (glide > 0.35 ? 1 : 0.25));
    b.wl.rotation.z = flap; b.wr.rotation.z = -flap;
  }
}

// ------------------------------------------------------------------ camera path (Bezier-like spline, eased)
const mxs = (v) => (M.mirror ? -v : v);
const camPath = new THREE.CatmullRomCurve3([B(0, -2, 1.8), B(mxs(0.8), 10, 3.2), B(mxs(3.5), 24, 6.2), B(mxs(6.5), 34, 9.5), B(mxs(8), 40, 12)], false, 'centripetal');
const tgtPath = new THREE.CatmullRomCurve3([B(0, 100, 12.3), B(mxs(4), 100, 12.5), B(mxs(12), 100, 13.5), B(mxs(18), 100, 14), B(mxs(20), 100, 13)], false, 'centripetal');
const ease = (t) => t * t * t * (t * (t * 6 - 15) + 10);

// ------------------------------------------------------------------ post: god rays + sun glare
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
composer.addPass(new RenderPass(scene, camera));
const rays = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uSun: { value: new THREE.Vector2(0.7, 0.8) }, uOn: { value: 1 }, uAspect: { value: W / H } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform vec2 uSun; uniform float uOn; uniform float uAspect; varying vec2 vUv;
    float lum(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
    void main(){
      vec4 base = texture2D(tDiffuse, vUv);
      vec2 delta = (vUv - uSun) * (0.85 / 36.0);
      vec2 uv = vUv; float decay = 1.0; vec3 acc = vec3(0.0);
      for (int i = 0; i < 36; i++){
        uv -= delta;
        vec3 s = texture2D(tDiffuse, clamp(uv, 0.001, 0.999)).rgb;
        float l = max(lum(s) - 2.2, 0.0);
        acc += vec3(1.0, 0.86, 0.62) * min(l, 6.0) * decay;
        decay *= 0.955;
      }
      float vis = 0.0;
      for (int i = 0; i < 5; i++){ vec2 o = vec2(float(i - 2) * 0.004, float((i * 3) % 5 - 2) * 0.004); vis += smoothstep(1.5, 12.0, lum(texture2D(tDiffuse, uSun + o).rgb)); }
      vis /= 5.0;
      vec2 dd = (vUv - uSun) * vec2(uAspect, 1.0);
      float r = length(dd);
      vec3 glare = vec3(1.0, 0.84, 0.58) * (0.30 * exp(-r * 6.0) + 0.9 * exp(-r * 28.0) + 0.25 * exp(-abs(dd.y) * 90.0) * exp(-abs(dd.x) * 3.0));
      gl_FragColor = vec4(base.rgb + (acc * 0.032 + glare * vis) * uOn, base.a);
    }`,
});
composer.addPass(rays);
composer.addPass(new OutputPass());

// ------------------------------------------------------------------ frame driver
const tmp = new THREE.Vector3();
window.renderFrame = (frame) => {
  const t = (frame - 1) / FPS;
  U.time.value = t;
  const u = ease(Math.min(Math.max((frame - 1) / (FRAMES - 1), 0), 1));
  camera.position.copy(camPath.getPoint(u));
  camera.lookAt(tgtPath.getPoint(u));
  camera.updateMatrixWorld();
  sky.position.copy(camera.position);
  updateBirds(t);
  updateFallParticles(t);
  tmp.copy(camera.position).addScaledVector(SUN_VIS, 1000).project(camera);
  const onScreen = tmp.z < 1 && Math.abs(tmp.x) < 1.3 && Math.abs(tmp.y) < 1.3;
  rays.uniforms.uSun.value.set(tmp.x * 0.5 + 0.5, tmp.y * 0.5 + 0.5);
  rays.uniforms.uOn.value = onScreen ? 1 : 0;
  composer.render();
  return true;
};
window.renderFrame(1);
window.READY = true;
console.log('READY', renderer.info.render.triangles, 'tris');
