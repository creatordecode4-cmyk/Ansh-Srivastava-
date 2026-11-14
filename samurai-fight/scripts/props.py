"""Procedural stand-in props. Every builder fills one collection, origin on the ground.
Each collection can later be swapped for an image-to-3D GLB without touching the layout."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
from sf_lib import *

LANTERN_W = 1300.0     # stone lantern point light power
PAPER_W = 95.0


def _pt_light(name, coll, loc, power, color=(1.0, 0.16, 0.05), radius=0.12):
    l = bpy.data.lights.new(name, 'POINT')
    l.energy, l.color, l.shadow_soft_size = power, color, radius
    ob = bpy.data.objects.new(name, l)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def add_curved_beam(bm, L, w, h, z, sori=0.0, segs=24, y=0.0, mat_index=0, flare=0.0):
    secs = []
    for i in range(segs + 1):
        t = -1 + 2 * i / segs
        x, zc = t * L / 2, z + sori * abs(t) ** 2.2
        hh = h * (1 + flare * abs(t) ** 2)
        secs.append([bm.verts.new((x, y - w / 2, zc)), bm.verts.new((x, y + w / 2, zc)),
                     bm.verts.new((x, y + w / 2, zc + hh)), bm.verts.new((x, y - w / 2, zc + hh))])
    faces = []
    for a, b in zip(secs, secs[1:]):
        for k in range(4):
            faces.append(bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k])))
    faces.append(bm.faces.new(secs[0]))
    faces.append(bm.faces.new(secs[-1][::-1]))
    for f in faces:
        f.material_index = mat_index


def add_prism_yz(bm, profile, x0, x1):
    a = [bm.verts.new((x0, y, z)) for y, z in profile]
    b = [bm.verts.new((x1, y, z)) for y, z in profile]
    n = len(profile)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)


def add_plane_uv(bm, c, ux, uy, w, h, uv_m=True, nx=1, ny=1, mat_index=0):
    """Plane centred at c spanned by unit vectors ux, uy. UV in metres or 0..1."""
    uvl = bm.loops.layers.uv.verify()
    c, ux, uy = Vector(c), Vector(ux), Vector(uy)
    grid = [[bm.verts.new(c + ux * (w * (i / nx - 0.5)) + uy * (h * (j / ny - 0.5))) for i in range(nx + 1)] for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            q = [(grid[j][i], i, j), (grid[j][i + 1], i + 1, j), (grid[j + 1][i + 1], i + 1, j + 1), (grid[j + 1][i], i, j + 1)]
            f = bm.faces.new([t[0] for t in q])
            f.material_index = mat_index
            for l, (_, ii, jj) in zip(f.loops, q):
                l[uvl].uv = (ii / nx * (w if uv_m else 1.0), jj / ny * (h if uv_m else 1.0))
    return grid


# ------------------------------------------------------------------ stone lantern
def build_stone_lantern(coll, broken=False, seed=1, power=LANTERN_W):
    rnd = random.Random(seed)
    bm = bmesh.new()

    def piece(r1, r2, h, z, segs=6, rot=0.0):
        return add_cyl(bm, r1, r2, h, (0, 0, z), segs, Matrix.Rotation(rot, 4, 'Z'), tris=True)

    piece(0.80, 0.66, 0.26, 0.0, 7, 0.3)
    piece(0.62, 0.52, 0.22, 0.26, 6, 0.9)
    piece(0.30, 0.23, 0.98, 0.48, 8)
    piece(0.30, 0.60, 0.16, 1.46)
    piece(0.60, 0.62, 0.12, 1.62)
    z0, fb = 1.74, 0.46
    for k in range(6):
        a = k * math.pi / 3
        add_box(bm, (0.12, 0.12, fb), (0.38 * math.cos(a), 0.38 * math.sin(a), z0 + fb / 2), Matrix.Rotation(a, 4, 'Z'))
    piece(0.48, 0.48, 0.07, z0 + fb)
    zr = z0 + fb + 0.07
    rv = piece(1.02, 0.30, 0.36, zr, 12)
    ring = [v for v in rv if abs(v.co.z - zr) < 1e-4 and v.co.xy.length > 0.5]
    for v in ring:
        k = round(math.atan2(v.co.y, v.co.x) / (math.pi / 6))
        if k % 2 == 0:
            v.co.z += 0.10
        else:
            v.co.x *= 0.86
            v.co.y *= 0.86
    piece(0.30, 0.18, 0.10, zr + 0.36, 12)
    top = []
    if not broken:
        r = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=0.17,
                                      matrix=Matrix.Translation((0, 0, zr + 0.36 + 0.10 + 0.19)) @ Matrix.Diagonal((1, 1, 1.35, 1)))
        top = r['verts']
    subdivide(bm, 2)
    rockify(bm, 0.035, 2.6, seed)
    rockify(bm, 0.012, 11.0, seed + 5)
    if broken:
        piv = Vector((0, 0, zr))
        R = Matrix.Rotation(math.radians(17), 4, 'X') @ Matrix.Rotation(math.radians(-9), 4, 'Y')
        for v in bm.verts:
            if v.co.z > zr - 0.02:
                v.co = piv + (R @ (v.co - piv)) + Vector((0.07, -0.10, -0.03))
                if v.co.x > 0.55:               # knocked-off corner
                    v.co.x = 0.55 + (v.co.x - 0.55) * 0.25
                    v.co.z -= 0.08
    ob = mesh_obj('StoneLantern' + ('_Broken' if broken else ''), bm, coll, [mat_stone()], smooth=True, sharp_deg=50)
    bm = bmesh.new()
    add_cyl(bm, 0.29, 0.29, fb - 0.04, (0, 0, z0 + 0.02), 6)
    mesh_obj('LanternFire', bm, coll, [mat_emit('MAT_LanternFire', (1.0, 0.10, 0.02), 5.0)])
    _pt_light('LGT_Lantern', coll, (0, 0, z0 + fb / 2), power, radius=0.2)
    if broken:
        ob.rotation_euler = (math.radians(4), math.radians(-3), 0)
    return ob


# ------------------------------------------------------------------ torii gate
def build_banner(coll, name, w, h, top, rot_z=0.0, seed=0):
    rnd = random.Random(seed)
    bm = bmesh.new()
    grid = add_plane_uv(bm, (0, 0, -h / 2), (1, 0, 0), (0, 0, 1), w, h, uv_m=False, nx=6, ny=20)
    for j, row in enumerate(grid):
        t = 1 - j / 20                        # 0 at top, 1 at the free end
        for i, v in enumerate(row):
            v.co.y += 0.10 * t * math.sin(3.1 * t + i * 0.5 + seed) + 0.03 * t * math.sin(9 * t + seed * 2)
            v.co.x += 0.04 * t * math.sin(2 * t + seed)
    ob = mesh_obj(name, bm, coll, [mat_banner()], smooth=True)
    ob.location = top
    ob.rotation_euler = (0, 0, rot_z)
    return ob


def build_torii(coll, span=6.0, height=8.4):
    red, cap, stone = mat_lacquer(), mat_simple('MAT_ToriiCap', (0.02, 0.02, 0.024), 0.4, bump=0.3, snow=0.8), mat_stone()
    lean = math.radians(2.2)
    bm = bmesh.new()
    for s in (-1, 1):
        add_cyl(bm, 0.45, 0.37, height - 0.75, (s * span / 2, 0, 0.75), 24, Matrix.Rotation(-s * lean, 4, 'Y'))
    add_curved_beam(bm, span + 3.4, 0.62, 0.55, height - 0.12, sori=0.42, flare=0.15)          # shimagi
    add_curved_beam(bm, span + 2.3, 0.36, 0.62, height * 0.70, sori=0.0)                       # nuki
    add_box(bm, (0.5, 0.3, height - 0.12 - (height * 0.70 + 0.62)), (0, 0, (height - 0.12 + height * 0.70 + 0.62) / 2))  # gakuzuka
    for s in (-1, 1):                                                                       # wedges
        x = s * (span / 2 - height * 0.7 * math.sin(lean))
        add_box(bm, (0.16, 0.52, 0.22), (x + s * 0.5, 0, height * 0.70 + 0.66))
    mesh_obj('Torii_Red', bm, coll, [red], smooth=True, sharp_deg=35, bevel=0.025)
    bm = bmesh.new()
    add_curved_beam(bm, span + 4.4, 0.92, 0.34, height + 0.45, sori=0.50, flare=0.2)           # kasagi roof cap
    mesh_obj('Torii_Cap', bm, coll, [cap], bevel=0.04)
    bm = bmesh.new()
    for s in (-1, 1):
        add_cyl(bm, 0.78, 0.60, 0.85, (s * span / 2, 0, 0.0), 12, tris=True)
        add_box(bm, (1.9, 1.9, 0.24), (s * span / 2, 0, 0.0))
    subdivide(bm, 2)
    rockify(bm, 0.03, 2.5, 4)
    mesh_obj('Torii_Bases', bm, coll, [stone], smooth=True, sharp_deg=45)
    # shimenawa rope with tassels
    cu = bpy.data.curves.new('Torii_Rope', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = '3D', 0.075, 3
    sp = cu.splines.new('POLY')
    n, zr, half = 28, height * 0.70 - 0.25, span / 2 - 0.3
    sp.points.add(n)
    for i in range(n + 1):
        t = -1 + 2 * i / n
        sp.points[i].co = (t * half, -0.42, zr - 0.95 * (1 - t * t), 1)
    rope = bpy.data.objects.new('Torii_Rope', cu)
    rope.data.materials.append(mat_simple('MAT_Rope', (0.34, 0.26, 0.13), 0.8, bump=0.5, bump_scale=60))
    coll.objects.link(rope)
    bm = bmesh.new()
    for t in (-0.55, 0.0, 0.55):
        add_cyl(bm, 0.03, 0.11, 0.55, (t * half, -0.42, zr - 0.95 * (1 - t * t) - 0.62), 8)
    mesh_obj('Torii_Tassels', bm, coll, [bpy.data.materials['MAT_Rope']], smooth=True)
    zb = height * 0.70 - 0.02
    for k, (x, w, h) in enumerate([(-2.05, 0.62, 2.5), (-0.85, 0.5, 1.5), (0.95, 0.62, 2.1), (2.1, 0.5, 2.9)]):
        build_banner(coll, f'Torii_Banner{k}', w, h, (x, 0.0, zb), seed=k * 1.7)


# ------------------------------------------------------------------ roofs / temple
def hip_roof(bm, a, b, H, p=1.45, lift=0.9, nu=30, nv=12):
    """Hipped roof centred on the origin, eave at z=0 (corners lifted). a >= b are half sizes.
    UVs in metres: u along the eave, v up the slope."""
    uvl = bm.loops.layers.uv.verify()
    cache = {}
    slope = math.hypot(b, H)

    def zf(u, v):
        return H * v ** p + lift * abs(u) ** 5 * (1 - v) ** 3

    def vert(x, y, z):
        k = (round(x, 4), round(y, 4), round(z, 4))
        if k not in cache:
            cache[k] = bm.verts.new((x, y, z))
        return cache[k]

    faces = [lambda u, v: (u * (a - b * v), -b * (1 - v), u * (a - b * v)),
             lambda u, v: (-u * (a - b * v), b * (1 - v), u * (a - b * v)),
             lambda u, v: (a - b * v, u * b * (1 - v), u * b * (1 - v)),
             lambda u, v: (-(a - b * v), -u * b * (1 - v), u * b * (1 - v))]
    for pos in faces:
        g = []
        for j in range(nv + 1):
            v = j / nv
            row = []
            for i in range(nu + 1):
                u = -1 + 2 * i / nu
                x, y, ue = pos(u, v)
                row.append((vert(x, y, zf(u, v)), (ue, v * slope)))
            g.append(row)
        for j in range(nv):
            for i in range(nu):
                q, seen = [], set()
                for t in (g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]):
                    if t[0] not in seen:
                        seen.add(t[0])
                        q.append(t)
                if len(q) < 3:
                    continue
                try:
                    f = bm.faces.new([t[0] for t in q])
                except ValueError:
                    continue
                for l, t in zip(f.loops, q):
                    l[uvl].uv = t[1]
    return zf


def _roof_object(coll, name, a, b, H, loc, lift=0.9, p=1.45, ridge=True):
    roofm = mat_roof()
    bm = bmesh.new()
    zf = hip_roof(bm, a, b, H, p, lift)
    ob = mesh_obj(name, bm, coll, [roofm], smooth=True, sharp_deg=60)
    ob.location = loc
    s = ob.modifiers.new('solid', 'SOLIDIFY')
    s.thickness, s.offset = 0.17, -1.0
    # hip + main ridges
    cu = bpy.data.curves.new(name + '_Ridges', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = '3D', 0.15, 3, True
    for sx in (-1, 1):
        for sy in (-1, 1):
            sp = cu.splines.new('POLY')
            sp.points.add(12)
            for i in range(13):
                v = i / 12
                sp.points[i].co = (sx * (a - b * v), sy * b * (1 - v), zf(1, v) + 0.10, 1)
                sp.points[i].radius = 1.0 + 0.5 * (1 - v) ** 3
    rc = bpy.data.objects.new(name + '_Ridges', cu)
    rc.location = loc
    rc.data.materials.append(mat_simple('MAT_RoofRidge', (0.03, 0.033, 0.04), 0.35, bump=0.3, snow=0.85))
    coll.objects.link(rc)
    if ridge and a - b > 0.2:
        bm = bmesh.new()
        add_curved_beam(bm, 2 * (a - b) + 1.0, 0.42, 0.55, H - 0.05, sori=0.22, segs=12)
        r = mesh_obj(name + '_TopRidge', bm, coll, [bpy.data.materials['MAT_RoofRidge']], bevel=0.05)
        r.location = loc
    return zf


_paper = {}


def paper_lantern(coll, loc, power=PAPER_W, string=1.0):
    if 'me' not in _paper:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.27, matrix=Matrix.Diagonal((1, 1, 1.55, 1)))
        for f in bm.faces:
            f.material_index = 0
        add_cyl(bm, 0.14, 0.14, 0.07, (0, 0, 0.38), 12, mat_index=1)
        add_cyl(bm, 0.14, 0.14, 0.07, (0, 0, -0.45), 12, mat_index=1)
        add_cyl(bm, 0.012, 0.012, 1.0, (0, 0, 0.45), 6, mat_index=1)
        add_cyl(bm, 0.035, 0.012, 0.3, (0, 0, -0.75), 6, mat_index=2)
        me = bpy.data.meshes.new('PaperLantern')
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        for m in (mat_emit('MAT_PaperLantern', (1.0, 0.05, 0.015), 3.2, rib=True), mat_simple('MAT_Black', (0.01, 0.01, 0.012), 0.4),
                  mat_simple('MAT_Tassel', (0.4, 0.02, 0.02), 0.8)):
            me.materials.append(m)
        _paper['me'] = me
    ob = bpy.data.objects.new('PaperLantern', _paper['me'])
    ob.location = loc
    coll.objects.link(ob)
    _pt_light('LGT_Paper', coll, Vector(loc) + Vector((0, 0, -0.1)), power, (1.0, 0.12, 0.04), 0.25)
    return ob


def build_temple(coll, W=18.0, D=11.0, ph=1.6, wh=4.2, ov=2.6, rH=5.2, vw=1.9, bays=7, stairs=True, porch=True,
                 glow=0.3, lanterns=4, door_light=1500.0, tag='A'):
    stone, wood, red, win = mat_stone(), mat_wood_dark(), mat_lacquer(), mat_window('MAT_WindowGlow', glow)
    # --- stone platform + stairs
    bm = bmesh.new()
    add_box(bm, (W + 2 * vw + 0.8, D + 2 * vw + 0.8, ph - 0.12), (0, 0, (ph - 0.12) / 2))
    add_box(bm, (W + 2 * vw + 1.4, D + 2 * vw + 1.4, 0.26), (0, 0, 0.13))
    sw, n = 5.2, int(round(ph / 0.16))
    run, rise, y0 = 0.34, ph / n, -(D / 2 + vw + 0.4)
    if stairs:
        for i in range(n):
            add_box(bm, (sw, run * (n - i), rise), (0, y0 - run * (n - i) / 2, rise * i + rise / 2))
        L = run * n + 0.35
        for s in (-1, 1):
            add_prism_yz(bm, [(y0, 0.0), (y0 - L, 0.0), (y0 - L, 0.42), (y0, ph + 0.34)], s * (sw / 2), s * (sw / 2 + 0.62))
    uv_box_project(bm)
    mesh_obj(f'Temple{tag}_Platform', bm, coll, [stone], bevel=0.03)
    # --- deck, walls, beams
    bm = bmesh.new()
    add_box(bm, (W + 2 * vw, D + 2 * vw, 0.12), (0, 0, ph - 0.06))
    add_box(bm, (W, D, wh), (0, 0, ph + wh / 2))
    mesh_obj(f'Temple{tag}_Wood', bm, coll, [wood], bevel=0.015)
    bm = bmesh.new()
    cols = [(-W / 2 + i * W / bays, sy * D / 2) for i in range(bays + 1) for sy in (-1, 1)]
    nb = max(2, int(round(D / (W / bays))))
    cols += [(sx * W / 2, -D / 2 + j * D / nb) for j in range(1, nb) for sx in (-1, 1)]
    for x, y in cols:
        add_cyl(bm, 0.23, 0.21, wh, (x, y, ph), 14)
    zt = ph + wh
    for sy in (-1, 1):
        add_box(bm, (W + 0.6, 0.36, 0.40), (0, sy * D / 2, zt - 0.2))
        add_box(bm, (W + 0.3, 0.30, 0.20), (0, sy * D / 2, ph + 2.95))
        add_box(bm, (W + 0.3, 0.30, 0.22), (0, sy * D / 2, ph + 0.11))
    for sx in (-1, 1):
        add_box(bm, (0.36, D + 0.6, 0.40), (sx * W / 2, 0, zt - 0.2))
        add_box(bm, (0.30, D + 0.3, 0.20), (sx * W / 2, 0, ph + 2.95))
    for x, y in cols:                       # bracket clusters
        ox, oy = (0.0, (0.25 if y > 0 else -0.25)) if abs(abs(y) - D / 2) < 1e-6 else ((0.25 if x > 0 else -0.25), 0.0)
        for k, s in enumerate((0.5, 0.85, 1.2)):
            add_box(bm, (s if oy else 0.5 + 0.5 * k, s if ox else 0.5 + 0.5 * k, 0.17), (x + ox * k, y + oy * k, zt + 0.09 + 0.18 * k))
    # veranda railing
    ex, ey, rz = W / 2 + vw - 0.1, D / 2 + vw - 0.1, ph + 0.9

    def rail(p0, p1):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 0.3:
            return
        rot = Matrix.Rotation(math.atan2(d.y, d.x), 4, 'Z')
        mid = (p0 + p1) / 2
        add_box(bm, (L, 0.10, 0.10), (mid.x, mid.y, rz), rot)
        add_box(bm, (L, 0.07, 0.07), (mid.x, mid.y, ph + 0.45), rot)
        for i in range(int(L / 1.5) + 1):
            q = p0 + d * (i / max(1, int(L / 1.5)))
            add_box(bm, (0.13, 0.13, 0.98), (q.x, q.y, ph + 0.49))

    gap = sw / 2 + 0.7 if stairs else 0.0
    rail((-ex, -ey), (-gap, -ey)) if stairs else rail((-ex, -ey), (ex, -ey))
    if stairs:
        rail((gap, -ey), (ex, -ey))
    rail((ex, -ey), (ex, ey))
    rail((ex, ey), (-ex, ey))
    rail((-ex, ey), (-ex, -ey))
    mesh_obj(f'Temple{tag}_Red', bm, coll, [red], smooth=True, sharp_deg=35, bevel=0.012)
    # --- glowing lattice windows / door
    bm = bmesh.new()
    bw = W / bays
    for i in range(bays):
        xc = -W / 2 + (i + 0.5) * bw
        door = (i == bays // 2)
        h = 3.0 if door else 2.0
        add_plane_uv(bm, (xc, -D / 2 - 0.03, ph + (1.55 if door else 1.85)), (1, 0, 0), (0, 0, 1), bw - (0.5 if door else 0.7), h)
    for sx in (-1, 1):
        for j in range(nb):
            if j % 2 == 0:
                yc = -D / 2 + (j + 0.5) * D / nb
                add_plane_uv(bm, (sx * (W / 2 + 0.03), yc, ph + 1.85), (0, 1, 0), (0, 0, 1), D / nb - 0.7, 2.0)
    mesh_obj(f'Temple{tag}_Windows', bm, coll, [win])
    # --- roof (eave drops below the wall top so the roof rests on the brackets at the wall line)
    a, b = W / 2 + ov, D / 2 + ov
    z_roof = zt + 0.6 - rH * (ov / b) ** 1.45
    zf = _roof_object(coll, f'Temple{tag}_Roof', a, b, rH, (0, 0, z_roof))
    bm = bmesh.new()
    for sy in (-1, 1):                       # rafters under the eaves
        x = -a + 0.5
        while x < a - 0.4:
            z = z_roof + zf(x / a, 0.5 * ov / b) - 0.16
            add_box(bm, (0.10, ov + 0.3, 0.12), (x, sy * (b - ov / 2 - 0.1), z), Matrix.Rotation(sy * math.radians(14), 4, 'X'))
            x += 0.42
    for sx in (-1, 1):
        y = -b + 0.5
        while y < b - 0.4:
            z = z_roof + zf(y / b, 0.5 * ov / b) - 0.16
            add_box(bm, (ov + 0.3, 0.10, 0.12), (sx * (a - ov / 2 - 0.1), y, z), Matrix.Rotation(-sx * math.radians(14), 4, 'Y'))
            y += 0.42
    mesh_obj(f'Temple{tag}_Rafters', bm, coll, [red])
    if porch:
        yp = -(D / 2 + vw + 1.2)
        zp = z_roof - 0.15
        _roof_object(coll, f'Temple{tag}_PorchRoof', 3.7, 2.7, 1.5, (0, yp, zp), lift=0.5)
        bm = bmesh.new()
        for s in (-1, 1):
            add_box(bm, (0.32, 0.32, zp - ph + 0.25), (s * 2.9, -(D / 2 + vw - 0.25), (zp + ph + 0.25) / 2))
        add_box(bm, (6.4, 0.3, 0.36), (0, -(D / 2 + vw - 0.25), zp + 0.2))
        mesh_obj(f'Temple{tag}_PorchPosts', bm, coll, [red], bevel=0.015)
    for k in range(lanterns):
        x = (-1) ** k * W * (0.17 + 0.2 * (k // 2))
        paper_lantern(coll, (x, -(D / 2 + vw - 0.35), ph + 2.75))
    if door_light > 0:
        l = bpy.data.lights.new(f'LGT_Temple{tag}_Door', 'AREA')
        l.shape, l.size, l.size_y, l.energy, l.color = 'RECTANGLE', 3.2, 2.6, door_light, (1.0, 0.13, 0.04)
        ob = bpy.data.objects.new(l.name, l)
        ob.location = (0, -D / 2 - 0.25, ph + 1.7)
        ob.rotation_euler = (math.radians(-90), 0, 0)         # light travels toward -Y, out over the stairs
        coll.objects.link(ob)


def build_stairs(coll, width=9.0, n=9, rise=0.17, run=0.36, name='Stairs'):
    """Rises toward +Y from y=0."""
    bm = bmesh.new()
    for i in range(n):
        add_box(bm, (width, run * (n - i), rise), (0, run * i + run * (n - i) / 2, rise * i + rise / 2))
    L, H = run * n, rise * n
    for s in (-1, 1):
        x0, x1 = s * (width / 2), s * (width / 2 + 0.7)
        a = [bm.verts.new((x0, y, z)) for y, z in ((-0.3, 0), (L, 0), (L, H + 0.4), (-0.3, 0.45))]
        b = [bm.verts.new((x1, y, z)) for y, z in ((-0.3, 0), (L, 0), (L, H + 0.4), (-0.3, 0.45))]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
        bm.faces.new(a)
        bm.faces.new(b[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_obj(name, bm, coll, [mat_stone()], bevel=0.025)


def build_nobori(coll, h=4.6, seed=0):
    bm = bmesh.new()
    add_cyl(bm, 0.04, 0.03, h, (0, 0, 0), 8)
    add_box(bm, (0.9, 0.035, 0.035), (0.36, 0, h - 0.15))
    add_box(bm, (0.5, 0.5, 0.3), (0, 0, 0.15))
    mesh_obj('Nobori_Pole', bm, coll, [mat_simple('MAT_Black', (0.01, 0.01, 0.012), 0.4)], smooth=True, sharp_deg=40)
    build_banner(coll, 'Nobori_Banner', 0.72, 3.2, (0.42, 0, h - 0.17), seed=seed)


# ------------------------------------------------------------------ rocks / rubble
def make_rock_meshes(n=9, seed=11):
    rnd = random.Random(seed)
    out = []
    for k in range(n):
        bm = bmesh.new()
        sx, sy, sz = rnd.uniform(0.6, 1.0), rnd.uniform(0.5, 1.0), (rnd.uniform(0.12, 0.22) if k >= n - 3 else rnd.uniform(0.35, 0.7))
        for _ in range(16):
            v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized() * rnd.uniform(0.7, 1.0)
            bm.verts.new((v.x * sx * 0.5, v.y * sy * 0.5, v.z * sz * 0.5))
        r = bmesh.ops.convex_hull(bm, input=bm.verts[:])
        junk = list({e for e in r.get('geom_interior', []) + r.get('geom_unused', []) if isinstance(e, bmesh.types.BMVert)})
        if junk:
            bmesh.ops.delete(bm, geom=junk, context='VERTS')
        me = bpy.data.meshes.new(f'Rock{k}')
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat_stone())
        out.append(me)
    # two squared masonry blocks and one fallen drum
    for k, size in enumerate(((1.5, 0.7, 0.55), (0.9, 0.6, 0.4))):
        bm = bmesh.new()
        add_box(bm, size)
        subdivide(bm, 3)
        rockify(bm, 0.05, 2.0, k + 2)
        me = bpy.data.meshes.new(f'Block{k}')
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(40))
        me.materials.append(mat_stone())
        out.append(me)
    return out


def scatter_rubble(coll, rocks, centre, radius, count, seed, smax=1.6, keep_clear=None):
    rnd = random.Random(seed)
    made = 0
    for i in range(count * 3):
        if made >= count:
            break
        ang, rr = rnd.uniform(0, 6.283), radius * math.sqrt(rnd.random())
        p = Vector((centre[0] + rr * math.cos(ang), centre[1] + rr * math.sin(ang), 0))
        if keep_clear and keep_clear(p):
            continue
        s = rnd.uniform(0.25, 1.0) ** 2 * smax + 0.12
        ob = bpy.data.objects.new('Rubble', rnd.choice(rocks))
        ob.location = (p.x, p.y, 0.16 * s)
        ob.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 6.283))
        ob.scale = (s, s * rnd.uniform(0.7, 1.2), s * rnd.uniform(0.7, 1.1))
        coll.objects.link(ob)
        made += 1


# ------------------------------------------------------------------ trees
def build_cherry(coll, seed=1, height=7.5, name='Cherry', bough=False, r0=0.15):
    rnd = random.Random(seed)
    cu = bpy.data.curves.new(name + '_Wood', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = '3D', 1.0, 2, True
    spots = []

    def branch(p0, d, length, radius, depth):
        n, pts, p, dd = 6, [], p0.copy(), d.copy()
        for i in range(n + 1):
            pts.append((p.copy(), max(0.012, radius * (1 - 0.6 * i / n))))
            dd = (dd + Vector((rnd.uniform(-.28, .28), rnd.uniform(-.28, .28), rnd.uniform(-.16, .2)))).normalized()
            p = p + dd * (length / n)
        sp = cu.splines.new('POLY')
        sp.points.add(n)
        for i, (q, r) in enumerate(pts):
            sp.points[i].co = (q.x, q.y, q.z, 1)
            sp.points[i].radius = r
        if depth <= 2:
            spots.extend(q for q, _ in pts[2:])
        if depth == 0:
            return
        for k in range(rnd.randint(2, 3) + (1 if depth >= 3 else 0)):
            i = rnd.randint(2, n)
            q, r = pts[i]
            nd = (dd * 0.5 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.25, 0.55)))).normalized()
            branch(q, nd, length * rnd.uniform(0.62, 0.82), r * 0.72, depth - 1)

    if bough:
        branch(Vector((0, 0, 0)), Vector((1, rnd.uniform(-.1, .1), 0.12)), height * 0.5, r0, 3)
    else:
        branch(Vector((0, 0, -0.2)), Vector((rnd.uniform(-.25, .25), rnd.uniform(-.25, .25), 1)), height * 0.42, height * 0.042, 4)
    wood = bpy.data.objects.new(name + '_Wood', cu)
    wood.data.materials.append(mat_simple('MAT_Bark', (0.022, 0.016, 0.016), 0.7, bump=0.8, bump_scale=30, snow=0.6))
    coll.objects.link(wood)
    bm = bmesh.new()
    for q in spots:
        for _ in range(rnd.randint(34, 56)):
            c = q + Vector((rnd.gauss(0, 0.33), rnd.gauss(0, 0.33), rnd.gauss(0, 0.26)))
            s = rnd.uniform(0.03, 0.058)
            R = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-1.3, 1.3), 3, 'X')
            vs = [bm.verts.new(c + R @ Vector((x * s, y * s, 0))) for x, y in ((-1, 0), (-0.4, -0.8), (0.6, -0.75), (1, 0), (0.6, 0.75), (-0.4, 0.8))]
            bm.faces.new(vs)
    mesh_obj(name + '_Blossom', bm, coll, [mat_blossom()])
    return len(spots)


def build_pine(coll, seed=1, height=16.0, name='Pine'):
    rnd = random.Random(seed)
    bm = bmesh.new()
    add_cyl(bm, height * 0.022, height * 0.008, height * 0.95, (0, 0, 0), 7)
    z, tiers = height * 0.22, 7
    for i in range(tiers):
        t = i / (tiers - 1)
        r = height * 0.24 * (1 - 0.72 * t) * rnd.uniform(0.85, 1.1)
        h = height * 0.22 * (1 - 0.3 * t)
        add_cyl(bm, r, r * 0.08, h, (rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), z), 9, tris=True)
        z += h * 0.52
    subdivide(bm, 1)
    rockify(bm, height * 0.022, 1.3, seed)
    return mesh_obj(name, bm, coll, [mat_simple('MAT_Pine', (0.008, 0.016, 0.012), 0.8, snow=0.5)], smooth=True, sharp_deg=50)


# ------------------------------------------------------------------ floor
def build_floor(coll, x0, x1, y0, y1, seed=5):
    rnd = random.Random(seed)
    bm = bmesh.new()
    y = y0
    gap = 0.022
    while y < y1 - 0.2:
        d = min(rnd.uniform(1.15, 1.6), y1 - y)
        x = x0 - rnd.uniform(0, 0.8)
        while x < x1 - 0.2:
            w = min(rnd.uniform(1.0, 2.1), x1 - x)
            xa, xb = max(x, x0), x + w
            if xb - xa > 0.25:
                top = rnd.gauss(0, 0.0045)
                tilt = Matrix.Rotation(rnd.gauss(0, 0.004), 4, 'X') @ Matrix.Rotation(rnd.gauss(0, 0.004), 4, 'Y')
                add_box(bm, (xb - xa - gap, d - gap, 0.16), ((xa + xb) / 2, y + d / 2, top - 0.08), tilt)
            x += w
        y += d
    return mesh_obj('Floor_Slabs', bm, coll, [mat_floor()], bevel=0.012)


def build_frame_bough(coll, pts, seed=1, name='FrameBough', r0=0.13):
    """Art-directed blossom limb through world-space waypoints (frames the low-angle shots)."""
    rnd = random.Random(seed)
    cu = bpy.data.curves.new(name + '_Wood', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = '3D', 1.0, 2, True
    # densify the waypoint polyline with Catmull-Rom so the limb bends smoothly
    P = [Vector(p) for p in pts]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    path = []
    for i in range(1, len(P) - 2):
        for k in range(8):
            t = k / 8
            a, b, c, d = P[i - 1], P[i], P[i + 1], P[i + 2]
            path.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3))
    path.append(P[-2])
    n = len(path)
    sp = cu.splines.new('POLY')
    sp.points.add(n - 1)
    for i, q in enumerate(path):
        sp.points[i].co = (q.x, q.y, q.z, 1)
        sp.points[i].radius = r0 * (1 - 0.8 * i / (n - 1))
    spots = []
    for i in range(int(n * 0.25), n):
        for _ in range(rnd.randint(1, 3)):
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.9, 0.35))).normalized()
            L, m = rnd.uniform(0.7, 1.9), 5
            tw = cu.splines.new('POLY')
            tw.points.add(m)
            p = path[i].copy()
            for j in range(m + 1):
                tw.points[j].co = (p.x, p.y, p.z, 1)
                tw.points[j].radius = max(0.008, 0.035 * (1 - j / m))
                if j >= 1:
                    spots.append(p.copy())
                d = (d + Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), rnd.uniform(-.3, .1)))).normalized()
                p = p + d * (L / m)
    wood = bpy.data.objects.new(name + '_Wood', cu)
    wood.data.materials.append(mat_simple('MAT_Bark', (0.022, 0.016, 0.016), 0.7, bump=0.8, bump_scale=30, snow=0.6))
    coll.objects.link(wood)
    bm = bmesh.new()
    for q in spots:
        for _ in range(rnd.randint(16, 30)):
            c = q + Vector((rnd.gauss(0, 0.16), rnd.gauss(0, 0.16), rnd.gauss(0, 0.13)))
            s = rnd.uniform(0.022, 0.04)
            R = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-1.3, 1.3), 3, 'X')
            vs = [bm.verts.new(c + R @ Vector((x * s, y * s, 0))) for x, y in ((-1, 0), (-0.4, -0.8), (0.6, -0.75), (1, 0), (0.6, 0.75), (-0.4, 0.8))]
            bm.faces.new(vs)
    mesh_obj(name + '_Blossom', bm, coll, [mat_blossom()])
