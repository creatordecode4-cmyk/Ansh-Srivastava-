import { Glass, Reveal, useInView, useMotion } from '../lib/motion'
import { bigStats, type Stat } from '../data/brandStats'
import { CountUp, DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

function StatCard({ stat, delay }: { stat: Stat; delay: number }) {
  const motion = useMotion()
  const [ref, seen] = useInView<HTMLDivElement>(0.4)
  const on = seen || !motion
  return (
    <Glass as="article" ref={ref} reveal="pop" delay={delay} hover className="flex h-full flex-col p-5 md:p-8">
      <CountUp stat={stat} className="text-[3.4rem] md:text-8xl" />
      <h3 className="mt-2 font-display text-base font-bold uppercase tracking-[0.18em] text-frost md:text-xl">{stat.label}</h3>
      <div className="mt-auto pt-5" aria-hidden="true">
        <div className="h-1 overflow-hidden rounded-full bg-frost/15">
          <div
            className="h-full origin-left rounded-full bg-cyan transition-transform duration-[1600ms] ease-out motion-reduce:transition-none"
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
          <p className="eyebrow mb-3">By the Numbers</p>
          <h2 id="numbers-title" className="display text-5xl md:text-7xl">
            Numbers That <span className="text-cyan">Matter.</span>
          </h2>
          <DemoTag className="mt-4" delay={1.1} />
        </Reveal>
        <ul className="mt-8 grid grid-cols-2 gap-3 md:mt-12 md:grid-cols-3 md:gap-6">
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
