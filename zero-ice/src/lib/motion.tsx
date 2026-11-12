import { createContext, forwardRef, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion, useInView as useFramerInView, useReducedMotion, type Variants } from 'framer-motion'
import { setScrollLocked } from './scroll'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

/** true = full 3D scroll experience, false = static fallback (no WebGL / low-end / reduced motion). */
export const MotionContext = createContext(true)
export const useMotion = () => useContext(MotionContext)

export function detectMotion(): boolean {
  if (typeof window === 'undefined') return false
  const q = new URLSearchParams(window.location.search)
  if (q.has('no3d')) return false
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  const nav = navigator as Navigator & { deviceMemory?: number }
  if ((nav.hardwareConcurrency && nav.hardwareConcurrency <= 2) || (nav.deviceMemory && nav.deviceMemory <= 2)) return false
  try {
    const c = document.createElement('canvas')
    const gl = c.getContext('webgl2') || c.getContext('webgl')
    if (!gl) return false
    gl.getExtension('WEBGL_lose_context')?.loseContext()
  } catch {
    return false
  }
  return true
}

/**
 * Scroll-scrubbed GSAP timeline bound to a pinned section (motion mode only).
 * `build` receives a timeline whose 0..1 maps to the section's pin progress.
 */
export function usePinTimeline(
  ref: React.RefObject<HTMLElement>,
  build: (tl: gsap.core.Timeline, mm: { mobile: boolean }) => void,
  deps: unknown[] = [],
) {
  const motion = useMotion()
  useLayoutEffect(() => {
    if (!motion || !ref.current) return
    const mm = gsap.matchMedia(ref.current)
    const make = (mobile: boolean) => () => {
      const tl = gsap.timeline({
        defaults: { ease: 'none' },
        scrollTrigger: { trigger: ref.current, start: 'top top', end: 'bottom bottom', scrub: 0.4 },
      })
      build(tl, { mobile })
      // pad so timeline positions read as pin progress 0..1
      tl.set({}, {}, 1)
    }
    mm.add('(max-width: 767px)', make(true))
    mm.add('(min-width: 768px)', make(false))
    return () => mm.revert()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [motion, ...deps])
}

/** true once the element has scrolled into view (stays true). */
export function useInView<T extends Element>(threshold = 0.35) {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && setSeen(true), { threshold })
    io.observe(el)
    return () => io.disconnect()
  }, [seen, threshold])
  return [ref, seen] as const
}

/* ------------------------------------------------------------------ */
/*  Shared motion presets (Framer Motion)                              */
/* ------------------------------------------------------------------ */

/** soft ease-out used for every fade */
export const EASE = [0.16, 1, 0.3, 1] as const
/** spring used for every pop / press / height */
export const SPRING = { type: 'spring', stiffness: 260, damping: 22 } as const
/** from-state blur for scroll-scrubbed GSAP tweens (text blocks only, never a parent of glass) */
export const BLUR_IN = 'blur(12px)'
export const BLUR_OFF = 'blur(0px)'

/** phones animate transform + opacity only: no filter blur */
const SMALL = typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches

export type RevealKind = 'fade' | 'pop'
type RevealState = 'hidden' | 'show' | 'out'

/**
 * hidden → below the fold (faded, 24px low, blurred)
 * show   → in view
 * out    → scrolled away upward (faded, lifted 16px)
 * With prefers-reduced-motion everything is a plain opacity change.
 */
export function revealVariants(kind: RevealKind, reduced: boolean, delay = 0): Variants {
  if (reduced) {
    return {
      hidden: { opacity: 0 },
      show: { opacity: 1, transition: { duration: 0.4, delay } },
      out: { opacity: 0, transition: { duration: 0.3 } },
    }
  }
  const blur = !SMALL
  const pop = kind === 'pop'
  return {
    hidden: { opacity: 0, y: 24, ...(pop ? { scale: 0.92 } : {}), ...(blur ? { filter: BLUR_IN } : {}) },
    show: {
      opacity: 1,
      y: 0,
      ...(pop ? { scale: 1 } : {}),
      ...(blur ? { filter: BLUR_OFF } : {}),
      transition: pop ? { default: { duration: 0.9, ease: EASE, delay }, scale: { ...SPRING, delay } } : { duration: 0.9, ease: EASE, delay },
      // a resting filter would switch off backdrop-filter on glass children
      ...(blur ? { transitionEnd: { filter: 'none' } } : {}),
    },
    out: { opacity: 0, y: -16, transition: { duration: 0.5, ease: EASE } },
  }
}

/** In-view state that reverses both ways, with a 2 s safety net so nothing stays hidden. */
function useRevealState(ref: React.RefObject<Element>): RevealState {
  const inView = useFramerInView(ref, { amount: 0.25, once: false, margin: '-7% 0px 0px 0px' })
  const [state, setState] = useState<RevealState>('hidden')
  useEffect(() => {
    if (inView) return setState('show')
    const r = ref.current?.getBoundingClientRect()
    setState(r && r.top < window.innerHeight * 0.35 ? 'out' : 'hidden')
  }, [inView, ref])
  useEffect(() => {
    const t = window.setTimeout(() => {
      const r = ref.current?.getBoundingClientRect()
      if (r && r.bottom > 0 && r.top < window.innerHeight) setState((s) => (s === 'hidden' ? 'show' : s))
    }, 2000)
    return () => clearTimeout(t)
  }, [ref])
  return state
}

type Tag = 'div' | 'li' | 'ul' | 'article' | 'figure' | 'p' | 'span' | 'h2' | 'h3' | 'dl'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const tag = (as: string) => (motion as any)[as] as typeof motion.div

interface RevealProps {
  as?: Tag
  kind?: RevealKind
  /** seconds; use steps of 0.08 to 0.12 to stagger siblings */
  delay?: number
  className?: string
  children?: ReactNode
  id?: string
}

/** Fade / pop an element in when it enters the viewport and out again when it leaves. */
export function Reveal({ as = 'div', kind = 'fade', delay = 0, className, children, id }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null)
  const reduced = !!useReducedMotion()
  const state = useRevealState(ref)
  const variants = useMemo(() => revealVariants(kind, reduced, delay), [kind, reduced, delay])
  const T = tag(as)
  return (
    <T ref={ref} id={id} className={className} variants={variants} initial="hidden" animate={state}>
      {children}
    </T>
  )
}

interface GlassProps {
  as?: Tag
  /** 'pop' or 'fade' animates the panel in on view; false leaves entry to the parent (e.g. a GSAP wrapper) */
  reveal?: RevealKind | false
  delay?: number
  /** lift on hover, press on tap */
  hover?: boolean
  /** no glass surface: same motion, plain text block (the page keeps real glass to four places) */
  plain?: boolean
  className?: string
  children?: ReactNode
}

/** The one frosted-glass surface. Real glass is limited to four places: navbar, lineup card, nutrition card, dialogs. Styles live in `.glass` (index.css). */
export const Glass = forwardRef<HTMLDivElement, GlassProps>(function Glass({ as = 'div', reveal = false, delay = 0, hover = false, plain = false, className = '', children }, fwd) {
  const own = useRef<HTMLDivElement>(null)
  const ref = (fwd as React.RefObject<HTMLDivElement>) ?? own
  const reduced = !!useReducedMotion()
  const state = useRevealState(ref)
  const variants = useMemo(() => (reveal ? revealVariants(reveal, reduced, delay) : undefined), [reveal, reduced, delay])
  const T = tag(as)
  return (
    <T
      ref={ref}
      className={`${plain ? 'relative' : `glass ${hover ? 'glass-hover' : ''}`} ${className}`}
      variants={variants}
      initial={reveal ? 'hidden' : false}
      animate={reveal ? state : undefined}
      whileHover={hover && !reduced ? { y: -4, scale: 1.02, transition: SPRING } : undefined}
      whileTap={hover && !reduced ? { scale: 0.97, transition: SPRING } : undefined}
    >
      {children}
    </T>
  )
})

interface PopButtonProps {
  href?: string
  variant?: 'primary' | 'ghost'
  /** pop in on view (off for buttons whose parent already animates them) */
  reveal?: boolean
  delay?: number
  className?: string
  children?: ReactNode
  type?: 'button' | 'submit'
  onClick?: (e: React.MouseEvent) => void
  'aria-label'?: string
}

/** Pill button / link: springs in, grows a touch on hover, presses to 0.97. */
export function PopButton({ href, variant = 'primary', reveal = true, delay = 0, className = '', children, type = 'button', onClick, ...rest }: PopButtonProps) {
  const ref = useRef<HTMLDivElement>(null)
  const reduced = !!useReducedMotion()
  const state = useRevealState(ref)
  const variants = useMemo(() => (reveal ? revealVariants('pop', reduced, delay) : undefined), [reveal, reduced, delay])
  const T = tag(href ? 'a' : 'button')
  const extra = href ? { href } : { type }
  return (
    <T
      ref={ref}
      {...(extra as object)}
      {...rest}
      onClick={onClick as never}
      className={`${variant === 'primary' ? 'btn-primary' : 'btn-ghost'} ${className}`}
      variants={variants}
      initial={reveal ? 'hidden' : false}
      animate={reveal ? state : undefined}
      whileHover={reduced ? undefined : { scale: 1.04, transition: SPRING }}
      whileTap={reduced ? undefined : { scale: 0.97, transition: SPRING }}
    >
      {children}
    </T>
  )
}

/** Fade + height spring for the FAQ panels and the mobile menu. */
export function Collapse({ open, id, className, children, labelledBy }: { open: boolean; id?: string; className?: string; children: ReactNode; labelledBy?: string }) {
  const reduced = !!useReducedMotion()
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          key="panel"
          id={id}
          role={labelledBy ? 'region' : undefined}
          aria-labelledby={labelledBy}
          className={className}
          style={{ overflow: 'hidden' }}
          initial={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
          animate={reduced ? { opacity: 1 } : { height: 'auto', opacity: 1 }}
          exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
          transition={reduced ? { duration: 0.2 } : { height: SPRING, opacity: { duration: 0.35, ease: EASE } }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])'

/** Glass dialog: fades + pops from 0.94 over a blurred Midnight Navy backdrop. Esc / backdrop click closes, focus is trapped and restored. */
export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const reduced = !!useReducedMotion()
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    setScrollLocked(true)
    const focusFirst = window.setTimeout(() => (panel.current?.querySelector<HTMLElement>('input') ?? panel.current)?.focus(), 60)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') return onClose()
      if (e.key !== 'Tab' || !panel.current) return
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) (e.preventDefault(), last.focus())
      else if (!e.shiftKey && document.activeElement === last) (e.preventDefault(), first.focus())
    }
    window.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(focusFirst)
      window.removeEventListener('keydown', onKey)
      setScrollLocked(false)
      opener?.focus?.()
    }
  }, [open, onClose])

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          className="modal-backdrop fixed inset-0 z-[90] flex items-center justify-center p-5"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: EASE }}
          onClick={onClose}
          data-lenis-prevent
        >
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            className="glass w-full max-w-md p-6 text-left outline-none md:p-8"
            initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94 }}
            animate={reduced ? { opacity: 1 } : { opacity: 1, scale: 1 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
            transition={reduced ? { duration: 0.2 } : { scale: SPRING, opacity: { duration: 0.25 } }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <h2 className="display text-4xl">{title}</h2>
              <button type="button" onClick={onClose} aria-label="Close dialog" className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-silver transition-colors hover:text-cyan">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                  <path d="M5 5l14 14M19 5L5 19" />
                </svg>
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

export { ScrollTrigger }
