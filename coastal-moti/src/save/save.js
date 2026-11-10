// Game progress in localStorage. Every access is wrapped in try/catch:
// private mode, full storage or corrupted data must never crash the game.
const KEY = 'coastal-moti:save:v1';

export const freshProgress = () => ({
  currentMission: null,   // id of the mission to resume
  checkpoint: null,       // { mission, id } - where to resume INSIDE the current mission
  completed: [],          // ids of finished missions
  unlockedShaktis: [],    // 'vayu' | 'agni' | 'jal' | 'bijli' | 'dharti'
  flags: {},              // story facts, e.g. compassPointsToIsland, hasHalfMap
  playerLevel: 1,
  xp: 0,
});

const strings = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []);

export function loadProgress() {
  const base = freshProgress();
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (!raw || typeof raw !== 'object') return base;
    const cp = raw.checkpoint;
    const flags = {};
    if (raw.flags && typeof raw.flags === 'object') {
      for (const [k, v] of Object.entries(raw.flags)) if (['boolean', 'number', 'string'].includes(typeof v)) flags[k] = v;
    }
    return {
      currentMission: typeof raw.currentMission === 'string' ? raw.currentMission : null,
      checkpoint: cp && typeof cp.mission === 'string' && typeof cp.id === 'string' ? { mission: cp.mission, id: cp.id } : null,
      completed: strings(raw.completed),
      unlockedShaktis: strings(raw.unlockedShaktis),
      flags,
      playerLevel: Number.isInteger(raw.playerLevel) && raw.playerLevel > 0 ? raw.playerLevel : 1,
      xp: Number.isFinite(raw.xp) && raw.xp >= 0 ? raw.xp : 0,
    };
  } catch {
    return base;
  }
}

export function saveProgress(progress) {
  try {
    localStorage.setItem(KEY, JSON.stringify(progress));
    return true;
  } catch {
    return false; // storage unavailable: the game keeps running, progress just is not kept
  }
}

export function clearProgress() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
