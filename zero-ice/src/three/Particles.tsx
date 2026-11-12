import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Sparkles } from '@react-three/drei'
import { colors } from '../tokens'
import { live, seeded } from './rig'
import { makeMistTexture } from './textures'

const o = new THREE.Object3D()
const tmp = new THREE.Vector3()

export function Particles({ mobile }: { mobile: boolean }) {
  const dropN = mobile ? 18 : 40
  const burstN = mobile ? 20 : 36
  const mistN = mobile ? 4 : 7

  const drops = useMemo(() => {
    const rnd = seeded(97)
    return Array.from({ length: dropN }, () => ({
      x: (rnd() - 0.5) * 1.3,
      y: rnd(),
      z: -3.5 + rnd() * 5,
      size: 0.012 + rnd() * rnd() * 0.03,
      spd: 0.01 + rnd() * 0.03,
      k: 0.4 + rnd(),
    }))
  }, [dropN])

  const burst = useMemo(() => {
    const rnd = seeded(131)
    return Array.from({ length: burstN }, () => {
      const a = rnd() * Math.PI * 2
      const up = 0.5 + rnd() * 0.9
      const out = 0.25 + rnd() * 0.8
      return { vx: Math.cos(a) * out, vy: up, vz: Math.sin(a) * out * 0.6, size: 0.007 + rnd() * rnd() * 0.022, amber: rnd() < 0.4 }
    })
  }, [burstN])

  const mist = useMemo(() => {
    const rnd = seeded(211)
    return Array.from({ length: mistN }, () => ({
      x: (rnd() - 0.5) * 1.1,
      y: (rnd() - 0.5) * 0.8,
      z: -4 + rnd() * 2.5,
      scale: 6 + rnd() * 5,
      spd: 0.05 + rnd() * 0.08,
      phase: rnd() * 6.28,
    }))
  }, [mistN])

  const sphere = useMemo(() => new THREE.SphereGeometry(1, 10, 8), [])
  const dropMat = useMemo(
    () => new THREE.MeshPhysicalMaterial({ color: '#c9f3fb', emissive: '#0f5568', emissiveIntensity: 0.25, roughness: 0.05, metalness: 1, transparent: true, blending: THREE.AdditiveBlending, envMapIntensity: 2, depthWrite: false }),
    [],
  )
  const burstMat = useMemo(
    () => new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 0.03, metalness: 0.1, transparent: true, opacity: 0.8, clearcoat: 1, envMapIntensity: 2.5 }),
    [],
  )
  const mistTex = useMemo(() => makeMistTexture(), [])
  const mistMat = useMemo(
    () => new THREE.SpriteMaterial({ map: mistTex, color: '#8fa0ad', transparent: true, opacity: 0.028, depthWrite: false, fog: false }),
    [mistTex],
  )
  useEffect(
    () => () => {
      sphere.dispose()
      dropMat.dispose()
      burstMat.dispose()
      mistTex.dispose()
      mistMat.dispose()
    },
    [sphere, dropMat, burstMat, mistTex, mistMat],
  )

  // the one glow on the page: a soft cyan halo that stays behind the can
  const glowMat = useMemo(
    () => new THREE.SpriteMaterial({ map: mistTex, color: colors.cyan, transparent: true, opacity: 0.16, depthWrite: false, fog: false, blending: THREE.AdditiveBlending }),
    [mistTex],
  )
  useEffect(() => () => glowMat.dispose(), [glowMat])
  const glowRef = useRef<THREE.Sprite>(null)
  const dropRef = useRef<THREE.InstancedMesh>(null)
  const burstRef = useRef<THREE.InstancedMesh>(null)
  const mistRef = useRef<THREE.Group>(null)

  useEffect(() => {
    const mesh = burstRef.current
    if (!mesh) return
    const water = new THREE.Color(colors.frost)
    const cola = new THREE.Color('#C0621B') // cola droplets: the only amber left, inside the 3D splash
    burst.forEach((b, i) => mesh.setColorAt(i, b.amber ? cola : water))
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [burst])

  useFrame(() => {
    const { pose, canPos, viewW, viewH, time } = live
    // floating droplets, pushed away from the can during the splash burst
    const dm = dropRef.current
    if (dm) {
      for (let i = 0; i < drops.length; i++) {
        const d = drops[i]
        const yy = ((d.y + time * d.spd) % 1) - 0.5
        tmp.set(d.x * viewW, yy * viewH * 1.3, d.z)
        if (pose.explode > 0.001) {
          const dx = tmp.x - canPos.x
          const dy = tmp.y - canPos.y
          const len = Math.hypot(dx, dy) || 1
          tmp.x += (dx / len) * pose.explode * 1.6 * d.k
          tmp.y += (dy / len) * pose.explode * 1.6 * d.k
          tmp.z += pose.explode * d.k
        }
        o.position.copy(tmp)
        o.rotation.set(0, 0, 0)
        o.scale.setScalar(d.size * (1 + pose.explode * 0.8))
        o.updateMatrix()
        dm.setMatrixAt(i, o.matrix)
      }
      dm.instanceMatrix.needsUpdate = true
    }
    // final splash burst out of the ice bed
    const bm = burstRef.current
    if (bm) {
      const b = pose.burst
      bm.visible = b > 0.002 && b < 0.998 && pose.bed > 0.5
      if (bm.visible) {
        const u = live.bedUnit
        const pop = Math.sin(Math.min(b, 1) * Math.PI)
        for (let i = 0; i < burst.length; i++) {
          const p = burst[i]
          o.position.set(
            live.bedPos.x + p.vx * b * u * 1.3,
            live.bedPos.y + (0.2 + p.vy * b * 1.5 - b * b * 1.25) * u,
            live.bedPos.z + 0.3 * u + p.vz * b * u,
          )
          o.scale.setScalar(p.size * u * pop)
          o.updateMatrix()
          bm.setMatrixAt(i, o.matrix)
        }
        bm.instanceMatrix.needsUpdate = true
      }
    }
    const halo = glowRef.current
    if (halo) {
      halo.position.set(canPos.x, canPos.y, canPos.z - 1.2)
      halo.scale.set(live.canScale * 2.1, live.canScale * 2.3, 1)
    }
    // mist drift
    const g = mistRef.current
    if (g) {
      for (let i = 0; i < g.children.length; i++) {
        const m = mist[i]
        const sp = g.children[i]
        sp.position.set(m.x * viewW + Math.sin(time * m.spd + m.phase) * 1.2, m.y * viewH + Math.cos(time * m.spd * 0.7 + m.phase) * 0.4, m.z)
      }
    }
  })

  return (
    <>
      <instancedMesh ref={dropRef} args={[sphere, dropMat, dropN]} frustumCulled={false} />
      <instancedMesh ref={burstRef} args={[sphere, burstMat, burstN]} frustumCulled={false} />
      <sprite ref={glowRef} material={glowMat} />
      <group ref={mistRef}>
        {mist.map((m, i) => (
          <sprite key={i} material={mistMat} scale={[m.scale, m.scale * 0.7, 1]} />
        ))}
      </group>
      <Sparkles count={mobile ? 8 : 18} scale={[14, 8, 6]} size={mobile ? 1.6 : 2.2} speed={0.25} opacity={0.6} color={colors.frost} noise={1.2} />
    </>
  )
}
