import * as THREE from 'three';
import { QUALITY } from './quality.js';
import { createSky, SKY } from './sky.js';
import { createSea } from './sea.js';

// Owns the renderer, scene, camera and the frame loop.
export function createEngine(canvas, initialQuality) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: initialQuality !== 'low',
    powerPreference: 'high-performance',
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 2000);
  camera.position.set(0, 6, 14);

  // Lighting budget: one hemisphere fill + ONE directional sun (the only shadow caster).
  scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x3a5a4a, 0.9));
  const sun = new THREE.DirectionalLight(SKY.sun, 1.6);
  sun.position.copy(SKY.sunDir).multiplyScalar(100);
  sun.shadow.camera.left = sun.shadow.camera.bottom = -40;
  sun.shadow.camera.right = sun.shadow.camera.top = 40;
  sun.shadow.camera.far = 250;
  scene.add(sun);

  const sky = createSky();
  scene.add(sky);

  let quality = QUALITY[initialQuality];
  const sea = createSea(quality.seaSegments);
  scene.add(sea.mesh);

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
    renderer.shadowMap.enabled = quality.shadows;
    sun.castShadow = quality.shadows;
    if (quality.shadows) {
      sun.shadow.mapSize.set(quality.shadowMapSize, quality.shadowMapSize);
      sun.shadow.map?.dispose();
      sun.shadow.map = null;
    }
    resize();
  }

  let fpsCallback = null;
  let frames = 0, fpsFrames = 0, fpsTime = 0, running = false;
  const clock = new THREE.Clock();

  function frame() {
    if (!running) return;
    const dt = Math.min(clock.getDelta(), 0.1);
    const t = clock.elapsedTime;

    // Placeholder camera: a slow drift so the empty scene is visibly alive.
    camera.position.set(Math.sin(t * 0.08) * 14, 6 + Math.sin(t * 0.3) * 0.4, Math.cos(t * 0.08) * 14);
    camera.lookAt(SKY.sunDir.x * 60, 3, SKY.sunDir.z * 60);
    sky.position.copy(camera.position);
    sea.update(t);

    renderer.render(scene, camera);

    frames++; fpsFrames++; fpsTime += dt;
    if (fpsTime >= 0.5) {
      fpsCallback?.(Math.round(fpsFrames / fpsTime));
      fpsFrames = 0; fpsTime = 0;
    }
  }

  window.addEventListener('resize', resize);
  setQuality(initialQuality);

  return {
    renderer, scene, camera,
    setQuality,
    onFps(cb) { fpsCallback = cb; },
    get frames() { return frames; },
    start() { running = true; clock.start(); renderer.setAnimationLoop(frame); },
    stop() { running = false; renderer.setAnimationLoop(null); },
  };
}
