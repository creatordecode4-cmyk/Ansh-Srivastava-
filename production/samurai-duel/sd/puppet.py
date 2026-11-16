"""Posing a fighter from a handful of controls instead of 65 bone rotations.

A fight is choreographed in terms of where the feet stand, where the hips are, which way the
chest faces and where the sword is. This module turns such controls into a full skeleton pose:

  feet    placed in the world (ball of the foot, yaw, heel lift); the legs are solved to reach
          them, so a planted foot cannot slide
  swords  placed in the world (guard position, blade direction, edge direction); the hands are
          put on the grip and the arms solved to reach them, so blades meet where they are told to
  spine   hips and chest are given as world orientations, the bones between share the difference

Everything is worked out on world-space rotations 'D' that say how far a bone has turned from its
rest pose (bone now = D x bone at rest). Local bone rotations are derived at the end, and written
either straight onto the pose bones or in bulk into an action.

The fighters face -Y in the rest pose; +X is their left. Angles are in degrees:
  yaw    about +Z, positive turns to the fighter's left
  pitch  about +X, positive leans forward
  roll   about +Y, positive leans to the fighter's left
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from .rig import FINGERS, P

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
I3 = Matrix.Identity(3)


# ----------------------------------------------------------------------------- small maths
def rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, Vector(axis).normalized())


def ypr(yaw=0.0, pitch=0.0, roll=0.0):
    """Body orientation: roll and pitch in the body's own frame, then yaw about the vertical."""
    return rot(Z, yaw) @ rot(X, pitch) @ rot(Y, roll)


def slerp(A, B, t):
    return A.to_quaternion().slerp(B.to_quaternion(), t).to_matrix()


def perp(v, d):
    """Part of v at right angles to unit vector d, normalised (any perpendicular if v is along d)."""
    p = Vector(v) - d * Vector(v).dot(d)
    if p.length < 1e-6:
        p = d.orthogonal()
    return p.normalized()


def frame(d, f):
    """Right-handed frame with columns (d, f, d x f); d and f unit and perpendicular."""
    return Matrix((d, f, d.cross(f))).transposed()


def aim(a, b):
    """Smallest rotation taking direction a onto direction b."""
    return Vector(a).normalized().rotation_difference(Vector(b).normalized()).to_matrix()


def twist_angle(M, axis):
    """How far rotation M turns about 'axis' (degrees), the swing part left out."""
    q = M.to_quaternion()
    p = Vector((q.x, q.y, q.z)).dot(axis)
    a = 2.0 * math.atan2(p, q.w)
    return math.degrees((a + math.pi) % (2 * math.pi) - math.pi)


EASE = dict(
    linear=lambda u: u,
    inout=lambda u: u * u * (3 - 2 * u),
    slow_in=lambda u: u * u,                 # starts gently, arrives at speed
    slow_out=lambda u: 1 - (1 - u) ** 2,     # leaves at speed, settles
    wind=lambda u: u ** 3,
    snap=lambda u: 1 - (1 - u) ** 3,
    smoother=lambda u: u * u * u * (u * (6 * u - 15) + 10),     # like inout, but sets off and arrives without a kick in acceleration
)


def ease(kind, u):
    """Timing curve between two keys: a name from EASE or an exponent."""
    u = min(1.0, max(0.0, u))
    return EASE[kind](u) if isinstance(kind, str) else u ** kind


def two_bone(A, T, L1, L2, pole):
    """Mid joint of a two-bone limb rooted at A reaching for T, bulging toward 'pole'.
    Returns (mid joint, reached end point, hinge axis, shortfall in metres if T is out of reach)."""
    v = T - A
    dist = v.length
    n = v / dist if dist > 1e-9 else Vector((0, 0, -1))
    reach = min(max(dist, abs(L1 - L2) + 1e-4), L1 + L2 - 1e-5)
    b = perp(pole, n)
    ca = (L1 * L1 + reach * reach - L2 * L2) / (2 * L1 * reach)
    sa = math.sqrt(max(0.0, 1.0 - ca * ca))
    return A + n * (L1 * ca) + b * (L1 * sa), A + n * reach, n.cross(b), dist - reach


# ----------------------------------------------------------------------------- hand shapes
#            curl of the three joints (index .. little finger),               thumb: (opposition, flex 1, flex 2, flex 3)
SHAPES = dict(
    open=dict(curl=((0, 0, 0),) * 4, spread=0.0, thumb=(0, 0, 0, 0)),
    relaxed=dict(curl=((18, 26, 16), (22, 30, 18), (26, 34, 20), (30, 36, 22)), spread=0.0, thumb=(14, 8, 10, 12)),
    fist=dict(curl=((62, 78, 55),) * 4, spread=0.0, thumb=(38, 22, 30, 32)),
    grip=dict(curl=((54, 72, 44), (60, 76, 46), (64, 78, 48), (68, 80, 50)), spread=0.0, thumb=(46, 16, 26, 34)),
    blade=dict(curl=((4, 6, 4),) * 4, spread=-4.0, thumb=(20, 10, 8, 8)),          # flat hand, fingers together
)


def mix_shapes(a, b, t):
    """Blend between two hand shapes (names or dicts)."""
    a, b = (SHAPES[s] if isinstance(s, str) else s for s in (a, b))
    lerp = lambda u, v: u + (v - u) * t
    return dict(curl=tuple(tuple(lerp(x, y) for x, y in zip(fa, fb)) for fa, fb in zip(a["curl"], b["curl"])),
                spread=lerp(a["spread"], b["spread"]), thumb=tuple(lerp(x, y) for x, y in zip(a["thumb"], b["thumb"])))


# ----------------------------------------------------------------------------- the skeleton at rest
class Skeleton:
    """Rest-pose facts of one fighter's armature, and the way back from world rotations to bone channels."""

    def __init__(self, arm, hands):
        self.arm = arm
        bones = arm.data.bones
        self.names = [b.name[len(P):] for b in bones]                    # parents come before children
        self.parent = {b.name[len(P):]: (b.parent.name[len(P):] if b.parent else None) for b in bones}
        self.R0 = {b.name[len(P):]: b.matrix_local.to_3x3() for b in bones}
        self.H0 = {b.name[len(P):]: b.head_local.copy() for b in bones}
        self.dir0 = {n: (self.R0[n] @ Y).normalized() for n in self.names}
        self.children = {n: [c for c in self.names if self.parent[c] == n] for n in self.names}
        H = self.H0
        self.leg = {}
        self.arm_ = {}
        self.hand = {}
        for tag, side in (("Left", 1.0), ("Right", -1.0)):
            up, lo, ft, toe = tag + "UpLeg", tag + "Leg", tag + "Foot", tag + "ToeBase"
            self.leg[tag] = dict(L1=(H[lo] - H[up]).length, L2=(H[ft] - H[lo]).length,
                                 F0u=frame(self.dir0[up], perp(-Y, self.dir0[up])), F0l=frame(self.dir0[lo], perp(-Y, self.dir0[lo])),
                                 ankle_from_ball=H[ft] - H[toe], ball0=H[toe].copy())
            ua, fa, hd = tag + "Arm", tag + "ForeArm", tag + "Hand"
            self.arm_[tag] = dict(L1=(H[fa] - H[ua]).length, L2=(H[hd] - H[fa]).length,
                                  F0u=frame(self.dir0[ua], perp(Y, self.dir0[ua])), F0l=frame(self.dir0[fa], perp(Y, self.dir0[fa])))
            h = hands[tag]
            a, lat, n = Vector(h["a"]), Vector(h["lat"]), Vector(h["n"])
            self.hand[tag] = dict(a=a, lat=lat, n=n, W=Vector(h["W"]), Lh=h["Lh"], side=side, vc=0.5 * (h["v0"] + h["v1"]), bw=h["bw"])
        self.ball_h = 0.5 * (H["LeftToeBase"].z + H["RightToeBase"].z)       # height of the ball joint when the sole is on the ground
        self.hip_h = H["Hips"].z

    # ---- world rotations -> pose channels
    def channels(self, pose):
        """{bone: local quaternion} and the hips' pose-bone location for a solved pose."""
        D = pose["D"]
        out = {}
        for n in self.names:
            d = D.get(n)
            p = self.parent[n]
            dp = D.get(p, I3) if p else I3
            if d is None:
                d = D[n] = dp
            R0 = self.R0[n]
            out[n] = (R0.transposed() @ dp.transposed() @ d @ R0).to_quaternion()
        loc = self.R0["Hips"].transposed() @ (pose["hips"] - self.H0["Hips"])
        return out, loc

    def apply(self, pose):
        """Put a solved pose on the armature now (no keyframes)."""
        q, loc = self.channels(pose)
        for n, v in q.items():
            pb = self.arm.pose.bones[P + n]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = v
        self.arm.pose.bones[P + "Hips"].location = loc
        bpy.context.view_layer.update()

    def heads(self, pose):
        """World position of every joint for a solved pose."""
        D = pose["D"]
        out = {"Hips": pose["hips"].copy()}
        for n in self.names[1:]:
            p = self.parent[n]
            out[n] = out[p] + D.get(p, I3) @ (self.H0[n] - self.H0[p])
        return out

    def bone_matrix(self, pose, name, heads=None):
        """4x4 world matrix of a bone in a solved pose (what a bone-parented object would follow)."""
        heads = heads or self.heads(pose)
        m = (pose["D"].get(name, I3) @ self.R0[name]).to_4x4()
        m.translation = heads[name]
        return m

    def write(self, name, frames, poses):
        """Action holding the given poses at the given frame numbers (one key per frame, all bones)."""
        act = bpy.data.actions.new(name)
        slot = act.slots.new(id_type="OBJECT", name=self.arm.name)
        strip = act.layers.new("Layer").strips.new(type="KEYFRAME")
        bag = strip.channelbag(slot, ensure=True)
        chan = [self.channels(p) for p in poses]
        ft = [float(f) for f in frames]
        n = len(ft)

        def curve(path, index, values, group):
            fc = bag.fcurves.new(path, index=index, group_name=group)
            fc.keyframe_points.add(n)
            flat = [0.0] * (2 * n)
            flat[0::2] = ft
            flat[1::2] = values
            fc.keyframe_points.foreach_set("co", flat)
            fc.update()

        for b in self.names:
            qs = [c[0][b] for c in chan]
            for k in range(1, n):                              # keep to one side of the double cover: no flips between frames
                if qs[k - 1].dot(qs[k]) < 0.0:
                    qs[k].negate()
            if all(abs(q.w - 1.0) < 1e-7 for q in qs) and b != "Hips":
                continue                                       # never moves: leave the channel out
            path = f'pose.bones["{P + b}"].rotation_quaternion'
            for i in range(4):
                curve(path, i, [q[i] for q in qs], P + b)
        for i in range(3):
            curve(f'pose.bones["{P}Hips"].location', i, [c[1][i] for c in chan], P + "Hips")
        for pb in self.arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
        act.use_fake_user = True
        return act, slot

    def play(self, act, slot):
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = act
        ad.action_slot = slot


# ----------------------------------------------------------------------------- the solver
class Puppet(Skeleton):
    """Controls -> pose.

    canon() accepts the friendly forms below and returns the plain form the rest of the pipeline
    works on (vectors and 3x3 rotations only, so that two sets of controls can be blended):

    hips        (x, y, z) world position of the hip joint
    hips_rot    (yaw, pitch, roll) of the pelvis                     -> hips_D
    chest_rot   (yaw, pitch, roll) of the rib cage, in the world     -> chest_D   (default: as the pelvis)
    head_rot    (yaw, pitch, roll) of the head, in the world, or
    head_look   a point to look at                                   -> head_D    (default: as the chest)
    foot_L/R    dict(pos=(x, y, z) of the ball of the foot (z = 0 on the ground), yaw, pitch (heel lift),
                roll, toe)                                           -> dict(pos, D, toe)
    knee_L/R    world direction the knee points to (default: along the foot, a little toward the hips' front)
    hand_L/R    dict(pos=wrist position in the world, or rel=wrist position from the shoulder in the
                chest's frame; D=hand rotation from rest, or bend=(yaw, pitch, roll) of the wrist)
                default: the arm hangs at the side
    elbow_L/R   world direction the elbow points to
    fingers_L/R hand shape: a name from SHAPES or a dict
    """

    def canon(self, c):
        o = dict(hips=Vector(c["hips"]))
        o["hips_D"] = c["hips_D"] if "hips_D" in c else ypr(*c.get("hips_rot", (0, 0, 0)))
        o["chest_D"] = c["chest_D"] if "chest_D" in c else (ypr(*c["chest_rot"]) if "chest_rot" in c else o["hips_D"])
        if "head_D" in c:
            o["head_D"] = c["head_D"]
        elif "head_look" in c:
            Dh, Dc = o["hips_D"], o["chest_D"]
            H = self.H0
            eye = (o["hips"] + Dh @ (H["Spine"] - H["Hips"]) + slerp(Dh, Dc, 0.3) @ (H["Spine1"] - H["Spine"]) + slerp(Dh, Dc, 0.65) @ (H["Spine2"] - H["Spine1"])
                   + Dc @ (H["Head"] - H["Spine2"]) + Dc @ Vector((0, -0.05, 0.10)))
            to = Vector(c["head_look"]) - eye
            o["head_D"] = ypr(math.degrees(math.atan2(to.x, -to.y)), -math.degrees(math.atan2(to.z, math.hypot(to.x, to.y))), c.get("head_tilt", 0.0))
        else:
            o["head_D"] = ypr(*c["head_rot"]) if "head_rot" in c else o["chest_D"]
        for tag, s in (("Left", "L"), ("Right", "R")):
            L = self.leg[tag]
            f = c.get("foot_" + s) or dict(pos=(L["ball0"].x, L["ball0"].y, 0.0))
            D = f["D"] if "D" in f else ypr(f.get("yaw", 0.0), f.get("pitch", 0.0), f.get("roll", 0.0))
            o["foot_" + s] = dict(pos=Vector(f["pos"]), D=D, toe=f.get("toe"))
            if c.get("knee_" + s) is not None:
                o["knee_" + s] = Vector(c["knee_" + s]).normalized()
            h = dict(c.get("hand_" + s) or {})
            side = self.hand[tag]["side"]
            if "pos" in h:
                h["pos"] = Vector(h["pos"])
            else:
                h["rel"] = Vector(h.get("rel", (side * 0.10, -0.07, -0.49)))
            if "bend" in h and not isinstance(h["bend"], Matrix):
                h["bend"] = ypr(*h["bend"])
            o["hand_" + s] = h
            if c.get("elbow_" + s) is not None:
                o["elbow_" + s] = Vector(c["elbow_" + s]).normalized()
            fg = c.get("fingers_" + s, "relaxed")
            o["fingers_" + s] = SHAPES[fg] if isinstance(fg, str) else fg
        for k, v in c.items():                                       # anything else (prop tracks, notes) rides along
            if k not in o and not k.endswith("_rot") and k not in ("head_look", "head_tilt"):
                o[k] = v
        return o

    def solve(self, c):
        """Pose for one set of controls (friendly or plain form)."""
        if "hips_D" not in c or "fingers_L" not in c or not isinstance(c.get("foot_L", {}).get("D"), Matrix):
            c = self.canon(c)
        D = {}
        short = {}
        hips = Vector(c["hips"])
        Dh, Dc, Dhead = c["hips_D"], c["chest_D"], c["head_D"]
        D["Hips"] = Dh
        D["Spine"] = slerp(Dh, Dc, 0.3)
        D["Spine1"] = slerp(Dh, Dc, 0.65)
        D["Spine2"] = Dc
        D["Neck"] = slerp(Dc, Dhead, 0.45)
        D["Head"] = Dhead
        pose = dict(D=D, hips=hips, short=short)
        H = self.heads(pose)                                             # joints down to the shoulders and hip sockets are final now
        # --- legs
        for tag, s in (("Left", "L"), ("Right", "R")):
            L = self.leg[tag]
            f = c["foot_" + s]
            Df = f["D"]
            ball = f["pos"] + Vector((0, 0, self.ball_h))
            ankle = ball + Df @ L["ankle_from_ball"]
            A = H[tag + "UpLeg"]
            pole = c.get("knee_" + s)
            if pole is None:
                pole = (Df @ -Y) * 0.65 + (Dh @ -Y) * 0.35
            M, Te, h, lack = two_bone(A, ankle, L["L1"], L["L2"], pole)
            d1, d2 = (M - A).normalized(), (Te - M).normalized()
            D[tag + "UpLeg"] = frame(d1, h.cross(d1)) @ L["F0u"].transposed()
            D[tag + "Leg"] = frame(d2, h.cross(d2)) @ L["F0l"].transposed()
            D[tag + "Foot"] = Df
            toe = f.get("toe")
            if toe is None:                                              # toes stay flat on the ground while the heel lifts
                pitch = math.degrees(math.asin(max(-1.0, min(1.0, -(Df @ -Y).z))))
                toe = max(0.0, pitch) * max(0.0, 1.0 - f["pos"].z / 0.04)
            D[tag + "ToeBase"] = Df @ rot(X, -toe)
            if lack > 1e-4:
                short[tag + "Foot"] = lack
        # --- arms
        for tag, s in (("Left", "L"), ("Right", "R")):
            A_ = self.arm_[tag]
            side = self.hand[tag]["side"]
            ctl = c["hand_" + s]
            sh, ua, fa, hn = tag + "Shoulder", tag + "Arm", tag + "ForeArm", tag + "Hand"
            A0 = H[sh] + Dc @ (self.H0[ua] - self.H0[sh])                 # shoulder joint before the collar bone moves
            T = ctl["pos"] if "pos" in ctl else A0 + Dc @ ctl["rel"]
            # the collar bone follows the upper arm's direction by a fixed share (as the shoulder girdle does),
            # so it moves steadily with the arm instead of twitching as the elbow bends and stretches
            c0 = Dc @ self.dir0[sh]
            to = (T - H[sh]).normalized()
            up = Dc @ Z
            rise = math.asin(max(-1.0, min(1.0, to.dot(up))))                # arm above (+) or below (-) the shoulder line
            fore = math.asin(max(-1.0, min(1.0, to.dot(Dc @ -Y))))           # arm in front (+) or behind (-)
            lift = max(math.radians(-10.0), min(math.radians(24.0), rise * (0.30 if rise > 0 else 0.12)))
            reach = max(math.radians(-8.0), min(math.radians(14.0), fore * 0.16))
            axis_lift = c0.cross(up)
            axis_fore = c0.cross(Dc @ -Y)
            Dsh = Dc
            if axis_lift.length > 1e-6:
                Dsh = Matrix.Rotation(lift, 3, axis_lift.normalized()) @ Dsh
            if axis_fore.length > 1e-6:
                Dsh = Matrix.Rotation(reach, 3, axis_fore.normalized()) @ Dsh
            D[sh] = Dsh
            A = H[sh] + Dsh @ (self.H0[ua] - self.H0[sh])
            pole = c.get("elbow_" + s)
            if pole is None:
                pole = Dc @ Vector((side * 0.55, 0.45, -0.7))
            M, Te, h, lack = two_bone(A, T, A_["L1"], A_["L2"], pole)
            d1, d2 = (M - A).normalized(), (Te - M).normalized()
            D[ua] = frame(d1, h.cross(d1)) @ A_["F0u"].transposed()
            Dfa = frame(d2, h.cross(d2)) @ A_["F0l"].transposed()
            if ctl.get("D") is not None:
                Dhand = ctl["D"]
            else:                                                        # wrist as at rest, plus an optional bend given in the forearm's frame
                Dhand = Dfa @ ctl["bend"] if "bend" in ctl else Dfa
            tw = twist_angle(Dfa.transposed() @ Dhand, self.dir0[fa])     # the forearm takes half of the hand's roll
            D[fa] = Dfa @ rot(self.dir0[fa], 0.5 * tw)
            D[hn] = Dhand
            if lack > 1e-4:
                short[hn] = lack
            self._fingers(D, tag, c["fingers_" + s])
        return pose

    def _fingers(self, D, tag, shape):
        S = SHAPES[shape] if isinstance(shape, str) else shape
        hd = self.hand[tag]
        side, a, lat, n = hd["side"], hd["a"], hd["lat"], hd["n"]
        Dh = D[tag + "Hand"]
        for i, fn in enumerate(("Index", "Middle", "Ring", "Pinky")):
            Dp = Dh @ rot(n, side * S["spread"] * (i - 1.5))
            for k in (1, 2, 3):
                b = f"{tag}Hand{fn}{k}"
                Dp = Dp @ rot(perp(lat, self.dir0[b]) * side, S["curl"][i][k - 1])
                D[b] = Dp
        opp, f1, f2, f3 = S["thumb"]
        Dp = Dh @ rot(a * side, opp) @ rot(n * side, f1)
        D[tag + "HandThumb1"] = Dp
        for k, f in ((2, f2), (3, f3)):
            Dp = Dp @ rot(n * side, f)
            D[f"{tag}HandThumb{k}"] = Dp

    # ---- swords
    GRIP = dict(tilt=18.0, depth=0.030, up=0.37)     # how a handle lies in the closed fist: diagonal across the palm,
    #                                                  this far in front of the palm bones and this far up the hand

    def _grip_frame(self, tag):
        hd = self.hand[tag]
        a, lat, n = hd["a"], hd["lat"], hd["n"]
        t = math.radians(self.GRIP["tilt"])
        e_blade = (-lat * math.cos(t) + a * math.sin(t)).normalized()      # the blade leaves the fist on the thumb side
        e_edge = (a * math.cos(t) + lat * math.sin(t)).normalized()        # the edge leads with the knuckles
        g0 = a * (self.GRIP["up"] * hd["Lh"]) + lat * hd["vc"] - n * self.GRIP["depth"]   # centre of the closed fist, from the wrist, at rest
        return e_blade, e_edge, g0

    def grip(self, tag, S, at, along=0.0, roll=0.0, flip=False):
        """Where the wrist must be, and how the hand is turned, to hold a sword.

        S      3x3 world rotation of the sword where the fist sits (columns: flat, toward the point, back of the blade)
        at     world position of the handle's axis there (minus 'along' metres toward the pommel)
        roll   turn of the hand round the handle, degrees (0: knuckles in line with the edge)
        flip   thumb toward the pommel instead of the point (a hand resting on the scabbard, a reverse grip)
        Returns (wrist position, hand rotation D)."""
        e_blade, e_edge, g0 = self._grip_frame(tag)
        Ys = (S @ Y).normalized()
        Yh = -Ys if flip else Ys
        E = rot(Yh, roll) @ (S @ -Z)
        Dhand = frame(Yh, perp(E, Yh)) @ frame(e_blade, e_edge).transposed()
        G = Vector(at) - Ys * along
        return G - Dhand @ g0, Dhand

    def ungrip(self, tag, wrist, Dhand, roll=0.0, flip=False):
        """Inverse of grip(): the handle's axis position and the sword's 3x3 rotation in a closed hand."""
        e_blade, e_edge, g0 = self._grip_frame(tag)
        Yh = (Dhand @ e_blade).normalized()
        E = rot(Yh, -roll) @ (Dhand @ e_edge)
        Ys = -Yh if flip else Yh
        Zs = -perp(E, Ys)
        return wrist + Dhand @ g0, Matrix((Ys.cross(Zs), Ys, Zs)).transposed()


def sword_matrix(guard, point_dir, edge_dir):
    """4x4 world matrix of a katana: origin at the guard, +Y to the point, -Z the cutting edge."""
    y = Vector(point_dir).normalized()
    z = -perp(edge_dir, y)
    m = Matrix((y.cross(z), y, z)).transposed().to_4x4()
    m.translation = Vector(guard)
    return m
