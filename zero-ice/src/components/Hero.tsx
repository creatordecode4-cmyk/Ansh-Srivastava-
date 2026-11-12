import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { BLUR_IN, BLUR_OFF, PopButton, useMotion } from '../lib/motion'
import { scrollToSection } from '../lib/scroll'
import { sectionVh } from '../tokens'
import { heroMatch } from '../three/choreography'
import { scrollStore, ss } from '../three/scrollStore'
import { PinSection } from './PinSection'

const HEADLINE = ['ZERO SUGAR.', 'ZERO GUILT.', 'ALL ICE.']
const STATS = [
  { value: '0', label: 'Sugar' },
  { value: '0', label: 'Calories' },
  { value: '100%', label: 'Bold Taste' },
]
/** same box the 3D match uses: see heroBox in three/choreography.ts */
const MEDIA_BOX = 'left-0 top-0 h-[58svh] w-full md:left-[-20%] md:h-full md:w-[120%]'

export function Hero({ ready, onPoster }: { ready: boolean; onPoster: () => void }) {
  const motion = useMotion()
  const media = useRef<HTMLDivElement>(null)
  const zoomEl = useRef<HTMLDivElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const text = useRef<HTMLDivElement>(null)
  const zoom = useRef<gsap.core.Tween | null>(null)
  const [ended, setEnded] = useState(false)
  const [atTop, setAtTop] = useState(true)

  // poster painted → the app may start loading 3D
  useEffect(() => {
    const img = new Image()
    img.onload = img.onerror = () => onPoster()
    img.src = motion ? '/images/hero-first.jpg' : '/images/hero-last.jpg'
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // keep the zoom origin on the can so the 3D match only has to scale
  useEffect(() => {
    if (!motion) return
    const place = () => {
      const m = heroMatch(window.innerWidth / window.innerHeight, scrollStore.isMobile)
      if (zoomEl.current) zoomEl.current.style.transformOrigin = `${m.originX}% ${m.originY}%`
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [motion])

  // scroll handoff: the video blurs + fades while the 3D can fades in on top of it
  useEffect(() => {
    if (!motion) return
    let last = -1
    const tick = () => {
      const p = scrollStore.sections.hero.pin
      if (p === last) return
      last = p
      const el = media.current
      if (!el) return
      const fade = 1 - ss(0.1, 0.42, p)
      el.style.opacity = fade.toFixed(3)
      el.style.filter = p > 0.02 ? `blur(${(ss(0.02, 0.4, p) * 18).toFixed(1)}px)` : 'none'
      el.style.visibility = fade <= 0 ? 'hidden' : 'visible'
      setAtTop(p < 0.04)
    }
    gsap.ticker.add(tick)
    return () => gsap.ticker.remove(tick)
  }, [motion])

  // play once, then freeze on the last frame with a slow zoom
  const startZoom = () => {
    const state = { z: scrollStore.heroZoom }
    zoom.current?.kill()
    zoom.current = gsap.to(state, {
      z: 1.06,
      duration: 18,
      ease: 'sine.out',
      onUpdate: () => {
        scrollStore.heroZoom = state.z
        if (zoomEl.current) zoomEl.current.style.transform = `scale(${state.z.toFixed(4)})`
      },
    })
  }
  const replay = () => {
    const v = video.current
    if (!v) return
    zoom.current?.kill()
    scrollStore.heroZoom = 1
    if (zoomEl.current) zoomEl.current.style.transform = 'scale(1)'
    setEnded(false)
    v.currentTime = 0
    v.play().catch(() => setEnded(true))
  }
  useEffect(() => {
    if (!motion || !ready) return
    const v = video.current
    v?.play().catch(() => {
      // autoplay blocked: show the last frame instead
      setEnded(true)
    })
    return () => {
      zoom.current?.kill()
    }
  }, [motion, ready])

  // headline: word-by-word reveal once the loader is gone
  useLayoutEffect(() => {
    if (!motion || !text.current) return
    const ctx = gsap.context(() => {
      gsap.set('[data-word]', { yPercent: 115 })
      gsap.set('[data-fade]', { opacity: 0, y: 24, filter: BLUR_IN })
      if (ready) {
        gsap.to('[data-word]', { yPercent: 0, duration: 0.9, ease: 'power4.out', stagger: 0.08, delay: 0.25 })
        gsap.to('[data-fade]', { opacity: 1, y: 0, filter: BLUR_OFF, duration: 0.9, ease: 'expo.out', stagger: 0.1, delay: 0.85, clearProps: 'filter' })
      }
    }, text)
    return () => ctx.revert()
  }, [motion, ready])

  const mediaLayer = (
    <div ref={media} className={`${motion ? 'fixed z-[5]' : 'absolute z-0'} ${MEDIA_BOX} overflow-hidden`}>
      <div ref={zoomEl} className="h-full w-full will-change-transform">
        {motion ? (
          <video
            ref={video}
            className="h-full w-full object-cover"
            src="/videos/hero.mp4"
            poster="/images/hero-first.jpg"
            muted
            playsInline
            preload="auto"
            aria-label="A silver ZERO ICE can hit by a cola splash and flying ice, settling into cold blue mist"
            onEnded={() => {
              setEnded(true)
              startZoom()
            }}
          />
        ) : (
          <img src="/images/hero-last.jpg" alt="Silver ZERO ICE diet cola can covered in condensation, standing in crushed ice and blue mist" className="h-full w-full object-cover" />
        )}
      </div>
      {/* scrims: keep the headline readable and melt the video into the page */}
      <div className="absolute inset-0 bg-gradient-to-b from-midnight/50 via-transparent to-transparent" aria-hidden="true" />
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-midnight to-transparent md:h-1/4" aria-hidden="true" />
      <div className="absolute inset-0 hidden bg-gradient-to-r from-transparent from-[52%] to-midnight/80 md:block" aria-hidden="true" />
    </div>
  )

  return (
    <PinSection id="hero" vh={sectionVh.hero} behind={motion ? mediaLayer : undefined}>
      {!motion && mediaLayer}
      <div
        ref={text}
        className="absolute inset-x-0 bottom-0 flex h-[42svh] flex-col items-center justify-center px-5 pb-3 text-center md:inset-x-auto md:bottom-auto md:right-[4%] md:top-1/2 md:h-auto md:w-[34%] md:-translate-y-1/2 md:items-start md:px-0 md:pb-0 md:text-left"
      >
        <p className="eyebrow mb-3 hidden md:block" data-fade>
          Diet Cola · Served Ice Cold
        </p>
        <h1 id="hero-title" className="display text-[13.5vw] md:text-[clamp(3.5rem,5.9vw,7rem)]" aria-label={HEADLINE.join(' ')}>
          {HEADLINE.map((line, i) => (
            <span key={line} className="block overflow-hidden pb-[0.06em] pr-[0.12em] md:-mr-[0.12em]" aria-hidden="true">
              {line.split(' ').map((w, j) => (
                <span key={j} data-word className={`inline-block pr-[0.2em] ${i === 2 ? 'text-cyan' : ''}`}>
                  {w}
                </span>
              ))}
            </span>
          ))}
        </h1>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-3 md:mt-7 md:justify-start" data-fade>
          <PopButton href="#cta" reveal={false} onClick={(e) => (e.preventDefault(), scrollToSection('cta', 0.9))}>
            Buy Now
          </PopButton>
          <PopButton href="#splash" variant="ghost" reveal={false} onClick={(e) => (e.preventDefault(), scrollToSection('splash', 0.3))}>
            <svg width="12" height="14" viewBox="0 0 12 14" aria-hidden="true">
              <path d="M0 0 L12 7 L0 14Z" fill="currentColor" />
            </svg>
            Watch the Drop
          </PopButton>
        </div>
        <dl className="mt-4 flex w-full max-w-md items-stretch justify-center divide-x divide-frost/15 md:mt-9 md:justify-start" data-fade>
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col-reverse px-5 first:pl-0 last:pr-0 md:px-7">
              <dt className="mt-1 font-display text-xs font-bold uppercase tracking-[0.22em] text-frost md:text-sm">{s.label}</dt>
              <dd className="display text-3xl md:text-5xl">{s.value}</dd>
            </div>
          ))}
        </dl>
      </div>
      {motion && (
        <button
          type="button"
          onClick={replay}
          className={`absolute left-4 top-[calc(58svh-3.25rem)] flex min-h-[44px] items-center gap-2 rounded-full border border-frost/25 bg-midnight/60 px-4 font-display text-sm font-bold uppercase tracking-widest text-silver backdrop-blur transition-opacity duration-500 hover:border-cyan hover:text-cyan md:bottom-8 md:left-10 md:top-auto ${
            ended && atTop ? 'opacity-100' : 'pointer-events-none opacity-0'
          }`}
          tabIndex={ended && atTop ? 0 : -1}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 3-6.7" />
            <path d="M3 4v5h5" />
          </svg>
          Replay intro
        </button>
      )}
    </PinSection>
  )
}
