import { useEffect, useRef, useState } from 'react'
import { Glass, Reveal, useInView, useMotion } from '../lib/motion'
import { badges, recommend, testimonials } from '../data/brandStats'
import { CountUp, DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

const R = 52
const C = 2 * Math.PI * R

function Ring({ percent }: { percent: number }) {
  const motion = useMotion()
  const [ref, seen] = useInView<HTMLDivElement>(0.5)
  const on = seen || !motion
  return (
    <div ref={ref} className="relative h-36 w-36 shrink-0 md:h-52 md:w-52">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="60" cy="60" r={R} fill="none" stroke="rgba(185,245,255,0.14)" strokeWidth="7" />
        <circle
          cx="60"
          cy="60"
          r={R}
          fill="none"
          stroke="#00D5E7"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={on ? C * (1 - percent / 100) : C}
          className="transition-[stroke-dashoffset] duration-[1800ms] ease-out motion-reduce:transition-none"
          style={{ filter: 'drop-shadow(0 0 6px rgba(0,213,231,0.7))' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <CountUp stat={{ value: percent, suffix: '%' }} className="text-5xl md:text-7xl" />
      </div>
    </div>
  )
}

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-1" role="img" aria-label={`${rating} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <svg key={i} width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 2.5l2.9 6.2 6.6.8-4.9 4.6 1.3 6.6L12 17.4l-5.900 3.300 1.300-6.600L2.500 9.500l6.600-.8L12 2.500Z"
            fill={i <= rating ? '#00D5E7' : 'none'}
            stroke="#00D5E7"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      ))}
    </div>
  )
}

/** Auto-rotating, swipeable testimonial rail. Pauses on hover, focus and touch. */
function Carousel() {
  const motion = useMotion()
  const rail = useRef<HTMLUListElement>(null)
  const [paused, setPaused] = useState(false)

  const step = (dir: 1 | -1) => {
    const el = rail.current
    if (!el) return
    const card = el.querySelector('li')
    const w = (card?.getBoundingClientRect().width ?? 320) + 16
    const max = el.scrollWidth - el.clientWidth
    let left = el.scrollLeft + dir * w
    if (left > max + 8) left = 0
    if (left < -8) left = max
    el.scrollTo({ left, behavior: motion ? 'smooth' : 'auto' })
  }

  useEffect(() => {
    if (!motion || paused) return
    const id = window.setInterval(() => step(1), 3600)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [motion, paused])

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      onTouchStart={() => setPaused(true)}
    >
      <ul ref={rail} tabIndex={0} aria-label="Customer testimonials" className="no-scrollbar -mx-5 flex snap-x snap-mandatory gap-4 overflow-x-auto px-5 pb-2 md:mx-0 md:px-0">
        {testimonials.map((t) => (
          <li key={t.name} className="w-[80vw] max-w-[360px] shrink-0 snap-start md:w-[calc((100%-2rem)/3)] md:max-w-none">
            <Glass as="figure" reveal="pop" hover className="flex h-full flex-col p-5 md:p-7">
              <Stars rating={t.rating} />
              <blockquote className="mt-3 text-lg font-medium leading-snug text-silver md:text-xl">“{t.quote}”</blockquote>
              <figcaption className="mt-auto pt-4 text-sm text-frost">
                <span className="font-semibold text-silver">{t.name}</span> · {t.city}
              </figcaption>
            </Glass>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex justify-end gap-2">
        {([-1, 1] as const).map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => step(d)}
            aria-label={d < 0 ? 'Previous testimonials' : 'Next testimonials'}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-frost/40 text-silver transition hover:border-cyan hover:text-cyan"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={d < 0 ? 'M15 5l-7 7 7 7' : 'M9 5l7 7-7 7'} />
            </svg>
          </button>
        ))}
      </div>
    </div>
  )
}

export function Recommendations() {
  return (
    <FlowSection id="reviews" full glow="left-[-6%] top-[2%] h-[44%] w-[66%]">
      <div>
        <div className="flex flex-col items-start gap-5 md:flex-row md:items-center md:gap-10">
          <Reveal kind="pop">
            <Ring percent={recommend.percent} />
          </Reveal>
          <Reveal delay={0.1} className="max-w-2xl">
            <p className="eyebrow mb-3">Recommendations</p>
            <h2 id="reviews-title" className="display text-[2.6rem] md:text-6xl">
              <span className="text-cyan">{recommend.percent}%</span> {recommend.text}
            </h2>
            <DemoTag className="mt-4" delay={0.9} />
          </Reveal>
        </div>

        <div className="mt-8 md:mt-12">
          <Carousel />
        </div>

        <div className="mt-8 border-t border-frost/15 pt-6 md:mt-10">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-display text-base font-bold uppercase tracking-[0.25em] text-frost">Recommended by</h3>
            <DemoTag delay={0.6} />
          </div>
          <ul className="mt-4 flex flex-wrap gap-2.5 md:gap-4">
            {badges.map((b, i) => (
              <Reveal as="li" kind="pop" delay={i * 0.09} key={b} className="flex items-center gap-2 rounded-full border border-frost/25 bg-deep/60 px-4 py-2.5 font-display text-base font-bold uppercase tracking-wider text-silver md:text-lg">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00D5E7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="9" r="6" />
                  <path d="M8.500 14l-1.500 7 5-3 5 3-1.500-7" />
                </svg>
                {b}
              </Reveal>
            ))}
          </ul>
        </div>
      </div>
    </FlowSection>
  )
}
