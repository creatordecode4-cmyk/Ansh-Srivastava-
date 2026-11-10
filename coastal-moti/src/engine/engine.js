import * as THREE from 'three';
import { QUALITY } from './quality.js';
import { createSky, SKY } from './sky.js';
import { createSea } from './sea.js';
import { createWeather } from './weather.js';
import { ENV_DAY } from './environments.js';

// Owns the renderer, scene, camera, lights, weather and the frame loop.
export function createEngine(canvas, initialQuality) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: initialQuality !== 'low',
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.3, 2000);
  camera.position.set(0, 6, 14);

  // Lighting budget: one hemisphere fill + ONE directional light (sun or moon, the only shadow caster).
  const hemi = new THREE.HemisphereLight(0xcfe8ff, 0x6b6a4a, 1.1);
  const sun = new THREE.DirectionalLight(0xfff1c9, 1.7);
  sun.position.copy(SKY.sunDir).multiplyScalar(80);
  const sc = sun.shadow.camera;
  sc.left = sc.bottom = -28; sc.right = sc.top = 28; sc.near = 1; sc.far = 200;
  sun.shadow.bias = -0.0015;
  scene.add(hemi, sun, sun.target);

  const sky = createSky();
  scene.add(sky);

  let quality = QUALITY[initialQuality];
  const sea = createSea(quality.seaSegments);
  scene.add(sea.mesh);
  const weather = createWeather(scene);

  let baseHemi = 1.1;
  const fogBase = new THREE.Color(), fogFlash = new THREE.Color(0x8fa0b8);

  function setEnvironment(env) {
    SKY.zenith.setHex(env.zenith);
    SKY.horizon.setHex(env.horizon);
    SKY.sun.setHex(env.sun);
    SKY.sunStrength.value = env.sunDisc;
    hemi.color.setHex(env.hemi[0]);
    hemi.groundColor.setHex(env.hemi[1]);
    baseHemi = hemi.intensity = env.hemi[2];
    sun.color.setHex(env.sun);
    sun.intensity = env.sunIntensity;
    sea.setLook(env.sea);
    scene.fog = env.fog ? new THREE.Fog(env.fog.color, env.fog.near, env.fog.far) : null;
    if (env.fog) fogBase.setHex(env.fog.color);
    weather.set(env);
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, quality.pixelRatio));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function setQuality(name) {
    quality = QUALITY[name];
    sea.setSegments(quality.seaSegments);
    weather.setDensity(quality.rainDrops);
    renderer.shadowMap.enabled = quality.shadows;
    sun.castShadow = quality.shadows;
    if (quality.shadows) {
      sun.shadow.mapSize.set(quality.shadowMapSize, quality.shadowMapSize);
      sun.shadow.map?.dispose();
      sun.shadow.map = null;
    }
    resize();
  }

  // Keep the (small) shadow box centred on the action.
  function setShadowFocus(p) {
    sun.target.position.copy(p);
    sun.position.copy(SKY.sunDir).multiplyScalar(80).add(p);
  }

  const updaters = [];
  let fpsCallback = null;
  let frames = 0, fpsFrames = 0, fpsTime = 0;
  const clock = new THREE.Clock();

  function frame() {
    const dt = Math.min(clock.getDelta(), 0.1);
    for (const fn of updaters) fn(dt);
    sky.position.copy(camera.position);
    sea.update(dt);

    // Lightning lights the whole scene for a moment.
    const flash = weather.update(dt, camera);
    SKY.flash.value = flash;
    hemi.intensity = baseHemi + flash * 2.6;
    if (scene.fog) scene.fog.color.copy(fogBase).lerp(fogFlash, flash * 0.8);

    renderer.render(scene, camera);

    frames++; fpsFrames++; fpsTime += dt;
    if (fpsTime >= 0.5) {
      fpsCallback?.(Math.round(fpsFrames / fpsTime));
      fpsFrames = 0; fpsTime = 0;
    }
  }

  window.addEventListener('resize', resize);
  setQuality(initialQuality);
  setEnvironment(ENV_DAY);

  return {
    renderer, scene, camera, weather,
    setQuality, setShadowFocus, setEnvironment,
    onUpdate(fn) { updaters.push(fn); },
    onFps(cb) { fpsCallback = cb; },
    get frames() { return frames; },
    start() { clock.start(); renderer.setAnimationLoop(frame); },
    stop() { renderer.setAnimationLoop(null); },
  };
}
