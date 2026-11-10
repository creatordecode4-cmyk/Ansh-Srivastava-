// ENGINE TEST MISSION. Not part of the story campaign: it exists to exercise the combat systems
// (bots, Shakti unlock, Burst). It only loads when the game is opened with ?mission=t0_systems_check. Radio lines follow the bible: max 12 words, radio tone.

const MARKER = { x: -10, z: 30 };
const BOAT = { x: 0, z: 51 };
const BOTS = [
  { x: 12, z: -8, patrol: [{ x: 12, z: -8 }, { x: 24, z: -8 }, { x: 24, z: -17 }, { x: 12, z: -17 }] },
  { x: -6, z: 2, patrol: [{ x: -6, z: 2 }, { x: -16, z: -4 }, { x: -10, z: 10 }] },
  { x: 30, z: -2, patrol: [{ x: 30, z: -2 }, { x: 34, z: 10 }, { x: 22, z: 6 }] },
];

export const systemsCheck = {
  id: 't0_systems_check',
  name: 'Systems Check',
  location: 'Seepgaon Beach',
  time: '06:10',
  level: 'testArena',
  objectives: [
    { id: 'move', text: 'Reach the marker on the beach', target: MARKER },
    { id: 'clear', text: 'Clear the training bots' },
    { id: 'return', text: 'Return to the boat', target: BOAT },
  ],

  start(ctx) {
    ctx.placePlayer(BOAT.x, BOAT.z, 0); // camera yaw 0 = looking inland
    ctx.radio('Deepak', 'Disha, radio check. Move to the marker.');
    ctx.radio('Aangan', "Aangan here. Don't dent the boat, bhaiya.");
  },

  update(ctx) {
    const id = ctx.current?.id;
    if (id === 'move') {
      if (ctx.playerNear(MARKER, 2.5)) {
        ctx.unlockShakti('vayu'); // test unlock so the Shakti button can be tried
        BOTS.forEach((b) => ctx.spawnBot(b));
        ctx.radio('Deepak', 'Marker confirmed. Vayu online. Three targets ahead.');
        ctx.completeObjective('move');
      }
    } else if (id === 'clear') {
      const alive = ctx.game.bots.filter((b) => !b.health.dead);
      ctx.setObjectiveText('clear', `Clear the training bots (${BOTS.length - alive.length}/${BOTS.length})`);
      const p = ctx.game.player.pos;
      alive.sort((a, b) => a.pos.distanceToSquared(p) - b.pos.distanceToSquared(p));
      ctx.setTarget(alive[0]?.pos ?? null);
      if (!alive.length) {
        ctx.radio('Deepak', 'Area clear. Return to the boat.');
        ctx.completeObjective('clear');
      }
    } else if (id === 'return') {
      if (ctx.playerNear(BOAT, 2.5)) ctx.completeObjective('return');
    }
  },

  complete(ctx) {
    ctx.radio('Deepak', 'Systems green. Good work, Disha. Out.');
    ctx.radio('Aangan', 'Boat is fine. I checked. Twice.');
  },
};
