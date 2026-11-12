import { SECTION_IDS, scrollStore, lerp, ss, type SectionId } from './scrollStore'

/**
 * A pose describes the can, the camera and the FX levels for one moment.
 * x / y are viewport fractions from the centre (+y up), s is the can height
 * as a fraction of the viewport height, so layouts hold on any screen.
 */
export interface Pose {
  x: number
  y: number
  s: number
  rx: number
  ry: number
  rz: number
  /** camera distance multiplier (1 = base, <1 dolly in) */
  cam: number
  /** camera orbit angle around Y */
  orbit: number
  /** canvas opacity */
  o: number
  /** ice cube presence */
  ice: number
  /** ice burst 0..1 */
  explode: number
  /** lineup carousel weight */
  carousel: number
  /** crushed-ice bed weight */
  bed: number
  /** final splash burst 0..1 */
  burst: number
  /** idle bob multiplier */
  bob: number
}

const TAU = Math.PI * 2
const base: Pose = { x: 0, y: 0, s: 0.6, rx: 0, ry: 0, rz: 0, cam: 1, orbit: 0, o: 1, ice: 0, explode: 0, carousel: 0, bed: 0, burst: 0, bob: 1 }
const P = (p: Partial<Pose>): Pose => ({ ...base, ...p })
const KEYS = Object.keys(base) as (keyof Pose)[]

export function mixPose(a: Pose, b: Pose, t: number, out: Pose = { ...base }): Pose {
  for (const k of KEYS) out[k] = lerp(a[k], b[k], t)
  return out
}

/* ---------- hero video ↔ 3D match ---------- */
export const VIDEO_ASPECT = 1264 / 720
/** Where the hero video sits, as viewport fractions. Hero.tsx uses the same numbers. */
export const heroBox = {
  desktop: { l: -0.2, t: 0, w: 1.2, h: 1 },
  mobile: { l: 0, t: 0, w: 1, h: 0.58 },
}
/** Can centre + width inside the video's last frame (fractions of the frame). */
const LAST = { u: 0.463, v: 0.47, w: 0.4 }
const CAN_H_OVER_W = 1 / 0.54

export function heroMatch(aspect: number, mobile: boolean) {
  const b = mobile ? heroBox.mobile : heroBox.desktop
  const boxAspect = (b.w * aspect) / b.h
  // object-fit: cover
  const dispW = boxAspect > VIDEO_ASPECT ? b.w : (b.h * VIDEO_ASPECT) / aspect // in vw
  const dispH = boxAspect > VIDEO_ASPECT ? (b.w * aspect) / VIDEO_ASPECT : b.h // in vh
  const sx = b.l + b.w / 2 + (LAST.u - 0.5) * dispW
  const sy = b.t + b.h / 2 + (LAST.v - 0.5) * dispH
  return {
    x: sx - 0.5,
    y: 0.5 - sy,
    s: LAST.w * dispW * aspect * CAN_H_OVER_W,
    /** transform-origin for the slow zoom, as % of the video box */
    originX: ((sx - b.l) / b.w) * 100,
    originY: ((sy - b.t) / b.h) * 100,
  }
}

/* ---------- per-section poses ---------- */
type PoseFn = (p: number, m: boolean, aspect: number) => Pose

const FLIP = TAU // the splash flip leaves rx one full turn ahead

/** hero resting pose; the trust strip reuses it so the can simply stays put */
const heroFloat = (m: boolean) => (m ? P({ y: 0.2, s: 0.46, ry: -0.1, ice: 0.6 }) : P({ x: -0.2, y: -0.03, s: 0.72, ry: -0.1, ice: 0.7 }))
/** small can drifting behind Recommendations / Why People Love It / Community (short sections share one pose) */
const bgFloat = (m: boolean) =>
  P({ x: m ? 0.34 : 0.4, y: m ? 0.36 : 0.29, s: m ? 0.12 : 0.22, rx: FLIP, ry: 3 * TAU + 0.9, rz: 0.12, ice: 0.3, bob: 3.2 })

const poses: Record<SectionId, PoseFn> = {
  hero: (p, m, aspect) => {
    const h = heroMatch(aspect, m)
    const match = P({ x: h.x, y: h.y, s: h.s * scrollStore.heroZoom, ry: 0.62, rz: -0.012 })
    const float = heroFloat(m)
    const out = mixPose(match, float, ss(m ? 0.12 : 0.3, m ? 0.8 : 0.95, p))
    out.o = ss(0.02, 0.28, p)
    return out
  },
  trust: (_p, m) => heroFloat(m),
  story: (p, m) =>
    P({
      y: m ? -0.03 : 0,
      s: m ? 0.36 : lerp(0.6, 0.68, p),
      ry: TAU * ss(0.02, 0.98, p),
      cam: lerp(1, 0.8, p),
      ice: 0.45,
    }),
  journey: (p, m) =>
    P({
      x: m ? 0.3 : 0.33,
      y: m ? 0.085 : 0.13,
      s: m ? 0.17 : 0.44,
      ry: TAU + p * 1.3,
      rz: 0.06,
      ice: 0.25,
    }),
  why: (p, m) =>
    P({
      y: m ? 0.07 : -0.03,
      s: m ? 0.32 : 0.54,
      rx: 0.08,
      ry: TAU + 1.3 + p * 0.9,
      rz: 0.2 * ss(0, 0.35, p),
      orbit: lerp(-0.32, 0.32, p),
      ice: 1,
    }),
  numbers: (_p, m) =>
    P({ x: m ? 0.32 : 0.39, y: m ? 0.37 : 0.3, s: m ? 0.12 : 0.2, rx: 0.08, ry: TAU + 2.6, rz: 0.14, ice: 0.55, bob: 2 }),
  splash: (p, m) =>
    P({
      y: lerp(0.06, m ? 0.14 : 0.2, p),
      s: lerp(m ? 0.5 : 0.7, m ? 0.95 : 1.3, ss(0, 0.85, p)),
      rx: 0.08 + (FLIP - 0.08) * ss(0.42, 0.66, p),
      ry: 2 * TAU + lerp(-0.28, 0.12, p),
      cam: lerp(0.88, 0.62, p),
      ice: 1,
      explode: ss(0.08, 0.8, p),
    }),
  taste: (p, m) =>
    P({
      x: m ? 0 : 0.23,
      y: m ? 0.25 : 0,
      s: m ? 0.3 : 0.56,
      rx: FLIP,
      ry: 2 * TAU + 0.3 + p * 2.2,
      ice: 0.35,
    }),
  lineup: (_p, m) => P({ y: m ? 0.05 : 0.055, s: m ? 0.3 : 0.42, rx: FLIP, ry: 3 * TAU, carousel: 1 }),
  nutrition: (p, m) =>
    P({
      x: m ? 0 : -0.24,
      y: m ? 0.27 : 0,
      s: m ? 0.26 : 0.56,
      rx: FLIP,
      ry: 3 * TAU + lerp(-0.5, 0.5, p),
      ice: 0.2,
    }),
  reviews: (_p, m) => bgFloat(m),
  love: (_p, m) => bgFloat(m),
  community: (_p, m) => bgFloat(m),
  cta: (p, m) => {
    const rest = m ? -0.2 : -0.06
    const d = ss(0, 0.42, p)
    const drop = d * d // accelerate into the ice
    const settle = Math.sin(ss(0.42, 0.7, p) * Math.PI) * 0.012
    return P({
      x: m ? 0 : 0.24,
      y: lerp(1.15, rest, drop) - settle,
      s: m ? 0.3 : 0.5,
      rx: FLIP,
      ry: 4 * TAU - 0.3,
      rz: lerp(0.25, 0.04, drop),
      cam: 1.18,
      bed: 1,
      burst: ss(0.38, 0.8, p),
    })
  },
  faq: (_p, m, a) => ({ ...poses.cta(1, m, a), o: 0 }),
}

/** Where the crushed-ice bed sits (viewport fractions), derived from the CTA rest pose. */
export function bedAnchor(m: boolean) {
  const rest = poses.cta(1, m, 1)
  return { x: rest.x, y: rest.y - rest.s * 0.36, s: rest.s }
}

/** Target pose for the current scroll position. */
export function computePose(aspect: number, out: Pose): Pose {
  const m = scrollStore.isMobile
  let idx = 0
  for (let i = 1; i < SECTION_IDS.length; i++) if (scrollStore.sections[SECTION_IDS[i]].enter > 0) idx = i
  const id = SECTION_IDS[idx]
  const sec = scrollStore.sections[id]
  const cur = poses[id](sec.pin, m, aspect)
  if (idx > 0 && sec.enter < 1) {
    const prev = poses[SECTION_IDS[idx - 1]](1, m, aspect)
    return mixPose(prev, cur, ss(0, 1, sec.enter), out)
  }
  return Object.assign(out, cur)
}

export const basePose = base
