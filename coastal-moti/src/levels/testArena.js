import * as THREE from 'three';
import { smoothstep } from '../engine/mathx.js';
import { ENV_DAY } from '../engine/environments.js';

// TEST ARENA (placeholder art): a small daytime island with a walled compound, crates, rocks and palms.
// Used by the engine test mission (open the game with ?mission=t0_systems_check).

function heightAt(x, z) {
  const r = Math.hypot(x, z);
  const land = 1.5 - 4.5 * smoothstep(44, 72, r);
  const bumps = 0.35 * Math.sin(x * 0.15) * Math.cos(z * 0.13) * (1 - smoothstep(40, 60, r));
  const hill = 3.2 * Math.exp(-((x + 26) ** 2 + (z + 22) ** 2) / 180);
  return land + bumps + hill;
}

export const testArena = {
  id: 'testArena',
  env: ENV_DAY,
  heightAt,
  build(b) {
    const sand = new THREE.Color(0xe2cf9b), wet = new THREE.Color(0xb9a374);
    const grass = new THREE.Color(0x7fae5a), high = new THREE.Color(0x5f8f4a);
    b.terrain({ colorAt(h, x, z, c) {
      if (h < 0.25) c.copy(wet);
      else if (h < 1.0) c.copy(wet).lerp(sand, smoothstep(0.25, 0.6, h));
      else if (h < 1.9) c.copy(sand).lerp(grass, smoothstep(1.0, 1.35, h));
      else c.copy(grass).lerp(high, smoothstep(1.9, 4, h));
    } });

    // Walls: [x, z, sizeX, sizeZ, height]. 3 m tall: they block movement AND line of sight.
    b.boxes(0xd9c7a3, [
      [12, -20, 8, 0.8, 3], [25, -20, 6, 0.8, 3],      // compound north (gap = gate)
      [11, -4, 6, 0.8, 3], [23, -4, 10, 0.8, 3],       // compound south (gap = gate)
      [8, -15, 0.8, 10, 3], [28, -16, 0.8, 8, 3],      // compound west / east
      [18, -12, 0.8, 6, 3],                            // inner wall
      [-8, 14, 5, 0.8, 3], [-14, -6, 0.8, 5, 3], [2, -28, 6, 0.8, 3], [34, 4, 0.8, 6, 3], [0, 18, 6, 0.8, 3],
    ]);

    // Crates: low cover. Block movement, not sight.
    const crates = [[14, -13], [15.2, -13], [14.5, -11.8], [22, -9], [23.2, -9], [21, -17], [4, 6], [5.2, 6],
      [-4, -12], [30, 12], [-20, 12], [10, 28]];
    b.instanced(new THREE.BoxGeometry(1.1, 1.1, 1.1), 0x9a6b3f, crates, ([x, z], d) => {
      const col = b.collider(x, z, 1.1, 1.1, 1.1, false);
      d.position.set(x, col.y + 0.5, z);
      d.rotation.y = b.rand() * 0.3;
    });

    // Rocks: big ones block sight.
    const rocks = [[-18, 24, 1.8], [26, 26, 1.5], [40, -10, 1.9], [-32, 4, 1.4], [-6, -36, 1.7], [16, 38, 1.2],
      [-36, -30, 1.6], [44, 20, 1.3]];
    b.instanced(new THREE.IcosahedronGeometry(1, 0), 0x8d8a82, rocks, ([x, z, r], d) => {
      const col = b.collider(x, z, r * 1.4, r * 1.4, r * 1.5, r >= 1.5);
      d.position.set(x, col.y + r * 0.45, z);
      d.scale.set(r, r * 0.85, r);
      d.rotation.set(b.rand(), b.rand() * 6, b.rand());
    });

    // Palms: the trunk blocks movement only.
    const palms = [];
    while (palms.length < 16) {
      const a = b.rand() * Math.PI * 2, r = 30 + b.rand() * 20;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (Math.abs(x) < 6 && z > 20) continue; // keep the landing beach clear
      palms.push([x, z, 4.5 + b.rand() * 1.5, b.rand() * 6]);
    }
    b.instanced(new THREE.CylinderGeometry(0.16, 0.28, 1, 6), 0x8a6a45, palms, ([x, z, h], d) => {
      const col = b.collider(x, z, 0.6, 0.6, h, false);
      d.position.set(x, col.y + h / 2 - 0.2, z);
      d.scale.set(1, h, 1);
    });
    b.instanced(new THREE.ConeGeometry(2.3, 1.3, 6), 0x3f8f4f, palms, ([x, z, h, rot], d) => {
      d.position.set(x, heightAt(x, z) + h + 0.2, z);
      d.rotation.y = rot;
    });

    // Placeholder boat at the landing beach.
    const boat = new THREE.Group();
    const hull = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.7, 4.2), new THREE.MeshLambertMaterial({ color: 0x2f6f8f }));
    const rim = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.12, 4.4), new THREE.MeshLambertMaterial({ color: 0xe8a33d }));
    rim.position.y = 0.4;
    boat.add(hull, rim);
    boat.position.set(3.5, 0.25, 56.5);
    boat.rotation.y = 0.35;
    boat.traverse((o) => { o.castShadow = true; });
    b.add(boat);
    b.collider(3.5, 56.5, 2.4, 4.2, 1, false);
  },
};
