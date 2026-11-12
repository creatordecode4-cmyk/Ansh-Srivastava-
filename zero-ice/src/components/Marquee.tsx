import { brand } from '../tokens'

export function Marquee() {
  const run = brand.ticker.repeat(4)
  return (
    <div className="relative z-20 overflow-hidden border-y border-white/10 bg-ink/80 py-3 backdrop-blur" aria-label="Zero sugar, zero calories, bold taste, zero guilt">
      <div className="marquee-track flex w-max" aria-hidden="true">
        {[0, 1].map((i) => (
          <span key={i} className="whitespace-pre font-display text-2xl font-extrabold uppercase italic tracking-wider text-white md:text-3xl">
            {run.split('•').map((part, j, arr) => (
              <span key={j}>
                {part}
                {j < arr.length - 1 && <span className="text-ice">•</span>}
              </span>
            ))}
          </span>
        ))}
      </div>
    </div>
  )
}
