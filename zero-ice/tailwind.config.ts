import type { Config } from 'tailwindcss'
import { colors, fonts } from './src/tokens'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        midnight: colors.midnight,
        deep: colors.deep,
        cyan: colors.cyan,
        frost: colors.frost,
        silver: colors.silver,
      },
      fontFamily: {
        display: fonts.display.split(',').map((s) => s.trim()),
        sans: fonts.body.split(',').map((s) => s.trim()),
      },
    },
  },
  plugins: [],
} satisfies Config
