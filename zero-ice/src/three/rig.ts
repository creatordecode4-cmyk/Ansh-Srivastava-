import * as THREE from 'three'
import { basePose, type Pose } from './choreography'

/** Smoothed, per-frame scene state shared by Can / IceCubes / Particles. Written by <Rig/>. */
export const live = {
  pose: { ...basePose } as Pose,
  /** world position + scale (= world height) of the hero can */
  canPos: new THREE.Vector3(),
  canScale: 1,
  /** world height / width of the viewport at z = 0 for the base camera */
  viewH: 1,
  viewW: 1,
  /** crushed-ice bed anchor */
  bedPos: new THREE.Vector3(),
  bedUnit: 1,
  time: 0,
}

export const BASE_DIST = 10
export const FOV = 28

/** deterministic random so layouts are stable between reloads */
export function seeded(seed: number) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}
