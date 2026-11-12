import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { colors, fonts } from '../tokens'
import { seeded } from '../three/rig'
import { stage } from './stage'

/** ZERO BOOK: a fictional laptop, fully procedural. Units are roughly 10 cm. */
export const W = 3.2
export const D = 2.2
export const BASE_H = 0.1
export const LID_T = 0.05
/** deck surface */
export const TOP = BASE_H / 2
/** hinge line: the lid rests a hair above the key caps */
export const HINGE_Y = TOP + 0.022
export const HINGE_Z = -D / 2
export const SCREEN_W = 2.98
export const SCREEN_H = 1.92
/** floor level (under the rubber feet) */
export const FLOOR_Y = -BASE_H / 2 - 0.012

const KEY = 0.158
const PITCH = 0.19

/** fine horizontal streaks: drives roughness + a faint bump for the brushed look */
function makeBrushed() {
  const c = document.createElement('canvas')
  c.width = c.height = 512
  const g = c.getContext('2d')!
  g.fillStyle = 'rgb(205,205,205)'
  g.fillRect(0, 0, 512, 512)
  const rnd = seeded(7)
  for (let i = 0; i < 2600; i++) {
    const v = 120 + Math.floor(rnd() * 135)
    g.strokeStyle = `rgba(${v},${v},${v},${0.1 + rnd() * 0.3})`
    g.lineWidth = 0.5 + rnd()
    const y = rnd() * 512
    const x = rnd() * 512
    g.beginPath()
    g.moveTo(x, y)
    g.lineTo(x + 80 + rnd() * 420, y)
    g.stroke()
  }
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.repeat.set(2, 2)
  t.anisotropy = 8
  return t
}

function makeRadial(inner: string, outer: string) {
  const c = document.createElement('canvas')
  c.width = c.height = 256
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128)
  grad.addColorStop(0, inner)
  grad.addColorStop(1, outer)
  g.fillStyle = grad
  g.fillRect(0, 0, 256, 256)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

/** etched wordmark for the lid (fictional brand, type only) */
function makeWordmark() {
  const c = document.createElement('canvas')
  c.width = 1024
  c.height = 192
  const g = c.getContext('2d')!
  g.font = `italic 900 150px ${fonts.display}`
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillStyle = 'rgba(244,249,252,0.9)'
  try {
    ;(g as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = '14px'
  } catch {
    /* older browsers: default spacing */
  }
  g.fillText('ZERO BOOK', 512, 104)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 8
  return t
}

/** The ZERO ICE site as it looks on screen: hero frame + a light nav bar. */
function drawScreen(c: HTMLCanvasElement, img: HTMLImageElement | null) {
  const g = c.getContext('2d')!
  const w = c.width
  const h = c.height
  g.fillStyle = colors.midnight
  g.fillRect(0, 0, w, h)
  if (img) {
    const s = Math.max(w / img.width, h / img.height)
    g.drawImage(img, (w - img.width * s) / 2, (h - img.height * s) / 2, img.width * s, img.height * s)
  }
  const top = g.createLinearGradient(0, 0, 0, h * 0.2)
  top.addColorStop(0, 'rgba(7,21,34,0.85)')
  top.addColorStop(1, 'rgba(7,21,34,0)')
  g.fillStyle = top
  g.fillRect(0, 0, w, h * 0.2)

  const u = w / 1440
  g.textBaseline = 'middle'
  g.textAlign = 'left'
  g.fillStyle = colors.silver
  g.font = `italic 900 ${40 * u}px ${fonts.display}`
  g.fillText('ZERO ICE', 44 * u, 50 * u)
  g.font = `500 ${18 * u}px ${fonts.body}`
  g.fillStyle = 'rgba(244,249,252,0.85)'
  g.textAlign = 'center'
  ;['Story', 'Why Zero', 'Taste', 'Lineup', 'Nutrition'].forEach((label, i) => g.fillText(label, w / 2 + (i - 2) * 124 * u, 50 * u))
  // primary CTA pill
  const bw = 124 * u
  const bh = 42 * u
  const bx = w - 44 * u - bw
  const by = 50 * u - bh / 2
  g.fillStyle = colors.cyan
  g.beginPath()
  g.roundRect(bx, by, bw, bh, bh / 2)
  g.fill()
  g.fillStyle = colors.midnight
  g.font = `600 ${17 * u}px ${fonts.body}`
  g.fillText('Buy Now', bx + bw / 2, 51 * u)
  // disclaimer stays visible on screen
  g.textAlign = 'right'
  g.fillStyle = 'rgba(244,249,252,0.7)'
  g.font = `500 ${15 * u}px ${fonts.body}`
  g.fillText('Fictional brand · demo', w - 44 * u, h - 34 * u)
}

interface KeyCap {
  x: number
  z: number
  sx: number
  sz: number
}

function keyLayout(): KeyCap[] {
  const keys: KeyCap[] = []
  const cols = 14
  const x0 = -((cols - 1) * PITCH) / 2
  const zTop = -0.86
  // slim function row
  for (let i = 0; i < cols; i++) keys.push({ x: x0 + i * PITCH, z: zTop, sx: 1, sz: 0.55 })
  for (let r = 0; r < 4; r++) for (let i = 0; i < cols; i++) keys.push({ x: x0 + i * PITCH, z: zTop + 0.15 + r * PITCH, sx: 1, sz: 1 })
  // bottom row with a wide space bar
  const zb = zTop + 0.15 + 4 * PITCH
  for (let i = 0; i < 3; i++) keys.push({ x: x0 + i * PITCH, z: zb, sx: 1, sz: 1 })
  keys.push({ x: x0 + 5.5 * PITCH, z: zb, sx: (5 * PITCH + KEY) / KEY, sz: 1 })
  for (let i = 9; i < cols; i++) keys.push({ x: x0 + i * PITCH, z: zb, sx: 1, sz: 1 })
  return keys
}

export function Laptop() {
  const lid = useRef<THREE.Group>(null)
  const keysRef = useRef<THREE.InstancedMesh>(null)
  const glowLight = useRef<THREE.PointLight>(null)

  const a = useMemo(() => {
    const brushed = makeBrushed()
    const aluminum = new THREE.MeshPhysicalMaterial({
      color: '#c3ccd4',
      metalness: 1,
      roughness: 0.36,
      roughnessMap: brushed,
      bumpMap: brushed,
      bumpScale: 0.35,
      clearcoat: 0.15,
      clearcoatRoughness: 0.4,
      envMapIntensity: 1.25,
    })
    const dark = new THREE.MeshStandardMaterial({ color: '#0a1016', metalness: 0.4, roughness: 0.55 })
    const keyMat = new THREE.MeshStandardMaterial({ color: '#111a23', metalness: 0.2, roughness: 0.5 })
    const pad = new THREE.MeshPhysicalMaterial({ color: '#aab4bd', metalness: 1, roughness: 0.2, envMapIntensity: 1.1 })
    const rim = new THREE.MeshBasicMaterial({ color: new THREE.Color(colors.cyan).multiplyScalar(1.6), toneMapped: false })
    // clear ice without a transmission pass: thin transparent shell + frosted core
    const ice = new THREE.MeshPhysicalMaterial({ color: '#d9f6ff', transparent: true, opacity: 0.38, roughness: 0.04, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 2.4, depthWrite: false })
    const iceCore = new THREE.MeshStandardMaterial({ color: colors.frost, transparent: true, opacity: 0.3, roughness: 0.6, emissive: new THREE.Color(colors.cyan), emissiveIntensity: 0.12, depthWrite: false })

    const screenCanvas = document.createElement('canvas')
    screenCanvas.width = 1600
    screenCanvas.height = Math.round((1600 * SCREEN_H) / SCREEN_W)
    drawScreen(screenCanvas, null)
    const screenTex = new THREE.CanvasTexture(screenCanvas)
    screenTex.colorSpace = THREE.SRGBColorSpace
    screenTex.anisotropy = 8
    const screen = new THREE.MeshBasicMaterial({ map: screenTex, toneMapped: false, color: 0x000000 })
    const haloTex = makeRadial('rgba(0,213,231,0.55)', 'rgba(0,213,231,0)')
    const halo = new THREE.MeshBasicMaterial({ map: haloTex, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false })
    const wordTex = makeWordmark()
    const word = new THREE.MeshStandardMaterial({ map: wordTex, transparent: true, opacity: 0.5, metalness: 0.9, roughness: 0.2, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 })
    const floorTex = makeRadial('rgba(0,213,231,0.42)', 'rgba(0,213,231,0)')
    const floorGlow = new THREE.MeshBasicMaterial({ map: floorTex, transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false })
    const shadowTex = makeRadial('rgba(0,0,0,0.85)', 'rgba(0,0,0,0)')
    const shadow = new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, toneMapped: false })

    const baseGeo = new RoundedBoxGeometry(W, BASE_H, D, 5, 0.045)
    const lidGeo = new RoundedBoxGeometry(W, LID_T, D, 5, 0.024)
    const keyGeo = new RoundedBoxGeometry(KEY, 0.022, KEY, 2, 0.008)
    const cubeGeo = new RoundedBoxGeometry(0.24, 0.24, 0.24, 4, 0.035)
    const disposables = [brushed, aluminum, dark, keyMat, pad, rim, ice, iceCore, screenTex, screen, haloTex, halo, wordTex, word, floorTex, floorGlow, shadowTex, shadow, baseGeo, lidGeo, keyGeo, cubeGeo]
    return { aluminum, dark, keyMat, pad, rim, ice, iceCore, screenCanvas, screenTex, screen, halo, word, floorGlow, shadow, baseGeo, lidGeo, keyGeo, cubeGeo, dispose: () => disposables.forEach((d) => d.dispose()) }
  }, [])

  useEffect(() => () => a.dispose(), [a])

  // hero frame -> screen texture
  useEffect(() => {
    const img = new Image()
    img.onload = () => {
      drawScreen(a.screenCanvas, img)
      a.screenTex.needsUpdate = true
    }
    img.src = '/images/hero-last.jpg'
    return () => {
      img.onload = null
    }
  }, [a])

  const keys = useMemo(keyLayout, [])
  useLayoutEffect(() => {
    const mesh = keysRef.current
    if (!mesh) return
    const o = new THREE.Object3D()
    keys.forEach((k, i) => {
      o.position.set(k.x, TOP + 0.008, k.z)
      o.scale.set(k.sx, 1, k.sz)
      o.updateMatrix()
      mesh.setMatrixAt(i, o.matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [keys])

  useFrame(() => {
    if (lid.current) lid.current.rotation.x = -stage.lid
    // the display wakes up as the lid lifts
    const on = THREE.MathUtils.smoothstep(stage.lid, 0.3, 1.25)
    a.screen.color.setScalar(on)
    a.halo.opacity = on * 0.22
    if (glowLight.current) glowLight.current.intensity = on * 2.2
  })

  return (
    <group>
      {/* base */}
      <mesh geometry={a.baseGeo} material={a.aluminum} />
      {/* keyboard well */}
      <mesh position={[0, TOP + 0.001, -0.39]} rotation-x={-Math.PI / 2} material={a.dark}>
        <planeGeometry args={[2.78, 1.2]} />
      </mesh>
      <instancedMesh ref={keysRef} args={[a.keyGeo, a.keyMat, keys.length]} />
      {/* trackpad: flat inset with a dark seam */}
      <mesh position={[0, TOP + 0.001, 0.68]} rotation-x={-Math.PI / 2} material={a.dark}>
        <planeGeometry args={[1.16, 0.66]} />
      </mesh>
      <mesh position={[0, TOP + 0.002, 0.68]} rotation-x={-Math.PI / 2} material={a.pad}>
        <planeGeometry args={[1.14, 0.64]} />
      </mesh>
      {/* Ice Cyan rim strips: front lip and both sides */}
      <mesh position={[0, 0, D / 2 + 0.001]} material={a.rim}>
        <boxGeometry args={[1.5, 0.008, 0.004]} />
      </mesh>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * (W / 2 + 0.001), 0, 0]} material={a.rim}>
          <boxGeometry args={[0.004, 0.006, 1.3]} />
        </mesh>
      ))}
      {/* hinge bar + rubber feet */}
      <mesh position={[0, HINGE_Y - 0.005, HINGE_Z + 0.01]} rotation-z={Math.PI / 2} material={a.dark}>
        <cylinderGeometry args={[0.034, 0.034, 2.5, 20]} />
      </mesh>
      {[-1, 1].map((x) =>
        [-1, 1].map((z) => (
          <mesh key={`${x}${z}`} position={[x * 1.3, -BASE_H / 2 - 0.004, z * 0.85]} material={a.dark}>
            <cylinderGeometry args={[0.06, 0.06, 0.016, 16]} />
          </mesh>
        )),
      )}

      {/* lid: pivots on the hinge line, closed = flat over the deck */}
      <group ref={lid} position={[0, HINGE_Y, HINGE_Z]}>
        <mesh geometry={a.lidGeo} material={a.aluminum} position={[0, LID_T / 2, D / 2]} />
        <mesh position={[0, LID_T + 0.001, D / 2]} rotation-x={-Math.PI / 2} material={a.word}>
          <planeGeometry args={[1.05, 0.197]} />
        </mesh>
        <mesh position={[0, -0.001, D / 2]} rotation-x={Math.PI / 2}>
          <planeGeometry args={[W - 0.06, D - 0.06]} />
          <meshStandardMaterial color="#04080c" metalness={0.2} roughness={0.35} />
        </mesh>
        <mesh position={[0, -0.002, D / 2 + 0.01]} rotation-x={Math.PI / 2} material={a.screen}>
          <planeGeometry args={[SCREEN_W, SCREEN_H]} />
        </mesh>
        <mesh position={[0, -0.004, D / 2]} rotation-x={Math.PI / 2} material={a.halo} renderOrder={2}>
          <planeGeometry args={[W * 1.5, D * 1.6]} />
        </mesh>
        <pointLight ref={glowLight} position={[0, -0.7, D / 2]} color={colors.frost} intensity={0} distance={5} decay={2} />
      </group>

      {/* one tiny ice cube resting beside the laptop */}
      <group position={[W / 2 + 0.34, FLOOR_Y + 0.115, 0.62]} rotation={[0, 0.5, 0]} scale={[1, 0.94, 1.08]}>
        <mesh geometry={a.cubeGeo} material={a.iceCore} scale={0.62} rotation={[0.3, 0.4, 0.2]} renderOrder={3} />
        <mesh geometry={a.cubeGeo} material={a.ice} renderOrder={4} />
      </group>

      {/* ground: soft contact shadow + cyan pool of light */}
      <mesh position={[0, FLOOR_Y, 0]} rotation-x={-Math.PI / 2} material={a.floorGlow} renderOrder={-2}>
        <planeGeometry args={[11, 9]} />
      </mesh>
      <mesh position={[0, FLOOR_Y + 0.002, 0]} rotation-x={-Math.PI / 2} material={a.shadow} renderOrder={-1}>
        <planeGeometry args={[W * 1.5, D * 1.6]} />
      </mesh>
    </group>
  )
}
