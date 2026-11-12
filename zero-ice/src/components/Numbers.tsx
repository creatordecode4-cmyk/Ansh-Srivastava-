import { Glass, Reveal, useInView, useMotion } from '../lib/motion'
import { bigStats, type Stat } from '../data/brandStats'
import { CountUp, DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

function StatCard({ stat, delay }: { stat: Stat; delay: number }) {
  const motion = useMotion()
  const [ref, seen] = useInView<HTMLDivElement>(0.4)
  const on = seen || !motion
  return (
    <Glass plain as="article" ref={ref} reveal="fade" delay={delay} className="flex h-full flex-col border-t border-frost/20 pt-5 md:pt-7">
      <CountUp stat={stat} className="text-4xl md:text-7xl" />
      <h3 className="mt-2 font-sans text-base font-medium text-silver/70 md:text-xl">{stat.label}</h3>
      <div className="mt-auto pt-5" aria-hidden="true">
        <div className="h-1 overflow-hidden rounded-full bg-frost/15">
          <div
            className="h-full origin-left rounded-full bg-silver/70 transition-transform duration-[1600ms] ease-out motion-reduce:transition-none"
            style={{ transform: `scaleX(${on ? stat.fill ?? 1 : 0})` }}
          />
        </div>
      </div>
    </Glass>
  )
}

export function Numbers() {
  return (
    <FlowSection id="numbers" full glow="left-[-8%] top-[2%] h-[46%] w-[64%]">
      <div>
        <Reveal className="max-w-[70%] md:max-w-none">
          <h2 id="numbers-title" className="heading text-[2rem] md:text-5xl">
            Numbers That <span>Matter.</span>
          </h2>
          <DemoTag className="mt-4" delay={1.1} />
        </Reveal>
        <ul className="mt-8 grid grid-cols-2 gap-x-5 gap-y-10 md:mt-14 md:grid-cols-3 md:gap-x-12 md:gap-y-16">
          {bigStats.map((s, i) => (
            <li key={s.label}>
              <StatCard stat={s} delay={(i % 3) * 0.1} />
            </li>
          ))}
        </ul>
      </div>
    </FlowSection>
  )
}
