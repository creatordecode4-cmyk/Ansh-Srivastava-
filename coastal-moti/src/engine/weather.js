import * as THREE from 'three';

// Rain + lightning.
// Rain is ONE draw call: a fixed set of line segments that the vertex shader moves and wraps
// around the camera. Nothing is updated on the CPU per drop, so it is cheap on phones.
const MAX_DROPS = 1800;

export function createWeather(scene) {
  const positions = new Float32Array(MAX_DROPS * 6);
  const ends = new Float32Array(MAX_DROPS * 2);
  for (let i = 0; i < MAX_DROPS; i++) {
    const x = Math.random(), y = Math.random(), z = Math.random();
    positions.set([x, y, z, x, y, z], i * 6);
    ends[i * 2 + 1] = 1; // second vertex is the top of the streak
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aEnd', new THREE.BufferAttribute(ends, 1));
  const uniforms = {
    uTime: { value: 0 },
    uCam: { value: new THREE.Vector3() },
    uWind: { value: new THREE.Vector2(7, 3) }, // metres per second, sideways
    uOpacity: { value: 0.4 },
  };
  const rain = new THREE.LineSegments(geometry, new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false, fog: false,
    vertexShader: /* glsl */`
      attribute float aEnd;
      uniform float uTime;
      uniform vec3 uCam;
      uniform vec2 uWind;
      const vec3 BOX = vec3(36.0, 22.0, 36.0);
      void main() {
        float speed = 24.0 + fract(position.x * 37.3) * 9.0;
        vec3 p = position * BOX;
        p.y = mod(p.y - uTime * speed, BOX.y);
        p.xz = mod(p.xz + uWind * uTime - uCam.xz, BOX.xz) - BOX.xz * 0.5;
        vec3 world = vec3(uCam.x + p.x, uCam.y - 8.0 + p.y, uCam.z + p.z);
        float len = 0.7 * aEnd;
        world += vec3(-uWind.x * len / speed, len, -uWind.y * len / speed); // slanted streak
        gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
      }`,
    fragmentShader: /* glsl */`
      precision mediump float;
      uniform float uOpacity;
      void main() { gl_FragColor = vec4(0.76, 0.83, 0.95, uOpacity); }`,
  }));
  rain.frustumCulled = false;
  rain.visible = false;
  rain.name = 'rain';
  scene.add(rain);

  let lightning = false, nextStrike = 5, strikeT = -1, flash = 0;
  const weather = {
    onStrike: null,
    set({ rain: amount = 0, lightning: l = false }) {
      rain.visible = amount > 0;
      uniforms.uOpacity.value = 0.4 * amount;
      lightning = l;
      nextStrike = 3 + Math.random() * 4;
      strikeT = -1; flash = 0;
    },
    setDensity(drops) { geometry.setDrawRange(0, Math.min(MAX_DROPS, drops) * 2); },
    strike() { strikeT = 0; weather.onStrike?.(); },
    // Returns the current lightning brightness, 0..1.
    update(dt, camera) {
      uniforms.uTime.value += dt;
      uniforms.uCam.value.copy(camera.position);
      if (lightning && (nextStrike -= dt) <= 0) { nextStrike = 7 + Math.random() * 9; weather.strike(); }
      if (strikeT >= 0) {
        strikeT += dt;
        const t = strikeT; // double flicker, then a slow fade
        flash = t < 0.07 ? 1 : t < 0.15 ? 0.15 : t < 0.26 ? 0.8 : Math.max(0, 0.8 * (1 - (t - 0.26) / 0.5));
        if (t > 0.8) { strikeT = -1; flash = 0; }
      }
      return flash;
    },
  };
  return weather;
}
