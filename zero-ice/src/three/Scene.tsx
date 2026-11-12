import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree, type RootState } from '@react-three/fiber'
import { Environment, Lightformer, PerformanceMonitor } from '@react-three/drei'
import { Bloom, ChromaticAberration, EffectComposer, ToneMapping, Vignette } from '@react-three/postprocessing'
import { ToneMappingMode, type ChromaticAberrationEffect } from 'postprocessing'
import gsap from 'gsap'
import { colors } from '../tokens'
import { Can, GlbCan, createCanAssets } from './Can'
import { IceCubes } from './IceCubes'
import { Particles } from './Particles'
import { bedAnchor, computePose, type Pose } from './choreography'
import { BASE_DIST, FOV, live } from './rig'
import { carouselAt, clamp01, lerp, scrollStore } from './scrollStore'

type Quality = 'high' | 'low'
const TAU = Math.PI * 2
/** ?snap skips the smoothing (handy for screenshots / debugging poses) */
const SNAP = new URLSearchParams(window.location.search).has('snap')
if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__zi = { live, scrollStore }
const POSE_KEYS = Object.keys(live.pose) as (keyof Pose)[]

/** Reads the scroll store, smooths it and drives the camera + shared live state. */
function Rig({ wrap, onReady }: { wrap: React.RefObject<HTMLDivElement>; onReady: () => void }) {
  const target = useRef<Pose>({ ...live.pose })
  const first = useRef(true)
  const ptr = useRef({ x: 0, y: 0 })
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera
  const size = useThree((s) => s.size)

  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1)
    const aspect = size.width / size.height
    computePose(aspect, target.current)
    const p = live.pose
    if (first.current || SNAP) {
      Object.assign(p, target.current)
    } else {
      for (const k of POSE_KEYS) p[k] = THREE.MathUtils.damp(p[k], target.current[k], k === 'o' ? 14 : 7, d)
    }
    live.time += d
    live.viewH = 2 * Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * BASE_DIST
    live.viewW = live.viewH * aspect
    live.canScale = p.s * live.viewH
    live.canPos.set(p.x * live.viewW, (p.y + Math.sin(live.time * 0.9) * 0.006 * p.bob * Math.min(1, 0.8 / p.s)) * live.viewH, 0)

    const bed = bedAnchor(scrollStore.isMobile)
    live.bedUnit = bed.s * live.viewH
    live.bedPos.set(bed.x * live.viewW, bed.y * live.viewH, 0)

    // camera: dolly + orbit from the pose, tiny parallax from the pointer
    ptr.current.x = THREE.MathUtils.damp(ptr.current.x, scrollStore.pointer.x, 4, d)
    ptr.current.y = THREE.MathUtils.damp(ptr.current.y, scrollStore.pointer.y, 4, d)
    const dist = BASE_DIST * p.cam
    camera.position.set(Math.sin(p.orbit) * dist + ptr.current.x * 0.22, ptr.current.y * 0.14, Math.cos(p.orbit) * dist)
    camera.lookAt(0, 0, 0)

    if (wrap.current) wrap.current.style.opacity = p.o.toFixed(3)
    if (first.current) {
      first.current = false
      onReady()
    }
  }, -2)
  return null
}

/** Hero can + the two lineup variants. */
function Cans({ mobile, glbUrl }: { mobile: boolean; glbUrl: string | null }) {
  const assets = useMemo(() => createCanAssets(mobile), [mobile])
  useEffect(() => () => assets.dispose(), [assets])
  const main = useRef<THREE.Group>(null)
  const lime = useRef<THREE.Group>(null)
  const cherry = useRef<THREE.Group>(null)
  const ptr = useRef({ x: 0, y: 0 })

  useFrame((_, dt) => {
    const p = live.pose
    const w = p.carousel
    const a = carouselAt(scrollStore.sections.lineup.pin)
    const R = (mobile ? 0.62 : 0.82) * live.canScale
    ptr.current.x = THREE.MathUtils.damp(ptr.current.x, scrollStore.pointer.x, 4, dt)
    ptr.current.y = THREE.MathUtils.damp(ptr.current.y, scrollStore.pointer.y, 4, dt)
    // very subtle glow pulse on the can every 6 seconds
    const ph = (live.time % 6) / 1.5
    const glow = 1.2 + (ph < 1 ? Math.sin(ph * Math.PI) ** 2 : 0) * 0.2
    assets.bodyMats.original.envMapIntensity = assets.bodyMats.lime.envMapIntensity = assets.bodyMats.cherry.envMapIntensity = glow
    const refs = [main.current, lime.current, cherry.current]
    for (let k = 0; k < 3; k++) {
      const g = refs[k]
      if (!g) continue
      const phi = ((k - a) * TAU) / 3
      const front = (Math.cos(phi) + 1) / 2
      const isMain = k === 0
      const ww = isMain ? w : 1
      g.visible = isMain ? p.o > 0.003 : w > 0.01
      if (!g.visible) continue
      g.position.set(live.canPos.x + Math.sin(phi) * R * w, live.canPos.y, live.canPos.z + (Math.cos(phi) - 1) * R * w)
      g.scale.setScalar(Math.max(live.canScale * (isMain ? 1 : w) * lerp(1, lerp(0.74, 1, front), ww), 1e-4))
      g.rotation.set(p.rx - ptr.current.y * 0.05, p.ry + phi * ww + ptr.current.x * 0.1 + Math.sin(live.time * 0.5 + k) * 0.05 * ww, p.rz)
    }
  })

  return (
    <>
      {glbUrl ? (
        <Suspense fallback={<Can ref={main} assets={assets} variant="original" droplets={mobile ? 12 : 26} />}>
          <GlbCan ref={main} url={glbUrl} />
        </Suspense>
      ) : (
        <Can ref={main} assets={assets} variant="original" droplets={mobile ? 12 : 26} />
      )}
      <Can ref={lime} assets={assets} variant="lime" droplets={mobile ? 0 : 12} seed={19} />
      <Can ref={cherry} assets={assets} variant="cherry" droplets={mobile ? 0 : 12} seed={41} />
    </>
  )
}

/** Studio rig: blue rims left/right, soft white top strip, broad front fill, frost under-fill. */
function Studio() {
  return (
    <Environment resolution={256} frames={1} background={false}>
      <color attach="background" args={['#02080e']} />
      <Lightformer form="rect" intensity={1.5} color="#ffffff" position={[0, 0.6, 7]} scale={[9, 5, 1]} />
      <Lightformer form="rect" intensity={4} color="#ffffff" position={[0, 6, 0.5]} rotation-x={Math.PI / 2} scale={[7, 2.4, 1]} />
      <Lightformer form="rect" intensity={7} color={colors.cyan} position={[-6, 0.5, -2.5]} rotation-y={Math.PI / 2} scale={[2, 9, 1]} />
      <Lightformer form="rect" intensity={5} color={colors.silver} position={[6, 0.5, -2.5]} rotation-y={-Math.PI / 2} scale={[2, 9, 1]} />
      <Lightformer form="rect" intensity={1.2} color={colors.frost} position={[0, -5, 2]} rotation-x={-Math.PI / 2} scale={[8, 4, 1]} />
    </Environment>
  )
}

/** Bloom + vignette, chromatic aberration only while scrolling fast. */
function Effects() {
  const ca = useRef<ChromaticAberrationEffect>(null)
  const offset = useMemo(() => new THREE.Vector2(0, 0), [])
  const smooth = useRef(0)
  useFrame((_, dt) => {
    const v = clamp01((Math.abs(scrollStore.velocity) - 6) / 70)
    smooth.current = THREE.MathUtils.damp(smooth.current, v, 6, dt)
    ca.current?.offset.set(smooth.current * 0.0045, smooth.current * 0.0025)
  })
  return (
    <EffectComposer multisampling={0}>
      <Bloom mipmapBlur intensity={0.22} luminanceThreshold={1} luminanceSmoothing={0.2} radius={0.7} />
      <ChromaticAberration ref={ca as never} offset={offset} radialModulation modulationOffset={0.2} />
      <Vignette eskil={false} offset={0.2} darkness={0.75} />
      <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
    </EffectComposer>
  )
}

export default function Scene({ onReady }: { onReady: () => void }) {
  const mobile = scrollStore.isMobile
  const wrap = useRef<HTMLDivElement>(null)
  const root = useRef<RootState | null>(null)
  // ?dpr=1 pins the canvas resolution (software renderers, recordings)
  const forcedDpr = Number(new URLSearchParams(window.location.search).get('dpr')) || 0
  const maxDpr = forcedDpr || Math.min(Math.max(window.devicePixelRatio || 1, 1), 1.75)
  const [dpr, setDpr] = useState(mobile ? Math.min(maxDpr, 1.5) : maxDpr)
  const forced = new URLSearchParams(window.location.search).get('q') as Quality | null
  const [quality, setQuality] = useState<Quality>(forced ?? (mobile ? 'low' : 'high'))
  const [glbUrl, setGlbUrl] = useState<string | null>(null)

  // optional custom model
  useEffect(() => {
    let alive = true
    fetch('/models/can.glb', { method: 'HEAD' })
      .then((r) => {
        const type = r.headers.get('content-type') || ''
        if (alive && r.ok && !type.includes('text/html')) setGlbUrl('/models/can.glb')
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  // sleep the render loop while the canvas is fully hidden (FAQ + footer)
  useEffect(() => {
    let asleep = false
    const tick = () => {
      const state = root.current
      if (!state) return
      const hidden = scrollStore.sections.faq.enter >= 1 && live.pose.o < 0.004
      if (hidden !== asleep) {
        asleep = hidden
        state.setFrameloop(hidden ? 'never' : 'always')
        if (wrap.current) wrap.current.style.visibility = hidden ? 'hidden' : 'visible'
      }
    }
    gsap.ticker.add(tick)
    return () => gsap.ticker.remove(tick)
  }, [])

  return (
    <div ref={wrap} id="gl" aria-hidden="true" className="pointer-events-none fixed inset-0 z-10" style={{ opacity: 0 }}>
      <Canvas
        dpr={dpr}
        camera={{ fov: FOV, position: [0, 0, BASE_DIST], near: 0.1, far: 60 }}
        gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
        onCreated={(state) => {
          root.current = state
          state.gl.setClearColor(0x000000, 0)
        }}
      >
        <PerformanceMonitor
          bounds={() => [32, 58]}
          flipflops={2}
          onDecline={() => {
            if (!forced) setQuality('low')
            // the device is struggling: swap glass blur for solid Deep Blue
            document.documentElement.classList.add('lite-glass')
            if (!forcedDpr) setDpr(1)
          }}
          onIncline={() => setDpr(maxDpr)}
        />
        <fog attach="fog" args={[colors.midnight, 13, 30]} />
        <Studio />
        <Rig wrap={wrap} onReady={onReady} />
        <Cans mobile={mobile} glbUrl={glbUrl} />
        <IceCubes quality={quality} mobile={mobile} />
        <Particles mobile={mobile} />
        {quality === 'high' && <Effects />}
      </Canvas>
    </div>
  )
}
