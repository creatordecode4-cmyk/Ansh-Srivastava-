import * as THREE from 'three';
import { clamp, smoothstep, seededRandom } from './mathx.js';

// TEST ARENA (placeholder art): a small island with a walled compound, crates, rocks and palms.
// Story locations will replace the layout; the collision API below stays the same.

const MIN_STAND_HEIGHT = -0.55; // deeper water than this blocks movement
const TERRAIN_SIZE = 180;

// Analytic height field: the same function drives the mesh and the collision.
export function heightAt(x, z) {
  const r = Math.hypot(x, z);
  const land = 1.5 - 4.5 * smoothstep(44, 72, r);
  const bumps = 0.35 * Math.sin(x * 0.15) * Math.cos(z * 0.13) * (1 - smoothstep(40, 60, r));
  const hill = 3.2 * Math.exp(-((x + 26) ** 2 + (z + 22) ** 2) / 180);
  return land + bumps + hill;
}

export function createWorld(scene) {
  const colliders = []; // axis-aligned boxes on the XZ plane
  const rand = seededRandom(7);

  // ---- terrain -------------------------------------------------------------
  const geo = new THREE.PlaneGeometry(TERRAIN_SIZE, TERRAIN_SIZE, 90, 90);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  const colors = new Float32Array(pos.count * 3);
  const sand = new THREE.Color(0xe2cf9b), wet = new THREE.Color(0xb9a374);
  const grass = new THREE.Color(0x7fae5a), high = new THREE.Color(0x5f8f4a), c = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const h = heightAt(pos.getX(i), pos.getZ(i));
    pos.setY(i, h);
    if (h < 0.25) c.copy(wet);
    else if (h < 1.0) c.copy(wet).lerp(sand, smoothstep(0.25, 0.6, h));
    else if (h < 1.9) c.copy(sand).lerp(grass, smoothstep(1.0, 1.35, h));
    else c.copy(grass).lerp(high, smoothstep(1.9, 4, h));
    colors.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  const terrain = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  terrain.receiveShadow = true;
  terrain.name = 'terrain';
  scene.add(terrain);

  // ---- props (all instanced: one draw call per prop type) -------------------
  const dummy = new THREE.Object3D();
  function instanced(geometry, color, items, place) {
    const mesh = new THREE.InstancedMesh(geometry, new THREE.MeshLambertMaterial({ color, flatShading: true }), items.length);
    items.forEach((item, i) => {
      dummy.position.set(0, 0, 0); dummy.rotation.set(0, 0, 0); dummy.scale.set(1, 1, 1);
      place(item, dummy);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.castShadow = mesh.receiveShadow = true;
    scene.add(mesh);
    return mesh;
  }
  function addCollider(cx, cz, sx, sz, height, blocksSight) {
    const col = { minX: cx - sx / 2, maxX: cx + sx / 2, minZ: cz - sz / 2, maxZ: cz + sz / 2,
      cx, cz, y: heightAt(cx, cz), height, blocksSight };
    colliders.push(col);
    return col;
  }

  // Walls: [centreX, centreZ, sizeX, sizeZ]. 3 m tall, they block movement AND line of sight.
  const WALL_H = 3;
  const walls = [
    [12, -20, 8, 0.8], [25, -20, 6, 0.8],      // compound north (gap = gate)
    [11, -4, 6, 0.8], [23, -4, 10, 0.8],       // compound south (gap = gate)
    [8, -15, 0.8, 10], [28, -16, 0.8, 8],      // compound west / east
    [18, -12, 0.8, 6],                         // inner wall
    [-8, 14, 5, 0.8], [-14, -6, 0.8, 5], [2, -28, 6, 0.8], [34, 4, 0.8, 6], [0, 18, 6, 0.8], // loose cover
  ];
  instanced(new THREE.BoxGeometry(1, 1, 1), 0xd9c7a3, walls, ([x, z, sx, sz], d) => {
    const col = addCollider(x, z, sx, sz, WALL_H, true);
    d.position.set(x, col.y - 1 + (WALL_H + 1) / 2, z);
    d.scale.set(sx, WALL_H + 1, sz);
  });

  // Crates: low cover. Block movement, not sight.
  const crates = [[14, -13], [15.2, -13], [14.5, -11.8], [22, -9], [23.2, -9], [21, -17], [4, 6], [5.2, 6],
    [-4, -12], [30, 12], [-20, 12], [10, 28]];
  instanced(new THREE.BoxGeometry(1.1, 1.1, 1.1), 0x9a6b3f, crates, ([x, z], d) => {
    const col = addCollider(x, z, 1.1, 1.1, 1.1, false);
    d.position.set(x, col.y + 0.5, z);
    d.rotation.y = rand() * 0.3;
  });

  // Rocks: big ones block sight.
  const rocks = [[-18, 24, 1.8], [26, 26, 1.5], [40, -10, 1.9], [-32, 4, 1.4], [-6, -36, 1.7], [16, 38, 1.2],
    [-36, -30, 1.6], [44, 20, 1.3]];
  instanced(new THREE.IcosahedronGeometry(1, 0), 0x8d8a82, rocks, ([x, z, r], d) => {
    const col = addCollider(x, z, r * 1.4, r * 1.4, r * 1.5, r >= 1.5);
    d.position.set(x, col.y + r * 0.45, z);
    d.scale.set(r, r * 0.85, r);
    d.rotation.set(rand(), rand() * 6, rand());
  });

  // Palms: trunk blocks movement only.
  const palms = [];
  while (palms.length < 16) {
    const a = rand() * Math.PI * 2, r = 30 + rand() * 20;
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (Math.abs(x) < 6 && z > 20) continue; // keep the landing beach clear
    if (colliders.some((k) => x > k.minX - 2 && x < k.maxX + 2 && z > k.minZ - 2 && z < k.maxZ + 2)) continue;
    palms.push([x, z, 4.5 + rand() * 1.5, rand() * 6]);
  }
  instanced(new THREE.CylinderGeometry(0.16, 0.28, 1, 6), 0x8a6a45, palms, ([x, z, h], d) => {
    const col = addCollider(x, z, 0.6, 0.6, h, false);
    d.position.set(x, col.y + h / 2 - 0.2, z);
    d.scale.set(1, h, 1);
  });
  instanced(new THREE.ConeGeometry(2.3, 1.3, 6), 0x3f8f4f, palms, ([x, z, h, rot], d) => {
    d.position.set(x, heightAt(x, z) + h + 0.2, z);
    d.rotation.y = rot;
  });

  // Placeholder boat at the landing beach (also the mission start/end point).
  const boat = new THREE.Group();
  const hull = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.7, 4.2), new THREE.MeshLambertMaterial({ color: 0x2f6f8f }));
  const rim = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.12, 4.4), new THREE.MeshLambertMaterial({ color: 0xe8a33d }));
  rim.position.y = 0.4;
  boat.add(hull, rim);
  boat.position.set(3.5, 0.25, 56.5);
  boat.rotation.y = 0.35;
  boat.traverse((o) => { o.castShadow = true; });
  scene.add(boat);
  addCollider(3.5, 56.5, 2.4, 4.2, 1, false);

  // ---- collision API -----------------------------------------------------
  const canStand = (x, z) => heightAt(x, z) > MIN_STAND_HEIGHT;

  // Push a circle (p.x, p.z, radius) out of every box it overlaps.
  function resolveCircle(p, radius) {
    for (const k of colliders) {
      const nx = clamp(p.x, k.minX, k.maxX), nz = clamp(p.z, k.minZ, k.maxZ);
      const dx = p.x - nx, dz = p.z - nz;
      const d2 = dx * dx + dz * dz;
      if (d2 >= radius * radius) continue;
      if (d2 > 1e-8) {
        const d = Math.sqrt(d2);
        p.x = nx + (dx / d) * radius;
        p.z = nz + (dz / d) * radius;
      } else { // centre is inside the box: leave by the nearest face
        const l = p.x - k.minX, r = k.maxX - p.x, t = p.z - k.minZ, b = k.maxZ - p.z;
        const m = Math.min(l, r, t, b);
        if (m === l) p.x = k.minX - radius; else if (m === r) p.x = k.maxX + radius;
        else if (m === t) p.z = k.minZ - radius; else p.z = k.maxZ + radius;
      }
    }
  }

  // Move with sliding. Sub-steps stop fast moves (dodge-roll) from tunnelling through thin walls.
  function move(p, dx, dz, radius) {
    const steps = Math.max(1, Math.ceil(Math.hypot(dx, dz) / 0.3));
    dx /= steps; dz /= steps;
    for (let i = 0; i < steps; i++) {
      if (canStand(p.x + dx, p.z)) p.x += dx;
      if (canStand(p.x, p.z + dz)) p.z += dz;
      resolveCircle(p, radius);
    }
  }

  // First hit of segment A->B against sight-blocking boxes, as t in [0,1]. Returns 2 when clear.
  function segmentT(ax, az, bx, bz) {
    const dx = bx - ax, dz = bz - az;
    let best = 2;
    for (const k of colliders) {
      if (!k.blocksSight) continue;
      let t0 = 0, t1 = 1;
      if (Math.abs(dx) < 1e-9) { if (ax < k.minX || ax > k.maxX) continue; }
      else {
        let a = (k.minX - ax) / dx, b = (k.maxX - ax) / dx;
        if (a > b) [a, b] = [b, a];
        t0 = Math.max(t0, a); t1 = Math.min(t1, b);
        if (t0 > t1) continue;
      }
      if (Math.abs(dz) < 1e-9) { if (az < k.minZ || az > k.maxZ) continue; }
      else {
        let a = (k.minZ - az) / dz, b = (k.maxZ - az) / dz;
        if (a > b) [a, b] = [b, a];
        t0 = Math.max(t0, a); t1 = Math.min(t1, b);
        if (t0 > t1) continue;
      }
      if (t0 < best) best = t0;
    }
    return best;
  }
  const lineOfSight = (ax, az, bx, bz) => segmentT(ax, az, bx, bz) > 1;

  // Cover points: spots hugging each sight-blocking box. Bots pick one that hides them from the player.
  const coverPoints = [];
  for (const k of colliders) {
    if (!k.blocksSight) continue;
    const off = 0.95;
    const add = (x, z) => {
      if (!canStand(x, z)) return;
      if (colliders.some((o) => x > o.minX - 0.4 && x < o.maxX + 0.4 && z > o.minZ - 0.4 && z < o.maxZ + 0.4)) return;
      coverPoints.push({ x, z });
    };
    for (let x = k.minX + 0.6; x <= k.maxX - 0.5; x += 2.2) { add(x, k.minZ - off); add(x, k.maxZ + off); }
    for (let z = k.minZ + 0.6; z <= k.maxZ - 0.5; z += 2.2) { add(k.minX - off, z); add(k.maxX + off, z); }
  }

  return { heightAt, canStand, colliders, coverPoints, resolveCircle, move, segmentT, lineOfSight };
}
