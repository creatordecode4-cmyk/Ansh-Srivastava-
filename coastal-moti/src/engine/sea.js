import * as THREE from 'three';
import { SKY } from './sky.js';

const SIZE = 800;

// Animated low-poly sea. Waves are computed in the vertex shader (cheap on phones);
// segment count comes from the quality preset, colours and wave size from the environment.
export function createSea(segments) {
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uAmp: { value: 0.22 },
      uDeep: { value: new THREE.Color(0x0b4f6c) },
      uShallow: { value: new THREE.Color(0x2fa7a0) },
      uHorizon: { value: SKY.horizon },
      uSun: { value: SKY.sun },
      uSunDir: { value: SKY.sunDir },
      uFlash: SKY.flash,
    },
    vertexShader: /* glsl */`
      uniform float uTime, uAmp;
      varying vec3 vWorld;
      varying float vWave;
      float wave(vec2 p) {
        return sin(p.x * 0.09 + uTime * 0.9) * 0.55
             + sin(p.y * 0.13 + uTime * 1.2) * 0.35
             + sin((p.x + p.y) * 0.05 + uTime * 0.6) * 0.8;
      }
      void main() {
        vec4 world = modelMatrix * vec4(position, 1.0);
        float w = wave(world.xz);
        world.y += w * uAmp;
        vWave = w;
        vWorld = world.xyz;
        gl_Position = projectionMatrix * viewMatrix * world;
      }`,
    fragmentShader: /* glsl */`
      precision mediump float;
      uniform vec3 uDeep, uShallow, uHorizon, uSun, uSunDir;
      uniform float uFlash;
      varying vec3 vWorld;
      varying float vWave;
      void main() {
        // Flat-shaded normal from screen-space derivatives: gives the low-poly facet look.
        vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
        vec3 v = normalize(cameraPosition - vWorld);
        vec3 col = mix(uDeep, uShallow, smoothstep(-1.2, 1.4, vWave));
        col *= 0.75 + 0.35 * max(dot(n, uSunDir), 0.0);
        float spec = pow(max(dot(reflect(-uSunDir, n), v), 0.0), 60.0);
        col += uSun * spec * 0.6;
        float fres = pow(1.0 - max(dot(n, v), 0.0), 3.0);
        col = mix(col, uHorizon, fres * 0.55);
        float dist = length(cameraPosition.xz - vWorld.xz);
        col = mix(col, uHorizon, smoothstep(120.0, 390.0, dist));
        col += vec3(0.3, 0.34, 0.42) * uFlash;
        gl_FragColor = vec4(col, 1.0);
      }`,
  });

  const mesh = new THREE.Mesh(buildGeometry(segments), material);
  mesh.name = 'sea';
  mesh.frustumCulled = false;
  let time = 0, speed = 1;

  return {
    mesh,
    update(dt) { time += dt * speed; material.uniforms.uTime.value = time; },
    setSegments(n) {
      mesh.geometry.dispose();
      mesh.geometry = buildGeometry(n);
    },
    setLook({ deep, shallow, amp, speed: s }) {
      material.uniforms.uDeep.value.setHex(deep);
      material.uniforms.uShallow.value.setHex(shallow);
      material.uniforms.uAmp.value = amp;
      speed = s;
    },
  };
}

function buildGeometry(segments) {
  const g = new THREE.PlaneGeometry(SIZE, SIZE, segments, segments);
  g.rotateX(-Math.PI / 2);
  return g;
}
