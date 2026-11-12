import { useRef } from 'react'
import { BLUR_IN, BLUR_OFF, useMotion, usePinTimeline } from '../lib/motion'
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

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-taste="head"]', { opacity: 0, filter: BLUR_IN, y: 40 }, { opacity: 1, filter: BLUR_OFF, y: 0, duration: 0.2 }, 0)
    BARS.forEach((b, i) => {
      tl.fromTo(`[data-taste="row-${i}"]`, { opacity: 0, filter: BLUR_IN, x: -30 }, { opacity: 1, filter: BLUR_OFF, x: 0, duration: 0.12 }, 0.12 + i * 0.12)
      tl.fromTo(`[data-taste="fill-${i}"]`, { scaleX: 0 }, { scaleX: b.value / 100, duration: 0.4, ease: 'power1.out' }, 0.16 + i * 0.12)
    })
  })

  return (
    <PinSection id="taste" vh={sectionVh.taste} ref={ref} tone="gradient" glow="left-[-10%] top-[18%] hidden h-[60%] w-[58%] md:block">
      <div className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 bottom-[5svh] md:inset-x-auto md:bottom-auto md:left-[7%] md:top-1/2 md:w-[40%] md:-translate-y-1/2">
          <div data-taste="head">
            <h2 id="taste-title" className="heading text-[2rem] md:text-[clamp(2.4rem,3.6vw,3.75rem)]">
              Bold up front. <span>Clean finish.</span>
            </h2>
          </div>
          <ul className="mt-6 space-y-4 md:mt-10 md:space-y-6" aria-label="Taste profile, out of 100">
            {BARS.map((b, i) => (
              <li key={b.label} data-taste={`row-${i}`}>
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="font-sans text-xl font-medium text-silver md:text-2xl">{b.label}</span>
                  <span className="heading text-lg md:text-3xl">
                    {b.value}
                    <span className="ml-1 text-base text-silver/70">/100</span>
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-frost/10" aria-hidden="true">
                  <div
                    data-taste={`fill-${i}`}
                    className="h-full origin-left rounded-full bg-silver/80"
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
