import * as THREE from 'three';
import { distSegPoint } from './mathx.js';

// Projectiles (pooled) and simple placeholder effects (rings, beams).
export function createCombat(game) {
  const { scene } = game;
  const shotGeo = new THREE.SphereGeometry(0.13, 8, 6);
  const ringGeo = new THREE.RingGeometry(0.82, 1, 32).rotateX(-Math.PI / 2);
  const beamGeo = new THREE.BoxGeometry(0.1, 0.1, 1);
  const pool = [], shots = [], effects = [];

  function fire({ x, y, z, dx, dy = 0, dz, speed, damage, team, color, radius = 0.5, life = 2 }) {
    const mesh = pool.pop() || new THREE.Mesh(shotGeo, new THREE.MeshBasicMaterial());
    mesh.material.color.setHex(color);
    mesh.position.set(x, y, z);
    scene.add(mesh);
    shots.push({ mesh, dx, dy, dz, speed, damage, team, radius, life });
  }

  function effect(mesh, duration, tick) {
    scene.add(mesh);
    effects.push({ mesh, duration, t: 0, tick });
  }

  // Expanding ground ring: used for hits, area moves and pings.
  function ring(pos, color, radius, duration = 0.4) {
    const mesh = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
      color, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    mesh.position.set(pos.x, pos.y + 0.15, pos.z);
    effect(mesh, duration, (k) => { mesh.scale.setScalar(0.2 + radius * k); mesh.material.opacity = 1 - k; });
  }

  // Straight flash between two points (lightning placeholder).
  function beam(a, b, color, duration = 0.16) {
    const mesh = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({ color, transparent: true }));
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.lookAt(b);
    mesh.scale.z = a.distanceTo(b);
    effect(mesh, duration, (k) => { mesh.material.opacity = 1 - k; });
  }

  function update(dt) {
    for (let i = shots.length - 1; i >= 0; i--) {
      const s = shots[i], m = s.mesh;
      const ox = m.position.x, oz = m.position.z;
      const nx = ox + s.dx * s.speed * dt, nz = oz + s.dz * s.speed * dt;
      const ny = m.position.y + s.dy * s.speed * dt;
      let done = (s.life -= dt) <= 0;

      if (!done && game.world.segmentT(ox, oz, nx, nz) <= 1) done = true;       // hit a wall
      if (!done && ny < game.world.heightAt(nx, nz)) done = true;               // hit the ground
      if (!done) {
        if (s.team === 'bot') {
          const p = game.player;
          if (!p.health.dead && Math.abs(ny - (p.pos.y + 1)) < 1.4 &&
              distSegPoint(ox, oz, nx, nz, p.pos.x, p.pos.z) < s.radius) {
            game.damagePlayer(s.damage);
            done = true;
          }
        } else {
          for (const bot of game.bots) {
            if (bot.health.dead) continue;
            if (distSegPoint(ox, oz, nx, nz, bot.pos.x, bot.pos.z) < s.radius + 0.2) {
              game.damageBot(bot, s.damage);
              done = true;
              break;
            }
          }
        }
      }
      if (done) {
        ring({ x: nx, y: ny - 0.15, z: nz }, m.material.color.getHex(), 0.8, 0.2);
        scene.remove(m);
        pool.push(m);
        shots.splice(i, 1);
      } else m.position.set(nx, ny, nz);
    }

    for (let i = effects.length - 1; i >= 0; i--) {
      const e = effects[i];
      e.t += dt;
      const k = Math.min(1, e.t / e.duration);
      e.tick(k);
      if (k >= 1) { scene.remove(e.mesh); e.mesh.material.dispose(); effects.splice(i, 1); }
    }
  }

  function clear() {
    for (const s of shots) { scene.remove(s.mesh); pool.push(s.mesh); }
    shots.length = 0;
    for (const e of effects) { scene.remove(e.mesh); e.mesh.material.dispose(); }
    effects.length = 0;
  }

  return { fire, ring, beam, update, clear, get shotCount() { return shots.length; } };
}
