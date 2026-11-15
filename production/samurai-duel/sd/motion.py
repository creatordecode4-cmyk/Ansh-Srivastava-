"""Takes: stretches of motion held as puppet controls, one set per frame at 24 fps.

Whatever the source - a motion-capture clip, a retargeted download, poses keyed by hand - a take
is the same thing: per frame, where the hips, feet and hands are and how pelvis, chest and head
are turned (the plain control form of sd/puppet.py). That makes the sources interchangeable:
takes can be moved and turned in the arena, cross-faded, slowed down, and cleaned up.

The clean-up that matters most is foot locking. A captured foot never stands perfectly still:
it creeps a centimetre or two while it is supposed to be planted. lock_feet() finds the frames
where the heel or the ball of a foot is down and holds that point exactly where it landed; the
legs are then solved to those targets, so a planted foot cannot slide.
"""
import math

import numpy as np
from mathutils import Matrix, Vector

from .puppet import X, Y, Z, mix_shapes, rot, slerp, ypr

FPS = 24.0


# ----------------------------------------------------------------------------- controls as data
def mix(a, b, t):
    """Blend two sets of plain controls (0 = a, 1 = b)."""
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    o = {}
    for k, va in a.items():
        vb = b.get(k)
        if vb is None:
            o[k] = va
        elif isinstance(va, Vector):
            o[k] = va.lerp(vb, t) if not k.startswith(("knee", "elbow")) else va.lerp(vb, t).normalized()
        elif isinstance(va, Matrix):
            o[k] = slerp(va, vb, t) if len(va) == 3 else _mix4(va, vb, t)
        elif k.startswith("fingers"):
            o[k] = mix_shapes(va, vb, t)
        elif isinstance(va, dict):
            o[k] = _mix_part(va, vb, t)
        elif isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            o[k] = va + (vb - va) * t
        else:
            o[k] = va if t < 0.5 else vb
    for k, vb in b.items():
        if k not in o:
            o[k] = vb
    return o


def _mix4(a, b, t):
    m = slerp(a.to_3x3(), b.to_3x3(), t).to_4x4()
    m.translation = a.translation.lerp(b.translation, t)
    return m


def _mix_part(a, b, t):
    """A foot or hand entry: positions lerp, rotations slerp. A hand given once from the shoulder
    and once in the world cannot be mixed term by term: the caller resolves those first."""
    o = {}
    for k in set(a) | set(b):
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            o[k] = va if (vb is None and t < 0.5) or (va is not None and t < 0.5) else vb
        elif isinstance(va, Vector):
            o[k] = va.lerp(vb, t)
        elif isinstance(va, Matrix):
            o[k] = slerp(va, vb, t)
        else:
            o[k] = va + (vb - va) * t
    return o


def moved(c, R, t):
    """The same controls after turning the whole fighter by R (3x3, about the vertical) and moving by t."""
    o = dict(c)
    o["hips"] = R @ c["hips"] + t
    for k in ("hips_D", "chest_D", "head_D"):
        o[k] = R @ c[k]
    for s in "LR":
        f = c["foot_" + s]
        o["foot_" + s] = dict(pos=R @ f["pos"] + Vector((t.x, t.y, 0.0)), D=R @ f["D"], toe=f.get("toe"))
        for k in ("knee_" + s, "elbow_" + s):
            if c.get(k) is not None:
                o[k] = R @ c[k]
        h = dict(c["hand_" + s])
        if "pos" in h:
            h["pos"] = R @ h["pos"] + t
        if h.get("D") is not None:
            h["D"] = R @ h["D"]
        o["hand_" + s] = h
    return o


def foot_angles(D):
    """(yaw, pitch, roll) in degrees of a foot rotation, the inverse of puppet.ypr."""
    f = D @ -Y
    yaw = math.atan2(f.x, -f.y)
    pitch = math.asin(max(-1.0, min(1.0, -f.z)))
    R = rot(X, -math.degrees(pitch)) @ rot(Z, -math.degrees(yaw)) @ D
    return math.degrees(yaw), math.degrees(pitch), math.degrees(math.atan2(R[0][2], R[0][0]))


def _runs(flags):
    """[(first, last)] of each run of True."""
    out, start = [], None
    for i, v in enumerate(list(flags) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _clean(flags, min_len=2, max_gap=1):
    f = np.array(flags, dtype=bool)
    for a, b in _runs(~f):                               # close short gaps (not at the ends)
        if b - a + 1 <= max_gap and a > 0 and b < len(f) - 1:
            f[a:b + 1] = True
    for a, b in _runs(f):
        if b - a + 1 < min_len:
            f[a:b + 1] = False
    return f


def _hyst(height, speed, h_in, h_out, v_in, v_out):
    on, out = False, []
    for h, v in zip(height, speed):
        on = (h < h_out and v < v_out) if on else (h < h_in and v < v_in)
        out.append(on)
    return out


def _ease(n):
    """Weights 1 -> 0 over n steps (smooth)."""
    return [1.0 - (lambda u: u * u * (3 - 2 * u))((i + 1) / (n + 1)) for i in range(n)]


# ----------------------------------------------------------------------------- a take
class Take:
    def __init__(self, frames, name="take"):
        self.c = list(frames)
        self.name = name
        self.locks = {}

    def __len__(self):
        return len(self.c)

    @classmethod
    def from_clip(cls, pp, clip, t0=0.0, seconds=None, speed=1.0, widen=0.0, ground=None):
        """Sample a mocap clip (sd/mocap.py) at 24 fps. speed < 1 plays it slower."""
        from . import mocap
        seconds = clip.T / speed if seconds is None else seconds
        n = int(round(seconds * FPS)) + 1
        if ground is None:                               # the clip's own floor: where its ankles rest lowest
            zs = []
            for i in range(60):
                Pz = clip.pose(clip.T * i / 59.0)
                zs += [Pz["Left"]["ankle"].z, Pz["Right"]["ankle"].z]
            ground = float(np.percentile(zs, 8))
        frames = [mocap.controls(pp, clip.pose(t0 + i / FPS * speed), ground=ground, widen=widen) for i in range(n)]
        return cls(frames, clip.name)

    def moved(self, yaw=0.0, to=(0, 0, 0)):
        R = rot(Z, yaw)
        t = Vector(to)
        return Take([moved(c, R, t) for c in self.c], self.name)

    def placed(self, at, facing, frame=0):
        """Turned and moved so that the hips stand over 'at' (x, y) on the given frame, facing 'facing' degrees
        there (0 = toward -Y, positive to the fighter's left)."""
        f = self.c[frame]["hips_D"] @ -Y
        yaw0 = math.degrees(math.atan2(f.x, -f.y))
        R = rot(Z, facing - yaw0)
        h = R @ self.c[frame]["hips"]
        t = Take([moved(c, R, Vector((at[0] - h.x, at[1] - h.y, 0.0))) for c in self.c], self.name)
        t.locks = self.locks
        return t

    def held(self, frames):
        """The same take with its last pose held for some more frames."""
        t = Take(self.c + [self.c[-1]] * frames, self.name)
        t.locks = {k: v + [v[-1]] * frames for k, v in self.locks.items()}
        return t

    # ---- feet on the ground
    def lock_feet(self, pp, h_in=0.022, h_out=0.04, v_in=0.35, v_out=0.7, heel_back=0.055, fade=5, verbose=False):
        """Hold each foot's heel or ball exactly where it comes down, for as long as it stays down."""
        n = len(self.c)
        self.locks = {}
        for tag, s in (("Left", "L"), ("Right", "R")):
            L = pp.leg[tag]
            heel0 = L["ankle_from_ball"] + Vector((0.0, heel_back, 0.0))
            heel0.z = -pp.ball_h                                         # the heel's point on the ground, from the ball joint
            raw = []
            for c in self.c:
                f = c["foot_" + s]
                raw.append((f["pos"].copy(), *foot_angles(f["D"])))
            yaw = np.degrees(np.unwrap(np.radians([r[1] for r in raw])))
            P = np.array([r[0][:] for r in raw])
            pitch, roll = np.array([r[2] for r in raw]), np.array([r[3] for r in raw])

            def heel_of(i, p=None, yw=None, pt=None, rl=None):
                D = ypr(yaw[i] if yw is None else yw, pitch[i] if pt is None else pt, roll[i] if rl is None else rl)
                return Vector(P[i] if p is None else p) + Vector((0, 0, pp.ball_h)) + D @ heel0

            Hh = np.array([heel_of(i)[:] for i in range(n)])
            vb = np.linalg.norm(np.gradient(P[:, :2], axis=0), axis=1) * FPS if n > 1 else np.zeros(n)
            vh = np.linalg.norm(np.gradient(Hh[:, :2], axis=0), axis=1) * FPS if n > 1 else np.zeros(n)
            cb = _clean(_hyst(P[:, 2], vb, h_in, h_out, v_in, v_out))
            ch = _clean(_hyst(Hh[:, 2], vh, h_in, h_out, v_in, v_out))
            out = [None] * n
            lockB = lockH = yaw_off = None
            for i in range(n):
                if not (cb[i] or ch[i]):
                    lockB = lockH = yaw_off = None
                    continue
                if yaw_off is None:
                    yaw_off = 0.0
                yw = yaw[i] + yaw_off
                if cb[i] and ch[i]:                                      # flat on the ground
                    if lockB is None and lockH is None:
                        lockB = Vector((P[i][0], P[i][1], 0.0))
                    elif lockB is None:                                  # came down heel first: the ball lands where the heel puts it
                        lockB = Vector((lockH.x, lockH.y, 0.0)) - ypr(yw, 0, 0) @ heel0
                        lockB.z = 0.0
                    if not out[i - 1] or out[i - 1][4] != "flat":        # the yaw it lands with is the yaw it keeps
                        flat_yaw = yw
                    yaw_off = flat_yaw - yaw[i]
                    pos, ang, kind = lockB.copy(), (flat_yaw, 0.0, 0.0), "flat"
                    lockH = lockB + Vector((0, 0, pp.ball_h)) + ypr(flat_yaw, 0, 0) @ heel0
                    lockH.z = 0.0
                elif cb[i]:                                              # on the ball: the heel is free to rise and the foot to pivot
                    if lockB is None:
                        lockB = Vector((P[i][0], P[i][1], 0.0))
                    pos, ang, kind = lockB.copy(), (yw, max(0.0, pitch[i]), roll[i] * 0.5), "ball"
                    lockH = None
                else:                                                    # on the heel: toes still in the air
                    if lockH is None:
                        h = heel_of(i, yw=yw)
                        lockH = Vector((h.x, h.y, 0.0))
                    ang = (yw, min(0.0, pitch[i]), roll[i] * 0.5)
                    bj = lockH - ypr(*ang) @ heel0
                    pos, kind = bj - Vector((0, 0, pp.ball_h)), "heel"
                    lockB = None
                out[i] = (pos, ang[0], ang[1], ang[2], kind)
            # frames in the air keep the captured motion, eased into and out of the locked stretches
            held = np.array([o is not None for o in out])
            dP, dA = np.zeros((n, 3)), np.zeros((n, 3))
            for i in range(n):
                if out[i] is not None:
                    dP[i] = np.array(out[i][0][:]) - P[i]
                    dA[i] = np.array(out[i][1:4]) - np.array((yaw[i], pitch[i], roll[i]))
            w = _ease(fade)
            for a, b in _runs(held):
                for j, wj in enumerate(w):                               # after the foot leaves
                    i = b + 1 + j
                    if i < n and not held[i]:
                        dP[i] += dP[b] * wj
                        dA[i] += dA[b] * wj
                for j, wj in enumerate(_ease(min(3, fade))):             # before it lands
                    i = a - 1 - j
                    if i >= 0 and not held[i]:
                        dP[i] += dP[a] * wj * 0.999
                        dA[i] += dA[a] * wj * 0.999
            for i, c in enumerate(self.c):
                pos = Vector(P[i] + dP[i])
                ang = np.array((yaw[i], pitch[i], roll[i])) + dA[i]
                D = ypr(*ang)
                if not held[i]:                                          # in the air, but never through the floor
                    low = min(pos.z, (pos + Vector((0, 0, pp.ball_h)) + D @ heel0).z)
                    if low < 0.0:
                        pos.z -= low
                c["foot_" + s] = dict(pos=pos, D=D, toe=None)
            self.locks[tag] = [o[4] if o is not None else None for o in out]
            if verbose:
                runs = [(a, b, out[a][4]) for a, b in _runs(held)]
                print(f"    {tag} foot down: {[(a, b) for a, b, _ in runs]}  largest correction {np.abs(dP[held]).max() * 100 if held.any() else 0:.1f} cm")
        return self

    def fit_hips(self, pp, slack=0.004):
        """Lower the hips where a leg would otherwise have to stretch beyond its length to reach its foot."""
        n = len(self.c)
        need = np.zeros(n)
        H = pp.H0
        for i, c in enumerate(self.c):
            for tag, s in (("Left", "L"), ("Right", "R")):
                L = pp.leg[tag]
                A = c["hips"] + c["hips_D"] @ (H[tag + "UpLeg"] - H["Hips"])
                f = c["foot_" + s]
                T = f["pos"] + Vector((0, 0, pp.ball_h)) + f["D"] @ L["ankle_from_ball"]
                Lmax = L["L1"] + L["L2"] - slack
                d = T - A
                hor = math.hypot(d.x, d.y)
                if d.length > Lmax and hor < Lmax:
                    need[i] = max(need[i], (A.z - T.z) - math.sqrt(Lmax * Lmax - hor * hor))
        if need.max() > 0:
            sm = need.copy()
            for _ in range(3):                                           # spread each dip over its neighbours, never less than needed
                sm = np.maximum(need, np.convolve(np.pad(sm, 2, mode="edge"), np.ones(5) / 5.0, mode="valid"))
            for i, c in enumerate(self.c):
                c["hips"] = c["hips"] - Vector((0, 0, sm[i]))
        return float(need.max())

    # ---- solving
    def poses(self, pp):
        return [pp.solve(c) for c in self.c]

    def slide_report(self, pp, poses):
        """Largest drift (metres) of a planted ball or heel over each stretch it is held, and the worst reach shortfall."""
        worst, short = 0.0, 0.0
        for tag in ("Left", "Right"):
            kinds = self.locks.get(tag) or []
            pts = [pp.heads(p)[tag + "ToeBase"] for p in poses]
            for a, b in _runs([k in ("flat", "ball") for k in kinds]):
                for i in range(a, b + 1):
                    d = pts[i] - pts[a]
                    worst = max(worst, math.hypot(d.x, d.y))
        for p in poses:
            for k, v in p["short"].items():
                if "Foot" in k:
                    short = max(short, v)
        return worst, short
