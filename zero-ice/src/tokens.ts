/** Single source of truth for brand tokens (used by Tailwind, DOM and the 3D scene). */
export const colors = {
  /** Midnight Navy: page background, hero overlay base, footer */
  midnight: '#071522',
  /** Deep Blue: cards, alternating section backgrounds, glass panels */
  deep: '#162B40',
  /** Ice Cyan: primary buttons, glows, big numbers, progress, 3D rim light */
  cyan: '#00D5E7',
  /** Frost White: secondary text, light accents, ice highlights */
  frost: '#B9F5FF',
  /** Silver White: headings and main body text */
  silver: '#F4F9FC',
} as const

export const fonts = {
  display: '"Barlow Condensed", "Arial Narrow", sans-serif',
  body: '"Inter Variable", Inter, system-ui, sans-serif',
} as const

/** Scroll length of each pinned section, in viewport heights. */
export const sectionVh = {
  hero: 180,
  story: 240,
  journey: 260,
  why: 280,
  splash: 280,
  taste: 180,
  lineup: 300,
  nutrition: 160,
  cta: 210,
} as const

export const brand = {
  name: 'ZERO ICE',
  sub: 'DIET COLA',
  top: 'ZERO SUGAR • ZERO CALORIES',
  bottom: ['BOLD TASTE', 'ZERO GUILT'],
  ticker: 'ZERO SUGAR • ZERO CALORIES • BOLD TASTE • ZERO GUILT • ',
} as const

export type VariantId = 'original' | 'lime' | 'cherry'

export const variants: {
  id: VariantId
  name: string
  sub: string
  blurb: string
  available: boolean
  base: string
  band: string
}[] = [
  { id: 'original', name: 'Original Diet Cola', sub: 'DIET COLA', blurb: 'The one that started the chill. Bold cola, clean finish.', available: true, base: '#d9dee3', band: '#0b0c0f' },
  { id: 'lime', name: 'Zero Ice Lime', sub: 'LIME', blurb: 'A sharp twist of lime over the same ice-cold cola.', available: false, base: '#b7e07f', band: '#0c2a12' },
  { id: 'cherry', name: 'Zero Ice Cherry', sub: 'CHERRY', blurb: 'Dark cherry up front, crisp cola behind it.', available: false, base: '#ec97a8', band: '#3a0612' },
]
