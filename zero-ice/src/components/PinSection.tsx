import { forwardRef, type ReactNode } from 'react'
import { useMotion } from '../lib/motion'

interface Props {
  id: string
  /** scroll length in viewport heights (motion mode) */
  vh: number
  children: ReactNode
  /** layers that must sit *behind* the WebGL canvas (rendered outside the sticky stage) */
  behind?: ReactNode
  className?: string
}

/**
 * A tall section with a sticky 100svh stage. The stage sits above the fixed
 * WebGL canvas (z-20 vs z-10). In the static fallback it is a plain 100svh block.
 */
export const PinSection = forwardRef<HTMLElement, Props>(function PinSection({ id, vh, children, behind, className = '' }, ref) {
  const motion = useMotion()
  return (
    <section id={id} ref={ref} aria-labelledby={`${id}-title`} className="relative" style={motion ? { height: `${vh}svh` } : undefined}>
      {behind}
      <div className={`z-20 overflow-hidden ${motion ? 'sticky top-0 h-[100svh]' : 'relative min-h-[100svh]'} ${className}`}>{children}</div>
    </section>
  )
})
