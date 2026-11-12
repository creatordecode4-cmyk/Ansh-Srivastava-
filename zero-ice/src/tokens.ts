/** Single source of truth for brand tokens (used by Tailwind, DOM and the 3D scene). */
export const colors = {
  black: '#05070D',
  navy: '#0A1226',
  ice: '#4FB3FF',
  electric: '#1E6BFF',
  silver: '#C9D1D9',
  white: '#FFFFFF',
  amber: '#C0621B',
} as const

export const fonts = {
  display: '"Barlow Condensed", "Arial Narrow", sans-serif',
  body: '"Inter Variable", Inter, system-ui, sans-serif',
} as const

/** Scroll length of each pinned section, in viewport heights. */
export const sectionVh = {
  hero: 180,
  story: 240,
  why: 280,
  splash: 280,
  taste: 180,
  lineup: 300,
  nutrition: 160,
  fans: 160,
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
  accent: string
}[] = [
  { id: 'original', name: 'Original Diet Cola', sub: 'DIET COLA', blurb: 'The one that started the chill. Bold cola, clean finish.', available: true, base: '#d9dee3', band: '#0b0c0f', accent: colors.ice },
  { id: 'lime', name: 'Zero Ice Lime', sub: 'LIME', blurb: 'A sharp twist of lime over the same ice-cold cola.', available: false, base: '#b7e07f', band: '#0c2a12', accent: '#9BE564' },
  { id: 'cherry', name: 'Zero Ice Cherry', sub: 'CHERRY', blurb: 'Dark cherry up front, crisp cola behind it.', available: false, base: '#ec97a8', band: '#3a0612', accent: '#FF6B8B' },
]
