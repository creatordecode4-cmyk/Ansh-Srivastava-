import { useRef } from 'react'
import { useMotion, usePinTimeline, useReveal } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

const BARS = [
  { label: 'Fizz', value: 92 },
  { label: 'Chill', value: 100 },
  { label: 'Boldness', value: 88 },
]

export function Taste() {
  const ref = useRef<HTMLElement>(null)
  const motion = useMotion()
  const reveal = useReveal<HTMLDivElement>()

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-taste="head"]', { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.2 }, 0)
    BARS.forEach((b, i) => {
      tl.fromTo(`[data-taste="row-${i}"]`, { opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.12 }, 0.12 + i * 0.12)
      tl.fromTo(`[data-taste="fill-${i}"]`, { scaleX: 0 }, { scaleX: b.value / 100, duration: 0.4, ease: 'power1.out' }, 0.16 + i * 0.12)
    })
  })

  return (
    <PinSection id="taste" vh={sectionVh.taste} ref={ref} tone="gradient" glow="left-[-10%] top-[18%] hidden h-[60%] w-[58%] md:block">
      <div ref={reveal} className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 bottom-[5svh] md:inset-x-auto md:bottom-auto md:left-[7%] md:top-1/2 md:w-[40%] md:-translate-y-1/2">
          <div data-taste="head" data-reveal>
            <p className="eyebrow mb-3">Taste Profile</p>
            <h2 id="taste-title" className="display text-5xl md:text-[clamp(3.5rem,5.6vw,6.5rem)]">
              Bold up front. <span className="text-cyan">Clean finish.</span>
            </h2>
          </div>
          <ul className="mt-6 space-y-4 md:mt-10 md:space-y-6" aria-label="Taste profile, out of 100">
            {BARS.map((b, i) => (
              <li key={b.label} data-taste={`row-${i}`} data-reveal>
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="font-display text-xl font-bold uppercase tracking-[0.2em] text-silver md:text-2xl">{b.label}</span>
                  <span className="display text-2xl md:text-3xl">
                    {b.value}
                    <span className="ml-1 text-base text-frost">/100</span>
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-frost/10" aria-hidden="true">
                  <div
                    data-taste={`fill-${i}`}
                    className="h-full origin-left rounded-full bg-gradient-to-r from-cyan to-frost"
                    style={{ transform: `scaleX(${motion ? 0 : b.value / 100})` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </PinSection>
  )
}
