import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, Lightformer, PerformanceMonitor } from '@react-three/drei'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { colors } from '../tokens'
import { detectMotion } from '../lib/motion'
import { Logo } from '../components/Logo'
import { D, HINGE_Y, HINGE_Z, Laptop } from './Laptop'
import { LID_OPEN, stage } from './stage'

gsap.registerPlugin(ScrollTrigger)

const FOV = 32
const DEG = Math.PI / 180
/** ?snap skips the smoothing (stills / debugging) */
const SNAP = new URLSearchParams(window.location.search).has('snap')

// where the screen ends up once the lid is fully open
const SCREEN_CENTER = new THREE.Vector3(0, HINGE_Y + (D / 2) * Math.sin(LID_OPEN), HINGE_Z + (D / 2) * Math.cos(LID_OPEN))
const SCREEN_TILT = LID_OPEN - Math.PI / 2

interface Shot {
  at: number
  /** orbit angle around the target, degrees (0 = straight on) */
  az: number
  /** elevation, degrees */
  el: number
  dist: number
  target: [number, number, number]
}

/** Camera path: closed beauty shot -> orbit while the lid opens -> push in to the screen -> pull back. */
const SHOTS: Shot[] = [
  { at: 0, az: -34, el: 36, dist: 7.6, target: [0, -0.55, 0] },
  { at: 0.16, az: -22, el: 30, dist: 7.8, target: [0, -0.3, -0.1] },
  { at: 0.5, az: 30, el: 17, dist: 8.2, target: [0, 0.3, -0.35] },
  { at: 0.7, az: 0, el: SCREEN_TILT / DEG, dist: 5.0, target: [SCREEN_CENTER.x, SCREEN_CENTER.y - 0.42, SCREEN_CENTER.z] },
  { at: 0.82, az: 0, el: SCREEN_TILT / DEG, dist: 4.55, target: [SCREEN_CENTER.x, SCREEN_CENTER.y - 0.36, SCREEN_CENTER.z] },
  { at: 1, az: -26, el: 13, dist: 7.8, target: [0, 0.15, -0.3] },
]

const ease = (t: number) => t * t * (3 - 2 * t)
const mix = (a: number, b: number, t: number) => a + (b - a) * t

function Rig({ onReady }: { onReady: () => void }) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera
  const size = useThree((s) => s.size)
  const first = useRef(true)
  const look = useRef(new THREE.Vector3())

  useFrame((state, dt) => {
    const d = Math.min(dt, 0.1)
    stage.p = first.current || SNAP ? stage.target : THREE.MathUtils.damp(stage.p, stage.target, 4.5, d)
    const p = stage.p
    stage.lid = ease(THREE.MathUtils.clamp((p - 0.07) / 0.41, 0, 1)) * LID_OPEN

    let i = 0
    while (i < SHOTS.length - 2 && p > SHOTS[i + 1].at) i++
    const a = SHOTS[i]
    const b = SHOTS[i + 1]
    const t = ease(THREE.MathUtils.clamp((p - a.at) / (b.at - a.at), 0, 1))
    // narrow screens need more distance to keep the whole laptop in frame
    const fit = Math.max(1, 1.5 / (size.width / size.height))
    const drift = Math.sin(state.clock.elapsedTime * 0.35) * 1.4
    const az = (mix(a.az, b.az, t) + drift) * DEG
    const el = mix(a.el, b.el, t) * DEG
    const dist = mix(a.dist, b.dist, t) * fit
    look.current.set(mix(a.target[0], b.target[0], t), mix(a.target[1], b.target[1], t), mix(a.target[2], b.target[2], t))
    camera.position.set(look.current.x + Math.sin(az) * Math.cos(el) * dist, look.current.y + Math.sin(el) * dist, look.current.z + Math.cos(az) * Math.cos(el) * dist)
    camera.lookAt(look.current)

    if (first.current) {
      first.current = false
      onReady()
    }
  }, -1)
  return null
}

/** Cyan rims left/right/back, soft white strip on top, low front fill. */
function Studio() {
  return (
    <>
      <Environment resolution={256} frames={1} background={false}>
        <color attach="background" args={['#02070c']} />
        <Lightformer form="rect" intensity={3.2} color="#ffffff" position={[0, 6, 1]} rotation-x={Math.PI / 2} scale={[8, 3.5, 1]} />
        <Lightformer form="rect" intensity={0.7} color="#ffffff" position={[0, 1.5, 8]} scale={[10, 4, 1]} />
        <Lightformer form="rect" intensity={9} color={colors.cyan} position={[-7, 1, -1]} rotation-y={Math.PI / 2} scale={[1.6, 8, 1]} />
        <Lightformer form="rect" intensity={9} color={colors.cyan} position={[7, 1, -1]} rotation-y={-Math.PI / 2} scale={[1.6, 8, 1]} />
        <Lightformer form="rect" intensity={5} color={colors.cyan} position={[0, 1.2, -8]} rotation-y={Math.PI} scale={[9, 1.6, 1]} />
        <Lightformer form="rect" intensity={0.8} color={colors.frost} position={[0, -5, 2]} rotation-x={-Math.PI / 2} scale={[8, 4, 1]} />
      </Environment>
      <directionalLight position={[1.5, 6, 2.5]} intensity={1.1} color="#ffffff" />
      <pointLight position={[-4.5, 1.2, -3]} intensity={26} color={colors.cyan} distance={12} decay={2} />
      <pointLight position={[4.5, 1.2, -3]} intensity={26} color={colors.cyan} distance={12} decay={2} />
    </>
  )
}

const BEATS: { from: number; to: number; eyebrow: string; title: string; body: string }[] = [
  { from: -1, to: 0.1, eyebrow: 'Concept device', title: 'ZERO BOOK', body: 'Scroll to open.' },
  { from: 0.2, to: 0.46, eyebrow: 'Brushed aluminum', title: 'Cold to the touch.', body: 'One slab of brushed metal with an Ice Cyan edge.' },
  { from: 0.62, to: 0.86, eyebrow: 'On screen', title: 'ZERO ICE, full bleed.', body: 'The site, running edge to edge.' },
  { from: 0.94, to: 2, eyebrow: 'ZERO BOOK', title: 'Zero sugar. Zero guilt. Zero lag.', body: 'A fictional laptop for a fictional cola.' },
]

/** Static version for reduced motion / no WebGL. */
function Fallback() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-5 py-24 text-center">
      <p className="eyebrow mb-4">Concept device</p>
      <h1 className="display text-6xl md:text-8xl">ZERO BOOK</h1>
      <div className="mt-10 w-full max-w-3xl rounded-[18px] border border-frost/20 bg-[#04080c] p-3 shadow-[0_0_80px_rgba(0,213,231,0.18)]">
        <img src="/images/hero-last.jpg" alt="The ZERO ICE site shown on the ZERO BOOK screen" className="block w-full rounded-[10px]" />
      </div>
      <p className="mt-8 max-w-xl text-silver/70">A fictional laptop for a fictional cola.</p>
    </div>
  )
}

export default function Showcase() {
  const [motion] = useState(detectMotion)
  const [fonts, setFonts] = useState(false)
  const [ready, setReady] = useState(false)
  const track = useRef<HTMLDivElement>(null)
  const beats = useRef<(HTMLDivElement | null)[]>([])
  const bar = useRef<HTMLDivElement>(null)
  // ?dpr=1 pins the canvas resolution (software renderers, recordings)
  const forcedDpr = Number(new URLSearchParams(window.location.search).get('dpr')) || 0
  const maxDpr = forcedDpr || Math.min(Math.max(window.devicePixelRatio || 1, 1), 2)
  const [dpr, setDpr] = useState(maxDpr)

  useEffect(() => {
    document.title = 'ZERO BOOK — ZERO ICE showcase'
  }, [])

  // the lid wordmark and the screen are drawn to canvases with the brand fonts
  useEffect(() => {
    let alive = true
    const done = () => alive && setFonts(true)
    Promise.all(['italic 900 100px "Barlow Condensed"', '500 18px "Inter Variable"', '600 18px "Inter Variable"'].map((f) => document.fonts.load(f))).then(done, done)
    const t = window.setTimeout(done, 4000)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [])

  useEffect(() => {
    if (!motion || !track.current) return
    const st = ScrollTrigger.create({
      trigger: track.current,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (s) => (stage.target = s.progress),
      onRefresh: (s) => (stage.target = s.progress),
    })
    // captions + progress follow the smoothed value, so they stay in step with the camera
    const tick = () => {
      const p = stage.p
      BEATS.forEach((b, i) => {
        const el = beats.current[i]
        if (!el) return
        const o = Math.min(THREE.MathUtils.smoothstep(p, b.from - 0.04, b.from + 0.02), 1 - THREE.MathUtils.smoothstep(p, b.to - 0.02, b.to + 0.04))
        el.style.opacity = o.toFixed(3)
        el.style.transform = `translate3d(0, ${((1 - o) * 14).toFixed(1)}px, 0)`
      })
      if (bar.current) bar.current.style.transform = `scaleX(${p.toFixed(4)})`
    }
    gsap.ticker.add(tick)
    return () => {
      st.kill()
      gsap.ticker.remove(tick)
    }
  }, [motion])

  const disclaimer = <p className="text-xs text-silver/60 md:text-sm">ZERO BOOK and ZERO ICE are fictional brands created for a demo. Not a real product.</p>

  const header = (
    <header className="fixed inset-x-0 top-0 z-30 flex items-center justify-between px-5 py-5 md:px-10">
      <a href="/" aria-label="Back to the ZERO ICE site">
        <Logo className="h-8 w-auto" />
      </a>
      <a href="/" className="btn-ghost !min-h-[40px] !px-5 !text-sm">
        Back to site
      </a>
    </header>
  )

  if (!motion) {
    return (
      <main>
        {header}
        <Fallback />
        <footer className="px-5 pb-8 text-center">{disclaimer}</footer>
      </main>
    )
  }

  return (
    <main>
      {header}
      <div className="fixed left-0 top-0 z-40 h-[2px] w-full origin-left bg-cyan" ref={bar} style={{ transform: 'scaleX(0)' }} aria-hidden="true" />
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true" style={{ background: `radial-gradient(90% 70% at 50% 62%, #0d2233 0%, ${colors.midnight} 62%)` }} />
      <div className="fixed inset-0 z-10 transition-opacity duration-700" style={{ opacity: ready ? 1 : 0 }} aria-hidden="true">
        {fonts && (
          <Canvas dpr={dpr} camera={{ fov: FOV, position: [0, 3, 7], near: 0.4, far: 60 }} gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }} onCreated={(s) => s.gl.setClearColor(0x000000, 0)}>
            <PerformanceMonitor bounds={() => [40, 58]} flipflops={2} onDecline={() => !forcedDpr && setDpr(1)} onIncline={() => setDpr(maxDpr)} />
            <Studio />
            <Rig onReady={() => setReady(true)} />
            <Laptop />
          </Canvas>
        )}
      </div>

      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[15] h-[34svh]" aria-hidden="true" style={{ background: `linear-gradient(180deg, rgba(7,21,34,0) 0%, ${colors.midnight} 78%)` }} />
      {/* captions */}
      <div className="pointer-events-none fixed inset-x-0 bottom-[7svh] z-20 px-5 text-center">
        <div className="relative mx-auto h-40 max-w-3xl">
          {BEATS.map((b, i) => (
            <div key={b.title} ref={(el) => (beats.current[i] = el)} className="absolute inset-x-0 bottom-0" style={{ opacity: i === 0 ? 1 : 0 }}>
              <p className="eyebrow mb-3">{b.eyebrow}</p>
              {i === 0 ? <h1 className="display text-6xl md:text-8xl">{b.title}</h1> : <h2 className="heading text-3xl md:text-5xl">{b.title}</h2>}
              <p className="mt-3 text-base text-silver/75 md:text-lg">{b.body}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 px-5 pb-4 text-center">{disclaimer}</div>

      {/* scroll track: the page is just a long runway for the camera */}
      <div ref={track} className="relative" style={{ height: '520svh' }} />
    </main>
  )
}
