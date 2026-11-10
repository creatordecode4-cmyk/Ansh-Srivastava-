import * as THREE from 'three';
import { Health } from '../engine/health.js';
import { angleDiff, lerpAngle, damp } from '../engine/mathx.js';

// Bot AI framework: a small state machine.
//   patrol -> (hears noise) investigate -> (sees player) chase -> shoot <-> cover -> ... -> dead
// Senses: a vision cone with line-of-sight checks, plus hearing (noise events from the player).
// Movement is straight-line steering with a sidestep when stuck. There is no path-finding yet.

const VIEW_RANGE = 24, FOV = Math.PI * 0.6;           // 108 degree cone
const SHOOT_RANGE = 17, SHOT_DAMAGE = 8, SHOT_SPEED = 24;
const RADIUS = 0.4;
const SPEED = { patrol: 1.7, investigate: 2.6, chase: 3.8, cover: 4.4, strafe: 1.4 };
const STATE_COLOR = { patrol: 0x9aa3ad, investigate: 0xf2c14e, chase: 0xe5484d, shoot: 0xe5484d, cover: 0xe58a48, dead: 0x333333 };

let geo = null;
function geometry() {
  return geo ??= {
    body: new THREE.CapsuleGeometry(0.3, 0.75, 4, 8),
    head: new THREE.SphereGeometry(0.21, 8, 6),
    gun: new THREE.BoxGeometry(0.1, 0.12, 0.6),
    mark: new THREE.OctahedronGeometry(0.13, 0),
    bar: new THREE.PlaneGeometry(0.9, 0.09),
  };
}

export function createBot(game, { x, z, patrol = [], hp = 60 }) {
  const g = geometry();
  const { world } = game;
  const bodyMat = new THREE.MeshLambertMaterial({ color: 0x3b3f4a });
  const markMat = new THREE.MeshBasicMaterial({ color: STATE_COLOR.patrol });
  const root = new THREE.Group(), model = new THREE.Group();
  const body = new THREE.Mesh(g.body, bodyMat); body.position.y = 0.95;
  const head = new THREE.Mesh(g.head, bodyMat); head.position.y = 1.66;
  const gun = new THREE.Mesh(g.gun, bodyMat); gun.position.set(0.26, 1.2, 0.35);
  model.add(body, head, gun);
  model.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  const mark = new THREE.Mesh(g.mark, markMat); mark.position.y = 2.25;   // shows the AI state
  const barBack = new THREE.Mesh(g.bar, new THREE.MeshBasicMaterial({ color: 0x1a1a1a, depthTest: false }));
  const barFill = new THREE.Mesh(g.bar, new THREE.MeshBasicMaterial({ color: 0xe5484d, depthTest: false }));
  const bar = new THREE.Group(); bar.add(barBack, barFill); bar.position.y = 2.0; bar.visible = false;
  barFill.position.z = 0.001; barFill.renderOrder = 2; barBack.renderOrder = 1;
  root.add(model, mark, bar);
  game.scene.add(root);

  const pos = new THREE.Vector3(x, world.heightAt(x, z), z);
  const health = new Health(hp);
  const lastSeen = new THREE.Vector3(), heardPos = new THREE.Vector3(), knock = new THREE.Vector3();
  const bot = { pos, health, root, state: 'patrol', facing: 0, sees: false, awareness: 0, remove: false };

  let faceTarget = 0, wp = 0, waitT = 0, lookT = 0, unseenT = 0;
  let shootCd = 1, shots = 0, strafeDir = 1, strafeT = 0;
  let coverPt = null, coverT = 0, stuckT = 0, avoidT = 0, avoidSide = 1, flashT = 0, deadT = 0;

  const inCombat = () => bot.state === 'chase' || bot.state === 'shoot' || bot.state === 'cover';
  function setState(s) {
    if (bot.state === s) return;
    bot.state = s;
    markMat.color.setHex(STATE_COLOR[s]);
  }

  function engage() {
    if (!inCombat()) game.audio.play('alert');
    setState('chase');
    // Call nearby bots for help.
    for (const other of game.bots) {
      if (other !== bot && !other.health.dead && other.pos.distanceTo(pos) < 14) other.alert(lastSeen);
    }
  }
  bot.alert = (where) => {
    if (health.dead || inCombat()) return;
    lastSeen.copy(where); unseenT = 0; bot.awareness = 1;
    setState('chase');
  };

  // Hearing: the player's steps, attacks and Shaktis call this through game.noise().
  bot.hear = (where, radius) => {
    if (health.dead || pos.distanceTo(where) > radius) return;
    if (inCombat()) { if (!bot.sees) lastSeen.copy(where); return; }
    heardPos.copy(where); lookT = 0;
    setState('investigate');
  };

  bot.push = (vx, vz) => { knock.x += vx; knock.z += vz; };

  health.onDamage = () => {
    flashT = 0.12;
    bar.visible = true;
    barFill.scale.x = Math.max(0.001, health.ratio);
    barFill.position.x = -0.45 * (1 - health.ratio);
    if (!inCombat()) { lastSeen.copy(game.player.pos); unseenT = 0; bot.awareness = 1; engage(); }
    else if (bot.state === 'shoot' && (health.ratio < 0.5 || Math.random() < 0.4)) tryCover();
  };
  health.onDeath = () => {
    setState('dead'); bar.visible = false; mark.visible = false;
    game.audio.play('down');
    game.events.emit('botDown', bot);
  };

  // Pick the closest cover point that the player cannot see.
  function tryCover() {
    const p = game.player.pos;
    let best = null, bestD = 18;
    for (const c of world.coverPoints) {
      const d = Math.hypot(c.x - pos.x, c.z - pos.z);
      if (d >= bestD || Math.hypot(c.x - p.x, c.z - p.z) < 4) continue;
      if (world.lineOfSight(p.x, p.z, c.x, c.z)) continue;
      best = c; bestD = d;
    }
    if (!best) return false;
    coverPt = best; coverT = 1.6 + Math.random() * 1.4;
    setState('cover');
    return true;
  }

  // Returns true on arrival.
  function moveTo(target, speed, dt) {
    const tx = target.x - pos.x, tz = target.z - pos.z;
    const d = Math.hypot(tx, tz);
    if (d < 0.6) return true;
    let ux = tx / d, uz = tz / d;
    if (avoidT > 0) { // sidestep around whatever blocked us
      avoidT -= dt;
      ux = ux * 0.3 - uz * avoidSide; uz = uz * 0.3 + (tx / d) * avoidSide;
      const n = Math.hypot(ux, uz); ux /= n; uz /= n;
    }
    const bx = pos.x, bz = pos.z;
    world.move(pos, ux * speed * dt, uz * speed * dt, RADIUS);
    if (Math.hypot(pos.x - bx, pos.z - bz) < speed * dt * 0.4) {
      stuckT += dt;
      if (stuckT > 0.2) { stuckT = 0; avoidT = 0.7; avoidSide = Math.random() < 0.5 ? -1 : 1; }
    } else stuckT = Math.max(0, stuckT - dt);
    faceTarget = Math.atan2(ux, uz);
    return false;
  }

  function shoot() {
    const p = game.player.pos;
    const a = bot.facing + (Math.random() - 0.5) * 0.12; // aim spread
    const d = Math.hypot(p.x - pos.x, p.z - pos.z) || 1;
    game.combat.fire({
      x: pos.x + Math.sin(bot.facing) * 0.7, y: pos.y + 1.2, z: pos.z + Math.cos(bot.facing) * 0.7,
      dx: Math.sin(a), dz: Math.cos(a), dy: (p.y - pos.y) / d,
      speed: SHOT_SPEED, damage: SHOT_DAMAGE, team: 'bot', color: 0xffd27a,
    });
    game.audio.play('shoot');
  }

  bot.update = (dt) => {
    if (bot.state === 'dead') {
      deadT += dt;
      model.rotation.x = -Math.min(1, deadT / 0.35) * Math.PI / 2;
      if (deadT > 2) root.position.y -= dt * 0.8;
      if (deadT > 3.2) bot.remove = true;
      return;
    }
    if (knock.lengthSq() > 0.01) {
      world.move(pos, knock.x * dt, knock.z * dt, RADIUS);
      knock.multiplyScalar(Math.exp(-6 * dt));
    }

    // ---- senses ----
    const p = game.player;
    const dx = p.pos.x - pos.x, dz = p.pos.z - pos.z;
    const dist = Math.hypot(dx, dz), angTo = Math.atan2(dx, dz);
    const combat = inCombat();
    bot.sees = false;
    if (!p.health.dead && dist < VIEW_RANGE) {
      const inCone = Math.abs(angleDiff(bot.facing, angTo)) < (combat ? Math.PI * 0.9 : FOV / 2);
      if ((inCone || dist < 2.2) && world.lineOfSight(pos.x, pos.z, p.pos.x, p.pos.z)) bot.sees = true;
    }
    if (bot.sees) {
      lastSeen.copy(p.pos); unseenT = 0;
      bot.awareness = Math.min(1, bot.awareness + dt * (combat ? 10 : dist < 8 ? 4 : 1.6)); // closer = spotted faster
    } else {
      unseenT += dt;
      if (!combat) bot.awareness = Math.max(0, bot.awareness - dt * 0.5);
    }

    // ---- brain ----
    switch (bot.state) {
      case 'patrol':
        if (bot.awareness >= 1) { engage(); break; }
        if (!patrol.length) break;
        if (waitT > 0) waitT -= dt;
        else if (moveTo(patrol[wp], SPEED.patrol, dt)) { wp = (wp + 1) % patrol.length; waitT = 1.2; }
        break;

      case 'investigate':
        if (bot.awareness >= 1) { engage(); break; }
        if (moveTo(heardPos, SPEED.investigate, dt)) {
          lookT += dt; faceTarget += dt * 1.5; // look around
          if (lookT > 3) setState('patrol');
        }
        break;

      case 'chase':
        if (bot.sees && dist < SHOOT_RANGE) { setState('shoot'); break; }
        if ((moveTo(lastSeen, SPEED.chase, dt) && unseenT > 1) || unseenT > 8) {
          heardPos.copy(lastSeen); lookT = 0; bot.awareness = 0.5;
          setState('investigate'); // lost the player: search the last known spot
        }
        break;

      case 'shoot':
        if (!bot.sees) { if (unseenT > 0.7) setState('chase'); break; }
        if (dist > SHOOT_RANGE + 3) { setState('chase'); break; }
        if (dist < 6) {            // too close: back away
          world.move(pos, -dx / dist * 2.2 * dt, -dz / dist * 2.2 * dt, RADIUS);
        } else {                   // strafe so the bot is not a standing target
          strafeT -= dt;
          if (strafeT <= 0) { strafeT = 1 + Math.random() * 1.5; strafeDir = Math.random() < 0.5 ? -1 : 1; }
          world.move(pos, dz / dist * strafeDir * SPEED.strafe * dt, -dx / dist * strafeDir * SPEED.strafe * dt, RADIUS);
        }
        faceTarget = angTo;
        shootCd -= dt;
        if (shootCd <= 0 && Math.abs(angleDiff(bot.facing, angTo)) < 0.25) {
          shoot();
          shootCd = 0.9 + Math.random() * 0.5;
          if (++shots >= 4) { shots = 0; tryCover(); } // "reload" behind cover
        }
        break;

      case 'cover':
        if (bot.sees && dist < 4) { setState('shoot'); break; }
        if (moveTo(coverPt, SPEED.cover, dt)) {
          faceTarget = Math.atan2(lastSeen.x - pos.x, lastSeen.z - pos.z);
          coverT -= dt;
          if (coverT <= 0) setState('chase'); // peek out again
        }
        break;
    }

    bot.facing = lerpAngle(bot.facing, faceTarget, damp(8, dt));
    pos.y += (world.heightAt(pos.x, pos.z) - pos.y) * damp(20, dt);
    root.position.copy(pos);
    model.rotation.y = bot.facing;
    mark.rotation.y += dt * 2;
    bar.quaternion.copy(game.engine.camera.quaternion);
    flashT -= dt;
    bodyMat.emissive.setHex(flashT > 0 ? 0xaa2222 : 0x000000);
  };

  bot.dispose = () => {
    game.scene.remove(root);
    bodyMat.dispose(); markMat.dispose(); barBack.material.dispose(); barFill.material.dispose();
  };

  return bot;
}
