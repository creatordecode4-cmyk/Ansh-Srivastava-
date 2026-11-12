import { useRef } from 'react'
import { usePinTimeline, useReveal } from '../lib/motion'
import { journey } from '../data/brandStats'
import { sectionVh } from '../tokens'
import { DemoTag } from './CountUp'
import { PinSection } from './PinSection'

export function Journey() {
  const ref = useRef<HTMLElement>(null)
  const reveal = useReveal<HTMLDivElement>()
  const n = journey.steps.length

  // the line draws itself with scroll and each node lights up as the line reaches it
  usePinTimeline(ref, (tl, { mobile }) => {
    tl.fromTo('[data-j="head"]', { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.1 }, 0)
    tl.fromTo(mobile ? '[data-j="line-v"]' : '[data-j="line-h"]', mobile ? { scaleY: 0 } : { scaleX: 0 }, { scaleX: 1, scaleY: 1, duration: 0.76 }, 0.1)
    journey.steps.forEach((_, i) => {
      const at = 0.1 + (i / (n - 1)) * 0.76 * (mobile ? 0.94 : 0.9)
      tl.fromTo(`[data-j="dot-${i}"]`, { scale: 0.4, backgroundColor: '#071522' }, { scale: 1, backgroundColor: '#00D5E7', duration: 0.05 }, at)
      tl.fromTo(`[data-j="step-${i}"]`, { opacity: 0.22, y: 10 }, { opacity: 1, y: 0, duration: 0.07 }, at)
    })
  })

  return (
    <PinSection id="journey" vh={sectionVh.journey} ref={ref} glow="left-[-10%] top-[4%] h-[55%] w-[70%]">
      <div ref={reveal} className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 top-[11svh] md:inset-x-auto md:left-[6%] md:top-[19svh] md:w-[56%]">
          <div data-j="head" data-reveal>
            <p className="eyebrow mb-3">Our Journey</p>
            <h2 id="journey-title" className="display text-5xl md:text-[clamp(4rem,6.6vw,8rem)]">
              {journey.title[0]} <span className="block text-cyan">{journey.title[1]}</span>
            </h2>
            <DemoTag className="mt-4" />
          </div>
        </div>

        <ol className="absolute inset-x-5 bottom-[4svh] md:inset-x-[6%] md:bottom-[11svh] md:grid md:grid-cols-6 md:gap-4">
          {/* track + drawn line: vertical on mobile, horizontal on desktop */}
          <li className="absolute bottom-3 left-[9px] top-3 w-0.5 bg-frost/15 md:hidden" aria-hidden="true">
            <span data-j="line-v" className="block h-full w-full origin-top bg-cyan shadow-[0_0_12px_rgba(0,213,231,0.8)]" />
          </li>
          <li className="absolute left-0 right-0 top-[9px] hidden h-0.5 bg-frost/15 md:block" aria-hidden="true">
            <span data-j="line-h" className="block h-full w-full origin-left bg-cyan shadow-[0_0_12px_rgba(0,213,231,0.8)]" />
          </li>
          {journey.steps.map((s, i) => (
            <li key={s.year} data-reveal className="relative flex min-h-[3.9rem] items-start gap-4 md:block md:min-h-0">
              <span data-j={`dot-${i}`} className="relative z-10 mt-1 block h-5 w-5 shrink-0 rounded-full border-2 border-cyan bg-cyan shadow-[0_0_14px_rgba(0,213,231,0.7)] md:mt-0" aria-hidden="true" />
              <div data-j={`step-${i}`} className="flex items-baseline gap-3 md:mt-5 md:block">
                <p className="stat-num text-3xl md:text-5xl">{s.year}</p>
                <p className="text-base leading-snug text-silver md:mt-2 md:max-w-[12rem] md:text-lg">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </PinSection>
  )
}
