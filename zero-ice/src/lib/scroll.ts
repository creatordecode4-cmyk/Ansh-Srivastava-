import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import { SECTION_IDS, scrollStore } from '../three/scrollStore'

gsap.registerPlugin(ScrollTrigger)

let lenis: Lenis | null = null

/** Lenis smooth scroll + ScrollTrigger feeding the shared scroll store. Returns a cleanup. */
export function initScroll() {
  lenis = new Lenis({ lerp: 0.1, wheelMultiplier: 0.9 })
  lenis.on('scroll', ScrollTrigger.update)
  const raf = (t: number) => {
    lenis!.raf(t * 1000)
    scrollStore.velocity = lenis!.velocity
    scrollStore.progress = lenis!.progress || 0
  }
  gsap.ticker.add(raf)
  gsap.ticker.lagSmoothing(0)

  const triggers: ScrollTrigger[] = []
  SECTION_IDS.forEach((id) => {
    const el = document.getElementById(id)
    if (!el) return
    const sec = scrollStore.sections[id]
    if (id !== 'hero') {
      const set = (s: ScrollTrigger) => (sec.enter = s.progress)
      triggers.push(ScrollTrigger.create({ trigger: el, start: 'top bottom', end: 'top top', onUpdate: set, onRefresh: set }))
    }
    const setPin = (s: ScrollTrigger) => (sec.pin = s.progress)
    triggers.push(ScrollTrigger.create({ trigger: el, start: 'top top', end: 'bottom bottom', onUpdate: setPin, onRefresh: setPin }))
  })

  const mq = window.matchMedia('(max-width: 767px)')
  const onMq = () => (scrollStore.isMobile = mq.matches)
  mq.addEventListener('change', onMq)

  const onMove = (e: PointerEvent) => {
    if (e.pointerType !== 'mouse') return
    scrollStore.pointer.x = (e.clientX / window.innerWidth) * 2 - 1
    scrollStore.pointer.y = -((e.clientY / window.innerHeight) * 2 - 1)
  }
  window.addEventListener('pointermove', onMove, { passive: true })

  return () => {
    triggers.forEach((t) => t.kill())
    gsap.ticker.remove(raf)
    mq.removeEventListener('change', onMq)
    window.removeEventListener('pointermove', onMove)
    lenis?.destroy()
    lenis = null
  }
}

/**
 * Scroll to a section. Pinned sections land a little way into their pin
 * (`into` = 0..1) so the content is already on screen.
 */
export function scrollToSection(id: string, into = 0) {
  const el = document.getElementById(id)
  if (!el) return
  const y = el.getBoundingClientRect().top + window.scrollY + Math.max(el.offsetHeight - window.innerHeight, 0) * into
  if (lenis) lenis.scrollTo(y, { duration: 1.6 })
  else window.scrollTo({ top: y, behavior: 'smooth' })
}

export function setScrollLocked(locked: boolean) {
  if (lenis) locked ? lenis.stop() : lenis.start()
  document.documentElement.style.overflow = locked ? 'hidden' : ''
}
