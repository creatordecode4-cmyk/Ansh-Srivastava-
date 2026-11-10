import * as THREE from 'three';

// Shared palette so the sea can fade into exactly the sky's horizon colour.
export const SKY = {
  zenith: new THREE.Color(0x2f7fc4),
  horizon: new THREE.Color(0xf4e2c6),
  sun: new THREE.Color(0xfff1c9),
  sunDir: new THREE.Vector3(-0.45, 0.42, -0.79).normalize(),
};

// Gradient sky dome with a soft sun. One draw call, no textures.
export function createSky() {
  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      uZenith: { value: SKY.zenith },
      uHorizon: { value: SKY.horizon },
      uSun: { value: SKY.sun },
      uSunDir: { value: SKY.sunDir },
    },
    vertexShader: /* glsl */`
      varying vec3 vDir;
      void main() {
        vDir = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */`
      precision mediump float;
      uniform vec3 uZenith, uHorizon, uSun, uSunDir;
      varying vec3 vDir;
      void main() {
        vec3 d = normalize(vDir);
        float h = clamp(d.y, 0.0, 1.0);
        vec3 col = mix(uHorizon, uZenith, smoothstep(0.0, 0.4, h));
        float s = max(dot(d, uSunDir), 0.0);
        col += uSun * (pow(s, 600.0) * 1.5 + pow(s, 12.0) * 0.25);
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(900, 24, 12), material);
  mesh.name = 'sky';
  mesh.frustumCulled = false;
  mesh.renderOrder = -1;
  return mesh;
}
