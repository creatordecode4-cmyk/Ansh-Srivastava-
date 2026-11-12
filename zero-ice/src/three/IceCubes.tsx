import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { MeshTransmissionMaterial } from '@react-three/drei'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { live, seeded } from './rig'
import { makeFrostNormal } from './textures'

interface Seed {
  ang: number
  h: number
  r: number
  size: number
  spd: number
  k: number
  phase: number
  swing: boolean
  axis: THREE.Vector3
}

function makeSeeds(n: number, seed: number, rMin: number, rMax: number, sMin: number, sMax: number, clearFront = false): Seed[] {
  const rnd = seeded(seed)
  return Array.from({ length: n }, (_, i) => ({
    // clearFront keeps the big cubes out of the sector between the label and the camera
    ang: clearFront ? 3.05 + (i / Math.max(n - 1, 1)) * 3.32 + (rnd() - 0.5) * 0.2 : (i / n) * Math.PI * 2 + rnd() * 0.5,
    swing: clearFront,
    h: (rnd() - 0.5) * 1.25,
    r: rMin + rnd() * (rMax - rMin),
    size: sMin + rnd() * (sMax - sMin),
    spd: 0.5 + rnd(),
    k: 0.5 + rnd(),
    phase: rnd() * 6.28,
    axis: new THREE.Vector3(rnd() - 0.5, rnd() - 0.5, rnd() - 0.5).normalize(),
  }))
}

const o = new THREE.Object3D()

/** Orbiting cubes: ring around the can, scroll-driven "explode out". */
function animateRing(mesh: THREE.InstancedMesh, seeds: Seed[]) {
  const { pose, canPos, canScale, time } = live
  const S = canScale
  const ex = pose.explode
  for (let i = 0; i < seeds.length; i++) {
    const s = seeds[i]
    const a = s.swing ? s.ang + Math.sin(time * 0.16 * s.spd + s.phase + pose.ry * 0.6) * 0.72 : s.ang + time * 0.1 * s.spd + pose.ry * 0.18
    const rad = s.r * (1 + ex * 2.3 * s.k)
    o.position.set(
      canPos.x + Math.cos(a) * rad * S,
      canPos.y + (s.h * (1 + ex * 1.1) + Math.sin(time * 0.6 + s.phase) * 0.04) * S,
      canPos.z + (Math.sin(a) * rad * 0.7 + ex * s.k * 1.2) * S,
    )
    o.quaternion.setFromAxisAngle(s.axis, s.phase + time * 0.25 * s.spd + ex * 3 * s.k)
    o.scale.setScalar(Math.max(s.size * S * pose.ice * (1 - ex * 0.15), 1e-4))
    o.updateMatrix()
    mesh.setMatrixAt(i, o.matrix)
  }
  mesh.instanceMatrix.needsUpdate = true
  mesh.visible = pose.ice > 0.01
}

/** Cheap ice: reflections only, added over whatever is behind (no refraction pass). */
function useFakeGlass() {
  const [mat, frost] = useMemo(() => {
    const frost = makeFrostNormal(256)
    const mat = new THREE.MeshPhysicalMaterial({
      color: '#bcdcff',
      emissive: '#10305f',
      emissiveIntensity: 0.55,
      roughness: 0.08,
      metalness: 1,
      normalMap: frost,
      normalScale: new THREE.Vector2(0.55, 0.55),
      clearcoat: 1,
      clearcoatRoughness: 0.02,
      envMapIntensity: 2.2,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    return [mat, frost] as const
  }, [])
  useEffect(() => () => { mat.dispose(); frost.dispose() }, [mat, frost])
  return mat
}

export function IceCubes({ quality, mobile }: { quality: 'high' | 'low'; mobile: boolean }) {
  const heroN = mobile ? 8 : 14
  const smallN = mobile ? 16 : 40
  const bedN = mobile ? 38 : 76

  const heroSeeds = useMemo(() => makeSeeds(heroN, 11, 0.58, 1.05, 0.1, 0.17, true), [heroN])
  const smallSeeds = useMemo(() => makeSeeds(smallN, 29, 0.9, 2.3, 0.03, 0.075), [smallN])
  const bed = useMemo(() => {
    const rnd = seeded(53)
    return Array.from({ length: bedN }, () => {
      const x = (rnd() + rnd() + rnd() - 1.5) * 0.95
      const z = (rnd() - 0.5) * 1.1
      // a heaped mound: tallest under the can, thinning out to the sides
      const top = Math.max(0.34 - x * x * 0.22, 0.04)
      return {
        x,
        z,
        y: -0.16 + rnd() * top - Math.abs(z) * 0.05,
        size: 0.1 + rnd() * 0.1,
        rot: new THREE.Euler(rnd() * 3, rnd() * 3, rnd() * 3),
        k: rnd(),
      }
    })
  }, [bedN])

  const rounded = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 3, 0.12), [])
  const box = useMemo(() => new RoundedBoxGeometry(1, 1, 1, 1, 0.1), [])
  useEffect(() => () => { rounded.dispose(); box.dispose() }, [rounded, box])
  const fake = useFakeGlass()
  const frost = fake.normalMap!
  // the bed stacks many cubes, so it gets a calmer copy of the material
  const bedMat = useMemo(() => {
    const m = fake.clone()
    m.envMapIntensity = 0.9
    m.emissiveIntensity = 0.3
    return m
  }, [fake])
  useEffect(() => () => bedMat.dispose(), [bedMat])
  const frostScale = useMemo(() => new THREE.Vector2(0.35, 0.35), [])
  const mtmBg = useMemo(() => new THREE.Color('#0f2350'), [])

  const heroRef = useRef<THREE.InstancedMesh>(null)
  const smallRef = useRef<THREE.InstancedMesh>(null)
  const bedRef = useRef<THREE.InstancedMesh>(null)

  useFrame(() => {
    if (heroRef.current) animateRing(heroRef.current, heroSeeds)
    if (smallRef.current) animateRing(smallRef.current, smallSeeds)
    const mesh = bedRef.current
    if (mesh) {
      const w = live.pose.bed
      mesh.visible = w > 0.01
      if (mesh.visible) {
        const u = live.bedUnit
        const jolt = Math.sin(Math.min(live.pose.burst * 1.6, 1) * Math.PI)
        for (let i = 0; i < bed.length; i++) {
          const b = bed[i]
          o.position.set(live.bedPos.x + b.x * u, live.bedPos.y + (b.y + jolt * 0.07 * b.k - (1 - w) * 0.5) * u, live.bedPos.z + b.z * u)
          o.rotation.copy(b.rot)
          o.scale.setScalar(b.size * u * w)
          o.updateMatrix()
          mesh.setMatrixAt(i, o.matrix)
        }
        mesh.instanceMatrix.needsUpdate = true
      }
    }
  })

  return (
    <>
      {/* hero cubes: real refraction on capable devices, cheap glass otherwise */}
      {quality === 'high' ? (
        <instancedMesh key="mtm" ref={heroRef} args={[rounded, undefined, heroN]} frustumCulled={false}>
          <MeshTransmissionMaterial
            samples={4}
            resolution={256}
            transmission={1}
            thickness={0.6}
            roughness={0.1}
            ior={1.31}
            normalMap={frost}
            normalScale={frostScale}
            envMapIntensity={2.4}
            clearcoat={1}
            chromaticAberration={0.05}
            anisotropicBlur={0.1}
            distortion={0.15}
            distortionScale={0.4}
            temporalDistortion={0}
            color="#ffffff"
            background={mtmBg}
          />
        </instancedMesh>
      ) : (
        <instancedMesh key="fake" ref={heroRef} args={[rounded, fake, heroN]} frustumCulled={false} />
      )}
      <instancedMesh ref={smallRef} args={[box, fake, smallN]} frustumCulled={false} />
      <instancedMesh ref={bedRef} args={[rounded, bedMat, bedN]} frustumCulled={false} />
    </>
  )
}
