import { forwardRef, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useGLTF } from '@react-three/drei'
import type { VariantId } from '../tokens'
import { makeDropletMaps, makeLabelTexture } from './textures'
import { seeded } from './rig'

/** Can profile (radius, y) from the centre of the base up to the centre of the lid. Height = 1. */
const PROFILE: [number, number][] = [
  [0, -0.468], [0.1, -0.47], [0.17, -0.482], [0.205, -0.5], [0.222, -0.5], [0.24, -0.49],
  [0.258, -0.466], [0.268, -0.435], [0.27, -0.41], [0.27, 0.37], [0.267, 0.395], [0.255, 0.425],
  [0.238, 0.452], [0.229, 0.468], [0.229, 0.478], [0.236, 0.486], [0.237, 0.494], [0.231, 0.5],
  [0.223, 0.499], [0.218, 0.49], [0.216, 0.474], [0, 0.472],
]
export const CAN_RADIUS = 0.27

export interface CanAssets {
  body: THREE.BufferGeometry
  tab: THREE.BufferGeometry
  rivet: THREE.BufferGeometry
  drop: THREE.BufferGeometry
  metal: THREE.MeshStandardMaterial
  dropMat: THREE.MeshPhysicalMaterial
  bodyMats: Record<VariantId, THREE.MeshPhysicalMaterial>
  dispose: () => void
}

export function createCanAssets(mobile: boolean): CanAssets {
  const body = new THREE.LatheGeometry(PROFILE.map(([r, y]) => new THREE.Vector2(r, y)), mobile ? 56 : 96)
  // remap V to the can's height so the label texture maps 1:1 top to bottom
  const pos = body.attributes.position
  const uv = body.attributes.uv
  for (let i = 0; i < uv.count; i++) uv.setY(i, pos.getY(i) + 0.5)
  uv.needsUpdate = true

  // pull-tab: rounded plate with a finger hole
  const s = new THREE.Shape()
  const w = 0.058, h = 0.095, r = 0.026
  s.moveTo(-w + r, -h)
  s.lineTo(w - r, -h)
  s.quadraticCurveTo(w, -h, w, -h + r)
  s.lineTo(w * 0.8, h - r)
  s.quadraticCurveTo(w * 0.8, h, w * 0.8 - r, h)
  s.lineTo(-w * 0.8 + r, h)
  s.quadraticCurveTo(-w * 0.8, h, -w * 0.8, h - r)
  s.lineTo(-w, -h + r)
  s.quadraticCurveTo(-w, -h, -w + r, -h)
  const hole = new THREE.Path()
  hole.absellipse(0, -h * 0.42, w * 0.55, h * 0.3, 0, Math.PI * 2, true)
  s.holes.push(hole)
  const tab = new THREE.ExtrudeGeometry(s, { depth: 0.007, bevelEnabled: true, bevelSize: 0.003, bevelThickness: 0.003, bevelSegments: 2, curveSegments: 10 })
  const rivet = new THREE.CylinderGeometry(0.017, 0.019, 0.012, 20)
  const drop = new THREE.SphereGeometry(1, 10, 8)

  const maps = makeDropletMaps(mobile ? 512 : 1024)
  const labels = {
    original: makeLabelTexture('original', mobile ? 1024 : 2048),
    lime: makeLabelTexture('lime', 1024),
    cherry: makeLabelTexture('cherry', 1024),
  }
  const mk = (map: THREE.Texture) =>
    new THREE.MeshPhysicalMaterial({
      map,
      metalness: 1,
      roughness: 1, // scaled by the roughness map
      roughnessMap: maps.roughnessMap,
      normalMap: maps.normalMap,
      normalScale: new THREE.Vector2(0.6, 0.6),
      clearcoat: 0.55,
      clearcoatRoughness: 0.18,
      envMapIntensity: 1.2,
    })
  const bodyMats = { original: mk(labels.original), lime: mk(labels.lime), cherry: mk(labels.cherry) }
  const metal = new THREE.MeshStandardMaterial({ color: '#cfd5da', metalness: 1, roughness: 0.3 })
  const dropMat = new THREE.MeshPhysicalMaterial({
    color: '#d5f6fb',
    roughness: 0.04,
    metalness: 1,
    transparent: true,
    blending: THREE.AdditiveBlending,
    envMapIntensity: 0.9,
    depthWrite: false,
  })

  return {
    body, tab, rivet, drop, metal, dropMat, bodyMats,
    dispose() {
      ;[body, tab, rivet, drop].forEach((g) => g.dispose())
      Object.values(labels).forEach((t) => t.dispose())
      maps.normalMap.dispose()
      maps.roughnessMap.dispose()
      Object.values(bodyMats).forEach((m) => m.dispose())
      metal.dispose()
      dropMat.dispose()
    },
  }
}

/** ~60 glassy beads sitting on the can wall. */
function Condensation({ assets, count, seed }: { assets: CanAssets; count: number; seed: number }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  useLayoutEffect(() => {
    const mesh = ref.current!
    const rnd = seeded(seed)
    const o = new THREE.Object3D()
    for (let i = 0; i < count; i++) {
      const a = rnd() * Math.PI * 2
      const y = -0.36 + rnd() * 0.7
      const r = 0.0035 + rnd() * rnd() * 0.009
      o.position.set(Math.sin(a) * CAN_RADIUS, y, Math.cos(a) * CAN_RADIUS)
      o.rotation.set(0, a, 0)
      o.scale.set(r, r * (1.1 + rnd() * 0.5), r * 0.45)
      o.updateMatrix()
      mesh.setMatrixAt(i, o.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
  }, [count, seed])
  return <instancedMesh ref={ref} args={[assets.drop, assets.dropMat, count]} frustumCulled={false} />
}

interface CanProps {
  assets: CanAssets
  variant: VariantId
  droplets: number
  seed?: number
}

/** Procedural can. The group is 1 unit tall, centred on the origin, label facing +Z. */
export const Can = forwardRef<THREE.Group, CanProps>(function Can({ assets, variant, droplets, seed = 7 }, ref) {
  return (
    <group ref={ref}>
      <mesh geometry={assets.body} material={assets.bodyMats[variant]} rotation-y={-Math.PI / 2} />
      <mesh geometry={assets.tab} material={assets.metal} position={[0, 0.476, 0.06]} rotation-x={-Math.PI / 2} />
      <mesh geometry={assets.rivet} material={assets.metal} position={[0, 0.478, -0.02]} />
      {droplets > 0 && <Condensation assets={assets} count={droplets} seed={seed} />}
    </group>
  )
})

/** Optional drop-in model: public/models/can.glb replaces the procedural hero can. */
export const GlbCan = forwardRef<THREE.Group, { url: string }>(function GlbCan({ url }, ref) {
  const { scene } = useGLTF(url)
  const model = useMemo(() => {
    const m = scene.clone(true)
    const box = new THREE.Box3().setFromObject(m)
    const size = box.getSize(new THREE.Vector3())
    const centre = box.getCenter(new THREE.Vector3())
    m.position.sub(centre)
    const wrap = new THREE.Group()
    wrap.add(m)
    wrap.scale.setScalar(1 / size.y)
    return wrap
  }, [scene])
  useEffect(() => () => useGLTF.clear(url), [url])
  return (
    <group ref={ref}>
      <primitive object={model} />
    </group>
  )
})
