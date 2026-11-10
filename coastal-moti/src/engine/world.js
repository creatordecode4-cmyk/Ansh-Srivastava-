import * as THREE from 'three';
import { clamp, seededRandom } from './mathx.js';

// The world loads one LEVEL at a time. A level (see src/levels/) is a plain object:
//
//   { id, env, heightAt(x, z), build(b) -> handles }
//
// build() receives a builder `b` with helpers to add terrain, instanced props and colliders.
// Whatever build() returns is available as world.level (for example the lighthouse controls).
// The collision API (move, lineOfSight, ...) is the same for every level.

const MIN_STAND_HEIGHT = -0.55; // deeper water than this blocks movement

export function createWorld(scene) {
  let heightFn = () => 0;
  let owned = [];
  const dummy = new THREE.Object3D();

  const world = {
    id: null,
    level: {},        // handles returned by the level's build()
    colliders: [],    // axis-aligned boxes on the XZ plane
    coverPoints: [],
    lights: [],       // lit ground circles { x, z, r }: stealth uses them
    heightAt: (x, z) => heightFn(x, z),
    canStand: (x, z) => heightFn(x, z) > MIN_STAND_HEIGHT,
  };

  // ---- builder: what a level uses to construct itself ----------------------
  const builder = {
    rand: Math.random,
    heightAt: (x, z) => heightFn(x, z),

    add(object) { scene.add(object); owned.push(object); return object; },

    collider(cx, cz, sx, sz, height, blocksSight) {
      const col = { minX: cx - sx / 2, maxX: cx + sx / 2, minZ: cz - sz / 2, maxZ: cz + sz / 2,
        cx, cz, y: heightFn(cx, cz), height, blocksSight };
      world.colliders.push(col);
      return col;
    },

    // Height-field terrain. colorAt(height, x, z, outColor) paints each vertex.
    terrain({ size = 180, segments = 90, colorAt }) {
      const geo = new THREE.PlaneGeometry(size, size, segments, segments);
      geo.rotateX(-Math.PI / 2);
      const pos = geo.attributes.position;
      const colors = new Float32Array(pos.count * 3);
      const c = new THREE.Color();
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i), z = pos.getZ(i), h = heightFn(x, z);
        pos.setY(i, h);
        colorAt(h, x, z, c);
        colors.set([c.r, c.g, c.b], i * 3);
      }
      geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geo.computeVertexNormals();
      const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }));
      mesh.receiveShadow = true;
      mesh.name = 'terrain';
      return builder.add(mesh);
    },

    // One draw call for many copies. place(item, dummy) positions each copy.
    instanced(geometry, material, items, place, shadows = true) {
      if (typeof material === 'number') material = new THREE.MeshLambertMaterial({ color: material, flatShading: true });
      const mesh = new THREE.InstancedMesh(geometry, material, items.length);
      items.forEach((item, i) => {
        dummy.position.set(0, 0, 0); dummy.rotation.set(0, 0, 0); dummy.scale.set(1, 1, 1);
        place(item, dummy);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.castShadow = mesh.receiveShadow = shadows;
      mesh.frustumCulled = false;
      return builder.add(mesh);
    },

    // Solid boxes with colliders: [x, z, sizeX, sizeZ, height]. Tall ones (>= 1.8 m) block sight.
    boxes(color, list) {
      return builder.instanced(new THREE.BoxGeometry(1, 1, 1), color, list, ([x, z, sx, sz, h], d) => {
        const col = builder.collider(x, z, sx, sz, h, h >= 1.8);
        d.position.set(x, col.y - 1.5 + (h + 1.5) / 2, z); // sunk 1.5 m so slopes leave no gap
        d.scale.set(sx, h + 1.5, sz);
      });
    },

    // A soft lit circle on the ground that follows the terrain. Registers a stealth light zone.
    groundGlow(cx, cz, radius, color, strength = 0.5, register = true) {
      const RINGS = 4, SEGS = 24;
      const pos = [cx, heightFn(cx, cz) + 0.12, cz], col = [], idx = [];
      const base = new THREE.Color(color);
      col.push(base.r * strength, base.g * strength, base.b * strength);
      for (let i = 1; i <= RINGS; i++) {
        const k = strength * (1 - i / RINGS);
        for (let j = 0; j < SEGS; j++) {
          const a = (j / SEGS) * Math.PI * 2, r = radius * (i / RINGS);
          const x = cx + Math.cos(a) * r, z = cz + Math.sin(a) * r;
          pos.push(x, heightFn(x, z) + 0.12, z);
          col.push(base.r * k, base.g * k, base.b * k);
        }
      }
      const ring = (i, j) => 1 + (i - 1) * SEGS + (j % SEGS);
      for (let j = 0; j < SEGS; j++) {
        idx.push(0, ring(1, j + 1), ring(1, j));
        for (let i = 1; i < RINGS; i++) idx.push(ring(i, j), ring(i, j + 1), ring(i + 1, j), ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j));
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      geo.setIndex(idx);
      const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true,
        blending: THREE.AdditiveBlending, depthWrite: false, fog: false, side: THREE.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
      if (register) world.lights.push({ x: cx, z: cz, r: radius });
      return builder.add(mesh);
    },
  };

  function unload() {
    for (const obj of owned) {
      scene.remove(obj);
      obj.traverse((o) => {
        o.geometry?.dispose();
        if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose()); else o.material?.dispose();
      });
    }
    owned = [];
    world.colliders.length = 0;
    world.coverPoints.length = 0;
    world.lights.length = 0;
    world.level = {};
  }

  world.load = (def) => {
    unload();
    world.id = def.id;
    heightFn = def.heightAt;
    builder.rand = seededRandom(7); // same layout every run
    world.level = def.build(builder) || {};
    buildCoverPoints();
  };
  world.update = (dt, time) => world.level.update?.(dt, time);

  // ---- collision API -------------------------------------------------------
  // Push a circle (p.x, p.z, radius) out of every box it overlaps.
  world.resolveCircle = (p, radius) => {
    for (const k of world.colliders) {
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
  };

  // Move with sliding. Sub-steps stop fast moves (dodge-roll) from tunnelling through thin walls.
  world.move = (p, dx, dz, radius) => {
    const steps = Math.max(1, Math.ceil(Math.hypot(dx, dz) / 0.3));
    dx /= steps; dz /= steps;
    for (let i = 0; i < steps; i++) {
      if (world.canStand(p.x + dx, p.z)) p.x += dx;
      if (world.canStand(p.x, p.z + dz)) p.z += dz;
      world.resolveCircle(p, radius);
    }
  };

  // First hit of segment A->B against sight-blocking boxes, as t in [0,1]. Returns 2 when clear.
  world.segmentT = (ax, az, bx, bz) => {
    const dx = bx - ax, dz = bz - az;
    let best = 2;
    for (const k of world.colliders) {
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
  };
  world.lineOfSight = (ax, az, bx, bz) => world.segmentT(ax, az, bx, bz) > 1;

  // Is this spot inside a lit circle (street lamp)? Guards see much further there.
  world.isLit = (x, z) => world.lights.some((l) => Math.hypot(x - l.x, z - l.z) < l.r);

  // Cover points: spots hugging each sight-blocking box. Bots pick one that hides them from the player.
  function buildCoverPoints() {
    for (const k of world.colliders) {
      if (!k.blocksSight) continue;
      const off = 0.95;
      const add = (x, z) => {
        if (!world.canStand(x, z)) return;
        if (world.colliders.some((o) => x > o.minX - 0.4 && x < o.maxX + 0.4 && z > o.minZ - 0.4 && z < o.maxZ + 0.4)) return;
        world.coverPoints.push({ x, z });
      };
      for (let x = k.minX + 0.6; x <= k.maxX - 0.5; x += 2.2) { add(x, k.minZ - off); add(x, k.maxZ + off); }
      for (let z = k.minZ + 0.6; z <= k.maxZ - 0.5; z += 2.2) { add(k.minX - off, z); add(k.maxX + off, z); }
    }
  }

  return world;
}
