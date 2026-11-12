import { useRef } from 'react'
import { useMotion, usePinTimeline, useReveal } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

const CARDS = [
  { key: 'sugar', big: '0 g', title: 'Zero Sugar', body: 'All of the cola kick. None of the sugar.', pos: 'md:left-[6%] md:top-[25%]', depth: 'md:scale-100' },
  { key: 'cal', big: '0', title: 'Zero Calories', body: 'Nothing to count. Just crack it open.', pos: 'md:right-[6%] md:top-[38%]', depth: 'md:scale-110' },
  { key: 'crisp', big: 'Ice', title: 'Ice-Cold Crisp', body: 'Built to be served cold, with a clean, crisp finish.', pos: 'md:left-[11%] md:top-[60%]', depth: 'md:scale-90' },
]

export function WhyZero() {
  const ref = useRef<HTMLElement>(null)
  const motion = useMotion()
  const reveal = useReveal<HTMLDivElement>()

  usePinTimeline(ref, (tl, { mobile }) => {
    tl.fromTo('[data-why="title"]', { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.1 }, 0)
    if (mobile) {
      // one card at a time under the can
      const slots = [0.06, 0.38, 0.7]
      slots.forEach((t, i) => {
        tl.fromTo(`[data-why="card-${i}"]`, { opacity: 0, x: i % 2 ? 60 : -60 }, { opacity: 1, x: 0, duration: 0.12 }, t)
        if (i < 2) tl.to(`[data-why="card-${i}"]`, { opacity: 0, x: i % 2 ? -40 : 40, duration: 0.08 }, t + 0.24)
      })
    } else {
      tl.fromTo('[data-why="card-0"]', { opacity: 0, x: -160 }, { opacity: 1, x: 0, duration: 0.18 }, 0.08)
        .fromTo('[data-why="card-1"]', { opacity: 0, x: 200 }, { opacity: 1, x: 0, duration: 0.18 }, 0.3)
        .fromTo('[data-why="card-2"]', { opacity: 0, x: -130 }, { opacity: 1, x: 0, duration: 0.18 }, 0.52)
        // slow parallax drift at different depths
        .fromTo('[data-why="card-0"]', { y: 30 }, { y: -30, duration: 1 }, 0)
        .fromTo('[data-why="card-1"]', { y: 60 }, { y: -60, duration: 1 }, 0)
        .fromTo('[data-why="card-2"]', { y: 15 }, { y: -15, duration: 1 }, 0)
    }
  })

  return (
    <PinSection id="why" vh={sectionVh.why} ref={ref} tone="gradient" glow="left-[20%] top-[-6%] h-[44%] w-[60%]">
      <div ref={reveal} className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 top-[11svh] text-center md:top-[13svh]">
          <div data-why="title" data-reveal>
            <p className="eyebrow mb-2">Why Zero</p>
            <h2 id="why-title" className="display text-5xl md:text-7xl">
              Nothing <span className="text-cyan">Extra.</span>
            </h2>
          </div>
        </div>
        <ul className={`absolute inset-x-5 bottom-[5svh] md:static ${motion ? 'h-[11.5rem] md:h-auto' : 'flex flex-col gap-3 md:block'}`}>
          {CARDS.map((c, i) => (
            <li key={c.key} className={`${motion ? 'absolute inset-0' : 'relative'} md:absolute md:inset-auto md:w-[min(24vw,340px)] ${c.pos}`}>
              <div className={`origin-center ${c.depth}`}>
                <article data-why={`card-${i}`} data-reveal className="glass flex items-center gap-5 p-5 md:block md:p-7">
                  <p className="display w-[4.2rem] shrink-0 text-center text-5xl !normal-case !text-cyan md:w-auto md:text-left md:text-7xl" aria-hidden="true">
                    {c.big}
                  </p>
                  <div>
                    <h3 className="display text-3xl md:mt-3 md:text-4xl">{c.title}</h3>
                    <p className="mt-1.5 text-base leading-snug text-frost md:mt-2">{c.body}</p>
                  </div>
                </article>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </PinSection>
  )
}
