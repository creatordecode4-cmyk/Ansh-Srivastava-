import * as THREE from 'three';
import { SEEPGAON as S } from '../levels/seepgaon.js';
import { createGuard } from '../ai/guard.js';

// MISSION 0 "ANDHERA" (darkness) - 23:40, Seepgaon Diya-Ghar.
// A monsoon storm. The lighthouse flickers three times and dies. Veer learns Dadaji's compass,
// climbs to the Diya-Ghar, sees men in black cutting the lamp wires, and must get home unseen
// with Dadaji's tin box. Stealth only: guards stay on fixed routes; being seen = back to the checkpoint.
//
// Radio rules (story bible): every line max 12 words, radio tone.
// Callsigns: Aangan = Meenu at home, Disha = Veer. Baba has no callsign: he is on a fishing boat.

const LETTER = 'Veer, when the Diya-Ghar goes dark, remember the lullaby. The lullaby is the way.';

const START = { x: -4, z: 37.5 };
const MID = { x: -8.5, z: -12.5 };       // dark alley half-way down: checkpoint
const DOOR_SPAWN = { x: 0, z: -36.6 };
const BOX_SPAWN = { x: -10, z: 23.2 };

// Fixed patrol loops. `look` is the direction a guard faces while waiting (0 = south, toward +Z).
const GUARDS = [
  { start: 0, route: [{ x: 6.5, z: -47, wait: 1 }, { x: -6.5, z: -47, wait: 1.5 }, { x: -6.5, z: -36, wait: 1 },
    { x: 0, z: -34.5, wait: 2.5, look: 0 }, { x: 6.5, z: -36, wait: 1 }] },                                  // lighthouse yard
  { start: 1, route: [{ x: 1, z: -28, wait: 2.5, look: 0 }, { x: 1, z: -15, wait: 1 }, { x: 10, z: -12, wait: 2 }, { x: 1, z: -15, wait: 0.5 },
    { x: -10, z: -18, wait: 2.5, look: 0 }, { x: 1, z: -15, wait: 0.5 }] },                                   // upper lane + west alley
  { start: 1, route: [{ x: 3, z: 2, wait: 1.5 }, { x: 10, z: 9, wait: 2 }, { x: 3, z: 15, wait: 1.5 }, { x: -4, z: 9, wait: 1 },
    { x: -4.2, z: 6.5, wait: 0 }, { x: -13, z: 6.5, wait: 2.5 }, { x: -4.2, z: 6.5, wait: 0 }] },             // well square + west passage
  { start: 2, route: [{ x: -3, z: 23, wait: 4, look: -Math.PI / 2 }, { x: -3, z: 34, wait: 1.5 }, { x: 9, z: 34, wait: 1.5 }, { x: 9, z: 23, wait: 1 }] }, // lower lane, watches the shed
];

export const andhera = {
  id: 'm0_andhera',
  name: 'Andhera',
  location: 'Seepgaon Diya-Ghar',
  time: '23:40',
  level: 'seepgaon',
  objectives: [
    { id: 'compass', text: "Take Dadaji's compass from the porch", target: S.porch },
    { id: 'climb', text: 'Climb to the Diya-Ghar', target: S.door },
    { id: 'escape', text: 'Escape the lighthouse. Stay out of the torchlight.', target: MID },
    { id: 'box', text: "Find Dadaji's tin box in the boat shed", target: S.shed },
    { id: 'home', text: 'Get home unseen', target: S.home },
  ],
  endDelay: 7000,
  endLine: 'Night one. The Diya-Ghar stays dark.',

  // checkpoint: null (fresh start) | 'compass' | 'escape' | 'mid' | 'box'
  start(ctx, checkpoint) {
    const { game } = ctx;
    const level = game.world.level;
    this.guards = [];
    this.busy = false;        // true while a tutorial / cutscene / letter is running
    level.cutters.visible = false;
    level.tinBox.visible = !ctx.getFlag('hasHalfMap') || checkpoint !== 'box';
    level.lighthouse.setLit(!checkpoint);
    game.stealth = null;

    // Dadaji's compass hanging by the porch (placeholder prop).
    if (!checkpoint) {
      const prop = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.07, 14),
        new THREE.MeshBasicMaterial({ color: 0xe8a33d, fog: false }));
      prop.rotation.x = Math.PI / 2;
      prop.position.set(S.porch.x, game.world.heightAt(S.porch.x, S.porch.z) + 1.3, S.porch.z);
      game.scene.add(prop);
      this.compassProp = prop;
      game.onReset(() => { game.scene.remove(prop); prop.geometry.dispose(); prop.material.dispose(); });
    }

    if (!checkpoint) {
      ctx.placePlayer(START.x, START.z, 0, 0.1);   // camera looks north, up the hill, at the lighthouse
      ctx.script(async (s) => {
        await s.wait(2.6);
        level.lighthouse.flickerOut();        // off-on, off-on, off-on, dark
        for (let i = 0; i < 3; i++) { game.audio.play('flicker'); await s.wait(0.8); }
        await s.wait(0.5);
        game.engine.weather.strike();
        ctx.radio('Baba', 'Veer, where did the light go? I cannot see anything—');
        ctx.radio('Radio', 'Signal lost.', { sound: 'static' });
        ctx.radio('Aangan', 'Bhaiya, the Diya-Ghar is dark. Baba is still out.');
        ctx.radio('Disha', "Copy, Aangan. Getting Dadaji's compass. Then the lighthouse.");
      });
    } else if (checkpoint === 'compass') {
      ctx.skipTo('climb');
      ctx.placePlayer(S.porch.x + 1.5, S.porch.z - 1.5, 0);
    } else if (checkpoint === 'escape') {
      ctx.skipTo('escape');
      ctx.placePlayer(DOOR_SPAWN.x, DOOR_SPAWN.z, Math.PI); // camera looks south, down to the village
      this.spawnGuards(ctx);
      game.banner('Escape the lighthouse.');
    } else if (checkpoint === 'mid') {
      ctx.skipTo('box');
      ctx.placePlayer(MID.x, MID.z, Math.PI);
      this.spawnGuards(ctx);
    } else if (checkpoint === 'box') {
      ctx.skipTo('home');
      ctx.placePlayer(BOX_SPAWN.x, BOX_SPAWN.z, Math.PI);
      this.spawnGuards(ctx);
    }
  },

  spawnGuards(ctx) {
    const { game } = ctx;
    this.guards = GUARDS.map((g) => createGuard(game, g));
    game.onReset(() => { for (const g of this.guards) g.dispose(); this.guards = []; });
    game.stealth = { level: 0, lit: false };
  },

  update(ctx, dt) {
    const { game } = ctx;
    if (this.busy) return;
    const p = game.player.pos;
    const id = ctx.current?.id;

    // ---- stealth: one glimpse too long and it is back to the checkpoint ----
    if (this.guards.length) {
      let worst = 0;
      for (const g of this.guards) { g.update(dt); worst = Math.max(worst, g.suspicion); }
      game.stealth = { level: worst, lit: game.world.isLit(p.x, p.z) };
      if (worst >= 1) { ctx.fail('Spotted'); return; }
    }

    if (id === 'compass') {
      if (this.compassProp) this.compassProp.rotation.z += dt * 2;
      if (ctx.playerNear(S.porch, 2)) this.compassTutorial(ctx);
    } else if (id === 'climb') {
      if (!this.warned && p.z < 5) { this.warned = true; ctx.radio('Aangan', 'Rain is heavy. Stay on the lane, bhaiya.'); }
      if (ctx.playerNear(S.door, 2.6)) this.lampRoomCutscene(ctx);
    } else if (id === 'escape') {
      if (p.z > -13.5) {                      // out of the upper lane, by any route
        ctx.checkpoint('mid');
        ctx.completeObjective('escape');
        ctx.radio('Aangan', "Dadaji's tin box. Boat shed. Bring it home.");
      }
    } else if (id === 'box') {
      if (ctx.playerNear(S.shed, 1.8)) this.openTinBox(ctx);
    } else if (id === 'home') {
      if (ctx.playerNear(S.home, 2.5)) { game.stealth = null; ctx.completeObjective('home'); }
    }
  },

  // Tutorial: turn the compass; the needle always settles on the island.
  compassTutorial(ctx) {
    const { game } = ctx;
    this.busy = true;
    game.frozen = true;
    ctx.script(async (s) => {
      const p = game.player.pos, f = game.rig.forward(), r = game.rig.right();
      const dx = S.island.x - p.x, dz = S.island.z - p.z;
      const bearing = Math.atan2(dx * r.x + dz * r.z, dx * f.x + dz * f.z) * 180 / Math.PI;
      await s.after(game.compassTutorial.run(bearing));
      if (this.compassProp) this.compassProp.visible = false;
      ctx.setFlag('hasCompass');
      ctx.setFlag('compassPointsToIsland');   // needed in the finale
      game.rig.yaw = Math.atan2(-dx, -dz);    // turn to face what the needle points at
      game.rig.pitch = 0.12;
      game.engine.weather.strike();           // lightning shows the island on the horizon
      game.frozen = false;
      this.busy = false;
      ctx.checkpoint('compass');
      ctx.completeObjective('compass');
      ctx.radio('Aangan', 'That compass never points north. Broken?');
      ctx.radio('Disha', 'Not broken. It points to the island. Always.');
    });
  },

  // Cutscene: the men in black cut the lamp wires. Then the guards come down.
  lampRoomCutscene(ctx) {
    const { game } = ctx;
    const level = game.world.level;
    this.busy = true;
    game.frozen = true;
    ctx.script(async (s) => {
      await s.after(game.fade(true, 500));
      game.setCinematic(true);
      level.cutters.visible = true;
      const top = S.lampTop;
      game.rig.cinematic = {
        from: new THREE.Vector3(9, top.y + 2.2, -26), to: new THREE.Vector3(6.5, top.y + 1.2, -31.5),
        look: new THREE.Vector3(top.x, top.y - 0.4, top.z + 1), duration: 9,
      };
      await s.after(game.fade(false, 600));
      ctx.radio('Disha', 'Men in black. They are cutting the lamp wires.');
      await s.wait(4.2);
      game.engine.weather.strike();
      ctx.radio('Man in black', 'Lamp is dead. Sweep the village. No witnesses.');
      await s.wait(4.6);
      await s.after(game.fade(true, 500));
      level.cutters.visible = false;
      game.rig.cinematic = null;
      game.setCinematic(false);
      ctx.placePlayer(DOOR_SPAWN.x, DOOR_SPAWN.z, Math.PI);
      this.spawnGuards(ctx);
      ctx.checkpoint('escape');
      ctx.completeObjective('climb');
      await s.after(game.fade(false, 600));
      game.frozen = false;
      this.busy = false;
      game.banner('Escape the lighthouse.');      // objective card
      ctx.radio('Aangan', 'Bhaiya, come home. Quietly. Stay out of the torches.');
    });
  },

  // Dadaji's tin box: half a map and a letter.
  openTinBox(ctx) {
    const { game } = ctx;
    this.busy = true;
    game.frozen = true;
    game.audio.play('pickup');
    ctx.script(async (s) => {
      await s.after(game.letter.show(LETTER));
      game.world.level.tinBox.visible = false;
      ctx.setFlag('hasHalfMap');
      ctx.setFlag('hasDadajiLetter1');
      game.frozen = false;
      this.busy = false;
      ctx.checkpoint('box');
      ctx.completeObjective('box');
      ctx.radio('Disha', 'Got it. Half a map. And a letter.');
    });
  },

  complete(ctx) {
    ctx.radio('Aangan', 'You are soaked. Amma will count your bones.');
    ctx.radio('Disha', 'Three nights of storm. We light the Diya-Ghar.');
    ctx.game.banner('Light the Diya-Ghar. The storm lasts 3 nights.', 6000); // objective card
  },
};
