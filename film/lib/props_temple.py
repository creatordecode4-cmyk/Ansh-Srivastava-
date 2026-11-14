"""Japanese temple buildings, built procedurally with bmesh (no textures, no UVs).

Public builders (all return ONE mesh object, origin on the ground at the footprint centre, front = -Y):

    build_hall(width=16.0, depth=11.0, plinth=1.2, front_steps_width=6.0, name="PROP_TempleMain", seed=0)
    build_hall_small(width=8.0, depth=7.0, plinth=0.6, name="PROP_HallSmall", seed=0)
    build_corridor(length=24.0, depth=5.0, plinth=0.6, name="PROP_Corridor", seed=0)
    build_pagoda(tiers=3, name="PROP_Pagoda", seed=0)
    build_perimeter_wall(length=10.0, height=2.4, name="PROP_Wall", seed=0)

`width` x `depth` is the stone plinth at ground level. The front staircase sticks out in front of it (-Y) and the
roof overhangs it; the real extents are stored on the object (see below).

Custom properties written on every building:
    obj["size"]            [width, depth, total_height]              nominal footprint and real height
    obj["lantern_sockets"] [[x, y, z], ...]  local points on the underside of the front eave rafters (hang point)
    obj["lantern_drop"]    suggested cord length (m) from a socket down to the top of a paper lantern
    obj["door_point"]      [x, y, z]  local point on the floor in front of the main door (centre front for others)
    obj["floor_z"]         height of the walkable floor
    obj["eave_half"]       [ex, ey]  half extents of the roof edge in plan
    obj["eave_z"]          height of the roof edge at mid span
    obj["bbox_min"], obj["bbox_max"]   real local bounds (stairs and roof included)

Materials used (by name through materials.get): MAT_Roof_Tile, MAT_Wood_Red, MAT_Wood_Dark, MAT_Plaster,
MAT_Stone_Block, MAT_Stone_Mossy, MAT_Window_Glow, MAT_Metal_Dark, MAT_Gold.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from . import common, materials

TILE = "MAT_Roof_Tile"
RED = "MAT_Wood_Red"
DARK = "MAT_Wood_Dark"
PLASTER = "MAT_Plaster"
STONE = "MAT_Stone_Block"
MOSSY = "MAT_Stone_Mossy"
GLOW = "MAT_Window_Glow"
METAL = "MAT_Metal_Dark"
GOLD = "MAT_Gold"

_Z = Vector((0.0, 0.0, 1.0))


# ----------------------------------------------------------------------------------------------------------------
# geometry accumulator
# ----------------------------------------------------------------------------------------------------------------
def _newell(pts):
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % n]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _area2(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s


def _box_pts(a, b, c, e):
    out = []
    for sz in (-1, 1):
        for sy in (-1, 1):
            for sx in (-1, 1):
                out.append((sx * a, sy * (b - e), sz * (c - e)))
                out.append((sx * (a - e), sy * b, sz * (c - e)))
                out.append((sx * (a - e), sy * (b - e), sz * c))
    return out


_BOX_FACES = None
_PLAIN_FACES = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))


def _box_faces():
    """Face list of a chamfered box (24 vertices, 26 faces), wound outward. Computed once."""
    global _BOX_FACES
    if _BOX_FACES is None:
        def vid(sx, sy, sz, ax):
            return 3 * ((sx > 0) + 2 * (sy > 0) + 4 * (sz > 0)) + ax
        faces = []
        sg = (-1, 1)
        for s in sg:
            faces.append([vid(s, -1, -1, 0), vid(s, 1, -1, 0), vid(s, 1, 1, 0), vid(s, -1, 1, 0)])
            faces.append([vid(-1, s, -1, 1), vid(1, s, -1, 1), vid(1, s, 1, 1), vid(-1, s, 1, 1)])
            faces.append([vid(-1, -1, s, 2), vid(1, -1, s, 2), vid(1, 1, s, 2), vid(-1, 1, s, 2)])
        for s1 in sg:
            for s2 in sg:
                faces.append([vid(s1, s2, -1, 0), vid(s1, s2, -1, 1), vid(s1, s2, 1, 1), vid(s1, s2, 1, 0)])
                faces.append([vid(s1, -1, s2, 0), vid(s1, -1, s2, 2), vid(s1, 1, s2, 2), vid(s1, 1, s2, 0)])
                faces.append([vid(-1, s1, s2, 1), vid(-1, s1, s2, 2), vid(1, s1, s2, 2), vid(1, s1, s2, 1)])
        for sx in sg:
            for sy in sg:
                for sz in sg:
                    faces.append([vid(sx, sy, sz, 0), vid(sx, sy, sz, 1), vid(sx, sy, sz, 2)])
        pts = _box_pts(1.0, 1.0, 1.0, 0.2)
        out = []
        for f in faces:
            ps = [pts[i] for i in f]
            n = _newell(ps)
            cx = sum(p[0] for p in ps)
            cy = sum(p[1] for p in ps)
            cz = sum(p[2] for p in ps)
            if n[0] * cx + n[1] * cy + n[2] * cz < 0:
                f = f[::-1]
            out.append(tuple(f))
        _BOX_FACES = out
    return _BOX_FACES


class _B:
    """Collects vertices and faces in plain lists; `finish` turns them into one mesh object through bmesh."""

    def __init__(self, seed):
        self.vs = []
        self.fs = []
        self.fm = []
        self.slots = {}
        self.names = []
        self.rnd = common.rng(seed)

    # -- basics
    def mat(self, name):
        i = self.slots.get(name)
        if i is None:
            i = self.slots[name] = len(self.names)
            self.names.append(name)
        return i

    def v(self, p):
        self.vs.append((p[0], p[1], p[2]))
        return len(self.vs) - 1

    def face(self, idx, mat, hint=None):
        if hint is not None:
            n = _newell([self.vs[i] for i in idx])
            if n[0] * hint[0] + n[1] * hint[1] + n[2] * hint[2] < 0:
                idx = idx[::-1]
        self.fs.append(tuple(idx))
        self.fm.append(self.mat(mat))

    def quad(self, p0, p1, p2, p3, mat, hint):
        self.face([self.v(p0), self.v(p1), self.v(p2), self.v(p3)], mat, hint)

    def jit(self, amount):
        return self.rnd.uniform(-amount, amount)

    # -- primitives
    def box(self, c, size, mat, bevel=0.0, rot=None):
        """Box centred on c. bevel > 0 chamfers all 12 edges. rot: optional 3x3 rotation Matrix."""
        a, b, h = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        base = len(self.vs)
        if bevel > 0.0:
            e = min(bevel, 0.4 * min(a, b, h))
            pts = _box_pts(a, b, h, e)
            faces = _box_faces()
        else:
            pts = [(sx * a, sy * b, sz * h) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
            faces = _PLAIN_FACES
        cx, cy, cz = c
        if rot is None:
            self.vs.extend((cx + p[0], cy + p[1], cz + p[2]) for p in pts)
        else:
            for p in pts:
                q = rot @ Vector(p)
                self.vs.append((cx + q.x, cy + q.y, cz + q.z))
        m = self.mat(mat)
        for f in faces:
            self.fs.append(tuple(base + i for i in f))
            self.fm.append(m)

    def box2(self, lo, hi, mat, bevel=0.0):
        c = ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, (lo[2] + hi[2]) * 0.5)
        self.box(c, (abs(hi[0] - lo[0]), abs(hi[1] - lo[1]), abs(hi[2] - lo[2])), mat, bevel)

    def beam(self, p0, p1, w, h, mat, bevel=0.0, anchor="center", up=_Z):
        """Rectangular beam from p0 to p1 (w across, h in the 'up' plane). anchor: 'top' = the points lie on its top."""
        p0, p1 = Vector(p0), Vector(p1)
        y = p1 - p0
        length = y.length
        if length < 1e-6:
            return
        y.normalize()
        x = y.cross(Vector(up))
        if x.length < 1e-6:
            x = Vector((1.0, 0.0, 0.0))
        x.normalize()
        z = x.cross(y)
        rot = Matrix((x, y, z)).transposed()
        c = (p0 + p1) * 0.5
        if anchor == "top":
            c = c - z * (h * 0.5)
        elif anchor == "bottom":
            c = c + z * (h * 0.5)
        self.box(c, (w, length, h), mat, bevel, rot)

    def lathe(self, c, prof, n, mat, rot=None, phase=0.0):
        """Surface of revolution about the vertical through c. prof: [(r, z)] bottom -> top (r = 0 closes).

        mat may be one name or a list with one name per profile segment."""
        cx, cy, cz = c
        rings = []
        for r, z in prof:
            if r <= 1e-6:
                pts = [(0.0, 0.0, z)]
            else:
                pts = [(r * math.cos(phase + 2 * math.pi * k / n), r * math.sin(phase + 2 * math.pi * k / n), z)
                       for k in range(n)]
            ring = []
            for p in pts:
                if rot is not None:
                    q = rot @ Vector(p)
                    p = (q.x, q.y, q.z)
                ring.append(self.v((cx + p[0], cy + p[1], cz + p[2])))
            rings.append(ring)
        for i in range(len(prof) - 1):
            a, b = rings[i], rings[i + 1]
            m = mat[i] if isinstance(mat, (list, tuple)) else mat
            if len(a) == 1 and len(b) == 1:
                continue
            for k in range(n):
                k2 = (k + 1) % n
                if len(a) == 1:
                    self.face((a[0], b[k2], b[k]), m)
                elif len(b) == 1:
                    self.face((a[k], a[k2], b[0]), m)
                else:
                    self.face((a[k], a[k2], b[k2], b[k]), m)

    def sweep(self, path, prof, mat, lateral=None, perp=False, caps=(True, True), scales=None):
        """Sweep a closed 2D profile [(lateral, up)] along a path. Sections stay vertical unless perp=True."""
        pts = [Vector(p) for p in path]
        n = len(pts)
        m = len(prof)
        rings = []
        hand = 1.0
        for i, p in enumerate(pts):
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
            if t.length < 1e-9:
                t = Vector((0.0, 1.0, 0.0))
            t.normalize()
            if lateral is not None:
                lat = Vector(lateral).normalized()
            else:
                lat = t.cross(_Z)
                if lat.length < 1e-6:
                    lat = Vector((1.0, 0.0, 0.0))
                lat.normalize()
            upv = lat.cross(t).normalized() if perp else _Z
            s = scales[i] if scales else 1.0
            rings.append([self.v(p + lat * (l * s) + upv * (u * s)) for l, u in prof])
            if i == 0:
                hand = lat.cross(upv).dot(t)
        flip = (hand * _area2(prof)) < 0
        for i in range(n - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(m):
                k2 = (k + 1) % m
                f = (a[k], a[k2], b[k2], b[k])
                self.face(f[::-1] if flip else f, mat)
        if caps[0]:
            f = rings[0]
            self.face(f if flip else f[::-1], mat)
        if caps[1]:
            f = rings[-1]
            self.face(f[::-1] if flip else f, mat)

    def tube(self, path, r, n, mat, r_end=None, caps=(True, True)):
        prof = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        scales = None
        if r_end is not None:
            cnt = len(path)
            scales = [1.0 + (r_end / r - 1.0) * i / (cnt - 1) for i in range(cnt)]
        self.sweep(path, prof, mat, perp=True, caps=caps, scales=scales)

    def prism(self, outline, origin, u, v, thick, mat, center=True):
        """Extrude a 2D outline (in the u, v plane through origin) by `thick` along u x v."""
        u, v = Vector(u), Vector(v)
        nrm = u.cross(v).normalized()
        o = Vector(origin)
        if center:
            o = o - nrm * (thick * 0.5)
        a = [self.v(o + u * p[0] + v * p[1]) for p in outline]
        b = [self.v(o + u * p[0] + v * p[1] + nrm * thick) for p in outline]
        flip = _area2(outline) < 0
        m = len(outline)
        for k in range(m):
            k2 = (k + 1) % m
            f = (a[k], a[k2], b[k2], b[k])
            self.face(f[::-1] if flip else f, mat)
        self.face(a if flip else a[::-1], mat)
        self.face(b[::-1] if flip else b, mat)

    def disc(self, c, out, along, r, t0, t1, n, mat):
        """Short horizontal cylinder (round tile end): axis = out, from offset t0 (back) to t1 (front)."""
        c, out, along = Vector(c), Vector(out), Vector(along)
        back, front = [], []
        for k in range(n):
            th = 2 * math.pi * (k + 0.5) / n
            off = along * (r * math.cos(th)) + _Z * (r * math.sin(th))
            back.append(self.v(c + off + out * t0))
            front.append(self.v(c + off * 0.86 + out * t1))
        for k in range(n):
            k2 = (k + 1) % n
            th = 2 * math.pi * (k + 1.0) / n
            hint = along * math.cos(th) + _Z * math.sin(th)
            self.face((back[k], back[k2], front[k2], front[k]), mat, hint)
        self.face(front, mat, out)

    # -- result
    def finish(self, name, smooth=35.0):
        bm = bmesh.new()
        bv = [bm.verts.new(p) for p in self.vs]
        new_face = bm.faces.new
        for idx, m in zip(self.fs, self.fm):
            try:
                f = new_face([bv[i] for i in idx])
            except ValueError:
                continue
            f.material_index = m
        bm.normal_update()
        obj = common.bm_to_object(name, bm, materials=[materials.get(n) for n in self.names])
        common.set_smooth(obj, smooth)
        return obj


class _Frame:
    """Axis-aligned wall frame: a = along the wall, o = outward, z = up. dist = distance of the wall plane from 0."""

    def __init__(self, b, side, dist):
        self.b = b
        self.side = side
        self.dist = dist
        self.out = {"F": (0.0, -1.0, 0.0), "B": (0.0, 1.0, 0.0), "R": (1.0, 0.0, 0.0), "L": (-1.0, 0.0, 0.0)}[side]

    def pt(self, a, o, z):
        d = self.dist + o
        if self.side == "F":
            return (a, -d, z)
        if self.side == "B":
            return (-a, d, z)
        if self.side == "R":
            return (d, a, z)
        return (-d, -a, z)

    def box(self, a0, a1, o0, o1, z0, z1, mat, bevel=0.0):
        p, q = self.pt(a0, o0, z0), self.pt(a1, o1, z1)
        lo = (min(p[0], q[0]), min(p[1], q[1]), min(p[2], q[2]))
        hi = (max(p[0], q[0]), max(p[1], q[1]), max(p[2], q[2]))
        self.b.box2(lo, hi, mat, bevel)

    def quad(self, a0, a1, o, z0, z1, mat):
        self.b.quad(self.pt(a0, o, z0), self.pt(a1, o, z0), self.pt(a1, o, z1), self.pt(a0, o, z1), mat, self.out)


# ----------------------------------------------------------------------------------------------------------------
# roof
# ----------------------------------------------------------------------------------------------------------------
class _Roof:
    """Curved Japanese roof as a function of (side, along-eave position a, inward distance d).

    kind 'gable'   (kirizuma): two slopes F/B, verges at x = +-ex
         'irimoya' (hip-and-gable): hip skirt of depth s on all four sides, gable part above it on F/B
         'skirt'   : hipped ring of depth s on all four sides (s = ex = ey gives a pyramid)
    """

    def __init__(self, b, kind, ex, ey, rise, s=0.0, vo=0.0, lift=0.5, lift_r=4.0, sag=0.0, a=0.5, p=2.0,
                 wave=0.012):
        self.kind = kind
        self.ex, self.ey = ex, ey
        self.rise = rise
        self.s = 0.0 if kind == "gable" else s
        self.vo = vo
        self.gx = ex - self.s
        self.xv = ex if kind == "gable" else self.gx + vo
        self.lift, self.lift_r, self.sag = lift, lift_r, sag
        self.a, self.p = a, p
        self.wave = wave
        self.z0 = 0.0
        self.ph = [b.rnd.uniform(0.0, 6.2832) for _ in range(3)]

    def f(self, d):
        t = min(max(d / self.ey, 0.0), 1.0)
        return self.rise * (self.a * t + (1.0 - self.a) * t ** self.p)

    def amax(self, side):
        return self.ex if side in "FB" else self.ey

    def alim(self, side, d):
        if side in "FB":
            if self.kind == "gable":
                return self.ex
            if self.kind == "irimoya":
                return max(self.ex - d, self.xv)
            return max(self.ex - d, 0.01)
        return max(self.ey - d, 0.01)

    @staticmethod
    def out(side):
        return {"F": (0.0, -1.0, 0.0), "B": (0.0, 1.0, 0.0), "R": (1.0, 0.0, 0.0), "L": (-1.0, 0.0, 0.0)}[side]

    @staticmethod
    def along(side):
        return (1.0, 0.0, 0.0) if side in "FB" else (0.0, 1.0, 0.0)

    def xy(self, side, a, d):
        if side == "F":
            return a, -(self.ey - d)
        if side == "B":
            return a, self.ey - d
        if side == "R":
            return self.ex - d, a
        return -(self.ex - d), a

    def z(self, side, a, d):
        fb = side in "FB"
        m = (self.ex if fb else self.ey) - abs(a)
        z = self.z0 + self.f(d)
        if self.lift:
            hi = max(d, m)
            g = 1.0 - hi / self.lift_r
            if g > 0.0:
                lo = max(0.0, min(d, m))
                h = max(0.0, 1.0 - lo / (0.75 * self.lift_r))
                z += self.lift * g ** 2.5 * h * h
        if fb and self.sag and d > self.s:
            w = (d - self.s) / (self.ey - self.s)
            z += self.sag * (a / self.xv) ** 2 * w * w
        if self.wave:
            x, y = self.xy(side, a, d)
            z += self.wave * (math.sin(0.83 * x + self.ph[0]) * math.sin(1.17 * y + self.ph[1])
                              + 0.5 * math.sin(2.3 * x + 1.7 * y + self.ph[2]))
        return z

    def P(self, side, a, d, dz=0.0, de=None):
        x, y = self.xy(side, a, d)
        return Vector((x, y, self.z(side, a, d if de is None else de) + dz))

    def rib_dmax(self, side, a, margin):
        aa = abs(a)
        if side in "FB":
            if self.kind == "gable":
                return self.ey if aa <= self.ex - margin else 0.0
            if self.kind == "irimoya":
                if aa <= self.xv - margin:
                    return self.ey
                return min(self.ex - aa - 0.03, self.s - self.vo)
            return min(self.s, self.ex - aa - 0.03)
        return min(self.s, self.ey - aa - 0.03)

    def mitre(self, side, a):
        """Distance from the eave to the hip line at position a (very large when there is no hip)."""
        if self.kind == "gable":
            return 1e9
        return self.amax(side) - abs(a)


_ROOF_DEF = dict(step=0.03, course=0.34, dx=0.26, rib_dx=0.40, rib_r=0.08, rib_seg=5, disc_n=8, rib_half=False,
                 t1=0.16, t2=0.31, es=1.0, dk=1.2, d_in=2.9, raf_dx=0.30, raf=True, raf_w=0.09, raf_h1=0.12,
                 raf_h2=0.14, rs=1.0, ridge=True, verge=True, verge_margin=None, ends=True, worn=0.012)


def _courses(lo, hi, c):
    n = max(1, int(round((hi - lo) / c)))
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def _sheet(b, R, side, rows, strips, dx):
    """Skin strips between consecutive rows (d_plan, d_eval, dz), mitred at the hips."""
    K = max(2, int(math.ceil(R.amax(side) / dx)))
    hints = {"up": (0.0, 0.0, 1.0), "down": (0.0, 0.0, -1.0), "out": R.out(side)}
    prev = None
    for i, (dp, de, dz) in enumerate(rows):
        lim = R.alim(side, dp)
        ring = [b.v(R.P(side, lim * k / K, dp, dz, de)) for k in range(-K, K + 1)]
        if prev is not None:
            mat, h = strips[i - 1]
            hv = hints[h]
            for k in range(2 * K):
                b.face((prev[k], prev[k + 1], ring[k + 1], ring[k]), mat, hv)
        prev = ring


def _ribs(b, R, side, bounds, st):
    """Round cover tiles running down the slope, one tapered half-round segment per tile course."""
    r0 = st["rib_r"]
    nseg = st["rib_seg"]
    step = st["step"]
    dxr = st["rib_dx"]
    emb = 0.012
    amax = R.amax(side)
    margin = st["verge_margin"] if st["verge_margin"] is not None else 3.4 * r0
    al = Vector(R.along(side))
    out = Vector(R.out(side))
    if st["rib_half"]:
        n = max(1, int(round(amax / dxr)))
        dxr = amax / n
        pos = [(i + 0.5) * dxr for i in range(-n, n)]
    else:
        n = int((amax - r0 - 0.02) / dxr)
        pos = [i * dxr for i in range(-n, n + 1)]
    cs = [(math.cos(math.pi * k / nseg), math.sin(math.pi * k / nseg)) for k in range(nseg + 1)]
    for a in pos:
        dmax = R.rib_dmax(side, a, margin)
        if dmax < 0.2:
            continue
        rr = r0 * (1.0 + b.jit(0.04))
        if st["disc_n"]:
            c = R.P(side, a, 0.0, step - emb)
            b.disc(c, out, al, rr * 1.07, -0.01, 0.03, st["disc_n"], TILE)
        for j in range(len(bounds) - 1):
            d0 = bounds[j]
            if d0 > dmax - 0.06:
                break
            d1 = min(bounds[j + 1] + 0.03, dmax)
            ja = a + b.jit(0.004)
            if j and st["worn"] and b.rnd.random() < st["worn"]:
                continue                    # a cover tile has slipped off
            p0 = R.P(side, ja, d0, step - emb)
            p1 = R.P(side, ja, d1, step * 0.3 - emb)
            ra, rb = rr, rr * 0.84
            lo = [b.v(p0 + al * (ra * c) + _Z * (ra * s)) for c, s in cs]
            hi = [b.v(p1 + al * (rb * c) + _Z * (rb * s)) for c, s in cs]
            for k in range(nseg):
                b.face((lo[k], lo[k + 1], hi[k + 1], hi[k]), TILE, (0.0, 0.0, 1.0))
            b.face(lo, TILE, out)


def _ridge_prof(w, h, cr, emb=None):
    """Stacked tile ridge: vertical sides with two shadow ledges and a round cap tile. CCW in (lateral, up)."""
    hw = w * 0.5
    if emb is None:
        emb = min(0.12, 0.3 * h)
    right = [(hw, -emb), (hw, 0.5 * h), (hw + 0.025, 0.5 * h), (hw + 0.025, 0.5 * h + 0.035),
             (hw - 0.03, 0.5 * h + 0.035), (hw - 0.03, h)]
    cap = [(cr * math.cos(math.pi * k / 4), h + cr * math.sin(math.pi * k / 4)) for k in range(5)]
    left = [(-x, y) for x, y in reversed(right)]
    return right + cap + left


def _ridge_end(b, pos, out, rs, horn=True):
    """Ogre-tile plate with two horns standing at the end of a ridge, plus an upturned round end tile."""
    pos, out = Vector(pos), Vector(out).normalized()
    u = _Z.cross(out)
    shape = [(-0.30, -0.10), (0.30, -0.10), (0.38, 0.22), (0.30, 0.46), (0.36, 0.78), (0.15, 0.62), (0.0, 0.72),
             (-0.15, 0.62), (-0.36, 0.78), (-0.30, 0.46), (-0.38, 0.22)]
    b.prism([(x * rs, y * rs) for x, y in shape], pos + out * (0.07 * rs), u, _Z, 0.14 * rs, TILE)
    b.box(pos + out * (0.15 * rs) + _Z * (0.26 * rs), (0.2 * rs, 0.2 * rs, 0.2 * rs), TILE, bevel=0.03 * rs,
          rot=Matrix.Rotation(math.radians(45), 3, out))
    if horn:
        base = pos + _Z * (0.5 * rs)
        path = [base - out * (0.25 * rs), base + out * (0.2 * rs) + _Z * (0.04 * rs),
                base + out * (0.42 * rs) + _Z * (0.16 * rs), base + out * (0.56 * rs) + _Z * (0.36 * rs),
                base + out * (0.62 * rs) + _Z * (0.58 * rs)]
        b.tube(path, 0.085 * rs, 8, TILE, r_end=0.045 * rs)


def _gable_wall(b, R, xg, sx, zb, d0, drop, mat, n=10):
    """Vertical triangle under a gable, in the plane x = xg, from height zb up to the underside of the roof."""
    pts = []
    for i in range(n + 1):
        d = d0 + (R.ey - d0) * i / n
        zt = max(zb, R.z("F", xg, d) - drop)
        pts.append((-(R.ey - d), zt))
    pts += [(-y, z) for y, z in reversed(pts[:-1])]
    hint = (sx, 0.0, 0.0)
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        if max(z0, z1) - zb < 1e-4:
            continue
        b.quad((xg, y0, zb), (xg, y1, zb), (xg, y1, z1), (xg, y0, z0), mat, hint)


def _verge(b, R, st, d_lo, board=0.48):
    """Verge roll tile, bargeboards and pendant along both gable edges (x = +-xv)."""
    step = st["step"]
    rs = st["rs"]
    rv = st["rib_r"] * 1.15
    n = max(4, int(round((R.ey - d_lo) / 0.35)))
    ds = [d_lo + (R.ey - d_lo) * i / n for i in range(n + 1)]
    roll = [(0.0, -0.07), (0.0, step + 0.01)]
    roll += [(-rv + rv * math.cos(math.pi * k / 4), step + 0.01 + rv * math.sin(math.pi * k / 4)) for k in range(1, 5)]
    roll += [(-2 * rv, -0.03)]
    bd = board * rs
    plank = [(-0.115, -bd), (-0.025, -bd), (-0.025, -0.04), (-0.115, -0.04)]
    trim = [(-0.03, -0.19 * rs - 0.03), (0.012, -0.19 * rs - 0.03), (0.012, -0.065), (-0.03, -0.065)]
    for sx in (-1, 1):
        a = sx * R.xv
        path = [R.P("F", a, d) for d in ds] + [R.P("B", a, d) for d in reversed(ds[:-1])]
        lat = (float(sx), 0.0, 0.0)
        b.sweep(path, roll, TILE, lateral=lat)
        dl = max(0.0, d_lo - 0.3)
        ds2 = [dl] + ds if dl < d_lo else ds
        path2 = [R.P("F", a, d) for d in ds2] + [R.P("B", a, d) for d in reversed(ds2[:-1])]
        b.sweep(path2, plank, RED, lateral=lat)
        b.sweep(path2, trim, DARK, lateral=lat)
        apex = R.P("F", a, R.ey)
        # pendant under the apex and a gold fitting over the board joint
        shape = [(0.0, -0.62), (0.13, -0.47), (0.28, -0.33), (0.31, -0.13), (0.2, 0.0), (-0.2, 0.0), (-0.31, -0.13),
                 (-0.28, -0.33), (-0.13, -0.47)]
        o = apex + Vector((sx * 0.0, 0.0, -0.17 * rs - 0.1))
        b.prism([(x * rs, y * rs) for x, y in shape], o, (0.0, 1.0, 0.0), _Z, 0.06, DARK)
        b.box(o + Vector((sx * 0.04, 0.0, -0.2 * rs)), (0.03, 0.2 * rs, 0.2 * rs), GOLD, bevel=0.008,
              rot=Matrix.Rotation(math.radians(45), 3, "X"))
        b.box(apex + Vector((0.0, 0.0, -0.16 * rs - 0.02)), (0.07, 0.34 * rs, 0.22 * rs), GOLD, bevel=0.008)


def _build_roof(b, R, opt):
    """Tile skin with courses, cover-tile ribs, layered eave, soffit, two rafter tiers, ridges and gable ends."""
    st = dict(_ROOF_DEF)
    st.update(opt)
    es, step, t1, t2, dk, d_in = st["es"], st["step"], st["t1"], st["t2"], st["dk"], st["d_in"]
    kind = R.kind
    rs = st["rs"]
    if kind == "gable":
        fb = _courses(0.0, R.ey, st["course"])
        lr = None
    elif kind == "irimoya":
        lr = _courses(0.0, R.s, st["course"])
        fb = lr + _courses(R.s, R.ey, st["course"])[1:]
    else:
        lr = _courses(0.0, R.s, st["course"])
        fb = lr

    # ---- skin: soffit (two levels) -> eave board -> tile lip -> tile courses
    n_in = max(1, int(math.ceil((d_in - dk) / 0.7)))
    under = []
    for i in range(n_in):
        d = d_in + (dk - d_in) * i / n_in
        under.append((d, d, -t2))
    e1, e2 = 0.14 * es, 0.06 * es
    dm = (dk + e1) * 0.5
    under += [(dk, dk, -t2), (dk, dk, -t1), (dm, dm, -t1), (e1, e1, -t1), (e2, 0.0, -0.15 * es),
              (e2, 0.0, -0.055 * es), (0.0, 0.0, -0.055 * es)]
    ustr = [(DARK, "down")] * n_in + [(DARK, "out"), (DARK, "down"), (DARK, "down"), (RED, "down"), (RED, "out"),
                                      (TILE, "down"), (TILE, "out")]

    def top_rows(bd):
        rows = [(bd[0], bd[0], step)]
        for j in range(len(bd) - 1):
            rows.append((bd[j + 1], bd[j + 1], 0.0))
            if j + 1 < len(bd) - 1:
                rows.append((bd[j + 1] + 0.004, bd[j + 1], step))
        return rows

    for sides, bd in (("FB", fb), ("LR", lr)):
        if bd is None:
            continue
        rows = under + top_rows(bd)
        strips = ustr + [(TILE, "up")] * (len(rows) - len(under) - 1)
        for side in sides:
            _sheet(b, R, side, rows, strips, st["dx"])
            _ribs(b, R, side, bd, st)

    # ---- rafters (flying tier at the edge, base tier behind the intermediate eave board)
    sides_all = "FB" if kind == "gable" else "FBLR"
    if st["raf"]:
        w, h1, h2 = st["raf_w"], st["raf_h1"], st["raf_h2"]
        for side in sides_all:
            amax = R.amax(side)
            edge = 0.2 if kind == "gable" else 0.0
            n = int((amax - edge) / st["raf_dx"])
            for i in range(-n, n + 1):
                a = i * st["raf_dx"] + b.jit(0.006)
                m = R.mitre(side, a)
                d0, d1 = 0.13 * es, min(dk - 0.05, m - 0.09)
                if d1 - d0 > 0.1:
                    p0, p1 = R.P(side, a, d0, -t1 + 0.012), R.P(side, a, d1, -t1 + 0.012)
                    b.beam(p0, p1, w, h1, RED, anchor="top")
                    dirv = (p0 - p1).normalized()
                    b.beam(p0 - dirv * 0.04 - _Z * 0.004, p0 + dirv * 0.008 - _Z * 0.004, w + 0.012, h1 + 0.004, GOLD,
                           anchor="top")
                d0, d1 = dk + 0.04, min(d_in - 0.03, m - 0.09)
                if d1 - d0 > 0.1:
                    ns = max(1, int(math.ceil((d1 - d0) / 1.3)))
                    for q in range(ns):
                        da, db = d0 + (d1 - d0) * q / ns, d0 + (d1 - d0) * (q + 1) / ns
                        b.beam(R.P(side, a, da - (0.02 if q else 0.0), -t2 + 0.012), R.P(side, a, db, -t2 + 0.012),
                               w + 0.015, h2, RED, anchor="top")
            # intermediate eave board hiding the step between the two soffit levels
            lim = R.alim(side, dk) - (0.13 if kind == "gable" else 0.0)
            cnt = max(2, int(math.ceil(2 * lim / 0.6)))
            path = [R.P(side, -lim + 2 * lim * q / cnt, dk, -t1 + 0.01) for q in range(cnt + 1)]
            o = Vector(R.out(side))
            bh = (t2 - t1) + h2 + 0.03
            prof = [(-0.06, -bh), (0.07, -bh), (0.07, 0.0), (-0.06, 0.0)]
            b.sweep(path, prof, RED, lateral=o)
        if kind != "gable":
            # hip rafters under the four corners
            for sx in (-1, 1):
                for side in "FB":
                    top = min(d_in, R.s)
                    cnt = 5
                    path = []
                    for q in range(cnt + 1):
                        d = 0.12 + (top - 0.12) * q / cnt
                        path.append(R.P(side, sx * (R.ex - d), d, -t1 + 0.01 if d < dk else -t2 + 0.01))
                    hw_, hd_ = 0.8 * w, 1.9 * h2
                    b.sweep(path, [(-hw_, -hd_), (hw_, -hd_), (hw_, 0.0), (-hw_, 0.0)], RED)
                    tip = (path[0] - path[1]).normalized()
                    hw_, hd_ = hw_ + 0.008, hd_ + 0.008
                    b.sweep([path[0] - tip * 0.06, path[0] + tip * 0.012],
                            [(-hw_, -hd_), (hw_, -hd_), (hw_, 0.0), (-hw_, 0.0)], GOLD)

    # ---- ridges
    if st["ridge"]:
        hw, hh, cr = 0.36 * rs, 0.5 * rs, 0.1 * rs
        if kind in ("gable", "irimoya"):
            xe = R.xv - (0.04 if st["ends"] else 0.0)
            cnt = max(2, int(math.ceil(2 * xe / 0.8)))
            path = [R.P("F", -xe + 2 * xe * q / cnt, R.ey) for q in range(cnt + 1)]
            b.sweep(path, _ridge_prof(hw, hh, cr), TILE, lateral=(0.0, 1.0, 0.0))
            if st["ends"]:
                for sx in (-1, 1):
                    _ridge_end(b, R.P("F", sx * xe, R.ey), (sx, 0.0, 0.0), rs)
        if kind == "irimoya":
            # descending ridges beside the gable verges
            xa = R.xv - 0.62 * rs
            d_top, d_bot = R.ey - 0.2 * rs, R.s - R.vo + 0.35
            cnt = max(3, int(math.ceil((d_top - d_bot) / 0.45)))
            prof = _ridge_prof(0.27 * rs, 0.3 * rs, 0.085 * rs)
            for side in "FB":
                for sx in (-1, 1):
                    path = [R.P(side, sx * xa, d_top + (d_bot - d_top) * q / cnt) for q in range(cnt + 1)]
                    b.sweep(path, prof, TILE, lateral=(1.0, 0.0, 0.0))
                    _ridge_end(b, path[-1], R.out(side), rs * 0.62)
        if kind in ("irimoya", "skirt"):
            # hip ridges from the gable foot (or the top of the skirt) down to the upturned corners
            d_top = (R.s - R.vo - 0.05) if kind == "irimoya" else R.s - 0.02
            d_bot = 0.42 * rs + 0.1
            cnt = max(4, int(math.ceil((d_top - d_bot) / 0.4)))
            prof = _ridge_prof(0.25 * rs, 0.27 * rs, 0.085 * rs)
            for side in "FB":
                o = Vector(R.out(side))
                for sx in (-1, 1):
                    path = []
                    for q in range(cnt + 1):
                        d = d_top + (d_bot - d_top) * q / cnt
                        up = 0.16 * rs * max(0.0, 1.0 - (d - d_bot) / 1.0) ** 2
                        path.append(R.P(side, sx * (R.ex - d), d, up))
                    heading = (Vector((sx, 0.0, 0.0)) + o).normalized()
                    b.sweep(path, prof, TILE, lateral=heading.cross(_Z))
                    _ridge_end(b, path[-1], heading, rs * 0.6)

    # ---- gable ends
    if st["verge"]:
        if kind == "gable":
            _verge(b, R, st, 0.0)
        elif kind == "irimoya":
            _verge(b, R, st, R.s - R.vo)
            xg = R.gx - 0.03
            n = max(4, int(round((R.ey - R.s + R.vo) / 0.4)))
            for sx in (-1, 1):
                zb = R.z("R", 0.0, R.s) - 0.08
                _gable_wall(b, R, sx * xg, sx, zb, R.s - 0.02, 0.12, DARK)
                # underside of the verge overhang
                ds = [R.s - R.vo + (R.ey - R.s + R.vo) * i / n for i in range(n + 1)]
                for side in "FB":
                    for da, db in zip(ds[:-1], ds[1:]):
                        ya, yb = R.xy(side, 0.0, da)[1], R.xy(side, 0.0, db)[1]
                        za, zb2 = R.z(side, sx * R.xv, da) - 0.13, R.z(side, sx * R.xv, db) - 0.13
                        x0, x1 = sx * (R.gx - 0.06), sx * (R.xv - 0.03)
                        b.quad((x0, ya, za), (x1, ya, za), (x1, yb, zb2), (x0, yb, zb2), DARK, (0.0, 0.0, -1.0))
                # timber frame on the gable face, flashing strip at its foot
                gy = R.ey - R.s
                xf = sx * (xg + 0.03)
                b.box2((xf - 0.07, -gy + 0.15, zb + 0.06), (xf + 0.07, gy - 0.15, zb + 0.32 * rs + 0.06), RED, 0.015)
                zt = R.z("F", sx * R.gx, R.ey) - 0.2
                b.box2((xf - 0.06, -0.12 * rs, zb + 0.3), (xf + 0.06, 0.12 * rs, zt), RED, 0.015)
                for sy in (-1, 1):
                    y = sy * gy * 0.42
                    zt2 = R.z("F", sx * R.gx, R.ey - abs(y)) - 0.2
                    b.box2((xf - 0.05, y - 0.08 * rs, zb + 0.3), (xf + 0.05, y + 0.08 * rs, zt2), RED, 0.012)
                path = [(sx * (R.gx + 0.07), -gy - 0.1, zb + 0.08), (sx * (R.gx + 0.07), gy + 0.1, zb + 0.08)]
                b.sweep(path, [(-0.12, -0.05), (0.12, -0.05), (0.12, 0.1), (0.0, 0.17), (-0.12, 0.1)], TILE,
                        lateral=(1.0, 0.0, 0.0))
    return st


# ----------------------------------------------------------------------------------------------------------------
# masonry, stairs, floor, railing
# ----------------------------------------------------------------------------------------------------------------
def _block_ring(b, hx, hy, z0, z1, depth, avg, mat, skip=None, bevel=0.02):
    """One course of stone blocks around the rectangle (+-hx, +-hy); outer faces on the rectangle."""
    r = b.rnd
    runs = [("F", -hx, hx), ("B", -hx, hx), ("L", -hy + depth, hy - depth), ("R", -hy + depth, hy - depth)]
    for side, lo, hi in runs:
        t = lo + (r.uniform(-0.35, 0.0) * avg if side in "FB" else 0.0)
        while t < hi - 1e-6:
            length = avg * r.uniform(0.7, 1.35)
            if hi - (t + length) < 0.5 * avg:
                length = hi - t
            a0, a1 = max(t, lo) + 0.005, min(t + length, hi) - 0.005
            t += length
            off = r.uniform(-0.012, 0.012)
            bv = bevel * r.uniform(0.6, 1.4) * (2.4 if r.random() < 0.1 else 1.0)
            dz = r.uniform(0.0, 0.006)
            if skip and side == "F" and a0 > skip[0] and a1 < skip[1]:
                continue
            if side == "F":
                b.box2((a0, -hy - off, z0), (a1, -hy + depth, z1 - dz), mat, bv)
            elif side == "B":
                b.box2((a0, hy - depth, z0), (a1, hy + off, z1 - dz), mat, bv)
            elif side == "L":
                b.box2((-hx - off, a0, z0), (-hx + depth, a1, z1 - dz), mat, bv)
            else:
                b.box2((hx - depth, a0, z0), (hx + off, a1, z1 - dz), mat, bv)


def _plinth(b, hx, hy, h, skip=None, avg=1.0):
    """Stone podium: mossy footing, coursed blocks, overhanging cap slabs, dark core that shows in the joints."""
    cap_t = 0.15 if h > 0.9 else 0.12
    foot = 0.13 if h > 0.9 else 0.09
    b.box2((-hx + 0.04, -hy + 0.04, 0.0), (hx - 0.04, hy - 0.04, h - 0.02), MOSSY)
    n = max(1, int(round((h - cap_t - foot) / 0.36)))
    ch = (h - cap_t - foot) / n
    _block_ring(b, hx + 0.07, hy + 0.07, 0.0, foot, 0.42, avg * 1.6, MOSSY, skip)
    for i in range(n):
        _block_ring(b, hx, hy, foot + i * ch, foot + (i + 1) * ch, 0.36, avg, MOSSY if (i == 0 and n > 1) else STONE,
                    skip)
    _block_ring(b, hx + 0.045, hy + 0.045, h - cap_t, h, 0.62, avg * 1.5, STONE)
    b.box2((-hx + 0.55, -hy + 0.55, h - 0.1), (hx - 0.55, hy - 0.55, h - 0.008), STONE)


def _stairs(b, w, y_face, h, run=0.32, cheek=0.45):
    """Stone steps climbing +Y to the plinth face at y_face. cheek > 0 adds sloped side walls with end posts.

    Returns the distance the stair sticks out in front of the plinth face."""
    r = b.rnd
    n = max(2, int(round(h / 0.172)))
    rise = h / n
    for k in range(1, n):
        y_nose = y_face - (n - k) * run
        x = -w * 0.5
        while x < w * 0.5 - 1e-6:
            length = r.uniform(1.3, 2.3)
            if w * 0.5 - (x + length) < 0.9:
                length = w * 0.5 - x
            b.box2((x + 0.004, y_nose - 0.02 + r.uniform(-0.008, 0.008), max(0.0, (k - 1) * rise - 0.015)),
                   (x + length - 0.004, y_face + 0.06, k * rise - r.uniform(0.0, 0.006)), STONE, 0.016)
            x += length
    depth = (n - 1) * run
    if cheek <= 0.0:
        return depth + 0.03
    slope = rise / run
    y0, y1 = y_face + 0.03, y_face - depth - 0.25
    zt0 = h + 0.26
    zt1 = zt0 - (y0 - y1) * slope
    for sx in (-1, 1):
        xc = sx * (w * 0.5 + cheek * 0.5 - 0.03)
        ln = y0 - y1
        b.prism([(0.0, 0.0), (ln, 0.0), (ln, zt1), (0.0, zt0)], (xc, y0, 0.0), (0.0, -1.0, 0.0), _Z, cheek, MOSSY)
        b.beam((xc, y0 + 0.02, zt0 + 0.045), (xc, y1 - 0.02, zt1 + 0.045), cheek + 0.09, 0.12, STONE, bevel=0.022)
        ph = max(zt1 + 0.22, 0.55)
        b.box((xc + r.uniform(-0.01, 0.01), y1 - 0.2, ph * 0.5), (cheek + 0.13, 0.52, ph), STONE, bevel=0.03)
        b.box((xc, y1 - 0.2, ph + 0.045), (cheek + 0.22, 0.61, 0.1), STONE, bevel=0.025)
    return depth + 0.25 + 0.2 + 0.31


def _planks(b, x0, x1, y0, y1, z0, z1, along, width=0.24, mat=DARK):
    """Floor boards filling the rectangle; `along` is the axis the boards run along ('x' or 'y')."""
    r = b.rnd
    lo, hi = (y0, y1) if along == "x" else (x0, x1)
    n = max(1, int(round((hi - lo) / width)))
    wd = (hi - lo) / n
    for i in range(n):
        a0, a1 = lo + i * wd + 0.003, lo + (i + 1) * wd - 0.003
        dz = r.uniform(-0.004, 0.003)
        e0, e1 = r.uniform(0.0, 0.02), r.uniform(0.0, 0.02)
        if along == "x":
            b.box2((x0 + e0, a0, z0), (x1 - e1, a1, z1 + dz), mat)
        else:
            b.box2((a0, y0 + e0, z0), (a1, y1 - e1, z1 + dz), mat)


def _railing(b, p0, p1, zf, h=0.9, k=1.0, end0=True, end1=True):
    """Timber balustrade from p0 to p1 (2D points) standing on the floor at zf."""
    r = b.rnd
    x0, y0 = p0
    x1, y1 = p1
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 0.3:
        return
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    n = max(1, int(round(length / 1.55)))
    tops = []
    for i in range(n + 1):
        t = length * i / n
        px, py = x0 + ux * t, y0 + uy * t
        is_end = (i == 0 and end0) or (i == n and end1)
        ph = h + (0.14 if is_end else -0.05)
        lean = Matrix.Rotation(math.radians(r.uniform(-0.7, 0.7)), 3, "X") @ \
            Matrix.Rotation(math.radians(r.uniform(-0.7, 0.7)), 3, "Y")
        b.box((px, py, zf + ph * 0.5 - 0.01), (0.115 * k, 0.115 * k, ph), RED, bevel=0.01, rot=lean)
        if is_end:
            b.lathe((px, py, zf + ph - 0.015), [(0.07 * k, 0.0), (0.075 * k, 0.03), (0.045 * k, 0.05),
                                                (0.068 * k, 0.1), (0.05 * k, 0.15), (0.0, 0.19)], 8, METAL)
        tops.append((px, py))
    for i in range(n):
        (ax, ay), (bx, by) = tops[i], tops[i + 1]
        sag = r.uniform(0.0, 0.012)
        for zz, hh in ((0.14 * h, 0.07 * k), (0.52 * h, 0.065 * k)):
            b.beam((ax, ay, zf + zz), (bx, by, zf + zz - sag * 0.5), 0.06 * k, hh, RED)
        span = math.hypot(bx - ax, by - ay)
        m = max(2, int(round(span / 0.4)))
        for q in range(1, m):
            if r.random() < 0.05:
                continue
            f = q / m
            sx, sy = ax + (bx - ax) * f, ay + (by - ay) * f
            b.box((sx, sy, zf + 0.33 * h), (0.042 * k, 0.042 * k, 0.38 * h), RED)
    # round top rail, one sagging piece per span, running past the end posts
    path = []
    ext = 0.2 * k
    zr = zf + h - 0.1
    path.append((x0 - ux * ext, y0 - uy * ext, zr + 0.035))
    for i in range(n + 1):
        px, py = tops[i]
        path.append((px, py, zr))
        if i < n:
            qx, qy = tops[i + 1]
            path.append(((px + qx) * 0.5, (py + qy) * 0.5, zr - r.uniform(0.002, 0.014)))
    path.append((x1 + ux * ext, y1 + uy * ext, zr + 0.035))
    b.tube(path, 0.042 * k, 8, RED)


# ----------------------------------------------------------------------------------------------------------------
# timber walls, columns, brackets
# ----------------------------------------------------------------------------------------------------------------
def _column(b, x, y, z0, h, r, n=14, base=True):
    rnd = b.rnd
    lean = Matrix.Rotation(math.radians(rnd.uniform(-0.25, 0.25)), 3, "X") @ \
        Matrix.Rotation(math.radians(rnd.uniform(-0.25, 0.25)), 3, "Y")
    ph = rnd.uniform(0.0, 1.0)
    if base:
        b.lathe((x, y, z0 - 0.02), [(r * 1.75, 0.0), (r * 1.75, 0.07), (r * 1.45, 0.12), (r * 1.02, 0.12)], n, STONE,
                phase=ph)
    b.lathe((x, y, z0), [(r, 0.0), (r * 1.0, h * 0.55), (r * 0.965, h * 0.85), (r * 0.93, h), (0.0, h)], n, RED,
            rot=lean, phase=ph)


def _arm(b, x, y, zb, d2, k, length):
    """Boat-shaped bracket arm centred on (x, y), running along the 2D direction d2, bottom at zb."""
    hl = length * 0.5
    shape = [(-hl, 0.2 * k), (-hl, 0.09 * k), (-hl + 0.17 * k, 0.0), (hl - 0.17 * k, 0.0), (hl, 0.09 * k),
             (hl, 0.2 * k)]
    b.prism(shape, (x, y, zb), (d2[0], d2[1], 0.0), _Z, 0.15 * k, RED)


def _bracket(b, x, y, zc, outs, k, stepped):
    """Bearing block, bracket arms and small blocks on a column head. outs: wall normals (1 or 2 for a corner)."""
    b.box((x, y, zc + 0.05 * k), (0.3 * k, 0.3 * k, 0.12 * k), RED, bevel=0.012)
    b.box((x, y, zc + 0.17 * k), (0.43 * k, 0.43 * k, 0.13 * k), RED, bevel=0.014)
    for ox, oy in outs:
        al = (-oy, ox)
        _arm(b, x, y, zc + 0.16 * k, al, k, 1.3 * k)
        for t in (-0.5, 0.0, 0.5):
            b.box((x + al[0] * t * k, y + al[1] * t * k, zc + 0.425 * k), (0.21 * k, 0.21 * k, 0.13 * k), RED,
                  bevel=0.01)
        if stepped:
            e = 0.6 * k
            shape = [(-0.15 * k, 0.2 * k), (-0.15 * k, 0.0), (e - 0.03 * k, 0.0), (e + 0.15 * k, 0.1 * k),
                     (e + 0.15 * k, 0.2 * k)]
            b.prism(shape, (x, y, zc + 0.16 * k), (ox, oy, 0.0), _Z, 0.15 * k, RED)
            cx, cy = x + ox * e, y + oy * e
            b.box((cx, cy, zc + 0.425 * k), (0.21 * k, 0.21 * k, 0.13 * k), RED, bevel=0.01)
            _arm(b, cx, cy, zc + 0.47 * k, al, k, 1.2 * k)
            for t in (-0.46, 0.0, 0.46):
                b.box((cx + al[0] * t * k, cy + al[1] * t * k, zc + 0.735 * k), (0.2 * k, 0.2 * k, 0.13 * k), RED,
                      bevel=0.01)
    if stepped and len(outs) == 2:
        dx, dy = outs[0][0] + outs[1][0], outs[0][1] + outs[1][1]
        e = 0.6 * k
        b.beam((x, y, zc + 0.36 * k), (x + dx * (e + 0.12 * k), y + dy * (e + 0.12 * k), zc + 0.62 * k), 0.15 * k,
               0.2 * k, RED, bevel=0.012)


_SIMPLE_TOP = 0.67      # top of the wall purlin above the column head, in units of k
_STEP_TOP = 0.98        # top of the outer purlin (stepped bracket)


def _wall(b, fr, half, nb, kinds, zf, hc, col_r, k, glow=True, dz=0.0):
    """Timber infill for one wall: per bay a sill, lintel, head tie, transom and a door / window / panel."""
    r = b.rnd
    bay = 2.0 * half / nb
    hs = 0.16
    hw = 0.25 * hc
    hl = 0.66 * hc
    lh = 0.2 * k
    zt_tr = zf + hc - 0.34 * k
    for i in range(nb):
        kind = kinds[i]
        a0 = -half + i * bay + col_r * 0.85
        a1 = -half + (i + 1) * bay - col_r * 0.85
        ac = (a0 + a1) * 0.5
        fr.box(a0, a1, -0.085 * k - 0.02, 0.085 * k + 0.02, zt_tr, zf + hc - 0.04, RED, 0.014)
        if kind == "open":
            continue
        fr.box(a0, a1, -0.08, 0.08, zf + hl, zf + hl + lh, RED, 0.012)
        fr.box(a0, a1, -0.1, 0.1, zf - 0.01, zf + hs, RED, 0.012)
        # transom
        z0t, z1t = zf + hl + lh - 0.01, zt_tr + 0.01
        zm = (z0t + z1t) * 0.5
        if kind == "panel":
            fr.box(a0, a1, -0.03, 0.03, z0t, z1t, PLASTER)
            fr.box(ac - 0.045, ac + 0.045, -0.04, 0.045, z0t, z1t, RED)
        else:
            fr.box(a0, a1, -0.03, 0.02, z0t, z1t, DARK)
            fr.box(a0, a1, 0.02, 0.055, zm - 0.022, zm + 0.022, RED)
            m = max(2, int(round((a1 - a0) / 0.3)))
            for q in range(1, m):
                aq = a0 + (a1 - a0) * q / m
                fr.box(aq - 0.018, aq + 0.018, 0.02, 0.048, z0t, z1t, RED)
            if kind == "door":
                fr.box(ac - 0.1, ac + 0.1, 0.05, 0.078, zm - 0.1, zm + 0.1, GOLD, 0.012)
        if kind == "door":
            zb, zt = zf + hs - 0.005, zf + hl + 0.005
            zr = zb + 0.36 * (zt - zb)
            st = 0.085
            for l0, l1 in ((a0, ac - 0.004), (ac + 0.004, a1)):
                fr.box(l0, l0 + st, 0.0, 0.07, zb, zt, RED, 0.008)
                fr.box(l1 - st, l1, 0.0, 0.07, zb, zt, RED, 0.008)
                for zz in (zb + st * 0.5, zr, zt - st * 0.5):
                    fr.box(l0 + st - 0.005, l1 - st + 0.005, 0.005, 0.065, zz - st * 0.5, zz + st * 0.5, RED, 0.008)
                fr.box(l0 + st - 0.01, l1 - st + 0.01, 0.012, 0.04, zb + st - 0.01, zr - st * 0.5 + 0.01, DARK)
                lc = (l0 + l1) * 0.5
                fr.box(lc - 0.03, lc + 0.03, 0.04, 0.058, zb + st, zr - st * 0.5, RED)
                # square lattice over the glowing paper
                wl0, wl1, zl0, zl1 = l0 + st, l1 - st, zr + st * 0.5, zt - st
                nv = max(2, int(round((wl1 - wl0) / 0.15)))
                for q in range(1, nv):
                    aq = wl0 + (wl1 - wl0) * q / nv
                    fr.box(aq - 0.013, aq + 0.013, 0.03, 0.056, zl0 - 0.01, zl1 + 0.01, DARK)
                nh = max(2, int(round((zl1 - zl0) / 0.15)))
                for q in range(1, nh):
                    zq = zl0 + (zl1 - zl0) * q / nh
                    fr.box(wl0 - 0.01, wl1 + 0.01, 0.022, 0.048, zq - 0.013, zq + 0.013, DARK)
                fr.quad(l0 + 0.03, l1 - 0.03, -0.004, zr, zt - 0.03, GLOW if glow else DARK)
            continue
        # window / lattice / panel share the waist rail and the boarded lower wall
        fr.box(a0, a1, -0.07, 0.09, zf + hw - 0.07, zf + hw + 0.07, RED, 0.012)
        fr.box(a0, a1, -0.03, 0.034, zf + hs - 0.01, zf + hw - 0.06, DARK)
        m = max(2, int(round((a1 - a0) / 0.45)))
        for q in range(1, m):
            aq = a0 + (a1 - a0) * q / m + r.uniform(-0.01, 0.01)
            fr.box(aq - 0.028, aq + 0.028, 0.03, 0.058, zf + hs - 0.01, zf + hw - 0.06, RED)
        zb, zt = zf + hw + 0.065, zf + hl + 0.005
        if kind == "panel":
            fr.box(a0, a1, -0.03, 0.03, zb, zt, PLASTER)
            fr.box(ac - 0.05, ac + 0.05, -0.04, 0.046, zb, zt, RED)
            continue
        jw = 0.1
        fr.box(a0, a0 + jw, -0.03, 0.075, zb, zt, RED, 0.008)
        fr.box(a1 - jw, a1, -0.03, 0.075, zb, zt, RED, 0.008)
        wl0, wl1 = a0 + jw, a1 - jw
        nv = max(3, int(round((wl1 - wl0) / 0.125)))
        for q in range(1, nv):
            aq = wl0 + (wl1 - wl0) * q / nv
            fr.box(aq - 0.02, aq + 0.02, 0.012, 0.052, zb - 0.01, zt + 0.01, DARK)
        for f in (0.33, 0.67):
            zq = zb + (zt - zb) * f
            fr.box(wl0 - 0.01, wl1 + 0.01, 0.0, 0.036, zq - 0.022, zq + 0.022, DARK)
        fr.quad(a0 + 0.04, a1 - 0.04, -0.012, zb - 0.02, zt + 0.02, GLOW if (glow and kind == "window") else DARK)
    # continuous tie rail in front of the column faces at lintel height
    if any(kd != "open" for kd in kinds):
        fr.box(-half - col_r - 0.12, half + col_r + 0.12, col_r - 0.035, col_r + 0.06, zf + hl + 0.025 + dz,
               zf + hl + lh - 0.01 + dz, RED, 0.012)


# ----------------------------------------------------------------------------------------------------------------
# halls
# ----------------------------------------------------------------------------------------------------------------
def _odd_near(x):
    """Odd bay count closest to x (at least 3)."""
    n = int(round(x))
    if n % 2 == 0:
        n -= 1
    return max(3, n)


def _store(obj, size_wd, sockets, drop, door, floor_z, R):
    common.update()
    lo = [min(c[i] for c in obj.bound_box) for i in range(3)]
    hi = [max(c[i] for c in obj.bound_box) for i in range(3)]
    obj["size"] = [float(size_wd[0]), float(size_wd[1]), round(hi[2], 3)]
    obj["lantern_sockets"] = [[round(c, 3) for c in s] for s in sockets]
    obj["lantern_drop"] = round(drop, 3)
    obj["door_point"] = [round(c, 3) for c in door]
    obj["floor_z"] = round(floor_z, 3)
    if R is not None:
        obj["eave_half"] = [round(R.ex, 3), round(R.ey, 3)]
        obj["eave_z"] = round(R.z0, 3)
    obj["bbox_min"] = [round(c, 3) for c in lo]
    obj["bbox_max"] = [round(c, 3) for c in hi]
    return obj


def _hall(name, seed, width, depth, plinth, steps_w, big):
    b = _B(seed)
    hx, hy = width * 0.5, depth * 0.5
    if big:
        sc = math.sqrt(width * depth / 176.0)
        ver, col_r, hc, ov = 1.75 * sc, 0.21 * sc ** 0.5, 3.9 * sc ** 0.6, 2.55 * sc
        k, rise_k, lift, lift_r, vo = 0.82 * sc ** 0.5, 0.68, 0.85 * sc, 5.5 * sc, 0.5 * sc
        stepped, rs, rail_h, sag, cheek = True, 1.0 * sc ** 0.5, 0.9, 0.12, 0.45
        roof_opt = dict(rib_dx=0.40, rib_r=0.082, course=0.34, dx=0.27, raf_dx=0.31)
    else:
        sc = math.sqrt(width * depth / 56.0)
        ver, col_r, hc, ov = 1.0 * sc, 0.17 * sc ** 0.5, 3.0 * sc ** 0.6, 1.75 * sc
        k, rise_k, lift, lift_r, vo = 0.72 * sc ** 0.5, 0.69, 0.6 * sc, 3.9 * sc, 0.35 * sc
        stepped, rs, rail_h, sag, cheek = False, 0.72 * sc ** 0.5, 0.78, 0.07, 0.3
        roof_opt = dict(rib_dx=0.40, rib_r=0.078, course=0.36, dx=0.3, raf_dx=0.34)
    bx, by = hx - ver, hy - ver
    nbf = _odd_near(2 * bx / 2.5)
    nbs = max(2, int(round(2 * by / 2.5)))
    zp = plinth
    zf = zp + 0.10
    zc = zf + hc
    ex, ey = bx + ov, by + ov
    d_in, dk = ov + 0.35, 0.48 * ov
    s = max(d_in + vo + 0.1, 0.56 * ey)
    R = _Roof(b, "irimoya", ex, ey, rise_k * ey, s=s, vo=vo, lift=lift, lift_r=lift_r, sag=sag)
    t2, raf_h2 = _ROOF_DEF["t2"], _ROOF_DEF["raf_h2"]
    if stepped:
        R.z0 = zc + _STEP_TOP * k + t2 + raf_h2 - R.f(ov - 0.6 * k)
    else:
        R.z0 = zc + _SIMPLE_TOP * k + t2 + raf_h2 - R.f(ov)
    z_sof = R.z0 + R.f(ov) - t2          # soffit height on the wall line

    # ---- podium and front stairs
    if steps_w is None:
        steps_w = max(2.2, 2 * bx / nbf + 0.6)
    steps_w = min(steps_w, width - 2.0)
    _plinth(b, hx, hy, zp, skip=(-steps_w * 0.5 + 0.2, steps_w * 0.5 - 0.2))
    _stairs(b, steps_w, -hy - 0.03, zp, cheek=cheek)

    # ---- veranda floor and edge beam
    fe = 0.2
    _planks(b, -hx + fe, hx - fe, -hy + fe, -by + 0.06, zp - 0.01, zf, "y")
    _planks(b, -hx + fe, hx - fe, by - 0.06, hy - fe, zp - 0.01, zf, "y")
    _planks(b, -hx + fe, -bx + 0.06, -by + 0.06, by - 0.06, zp - 0.01, zf, "x")
    _planks(b, bx - 0.06, hx - fe, -by + 0.06, by - 0.06, zp - 0.01, zf, "x")
    for side, half, dist in (("F", hx - fe, hy - fe), ("B", hx - fe, hy - fe), ("R", hy - fe, hx - fe),
                             ("L", hy - fe, hx - fe)):
        dz = 0.004 if side in "LR" else 0.0
        _Frame(b, side, dist).box(-half - 0.06, half + 0.06, -0.05, 0.07, zp - 0.012, zf + 0.012 + dz, RED, 0.012)

    # ---- dark core (nothing is see-through), columns
    b.box2((-bx + 0.075, -by + 0.075, zp - 0.02), (bx - 0.075, by - 0.075, z_sof + 0.1), DARK)
    bay_f, bay_s = 2 * bx / nbf, 2 * by / nbs
    cols = {}
    for i in range(nbf + 1):
        x = -bx + i * bay_f
        cols.setdefault((round(x, 4), -by), []).append((0.0, -1.0))
        cols.setdefault((round(x, 4), by), []).append((0.0, 1.0))
    for j in range(nbs + 1):
        y = -by + j * bay_s
        cols.setdefault((-bx, round(y, 4)), []).append((-1.0, 0.0))
        cols.setdefault((bx, round(y, 4)), []).append((1.0, 0.0))
    for (x, y), outs in cols.items():
        _column(b, x, y, zf, hc, col_r)
        _bracket(b, x, y, zc, outs, k, stepped)

    # ---- walls
    cdoor = nbf // 2
    nd = 1 if nbf <= 3 else (nbf - 2 if big else 1)
    kinds_f = ["door" if abs(i - cdoor) <= nd // 2 else "window" for i in range(nbf)]
    if big:
        kinds_s = ["window" if (nbs % 2 and j == nbs // 2) else "panel" for j in range(nbs)]
    else:
        kinds_s = ["panel"] * nbs
    walls = (("F", bx, by, nbf, kinds_f), ("B", bx, by, nbf, ["panel"] * nbf), ("R", by, bx, nbs, kinds_s),
             ("L", by, bx, nbs, kinds_s))
    for side, half, dist, nb, kinds in walls:
        fr = _Frame(b, side, dist)
        dz = 0.004 if side in "LR" else 0.0
        _wall(b, fr, half, nb, kinds, zf, hc, col_r, k, dz=dz)
        bay = 2 * half / nb
        # bracket zone: plaster frieze, struts, purlins
        fr.box(-half, half, -0.04, 0.04, zc - 0.06, z_sof + 0.12, PLASTER)
        fr.box(-half - 0.55 * k, half + 0.55 * k, -0.085 * k, 0.085 * k, zc + 0.49 * k + dz,
               zc + _SIMPLE_TOP * k + dz, RED, 0.014)
        for i in range(nb):
            ac = -half + (i + 0.5) * bay
            fr.box(ac - 0.07 * k, ac + 0.07 * k, -0.055, 0.06, zc - 0.05, zc + 0.37 * k, RED, 0.01)
            fr.box(ac - 0.105 * k, ac + 0.105 * k, -0.105 * k, 0.105 * k, zc + 0.36 * k, zc + 0.495 * k, RED, 0.01)
        if stepped:
            e = 0.6 * k
            fr.box(-half - e - 0.45 * k, half + e + 0.45 * k, e - 0.085 * k, e + 0.085 * k, zc + 0.8 * k + dz,
                   zc + _STEP_TOP * k + dz, RED, 0.014)
            if z_sof - 0.14 - (zc + _SIMPLE_TOP * k) > 0.3:
                fr.box(-half - 0.2, half + 0.2, -0.075, 0.09, z_sof - 0.14 - 0.17 + dz, z_sof - 0.11 + dz, RED, 0.012)
                m = nb * 3
                for q in range(m):
                    aq = -half + (q + 0.5) * 2 * half / m
                    fr.box(aq - 0.05, aq + 0.05, -0.05, 0.062, zc + _SIMPLE_TOP * k - 0.01, z_sof - 0.3, RED)

    # ---- roof
    roof_opt.update(dk=dk, d_in=d_in, rs=rs)
    st = _build_roof(b, R, roof_opt)

    # ---- veranda railing (open at the stairs)
    ri = 0.3
    rx, ry = hx - ri, hy - ri
    gap = steps_w * 0.5 + (cheek if cheek > 0 else 0.0) - 0.02
    kr = 1.0 if big else 0.85
    _railing(b, (-rx, -ry), (-gap, -ry), zf, rail_h, kr)
    _railing(b, (gap, -ry), (rx, -ry), zf, rail_h, kr)
    _railing(b, (rx, -ry), (rx, ry), zf, rail_h, kr)
    _railing(b, (-rx, ry), (-rx, -ry), zf, rail_h, kr)
    _railing(b, (rx, ry), (-rx, ry), zf, rail_h, kr)

    # ---- sockets
    ys = by + min(1.0, 0.55 * ver + 0.1)
    zs = lambda a: R.z("F", a, ey - ys) - st["t2"] - st["raf_h2"] - 0.012
    if big:
        xs = [-bx + (i + 0.5) * bay_f for i in range(nbf)]
        if len(xs) > 5:
            c = len(xs) // 2
            xs = xs[c - 2:c + 3]
    else:
        xs = [-bx + 0.5 * bay_f, bx - 0.5 * bay_f]
    sockets = [(x, -ys, zs(x)) for x in xs]
    drop = max(0.3, zs(0.0) - (zf + 0.66 * hc + 0.55))
    obj = b.finish(name)
    return _store(obj, (width, depth), sockets, drop, (0.0, -(by + 0.5 * ver), zf), zf, R)


def build_hall(width=16.0, depth=11.0, plinth=1.2, front_steps_width=6.0, name="PROP_TempleMain", seed=0):
    """Main temple hall with a hip-and-gable roof. Returns one mesh object (see the module docstring)."""
    return _hall(name, seed, width, depth, plinth, front_steps_width, True)


def build_hall_small(width=8.0, depth=7.0, plinth=0.6, name="PROP_HallSmall", seed=0):
    """Smaller hall in the same style: three front bays, simple brackets."""
    return _hall(name, seed, width, depth, plinth, None, False)


# ----------------------------------------------------------------------------------------------------------------
# corridor
# ----------------------------------------------------------------------------------------------------------------
def build_corridor(length=24.0, depth=5.0, plinth=0.6, name="PROP_Corridor", seed=0):
    """Long roofed gallery: open colonnade on the front (-Y), plaster and lattice wall at the back, gable roof."""
    b = _B(seed)
    hx, hy = length * 0.5, depth * 0.5
    col_r, hc, k, ov = 0.16, 3.0, 0.7, 1.5
    inset = 0.55
    bx, by = hx - 0.6, hy - inset
    nb = _odd_near(2 * bx / 2.6)
    bay = 2 * bx / nb
    zp = plinth
    zf = zp + 0.08
    zc = zf + hc
    ex, ey = hx + 0.45, by + ov
    R = _Roof(b, "gable", ex, ey, 0.6 * ey, lift=0.28, lift_r=3.0, sag=0.07)
    t2, raf_h2 = _ROOF_DEF["t2"], _ROOF_DEF["raf_h2"]
    R.z0 = zc + _SIMPLE_TOP * k + t2 + raf_h2 - R.f(ov)

    # podium, low steps on the three middle bays, plank floor
    sw = 3 * bay - 2 * col_r - 0.3
    _plinth(b, hx, hy, zp, skip=(-sw * 0.5 + 0.2, sw * 0.5 - 0.2))
    _stairs(b, sw, -hy - 0.03, zp, cheek=0.0)
    fe = 0.18
    _planks(b, -hx + fe, hx - fe, -hy + fe, hy - fe, zp - 0.01, zf, "y")
    for side, half, dist in (("F", hx - fe, hy - fe), ("B", hx - fe, hy - fe), ("R", hy - fe, hx - fe),
                             ("L", hy - fe, hx - fe)):
        dz = 0.004 if side in "LR" else 0.0
        _Frame(b, side, dist).box(-half - 0.05, half + 0.05, -0.05, 0.06, zp - 0.012, zf + 0.01 + dz, RED, 0.012)

    # columns, brackets, tie beams
    for i in range(nb + 1):
        x = -bx + i * bay
        end = i in (0, nb)
        _column(b, x, -by, zf, hc, col_r)
        _column(b, x, by, zf, hc, col_r)
        _bracket(b, x, -by, zc, [(0.0, -1.0)] + ([(-1.0 if i == 0 else 1.0, 0.0)] if end else []), k, False)
        _bracket(b, x, by, zc, [(0.0, 1.0)] + ([(-1.0 if i == 0 else 1.0, 0.0)] if end else []), k, False)
        b.box2((x - 0.09, -by, zc - 0.36), (x + 0.09, by, zc - 0.08), RED, 0.014)
        b.box2((x - 0.08, -by, zc + 0.47 * k), (x + 0.08, by, zc + _SIMPLE_TOP * k - 0.006), RED, 0.012)

    # front: open bays with a head tie and a low rail except at the steps; back: plaster panels and lattice
    front = _Frame(b, "F", by)
    _wall(b, front, bx, nb, ["open"] * nb, zf, hc, col_r, k)
    front.box(-bx - 0.5 * k, bx + 0.5 * k, -0.085 * k, 0.085 * k, zc + 0.49 * k, zc + _SIMPLE_TOP * k, RED, 0.014)
    back = _Frame(b, "F", -by)          # detailed face looks into the gallery (towards -Y)
    kinds = ["lattice" if i % 2 == 0 else "panel" for i in range(nb)]
    _wall(b, back, bx, nb, kinds, zf, hc, col_r, k, glow=False)
    z_sof = R.z0 + R.f(ov) - t2
    back.box(-bx, bx, -0.04, 0.04, zc - 0.06, z_sof + 0.1, PLASTER)
    back.box(-bx - 0.5 * k, bx + 0.5 * k, -0.085 * k, 0.085 * k, zc + 0.49 * k, zc + _SIMPLE_TOP * k, RED, 0.014)
    for i in range(nb):
        ac = -bx + (i + 0.5) * bay
        for fr in (front, back):
            fr.box(ac - 0.07 * k, ac + 0.07 * k, -0.055, 0.06, zc - 0.05, zc + 0.37 * k, RED, 0.01)
            fr.box(ac - 0.105 * k, ac + 0.105 * k, -0.105 * k, 0.105 * k, zc + 0.36 * k, zc + 0.495 * k, RED, 0.01)
        if abs(i - nb // 2) > 1:
            x0, x1 = -bx + i * bay + col_r + 0.02, -bx + (i + 1) * bay - col_r - 0.02
            _railing(b, (x0, -by), (x1, -by), zf, 0.75, 0.8, end0=False, end1=False)
    # end walls with one middle post, closed gables above
    for side in ("L", "R"):
        fr = _Frame(b, side, bx)
        _wall(b, fr, by, 2, ["panel", "panel"], zf, hc, col_r, k, dz=0.004)
        p = fr.pt(0.0, 0.0, 0.0)
        _column(b, p[0], p[1], zf, hc, col_r * 0.9)
        fr.box(-by, by, -0.04, 0.04, zc - 0.06, zc + _SIMPLE_TOP * k, PLASTER)
    for sx in (-1, 1):
        _gable_wall(b, R, sx * (bx + 0.01), sx, zc + 0.3, ov - 0.12, t2 - 0.05, PLASTER)
        b.box2((sx * bx - 0.07, -0.1, zc + 0.3), (sx * bx + 0.07, 0.1, R.z("F", sx * bx, ey) - 0.3), RED, 0.012)

    st = _build_roof(b, R, dict(dk=0.5 * ov, d_in=ey, rs=0.72, rib_dx=0.4, rib_r=0.078, course=0.36, dx=0.3,
                               raf_dx=0.34))
    ys = by + 0.7
    sockets = []
    for i in range(0, nb, 2):
        x = -bx + (i + 0.5) * bay
        sockets.append((x, -ys, R.z("F", x, ey - ys) - st["t2"] - st["raf_h2"] - 0.012))
    drop = max(0.3, sockets[len(sockets) // 2][2] - (zf + 0.66 * hc + 0.55))
    obj = b.finish(name)
    return _store(obj, (length, depth), sockets, drop, (0.0, -by + 0.4, zf), zf, R)


# ----------------------------------------------------------------------------------------------------------------
# pagoda (background silhouette)
# ----------------------------------------------------------------------------------------------------------------
def build_pagoda(tiers=3, name="PROP_Pagoda", seed=0):
    """Square multi-storey pagoda with stacked upturned roofs and a ringed finial. Low detail."""
    b = _B(seed)
    tiers = max(1, int(tiers))
    base_h, hb = 0.9, 3.9
    _plinth(b, hb, hb, base_h, skip=(-1.0, 1.0), avg=1.2)
    _stairs(b, 2.4, -hb - 0.03, base_h, cheek=0.34)
    z = base_h
    b0 = 2.45
    sockets, door, floor_z, R0 = [], (0.0, -b0 - 0.7, base_h), base_h, None
    opt = dict(course=0.5, rib_dx=0.5, rib_r=0.09, rib_seg=4, dx=0.5, disc_n=6, raf_dx=0.46, rs=0.62, t1=0.14,
               t2=0.27, raf_h1=0.11, raf_h2=0.13, raf_w=0.1)
    for i in range(tiers):
        last = i == tiers - 1
        bi = b0 * (1.0 - 0.13 * i)
        bn = b0 * (1.0 - 0.13 * (i + 1))
        hi = 3.2 if i == 0 else 1.9 - 0.08 * (i - 1)
        ov = 2.25 - 0.15 * i
        e = bi + ov
        r = 0.2 - 0.02 * i
        zc = z + hi
        # storey: dark core, 4 columns per side, tie rails, glowing centre bay on three sides
        b.box2((-bi + 0.06, -bi + 0.06, z - 0.3), (bi - 0.06, bi - 0.06, zc + 0.62), DARK)
        for side in "FBLR":
            fr = _Frame(b, side, bi)
            dz = 0.004 if side in "LR" else 0.0
            qs = range(4) if side in "FB" else (1, 2)
            for q in qs:
                a = -bi + 2 * bi * q / 3
                p = fr.pt(a, 0.0, 0.0)
                b.lathe((p[0], p[1], z - 0.05), [(r, 0.0), (r * 0.94, hi + 0.05)], 8, RED)
                fr.box(a - 0.17, a + 0.17, -0.17, 0.3, zc - 0.04, zc + 0.13, RED, 0.012)
            for zz in (0.12, 0.62 * hi, hi - 0.16):
                fr.box(-bi - 0.1, bi + 0.1, r - 0.06, r + 0.05, z + zz - 0.09 + dz, z + zz + 0.09 + dz, RED, 0.012)
            fr.box(-bi - 0.35, bi + 0.35, -0.1, 0.1, zc + 0.12 + dz, zc + 0.34 + dz, RED, 0.014)
            if side != "B":
                w = bi / 3 - r - 0.04
                fr.quad(-w, w, 0.07, z + 0.25, z + 0.62 * hi - 0.1, GLOW)
                nv = 5
                for q in range(1, nv):
                    a = -w + 2 * w * q / nv
                    fr.box(a - 0.025, a + 0.025, 0.075, 0.11, z + 0.22, z + 0.62 * hi - 0.08, DARK)
                fr.box(-w, w, 0.07, 0.105, z + 0.31 * hi - 0.03, z + 0.31 * hi + 0.03, DARK)
            for sgn in (-1, 1):
                a0, a1 = sgn * (bi / 3 + r), sgn * (bi - r)
                fr.box(min(a0, a1), max(a0, a1), 0.06, 0.09, z + 0.2, z + hi - 0.25, PLASTER)
        if i > 0:
            # balcony with a plain rail
            wb = bi + 0.62
            b.box2((-wb, -wb, z - 0.1), (wb, wb, z + 0.02), DARK, 0.012)
            for side in "FBLR":
                fr = _Frame(b, side, wb - 0.07)
                dz = 0.004 if side in "LR" else 0.0
                for zz in (0.22, 0.48):
                    fr.box(-wb + 0.02, wb - 0.02, -0.03, 0.03, z + zz - 0.03 + dz, z + zz + 0.03 + dz, RED)
                for q in (range(7) if side in "FB" else range(1, 6)):
                    a = -wb + 0.07 + (2 * wb - 0.14) * q / 6
                    fr.box(a - 0.04, a + 0.04, -0.04, 0.04, z, z + 0.56, RED)
        s = e if last else e - bn - 0.15
        d_in = min(ov + 0.12, s)
        R = _Roof(b, "skirt", e, e, (0.78 if last else 0.64) * e, s=s, lift=0.5 - 0.04 * i, lift_r=3.2 - 0.2 * i,
                  wave=0.008)
        R.z0 = zc + 0.34 + opt["t2"] + opt["raf_h2"] - R.f(ov)
        _build_roof(b, R, dict(opt, dk=0.5 * ov, d_in=d_in))
        if i == 0:
            R0 = R
            zs = R.z("F", bi * 0.5, e - (bi + 0.9)) - opt["t2"] - opt["raf_h2"] - 0.012
            sockets = [(-bi * 0.5, -(bi + 0.9), zs), (bi * 0.5, -(bi + 0.9), zs)]
        ztop = R.z0 + R.f(s)
        if not last:
            # tile flashing where the roof meets the next storey
            for side in "FBLR":
                fr = _Frame(b, side, bn + 0.12)
                dz = 0.004 if side in "LR" else 0.0
                fr.box(-bn - 0.25, bn + 0.25, -0.14, 0.14, ztop - 0.12, ztop + 0.12 + dz, TILE, 0.03)
            z = ztop + 0.1
        else:
            # finial: dew basin, inverted bowl, nine rings, flame and jewel
            zt = ztop - 0.25
            b.box((0.0, 0.0, zt + 0.2), (0.9, 0.9, 0.5), METAL, bevel=0.03)
            prof = [(0.36, 0.42), (0.42, 0.5), (0.34, 0.74), (0.14, 0.86), (0.2, 0.93), (0.07, 1.0)]
            zr = 1.05
            for q in range(9):
                rr = 0.36 - 0.022 * q
                prof += [(0.07, zr), (rr, zr + 0.03), (rr, zr + 0.11), (0.07, zr + 0.14)]
                zr += 0.3
            prof += [(0.07, zr), (0.18, zr + 0.12), (0.2, zr + 0.3), (0.06, zr + 0.42), (0.05, zr + 0.55),
                     (0.13, zr + 0.66), (0.1, zr + 0.8), (0.0, zr + 0.9)]
            mats = [METAL] * (len(prof) - 4) + [GOLD] * 3
            b.lathe((0.0, 0.0, zt), prof, 10, mats)
    obj = b.finish(name)
    return _store(obj, (2 * hb, 2 * hb), sockets, 0.9, door, floor_z, R0)


# ----------------------------------------------------------------------------------------------------------------
# perimeter wall
# ----------------------------------------------------------------------------------------------------------------
def build_perimeter_wall(length=10.0, height=2.4, name="PROP_Wall", seed=0):
    """Plaster wall on a stone base with a small tiled cap; runs along X, pieces butt end to end seamlessly."""
    b = _B(seed)
    r = b.rnd
    hx = length * 0.5
    base_h, base_t, wall_t = 0.5, 0.62, 0.42
    # stone base: two courses of through blocks
    for c in range(2):
        z0, z1 = c * base_h * 0.5, (c + 1) * base_h * 0.5
        t = -hx
        first = True
        while t < hx - 1e-6:
            ln = r.uniform(0.65, 1.15) * (0.6 if (first and c) else 1.0)
            first = False
            if hx - (t + ln) < 0.45:
                ln = hx - t
            off = r.uniform(-0.012, 0.012)
            b.box2((t + 0.004, -base_t * 0.5 - off, z0), (t + ln - 0.004, base_t * 0.5 + r.uniform(-0.012, 0.012),
                                                          z1 - r.uniform(0.0, 0.005)), MOSSY if c == 0 else STONE,
                   0.02 * r.uniform(0.7, 1.4))
            t += ln
    b.box2((-hx, -base_t * 0.5 + 0.05, 0.02), (hx, base_t * 0.5 - 0.05, base_h - 0.02), MOSSY)
    ex, ey, rs = hx, 0.66, 0.42
    rise = 0.34
    hr = 0.5 * rs + 0.1 * rs
    R = _Roof(b, "gable", ex, ey, rise, lift=0.0, sag=0.0, wave=0.004, a=0.6)
    R.z0 = height - hr - rise
    z_top = R.z0 + 0.12                 # hidden inside the tile cap
    z_head = R.z0 + 0.03
    b.box2((-hx, -wall_t * 0.5, base_h - 0.02), (hx, wall_t * 0.5, z_top), PLASTER)
    # timber sill, head rail and posts on both faces
    n = max(1, int(round(length / 2.5)))
    for sy in (-1, 1):
        y0, y1 = sorted((sy * (wall_t * 0.5 - 0.02), sy * (wall_t * 0.5 + 0.035)))
        b.box2((-hx, y0, base_h - 0.01), (hx, y1, base_h + 0.13), DARK)
        b.box2((-hx, y0, z_head - 0.17), (hx, y1, z_head), DARK)
        for i in range(n):
            x = -hx + (i + 0.5) * length / n
            ya, yb = sorted((sy * (wall_t * 0.5 - 0.02), sy * (wall_t * 0.5 + 0.05)))
            b.box2((x - 0.075, ya, base_h + 0.12), (x + 0.075, yb, z_head - 0.16), DARK, 0.01)
    _build_roof(b, R, dict(es=0.6, t1=0.09, t2=0.12, dk=0.3, d_in=ey, raf=False, rs=rs, verge=False, ends=False,
                           rib_half=True, rib_dx=0.34, rib_r=0.065, rib_seg=4, disc_n=6, verge_margin=0.0,
                           course=ey, dx=0.55, step=0.02))
    # flat closures so a free end is not hollow
    for sx in (-1, 1):
        x = sx * (hx - 0.006)
        zr = R.z("F", x, ey)
        ze = R.z("F", x, 0.0)
        pts = [(-ey, ze - 0.035), (-ey, ze + 0.02), (0.0, zr), (ey, ze + 0.02), (ey, ze - 0.035),
               (wall_t * 0.5, z_top - 0.04), (-wall_t * 0.5, z_top - 0.04)]
        b.face([b.v((x, y, z)) for y, z in pts], DARK, (sx, 0.0, 0.0))
    obj = b.finish(name)
    return _store(obj, (length, base_t), [], 0.0, (0.0, -base_t * 0.5 - 0.5, 0.0), 0.0, R)
