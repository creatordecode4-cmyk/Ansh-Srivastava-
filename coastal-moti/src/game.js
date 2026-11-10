import * as THREE from 'three';
import { createEngine } from './engine/engine.js';
import { createEvents } from './engine/events.js';
import { createInput } from './engine/input.js';
import { createWorld } from './engine/world.js';
import { createPlayer } from './engine/player.js';
import { createCameraRig } from './engine/cameraRig.js';
import { createCombat } from './engine/combat.js';
import { createBot } from './ai/bot.js';
import { createAudio } from './audio/audio.js';
import { loadProgress, saveProgress, clearProgress, freshProgress } from './save/save.js';
import { createMissionManager } from './missions/missionManager.js';
import { systemsCheck } from './missions/systemsCheck.js';
import { createHud } from './ui/hud.js';
import { createRadio } from './ui/radio.js';
import { createMissionCard } from './ui/missionCard.js';
import { createPauseMenu } from './ui/pauseMenu.js';
import { enableTouchControls } from './ui/touchControls.js';
import { showControlsHint } from './ui/controlsHint.js';

const XP_PER_BOT = 40, XP_PER_LEVEL = 100;

// Wires every system together. `game` is the shared context that systems receive.
export function createGame({ canvas, mobile, settings }) {
  const engine = createEngine(canvas, settings.quality);
  const game = {
    engine, scene: engine.scene, mobile, settings,
    events: createEvents(),
    progress: loadProgress(),
    bots: [],
    paused: false,   // pause menu open
    frozen: true,    // mission card / "down" screen: the world does not tick
    objectiveTarget: null,
  };
  game.audio = createAudio(settings);
  game.input = createInput(canvas);
  game.world = createWorld(engine.scene);
  game.player = createPlayer(game);
  game.rig = createCameraRig(game);
  game.combat = createCombat(game);
  game.radio = createRadio(game);
  game.card = createMissionCard(mobile);
  game.missions = createMissionManager(game);
  game.pauseMenu = createPauseMenu(game);
  game.hud = createHud(game);

  // ---- objective beacon (placeholder until Neelu the kingfisher exists) ----
  const beacon = new THREE.Mesh(
    new THREE.CylinderGeometry(0.5, 0.5, 14, 12, 1, true),
    new THREE.MeshBasicMaterial({ color: 0xe8a33d, transparent: true, opacity: 0.35, depthWrite: false, side: THREE.DoubleSide }));
  beacon.visible = false;
  engine.scene.add(beacon);
  let beaconPulse = 0;
  game.events.on('tool', () => { beaconPulse = 1.2; });

  // ---- shared services -----------------------------------------------------
  game.persist = () => saveProgress(game.progress);
  game.setObjectiveTarget = (pos) => { game.objectiveTarget = pos; };
  game.noise = (pos, radius) => { for (const b of game.bots) b.hear(pos, radius); };

  game.placePlayer = (x, z, yaw = 0) => {
    game.player.reset(x, z, yaw + Math.PI); // face the way the camera looks
    game.rig.yaw = yaw; game.rig.pitch = 0.32;
    game.rig.snap();
  };

  game.spawnBot = (opts) => { const b = createBot(game, opts); game.bots.push(b); return b; };

  game.damageBot = (bot, amount, push) => {
    const dealt = bot.health.damage(amount, 'player');
    if (dealt <= 0) return 0;
    if (push) bot.push(push.x, push.z);
    game.player.addBurst(dealt);
    game.combat.ring({ x: bot.pos.x, y: bot.pos.y + 1, z: bot.pos.z }, 0xffffff, 0.9, 0.18);
    game.audio.play('hit');
    return dealt;
  };

  game.damagePlayer = (amount) => {
    if (game.player.health.damage(amount, 'bot') > 0) { game.audio.play('hurt'); game.hud.flashDamage(); }
  };

  game.addXp = (xp) => {
    const p = game.progress;
    p.xp += xp;
    const level = 1 + Math.floor(p.xp / XP_PER_LEVEL);
    if (level > p.playerLevel) {
      p.playerLevel = level;
      game.player.health.max = 100 + 10 * (level - 1);
      game.player.health.heal(game.player.health.max);
      game.audio.play('levelUp');
      game.events.emit('levelUp', level);
    }
    game.persist();
  };
  game.events.on('botDown', () => game.addXp(XP_PER_BOT));

  // Clear everything a mission created, ready for a (re)start.
  game.resetActors = () => {
    for (const b of game.bots) b.dispose();
    game.bots.length = 0;
    game.combat.clear();
    game.radio.clear();
    document.getElementById('down').hidden = true;
  };

  let downTimer = 0;
  game.onPlayerDown = () => {
    game.audio.play('down');
    game.frozen = true;
    game.player.root.visible = false;
    document.getElementById('down').hidden = false;
    clearTimeout(downTimer);
    downTimer = setTimeout(() => game.missions.restart(), 1800);
  };

  game.resetProgress = () => {
    clearProgress();
    Object.assign(game.progress, freshProgress());
    game.player.currentShakti = 0;
    game.missions.start(game.missions.list[0].id);
  };

  // ---- frame loop ----------------------------------------------------------
  engine.onUpdate((dt) => {
    const { input, player } = game;
    if (input.take('lockLost') && !game.frozen) game.pauseMenu.open();
    if (input.take('pause')) game.pauseMenu.toggle();

    const live = !game.paused && !game.frozen;
    if (live) {
      player.update(dt);
      for (const b of game.bots) b.update(dt);
      for (let i = game.bots.length - 1; i >= 0; i--) {
        if (game.bots[i].remove) { game.bots[i].dispose(); game.bots.splice(i, 1); }
      }
      game.combat.update(dt);
      game.missions.update(dt);
    } else input.lookDelta(); // drop look input gathered while paused
    game.rig.update(dt, live);

    const t = game.objectiveTarget;
    beacon.visible = !!t;
    if (t) {
      beaconPulse = Math.max(0, beaconPulse - dt);
      beacon.position.set(t.x, game.world.heightAt(t.x, t.z) + 7, t.z);
      beacon.material.opacity = 0.3 + 0.1 * Math.sin(performance.now() * 0.004) + beaconPulse * 0.4;
      beacon.scale.x = beacon.scale.z = 1 + beaconPulse;
    }
    engine.setShadowFocus(player.pos);
    game.hud.update();
    input.endFrame();
  });
  engine.onFps((fps) => game.hud.setFps(fps));

  // ---- controls: picked automatically --------------------------------------
  if (mobile) enableTouchControls(game.input);
  else {
    // A laptop with a touch screen: switch the touch UI on at the first touch.
    window.addEventListener('pointerdown', function onFirstTouch(e) {
      if (e.pointerType !== 'touch') return;
      window.removeEventListener('pointerdown', onFirstTouch);
      enableTouchControls(game.input);
    });
  }
  showControlsHint(mobile);

  // Leaving the tab pauses the game.
  document.addEventListener('visibilitychange', () => { if (document.hidden && !game.frozen) game.pauseMenu.open(); });

  // ---- missions ------------------------------------------------------------
  game.missions.register(systemsCheck);

  game.start = () => {
    engine.start();
    game.missions.start(game.progress.currentMission);
  };
  return game;
}
