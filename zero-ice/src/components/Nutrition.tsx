import { useRef } from 'react'
import { Glass, usePinTimeline } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

const FACTS = [
  { label: 'Serving size', value: '330 ml' },
  { label: 'Calories', value: '0' },
  { label: 'Sugar', value: '0 g' },
]

export function Nutrition() {
  const ref = useRef<HTMLElement>(null)

  usePinTimeline(ref, (tl, { mobile }) => {
    tl.fromTo('[data-nut="card"]', { opacity: 0, x: mobile ? 0 : 80, y: mobile ? 40 : 0 }, { opacity: 1, x: 0, y: 0, duration: 0.3 }, 0)
    tl.fromTo('[data-nut="row"]', { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.14, stagger: 0.1 }, 0.14)
  })

  return (
    <PinSection id="nutrition" vh={sectionVh.nutrition} ref={ref} tone="gradient">
      <div className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 bottom-[5svh] md:inset-x-auto md:bottom-auto md:right-[8%] md:top-1/2 md:w-[min(38vw,480px)] md:-translate-y-1/2">
          <div data-nut="card">
            <Glass hover className="p-6 md:p-9">
            <h2 id="nutrition-title" className="heading text-[2rem] md:text-[2.75rem]">
              Nutrition Facts
            </h2>
            <p className="mt-1 text-sm text-silver/70">Per 330 ml can</p>
            <dl className="mt-5 border-t-4 border-silver">
              {FACTS.map((f) => (
                <div key={f.label} data-nut="row" className="flex items-baseline justify-between border-b border-frost/20 py-3 md:py-4">
                  <dt className="font-sans text-xl font-medium text-silver md:text-2xl">{f.label}</dt>
                  <dd className="heading text-2xl md:text-3xl">{f.value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-sm text-silver/70">Sample values for demo purposes.</p>
            </Glass>
          </div>
        </div>
      </div>
    </PinSection>
  )
}
