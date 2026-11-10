import * as THREE from 'three';
import { angleDiff, lerpAngle, damp, clamp } from '../engine/mathx.js';

// Stealth guard. Unlike the combat bots, a guard NEVER leaves its route:
//   - walks a fixed loop of waypoints: { x, z, wait?: seconds, look?: angle }
//   - carries a torch: the lit cone drawn on the ground is exactly what it can see
//   - stops and turns toward a noise (running nearby) or toward a glimpse of the player
// guard.suspicion goes 0 -> 1 while the player is seen. At 1 the mission treats the player as spotted.

const RADIUS = 0.4;
const SEGS = 12;                 // cone resolution
const LIT_RANGE = 20, LIT_FOV = 1.9; // how well a guard sees someone standing under a street lamp

let geo = null;
const geometry = () => geo ??= {
  body: new THREE.CapsuleGeometry(0.3, 0.75, 4, 8),
  head: new THREE.SphereGeometry(0.21, 8, 6),
  torch: new THREE.SphereGeometry(0.09, 6, 5),
  mark: new THREE.OctahedronGeometry(0.14, 0),
};

export function createGuard(game, { route, start = 0, speed = 1.5, torchRange = 10, torchFov = 1.2 }) {
  const g = geometry();
  const { world } = game;
  const bodyMat = new THREE.MeshLambertMaterial({ color: 0x15171c });
  const sashMat = new THREE.MeshLambertMaterial({ color: 0x5c1f1f });
  const markMat = new THREE.MeshBasicMaterial({ color: 0xf2c14e, fog: false });
  const root = new THREE.Group();
  const body = new THREE.Mesh(g.body, bodyMat); body.position.y = 0.95;
  const head = new THREE.Mesh(g.head, bodyMat); head.position.y = 1.66;
  const sash = new THREE.Mesh(new THREE.CylinderGeometry(0.315, 0.315, 0.12, 8), sashMat); sash.position.y = 1.0;
  const torch = new THREE.Mesh(g.torch, new THREE.MeshBasicMaterial({ color: 0xfff1c9, fog: false })); torch.position.set(0.3, 1.15, 0.38);
  const mark = new THREE.Mesh(g.mark, markMat); mark.position.y = 2.3; mark.visible = false;
  root.add(body, head, sash, torch, mark);
  root.traverse((o) => { if (o.isMesh && o !== torch && o !== mark) o.castShadow = true; });
  game.scene.add(root);

  // Vision cone on the ground: a fan with two rings, re-built every frame so walls cut it.
  const coneGeo = new THREE.BufferGeometry();
  const conePos = new Float32Array((1 + (SEGS + 1) * 2) * 3);
  coneGeo.setAttribute('position', new THREE.BufferAttribute(conePos, 3));
  const idx = [];
  for (let j = 0; j < SEGS; j++) {
    const a = 1 + j * 2, b = a + 2;        // inner ring
    idx.push(0, a, b, a, a + 1, b, a + 1, b + 1, b);
  }
  coneGeo.setIndex(idx);
  const coneMat = new THREE.MeshBasicMaterial({ color: 0xffe08a, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending,
    depthWrite: false, fog: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 });
  const cone = new THREE.Mesh(coneGeo, coneMat);
  cone.frustumCulled = false;
  game.scene.add(cone);
  const calm = new THREE.Color(0xffe08a), hot = new THREE.Color(0xff4a3d);

  const first = route[start % route.length];
  const pos = new THREE.Vector3(first.x, world.heightAt(first.x, first.z), first.z);
  const guard = { pos, root, facing: 0, suspicion: 0, seesPlayer: false, state: 'patrol' };
  let wp = (start + 1) % route.length, waitT = 0, lookT = 0, faceTarget = 0;
  faceTarget = guard.facing = Math.atan2(route[wp].x - pos.x, route[wp].z - pos.z);

  // Noise: a guard does not leave the route, it only stops and looks.
  const offNoise = game.events.on('noise', ({ pos: where, radius }) => {
    const d = Math.hypot(where.x - pos.x, where.z - pos.z);
    if (d > radius || d < 0.01) return;
    lookT = 2.2;
    faceTarget = Math.atan2(where.x - pos.x, where.z - pos.z);
  });

  function updateCone() {
    const y0 = pos.y + 0.15;
    conePos[0] = pos.x; conePos[1] = y0; conePos[2] = pos.z;
    for (let j = 0; j <= SEGS; j++) {
      const a = guard.facing - torchFov / 2 + (j / SEGS) * torchFov;
      const dx = Math.sin(a), dz = Math.cos(a);
      const t = Math.min(1, world.segmentT(pos.x, pos.z, pos.x + dx * torchRange, pos.z + dz * torchRange));
      const len = torchRange * t;
      for (let k = 0; k < 2; k++) {
        const r = len * (k ? 1 : 0.5), x = pos.x + dx * r, z = pos.z + dz * r;
        conePos.set([x, world.heightAt(x, z) + 0.15, z], (1 + j * 2 + k) * 3);
      }
    }
    coneGeo.attributes.position.needsUpdate = true;
  }

  guard.update = (dt) => {
    // ---- senses ----
    const p = game.player;
    const dx = p.pos.x - pos.x, dz = p.pos.z - pos.z;
    const dist = Math.hypot(dx, dz), angTo = Math.atan2(dx, dz);
    const off = Math.abs(angleDiff(guard.facing, angTo));
    let rate = 0;
    if (!p.health.dead && dist < LIT_RANGE + 2 && world.lineOfSight(pos.x, pos.z, p.pos.x, p.pos.z)) {
      if (dist < torchRange && off < torchFov / 2) rate = dist < 4 ? 2.6 : 1.4;    // in the torch beam: about 0.4 s close up, 0.7 s further away
      else if (dist < LIT_RANGE && off < LIT_FOV / 2 && world.isLit(p.pos.x, p.pos.z)) rate = 1.0; // under a lamp
    }
    if (dist < 1.5) rate = Math.max(rate, 3.5); // bumped into the guard
    guard.seesPlayer = rate > 0;
    guard.suspicion = clamp(guard.suspicion + (rate > 0 ? rate : -0.45) * dt, 0, 1);

    // ---- movement: route only ----
    if (guard.seesPlayer && guard.suspicion > 0.25) {
      guard.state = 'alert';                 // stop and stare
      faceTarget = angTo;
    } else if (lookT > 0) {
      guard.state = 'listen';
      lookT -= dt;
    } else if (waitT > 0) {
      guard.state = 'wait';
      waitT -= dt;
    } else {
      guard.state = 'patrol';
      const target = route[wp];
      const tx = target.x - pos.x, tz = target.z - pos.z, d = Math.hypot(tx, tz);
      if (d < 0.35) {
        waitT = target.wait ?? 0.6;
        if (target.look !== undefined) faceTarget = target.look;
        wp = (wp + 1) % route.length;
      } else {
        world.move(pos, tx / d * speed * dt, tz / d * speed * dt, RADIUS);
        faceTarget = Math.atan2(tx, tz);
      }
    }

    guard.facing = lerpAngle(guard.facing, faceTarget, damp(guard.state === 'alert' ? 6 : 3.5, dt));
    pos.y += (world.heightAt(pos.x, pos.z) - pos.y) * damp(20, dt);
    root.position.copy(pos);
    root.rotation.y = guard.facing;
    mark.visible = guard.suspicion > 0.2 || guard.state === 'listen';
    mark.rotation.y += dt * 3;
    markMat.color.copy(calm).lerp(hot, guard.suspicion);
    coneMat.color.copy(calm).lerp(hot, guard.suspicion);
    coneMat.opacity = 0.2 + guard.suspicion * 0.2;
    updateCone();
  };

  guard.dispose = () => {
    offNoise();
    game.scene.remove(root, cone);
    bodyMat.dispose(); sashMat.dispose(); markMat.dispose(); torch.material.dispose(); sash.geometry.dispose();
    coneGeo.dispose(); coneMat.dispose();
  };

  guard.update(0);
  return guard;
}
