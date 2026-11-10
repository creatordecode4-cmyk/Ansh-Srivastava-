import { SEEPGAON as S } from '../levels/seepgaon.js';

// PLACEHOLDER for Mission 1. It only shows a mission card and lets the player walk around
// the dark village. Replace this file when Mission 1 is designed.
export const mission1Placeholder = {
  id: 'm1_placeholder',
  name: 'Mission 1',
  location: 'Seepgaon',
  time: 'Coming soon',
  level: 'seepgaon',
  objectives: [{ id: 'wait', text: 'Mission 1 is not built yet. Free roam.' }],
  start(ctx) {
    ctx.game.world.level.lighthouse.setLit(false);
    ctx.game.world.level.tinBox.visible = false;
    ctx.placePlayer(S.home.x, S.home.z, 0);
  },
  update() {},
  complete() {},
};
