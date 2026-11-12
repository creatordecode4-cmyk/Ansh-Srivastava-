import type { Config } from 'tailwindcss'
import { colors, fonts } from './src/tokens'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: colors.black,
        navy: colors.navy,
        ice: colors.ice,
        electric: colors.electric,
        silver: colors.silver,
        amber: colors.amber,
      },
      fontFamily: {
        display: fonts.display.split(',').map((s) => s.trim()),
        sans: fonts.body.split(',').map((s) => s.trim()),
      },
    },
  },
  plugins: [],
} satisfies Config
