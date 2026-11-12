import { trustStats } from '../data/brandStats'
import { CountUp, DemoTag } from './CountUp'

/** Slim glass bar of four counters, right under the hero ticker. */
export function TrustStrip() {
  return (
    <section id="trust" aria-label="ZERO ICE in numbers" className="relative z-20 px-5 py-8 md:px-10 md:py-10">
      <div className="glass relative mx-auto max-w-[1300px] px-4 py-6 md:px-10 md:py-7">
        <DemoTag className="absolute -top-3 right-4 !bg-midnight md:right-8" />
        <dl className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-4 md:divide-x md:divide-frost/15">
          {trustStats.map((s) => (
            <div key={s.label} className="flex flex-col-reverse items-center text-center md:px-6">
              <dt className="mt-1.5 font-display text-sm font-bold uppercase tracking-[0.2em] text-frost md:text-base">{s.label}</dt>
              <dd>
                <CountUp stat={s} className="text-5xl md:text-6xl" />
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
