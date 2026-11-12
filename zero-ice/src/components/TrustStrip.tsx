import { Glass, Reveal } from '../lib/motion'
import { trustStats } from '../data/brandStats'
import { CountUp, DemoTag } from './CountUp'

/** Slim row of four counters, right under the hero ticker. */
export function TrustStrip() {
  return (
    <section id="trust" aria-label="ZERO ICE in numbers" className="relative z-20 px-5 py-8 md:px-10 md:py-10">
      <Glass plain reveal="fade" className="mx-auto max-w-[1300px] border-y border-frost/15 px-2 py-7 md:px-6 md:py-9">
        <DemoTag className="absolute -top-3 right-2 !bg-midnight md:right-6" delay={0.9} />
        <dl className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-4 md:divide-x md:divide-frost/15">
          {trustStats.map((s, i) => (
            // number and label count up and fade in together, one tile after another
            <Reveal key={s.label} delay={0.15 + i * 0.1} className="flex flex-col-reverse items-center text-center md:px-6">
              <dt className="mt-1.5 font-sans text-sm font-medium text-silver/70 md:text-base">{s.label}</dt>
              <dd>
                <CountUp stat={s} className="text-3xl md:text-5xl" />
              </dd>
            </Reveal>
          ))}
        </dl>
      </Glass>
    </section>
  )
}
