import * as THREE from 'three';
import { Health } from './health.js';
import { SHAKTIS } from './shaktis.js';
import { angleDiff, lerpAngle, damp } from './mathx.js';

const WALK_SPEED = 3.4, RUN_SPEED = 6.4;
const ROLL_SPEED = 11, ROLL_TIME = 0.42, ROLL_COOLDOWN = 0.9;
const RADIUS = 0.4;
const ATTACK_DAMAGE = 25, ATTACK_RANGE = 2.5, ATTACK_ARC = 1.1, ATTACK_TIME = 0.28, ATTACK_COOLDOWN = 0.42;
const BURST_DAMAGE = 70, BURST_RANGE = 8, BURST_CHARGE_PER_DAMAGE = 0.8;

// Third-person character controller + the player's combat actions.
// Placeholder model: capsule body, sphere head, an oar as the melee weapon.
export function createPlayer(game) {
  const lambert = (color) => new THREE.MeshLambertMaterial({ color });
  const root = new THREE.Group();   // feet position + facing
  const tilt = new THREE.Group();   // spins around the body centre during a roll
  const model = new THREE.Group();
  tilt.position.y = 0.9; model.position.y = -0.9;
  root.add(tilt); tilt.add(model);

  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 0.75, 4, 8), lambert(0x1f8fa3));
  body.position.y = 0.95;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 10, 8), lambert(0xb9805a));
  head.position.y = 1.68;
  const nose = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.08, 0.14), lambert(0xb9805a));
  nose.position.set(0, 1.66, 0.22);
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.225, 0.225, 0.07, 10), lambert(0xe8a33d));
  band.position.y = 1.77;
  const oar = new THREE.Group();
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.5, 0.06), lambert(0x8a6a45));
  shaft.position.y = 0.45;
  const blade = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.5, 0.04), lambert(0xa9824f));
  blade.position.y = 1.3;
  oar.add(shaft, blade);
  oar.position.set(0.38, 1.0, 0.05);
  model.add(body, head, nose, band, oar);
  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  game.scene.add(root);

  const health = new Health(100);
  const pos = new THREE.Vector3();
  const player = {
    pos, health, root,
    facing: Math.PI, burst: 0, currentShakti: 0,
    shaktiCooldowns: SHAKTIS.map(() => 0),
    rolling: false, running: false, moving: false,
  };
  let rollT = 0, rollCd = 0, rollX = 0, rollZ = 0;
  let attackT = 0, attackCd = 0, stepT = 0, toolCd = 0;

  health.onDeath = () => { game.onPlayerDown(); };

  const unlocked = (i) => game.progress.unlockedShaktis.includes(SHAKTIS[i].id);

  player.reset = (x, z, facing = Math.PI) => {
    health.reset(100 + 10 * (game.progress.playerLevel - 1));
    pos.set(x, game.world.heightAt(x, z), z);
    player.facing = facing;
    player.burst = 0;
    player.shaktiCooldowns.fill(0);
    rollT = rollCd = attackT = attackCd = 0;
    player.rolling = false;
    tilt.rotation.set(0, 0, 0); tilt.scale.setScalar(1);
    root.visible = true;
    sync();
  };

  player.selectShakti = (i) => {
    if (i === player.currentShakti) return;
    if (!unlocked(i)) { game.audio.play('denied'); return; }
    player.currentShakti = i;
    game.audio.play('ui');
  };

  player.addBurst = (damageDealt) => {
    const before = player.burst;
    player.burst = Math.min(100, player.burst + damageDealt * BURST_CHARGE_PER_DAMAGE);
    if (before < 100 && player.burst >= 100) game.audio.play('burstReady');
  };

  const livingBots = () => game.bots.filter((b) => !b.health.dead);
  const angleTo = (b) => Math.atan2(b.pos.x - pos.x, b.pos.z - pos.z);
  const distTo = (b) => Math.hypot(b.pos.x - pos.x, b.pos.z - pos.z);

  // Aim along the camera, snapping gently to a visible bot near the crosshair direction.
  function aimAngle() {
    const f = game.rig.forward();
    const camAngle = Math.atan2(f.x, f.z);
    let best = null, bestScore = 0.4;
    for (const b of livingBots()) {
      const d = distTo(b);
      if (d > 26 || !game.world.lineOfSight(pos.x, pos.z, b.pos.x, b.pos.z)) continue;
      const off = Math.abs(angleDiff(camAngle, angleTo(b)));
      if (off < bestScore) { bestScore = off; best = b; }
    }
    return best ? angleTo(best) : camAngle;
  }

  function areaDamage(range, damage, push = 6) {
    for (const b of livingBots()) {
      const d = distTo(b);
      if (d < range) game.damageBot(b, damage, { x: (b.pos.x - pos.x) / (d || 1) * push, z: (b.pos.z - pos.z) / (d || 1) * push });
    }
  }

  function attack() {
    attackT = ATTACK_TIME; attackCd = ATTACK_COOLDOWN;
    // Soft lock: turn to the nearest close bot so melee is usable on touch screens.
    let near = null, nd = 3.2;
    for (const b of livingBots()) { const d = distTo(b); if (d < nd) { nd = d; near = b; } }
    if (near) player.facing = angleTo(near);
    for (const b of livingBots()) {
      if (distTo(b) < ATTACK_RANGE && Math.abs(angleDiff(player.facing, angleTo(b))) < ATTACK_ARC) {
        game.damageBot(b, ATTACK_DAMAGE, { x: Math.sin(player.facing) * 3, z: Math.cos(player.facing) * 3 });
      }
    }
    game.audio.play('attack');
    game.noise(pos, 10);
  }

  function useShakti() {
    const i = player.currentShakti, s = SHAKTIS[i];
    if (!unlocked(i)) { game.audio.play('denied'); return; }
    if (player.shaktiCooldowns[i] > 0) return;
    player.shaktiCooldowns[i] = s.cooldown;
    const a = aimAngle(), ax = Math.sin(a), az = Math.cos(a);
    if (s.kind !== 'heal') player.facing = a;
    const chest = new THREE.Vector3(pos.x, pos.y + 1.2, pos.z);

    if (s.kind === 'cone') {            // wind gust: light damage, big push
      for (const b of livingBots()) {
        if (distTo(b) < s.range && Math.abs(angleDiff(a, angleTo(b))) < 0.7) {
          game.damageBot(b, s.damage, { x: ax * s.push, z: az * s.push });
        }
      }
      game.combat.ring({ x: pos.x + ax * 2.5, y: pos.y, z: pos.z + az * 2.5 }, s.color, s.range * 0.6, 0.35);
    } else if (s.kind === 'projectile') {
      game.combat.fire({ x: chest.x + ax * 0.6, y: chest.y, z: chest.z + az * 0.6, dx: ax, dz: az,
        speed: s.speed, damage: s.damage, team: 'player', color: s.color, radius: 0.7 });
    } else if (s.kind === 'heal') {
      health.heal(s.amount);
      game.combat.ring(pos, s.color, 2.5, 0.5);
    } else if (s.kind === 'bolt') {     // instant hit on the best target in front
      let best = null, bd = s.range;
      for (const b of livingBots()) {
        const d = distTo(b);
        if (d < bd && Math.abs(angleDiff(a, angleTo(b))) < 0.6 && game.world.lineOfSight(pos.x, pos.z, b.pos.x, b.pos.z)) { bd = d; best = b; }
      }
      const end = best ? new THREE.Vector3(best.pos.x, best.pos.y + 1.1, best.pos.z)
                       : new THREE.Vector3(chest.x + ax * s.range, chest.y, chest.z + az * s.range);
      game.combat.beam(chest, end, s.color);
      if (best) game.damageBot(best, s.damage);
    } else if (s.kind === 'aoe') {
      areaDamage(s.range, s.damage);
      game.combat.ring(pos, s.color, s.range, 0.45);
    }
    game.audio.play('shakti');
    game.noise(pos, 16);
    game.events.emit('shakti', s);
  }

  function useBurst() {
    if (player.burst < 100) { game.audio.play('denied'); return; }
    player.burst = 0;
    areaDamage(BURST_RANGE, BURST_DAMAGE, 12);
    game.combat.ring(pos, 0xfff1c9, BURST_RANGE, 0.6);
    game.combat.ring(pos, 0xe8a33d, BURST_RANGE * 0.6, 0.45);
    game.audio.play('burst');
    game.noise(pos, 25);
    game.events.emit('burst');
  }

  // Tool slot. Placeholder tool: a compass ping that highlights the objective.
  function useTool() {
    if (toolCd > 0) return;
    toolCd = 1.5;
    game.combat.ring(pos, 0xe8a33d, 4, 0.6);
    game.audio.play('tool');
    game.events.emit('tool');
  }

  function sync() {
    root.position.copy(pos);
    root.rotation.y = player.facing;
  }

  player.update = (dt) => {
    const { input, world, rig } = game;
    rollCd -= dt; attackCd -= dt; toolCd -= dt;
    for (let i = 0; i < 5; i++) player.shaktiCooldowns[i] = Math.max(0, player.shaktiCooldowns[i] - dt);
    if (health.dead) return;

    for (let i = 0; i < 5; i++) if (input.take(`shakti${i + 1}`)) player.selectShakti(i);

    // Camera-relative movement direction.
    const m = input.move();
    const mag = Math.min(1, Math.hypot(m.x, m.y));
    const f = rig.forward(), r = rig.right();
    let dx = f.x * m.y + r.x * m.x, dz = f.z * m.y + r.z * m.x;
    const len = Math.hypot(dx, dz);
    if (len > 1e-4) { dx /= len; dz /= len; }
    player.moving = false;

    if (rollT > 0) {
      rollT -= dt;
      world.move(pos, rollX * ROLL_SPEED * dt, rollZ * ROLL_SPEED * dt, RADIUS);
      const k = 1 - Math.max(0, rollT) / ROLL_TIME;
      tilt.rotation.x = k * Math.PI * 2;
      tilt.scale.setScalar(0.78);
      if (rollT <= 0) {
        player.rolling = false; health.invulnerable = false;
        tilt.rotation.x = 0; tilt.scale.setScalar(1);
      }
    } else {
      if (input.take('dodge') && rollCd <= 0) {
        rollX = mag > 0.1 ? dx : Math.sin(player.facing);
        rollZ = mag > 0.1 ? dz : Math.cos(player.facing);
        player.facing = Math.atan2(rollX, rollZ);
        rollT = ROLL_TIME; rollCd = ROLL_COOLDOWN;
        player.rolling = true; health.invulnerable = true; // i-frames
        game.audio.play('dodge');
        game.noise(pos, 6);
      } else if (mag > 0.1) {
        player.running = input.run();
        const speed = player.running ? RUN_SPEED : WALK_SPEED * Math.max(mag, 0.4);
        world.move(pos, dx * speed * dt, dz * speed * dt, RADIUS);
        player.facing = lerpAngle(player.facing, Math.atan2(dx, dz), damp(14, dt));
        player.moving = true;
        stepT -= dt * (player.running ? 1.6 : 1);
        if (stepT <= 0) { stepT = 0.42; game.audio.play('step'); game.noise(pos, player.running ? 9 : 3.5); }
      }
      if (!player.rolling) {
        if (input.take('attack') && attackCd <= 0) attack();
        if (input.take('shakti')) useShakti();
        if (input.take('burst')) useBurst();
        if (input.take('tool')) useTool();
      }
    }

    // Stick to the terrain.
    pos.y += (world.heightAt(pos.x, pos.z) - pos.y) * damp(20, dt);

    // Placeholder animation: oar swing + a small walk bob.
    attackT = Math.max(0, attackT - dt);
    const swing = attackT > 0 ? 1 - attackT / ATTACK_TIME : 0;
    oar.rotation.x = attackT > 0 ? -1.1 + swing * 2.9 : -0.25;
    model.position.y = -0.9 + (player.moving ? Math.abs(Math.sin(performance.now() * (player.running ? 0.016 : 0.01))) * 0.06 : 0);
    sync();
  };

  return player;
}
