import { useRef } from 'react'
import { usePinTimeline, useReveal } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

const QUOTES = [
  { quote: 'Tastes like the first sip, every sip.', name: 'Frostbyte', handle: '@frostbyte' },
  { quote: 'I came for zero sugar. I stayed for the crack of the can.', name: 'Mila', handle: '@mila.on.ice' },
  { quote: 'My fridge has a dedicated shelf now.', name: 'Desk Jockey', handle: '@deskjockey' },
]

export function FanWall() {
  const ref = useRef<HTMLElement>(null)
  const reveal = useReveal<HTMLDivElement>()

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-fan="head"]', { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.15 }, 0)
    tl.fromTo('[data-fan="card"]', { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 0.22, stagger: 0.12 }, 0.06)
  })

  return (
    <PinSection id="fans" vh={sectionVh.fans} ref={ref}>
      <div ref={reveal} className="absolute inset-0 mx-auto flex max-w-[1300px] flex-col justify-center px-5 pt-16 md:px-10">
        <div data-fan="head" data-reveal className="max-w-[62%] md:max-w-none">
          <p className="eyebrow mb-2">07 · Fan Wall</p>
          <h2 id="fans-title" className="display text-5xl md:text-7xl">
            Heard on <span className="text-ice">Ice.</span>
          </h2>
          <p className="mt-3 inline-block rounded-full border border-white/25 px-3 py-1 font-display text-sm font-bold uppercase tracking-[0.2em] text-silver">Demo content</p>
        </div>
        <ul className="mt-6 grid gap-3 md:mt-12 md:grid-cols-3 md:gap-6">
          {QUOTES.map((q) => (
            <li key={q.handle} data-fan="card" data-reveal>
              <figure className="glass h-full p-5 md:p-8">
                <svg width="28" height="22" viewBox="0 0 28 22" aria-hidden="true" className="mb-3 hidden text-ice md:block">
                  <path d="M0 22V12C0 5 4 1 11 0v4c-3 1-5 3-5 6h5v12H0Zm16 0V12c0-7 4-11 11-12v4c-3 1-5 3-5 6h5v12H16Z" fill="currentColor" />
                </svg>
                <blockquote className="text-lg font-medium leading-snug text-white md:text-2xl">“{q.quote}”</blockquote>
                <figcaption className="mt-3 text-sm text-silver md:mt-6">
                  <span className="font-semibold text-white">{q.name}</span> · {q.handle}
                </figcaption>
              </figure>
            </li>
          ))}
        </ul>
      </div>
    </PinSection>
  )
}
