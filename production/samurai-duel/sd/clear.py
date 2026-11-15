"""Keeping things from passing through each other.

A captured performer is slim and wears nothing; the fighters are broad, armoured and hung with
cloth, scabbards and a wide hat. Put the performer's motion on them unchanged and hands swing
through hips and skirts, a scabbard tied to one bone cuts through the trousers when the leg under
it moves, and the hat brim dips into the sword grips behind the shoulders.

Each kind of contact is resolved the way it resolves in life, against the posed body (sd/skin.py):

  arms      a free hand that would enter the body is moved out along the body's surface normal
  scabbards are not glued to one bone: they lie on the skin at two points (back) or hang from the
            belt and are pushed aside by whatever moves under them (hip)
  hat       the head keeps its turn but loses as much of its tilt as is needed for the brim to clear
  tassels   swing as before but stop at the body
  cloth     after simulation, any vertex left inside the body is put back on its surface

clip_report() measures what is left, so 'fixed' is a number and not an impression.
"""
import math

import numpy as np
from mathutils import Matrix, Vector

from .puppet import I3, slerp, ypr


def _vec(a):
    return Vector((float(a[0]), float(a[1]), float(a[2])))


def _rotation(M):
    """Nearest proper rotation to a 3x3 that is only roughly one (a blend of bone rotations)."""
    u, _, vt = np.linalg.svd(np.asarray(M, dtype=np.float64))
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ vt
    return Matrix(r.tolist())


def _smooth(a, k=5):
    """Moving average over time (rows are frames)."""
    a = np.asarray(a, dtype=np.float64)
    if len(a) < 3 or k < 2:
        return a
    pad = np.pad(a, ((k // 2, k // 2),) + ((0, 0),) * (a.ndim - 1), mode="edge")
    out = np.zeros_like(a)
    for i in range(k):
        out += pad[i:i + len(a)]
    return out / k


# ----------------------------------------------------------------------------- arms
def arm_points(pp, skin, pose, tag):
    """Centre-line points of one arm with the radius of the limb there: (name, position, radius)."""
    H = pp.heads(pose)
    W, E = H[tag + "Hand"], H[tag + "ForeArm"]
    K = H[tag + "HandMiddle1"]
    tip = K + (K - W).normalized() * (0.55 * pp.hand[tag]["Lh"])
    r = skin.limb_radius
    return [("hand", W.lerp(K, 0.6), r["hand"]), ("fingers", K.lerp(tip, 0.5), r["hand"] * 0.8), ("wrist", W, r["wrist"]),
            ("forearm", E.lerp(W, 0.5), r["forearm"])]              # not the elbow: it is too near the shoulder to be judged against the trunk


def arm_lack(pp, skin, posed, pose, tag, gap, parts=None, brim=None):
    """How far the arm is short of its clearance from the body (metres; <= 0 is clear), and the way out.
    parts limits the test to some of the arm's points; brim = hat points on this frame (the arm must
    also stay off the hat)."""
    pts = [q for q in arm_points(pp, skin, pose, tag) if parts is None or q[0] in parts]
    if parts is not None and "elbow" in parts:
        pts.append(("elbow", pp.heads(pose)[tag + "ForeArm"], skin.limb_radius["forearm"] * 0.9))
    P = np.array([p for _, p, _ in pts])
    rad = np.array([r for _, _, r in pts])
    d, nrm, _ = posed.signed(P, "body")
    lack = rad + gap - d
    k = int(np.argmax(lack))
    best = (float(lack[k]), nrm[k], pts[k][0])
    if brim is not None:
        for i in range(len(P)):
            v = P[i] - brim
            dist = np.linalg.norm(v, axis=1)
            j = int(np.argmin(dist))
            short = rad[i] + 0.012 - dist[j]
            if short > best[0]:
                best = (float(short), v[j] / max(dist[j], 1e-9), "hat")
    return best


def _swivel(pp, skin, posed, c, pose, tag, gap, prefer=0.0, brim=None):
    """Turn the elbow round the line from shoulder to wrist until forearm and elbow clear the body.
    Returns (angle in degrees, changed controls, pose) or None if they are clear as they are."""
    lack, _, _ = arm_lack(pp, skin, posed, pose, tag, gap, parts=("forearm", "elbow"), brim=brim)
    if lack <= 1e-4 and abs(prefer) < 1.0:
        return None
    H = pp.heads(pose)
    A, T, E = H[tag + "Arm"], H[tag + "Hand"], H[tag + "ForeArm"]
    n = (T - A).normalized()
    b0 = (E - A) - n * (E - A).dot(n)
    if b0.length < 1e-5:
        return None
    b0.normalize()
    key = "elbow_" + tag[0]
    best = None
    for ang in sorted((0, 12, -12, 25, -25, 38, -38, 52, -52, 66, -66, 80, -80), key=lambda a: abs(a - prefer)):
        c2 = dict(c)
        c2[key] = Matrix.Rotation(math.radians(ang), 3, n) @ b0
        p2 = pp.solve(c2)
        lk, _, _ = arm_lack(pp, skin, posed, p2, tag, gap, parts=("forearm", "elbow"), brim=brim)
        if best is None or lk < best[0] - 1e-4:
            best = (lk, ang, c2, p2)
        if lk <= 1e-4:
            break
    return best[1], best[2], best[3]


def arms(pp, skin, posed, controls, poses, free, gap=0.012, brims=None):
    """Keep the arms out of the body. controls and poses are in the armature's space and are changed
    in place; posed[f] is the skin in that space; free[f][tag] says whether that hand may be moved
    on frame f (a hand closed on a planned sword may not: only its elbow is turned).
    Returns (largest hand push in metres, largest elbow turn in degrees)."""
    n = len(poses)
    worst, turn = 0.0, 0.0
    for tag in ("Left", "Right"):
        s = tag[0]
        reach = (pp.arm_[tag]["L1"] + pp.arm_[tag]["L2"]) * 0.97       # a pushed hand never asks for a locked-straight arm
        # free hands first: push them out; the first push is eased in and out over time
        total = np.zeros((n, 3))
        for rnd in range(8):
            need = np.zeros((n, 3))
            for f in range(n):
                if free[f][tag]:
                    lack, nrm, _ = arm_lack(pp, skin, posed[f], poses[f], tag, gap, brim=brims[f] if brims else None)
                    if lack > 1e-4:
                        need[f] = nrm * lack
            if not need.any():
                break
            add = need
            if rnd == 0:
                sm = _smooth(need, 7)
                add = np.where(np.linalg.norm(need, axis=1, keepdims=True) > np.linalg.norm(sm, axis=1, keepdims=True), need, sm)
            total += add
            for f in range(n):
                if not free[f][tag] or not add[f].any():
                    continue
                c = controls[f]
                h = dict(c["hand_" + s])
                H = pp.heads(poses[f])
                A = H[tag + "Arm"]
                T = H[tag + "Hand"] + _vec(add[f])                     # from where the wrist is now, not from where it was asked to be
                if (T - A).length > reach:
                    T = A + (T - A).normalized() * reach               # further out means higher: the arm swings away from the side
                h.pop("rel", None)
                h["pos"] = T
                c["hand_" + s] = h
                poses[f] = pp.solve(c)
        worst = max(worst, float(np.linalg.norm(total, axis=1).max()))
        # then elbows: turn them out of the way, following on from the frame before
        prev = 0.0
        for f in range(n):
            got = _swivel(pp, skin, posed[f], controls[f], poses[f], tag, gap * 0.5, prev, brims[f] if brims else None)
            if got is None:
                prev *= 0.7
                continue
            prev, controls[f], poses[f] = got
            turn = max(turn, abs(prev))
    return worst, turn


def brim_points(pp, pose, hat_pos, pts):
    """The hat's brim points in a pose (armature space)."""
    off = pts + (np.array(hat_pos) - np.array(pp.H0["Head"]))
    return off @ np.array(pose["D"]["Head"]).T + np.array(pp.heads(pose)["Head"])


BENDS = [(0, 0, 0)] + [(y, p, r) for r in (0, 25, -25, 50, -50, 80, -80) for p in (0, 20, -20, 40, -40) for y in (0, 20, -20) if (y, p, r) != (0, 0, 0)]
BENDS.sort(key=lambda b: abs(b[0]) + abs(b[1]) + 0.6 * abs(b[2]))


def blades(pp, skin, posed, controls, poses, carried, blade_of, gap=0.02, brims=None):
    """Turn the wrist of a hand that carries a sword until the blade clears the fighter's own body
    (and hat). carried[f] = {tag: key}; blade_of(pose, tag, key) -> (m, 3) points along that blade.
    Changes controls and poses in place; returns the largest overlap left, in metres."""
    n = len(poses)
    left = 0.0
    for tag in ("Left", "Right"):
        s = tag[0]
        prev = (0, 0, 0)
        for f in range(n):
            key = carried[f].get(tag)
            if key is None:
                continue

            def lack(pose):
                B = blade_of(pose, tag, key)
                d, _, _ = posed[f].signed(B, "body")
                worst = float((gap - d).max())
                if brims is not None:
                    worst = max(worst, gap - float(np.linalg.norm(B[:, None, :] - brims[f][None, :, :], axis=2).min()))
                return worst

            base = dict(controls[f]["hand_" + s])
            if lack(poses[f]) <= 0.0 and prev == (0, 0, 0):
                continue
            best = None
            for b in sorted(BENDS, key=lambda q: abs(q[0] - prev[0]) + abs(q[1] - prev[1]) + 0.6 * abs(q[2] - prev[2])):
                c2 = dict(controls[f])
                c2["hand_" + s] = dict(base, bend=(base["bend"] @ ypr(*b)) if "bend" in base else ypr(*b))
                p2 = pp.solve(c2)
                lk = lack(p2)
                if best is None or lk < best[0] - 1e-4:
                    best = (lk, b, c2, p2)
                if lk <= 0.0:
                    break
            _, prev, controls[f], poses[f] = best
            left = max(left, best[0])
    return max(0.0, left)


# ----------------------------------------------------------------------------- scabbards
class Scabbard:
    """How one scabbard is carried: lying on the back between two points of the skin, or hanging
    from the belt. Set up once in the rest pose; frame(posed, ...) gives its place in a pose."""

    def __init__(self, skin, M0, arc, length, mode, radius=0.018, gap=0.017):
        self.skin, self.M0, self.arc, self.L, self.mode = skin, M0.copy(), arc, length, mode
        self.need = radius + gap                                   # how far the axis must stay from the skin
        self.s = np.linspace(0.02, length - 0.01, 14)
        R0, o0 = np.array(M0.to_3x3()), np.array(M0.translation)
        self.local = np.array([arc(s) for s in self.s])            # axis points in the scabbard's own space
        rest = self.local @ R0.T + o0
        tree_sel = np.flatnonzero(skin.region["trunk"] & ~skin.region["legs"])
        from scipy.spatial import cKDTree
        tree = cKDTree(skin.P0[tree_sel])
        dist, i = tree.query(rest)
        v = tree_sel[i]
        self.rest_gap = dist
        if mode == "back":
            on = np.flatnonzero(dist < 0.09)                       # where it still lies over the torso
            a, b = (on[0], on[-1]) if len(on) >= 2 else (0, len(self.s) // 2)
            if b - a < 3:
                b = min(len(self.s) - 1, a + 4)
            self.anchor = [(int(v[a]), rest[a] - skin.P0[v[a]], self.local[a]), (int(v[b]), rest[b] - skin.P0[v[b]], self.local[b])]
        else:
            a = 1                                                  # just below the mouth: where the belt holds it
            self.anchor = [(int(v[a]), rest[a] - skin.P0[v[a]], self.local[a])]
        self.prev = None

    def frame(self, posed, hips_D=None):
        """4x4 matrix of the scabbard (its own standard axes) for a posed skin, clear of the body."""
        R0 = self.M0.to_3x3()
        if self.mode == "back":
            (v0, o0, l0), (v1, o1, l1) = self.anchor
            A, B = posed.carry(v0, o0), posed.carry(v1, o1)
            for _ in range(10):
                Rot = self._between(posed, v0, A, B, l0, l1, R0)
                org = _vec(A) - Rot @ _vec(l0)
                pts = self.local @ np.array(Rot).T + np.array(org)
                d, nrm, _ = posed.signed(pts, "body")
                lack = self.need - d
                k = int(np.argmax(lack))
                if lack[k] <= 1e-4:
                    break
                t = float(np.clip((self.s[k] - self.s[0]) / max(1e-6, self.s[-1] - self.s[0]), 0.0, 1.0))
                # lift the two ends so that the point that is too close comes clear (smallest move that does it)
                den = (1 - t) ** 2 + t ** 2
                A = A + nrm[k] * lack[k] * (1 - t) / den
                B = B + nrm[k] * lack[k] * t / den
            Rot = self._between(posed, v0, A, B, l0, l1, R0)
            m = Rot.to_4x4()
            m.translation = _vec(A) - Rot @ _vec(l0)
            return m
        (v0, o0, l0), = self.anchor
        A = _vec(posed.carry(v0, o0))
        pref = hips_D @ R0                                          # as if it were fixed to the pelvis
        Rot = pref if self.prev is None else pref @ slerp(I3, self.prev, 0.86)     # it remembers where it was pushed and swings back slowly
        for _ in range(14):
            pts = (self.local - np.array(l0)) @ np.array(Rot).T + np.array(A)
            d, nrm, _ = posed.signed(pts, "body")
            lack = self.need - d
            lack[:2] = 0.0                                          # the mouth is held by the belt: only the free length is pushed
            k = int(np.argmax(lack))
            if lack[k] <= 1e-4:
                break
            r = _vec(pts[k]) - A
            to = r + _vec(nrm[k]) * float(lack[k])
            Rot = r.rotation_difference(to).to_matrix() @ Rot
        self.prev = pref.inverted() @ Rot
        m = Rot.to_4x4()
        m.translation = A - Rot @ _vec(l0)
        return m

    def _between(self, posed, v0, A, B, l0, l1, R0):
        ref = _rotation(posed.R[v0]) @ R0                           # turned as the skin under its upper end is turned
        c0 = ref @ (_vec(l1) - _vec(l0))
        c1 = _vec(B) - _vec(A)
        return c0.rotation_difference(c1).to_matrix() @ ref

    def clearance(self, posed, m):
        pts = self.local @ np.array(m.to_3x3()).T + np.array(m.translation)
        d, _, _ = posed.signed(pts, "body")
        return float(d.min()) - (self.need - 0.017)                 # distance from the scabbard's surface to the skin


# ----------------------------------------------------------------------------- the hat
def hat_points(radius, rise, n=28):
    """Points on the underside of the brim, in the hat's own space (origin on the axis at rim height)."""
    out = []
    for ring, z in ((1.0, 0.0), (0.8, rise * 0.2 ** 0.94), (0.6, rise * 0.4 ** 0.94)):
        for k in range(n):
            a = 2 * math.pi * k / n
            out.append((radius * ring * math.cos(a), radius * ring * math.sin(a), z - 0.004))
    return np.array(out)


def hat(pp, posed, poses, hat_pos, pts, grips=None, gap=0.012):
    """Take tilt off the head until the hat brim clears shoulders, arms and sword grips.
    poses are changed in place (neck and head only); posed[f] is the skin on that frame;
    grips[f] = list of (a, b, radius) segments. Returns the smallest share of the tilt that was
    kept (1 = nothing had to be changed)."""
    from .motion import foot_angles
    n = len(poses)
    keep = np.ones(n)
    rel = []
    off = pts + (np.array(hat_pos) - np.array(pp.H0["Head"]))        # brim points from the head joint, rest pose

    def clear(pose, Dhead, f):
        D = dict(pose["D"])
        D["Neck"] = slerp(D["Spine2"], Dhead, 0.45)
        D["Head"] = Dhead
        trial = dict(D=D, hips=pose["hips"], short={})
        head = np.array(pp.heads(trial)["Head"])
        P = off @ np.array(Dhead).T + head
        d, _, _ = posed[f].signed(P, "trunk")                         # the arms are kept off the hat by arms(), not the other way round
        lo = float(d.min())
        for a, b, r in (grips[f] if grips else ()):
            ab = b - a
            t = np.clip(((P - a) @ ab) / max(1e-12, float(ab @ ab)), 0.0, 1.0)
            lo = min(lo, float(np.linalg.norm(P - (a + t[:, None] * ab), axis=1).min()) - r)
        return lo

    for f in range(n):
        p = poses[f]
        Dc, Dh = p["D"]["Spine2"], p["D"]["Head"]
        yaw, pitch, roll = foot_angles(Dc.transposed() @ Dh)
        rel.append((yaw, pitch, roll))
        if clear(p, Dh, f) >= gap:
            continue
        lo, hi = 0.0, 1.0
        for _ in range(7):
            mid = 0.5 * (lo + hi)
            if clear(p, Dc @ ypr(yaw, pitch * mid, roll * mid), f) >= gap:
                lo = mid
            else:
                hi = mid
        keep[f] = lo
    if keep.min() < 1.0:
        soft = _smooth(np.minimum.reduce([np.roll(keep, k) for k in (-2, -1, 0, 1, 2)]), 5)   # ease in and out of the limit
        soft[:2], soft[-2:] = np.minimum(soft[:2], keep[:2]), np.minimum(soft[-2:], keep[-2:])
        keep = np.minimum(keep, soft)
        for f in range(n):
            if keep[f] < 1.0:
                yaw, pitch, roll = rel[f]
                Dc = poses[f]["D"]["Spine2"]
                Dh = Dc @ ypr(yaw, pitch * keep[f], roll * keep[f])
                poses[f]["D"]["Neck"] = slerp(Dc, Dh, 0.45)
                poses[f]["D"]["Head"] = Dh
    return float(keep.min())


# ----------------------------------------------------------------------------- hanging things
def pendulum(anchors, posed=None, length=0.11, bob=0.022, fps=24.0, sub=6, drag=0.035):
    """World matrices of something hanging from a moving point: a weight on a cord of the given
    length (to its centre of mass), swung by the point's motion, settling under gravity and
    stopped by the body (posed[f]: the skin on that frame, in the same space as the anchors).
    The object's own -Z is taken as 'down the cord'."""
    out = []
    p = anchors[0] + Vector((0, 0, -length))
    prev = p.copy()
    dt = 1.0 / (fps * sub)
    last = anchors[0]
    for f, a in enumerate(anchors):
        sk = posed[f] if posed is not None else None
        for k in range(sub):
            at = last.lerp(a, (k + 1) / sub)
            nxt = p + (p - prev) * (1.0 - drag) + Vector((0, 0, -9.81)) * dt * dt
            prev, p = p, nxt
            for _ in range(2):
                d = p - at
                p = at + d.normalized() * length if d.length > 1e-9 else at + Vector((0, 0, -length))
                if sk is None:
                    break
                dist, nrm, _ = sk.signed([p[:]], "body")
                if dist[0] >= bob:
                    break
                p = p + _vec(nrm[0]) * float(bob - dist[0])
                prev = prev.lerp(p, 0.5)                             # it loses speed where it touches
        last = a
        m = Vector((0, 0, -1)).rotation_difference((p - a).normalized()).to_matrix().to_4x4()
        m.translation = a
        out.append(m)
    return out


# ----------------------------------------------------------------------------- cloth
def depenetrate(X, posed, gap=0.004, region="all", reach=0.09):
    """Put cloth vertices that ended up inside the body (or closer to it than 'gap') back on its
    surface. X: (n, 3) positions in the skin's space, changed in place. Returns how many were moved
    and how deep the deepest one was."""
    d, nrm, _ = posed.signed(X, region)
    bad = (d < gap) & (d > -reach)
    if bad.any():
        X[bad] += nrm[bad] * (gap - d[bad])[:, None]
    return int(bad.sum()), float(-d[bad].min()) if bad.any() else 0.0


def out_of_capsules(X, segs, gap=0.003):
    """Push points out of capsules. segs: [(a, b, radius)]. Returns how many were moved."""
    moved = 0
    for a, b, r in segs:
        ab = b - a
        t = np.clip(((X - a) @ ab) / max(1e-12, float(ab @ ab)), 0.0, 1.0)
        c = a + t[:, None] * ab
        v = X - c
        dist = np.linalg.norm(v, axis=1)
        bad = dist < r + gap
        if bad.any():
            X[bad] = c[bad] + v[bad] / np.maximum(dist[bad], 1e-9)[:, None] * (r + gap)
            moved += int(bad.sum())
    return moved


def part_legs(X, rest, pose, pp, crotch=0.72, gap=0.010):
    """Keep the two legs of a pair of trousers on their own sides. Skinned to legs that pass close,
    the left leg's cloth ends up inside the right one; real cloth presses together and flattens.
    X: (n, 3) cage positions in the armature's space (changed in place); rest: the same vertices at
    rest. A vertex that belongs to the left leg may not cross the plane between the legs (the
    pelvis's own middle plane), nor a right one the other way. Returns how many were moved."""
    left = (rest[:, 0] > 0.02) & (rest[:, 2] < crotch)
    right = (rest[:, 0] < -0.02) & (rest[:, 2] < crotch)
    D = np.array(pose["D"]["Hips"])
    head = np.array(pose["hips"])
    h0 = np.array(pp.H0["Hips"])
    Xh = (X - head) @ D + h0                                          # as if the pelvis stood in the rest pose
    bad_l = left & (Xh[:, 0] < gap)
    bad_r = right & (Xh[:, 0] > -gap)
    Xh[bad_l, 0] = gap
    Xh[bad_r, 0] = -gap
    if bad_l.any() or bad_r.any():
        X[:] = (Xh - h0) @ D.T + head
    return int(bad_l.sum() + bad_r.sum())

