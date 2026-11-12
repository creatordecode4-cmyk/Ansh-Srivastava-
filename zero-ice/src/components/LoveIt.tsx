import { useReveal } from '../lib/motion'
import { loveCards } from '../data/brandStats'
import { DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

const ICONS: Record<(typeof loveCards)[number]['icon'], JSX.Element> = {
  snow: <path d="M12 2v20M3.300 7l17.400 10M20.700 7L3.300 17M9 4l3 3 3-3M9 20l3-3 3 3M4 12.500l4-1-1-4M20 11.500l-4 1 1 4M5 16l4-1M19 8l-4 1" />,
  bolt: <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8Z" />,
  meal: <path d="M5 2v8a3 3 0 0 0 6 0V2M8 2v20M17 2c-2 2-3 5-3 8s1 4 3 4v8" />,
}

export function LoveIt() {
  const reveal = useReveal<HTMLDivElement>()
  return (
    <FlowSection id="love" tone="gradient" glow="left-[18%] top-[2%] h-[50%] w-[64%]">
      <div ref={reveal}>
        <div data-reveal className="max-w-[72%] md:mx-auto md:max-w-none md:text-center">
          <p className="eyebrow mb-3">The Verdict</p>
          <h2 id="love-title" className="display text-5xl md:text-7xl">
            Why People <span className="text-cyan">Love It.</span>
          </h2>
          <DemoTag className="mt-4" />
        </div>
        <ul className="mt-8 grid gap-3 md:mt-12 md:grid-cols-3 md:gap-6">
          {loveCards.map((c) => (
            <li key={c.title} data-reveal>
              <article className="glass flex h-full items-start gap-4 p-5 md:block md:p-8">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-cyan/40 bg-midnight/50 shadow-[0_0_24px_-8px_rgba(0,213,231,0.7)]">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00D5E7" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    {ICONS[c.icon]}
                  </svg>
                </span>
                <div>
                  <h3 className="display text-3xl md:mt-5 md:text-4xl">{c.title}</h3>
                  <p className="mt-1.5 text-base leading-snug text-frost md:mt-3 md:text-lg">{c.stat}</p>
                </div>
              </article>
            </li>
          ))}
        </ul>
      </div>
    </FlowSection>
  )
}
