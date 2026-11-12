import { useEffect, useState } from 'react'
import { useInView, useMotion } from '../lib/motion'
import { DEMO_TAG, type Stat } from '../data/brandStats'

const fmt = (v: number, decimals = 0) => v.toFixed(decimals)

/**
 * Counts up to `value` when scrolled into view. The final text is always in the
 * layout (invisible) so the width is reserved and nothing shifts while counting.
 * With reduced motion / the static fallback it shows the final number at once.
 */
export function CountUp({ stat, className = '', unitClass = '' }: { stat: Pick<Stat, 'value' | 'decimals' | 'suffix' | 'unit'>; className?: string; unitClass?: string }) {
  const motion = useMotion()
  const [ref, seen] = useInView<HTMLSpanElement>(0.5)
  const [now, setNow] = useState(motion ? 0 : stat.value)

  useEffect(() => {
    if (!motion || !seen) return
    let raf = 0
    const t0 = performance.now()
    const dur = 1600
    const tick = (t: number) => {
      const k = Math.min((t - t0) / dur, 1)
      setNow(stat.value * (1 - Math.pow(1 - k, 3)))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [motion, seen, stat.value])

  const body = (v: number) => (
    <>
      {fmt(v, stat.decimals)}
      {stat.suffix}
      {stat.unit && <span className={`ml-[0.18em] text-[0.42em] not-italic text-frost ${unitClass}`}>{stat.unit}</span>}
    </>
  )
  return (
    <span ref={ref} className={`stat-num relative inline-block whitespace-nowrap ${className}`}>
      <span className="invisible" aria-hidden="true">
        {body(stat.value)}
      </span>
      <span className="absolute inset-0" aria-hidden="true">
        {body(now)}
      </span>
      <span className="sr-only">
        {fmt(stat.value, stat.decimals)}
        {stat.suffix} {stat.unit}
      </span>
    </span>
  )
}

/** Small tag that marks placeholder figures. */
export function DemoTag({ label = DEMO_TAG, className = '' }: { label?: string; className?: string }) {
  return <span className={`demo-tag ${className}`}>{label}</span>
}
