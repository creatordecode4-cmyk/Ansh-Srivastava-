import { useRef } from 'react'
import { usePinTimeline, useReveal } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

export function Story() {
  const ref = useRef<HTMLElement>(null)
  const reveal = useReveal<HTMLDivElement>()

  usePinTimeline(ref, (tl, { mobile }) => {
    const dx = mobile ? 0 : 70
    tl.fromTo('[data-story="head"]', { opacity: 0, x: -dx, y: mobile ? 30 : 0 }, { opacity: 1, x: 0, y: 0, duration: 0.2 }, 0.04)
      .fromTo('[data-story="copy"]', { opacity: 0, x: dx, y: mobile ? 30 : 0 }, { opacity: 1, x: 0, y: 0, duration: 0.2 }, 0.3)
      .fromTo('[data-story="meter"]', { scaleX: 0 }, { scaleX: 1, duration: 0.96 }, 0.02)
  })

  return (
    <PinSection id="story" vh={sectionVh.story} ref={ref} tone="gradient" glow="left-[-12%] top-[22%] hidden h-[56%] w-[52%] md:block">
      <div ref={reveal} className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 top-[12svh] text-center md:inset-x-auto md:left-[6%] md:top-1/2 md:w-[27%] md:-translate-y-1/2 md:text-left">
          <div data-story="head" data-reveal>
            <p className="eyebrow mb-3">The Story</p>
            <h2 id="story-title" className="display text-6xl md:text-[clamp(4rem,7vw,8.5rem)]">
              Born <span className="text-cyan">Cold.</span>
            </h2>
          </div>
        </div>
        <div className="absolute inset-x-5 bottom-[7svh] text-center md:inset-x-auto md:bottom-auto md:right-[6%] md:top-1/2 md:w-[25%] md:-translate-y-1/2 md:text-left">
          <div data-story="copy" data-reveal>
            <p className="text-lg leading-relaxed text-silver md:text-2xl md:leading-snug">
              We took the chill of crushed ice and the kick of cola, and removed everything else.
            </p>
            <div className="mx-auto mt-5 flex max-w-[16rem] items-center gap-3 md:mx-0" aria-hidden="true">
              <span className="font-display text-sm font-bold uppercase tracking-[0.25em] text-frost">360°</span>
              <span className="h-px flex-1 bg-frost/15">
                <span data-story="meter" className="block h-px origin-left bg-cyan" />
              </span>
            </div>
          </div>
        </div>
      </div>
    </PinSection>
  )
}
