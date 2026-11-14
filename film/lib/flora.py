"""Cherry trees, overhanging blossom branches and background pines (procedural meshes, Blender 5.3 headless).

Public builders (each returns ONE mesh object linked to the scene collection, nothing is rendered or saved):
    build_cherry_tree(height=9.0, spread=7.5, seed=0, name=None, *, flowers=100000)
    build_cherry_branch(length=3.5, seed=0, name=None, *, flowers=6000)
    build_pine(height=14.0, seed=0, name=None)

Why procedural: the Poly Haven jacaranda (the only CC0 tree in the cache) has green fern-leaf alpha cards and no
flowers, 1.85 M triangles at LOD1 and alpha-hashed foliage; tinted pink it reads as a sparse mauve fern tree, not
as a cherry in bloom. These trees are solid geometry (no alpha), so they are cheap for Cycles on CPU.

Mesh sharing: the mesh of a tree / branch / pine is cached in the current file by (kind, seed, detail).
Calling a builder again with the same seed returns a new object that SHARES the mesh; a different height / spread
with the same seed only changes the object scale (the mesh keeps the size of its first build).
"""
import math

import bpy
import numpy as np
from mathutils import Vector, noise

from . import common, materials

TAU = 2.0 * math.pi
GOLDEN = 2.399963


# ------------------------------------------------------------------------------------------------ small helpers
def _perp(v):
    ref = Vector((0.0, 0.0, 1.0)) if abs(v.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    return v.cross(ref).normalized()


def _dir_from(d, angle, azimuth):
    """Unit vector at `angle` from d, turned by `azimuth` around d."""
    u = _perp(d)
    v = d.cross(u)
    side = u * math.cos(azimuth) + v * math.sin(azimuth)
    return (d * math.cos(angle) + side * math.sin(angle)).normalized()


def _cached(key):
    for me in bpy.data.meshes:
        if me.get("flora_key") == key:
            return me
    return None


class _Skel:
    """A branching skeleton: branches = [(points, radii, level)], points are Vectors."""

    def __init__(self, R):
        self.R = R
        self.branches = []
        self.phase = Vector((R.uniform(-90, 90), R.uniform(-90, 90), R.uniform(-90, 90)))


def _axis(T, start, d0, length, r0, level, lv, pre=None):
    """Grow one branch axis from `start` along d0 and, recursively, its side branches.

    lv[level] holds the growth rules of this level:
        seg      node spacing (m)                 wander / wfreq  smooth meander strength (per metre) and frequency
        r_tip    radius at the tip                taper           exponent of the radius falloff
        trop     f(t, d, p) -> Vector added to the direction per metre of growth (gravity, light, reach)
        kink     how hard the axis turns away from each side branch (zigzag of old fruit wood)
        scale    size factor of the plant (rules are written for scale 1)
        child    None or dict(first, last, gap=(lo, hi), angle=(lo, hi) degrees,
                              length=f(parent_length, t), radius=f(parent_radius), shape=f(dir, p) -> dir)
    """
    R = T.R
    L = lv[level]
    n = max(2, int(round(length / L["seg"])))
    step = length / n
    pts = list(pre[0]) if pre else []
    rad = list(pre[1]) if pre else []
    pts.append(start.copy())
    rad.append(r0)
    spawn = set()
    ch = L.get("child")
    if ch is not None and level + 1 < len(lv):
        s = length * ch["first"] + R.uniform(0.0, ch["gap"][0])
        while s < length * ch["last"]:
            spawn.add(max(1, int(round(s / step))))
            s += R.uniform(*ch["gap"])
    d = d0.normalized()
    p = start.copy()
    az = R.uniform(0.0, TAU)
    phase = T.phase + Vector((R.uniform(-40, 40), R.uniform(-40, 40), R.uniform(-40, 40)))
    pending = []
    for i in range(1, n + 1):
        t = i / n
        w = noise.noise_vector(p * L["wfreq"] + phase)
        d = d + (w * L["wander"] + L["trop"](t, d, p)) * (step / L["scale"])
        d.normalize()
        p = p + d * step
        r = L["r_tip"] + (r0 - L["r_tip"]) * (1.0 - t) ** L["taper"]
        pts.append(p.copy())
        rad.append(r)
        if i in spawn and i < n:
            az += GOLDEN + R.uniform(-0.7, 0.7)
            ang = math.radians(R.uniform(*ch["angle"]))
            cd = ch["shape"](_dir_from(d, ang, az), p)
            pending.append((p.copy(), cd, r, t))
            side = cd - d * cd.dot(d)
            d = (d - side * L["kink"]).normalized()
    T.branches.append((pts, rad, level))
    for (cp, cd, pr, t) in pending:
        _axis(T, cp, cd, ch["length"](length, t), ch["radius"](pr), level + 1, lv)


# ------------------------------------------------------------------------------------------------ bark mesh
def _sides(r, fine):
    if r >= 0.10:
        return 16 if fine else 14
    if r >= 0.045:
        return 12 if fine else 10
    if r >= 0.018:
        return 8 if fine else 7
    if r >= 0.007:
        return 6 if fine else 5
    return 4 if fine else 3


def _bridge(faces, a, b):
    (sa, na), (sb, nb) = a, b
    if na == nb:
        for k in range(na):
            k2 = (k + 1) % na
            faces.append((sa + k, sa + k2, sb + k2, sb + k))
        return
    i = j = 0
    while i < na or j < nb:
        if j >= nb or (i < na and (i + 1) * nb <= (j + 1) * na):
            faces.append((sa + i % na, sa + (i + 1) % na, sb + j % nb))
            i += 1
        else:
            faces.append((sa + i % na, sb + (j + 1) % nb, sb + j % nb))
            j += 1


def _sweep(verts, faces, pts, rad, phase, fine=False, cap_base=False, flare=None, relief=True, sides=None):
    """Tube along a polyline with a ring count that follows the radius, a pointed tip and bark relief."""
    n = len(pts)
    nrm = None
    prev = None
    dist = 0.0
    lobes = None
    if flare:
        lobes = flare["lobes"]
    for i in range(n):
        a_pt = pts[max(i - 1, 0)]
        b_pt = pts[min(i + 1, n - 1)]
        t = (b_pt - a_pt).normalized()
        if nrm is None:
            nrm = _perp(t)
        nrm = (nrm - t * nrm.dot(t)).normalized()
        bn = t.cross(nrm)
        if i > 0:
            dist += (pts[i] - pts[i - 1]).length
        if i == n - 1 and prev is not None:
            vi = len(verts)
            verts.append(tuple(pts[i]))
            ps, pc = prev
            for k in range(pc):
                faces.append((ps + k, ps + (k + 1) % pc, vi))
            break
        r = rad[i]
        m = sides or _sides(r, fine)
        gn = (0.11 if r > 0.05 else (0.05 if r > 0.02 else 0.0)) if relief else 0.0
        fl = 0.0
        if flare:
            fl = math.exp(-max(pts[i].z, 0.0) / flare["height"])
        start = len(verts)
        for k in range(m):
            a = TAU * k / m
            ca, sa = math.cos(a), math.sin(a)
            f = 1.0
            if gn:
                q = Vector((ca * 1.4, sa * 1.4, dist * 1.3)) + phase
                f += gn * 2.0 * noise.noise(q)                                   # slow swelling and hollows
                f += gn * 0.9 * noise.noise(Vector((ca * 4.0, sa * 4.0, dist * 0.45)) - phase)   # long ridges
            if fl:
                f *= 1.0 + fl * (flare["gain"] + flare["lobe_gain"] * (0.5 + 0.5 * math.cos(lobes * a + flare["turn"]))
                                 + 0.25 * noise.noise(Vector((ca * 2.0, sa * 2.0, 7.0)) + phase))
            verts.append(tuple(pts[i] + (nrm * ca + bn * sa) * (r * f)))
        if prev is not None:
            _bridge(faces, prev, (start, m))
        elif cap_base:
            faces.append(tuple(range(start + m - 1, start - 1, -1)))
        prev = (start, m)


def _bark_part(T, fine=False, cap_first=False, flare=None):
    verts, faces = [], []
    for bi, (pts, rad, level) in enumerate(T.branches):
        root = level == 0
        _sweep(verts, faces, pts, rad, T.phase + Vector((bi * 3.7, bi * 1.3, 0.0)), fine=fine,
               cap_base=root and (cap_first or flare is not None), flare=flare if root else None)
    co = np.array(verts, dtype=np.float32).reshape(-1, 3)
    total = np.fromiter((len(f) for f in faces), dtype=np.int32, count=len(faces))
    loops = np.fromiter((i for f in faces for i in f), dtype=np.int32, count=int(total.sum()))
    return co, total, loops


# ------------------------------------------------------------------------------------------------ blossom
def _flower_template(fine):
    """Five petals around a shared centre vertex, +Z = the way the flower faces, radius 1."""
    V = [(0.0, 0.0, 0.0)]
    F = []
    for k in range(5):
        a = TAU * k / 5.0

        def pt(r, da, z):
            return (r * math.cos(a + da), r * math.sin(a + da), z)

        i = len(V)
        if fine:   # notched sakura petal with a fold along the midrib
            V += [pt(0.58, -0.58, 0.21), pt(0.98, -0.25, 0.30), pt(0.85, 0.0, 0.17), pt(0.98, 0.25, 0.30), pt(0.58, 0.58, 0.21)]
            F += [(0, i, i + 1), (0, i + 1, i + 2), (0, i + 2, i + 3), (0, i + 3, i + 4)]
        else:      # wedge petal, one triangle (widest at the tip like a real cherry petal)
            V += [pt(1.0, -0.50, 0.30), pt(1.0, 0.50, 0.30)]
            F += [(0, i, i + 1)]
    return np.array(V, dtype=np.float32), np.array(F, dtype=np.int32)


def _bud_template():
    V = [(0.0, 0.0, 0.0), (0.45, 0.0, 0.7), (0.0, 0.45, 0.7), (-0.45, 0.0, 0.7), (0.0, -0.45, 0.7), (0.0, 0.0, 1.6)]
    F = [(0, 2, 1), (0, 3, 2), (0, 4, 3), (0, 1, 4), (5, 1, 2), (5, 2, 3), (5, 3, 4), (5, 4, 1)]
    return np.array(V, dtype=np.float32), np.array(F, dtype=np.int32)


def _stamp(template, rows):
    """Copy a template to every row of (px, py, pz, nx, ny, nz, size, spin, open)."""
    TV, TF = template
    if not rows:
        return np.zeros((0, 3), np.float32), np.zeros(0, np.int32), np.zeros(0, np.int32)
    A = np.array(rows, dtype=np.float64)
    pos, nrm, size, spin, opn = A[:, 0:3], A[:, 3:6], A[:, 6], A[:, 7], A[:, 8]
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    ref = np.where(np.abs(nrm[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    u = np.cross(ref, nrm)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(nrm, u)
    c, s = np.cos(spin)[:, None], np.sin(spin)[:, None]
    uu = u * c + v * s
    vv = v * c - u * s
    tv = TV.astype(np.float64)
    co = (pos[:, None, :] + size[:, None, None] * (
        tv[None, :, 0:1] * uu[:, None, :] + tv[None, :, 1:2] * vv[:, None, :]
        + (tv[None, :, 2:3] * opn[:, None, None]) * nrm[:, None, :]))
    n, nv = len(rows), len(TV)
    loops = (np.arange(n, dtype=np.int32)[:, None] * nv + TF.ravel()[None, :]).ravel()
    total = np.full(n * len(TF), TF.shape[1], dtype=np.int32)
    return co.reshape(-1, 3).astype(np.float32), total, loops.astype(np.int32)


def _flower_rows(T, R, target, per_cluster, min_level, r_limit, pedicel, size, bud_share=0.0):
    """Flower clusters along every thin twig. Returns (flower rows, bud rows); about `target` flowers."""
    segs = []
    total_len = 0.0
    for pts, rad, level in T.branches:
        if level < min_level:
            continue
        for i in range(len(pts) - 1):
            if rad[i] > r_limit:
                continue
            seg = pts[i + 1] - pts[i]
            ln = seg.length
            if ln > 1e-6:
                segs.append((pts[i], seg / ln, ln, i == len(pts) - 2))
                total_len += ln
    mean_k = 0.5 * (per_cluster[0] + per_cluster[1])
    spacing = max(0.012, total_len * mean_k / max(target, 1))
    flowers, buds = [], []
    carry = R.uniform(0.0, spacing)
    down = Vector((0.0, 0.0, -1.0))
    for (a, t, ln, last) in segs:
        u = _perp(t)
        v = t.cross(u)
        s = carry
        while s < ln:
            p = a + t * s
            for _ in range(R.randint(*per_cluster)):
                ang = R.uniform(0.0, TAU)
                radial = u * math.cos(ang) + v * math.sin(ang)
                pos = p + radial * R.uniform(*pedicel) + t * R.uniform(-0.03, 0.03)
                nrm = radial + t * R.uniform(-0.55, 0.55) + down * 0.2 + Vector((R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3)))
                if bud_share and R.random() < bud_share:
                    buds.append((pos.x, pos.y, pos.z, nrm.x, nrm.y, nrm.z, R.uniform(0.006, 0.009), R.uniform(0.0, TAU), 1.0))
                else:
                    flowers.append((pos.x, pos.y, pos.z, nrm.x, nrm.y, nrm.z, R.uniform(*size), R.uniform(0.0, TAU), R.uniform(0.25, 1.5)))
            s += spacing * R.uniform(0.55, 1.45)
        carry = s - ln
    return flowers, buds


def _mesh(name, parts, mats):
    """parts: [(co (V,3), loop_total (F,), loop_vertex (sum,), material index)] -> one mesh, smooth shaded."""
    parts = [p for p in parts if len(p[0])]
    co = np.concatenate([p[0] for p in parts])
    total = np.concatenate([p[1] for p in parts])
    off = 0
    loops, mat_idx = [], []
    for (pc, pt, pl, mi) in parts:
        loops.append(pl + off)
        mat_idx.append(np.full(len(pt), mi, dtype=np.int32))
        off += len(pc)
    loops = np.concatenate(loops).astype(np.int32)
    mat_idx = np.concatenate(mat_idx)
    start = np.zeros(len(total), dtype=np.int32)
    np.cumsum(total[:-1], out=start[1:])
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.ravel())
    me.loops.add(len(loops))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(total))
    me.polygons.foreach_set("loop_start", start)
    me.polygons.foreach_set("loop_total", total)
    me.polygons.foreach_set("material_index", mat_idx)
    me.update(calc_edges=True)
    me.validate()
    for m in mats:
        me.materials.append(m)
    me.shade_smooth()
    return me


def _tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# ------------------------------------------------------------------------------------------------ cherry tree
def _tree_levels(S, R, height):
    """Growth rules of a spreading old cherry (limb -> bough -> branch -> twig); S = height / 9."""
    up = Vector((0.0, 0.0, 1.0))
    floor = 0.24 * height          # nothing hangs lower than this

    def out_of(p):
        h = Vector((p.x, p.y, 0.0))
        return h.normalized() if h.length > 0.3 * S else Vector((0.0, 0.0, 0.0))

    def lift(p):
        return up * (1.2 * min(1.0, (floor - p.z) / (0.1 * height))) if p.z < floor else Vector((0.0, 0.0, 0.0))

    def trop_limb(t, d, p):       # rise, then arch outwards
        return up * (0.12 * (0.5 - t)) + out_of(p) * 0.05 + lift(p)

    def trop_bough(t, d, p):      # reach sideways, tips sag a little
        return Vector((0.0, 0.0, -d.z * 0.22 - 0.05 * t)) + lift(p)

    def trop_branch(t, d, p):
        return Vector((0.0, 0.0, -0.05)) + lift(p)

    def trop_twig(t, d, p):       # young wood turns up to the light
        return up * 0.45 + lift(p)

    def shape_bough(cd, p):       # sideways and outwards rather than back into the crown
        o = out_of(p)
        v = Vector((cd.x, cd.y, cd.z * 0.6 + 0.10))
        if v.dot(o) < -0.25:
            v = v - o * (1.5 * v.dot(o))
        return v.normalized()

    def shape_branch(cd, p):
        return Vector((cd.x, cd.y, cd.z * 0.75 + 0.05)).normalized()

    def shape_twig(cd, p):
        return Vector((cd.x, cd.y, cd.z * 0.8 + 0.15)).normalized()

    return [
        {},   # level 0 (trunk + leader) uses the limb rules
        {"scale": S, "seg": 0.16 * S, "wander": 0.70, "wfreq": 0.45 / S, "r_tip": 0.011, "taper": 1.05, "trop": trop_limb, "kink": 0.22,
         "child": {"first": 0.12, "last": 0.97, "gap": (0.40 * S, 0.62 * S), "angle": (42, 74),
                   "length": lambda pl, t: S * R.uniform(1.9, 3.3) * (1.0 - 0.45 * t),
                   "radius": lambda pr: min(0.07, max(0.016, pr * R.uniform(0.40, 0.58))), "shape": shape_bough}},
        {"scale": S, "seg": 0.13 * S, "wander": 0.9, "wfreq": 0.8 / S, "r_tip": 0.007, "taper": 0.95, "trop": trop_bough, "kink": 0.22,
         "child": {"first": 0.14, "last": 0.97, "gap": (0.22 * S, 0.36 * S), "angle": (38, 72),
                   "length": lambda pl, t: S * R.uniform(0.7, 1.5) * (1.0 - 0.45 * t),
                   "radius": lambda pr: min(0.022, max(0.008, pr * R.uniform(0.40, 0.55))), "shape": shape_branch}},
        {"scale": S, "seg": 0.10 * S, "wander": 1.3, "wfreq": 1.5 / S, "r_tip": 0.004, "taper": 0.9, "trop": trop_branch, "kink": 0.25,
         "child": {"first": 0.12, "last": 0.96, "gap": (0.10 * S, 0.19 * S), "angle": (36, 72),
                   "length": lambda pl, t: S * R.uniform(0.28, 0.68) * (1.0 - 0.35 * t),
                   "radius": lambda pr: min(0.007, max(0.004, pr * 0.5)), "shape": shape_twig}},
        {"scale": S, "seg": 0.085 * S, "wander": 1.8, "wfreq": 3.0 / S, "r_tip": 0.0026, "taper": 0.85, "trop": trop_twig, "kink": 0.0, "child": None},
    ]


def _tree_skeleton(height, spread, seed):
    R = common.rng(977 * int(seed) + 11)
    T = _Skel(R)
    S = height / 9.0
    lv = _tree_levels(S, R, height)
    trunk_h = height * R.uniform(0.17, 0.24)
    r_base = 0.030 * height * R.uniform(0.85, 1.08)
    lean = math.radians(R.uniform(3.0, 11.0))
    laz = R.uniform(0.0, TAU)
    d = Vector((math.sin(lean) * math.cos(laz), math.sin(lean) * math.sin(laz), math.cos(lean)))
    sink = 0.35
    p = -d * (sink / d.z)
    seg = 0.10 * S
    n_tr = max(6, int(round((trunk_h + sink) / seg)))
    n_limbs = R.choice([3, 4, 4, 5])
    base_az = R.uniform(0.0, TAU)
    laterals = []
    for k in range(1, n_limbs):
        laterals.append({"az": base_az + TAU * k / n_limbs + R.uniform(-0.35, 0.35), "incl": math.radians(R.uniform(40.0, 64.0)),
                         "node": int(round(n_tr * R.uniform(0.80, 0.98))), "r": r_base * R.uniform(0.47, 0.60)})
    pts, rad = [], []
    starts = []
    for i in range(n_tr + 1):
        pts.append(p.copy())
        rad.append(r_base * (1.0 - 0.18 * i / n_tr))
        for lat in laterals:
            if lat["node"] == i:
                starts.append((p.copy(), lat))
        if i < n_tr:
            d = (d + noise.noise_vector(p * 0.8 + T.phase) * 0.10).normalized()
            p = p + d * seg
    reach = (spread * 0.5) * 0.92
    rise = (height - trunk_h) * 0.95

    def limb_len(incl):
        return min(reach / max(math.sin(incl), 0.2), rise / max(math.cos(incl), 0.2)) * R.uniform(0.85, 1.0)

    # the leader carries on from the trunk as one continuous tube
    incl = math.radians(R.uniform(16.0, 32.0))
    az = base_az + R.uniform(-0.3, 0.3)
    ld = Vector((math.sin(incl) * math.cos(az), math.sin(incl) * math.sin(az), math.cos(incl)))
    ld = (d * 0.35 + ld * 0.65).normalized()
    _axis(T, pts[-1], ld, limb_len(incl), r_base * 0.60, 1, lv, pre=(pts[:-1], rad[:-1]))
    T.branches[0] = (T.branches[0][0], T.branches[0][1], 0)       # _axis appends the parent before its children
    for (sp, lat) in starts:
        ldir = Vector((math.sin(lat["incl"]) * math.cos(lat["az"]), math.sin(lat["incl"]) * math.sin(lat["az"]), math.cos(lat["incl"])))
        _axis(T, sp, ldir, limb_len(lat["incl"]), lat["r"], 1, lv)
    # fit the crown to the requested envelope (radii are kept)
    allp = [q for b in T.branches for q in b[0]]
    zmax = max(q.z for q in allp)
    ext = max(max(q.x for q in allp) - min(q.x for q in allp), max(q.y for q in allp) - min(q.y for q in allp))
    sx = (spread - 0.08) / ext
    sz = (height - 0.05) / zmax
    for q in allp:
        q.x *= sx
        q.y *= sx
        if q.z > 0.0:
            q.z *= sz
    T.fit = (round(sx, 3), round(sz, 3))
    T.r_base = r_base
    return T


def _crown(T, min_level=2):
    pts = [q for b in T.branches if b[2] >= min_level for q in b[0]]
    lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
    hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
    return (lo + hi) * 0.5, (hi - lo) * 0.5


def build_cherry_tree(height=9.0, spread=7.5, seed=0, name=None, *, flowers=100000):
    """Old spreading cherry in full bloom. One object, origin at the trunk base (the trunk continues 0.35 m below
    it), +Z up. Slots: MAT_Bark, MAT_Blossom. `flowers` is the approximate number of 5-petal flowers (5 triangles
    each). Custom properties: height, spread, seed, tris, crown_center [x, y, z] and crown_radius [rx, ry, rz]
    (local space, before the object scale)."""
    key = f"cherry_tree:{int(seed)}:{int(flowers)}"
    me = _cached(key)
    if me is None:
        T = _tree_skeleton(height, spread, seed)
        R = common.rng(977 * int(seed) + 12)
        flare = {"height": 0.20 * height / 9.0, "gain": 0.30, "lobe_gain": 0.40, "lobes": R.choice([4, 5, 5, 6]), "turn": R.uniform(0.0, TAU)}
        bark = _bark_part(T, flare=flare)
        rows, _ = _flower_rows(T, R, flowers, (3, 6), 3, 0.0085, (0.02, 0.085), (0.017, 0.025))
        fl = _stamp(_flower_template(False), rows)
        me = _mesh(f"PROP_CherryTree_s{int(seed)}", [(*bark, 0), (*fl, 1)], [materials.get("MAT_Bark"), materials.get("MAT_Blossom")])
        c, r = _crown(T)
        me["flora_key"] = key
        me["built_height"] = float(height)
        me["built_spread"] = float(spread)
        me["tris"] = _tris(me)
        me["flower_count"] = len(rows)
        me["fit"] = list(T.fit)
        me["crown_center"] = [round(v, 3) for v in c]
        me["crown_radius"] = [round(v, 3) for v in r]
    obj = common.mesh_object(name or f"PROP_CherryTree_s{int(seed)}", me)
    sxy = spread / me["built_spread"]
    obj.scale = (sxy, sxy, height / me["built_height"])
    if "sharp_done" not in me:
        common.set_smooth(obj, 50.0)
        me["sharp_done"] = True
    obj["height"], obj["spread"], obj["seed"], obj["tris"] = float(height), float(spread), int(seed), me["tris"]
    obj["crown_center"] = list(me["crown_center"])
    obj["crown_radius"] = list(me["crown_radius"])
    return obj


# ------------------------------------------------------------------------------------------------ blossom branch
def _branch_levels(S, R):
    """Growth rules of one overhanging limb (main -> side branch -> twig -> spur); S = length / 3.5."""
    up = Vector((0.0, 0.0, 1.0))

    def trop_main(t, d, p):       # leaves the trunk rising a little, then arcs over and hangs
        return up * (0.05 - 0.42 * t)

    def trop_side(t, d, p):
        return Vector((0.0, 0.0, -d.z * 0.3 - 0.10 * t))

    def trop_twig(t, d, p):
        return up * 0.35

    def shape_side(cd, p):        # a flat spray, like the reference branch
        return Vector((cd.x + 0.25, cd.y, cd.z * 0.45 + 0.03)).normalized()

    def shape_twig(cd, p):
        return Vector((cd.x + 0.1, cd.y, cd.z * 0.7 + 0.05)).normalized()

    def shape_spur(cd, p):
        return Vector((cd.x, cd.y, cd.z + 0.1)).normalized()

    return [
        {"scale": S, "seg": 0.10 * S, "wander": 1.0, "wfreq": 0.8 / S, "r_tip": 0.008, "taper": 1.1, "trop": trop_main, "kink": 0.28,
         "child": {"first": 0.10, "last": 0.97, "gap": (0.22 * S, 0.38 * S), "angle": (40, 72),
                   "length": lambda pl, t: S * R.uniform(0.8, 1.6) * (1.0 - 0.55 * t),
                   "radius": lambda pr: min(0.03, max(0.009, pr * R.uniform(0.38, 0.55))), "shape": shape_side}},
        {"scale": S, "seg": 0.09 * S, "wander": 1.2, "wfreq": 1.4 / S, "r_tip": 0.0045, "taper": 0.9, "trop": trop_side, "kink": 0.24,
         "child": {"first": 0.12, "last": 0.97, "gap": (0.11 * S, 0.20 * S), "angle": (36, 70),
                   "length": lambda pl, t: S * R.uniform(0.25, 0.62) * (1.0 - 0.4 * t),
                   "radius": lambda pr: min(0.008, max(0.004, pr * 0.45)), "shape": shape_twig}},
        {"scale": S, "seg": 0.07 * S, "wander": 1.8, "wfreq": 2.6 / S, "r_tip": 0.0028, "taper": 0.9, "trop": trop_twig, "kink": 0.24,
         "child": {"first": 0.15, "last": 0.95, "gap": (0.09 * S, 0.17 * S), "angle": (35, 75),
                   "length": lambda pl, t: S * R.uniform(0.07, 0.20),
                   "radius": lambda pr: R.uniform(0.0024, 0.0030), "shape": shape_spur}},
        {"scale": S, "seg": 0.055 * S, "wander": 1.5, "wfreq": 4.0 / S, "r_tip": 0.0018, "taper": 0.6, "trop": trop_twig, "kink": 0.0, "child": None},
    ]


def build_cherry_branch(length=3.5, seed=0, name=None, *, flowers=6000):
    """One overhanging blossom branch for the top corners of a frame. Origin at the centre of the cut end, the
    branch grows along +X (about `length` metres), spreads mostly in the XY plane and hangs slightly at the tip.
    Close-up detail: notched petals (20 triangles a flower) and buds. Slots: MAT_Bark, MAT_Blossom.
    Custom properties: length, seed, tris, tip [x, y, z] (local position of the far end)."""
    key = f"cherry_branch:{int(seed)}:{int(flowers)}:{round(float(length), 3)}"
    me = _cached(key)
    if me is None:
        R = common.rng(613 * int(seed) + 5)
        T = _Skel(R)
        S = length / 3.5
        lv = _branch_levels(S, R)
        d0 = Vector((1.0, R.uniform(-0.08, 0.08), R.uniform(0.14, 0.28))).normalized()
        _axis(T, Vector((0.0, 0.0, 0.0)), d0, length * 1.04, 0.019 * length * R.uniform(0.9, 1.1), 0, lv)
        # the far end defines +X and the length
        main = T.branches[0][0]
        tip = main[-1]
        yaw = math.atan2(tip.y, tip.x)
        cy, sy = math.cos(-yaw), math.sin(-yaw)
        allp = [q for b in T.branches for q in b[0]]
        for q in allp:
            q.x, q.y = q.x * cy - q.y * sy, q.x * sy + q.y * cy
        # pitch the whole branch so that the far end hangs a little below the cut end
        pitch = math.atan2(tip.z, tip.x) - math.radians(R.uniform(-7.0, -2.0))
        cp, sp = math.cos(-pitch), math.sin(-pitch)
        for q in allp:
            q.x, q.z = q.x * cp - q.z * sp, q.x * sp + q.z * cp
        k = length / max(q.x for q in allp)
        for q in allp:
            q.x *= k
        bark = _bark_part(T, fine=True, cap_first=True)
        rows, buds = _flower_rows(T, R, flowers / 0.88, (4, 8), 1, 0.0085, (0.016, 0.045), (0.017, 0.025), bud_share=0.12)
        fl = _stamp(_flower_template(True), rows)
        bd = _stamp(_bud_template(), buds)
        me = _mesh(f"PROP_CherryBranch_s{int(seed)}", [(*bark, 0), (*fl, 1), (*bd, 1)], [materials.get("MAT_Bark"), materials.get("MAT_Blossom")])
        me["flora_key"] = key
        me["tris"] = _tris(me)
        me["flower_count"] = len(rows)
        me["tip"] = [round(v, 3) for v in main[-1]]
    obj = common.mesh_object(name or f"PROP_CherryBranch_s{int(seed)}", me)
    if "sharp_done" not in me:
        common.set_smooth(obj, 50.0)
        me["sharp_done"] = True
    obj["length"], obj["seed"], obj["tris"] = float(length), int(seed), me["tris"]
    obj["tip"] = list(me["tip"])
    return obj


# ------------------------------------------------------------------------------------------------ pine
def build_pine(height=14.0, seed=0, name=None):
    """Dark background conifer (cedar-like silhouette): bare lower trunk, drooping layered boughs with a ragged
    outline, pointed top. Low detail (about 5k triangles), one slot: MAT_Pine_Dark. Origin at the trunk base."""
    key = f"pine:{int(seed)}"
    me = _cached(key)
    if me is None:
        R = common.rng(431 * int(seed) + 3)
        H = float(height)
        verts, faces = [], []
        # trunk: a gently bent, tapered tube
        bend_az = R.uniform(0.0, TAU)
        bend = R.uniform(0.0, 0.035) * H
        r0 = 0.016 * H * R.uniform(0.9, 1.15)

        def axis(z):
            u = z / H
            off = bend * math.sin(u * math.pi * R_bend) * (1.0 - u * 0.3)
            return Vector((math.cos(bend_az) * off, math.sin(bend_az) * off, z))

        R_bend = R.uniform(0.8, 1.6)
        rings = 9
        tp, tr = [], []
        for i in range(rings + 1):
            u = i / rings
            z = -0.3 + (H * 0.985 + 0.3) * u
            tp.append(axis(z))
            tr.append(max(0.012, r0 * (1.0 - u) ** 0.85 + 0.01))
        _sweep(verts, faces, tp, tr, Vector((seed * 1.7, 0.3, 0.9)), cap_base=True, sides=7)
        # boughs in tiers
        z0 = H * R.uniform(0.16, 0.27)
        rmax = H * R.uniform(0.15, 0.19)
        z = z0
        tier = 0
        while z < H * 0.965:
            u = (z - z0) / (H - z0)
            rad = rmax * ((1.0 - u) ** 0.8) * R.uniform(0.78, 1.12) + 0.12
            if tier < 2:
                rad *= 0.55 + 0.25 * tier                      # ragged, thin skirt at the bottom
            nb = max(5, int(round(11.0 - 5.0 * u + R.uniform(-1.0, 1.0))))
            a0 = R.uniform(0.0, TAU)
            c = axis(z)
            for k in range(nb):
                if tier < 3 and R.random() < 0.3:
                    continue
                az = a0 + TAU * k / nb + R.uniform(-0.3, 0.3)
                ln = rad * R.uniform(0.7, 1.15)
                wid = ln * R.uniform(0.42, 0.62) + 0.12
                droop = R.uniform(0.45, 0.80) * (1.0 - 0.5 * u)
                lift = R.uniform(0.05, 0.20)
                dirv = Vector((math.cos(az), math.sin(az), 0.0))
                roll = R.uniform(-0.35, 0.35)
                side = Vector((-math.sin(az) * math.cos(roll), math.cos(az) * math.cos(roll), math.sin(roll)))
                nseg = 5
                prev = None
                for s in range(nseg + 1):
                    t = s / nseg
                    w = wid * math.sin(math.pi * min(1.0, 0.12 + t * 0.88) ** 0.75) * (1.25 if s % 2 else 0.8)
                    zc = -droop * ln * t ** 1.6 + lift * ln * t + R.uniform(-0.04, 0.04) * ln
                    pc = c + dirv * (ln * t) + Vector((0.0, 0.0, zc))
                    if s == nseg:
                        i0 = len(verts)
                        verts.append(tuple(pc + Vector((0.0, 0.0, 0.06 * ln))))
                        faces.append((prev[0], prev[1], i0))
                        faces.append((prev[1], prev[2], i0))
                        break
                    sag = 0.34 * w + 0.03
                    i0 = len(verts)
                    verts.append(tuple(pc - side * w * 0.5 - Vector((0.0, 0.0, sag))))
                    verts.append(tuple(pc + Vector((0.0, 0.0, 0.02))))
                    verts.append(tuple(pc + side * w * 0.5 - Vector((0.0, 0.0, sag))))
                    cur = (i0, i0 + 1, i0 + 2)
                    if prev is not None:
                        faces.append((prev[0], prev[1], cur[1], cur[0]))
                        faces.append((prev[1], prev[2], cur[2], cur[1]))
                    prev = cur
            z += (0.020 + 0.022 * (1.0 - u)) * H * R.uniform(0.8, 1.2)
            tier += 1
        # dark core so the sky does not show between the tiers
        core_p, core_r = [], []
        for i in range(8):
            u = i / 7.0
            zc = z0 - 0.02 * H + (H * 0.97 - z0) * u
            core_p.append(axis(zc))
            core_r.append(max(0.02, rmax * 0.26 * min(1.0, 0.25 + u * 5.0) * (1.0 - u) ** 0.9))
        _sweep(verts, faces, core_p, core_r, Vector((0.2, seed * 0.9, 4.0)), cap_base=True, relief=False, sides=7)
        co = np.array(verts, dtype=np.float32).reshape(-1, 3)
        total = np.fromiter((len(f) for f in faces), dtype=np.int32, count=len(faces))
        loops = np.fromiter((i for f in faces for i in f), dtype=np.int32, count=int(total.sum()))
        me = _mesh(f"PROP_Pine_s{int(seed)}", [(co, total, loops, 0)], [materials.get("MAT_Pine_Dark")])
        me["flora_key"] = key
        me["built_height"] = H
        me["tris"] = _tris(me)
    obj = common.mesh_object(name or f"PROP_Pine_s{int(seed)}", me)
    k = height / me["built_height"]
    obj.scale = (k, k, k)
    if "sharp_done" not in me:
        common.set_smooth(obj, 42.0)
        me["sharp_done"] = True
    obj["height"], obj["seed"], obj["tris"] = float(height), int(seed), me["tris"]
    return obj
