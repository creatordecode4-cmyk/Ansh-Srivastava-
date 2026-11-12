import { createContext, useContext, useEffect, useLayoutEffect, useRef } from 'react'
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

/** Simple fade-in on view for the static fallback. */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const motion = useMotion()
  useEffect(() => {
    const el = ref.current
    if (!el || motion) return
    const items = el.querySelectorAll<HTMLElement>('[data-reveal]')
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return
    items.forEach((i) => i.classList.add('reveal'))
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && (e.target.classList.add('is-in'), io.unobserve(e.target))),
      { threshold: 0.15 },
    )
    items.forEach((i) => io.observe(i))
    return () => io.disconnect()
  }, [motion])
  return ref
}

export { ScrollTrigger }
