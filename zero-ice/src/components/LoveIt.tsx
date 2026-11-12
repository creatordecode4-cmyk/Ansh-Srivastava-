import { Glass, Reveal } from '../lib/motion'
import { loveCards } from '../data/brandStats'
import { DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

const ICONS: Record<(typeof loveCards)[number]['icon'], JSX.Element> = {
  snow: <path d="M12 2v20M3.300 7l17.400 10M20.700 7L3.300 17M9 4l3 3 3-3M9 20l3-3 3 3M4 12.500l4-1-1-4M20 11.500l-4 1 1 4M5 16l4-1M19 8l-4 1" />,
  bolt: <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8Z" />,
  meal: <path d="M5 2v8a3 3 0 0 0 6 0V2M8 2v20M17 2c-2 2-3 5-3 8s1 4 3 4v8" />,
}

export function LoveIt() {
  return (
    <FlowSection id="love" tone="gradient" glow="left-[18%] top-[2%] h-[50%] w-[64%]">
      <div>
        <Reveal className="max-w-[72%] md:mx-auto md:max-w-none md:text-center">
          <h2 id="love-title" className="heading text-[2rem] md:text-5xl">
            Why People <span>Love It.</span>
          </h2>
          <DemoTag className="mt-4" delay={0.9} />
        </Reveal>
        <ul className="mt-8 grid gap-8 md:mt-14 md:grid-cols-3 md:gap-12">
          {loveCards.map((c, i) => (
            <li key={c.title}>
              <Glass plain as="article" reveal="fade" delay={i * 0.1} className="flex h-full items-start gap-4 md:block">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-frost/25 bg-transparent">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#F4F9FC" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    {ICONS[c.icon]}
                  </svg>
                </span>
                <div>
                  <h3 className="heading text-xl md:mt-5 md:text-2xl">{c.title}</h3>
                  <p className="mt-1.5 text-base leading-snug text-silver/70 md:mt-3 md:text-lg">{c.stat}</p>
                </div>
              </Glass>
            </li>
          ))}
        </ul>
      </div>
    </FlowSection>
  )
}
