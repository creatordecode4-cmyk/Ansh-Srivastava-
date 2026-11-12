import { useEffect, useRef, useState } from 'react'
import { ScrollTrigger, useMotion, usePinTimeline, useReveal } from '../lib/motion'
import { scrollToSection } from '../lib/scroll'
import { sectionVh, variants, type VariantId } from '../tokens'
import { carouselAt } from '../three/scrollStore'
import { PinSection } from './PinSection'

/** where in the pin each can is front and centre */
const STOPS = [0.04, 0.5, 0.96]

function VariantCard({ v, notified, onNotify }: { v: (typeof variants)[number]; notified: boolean; onNotify: () => void }) {
  return (
    <article className="glass p-5 text-center md:p-6">
      <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-frost">
        {v.available ? 'Available now' : 'Coming soon'}
      </p>
      <h3 className="display mt-1.5 text-4xl md:text-5xl">{v.name}</h3>
      <p className="mx-auto mt-2 max-w-md text-base text-frost">{v.blurb}</p>
      <div className="mt-4 flex min-h-[44px] items-center justify-center" aria-live="polite">
        {v.available ? (
          <a href="#cta" className="btn-primary" onClick={(e) => (e.preventDefault(), scrollToSection('cta', 0.9))}>
            Buy Now
          </a>
        ) : notified ? (
          <p className="pop-in font-display text-lg font-bold uppercase tracking-widest text-silver">✓ You're on the list</p>
        ) : (
          <button type="button" className="btn-ghost" onClick={onNotify}>
            Notify me
          </button>
        )}
      </div>
    </article>
  )
}

export function Lineup() {
  const ref = useRef<HTMLElement>(null)
  const motion = useMotion()
  const reveal = useReveal<HTMLDivElement>()
  const [active, setActive] = useState(0)
  const [notified, setNotified] = useState<Partial<Record<VariantId, boolean>>>({})
  const notify = (id: VariantId) => setNotified((n) => ({ ...n, [id]: true }))

  // which can faces the camera (same curve the 3D carousel uses)
  useEffect(() => {
    if (!motion || !ref.current) return
    const st = ScrollTrigger.create({
      trigger: ref.current,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (s) => setActive(Math.round(carouselAt(s.progress))),
    })
    return () => st.kill()
  }, [motion])

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-lineup="head"]', { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.06 }, 0)
  })

  const v = variants[active]

  return (
    <PinSection id="lineup" vh={sectionVh.lineup} ref={ref} glow="left-[20%] top-[-6%] h-[42%] w-[60%]">
      <div ref={reveal} className={motion ? 'absolute inset-0' : 'mx-auto max-w-6xl px-5 py-24'}>
        <div className={motion ? 'absolute inset-x-5 top-[11svh] text-center md:top-[12svh]' : 'text-center'}>
          <div data-lineup="head" data-reveal>
            <p className="eyebrow mb-2">The Lineup</p>
            <h2 id="lineup-title" className="display text-5xl md:text-7xl">
              Pick Your <span className="text-cyan">Chill.</span>
            </h2>
          </div>
        </div>
        {motion ? (
          <div className="absolute inset-x-5 bottom-[3svh] mx-auto max-w-xl">
            <div key={v.id} className="pop-in">
              <VariantCard v={v} notified={!!notified[v.id]} onNotify={() => notify(v.id)} />
            </div>
            <div className="mt-3 flex justify-center gap-1" role="group" aria-label="Choose a flavour">
              {variants.map((x, i) => (
                <button
                  key={x.id}
                  type="button"
                  aria-label={x.name}
                  aria-pressed={i === active}
                  onClick={() => scrollToSection('lineup', STOPS[i])}
                  className="flex h-11 w-11 items-center justify-center"
                >
                  <span className={`block h-1.5 rounded-full transition-all duration-300 ${i === active ? 'w-8 bg-cyan' : 'w-3 bg-frost/35'}`} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="mt-10 grid gap-5 md:grid-cols-3">
            {variants.map((x) => (
              <li key={x.id} data-reveal>
                <VariantCard v={x} notified={!!notified[x.id]} onNotify={() => notify(x.id)} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </PinSection>
  )
}
