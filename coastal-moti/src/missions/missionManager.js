// Mission manager. A mission is a plain data object:
//
//   {
//     id: 'm1_example', name: 'Mission name', location: 'Seepgaon Diya-Ghar', time: '23:40',
//     level: 'seepgaon',                       // which level to load (src/levels/)
//     objectives: [{ id: 'reach', text: 'Reach the gate', target: { x: 0, z: 0 } }, ...],
//     endLine: 'One line shown on a black card when the mission ends.',   // optional
//     start(ctx, checkpoint) {},  // set up the world. checkpoint = id saved by ctx.checkpoint(), or null
//     update(ctx, dt)        {},  // every frame: check conditions, call ctx.completeObjective(id)
//     complete(ctx)          {},  // rewards and closing radio lines
//   }
//
// Flow: mission card -> start() -> update() every frame -> all objectives done -> complete()
//       -> optional one-line card -> next mission's card.
// Saved (localStorage): current mission, last checkpoint, completed missions, unlocked Shaktis, flags, level.
// A refresh resumes from the last checkpoint. ctx.fail() also returns the player to it.

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function createMissionManager(game) {
  const missions = [];
  let active = null, objectives = [], current = null;
  let state = 'idle'; // idle | card | running | failed | complete
  let token = 0, freeRoam = false;
  let timers = [];

  const ctx = {
    game,
    get current() { return current; },
    get objectives() { return objectives; },
    radio: (callsign, text, options) => game.radio.say(callsign, text, options),
    spawnBot: (opts) => game.spawnBot(opts),
    setTarget: (pos) => game.setObjectiveTarget(pos),
    placePlayer: (x, z, yaw, pitch) => game.placePlayer(x, z, yaw, pitch),
    playerNear: (t, radius) => Math.hypot(game.player.pos.x - t.x, game.player.pos.z - t.z) < radius,
    unlockShakti(id) {
      if (game.progress.unlockedShaktis.includes(id)) return;
      game.progress.unlockedShaktis.push(id);
      game.persist();
      game.audio.play('unlock');
      game.events.emit('shaktiUnlocked', id);
    },
    // Story facts that later missions can read from game.progress.flags.
    setFlag(name, value = true) { game.progress.flags[name] = value; game.persist(); },
    getFlag: (name) => game.progress.flags[name],
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
    // Used when resuming from a checkpoint: mark everything before `id` as done, silently.
    skipTo(id) {
      for (const o of objectives) { if (o.id === id) break; o.done = true; }
      current = objectives.find((x) => !x.done) || null;
      game.setObjectiveTarget(current?.target ?? null);
    },
    // Save progress inside the mission. A refresh or ctx.fail() comes back here.
    checkpoint(id) {
      game.progress.checkpoint = { mission: active.id, id };
      const ok = game.persist();
      game.toast(ok ? 'Checkpoint saved' : 'Checkpoint (not saved: storage is off)');
      game.events.emit('checkpoint', id);
    },
    // Show a short alert, then restart from the last checkpoint.
    fail(title, sub = 'Back to the last checkpoint.') {
      if (state !== 'running') return;
      state = 'failed';
      game.frozen = true;
      game.showAlert(title, sub);
      game.audio.play('alert');
      const my = token;
      setTimeout(() => { if (my === token) start(active.id, { card: false }); }, 1700);
    },
    // Run a timed sequence (cutscene, intro). s.wait() counts game time, so pausing pauses it;
    // if the mission restarts, the old script simply never continues.
    script(fn) {
      const my = token;
      const s = {
        alive: () => my === token,
        wait: (seconds) => new Promise((resolve) => { timers.push({ t: seconds, resolve, my }); }),
        // Wraps a real-time promise (fade, overlay) so a stale script stops after it.
        after: (promise) => new Promise((resolve) => { promise.then((v) => { if (my === token) resolve(v); }); }),
      };
      fn(s).catch((e) => console.error('Mission script failed', e));
    },
  };

  function register(mission) { missions.push(mission); }

  async function start(id, { card = true, useCheckpoint = true } = {}) {
    const mission = missions.find((m) => m.id === id) || missions[0];
    if (!mission) return;
    const my = ++token;
    active = mission; state = 'card'; freeRoam = false;
    game.frozen = true;
    timers = [];
    if (!card) { await game.fade(true, 250); if (my !== token) return; }

    game.resetActors();
    game.loadLevel(mission.level || 'testArena');
    objectives = mission.objectives.map((o) => ({ ...o, done: false }));
    current = objectives[0] || null;
    game.setObjectiveTarget(current?.target ?? null);
    const saved = game.progress.checkpoint;
    const checkpoint = useCheckpoint && saved?.mission === mission.id ? saved.id : null;
    if (!checkpoint) game.progress.checkpoint = null;
    game.progress.currentMission = mission.id;
    game.persist();

    game.radio.hold(true);          // radio lines queued in start() wait for the card to finish
    mission.start(ctx, checkpoint);
    if (card) await game.card.show(mission);
    else await game.fade(false, 400);
    if (my !== token) return;       // another start() replaced this one
    state = 'running';
    game.frozen = false;
    game.radio.hold(false);
    game.audio.play('missionStart');
    game.events.emit('missionStart', mission);
  }

  function finish() {
    state = 'complete';
    const mission = active, my = token;
    mission.complete(ctx);
    const p = game.progress;
    if (!p.completed.includes(mission.id)) p.completed.push(mission.id);
    const next = missions[missions.indexOf(mission) + 1];
    p.currentMission = next ? next.id : mission.id;
    p.checkpoint = null;
    game.persist();
    game.audio.play('missionComplete');
    game.events.emit('missionComplete', mission);
    if (!next && !mission.endLine) { freeRoam = true; return; }
    (async () => {
      await sleep(mission.endDelay ?? 3000);
      if (my !== token) return;
      if (mission.endLine) {
        game.frozen = true;
        await game.card.line(mission.endLine); // fade to a one-line card
        if (my !== token) return;
      }
      if (next) start(next.id);
      else { game.card.hide(); game.frozen = false; freeRoam = true; }
    })();
  }

  return {
    register, start,
    // Full restart of the current mission (pause menu): forgets the checkpoint.
    restart() { if (active) start(active.id, { useCheckpoint: false }); },
    // Back to the last checkpoint without the mission card (player down / spotted).
    restartFromCheckpoint() { if (active) start(active.id, { card: false }); },
    update(dt) { if (state === 'running') active.update(ctx, dt); },
    // Script timers run whenever the game is not paused (also during cutscenes),
    // but not while the mission card still covers the screen.
    tick(dt) {
      if (state === 'card') return;
      for (let i = timers.length - 1; i >= 0; i--) {
        const t = timers[i];
        if ((t.t -= dt) <= 0) { timers.splice(i, 1); if (t.my === token) t.resolve(); }
      }
    },
    get active() { return active; },
    get state() { return state; },
    get objectiveText() {
      if (freeRoam) return 'Mission complete. Free roam.';
      return current?.text ?? '';
    },
    get list() { return missions; },
  };
}
