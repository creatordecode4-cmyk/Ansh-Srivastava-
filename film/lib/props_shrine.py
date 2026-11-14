"""Shrine props for the night temple courtyard, built procedurally with bmesh (Blender 5.3, headless).

Public builders. Each returns ONE mesh object (build_rocks: a list of objects), real-world metres, front = -Y.
Same arguments + seed give the same mesh. Nothing is rendered, saved or reset.

    build_torii(height=7.0, width=6.4, name="PROP_Torii", seed=0)
    build_stone_lantern(variant="intact" | "broken", seed=0, name=None)
    build_paper_lantern(name="PROP_PaperLantern")                       origin = TOP hanging point
    build_banner(height=4.2, seed=0, name=None)                         origin = pole base
    build_rocks(count=8, seed=0, name="PROP_Rock")                      -> [PROP_Rock_00, ...]
    scatter_rocks(objs, center=(0, 0, 0), radius=1.5, seed=0, overlap=0.0)   optional helper: spread rocks over a disc
    build_stairs(width=5.0, steps=16, rise=0.17, run=0.34, side_walls=True, name="PROP_Stairs", seed=0)
    build_steps(width=9.0, count=4, rise=0.15, run=0.4, name="PROP_Steps")

Custom properties (plain lists of floats, local space):
    torii          lantern_sockets [[x, y, z], [x, y, z]] under the tie beam, column_spacing, clear_width,
                   clear_height, crest_center / crest_radius (read by MAT_Banner_Red for the small hanging banner)
    stone lantern  light_socket [x, y, z] centre of the fire box (also read by MAT_Lantern_Glow), variant
    paper lantern  light_socket [x, y, z] centre of the paper body, crest_center / crest_radius (MAT_Paper_Lantern)
    banner         crest_center / crest_radius (MAT_Banner_Red), cloth_size [w, l]
    stairs / steps size [overall width, run length, total rise], top_point [x, y, z] centre of the top edge
    rocks          size (largest dimension in metres), kind "block" | "natural"
"""
import math
import os

import bpy  # noqa: F401  (with the pip bpy module, bmesh and mathutils only exist after bpy is imported)
import bmesh
from mathutils import Matrix, Vector, noise

from . import common, materials

STONE = "MAT_Stone_Mossy"
STEP = "MAT_Floor_WetStone"     # tread slabs of build_stairs / build_steps: dark wet stone like the courtyard floor
RED = "MAT_Wood_Red"
DARK = "MAT_Wood_Dark"
TILE = "MAT_Roof_Tile"
METAL = "MAT_Metal_Dark"
ROPE = "MAT_Rope"
CLOTH = "MAT_Banner_Red"
PAPER = "MAT_Paper_Lantern"
GLOW = "MAT_Lantern_Glow"
WHITE = "MAT_Plaster"

TAU = 2.0 * math.pi


# ----------------------------------------------------------------------------------------------- small maths
def _T(x=0.0, y=0.0, z=0.0):
    return Matrix.Translation((x, y, z))


def _R(deg, axis="Z"):
    return Matrix.Rotation(math.radians(deg), 4, axis)


def _off(r, span=40.0):
    """Random offset into the noise field, so every seed sees another part of it."""
    return Vector((r.uniform(-span, span), r.uniform(-span, span), r.uniform(-span, span)))


def _n(x, y, z, off):
    """Perlin noise in -1 .. 1."""
    return noise.noise(Vector((x, y, z)) + off)


def _lerp(a, b, t):
    return a + (b - a) * t


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------------------------- mesh collector
class _B:
    """Collects finished parts (each built in its own small bmesh) into one mesh with material slots."""

    def __init__(self):
        self.bm = bmesh.new()
        self.names = []

    def slot(self, name):
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)

    def add(self, part, mat=None, xf=None, recalc=True):
        """Merge `part` (a bmesh, freed here). mat: one material for all faces, or None to keep the face indices."""
        if recalc:
            bmesh.ops.recalc_face_normals(part, faces=part.faces[:])
        if xf is not None:
            part.transform(xf)
            if xf.determinant() < 0.0:
                bmesh.ops.reverse_faces(part, faces=part.faces[:])
        if mat is not None:
            idx = self.slot(mat)
            for f in part.faces:
                f.material_index = idx
        me = bpy.data.meshes.new("_part")
        part.to_mesh(me)
        part.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    def finish(self, name, angle=35.0):
        obj = common.bm_to_object(name, self.bm, materials=[materials.get(n) for n in self.names])
        common.set_smooth(obj, angle)
        return obj


# ----------------------------------------------------------------------------------------------- primitives
def _loft(bm, rings, closed=True, cap_start=True, cap_end=True):
    """Skin consecutive rings of points (all the same length). Returns the vertex rings."""
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if closed and n >= 3:
        if cap_start:
            bm.faces.new(vr[0][::-1])
        if cap_end:
            bm.faces.new(vr[-1])
    return vr


def _lathe(bm, profile, sides=24, center=(0.0, 0.0), radial=None):
    """Revolve a (radius, z) profile around Z. A radius of 0 at either end closes the shape with a fan.
    radial(angle, z) -> factor lets a caller break the perfect circle."""
    cx, cy = center
    prev = None
    first = last = None
    for k, (rad, z) in enumerate(profile):
        if rad <= 1e-6:
            cur = bm.verts.new((cx, cy, z))
        else:
            cur = []
            for i in range(sides):
                a = TAU * i / sides
                f = radial(a, z) if radial else 1.0
                cur.append(bm.verts.new((cx + math.cos(a) * rad * f, cy + math.sin(a) * rad * f, z)))
        if prev is not None:
            p_pt, c_pt = not isinstance(prev, list), not isinstance(cur, list)
            for i in range(sides):
                j = (i + 1) % sides
                if p_pt and c_pt:
                    break
                if p_pt:
                    bm.faces.new((prev, cur[j], cur[i]))
                elif c_pt:
                    bm.faces.new((prev[i], prev[j], cur))
                else:
                    bm.faces.new((prev[i], prev[j], cur[j], cur[i]))
        if k == 0:
            first = cur
        last = cur
        prev = cur
    if isinstance(first, list):
        bm.faces.new(first[::-1])
    if isinstance(last, list):
        bm.faces.new(last)
    return bm


def _frames(pts):
    """Parallel-transport frames along a polyline: [(tangent, normal, binormal), ...]."""
    n = len(pts)
    tans = []
    for i in range(n):
        t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0.0, 0.0, 1.0)))
    up = Vector((0.0, 0.0, 1.0))
    ref = up if abs(tans[0].dot(up)) < 0.9 else Vector((1.0, 0.0, 0.0))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    out = []
    prev = tans[0]
    for t in tans:
        axis = prev.cross(t)
        if axis.length > 1e-8:
            nrm = Matrix.Rotation(prev.angle(t), 3, axis.normalized()) @ nrm
        nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
        prev = t
    return out


def _tube(bm, pts, radius, sides=6, caps=True, phase=0.0):
    """Round tube along a polyline. radius: number or f(index)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, (p, (_t, nr, bi)) in enumerate(zip(pts, _frames(pts))):
        rad = radius(i) if callable(radius) else radius
        rings.append([p + (nr * math.cos(phase + TAU * k / sides) + bi * math.sin(phase + TAU * k / sides)) * rad
                      for k in range(sides)])
    _loft(bm, rings, cap_start=caps, cap_end=caps)
    return bm


def _rope(bm, pts, radius, strands=3, pitch=0.3, sides=5):
    """Twisted rope: `strands` round strands wound around the polyline. radius: number or f(index)."""
    pts = [Vector(p) for p in pts]
    fr = _frames(pts)
    arc = [0.0]
    for a, b in zip(pts, pts[1:]):
        arc.append(arc[-1] + (b - a).length)
    rad = [radius(i) if callable(radius) else radius for i in range(len(pts))]
    for k in range(strands):
        cen = []
        for i, (p, (_t, nr, bi)) in enumerate(zip(pts, fr)):
            a = TAU * arc[i] / pitch + TAU * k / strands
            cen.append(p + (nr * math.cos(a) + bi * math.sin(a)) * rad[i] * 0.48)
        _tube(bm, cen, lambda i: rad[i] * 0.58, sides)
    return bm


def _grid_box(sx, sy, sz, nx=1, ny=1, nz=1):
    """Box centred on the Z axis with its base on z = 0, every side a grid (so it can be roughened)."""
    bm = bmesh.new()
    verts = {}

    def v(i, j, k):
        key = (i, j, k)
        if key not in verts:
            verts[key] = bm.verts.new((sx * (i / nx - 0.5), sy * (j / ny - 0.5), sz * k / nz))
        return verts[key]

    for i in range(nx):
        for j in range(ny):
            bm.faces.new((v(i, j, 0), v(i, j + 1, 0), v(i + 1, j + 1, 0), v(i + 1, j, 0)))
            bm.faces.new((v(i, j, nz), v(i + 1, j, nz), v(i + 1, j + 1, nz), v(i, j + 1, nz)))
    for i in range(nx):
        for k in range(nz):
            bm.faces.new((v(i, 0, k), v(i + 1, 0, k), v(i + 1, 0, k + 1), v(i, 0, k + 1)))
            bm.faces.new((v(i, ny, k), v(i, ny, k + 1), v(i + 1, ny, k + 1), v(i + 1, ny, k)))
    for j in range(ny):
        for k in range(nz):
            bm.faces.new((v(0, j, k), v(0, j, k + 1), v(0, j + 1, k + 1), v(0, j + 1, k)))
            bm.faces.new((v(nx, j, k), v(nx, j + 1, k), v(nx, j + 1, k + 1), v(nx, j, k + 1)))
    return bm


def _roughen(bm, amp, scale, off, detail=0.4):
    """Push every vertex along its normal by two octaves of noise (hand-hewn, weathered surfaces)."""
    bm.normal_update()
    for v in bm.verts:
        p = v.co * scale + off
        d = noise.noise(p) + detail * noise.noise(p * 2.9 + Vector((7.3, 1.7, 4.1)))
        v.co += v.normal * (amp * d)


def _bevel_sharp(bm, width, segs=2, angle=40.0):
    """Bevel every edge sharper than `angle` degrees."""
    lim = math.radians(angle)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim]
    if edges and width > 0.0:
        bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segs, profile=0.5,
                        affect="EDGES", clamp_overlap=True)


def _cut(bm, co, no, keep_min=0.35):
    """Slice off everything in front of the plane (co, no) and close the wound. Skipped (returns False) when the
    plane would miss the mesh or remove more than 1 - keep_min of its vertices."""
    co, no = Vector(co), Vector(no).normalized()
    front = sum(1 for v in bm.verts if (v.co - co).dot(no) > 1e-5)
    total = len(bm.verts)
    if front == 0 or total == 0 or (total - front) < keep_min * total:
        return False
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=no, clear_outer=True, clear_inner=False)
    edges = [g for g in res["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]
    if len(edges) >= 3:
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges, normal=no)
    return True


def _clean(bm):
    """Weld coincident vertices and drop the zero-area slivers plane cuts can leave behind."""
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    dead = [f for f in bm.faces if f.calc_area() < 1e-9]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")


def _bounds(bm):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for v in bm.verts:
        for a in range(3):
            lo[a] = min(lo[a], v.co[a])
            hi[a] = max(hi[a], v.co[a])
    return lo, hi


def _rebase(bm, sink=0.0):
    """Centre the footprint on the Z axis and put the lowest point on z = -sink."""
    lo, hi = _bounds(bm)
    bm.transform(_T(-(lo.x + hi.x) / 2.0, -(lo.y + hi.y) / 2.0, -lo.z - sink))


def _tris(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)


def _merge(dst, src, xf=None):
    """Append the bmesh `src` (freed here) to `dst`, optionally transformed."""
    if xf is not None:
        src.transform(xf)
    me = bpy.data.meshes.new("_merge")
    src.to_mesh(me)
    src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)


# ----------------------------------------------------------------------------------------------- stone pieces
def _stone_box(r, sx, sy, sz, cell=0.07, rough=0.007, bevel=0.012, segs=2, chips=0, taper=0.0, max_n=14):
    """Hand-dressed stone block: grid box (base on z = 0), slightly lumpy, worn edges, optional chipped corners."""
    nx = max(1, min(max_n, int(round(sx / cell))))
    ny = max(1, min(max_n, int(round(sy / cell))))
    nz = max(1, min(max_n, int(round(sz / cell))))
    bm = _grid_box(sx, sy, sz, nx, ny, nz)
    if taper:
        for v in bm.verts:
            f = 1.0 - taper * v.co.z / sz
            v.co.x *= f
            v.co.y *= f
    off = _off(r)
    if rough > 0.0:
        _roughen(bm, rough, 5.5, off)
    _bevel_sharp(bm, min(bevel, 0.3 * min(sx, sy, sz)), segs)
    for _ in range(chips):
        sgx, sgy = r.choice((-1, 1)), r.choice((-1, 1))
        top = r.random() < 0.8
        corner = Vector((sgx * sx / 2.0, sgy * sy / 2.0, sz if top else 0.0))
        no = Vector((sgx * r.uniform(0.5, 1.5), sgy * r.uniform(0.5, 1.5), (1 if top else -1) * r.uniform(0.35, 1.2))).normalized()
        depth = min(0.14, r.uniform(0.2, 0.55) * min(sx, sy, sz))
        _cut(bm, corner - no * depth, no, keep_min=0.6)
    if chips:
        _clean(bm)
    return bm


def _chunk(r, size, flat=None):
    """Broken piece of dressed stone, largest dimension about `size`, base on z = 0 and centred: a worn block
    split by a few random planes (sharp fresh faces), lying flat or tumbled onto one of its broken sides."""
    flat = r.random() < 0.4 if flat is None else flat
    lx = size
    ly = size * r.uniform(0.5, 0.9)
    lz = size * (r.uniform(0.25, 0.42) if flat else r.uniform(0.45, 0.8))
    cell = max(size / 6.0, 0.025)
    bm = _stone_box(r, lx, ly, lz, cell=cell, rough=size * 0.018, bevel=size * 0.022, segs=1, max_n=7)
    c = Vector((0.0, 0.0, lz / 2.0))
    ext = Vector((lx, ly, lz)) / 2.0
    for _ in range(r.randint(3, 5)):
        no = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.3, 1.0))).normalized()
        reach = abs(no.x) * ext.x + abs(no.y) * ext.y + abs(no.z) * ext.z
        _cut(bm, c + no * reach * r.uniform(0.3, 0.8), no, keep_min=0.45)
    if not flat and r.random() < 0.6:                        # tumbled: any way up, then ground flat underneath
        bm.transform(_R(r.uniform(0.0, 360.0), "X") @ _R(r.uniform(0.0, 360.0), "Y"))
        lo, hi = _bounds(bm)
        _cut(bm, (0.0, 0.0, lo.z + r.uniform(0.08, 0.16) * (hi.z - lo.z)), (0.0, 0.0, -1.0), keep_min=0.3)
    else:                                                    # lying on its dressed face, a little out of level
        bm.transform(_R(r.uniform(-7.0, 7.0), "X") @ _R(r.uniform(-7.0, 7.0), "Y"))
        lo, hi = _bounds(bm)
        _cut(bm, (0.0, 0.0, lo.z + 0.06 * (hi.z - lo.z) + 0.004), (0.0, 0.0, -1.0), keep_min=0.3)
    bm.transform(_R(r.uniform(0.0, 360.0)))
    lo, hi = _bounds(bm)
    d = hi - lo
    bm.transform(Matrix.Scale(size / max(d.x, d.y, d.z, 1e-6), 4))
    _clean(bm)
    _rebase(bm, 0.006)
    return bm


# ----------------------------------------------------------------------------------------------- cloth
def _cloth(bm, w, length, nx, nz, r, tear=0.12, fold=0.03, pins=(0.08, 0.92), mat=0):
    """Hanging cloth in the XZ plane: top edge on z = 0, x in -w/2 .. w/2, hanging to z = -length, front = -Y.
    Vertical folds grow towards the hem; the hem is uneven with a few deep tears."""
    off = _off(r)
    ph1, ph2 = r.uniform(0.0, TAU), r.uniform(0.0, TAU)
    notches = [(r.uniform(0.06, 0.94), r.uniform(0.04, 0.09), r.uniform(0.45, 1.0) * tear) for _ in range(r.randint(3, 5))]

    def hem(u):
        d = 0.35 * tear * (0.5 + 0.5 * _n(u * 3.0, 0.0, 0.0, off))
        d += 0.30 * tear * abs(_n(u * 19.0, 3.0, 0.0, off))
        for c, hw, dep in notches:
            d += dep * max(0.0, 1.0 - abs(u - c) / hw)
        return length * (1.0 - d)

    t0 = 0.7
    grid = []
    for j in range(nz + 1):
        t = j / nz
        row = []
        for i in range(nx + 1):
            u = i / nx
            x = (u - 0.5) * w
            if t <= t0:
                z = -t * length
            else:
                z = -(t0 * length + (t - t0) / (1.0 - t0) * (hem(u) - t0 * length))
            if pins:                                           # the top edge sags a little between its ties
                span = (u - pins[0]) / (pins[1] - pins[0])
                if 0.0 < span < 1.0:
                    z -= 0.03 * w * math.sin(math.pi * span) * max(0.0, 1.0 - 5.0 * t)
            a = fold * (0.2 + 0.8 * t)
            y = a * (0.6 * math.sin(TAU * 1.4 * u + ph1 + 1.3 * t) + 0.4 * math.sin(TAU * 2.9 * u + ph2 - 2.1 * t))
            y += 0.6 * fold * _n(u * 2.0, t * length * 1.2, 0.0, off) * (0.3 + 0.7 * t)
            x *= 1.0 - 0.05 * t * (0.5 + 0.5 * _n(7.0, t * 4.0, 0.0, off))
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))
            f.material_index = mat
    return grid


def _tab(bm, x, bar_r, drop, w=0.05):
    """Cloth loop over a round bar centred on (y = 0, z = 0): up the front, over the top, down the back."""
    rr = bar_r + 0.004
    path = [(-0.002, -drop)]
    path += [(-rr * math.cos(a), rr * math.sin(a)) for a in (math.radians(d) for d in (-20, 20, 55, 90, 125, 160, 200))]
    path += [(0.002, -drop)]
    rows = [(bm.verts.new((x - w / 2.0, y, z)), bm.verts.new((x + w / 2.0, y, z))) for y, z in path]
    for (a0, a1), (b0, b1) in zip(rows, rows[1:]):
        bm.faces.new((a0, a1, b1, b0))


# ----------------------------------------------------------------------------------------------- torii
def build_torii(height=7.0, width=6.4, name="PROP_Torii", seed=0):
    """Myojin torii. `height` is the highest point (the upturned roof tips), `width` the overall width of the top
    lintel tip to tip; the columns stand 0.62 * width apart (centre to centre). People walk through along Y."""
    r = common.rng(seed)
    b = _B()
    s = height / 7.0
    half = width / 2.0
    xs = 0.31 * width                       # column centre at ground level
    lean = 0.022                            # inward lean of the columns (m per m)
    sori = 0.40 * s                         # how far the lintel tips curve up
    h_shi, h_kas, h_roof, r_ridge = 0.36 * s, 0.26 * s, 0.14 * s, 0.045 * s
    z_sh = height - sori - (h_shi - 0.01 + h_kas - 0.01 + h_roof + 0.02 + r_ridge)   # underside of the lower lintel

    def curve(x):
        return sori * (abs(x) / half) ** 2.3

    rc0, rc1 = 0.28 * s, 0.245 * s
    off = _off(r)

    def col_x(side, z):
        return side * (xs - lean * z)

    z_nt = z_sh - 0.58 * s                  # tie beam top
    hn, dn = 0.40 * s, 0.20 * s
    z_nb = z_nt - hn

    for side in (-1, 1):
        # stone footing
        b.add(_stone_box(r, 1.04 * s, 1.04 * s, 0.24 * s, chips=r.randint(1, 2)), STONE,
              _T(col_x(side, 0), 0, -0.03) @ _R(r.uniform(-2, 2)))
        b.add(_stone_box(r, 0.78 * s, 0.78 * s, 0.42 * s, chips=r.randint(0, 2), bevel=0.02), STONE,
              _T(col_x(side, 0), 0, 0.19 * s) @ _R(r.uniform(-2, 2)))
        # black sleeve
        cx = col_x(side, 0.85 * s)
        rs = rc0 + 0.035 * s
        sl = bmesh.new()
        _lathe(sl, [(rs, 0.57 * s), (rs + 0.012, 0.60 * s), (rs + 0.012, 0.66 * s), (rs, 0.68 * s), (rs, 1.10 * s),
                    (rs + 0.01, 1.11 * s), (rs + 0.01, 1.15 * s), (rs - 0.02 * s, 1.165 * s)], sides=28, center=(cx, 0.0))
        b.add(sl, DARK)
        # column
        z_top = z_sh + curve(col_x(side, z_sh)) + 0.03
        zs = [0.6 * s + (z_top - 0.6 * s) * i / 16 for i in range(17)]
        rings = []
        for z in zs:
            t = (z - zs[0]) / (zs[-1] - zs[0])
            rad = _lerp(rc0, rc1, t ** 1.3)
            cxz = col_x(side, z) + 0.006 * _n(side * 3.0, 0.0, z * 0.5, off)
            ring = []
            for k in range(28):
                a = TAU * k / 28
                rr = rad * (1.0 + 0.012 * _n(math.cos(a) * 1.5 + side * 9.0, math.sin(a) * 1.5, z * 0.9, off))
                ring.append(Vector((cxz + math.cos(a) * rr, math.sin(a) * rr, z)))
            rings.append(ring)
        col = bmesh.new()
        _loft(col, rings)
        b.add(col, RED)
        # collar under the lintel
        cz = z_top - 0.16 * s
        ctx = col_x(side, cz)
        ring = bmesh.new()
        _lathe(ring, [(rc1 + 0.01, cz), (rc1 + 0.07 * s, cz + 0.02 * s), (rc1 + 0.07 * s, cz + 0.10 * s), (rc1 + 0.01, cz + 0.12 * s)],
               sides=28, center=(ctx, 0.0))
        b.add(ring, RED)

    # lower lintel (shimaki), upper lintel (kasagi) and the tiled cap, all following the same curve
    nseg = 40

    def beam(half_len, section, slant=0.0):
        rings = []
        for i in range(nseg + 1):
            x = -half_len + 2.0 * half_len * i / nseg
            end = -1 if i == 0 else (1 if i == nseg else 0)
            zc = curve(x)
            ring = [Vector((x + end * slant * zz, y, zc + zz)) for y, zz in section]
            rings.append(ring)
        bm = bmesh.new()
        _loft(bm, rings)
        return bm

    def rect(hd0, hd1, h, c=0.02):
        """Section (y, z) of a beam: half depth hd0 at the bottom, hd1 at the top, chamfered corners."""
        return [(-hd0 + c, 0.0), (-hd0, c), (-hd1, h - c), (-hd1 + c, h), (hd1 - c, h), (hd1, h - c), (hd0, c), (hd0 - c, 0.0)]

    z_kas = z_sh + h_shi - 0.01
    z_roof = z_kas + h_kas - 0.01
    b.add(beam(0.86 * half, rect(0.19 * s, 0.19 * s, h_shi)), RED, _T(0, 0, z_sh))
    b.add(beam(half - 0.16 * s, rect(0.22 * s, 0.265 * s, h_kas), slant=0.45), DARK, _T(0, 0, z_kas))
    roof = [(-0.34 * s, 0.0), (-0.345 * s, 0.045 * s), (-0.05 * s, h_roof), (0.05 * s, h_roof), (0.345 * s, 0.045 * s), (0.34 * s, 0.0)]
    b.add(beam(half - 0.03, roof), TILE, _T(0, 0, z_roof))
    ridge = bmesh.new()
    _tube(ridge, [Vector((x, 0.0, z_roof + curve(x) + h_roof + 0.02)) for x in (-(half - 0.01) + 2.0 * (half - 0.01) * i / nseg for i in range(nseg + 1))],
          r_ridge, sides=8)
    b.add(ridge, TILE)
    ribs = bmesh.new()
    n_rib = max(4, int(round((2.0 * half - 0.3) / (0.21 * s))))
    for i in range(n_rib + 1):
        x = -half + 0.15 + (2.0 * half - 0.3) * i / n_rib
        zc = z_roof + curve(x)
        for sy in (-1, 1):
            p0 = Vector((x, sy * 0.045 * s, zc + h_roof + 0.004))
            p1 = Vector((x, sy * 0.352 * s, zc + 0.045 * s + 0.006))
            _tube(ribs, [p0, p1], 0.036 * s, sides=6)
    b.add(ribs, TILE)

    # tie beam (nuki) through the columns, a hair off level, with dark end caps and wedges
    ln = 0.90 * width
    nuki = _stone_box(r, ln, dn, hn, cell=ln / 12.0, rough=0.0, bevel=0.012 * s, segs=1)
    tilt = _R(r.uniform(-0.25, 0.25), "Y")
    b.add(nuki, RED, _T(0, 0, z_nb) @ tilt)
    for side in (-1, 1):
        capb = _stone_box(r, 0.26 * s, dn + 0.03, hn + 0.03, cell=1.0, rough=0.0, bevel=0.01, segs=1)
        b.add(capb, DARK, _T(0, 0, z_nb) @ tilt @ _T(side * (ln / 2.0 - 0.115 * s), 0, -0.015))
        xc = col_x(side, z_nt)
        for d in (-1, 1):                                      # wedges on top of the beam, both sides of the column
            wl, wh = r.uniform(0.42, 0.52) * s, r.uniform(0.17, 0.21) * s
            x0 = xc + d * (rc1 - 0.04)
            wd = dn * 0.84
            wb = bmesh.new()
            pts = [(x0, -wd / 2, z_nt - 0.02), (x0 + d * wl, -wd / 2, z_nt - 0.02), (x0 + d * wl, -wd / 2, z_nt + 0.03 * s), (x0, -wd / 2, z_nt + wh)]
            _loft(wb, [[Vector(p) for p in pts], [Vector((p[0], wd / 2, p[2])) for p in pts]])
            _bevel_sharp(wb, 0.006, 1)
            b.add(wb, RED)

    # central strut with its tablet
    gz0, gz1 = z_nt - 0.03, z_sh + 0.03
    b.add(_stone_box(r, 0.34 * s, 0.17 * s, gz1 - gz0, cell=1.0, rough=0.0, bevel=0.01, segs=1), RED, _T(0, 0, gz0))
    tab = _T(0, -0.085 * s - 0.03, (gz0 + gz1) / 2.0) @ _R(-7.0, "X")
    b.add(_stone_box(r, 0.46 * s, 0.04, 0.52 * s, cell=1.0, rough=0.0, bevel=0.008, segs=1), DARK, tab @ _T(0, 0, -0.26 * s))
    b.add(_stone_box(r, 0.34 * s, 0.03, 0.40 * s, cell=1.0, rough=0.0, bevel=0.004, segs=1), RED, tab @ _T(0, -0.012, -0.20 * s))

    # straw rope (shimenawa) in front of the columns, sagging between them
    z_e = z_nt + 0.14 * s
    xe = xs - lean * z_e
    rr_mid, rr_end = 0.08 * s, 0.055 * s
    y_r = -(rc1 + 0.01 + rr_end)
    z_c = z_e - 0.85 * s
    x_low = r.uniform(-0.12, 0.12)

    def rope_z(x):
        d = (x - x_low) / ((xe - x_low) if x > x_low else (xe + x_low))
        return z_c + (z_e - z_c) * d * d

    def rope_r(x):
        return _lerp(rr_mid, rr_end, (abs(x) / xe) ** 1.5)

    n_r = 120
    xr = [-xe + 2.0 * xe * i / n_r for i in range(n_r + 1)]
    rope = bmesh.new()
    _rope(rope, [Vector((x, y_r - 0.02 * math.sin(math.pi * (x + xe) / (2 * xe)), rope_z(x))) for x in xr],
          lambda i: rope_r(xr[i]), pitch=0.30 * s)
    for side in (-1, 1):                                       # wraps around the columns and loose tails
        xc = col_x(side, z_e)
        rad = rc1 + 0.012 + rr_end * 0.8
        ring = [Vector((xc + math.cos(TAU * k / 30) * rad, math.sin(TAU * k / 30) * rad, z_e + 0.035 * math.sin(TAU * k / 30 + side)))
                for k in range(31)]
        _rope(rope, ring, rr_end * 0.9, pitch=0.24 * s)
        for k in range(2):
            a = math.radians(-90 - side * (35 + 40 * k))
            p0 = Vector((xc + math.cos(a) * (rad + 0.02), math.sin(a) * (rad + 0.02), z_e - 0.01))
            ln_t = r.uniform(0.35, 0.6) * s
            sway = r.uniform(-0.04, 0.04)
            pts = [p0 + Vector((sway * t * t, -0.01 * t, -ln_t * t)) for t in (i / 6 for i in range(7))]
            _tube(rope, pts, lambda i: _lerp(0.022, 0.011, i / 6) * s, sides=5)
    b.add(rope, ROPE)

    # straw tassels
    tas = bmesh.new()
    for fx, ln_t in ((-0.47, 0.68), (0.44, 0.6), (0.85, 0.4), (-0.83, 0.36)):
        x = fx * xe + r.uniform(-0.05, 0.05)
        ln_t *= s * r.uniform(0.9, 1.1)
        zt = rope_z(x) - rope_r(x) * 0.8
        ph = r.uniform(0.0, TAU)
        k = ln_t / 0.5
        w = (0.75 + 0.45 * k) * s
        prof = [(0.0, zt + 0.02), (0.022 * w, zt), (0.03 * w, zt - 0.05 * k), (0.05 * w, zt - 0.10 * k), (0.058 * w, zt - 0.16 * k),
                (0.04 * w, zt - 0.21 * k), (0.036 * w, zt - 0.235 * k), (0.05 * w, zt - 0.27 * k), (0.066 * w, zt - 0.36 * k),
                (0.078 * w, zt - 0.47 * k), (0.07 * w, zt - 0.5 * k), (0.0, zt - 0.47 * k)]
        _lathe(tas, prof, sides=18, center=(x, y_r - 0.01),
               radial=lambda a, z, ph=ph: 1.0 + 0.13 * math.cos(9 * a + ph + z * 4.0))
    b.add(tas, ROPE)

    # zig-zag paper streamers (shide)
    shide = bmesh.new()
    for fx in (-0.66, -0.2, 0.18, 0.66):
        x = fx * xe + r.uniform(-0.06, 0.06)
        z = rope_z(x) - rope_r(x) * 0.6
        d = r.choice((-1, 1))
        pw, ph_ = 0.085 * s, 0.13 * s
        yaw = r.uniform(-0.5, 0.5)
        for k in range(4):
            x0 = x + d * (k * 0.5 - 0.75) * pw
            z0 = z - k * ph_ * 0.86
            c, sn = math.cos(yaw + 0.25 * k), math.sin(yaw + 0.25 * k)
            pts = []
            for px, pz in ((0, 0), (pw, 0), (pw, -ph_), (0, -ph_)):
                lx = px - pw / 2.0
                pts.append(shide.verts.new((x0 + pw / 2.0 + lx * c, y_r - rr_end * 0.3 + lx * sn - 0.004 * k, z0 + pz)))
            shide.faces.new(pts)
    b.add(shide, WHITE, recalc=False)

    # small red banner hanging from the tie beam on a rod
    bw, bl = 0.42 * s, 1.3 * s
    bx = 0.19 * xe
    rod = bmesh.new()
    _tube(rod, [Vector((bx - bw / 2 - 0.04, 0.0, z_nb - 0.02)), Vector((bx + bw / 2 + 0.04, 0.0, z_nb - 0.02))], 0.013, sides=8)
    b.add(rod, DARK)
    cl = bmesh.new()
    _cloth(cl, bw, bl, 10, 28, r, tear=0.16, fold=0.018)
    b.add(cl, CLOTH, _T(bx, 0.0, z_nb - 0.035), recalc=False)

    obj = b.finish(name, 35.0)
    sx = 0.53 * (xs - lean * z_nb)
    obj["lantern_sockets"] = [[-sx, 0.0, z_nb], [sx, 0.0, z_nb]]
    obj["crest_center"] = [bx, 0.0, z_nb - 0.035 - 0.40 * bl]
    obj["crest_radius"] = 0.33 * bw
    obj["column_spacing"] = 2.0 * xs
    obj["clear_width"] = 2.0 * (xs - lean * 2.0 - rc0)
    obj["clear_height"] = z_nb
    obj["size"] = [width, 1.04 * s, height]
    return obj


# ----------------------------------------------------------------------------------------------- stone lantern
def _lantern_cap(r, half=0.45, r_top=0.10, h=0.245, thick=0.10, lift=0.09, sides=40):
    """Pagoda-like stone cap: round at the top, square at the eave, corners curling up. Base (soffit) near z = 0."""
    ts_top = (0.0, 0.1, 0.22, 0.36, 0.5, 0.64, 0.77, 0.89, 0.97, 1.0)
    rings = []

    def shape(a):
        sq = 1.0 / max(abs(math.cos(a)), abs(math.sin(a)))
        return sq, (sq - 1.0) / (math.sqrt(2.0) - 1.0)

    def pt(a, t, z, grow=1.0):
        sq, _c = shape(a)
        rad = _lerp(r_top, half, t ** 0.85) * _lerp(1.0, sq, _smooth(t * 1.25)) * grow
        return Vector((math.cos(a) * rad, math.sin(a) * rad, z))

    def corner_lift(a, t):
        _sq, c = shape(a)
        return lift * (c ** 1.6) * (t ** 2.5) + 0.018 * (c ** 8) * math.sin(math.pi * min(1.0, t * 1.05))

    angs = [TAU * k / sides for k in range(sides)]
    for t in ts_top:                                           # upper surface, apex to eave
        rings.append([pt(a, t, thick + h * (1.0 - t) ** 1.9 + corner_lift(a, t)) for a in angs])
    rings.append([pt(a, 1.0, thick * 0.5 + corner_lift(a, 1.0), 1.012) for a in angs])      # rounded eave edge
    rings.append([pt(a, 1.0, corner_lift(a, 1.0), 0.985) for a in angs])
    for t in (0.8, 0.55, 0.3):                                 # soffit, rising a little towards the middle
        rings.append([pt(a, t, 0.045 * (1.0 - t) + corner_lift(a, t) * 0.9) for a in angs])
    bm = bmesh.new()
    _loft(bm, rings)
    _roughen(bm, 0.006, 6.0, _off(r))
    return bm


def _finial(sides=20):
    prof = [(0.085, 0.0), (0.098, 0.015), (0.098, 0.05), (0.072, 0.066), (0.066, 0.09), (0.12, 0.10), (0.137, 0.122),
            (0.12, 0.146), (0.072, 0.157), (0.062, 0.172), (0.088, 0.192), (0.116, 0.226), (0.112, 0.262), (0.078, 0.296),
            (0.034, 0.317), (0.013, 0.332), (0.0, 0.336)]
    bm = bmesh.new()
    _lathe(bm, prof, sides=sides)
    return bm


def _shaft(r, r0=0.215, r1=0.152, h=0.66, sides=20, rings=11):
    """Tapering, irregular rough-hewn shaft with a rounded-square section; base on z = 0."""
    off = _off(r)
    out = []
    for j in range(rings + 1):
        t = j / rings
        z = h * t
        rad = _lerp(r0, r1, t ** 0.75)
        ring = []
        for k in range(sides):
            a = TAU * k / sides
            c, sn = math.cos(a), math.sin(a)
            sq = 1.0 / (abs(c) ** 3.2 + abs(sn) ** 3.2) ** (1.0 / 3.2)
            rr = rad * sq * (1.0 + 0.075 * _n(c * 1.6, sn * 1.6, z * 3.0, off) + 0.035 * _n(c * 4.0, sn * 4.0, z * 8.0, off))
            ring.append(Vector((c * rr, sn * rr, z)))
        out.append(ring)
    bm = bmesh.new()
    _loft(bm, out)
    return bm


def build_stone_lantern(variant="intact", seed=0, name=None):
    """Stone lantern (ishi-doro), about 2.3 m tall, rough-hewn mossy granite. variant 'broken': cracked, leaning
    shaft, chipped cap with a missing corner, no finial, rubble around the base (inside a 1.0 m radius)."""
    broken = variant == "broken"
    r = common.rng(seed * 7919 + (17 if broken else 3))
    b = _B()

    def jit(a=0.005, ang=1.6):
        return _T(r.uniform(-a, a), r.uniform(-a, a), 0.0) @ _R(r.uniform(-ang, ang))

    # three stepped base tiers
    b.add(_stone_box(r, 0.94, 0.94, 0.21, chips=2 if broken else 1), STONE, _T(0, 0, -0.02) @ jit())
    b.add(_stone_box(r, 0.70, 0.70, 0.205, chips=r.randint(0, 1) + broken), STONE, _T(0, 0, 0.175) @ jit())
    b.add(_stone_box(r, 0.57, 0.57, 0.165, bevel=0.045, segs=3, rough=0.009), STONE, _T(0, 0, 0.365) @ jit())

    z_s0, h_s = 0.50, 0.66                                     # shaft
    shaft = _shaft(r, h=h_s)
    up = Matrix.Identity(4)                                     # transform of everything above the crack
    if broken:
        ca = r.uniform(0.0, TAU)
        cn = Vector((math.cos(ca) * 0.42, math.sin(ca) * 0.42, 1.0)).normalized()
        cp = Vector((0.0, 0.0, h_s * r.uniform(0.45, 0.6)))
        low, high = shaft, shaft.copy()
        _cut(low, cp, cn, keep_min=0.2)
        _cut(high, cp + cn * 0.004, -cn, keep_min=0.2)
        chip_n = Vector((-math.sin(ca), math.cos(ca), -0.5)).normalized()
        _cut(high, cp + chip_n * 0.13, chip_n, keep_min=0.2)
        b.add(low, STONE, _T(0, 0, z_s0))
        axis = Vector((-math.sin(ca), math.cos(ca), 0.0))       # lean towards the downhill side of the crack
        pivot = Vector((0.0, 0.0, z_s0)) + cp
        slide = Vector((cn.x, cn.y, 0.0)).normalized() * 0.014
        up = _T(*slide) @ _T(*pivot) @ Matrix.Rotation(math.radians(r.uniform(4.0, 6.0)), 4, axis) @ _T(*(-pivot))
        b.add(high, STONE, up @ _T(0, 0, z_s0) @ _R(r.uniform(-4, 4)))
    else:
        b.add(shaft, STONE, _T(0, 0, z_s0) @ jit(0.003, 3.0))

    # corbel and platform
    z = z_s0 + h_s - 0.02
    corbel = _stone_box(r, 0.47, 0.47, 0.11, taper=-0.0, bevel=0.02, segs=2)
    for v in corbel.verts:                                      # narrower at the bottom
        f = _lerp(0.78, 1.0, v.co.z / 0.11)
        v.co.x *= f
        v.co.y *= f
    b.add(corbel, STONE, up @ _T(0, 0, z) @ jit())
    z += 0.095
    b.add(_stone_box(r, 0.65, 0.65, 0.115, chips=1 + broken), STONE, up @ _T(0, 0, z) @ jit())
    z += 0.105                                                  # fire box floor
    fb, fh = 0.42, 0.33
    yaw = _R(r.uniform(-1.5, 1.5))
    fire = up @ _T(0, 0, z) @ yaw
    b.add(_stone_box(r, fb, fb, 0.055, cell=0.07, rough=0.004, bevel=0.008), STONE, fire)
    b.add(_stone_box(r, fb, fb, 0.055, cell=0.07, rough=0.004, bevel=0.008), STONE, fire @ _T(0, 0, fh - 0.055))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.add(_stone_box(r, 0.072, 0.072, fh - 0.09, cell=0.06, rough=0.003, bevel=0.007), STONE,
                  fire @ _T(sx * (fb / 2 - 0.041), sy * (fb / 2 - 0.041), 0.045))
    b.add(_grid_box(0.33, 0.33, fh - 0.07), GLOW, fire @ _T(0, 0, 0.035))
    bars = bmesh.new()
    skip = r.randrange(16) if broken else -1                    # the broken lantern has lost one bar
    k = 0
    for q in range(4):
        rot = _R(90.0 * q)
        for kind, pos in (("v", -0.048), ("v", 0.048), ("h", 0.118), ("h", 0.20)):
            k += 1
            if k - 1 == skip:
                continue
            if kind == "v":
                _merge(bars, _grid_box(0.014, 0.014, fh - 0.10), rot @ _T(pos, -0.188, 0.05))
            else:
                _merge(bars, _grid_box(fb - 0.13, 0.012, 0.014), rot @ _T(0.0, -0.181, pos))
    b.add(bars, DARK, fire)
    light = fire @ Vector((0.0, 0.0, fh / 2.0))

    # cap and finial
    z_cap = z + fh - 0.02
    cap = _lantern_cap(r)
    cap_m = up @ _T(0, 0, z_cap) @ _R(r.uniform(-2.0, 2.0))
    if broken:
        qa = math.radians(45.0 + 90.0 * r.randrange(4))
        corner = Vector((math.cos(qa), math.sin(qa), 0.0)) * (0.45 * math.sqrt(2.0))
        cno = Vector((math.cos(qa + r.uniform(-0.3, 0.3)), math.sin(qa + r.uniform(-0.3, 0.3)), r.uniform(0.1, 0.4))).normalized()
        _cut(cap, corner - cno * r.uniform(0.27, 0.36), cno, keep_min=0.5)
        cno2 = Vector((cno.y * 0.5 + cno.x, -cno.x * 0.5 + cno.y, -0.5)).normalized()
        _cut(cap, corner - cno2 * 0.42, cno2, keep_min=0.5)
        for _ in range(3):                                      # smaller chips along the eave
            ea = r.uniform(0.0, TAU)
            eno = Vector((math.cos(ea), math.sin(ea), r.uniform(-0.6, 0.8))).normalized()
            _cut(cap, Vector((math.cos(ea), math.sin(ea), 0.0)) * (0.45 / max(abs(math.cos(ea)), abs(math.sin(ea)))) - eno * r.uniform(0.04, 0.09)
                 + Vector((0, 0, 0.06)), eno, keep_min=0.6)
        stump = bmesh.new()                                     # what is left of the finial
        _lathe(stump, [(0.085, 0.0), (0.098, 0.015), (0.098, 0.05), (0.074, 0.066), (0.068, 0.12)], sides=16)
        tno = Vector((r.uniform(-0.7, 0.7), r.uniform(-0.7, 0.7), 1.0)).normalized()
        _cut(stump, Vector((0.0, 0.0, r.uniform(0.045, 0.07))), tno, keep_min=0.2)
        _roughen(stump, 0.004, 9.0, _off(r))
        _merge(cap, stump, _T(0, 0, 0.345 - 0.025))
        ta = r.uniform(0.0, TAU)
        tilt_axis = Vector((math.cos(ta), math.sin(ta), 0.0))
        cap_m = cap_m @ _T(-math.sin(ta) * 0.03, math.cos(ta) * 0.03, 0.02) @ Matrix.Rotation(math.radians(r.uniform(8.0, 12.0)), 4, tilt_axis)
        b.add(cap, STONE, cap_m)
    else:
        b.add(cap, STONE, cap_m)
        fin = _finial()
        _roughen(fin, 0.004, 9.0, _off(r))
        b.add(fin, STONE, cap_m @ _T(0, 0, 0.345 - 0.025) @ _R(r.uniform(-1.5, 1.5), "X"))

    if broken:                                                  # rubble: the fallen finial and broken pieces
        def ring_pos(size, a):
            reach = 0.47 / max(abs(math.cos(a)), abs(math.sin(a)))
            lo, hi = reach + size * 0.5 + 0.03, 0.97 - size * 0.5
            rad = r.uniform(lo, hi) if hi > lo else lo
            return Vector((math.cos(a) * rad, math.sin(a) * rad, 0.0))

        base_a = math.atan2(corner.y, corner.x)
        fin = _finial(16)
        _cut(fin, (0.0, 0.0, 0.158), (r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5), -1.0), keep_min=0.1)
        _roughen(fin, 0.004, 9.0, _off(r))
        fin.transform(_R(r.uniform(95.0, 125.0), "X"))
        _rebase(fin, 0.008)
        b.add(fin, STONE, _T(*ring_pos(0.24, base_a + r.uniform(-0.5, 0.5))) @ _R(r.uniform(0, 360)))
        n_rub = r.randint(8, 11)
        for i in range(n_rub):
            size = r.uniform(0.1, 0.26) if i > 1 else r.uniform(0.3, 0.36)
            a = base_a + (r.uniform(-1.3, 1.3) if i < n_rub - 2 else r.uniform(0.0, TAU))
            b.add(_chunk(r, size), STONE, _T(*ring_pos(size, a)) @ _R(r.uniform(0, 360)))

    obj = b.finish(name or ("PROP_StoneLantern_Broken" if broken else "PROP_StoneLantern"), 38.0)
    obj["light_socket"] = [light.x, light.y, light.z]
    obj["variant"] = "broken" if broken else "intact"
    return obj


# ----------------------------------------------------------------------------------------------- paper lantern
def build_paper_lantern(name="PROP_PaperLantern"):
    """Hanging red paper lantern (chochin), 0.8 m from the hanging point down to the tassel tip.
    Origin = the TOP hanging point; everything hangs below it along -Z."""
    b = _B()
    rib = 0.03                                                  # MAT_Paper_Lantern draws a rib every 3 cm of local z
    z_top, z_bot = -6 * rib, -19 * rib                          # paper body
    r_end, r_max = 0.08, 0.135

    hang = bmesh.new()
    _tube(hang, [Vector((0.012 * math.cos(TAU * k / 12), 0.0, -0.012 + 0.012 * math.sin(TAU * k / 12))) for k in range(13)], 0.0028, sides=5)
    _tube(hang, [Vector((0, 0, -0.022)), Vector((0, 0, -0.072))], 0.0035, sides=6)
    bail_z = z_top + 0.045
    _tube(hang, [Vector((0.07 * math.cos(a), 0.0, bail_z + 0.066 * math.sin(a))) for a in (math.pi * k / 14 for k in range(15))], 0.0035, sides=6)
    b.add(hang, METAL)

    caps = bmesh.new()
    zc = z_top + 0.045
    _lathe(caps, [(0.0, zc + 0.004), (0.06, zc + 0.004), (0.082, zc - 0.002), (0.086, zc - 0.01), (0.08, zc - 0.016), (0.078, zc - 0.04),
                  (0.086, zc - 0.046), (0.086, zc - 0.054), (0.07, zc - 0.058)], sides=28)
    zc = z_bot + 0.008
    _lathe(caps, [(0.068, zc + 0.004), (0.084, zc), (0.084, zc - 0.008), (0.076, zc - 0.014), (0.074, zc - 0.036), (0.08, zc - 0.042),
                  (0.074, zc - 0.05), (0.03, zc - 0.062), (0.012, zc - 0.078), (0.0, zc - 0.08)], sides=28)
    b.add(caps, DARK)

    body = bmesh.new()
    prof = []
    n = int(round((z_top - z_bot) / (rib / 2.0)))
    for j in range(n + 1):
        t = j / n
        barrel = (1.0 - abs(2.0 * t - 1.0) ** 2.7) ** (1.0 / 2.7)
        rad = r_end + (r_max - r_end) * barrel
        if j % 2 == 1:
            rad -= 0.0032                                       # paper sags in between the bamboo ribs
        prof.append((rad, z_top + (z_bot - z_top) * t))
    _lathe(body, prof, sides=28)
    b.add(body, PAPER)

    tas = bmesh.new()
    zt = z_bot - 0.07
    _tube(tas, [Vector((0, 0, zt + 0.004)), Vector((0, 0, zt - 0.026))], 0.003, sides=5)
    _lathe(tas, [(0.0, zt - 0.022), (0.012, zt - 0.027), (0.017, zt - 0.038), (0.012, zt - 0.05), (0.008, zt - 0.054), (0.013, zt - 0.06),
                 (0.017, zt - 0.09), (0.021, zt - 0.14), (0.02, -0.80), (0.0, -0.795)], sides=12,
           radial=lambda a, z: 1.0 + 0.12 * math.cos(6 * a + z * 30.0))
    b.add(tas, CLOTH)

    obj = b.finish(name, 40.0)
    zc = (z_top + z_bot) / 2.0
    obj["light_socket"] = [0.0, 0.0, zc]
    obj["crest_center"] = [0.0, 0.0, zc]
    obj["crest_radius"] = 0.082
    return obj


# ----------------------------------------------------------------------------------------------- banner
def build_banner(height=4.2, seed=0, name=None):
    """War banner (nobori): slim dark pole in a small stone foot, short crossbar near the top, a long narrow red
    cloth (about 0.75 x 2.6 m) with folds and a torn hem. Origin = the pole base; the cloth hangs on the +X side."""
    r = common.rng(seed * 31 + 5)
    b = _B()
    s = height / 4.2
    cw, cl = 0.75 * s, 2.6 * s
    rp, rb = 0.03 * s, 0.018 * s
    lean_x, lean_y = math.radians(r.uniform(-1.2, 1.2)), math.radians(r.uniform(-1.2, 1.2))
    bow = r.uniform(-0.02, 0.02) * s
    top = height - 0.05 * s

    def axis(z):
        return Vector((math.tan(lean_x) * z + bow * math.sin(math.pi * z / height), math.tan(lean_y) * z, z))

    b.add(_stone_box(r, 0.24 * s, 0.24 * s, 0.2 * s, cell=0.06, bevel=0.015, chips=r.randint(0, 1)), STONE, _T(0, 0, -0.02) @ _R(r.uniform(-8, 8)))
    pole = bmesh.new()
    zs = [-0.01 + (top + 0.01) * i / 14 for i in range(15)]
    _tube(pole, [axis(z) for z in zs], lambda i: _lerp(rp, rp * 0.78, i / 14), sides=10)
    z_bar = height - 0.26 * s
    pb = axis(z_bar) + Vector((0.0, -(rp + rb) * 0.95, 0.0))
    droop = r.uniform(0.0, 0.025) * s
    x0, x1 = -0.11 * s, 0.07 * s + cw + 0.09 * s
    bar_pts = [pb + Vector((x, 0.0, -droop * max(0.0, x) / x1)) for x in (x0 + (x1 - x0) * i / 8 for i in range(9))]
    _tube(pole, bar_pts, rb, sides=8)
    b.add(pole, DARK)
    knob = bmesh.new()
    pt = axis(top)
    _lathe(knob, [(rp * 0.8, -0.03 * s), (rp * 1.25, -0.02 * s), (rp * 1.25, 0.0), (rp * 0.7, 0.012 * s), (rp * 1.05, 0.03 * s),
                  (rp * 0.75, 0.045 * s), (0.0, 0.05 * s)], sides=12, center=(pt.x, pt.y))
    knob.transform(_T(0, 0, pt.z))
    for bx in (x0, x1):                                         # small end caps on the crossbar
        cap = bmesh.new()
        _lathe(cap, [(0.0, -0.012), (rb * 1.3, -0.01), (rb * 1.3, 0.01), (0.0, 0.012)], sides=8)
        _merge(knob, cap, _T(pb.x + bx, pb.y, pb.z - droop * max(0.0, bx) / x1) @ _R(90.0, "Y"))
    b.add(knob, METAL)
    lash = bmesh.new()                                          # rope lashing where the crossbar meets the pole
    pa = axis(z_bar)
    for dz in (-0.02, 0.0, 0.02):
        ring = [Vector((pa.x + math.cos(TAU * k / 14) * (rp + 0.006), pa.y - rb * 0.6 + math.sin(TAU * k / 14) * (rp + rb * 0.9), z_bar + dz * s + 0.012 * math.cos(TAU * k / 14)))
                for k in range(15)]
        _tube(lash, ring, 0.006 * s, sides=5)
    b.add(lash, ROPE)

    cloth = bmesh.new()
    cx = pb.x + 0.07 * s + cw / 2.0
    cz = pb.z - droop * 0.5 - rb - 0.075 * s
    pins = (0.1, 0.9)
    _cloth(cloth, cw, cl, 24, 56, r, tear=0.15, fold=0.06 * s, pins=pins)
    cloth.transform(_T(cx, pb.y, cz))
    for u in pins:
        tb = bmesh.new()
        tx = (u - 0.5) * cw
        _tab(tb, tx, rb, 0.085 * s, w=0.06 * s)
        _merge(cloth, tb, _T(cx, pb.y, pb.z - droop * (cx + tx - pb.x) / x1 * 0.9))
    b.add(cloth, CLOTH, recalc=False)

    obj = b.finish(name or "PROP_Banner", 45.0)
    obj["crest_center"] = [cx, pb.y, cz - 0.40 * cl]
    obj["crest_radius"] = 0.36 * cw
    obj["cloth_size"] = [cw, cl]
    return obj


# ----------------------------------------------------------------------------------------------- rocks
_PH_ROCKS = (
    ("rock_moss_set_01", tuple(f"rock_moss_set_01_rock{i:02d}" for i in range(1, 7))),
    ("rock_moss_set_02", tuple(f"rock_moss_set_02_rock{i:02d}" for i in range(7, 14))),
    ("boulder_01", ("boulder_01_LOD3",)),
)
ROCK_VALUE = 0.36          # Poly Haven rock albedo is multiplied by this (wet night stone)
ROCK_SATURATION = 0.35


def _night_rock_material(mat):
    """Darkened, desaturated, wet copy of a Poly Haven rock material (keeps its textures and UVs)."""
    name = "MAT_Rock_" + mat.name.split(".")[0]
    out = bpy.data.materials.get(name)
    if out is not None:
        return out
    out = mat.copy()
    out.name = name
    nt = out.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        return out
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        src = base.links[0].from_socket
        hsv = nt.nodes.new("ShaderNodeHueSaturation")
        hsv.inputs["Saturation"].default_value = ROCK_SATURATION
        hsv.inputs["Value"].default_value = ROCK_VALUE
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs[0].default_value = 1.0
        tint.inputs[7].default_value = (0.9, 0.95, 1.08, 1.0)
        nt.links.new(src, hsv.inputs["Color"])
        nt.links.new(hsv.outputs["Color"], tint.inputs[6])
        nt.links.new(tint.outputs[2], base)
    rough = bsdf.inputs["Roughness"]
    if rough.is_linked:
        src = rough.links[0].from_socket
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 0.62
        nt.links.new(src, mul.inputs[0])
        nt.links.new(mul.outputs[0], rough)
    bsdf.inputs["Coat Weight"].default_value = 0.35
    bsdf.inputs["Coat Roughness"].default_value = 0.18
    # thin snow on up-facing parts; the Value node is named like the film materials' tunable ("Snow Amount")
    amount = nt.nodes.new("ShaderNodeValue")
    amount.name = amount.label = "Snow Amount"
    amount.outputs[0].default_value = 0.5
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sep.inputs[0])
    up = nt.nodes.new("ShaderNodeMapRange")
    up.interpolation_type = "SMOOTHSTEP"
    up.inputs["From Min"].default_value, up.inputs["From Max"].default_value = 0.5, 0.92
    nt.links.new(sep.outputs["Z"], up.inputs["Value"])
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 2.2
    tex.inputs["Detail"].default_value = 3.0
    nt.links.new(geo.outputs["Position"], tex.inputs["Vector"])

    def math_node(op, a, b_):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for sock, val in ((n.inputs[0], a), (n.inputs[1], b_)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                nt.links.new(val, sock)
        return n.outputs[0]

    patch = math_node("SUBTRACT", math_node("MULTIPLY", common.sock(tex, ["Fac", "Factor"], out=True), 0.9), 0.45)
    field = math_node("ADD", up.outputs["Result"], patch)
    thr = math_node("SUBTRACT", 1.33, math_node("MULTIPLY", amount.outputs[0], 0.5))
    snow = nt.nodes.new("ShaderNodeMapRange")
    snow.interpolation_type = "SMOOTHSTEP"
    snow.inputs["From Min"].default_value, snow.inputs["From Max"].default_value = -0.05, 0.05
    nt.links.new(math_node("SUBTRACT", field, thr), snow.inputs["Value"])
    mask = math_node("MULTIPLY", snow.outputs["Result"], math_node("MINIMUM", math_node("MULTIPLY", amount.outputs[0], 5.0), 1.0))
    for sock_name, value in (("Base Color", (0.78, 0.82, 0.9, 1.0)), ("Roughness", 0.6), ("Coat Weight", 0.0)):
        sock = bsdf.inputs[sock_name]
        mix = nt.nodes.new("ShaderNodeMix")
        is_col = sock_name == "Base Color"
        mix.data_type = "RGBA" if is_col else "FLOAT"
        a_in, b_in, res = (mix.inputs[6], mix.inputs[7], mix.outputs[2]) if is_col else (mix.inputs[2], mix.inputs[3], mix.outputs[0])
        nt.links.new(mask, mix.inputs[0])
        if sock.is_linked:
            nt.links.new(sock.links[0].from_socket, a_in)
        else:
            a_in.default_value = sock.default_value
        b_in.default_value = value
        nt.links.new(res, sock)
    out["night_rock"] = True
    return out


def _ph_source(slug, obj_name, tris):
    """Decimated copy of one Poly Haven rock, cached in the current file as the mesh '_SRC_<name>_<tris>'."""
    key = f"_SRC_{obj_name}_{tris}"
    me = bpy.data.meshes.get(key)
    if me is not None:
        return me
    path = os.path.join(common.PH, slug, "2k", f"{slug}_2k.blend")
    if not os.path.exists(path):
        return None
    try:
        objs = common.append_objects(path, names=[obj_name])
    except Exception as exc:
        print(f"[props_shrine] could not append {obj_name}: {exc!r}")
        return None
    ob = next((o for o in objs if o.type == "MESH"), None)
    if ob is None:
        return None
    n = common.tri_count([ob])
    if n > tris:
        mod = ob.modifiers.new("Decimate", "DECIMATE")
        mod.ratio = tris / n
        common.update()
        common.apply_modifiers(ob)
    me = ob.data
    me.transform(ob.matrix_world)
    old = list(me.materials)
    bpy.data.objects.remove(ob, do_unlink=True)
    me.name = key
    for i, mat in enumerate(old):
        if mat is not None:
            me.materials[i] = _night_rock_material(mat)
            if mat.users == 0 or (mat.use_fake_user and mat.users == 1):
                bpy.data.materials.remove(mat)
    return me


def _natural_rock(r, size, src):
    bm = bmesh.new()
    bm.from_mesh(src)
    lo, hi = _bounds(bm)
    bm.transform(_T(-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -(lo.z + hi.z) / 2))
    squash = Matrix.Diagonal((r.uniform(0.85, 1.15), r.uniform(0.85, 1.15), r.uniform(0.85, 1.1), 1.0))
    bm.transform(_R(r.uniform(-12.0, 12.0), "X") @ _R(r.uniform(-12.0, 12.0), "Y") @ _R(r.uniform(0.0, 360.0)) @ squash)
    lo, hi = _bounds(bm)
    d = hi - lo
    bm.transform(Matrix.Scale(size / max(d.x, d.y, d.z), 4))
    lo, hi = _bounds(bm)
    _cut(bm, (0.0, 0.0, lo.z + r.uniform(0.06, 0.12) * (hi.z - lo.z)), (0.0, 0.0, -1.0), keep_min=0.3)
    _clean(bm)
    _rebase(bm, 0.006)
    return bm


def build_rocks(count=8, seed=0, name="PROP_Rock"):
    """`count` distinct rubble pieces, largest dimension 0.15 .. 0.9 m: about half broken dressed-stone blocks
    (MAT_Stone_Mossy), half natural rocks (decimated Poly Haven scans with their own darkened textured material;
    more dressed blocks if those files are missing). Every piece: origin at the centre of its base, all created
    at the world origin, identity transform. Names continue from the first free <name>_XX in the file."""
    r = common.rng(seed * 104729 + 11)
    pool = [(slug, n) for slug, names in _PH_ROCKS for n in names]
    r.shuffle(pool)
    first = 0
    while bpy.data.objects.get(f"{name}_{first:02d}") is not None:
        first += 1
    kinds = ["block" if i % 2 == 0 else "natural" for i in range(count)]
    r.shuffle(kinds)
    out = []
    for i in range(count):
        size = 0.15 + 0.75 * r.random() ** 1.7
        rr = common.rng(r.randrange(1 << 30))
        obj = None
        if kinds[i] == "natural":
            slug, src_name = pool[i % len(pool)]
            src = _ph_source(slug, src_name, 2400 if size > 0.4 else 1000)
            if src is not None:
                bm = _natural_rock(rr, size, src)
                me = bpy.data.meshes.new(f"{name}_{first + i:02d}")
                bm.to_mesh(me)
                bm.free()
                for mat in src.materials:
                    me.materials.append(mat)
                obj = common.mesh_object(me.name, me)
                me.shade_smooth()
                obj["kind"] = "natural"
        if obj is None:
            b = _B()
            b.add(_chunk(rr, size), STONE)
            obj = b.finish(f"{name}_{first + i:02d}", 38.0)
            obj["kind"] = "block"
        obj["size"] = size
        out.append(obj)
    return out


def scatter_rocks(objs, center=(0.0, 0.0, 0.0), radius=1.5, seed=0, overlap=0.0):
    """Spread rocks over a disc on the floor: big pieces first, random turn, footprints kept apart when there is
    room. overlap 0 .. 0.6 lets footprints run into each other by that share (a tighter heap). Only sets location
    and rotation_euler.z. Returns objs."""
    r = common.rng(seed * 613 + 1)
    placed = []
    for ob in sorted(objs, key=lambda o: -max(o.dimensions.x, o.dimensions.y)):
        rad = 0.5 * max(ob.dimensions.x, ob.dimensions.y)
        best = None
        for _ in range(40):
            a, d = r.uniform(0.0, TAU), radius * math.sqrt(r.random())
            d = min(d, max(0.0, radius - rad))
            p = (center[0] + math.cos(a) * d, center[1] + math.sin(a) * d)
            gap = min((math.hypot(p[0] - q[0], p[1] - q[1]) - (rad + qr) * (1.0 - overlap) for q, qr in placed), default=1.0)
            if best is None or gap > best[0]:
                best = (gap, p)
            if gap > 0.02:
                break
        ob.location = (best[1][0], best[1][1], center[2] if len(center) > 2 else 0.0)
        ob.rotation_euler = (0.0, 0.0, r.uniform(0.0, TAU))
        placed.append((best[1], rad))
    return objs


# ----------------------------------------------------------------------------------------------- stairs
def _step_block(r, off, x0, x1, y0, depth, z0, z1, width):
    """One tread slab: rounded, foot-worn nosing that varies along its length, bevelled ends."""
    length = x1 - x0
    n = max(2, int(round(length / 0.32)))
    e = 0.007
    xs = [x0, x0 + e] + [x0 + length * k / n for k in range(1, n)] + [x1 - e, x1]
    tilt = r.uniform(-0.004, 0.004)
    rings = []
    for idx, x in enumerate(xs):
        ins = e if idx in (0, len(xs) - 1) else 0.0
        mid = 1.0 - min(1.0, abs(x) / (width * 0.5)) ** 2                    # people walk in the middle
        w = 0.5 + 0.5 * _n(x * 1.1, y0 * 0.9, z1 * 3.0, off)
        nose = 0.012 + 0.016 * w + 0.012 * mid
        zt = z1 - ins - 0.007 * mid * w + tilt * (x - x0) / length
        yf = y0 + ins + 0.006 * _n(x * 2.3, y0 * 2.0 + 5.0, z1, off)
        yb, zb = y0 + depth - ins, z0 + ins
        ring = [Vector((x, yf, zb)), Vector((x, yf, zt - nose))]
        for a in (math.radians(30.0), math.radians(60.0)):
            ring.append(Vector((x, yf + nose * (1.0 - math.cos(a)), zt - nose * (1.0 - math.sin(a)))))
        ring += [Vector((x, yf + nose, zt)), Vector((x, yb, zt + 0.002)), Vector((x, yb, zb))]
        rings.append(ring)
    bm = bmesh.new()
    _loft(bm, rings)
    return bm


def _flight(b, r, width, steps, rise, run, slab=(0.8, 1.5), chip_p=0.14, into_wall=0.0, core_inset=0.02):
    """Rows of tread slabs over a plain stepped core (the core closes the joints and the sides)."""
    off = _off(r)
    hw = width / 2.0 + into_wall
    for i in range(steps):
        z1, z0, y0 = (i + 1) * rise, i * rise - 0.05, i * run
        depth = run + (0.06 if i < steps - 1 else 0.0)
        xs = [-hw]
        while True:
            nxt = xs[-1] + r.uniform(*slab)
            if nxt > hw - slab[0] * 0.6:
                break
            xs.append(nxt)
        xs.append(hw)
        for xa, xb in zip(xs, xs[1:]):
            gap = r.uniform(0.003, 0.006)
            blk = _step_block(r, off, xa + gap, xb - gap, y0 + r.uniform(-0.008, 0.008), depth, z0, z1 + r.uniform(-0.006, 0.004), width)
            if r.random() < chip_p:                                          # broken corner at a joint
                sx = r.choice((-1, 1))
                corner = Vector((xb if sx > 0 else xa, y0, z1))
                no = Vector((sx * r.uniform(0.5, 1.4), -1.0, r.uniform(0.6, 1.3))).normalized()
                _cut(blk, corner - no * r.uniform(0.03, 0.085), no, keep_min=0.5)
            elif r.random() < chip_p * 0.5:                                  # nosing spalled off along the slab
                no = Vector((r.uniform(-0.15, 0.15), -1.0, r.uniform(0.7, 1.2))).normalized()
                _cut(blk, Vector(((xa + xb) / 2, y0, z1)) - no * r.uniform(0.02, 0.035), no, keep_min=0.5)
            _clean(blk)
            b.add(blk, STEP)
    # core
    core = bmesh.new()
    cw = width / 2.0 - core_inset
    ins, zf = 0.035, -0.05
    y_end = steps * run - (0.0 if into_wall else 0.004)

    def quad(pts):
        core.faces.new([core.verts.new(p) for p in pts])

    for i in range(steps):
        ya = i * run + ins
        yb = (i + 1) * run + ins if i < steps - 1 else y_end
        top = (i + 1) * rise - ins
        low = i * rise - ins if i else zf
        quad([(-cw, ya, top), (cw, ya, top), (cw, yb, top), (-cw, yb, top)])               # tread
        quad([(-cw, ya, low), (cw, ya, low), (cw, ya, top), (-cw, ya, top)])               # riser
        quad([(-cw, ya, zf), (-cw, ya, top), (-cw, yb, top), (-cw, yb, zf)])               # -x side
        quad([(cw, ya, zf), (cw, yb, zf), (cw, yb, top), (cw, ya, top)])                   # +x side
    top = steps * rise - ins
    quad([(-cw, y_end, zf), (-cw, y_end, top), (cw, y_end, top), (cw, y_end, zf)])         # back
    quad([(-cw, ins, zf), (-cw, y_end, zf), (cw, y_end, zf), (cw, ins, zf)])               # bottom
    bmesh.ops.remove_doubles(core, verts=core.verts[:], dist=1e-5)
    b.add(core, STEP, recalc=False)


def build_stairs(width=5.0, steps=16, rise=0.17, run=0.34, side_walls=True, name="PROP_Stairs", seed=0):
    """Worn stone staircase. `width` is the clear tread width; the stepped side walls (0.45 m each) stand outside
    it. Origin = bottom centre of the first riser; the flight climbs towards +Y to z = steps * rise."""
    r = common.rng(seed * 977 + 23)
    b = _B()
    thick = 0.45
    _flight(b, r, width, steps, rise, run, into_wall=0.03 if side_walls else 0.0)
    if side_walls:
        per = 2
        n_seg = int(math.ceil(steps / per))
        for side in (-1, 1):
            for k in range(n_seg):
                last = min(steps, (k + 1) * per)
                ya, yb = k * per * run, last * run
                top = last * rise + 0.38 + r.uniform(-0.02, 0.02) + (0.22 if k == n_seg - 1 else 0.0)
                z = -0.05
                n_c = max(1, int(round((top - z) / 0.48)))
                hs = [r.uniform(0.8, 1.2) for _ in range(n_c)]
                tot = sum(hs)
                hs = [h * (top - z) / tot for h in hs]
                xc = side * (width / 2.0 + thick / 2.0)
                b.add(_grid_box(thick - 0.05 - 0.012 * (k % 2), (yb - ya) + 0.02, top - z - 0.03), STONE, _T(xc, (ya + yb) / 2.0, z))   # light-tight core
                for h in hs:
                    blk = _stone_box(r, thick + r.uniform(-0.012, 0.012), (yb - ya) - r.uniform(0.006, 0.012), h - r.uniform(0.004, 0.008),
                                     cell=0.3, rough=0.007, bevel=0.016, segs=1, chips=1 if r.random() < 0.3 else 0, max_n=3)
                    b.add(blk, STONE, _T(xc + r.uniform(-0.008, 0.008), (ya + yb) / 2.0, z) @ _R(r.uniform(-0.5, 0.5)))
                    z += h
    obj = b.finish(name, 35.0)
    obj["size"] = [width + (2.0 * thick if side_walls else 0.0), steps * run, steps * rise]
    obj["top_point"] = [0.0, steps * run, steps * rise]
    return obj


def build_steps(width=9.0, count=4, rise=0.15, run=0.4, name="PROP_Steps"):
    """Plain wide flight of low stone steps, no side walls. Origin = bottom centre of the first riser; climbs
    towards +Y to z = count * rise."""
    r = common.rng(int(width * 100) * 7 + count * 131 + 3)
    b = _B()
    _flight(b, r, width, count, rise, run, slab=(1.2, 2.0), chip_p=0.1)
    obj = b.finish(name, 35.0)
    obj["size"] = [width, count * run, count * rise]
    obj["top_point"] = [0.0, count * run, count * rise]
    return obj
