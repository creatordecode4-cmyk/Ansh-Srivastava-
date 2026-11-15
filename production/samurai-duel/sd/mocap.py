"""Motion-capture clips as controls for the puppet (sd/puppet.py).

The clips are the DeepMimic reference motions (tools/fetch_mocap.py): a simple 13-joint humanoid
with arms and legs hanging straight down at rest. A clip is not copied bone by bone. It is read
as what the performer did - where the hips were, which way the pelvis, chest and head were
turned, where each foot and hand was - and those become controls, scaled to the fighter's own leg
and arm length. The puppet then solves the fighter's skeleton, so the same clip fits both
fighters although their proportions differ, and stance width, hip height or lean can be changed
before solving.

Clip axes are x forward, y up, z to the performer's right; ours are -y forward, z up, x left.
"""
import json
import math
import os

from mathutils import Matrix, Quaternion, Vector

from . import core

DIR = os.path.join(core.ASSETS, "mocap", "deepmimic")
M = Matrix(((0, 0, -1), (-1, 0, 0), (0, 1, 0)))        # clip axes -> ours
MT = M.transposed()
# joint offsets of the clip's skeleton in metres (its description file is stored at 4x scale)
OFF = {k: Vector(v) for k, v in dict(
    chest=(0, 0.236151, 0), neck=(0, 0.223894, 0), hip=(0, 0, 0.084887), knee=(0, -0.421546, 0), ankle=(0, -0.409870, 0),
    shoulder=(-0.024050, 0.243500, 0.183110), elbow=(0, -0.274788, 0), wrist=(0, -0.258947, 0)).items()}
LEG = 0.421546 + 0.409870
ARM = 0.274788 + 0.258947
SOLE = 0.05                                            # ankle joint above the ground with the foot flat


def _q(v):
    return Quaternion((v[0], v[1], v[2], v[3]))        # stored as w, x, y, z


def _rz(a):
    return Matrix.Rotation(a, 3, "Z")


class Clip:
    """One clip. pose(t) gives joint positions and rotations at time t (seconds) in our axes,
    at the performer's own size. Looping clips keep travelling (and turning) cycle after cycle."""

    def __init__(self, name):
        path = name if os.path.exists(name) else os.path.join(DIR, f"humanoid3d_{name}.txt")
        with open(path) as fh:
            d = json.load(fh)
        self.name = os.path.basename(path).replace("humanoid3d_", "").replace(".txt", "")
        self.F = d["Frames"]
        self.loop = d.get("Loop") == "wrap"
        self.t = [0.0]
        for fr in self.F[:-1]:
            self.t.append(self.t[-1] + fr[0])
        self.T = self.t[-1]
        a, b = self._parts(self.F[0]), self._parts(self.F[-1])
        ya, yb = self._heading(a["root_q"]), self._heading(b["root_q"])
        turn = (yb - ya + math.pi) % (2 * math.pi) - math.pi
        self.turn = turn if abs(turn) > math.radians(20.0) else 0.0       # per cycle, about the vertical; a few degrees is capture noise
        Rg = Matrix.Rotation(self.turn, 3, "Y")
        self.step = b["root_p"] - Rg @ a["root_p"]
        self.step.y = 0.0
        # a looping clip rarely ends exactly as it began: what is left over is taken out evenly along the cycle
        self.seam = {}
        if self.loop:
            for key, va in a.items():
                vb = b[key]
                if key == "root_p":
                    self.seam[key] = Vector((0.0, vb.y - va.y, 0.0))
                elif key == "root_q":
                    self.seam[key] = (Rg.to_quaternion() @ va) @ vb.inverted()        # what turns the last frame into the first, one cycle on
                elif isinstance(va, Quaternion):
                    self.seam[key] = va @ vb.inverted()
                else:
                    self.seam[key] = va - vb

    @staticmethod
    def _heading(q):
        f = q.to_matrix() @ Vector((1, 0, 0))
        return math.atan2(-f.z, f.x)

    @staticmethod
    def _parts(fr):
        return dict(root_p=Vector(fr[1:4]), root_q=_q(fr[4:8]), chest=_q(fr[8:12]), neck=_q(fr[12:16]),
                    r_hip=_q(fr[16:20]), r_knee=fr[20], r_ankle=_q(fr[21:25]), r_shoulder=_q(fr[25:29]), r_elbow=fr[29],
                    l_hip=_q(fr[30:34]), l_knee=fr[34], l_ankle=_q(fr[35:39]), l_shoulder=_q(fr[39:43]), l_elbow=fr[43])

    def _raw(self, t):
        """Interpolated frame at time t, with the cycle count for looping clips."""
        cyc = 0
        if self.loop:
            cyc = math.floor(t / self.T)
            t -= cyc * self.T
        t = min(max(t, 0.0), self.T)
        k = max(0, min(len(self.t) - 2, next((i for i in range(len(self.t) - 1) if self.t[i + 1] >= t), len(self.t) - 2)))
        u = (t - self.t[k]) / max(1e-9, self.t[k + 1] - self.t[k])
        a, b = self._parts(self.F[k]), self._parts(self.F[k + 1])
        o = {}
        for key, va in a.items():
            vb = b[key]
            if isinstance(va, Quaternion):
                o[key] = va.slerp(vb, u)
            elif isinstance(va, Vector):
                o[key] = va.lerp(vb, u)
            else:
                o[key] = va + (vb - va) * u
        if self.seam:
            ph = t / self.T
            for key, d in self.seam.items():
                if key == "root_p":
                    o[key] = o[key] - d * ph
                elif isinstance(d, Quaternion):
                    o[key] = Quaternion().slerp(d, ph) @ o[key]
                else:
                    o[key] = o[key] + d * ph
        return o, cyc

    def pose(self, t):
        r, cyc = self._raw(t)
        Rr = r["root_q"].to_matrix()
        p = r["root_p"].copy()
        for _ in range(abs(cyc)):                                         # carry the root through the cycles already walked
            if cyc > 0:
                G = Matrix.Rotation(self.turn, 3, "Y")
                p = G @ p + self.step
                Rr = G @ Rr
            else:
                G = Matrix.Rotation(-self.turn, 3, "Y")
                p = G @ (p - self.step)
                Rr = G @ Rr
        Rc = Rr @ r["chest"].to_matrix()
        Rn = Rc @ r["neck"].to_matrix()
        pc = p + Rr @ OFF["chest"]
        out = dict(root_p=M @ p, root=M @ Rr @ MT, chest=M @ Rc @ MT, head=M @ Rn @ MT)
        for tag, s, sg in (("Right", "r", 1.0), ("Left", "l", -1.0)):
            Rh = Rr @ r[s + "_hip"].to_matrix()
            Rk = Rh @ _rz(r[s + "_knee"])
            Ra = Rk @ r[s + "_ankle"].to_matrix()
            ph = p + Rr @ Vector((0, 0, sg * OFF["hip"].z))
            pk = ph + Rh @ OFF["knee"]
            pa = pk + Rk @ OFF["ankle"]
            Rs = Rc @ r[s + "_shoulder"].to_matrix()
            Re = Rs @ _rz(r[s + "_elbow"])
            ps = pc + Rc @ Vector((OFF["shoulder"].x, OFF["shoulder"].y, sg * OFF["shoulder"].z))
            pe = ps + Rs @ OFF["elbow"]
            pw = pe + Re @ OFF["wrist"]
            out[tag] = dict(hip=M @ ph, knee=M @ pk, ankle=M @ pa, foot=M @ Ra @ MT, shoulder=M @ ps, elbow=M @ pe, wrist=M @ pw)
        return out


def controls(pp, P, ground=SOLE, widen=0.0):
    """Puppet controls (plain form) for clip pose P, fitted to the fighter behind puppet pp.

    ground  height of the clip's ankle joint when its foot is flat on the floor
    widen   extra distance of each foot from the body's centre line, metres"""
    from .puppet import perp
    k = (pp.leg["Left"]["L1"] + pp.leg["Left"]["L2"]) / LEG
    ka = (pp.arm_["Left"]["L1"] + pp.arm_["Left"]["L2"]) / ARM
    ank0 = 0.5 * (pp.H0["LeftFoot"].z + pp.H0["RightFoot"].z)

    def place(p):
        return Vector((p.x * k, p.y * k, (p.z - ground) * k + ank0))

    Dh, Dc = P["root"], P["chest"]
    H = pp.H0
    mid0 = 0.5 * (H["LeftUpLeg"] + H["RightUpLeg"]) - H["Hips"]
    c = dict(hips=place(P["root_p"]) - Dh @ mid0, hips_D=Dh, chest_D=Dc, head_D=P["head"])
    fwd = Dh @ Vector((0, -1, 0))
    lat = Vector((-fwd.y, fwd.x, 0.0)).normalized()                      # the performer's left on the ground
    for tag, s, side in (("Left", "L", 1.0), ("Right", "R", -1.0)):
        J = P[tag]
        L = pp.leg[tag]
        Df = J["foot"]
        ball = place(J["ankle"]) - Df @ L["ankle_from_ball"] + lat * (side * widen)
        c["foot_" + s] = dict(pos=ball - Vector((0, 0, pp.ball_h)), D=Df, toe=None)
        n = (J["ankle"] - J["hip"]).normalized()
        kv = J["knee"] - J["hip"]
        kv -= n * kv.dot(n)
        dflt = (Df @ Vector((0, -1, 0))) * 0.65 + fwd * 0.35
        w = min(1.0, kv.length / 0.06)                                    # a straight leg has no knee direction of its own
        c["knee_" + s] = (kv.normalized() * w + dflt.normalized() * (1.0 - w)).normalized() if kv.length > 1e-6 else dflt.normalized()
        rel = Dc.transposed() @ (J["wrist"] - J["shoulder"]) * ka
        c["hand_" + s] = dict(rel=rel)
        n = (J["wrist"] - J["shoulder"]).normalized()
        ev = J["elbow"] - J["shoulder"]
        ev -= n * ev.dot(n)
        if ev.length > 0.03:
            c["elbow_" + s] = ev.normalized()
    return pp.canon(c)
