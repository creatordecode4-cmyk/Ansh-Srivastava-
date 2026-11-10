// Game progress in localStorage. Every access is wrapped in try/catch:
// private mode, full storage or corrupted data must never crash the game.
const KEY = 'coastal-moti:save:v1';

export const freshProgress = () => ({
  currentMission: null,   // id of the mission to resume
  completed: [],          // ids of finished missions
  unlockedShaktis: [],    // 'vayu' | 'agni' | 'jal' | 'bijli' | 'dharti'
  playerLevel: 1,
  xp: 0,
});

export function loadProgress() {
  const base = freshProgress();
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (!raw || typeof raw !== 'object') return base;
    return {
      currentMission: typeof raw.currentMission === 'string' ? raw.currentMission : null,
      completed: Array.isArray(raw.completed) ? raw.completed.filter((x) => typeof x === 'string') : [],
      unlockedShaktis: Array.isArray(raw.unlockedShaktis) ? raw.unlockedShaktis.filter((x) => typeof x === 'string') : [],
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
