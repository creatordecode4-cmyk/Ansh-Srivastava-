import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { useMotion, usePinTimeline } from '../lib/motion'
import { sectionVh } from '../tokens'
import { scrollStore } from '../three/scrollStore'
import { PinSection } from './PinSection'

export function Splash() {
  const ref = useRef<HTMLElement>(null)
  const media = useRef<HTMLDivElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const motion = useMotion()
  const [load, setLoad] = useState(false)

  // full-bleed video behind the canvas: lazy-loaded, visible + playing only while the section is on screen
  useEffect(() => {
    if (!motion) return
    let last = -1
    let playing = false
    const tick = () => {
      const s = scrollStore.sections
      if (!load && s.why.pin > 0.4) setLoad(true)
      const o = Math.min(s.splash.enter, 1 - s.taste.enter)
      if (o === last) return
      last = o
      const el = media.current
      if (!el) return
      el.style.opacity = (o * 0.6).toFixed(3)
      el.style.visibility = o > 0 ? 'visible' : 'hidden'
      const v = video.current
      if (!v) return
      if (o > 0 && !playing) {
        playing = true
        v.play().catch(() => {})
      } else if (o <= 0 && playing) {
        playing = false
        v.pause()
      }
    }
    gsap.ticker.add(tick)
    return () => gsap.ticker.remove(tick)
  }, [motion, load])

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-splash="a"]', { opacity: 0, scale: 1.6 }, { opacity: 1, scale: 1, duration: 0.16, ease: 'power2.out' }, 0.05)
      .to('[data-splash="a"]', { opacity: 0, scale: 0.9, duration: 0.08 }, 0.4)
      .fromTo('[data-splash="b"]', { opacity: 0, scale: 1.6 }, { opacity: 1, scale: 1, duration: 0.16, ease: 'power2.out' }, 0.56)
  })

  const giant = 'display text-[clamp(3.4rem,13.5vw,13rem)] drop-shadow-[0_6px_30px_rgba(0,0,0,0.9)]'

  return (
    <PinSection
      id="splash"
      vh={sectionVh.splash}
      ref={ref}
      behind={
        motion ? (
          <div ref={media} className="pointer-events-none fixed inset-0 z-[5]" style={{ opacity: 0, visibility: 'hidden' }} aria-hidden="true">
            <video ref={video} className="h-full w-full scale-110 object-cover blur-[3px]" src={load ? '/videos/splash.mp4' : undefined} poster="/images/splash-poster.jpg" muted loop playsInline preload="none" />
            <div className="absolute inset-0 bg-gradient-to-b from-ink via-transparent to-ink" />
          </div>
        ) : undefined
      }
    >
      {!motion && (
        <>
          <img src="/images/splash-poster.jpg" alt="ZERO ICE can surrounded by a cola splash and flying ice cubes" loading="lazy" className="absolute inset-0 h-full w-full object-cover opacity-70" />
          <div className="absolute inset-0 bg-gradient-to-b from-ink via-transparent to-ink" aria-hidden="true" />
        </>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-ink via-ink/70 to-transparent" aria-hidden="true" />
      <div className={`absolute inset-x-0 bottom-[8svh] px-4 text-center ${motion ? 'grid place-items-center' : 'flex flex-col gap-3'}`}>
        <h2 id="splash-title" data-splash="a" className={`${giant} ${motion ? 'col-start-1 row-start-1' : ''}`}>
          Crack It Open.
        </h2>
        <p data-splash="b" className={`${giant} !text-ice ${motion ? 'col-start-1 row-start-1' : ''}`}>
          Feel The Chill.
        </p>
      </div>
    </PinSection>
  )
}
