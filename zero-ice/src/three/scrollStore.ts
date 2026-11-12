/**
 * Shared scroll state. GSAP ScrollTrigger writes here (see lib/scroll.ts),
 * the 3D scene reads it inside useFrame. No React state on the hot path.
 */
export const SECTION_IDS = ['hero', 'trust', 'story', 'journey', 'why', 'numbers', 'splash', 'taste', 'lineup', 'nutrition', 'reviews', 'love', 'community', 'cta', 'faq'] as const
export type SectionId = (typeof SECTION_IDS)[number]

export interface SectionProgress {
  /** 0 → 1 while the section's top travels from viewport bottom to viewport top */
  enter: number
  /** 0 → 1 while the section is pinned (top at top → bottom at bottom) */
  pin: number
}

export const scrollStore = {
  /** whole-page progress 0..1 */
  progress: 0,
  /** smoothed scroll velocity, px / frame */
  velocity: 0,
  sections: Object.fromEntries(SECTION_IDS.map((id) => [id, { enter: id === 'hero' ? 1 : 0, pin: 0 }])) as Record<SectionId, SectionProgress>,
  /** normalised pointer, -1..1 (desktop only) */
  pointer: { x: 0, y: 0 },
  isMobile: false,
  /** scale of the frozen hero video (slow zoom) so the 3D can matches it */
  heroZoom: 1,
}

export const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v)
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t
/** smoothstep between two edges */
export const ss = (a: number, b: number, v: number) => {
  const t = clamp01((v - a) / (b - a))
  return t * t * (3 - 2 * t)
}

/** Lineup carousel position (0..2) with a plateau on each can. */
export function carouselAt(pin: number) {
  const x = clamp01((pin - 0.08) / 0.84) * 2
  const i = Math.min(Math.floor(x), 1)
  return i + ss(0.3, 0.7, x - i)
}
