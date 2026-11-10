// Tiny event bus so systems can talk without importing each other.
export function createEvents() {
  const map = new Map();
  return {
    on(name, fn) {
      if (!map.has(name)) map.set(name, []);
      map.get(name).push(fn);
      return () => { const l = map.get(name); const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); };
    },
    emit(name, payload) { map.get(name)?.slice().forEach((fn) => fn(payload)); },
  };
}
