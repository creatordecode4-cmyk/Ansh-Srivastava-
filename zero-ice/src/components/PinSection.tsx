import { forwardRef, type ReactNode } from 'react'
import { Reveal, useMotion } from '../lib/motion'

interface Common {
  id: string
  children: ReactNode
  /** 'gradient' paints a subtle Midnight Navy → Deep Blue wash; default is plain Midnight Navy */
  tone?: 'navy' | 'gradient'
  /** position/size classes for a faint cyan glow behind the heading */
  glow?: string
  className?: string
}

/** Section tone. Sits behind the fixed WebGL canvas (z-0 vs z-10). */
/** Tones and heading glows were removed with the matte concrete theme; the props are kept so sections need no edits. */
function Tone(_: { tone?: Common['tone'] }) {
  return null
}
function Glow(_: { glow?: string }) {
  return null
}

interface PinProps extends Common {
  /** scroll length in viewport heights (motion mode) */
  vh: number
  /** layers that must sit *behind* the WebGL canvas (rendered outside the sticky stage) */
  behind?: ReactNode
}

/**
 * A tall section with a sticky 100svh stage. The stage sits above the fixed
 * WebGL canvas (z-20 vs z-10). In the static fallback it is a plain 100svh block.
 */
export const PinSection = forwardRef<HTMLElement, PinProps>(function PinSection({ id, vh, children, behind, tone, glow, className = '' }, ref) {
  const motion = useMotion()
  return (
    <section id={id} ref={ref} aria-labelledby={`${id}-title`} className="relative" style={motion ? { height: `${vh}svh` } : undefined}>
      <Tone tone={tone} />
      {behind}
      <div className={`z-20 overflow-hidden ${motion ? 'sticky top-0 h-[100svh]' : 'relative min-h-[100svh]'} ${className}`}>
        <Glow glow={glow} />
        {/* the whole stage fades in on entry and lifts out when it leaves upward */}
        <Reveal className={motion ? 'absolute inset-0' : 'relative min-h-[100svh]'}>{children}</Reveal>
      </div>
    </section>
  )
})

/** A normal-flow section (not pinned). Content scrolls over the fixed canvas. */
export const FlowSection = forwardRef<HTMLElement, Common & { full?: boolean }>(function FlowSection({ id, children, tone, glow, full, className = '' }, ref) {
  return (
    <section id={id} ref={ref} aria-labelledby={`${id}-title`} className="relative">
      <Tone tone={tone} />
      <div className={`relative z-20 mx-auto flex max-w-[1300px] flex-col justify-center px-5 py-20 md:px-10 md:py-28 ${full ? 'min-h-[100lvh]' : ''} ${className}`}>
        <Glow glow={glow} />
        {children}
      </div>
    </section>
  )
})
