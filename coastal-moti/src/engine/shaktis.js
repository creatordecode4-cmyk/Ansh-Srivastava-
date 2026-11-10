// The five Shaktis. Order matches keys 1-5 and the story bible.
// Effects and numbers here are PLACEHOLDER tuning for the engine; missions unlock them by id.
export const SHAKTIS = [
  { id: 'vayu',   name: 'Vayu',   element: 'wind',      color: 0xbfe9e0, cooldown: 3.0, kind: 'cone',       damage: 12, range: 7, push: 10 },
  { id: 'agni',   name: 'Agni',   element: 'fire',      color: 0xff7a2f, cooldown: 2.5, kind: 'projectile', damage: 30, speed: 22 },
  { id: 'jal',    name: 'Jal',    element: 'water',     color: 0x3fa9f5, cooldown: 6.0, kind: 'heal',       amount: 30 },
  { id: 'bijli',  name: 'Bijli',  element: 'lightning', color: 0xf7e463, cooldown: 4.0, kind: 'bolt',       damage: 40, range: 16 },
  { id: 'dharti', name: 'Dharti', element: 'earth',     color: 0xb98a55, cooldown: 6.0, kind: 'aoe',        damage: 28, range: 5 },
];

// Original, hand-drawn glyphs (24x24, stroke only).
export const SHAKTI_ICONS = {
  vayu:   'M3 8h10a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7',
  agni:   'M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z',
  jal:    'M12 3c3 5 6 8 6 12a6 6 0 0 1-12 0c0-4 3-7 6-12z',
  bijli:  'M13 2 5 14h6l-1 8 8-12h-6z',
  dharti: 'M2 19 9 7l4 6 2-3 7 9z',
};
