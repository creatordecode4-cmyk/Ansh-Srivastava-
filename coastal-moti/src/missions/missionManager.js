// Mission manager. A mission is a plain data object:
//
//   {
//     id: 'm1_example', name: 'Mission name', location: 'Seepgaon Diya-Ghar', time: '23:40',
//     objectives: [{ id: 'reach', text: 'Reach the gate', target: { x: 0, z: 0 } }, ...],
//     start(ctx)       {},  // set up the world: place the player, spawn bots, queue radio lines
//     update(ctx, dt)  {},  // every frame: check conditions, call ctx.completeObjective(id)
//     complete(ctx)    {},  // rewards and closing radio lines
//   }
//
// Flow: mission card -> start() -> update() every frame -> all objectives done -> complete() -> save -> next.
// Saved: current mission id, completed missions, unlocked Shaktis, player level.
// NOT saved: progress inside a mission (a refresh restarts the current mission).

export function createMissionManager(game) {
  const missions = [];
  let active = null, objectives = [], current = null;
  let state = 'idle'; // idle | card | running | complete
  let token = 0, freeRoam = false;

  const ctx = {
    game,
    get current() { return current; },
    get objectives() { return objectives; },
    radio: (callsign, text) => game.radio.say(callsign, text),
    spawnBot: (opts) => game.spawnBot(opts),
    setTarget: (pos) => game.setObjectiveTarget(pos),
    placePlayer: (x, z, yaw = 0) => game.placePlayer(x, z, yaw),
    playerNear: (t, radius) => Math.hypot(game.player.pos.x - t.x, game.player.pos.z - t.z) < radius,
    unlockShakti(id) {
      if (game.progress.unlockedShaktis.includes(id)) return;
      game.progress.unlockedShaktis.push(id);
      game.persist();
      game.audio.play('unlock');
      game.events.emit('shaktiUnlocked', id);
    },
    setObjectiveText(id, text) {
      const o = objectives.find((x) => x.id === id);
      if (o) o.text = text;
    },
    completeObjective(id) {
      const o = objectives.find((x) => x.id === id);
      if (!o || o.done) return;
      o.done = true;
      game.audio.play('objective');
      current = objectives.find((x) => !x.done) || null;
      game.setObjectiveTarget(current?.target ?? null);
      if (!current) finish();
    },
  };

  function register(mission) { missions.push(mission); }

  async function start(id) {
    const mission = missions.find((m) => m.id === id) || missions[0];
    if (!mission) return;
    const my = ++token;
    active = mission; state = 'card'; freeRoam = false;
    game.frozen = true;
    game.resetActors();
    objectives = mission.objectives.map((o) => ({ ...o, done: false }));
    current = objectives[0] || null;
    game.setObjectiveTarget(current?.target ?? null);
    game.progress.currentMission = mission.id;
    game.persist();

    game.radio.hold(true);          // radio lines queued in start() wait for the card to finish
    mission.start(ctx);
    await game.card.show(mission);
    if (my !== token) return;       // another start() replaced this one
    state = 'running';
    game.frozen = false;
    game.radio.hold(false);
    game.audio.play('missionStart');
    game.events.emit('missionStart', mission);
  }

  function finish() {
    state = 'complete';
    active.complete(ctx);
    const p = game.progress;
    if (!p.completed.includes(active.id)) p.completed.push(active.id);
    const next = missions[missions.indexOf(active) + 1];
    p.currentMission = next ? next.id : active.id;
    game.persist();
    game.audio.play('missionComplete');
    game.events.emit('missionComplete', active);
    if (next) {
      const my = token;
      setTimeout(() => { if (my === token) start(next.id); }, 3000);
    } else freeRoam = true;
  }

  return {
    register, start,
    restart() { if (active) start(active.id); },
    update(dt) { if (state === 'running') active.update(ctx, dt); },
    get active() { return active; },
    get state() { return state; },
    get objectiveText() {
      if (freeRoam) return 'Mission complete. Free roam.';
      return current?.text ?? '';
    },
    get list() { return missions; },
  };
}
