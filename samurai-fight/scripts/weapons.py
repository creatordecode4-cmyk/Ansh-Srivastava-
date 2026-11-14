"""Procedural katanas for the drawn-sword shots (clean straight geometry so blades can meet exactly).
Local axes: +Z along the blade toward the tip, cutting edge faces -Y, origin at the guard (tsuba).
The grip runs from z = -0.27 to 0. Sizes in metres.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix
from sf_lib import NT, new_mat, pset

BLADE_L, GRIP_L = 0.74, 0.27

STYLES = {
    # blade pattern colour, fittings colour (metal), guard shape, tassel
    'Oni': dict(pattern=(0.80, 0.66, 0.42), fit=(0.83, 0.62, 0.28), guard='mokko', tassel=True),
    'Ronin': dict(pattern=(0.92, 0.93, 0.95), fit=(0.72, 0.74, 0.78), guard='square', tassel=False),
}


def mat_blade(name, pattern):
    """Black steel with a pale flame pattern flowing along the middle of the blade, and a polished edge.
    Uses the blade UVs: u = metres along the blade, v = -1 at the cutting edge .. +1 at the spine."""
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    u, v, _ = nt.sep(nt.coords('UV'))
    comb = nt.new('ShaderNodeCombineXYZ')
    nt.link(nt.math('MULTIPLY', u, 7.0), comb.inputs[0])
    nt.link(nt.math('MULTIPLY', v, 0.9), comb.inputs[1])
    warp = nt.noise(comb.outputs[0], 1.6, 3, 0.5)
    comb2 = nt.new('ShaderNodeCombineXYZ')
    nt.link(nt.math('ADD', nt.math('MULTIPLY', u, 7.0), nt.math('MULTIPLY', warp, 1.6)), comb2.inputs[0])
    nt.link(nt.math('ADD', nt.math('MULTIPLY', v, 0.9), nt.math('MULTIPLY', warp, 0.9)), comb2.inputs[1])
    n = nt.noise(comb2.outputs[0], 1.9, 2, 0.4)
    band = nt.maprange(nt.math('ABSOLUTE', nt.math('SUBTRACT', v, 0.0)), 0.95, 0.35)     # strongest mid-width
    flame = nt.ramp(nt.math('MULTIPLY', n, nt.math('ADD', 0.55, nt.math('MULTIPLY', band, 0.45))), [(0.50, 0.0), (0.52, 1.0)], 'EASE')
    flame = nt.math('MULTIPLY', flame, nt.maprange(u, 0.04, 0.10))                     # clean steel at the collar
    edge = nt.maprange(v, -0.70, -0.82)
    col = nt.mix(flame, (0.012, 0.012, 0.014), pattern)
    col = nt.mix(edge, col, (0.70, 0.72, 0.76))
    rough = nt.mix(flame, (0.14,) * 3, (0.32,) * 3)
    pset(nt, b, color=col, rough=rough, metal=1.0)
    return m


def mat_metal(name, color, rough=0.36):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    n = nt.noise(nt.coords('Object'), 180.0, 4, 0.6)
    pset(nt, b, color=nt.mix(n, tuple(c * 0.75 for c in color), color), rough=nt.mix(n, (rough * 0.8,) * 3, (rough * 1.4,) * 3),
         metal=1.0, normal=nt.bump(n, 0.08, 0.002))
    return m


def mat_wrap(name='MAT_KatanaWrap'):
    """Black braid over white ray-skin: the classic diamond pattern, built from two crossing stripe sets."""
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    x, y, z = nt.sep(nt.coords('Object'))
    ang = nt.math('ARCTAN2', x, y)                                  # around the grip
    u = nt.math('MULTIPLY', ang, 0.0165 / 1.0)                      # ~ arc length at grip radius
    a = nt.math('ABSOLUTE', nt.math('SINE', nt.math('MULTIPLY', nt.math('ADD', z, u), math.pi / 0.030)))
    c = nt.math('ABSOLUTE', nt.math('SINE', nt.math('MULTIPLY', nt.math('SUBTRACT', z, u), math.pi / 0.030)))
    diamond = nt.math('MULTIPLY', nt.math('GREATER_THAN', a, 0.80), nt.math('GREATER_THAN', c, 0.80))   # small white windows in black braid
    braid = nt.math('SUBTRACT', 1.0, diamond)
    grain = nt.noise(nt.coords('Object'), 900.0, 3, 0.6)
    col = nt.mix(diamond, nt.mix(grain, (0.008, 0.008, 0.009), (0.03, 0.03, 0.033)), nt.mix(grain, (0.62, 0.60, 0.56), (0.85, 0.83, 0.78)))
    hgt = nt.math('ADD', nt.math('MULTIPLY', braid, 1.0), nt.math('MULTIPLY', grain, 0.25))
    pset(nt, b, color=col, rough=nt.mix(diamond, (0.75,) * 3, (0.45,) * 3), normal=nt.bump(hgt, 0.6, 0.0012))
    return m


def _ring(bm, pts, M):
    return [bm.verts.new(M @ Vector(p)) for p in pts]


def _skin(bm, rings, mat_index, cap_start=True, cap_end=True, uvs=None):
    """uvs: per ring, one (u, v) per point. Used by the blade shader (u = metres along, v = -1 edge .. +1 spine)."""
    n = len(rings[0])
    uvl = bm.loops.layers.uv.verify()
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((a[k], a[k2], b[k2], b[k]))
            f.material_index = mat_index
            if uvs:
                for l, uv in zip(f.loops, (uvs[i][k], uvs[i][k2], uvs[i + 1][k2], uvs[i + 1][k])):
                    l[uvl].uv = uv
    if cap_start:
        bm.faces.new(rings[0][::-1]).material_index = mat_index
    if cap_end:
        bm.faces.new(rings[-1]).material_index = mat_index


def build_katana(coll, name='Katana_Oni', style='Oni'):
    st = STYLES[style]
    bm = bmesh.new()
    sori, w0, w1, th = 0.030, 0.031, 0.023, 0.0068

    def frame(z):                                   # centre line bends toward the spine (+Y)
        t = z / BLADE_L
        y = sori * t * t
        ang = math.atan2(2 * sori * t / BLADE_L, 1.0)
        return Matrix.Translation((0, y, z)) @ Matrix.Rotation(-ang, 4, 'X')

    # --- blade: 0 = material blade
    rings, uvs, N, tip = [], [], 56, 0.05
    for i in range(N + 1):
        z = 0.022 + (BLADE_L - 0.022) * (i / N) ** 0.92
        t = z / BLADE_L
        w = w0 + (w1 - w0) * t
        k = 1.0
        if z > BLADE_L - tip:                      # kissaki: the edge sweeps up to the spine
            k = max(0.02, math.sqrt(max(0.0, 1 - ((z - (BLADE_L - tip)) / tip) ** 2)))
        spine, ridge, edge = w / 2, w / 2 - 0.30 * w, w / 2 - w * k
        s = th * (0.55 + 0.45 * k)
        pts = [(-s * 0.28, spine, 0), (s * 0.28, spine, 0), (s * 0.5, max(ridge, edge + 1e-4), 0), (0, edge, 0), (-s * 0.5, max(ridge, edge + 1e-4), 0)]
        rings.append(_ring(bm, pts, frame(z)))
        uvs.append([(z, 1.0), (z, 1.0), (z, 0.4), (z, -1.0), (z, 0.4)])
    _skin(bm, rings, 0, uvs=uvs)
    # --- collar (habaki) + guard (tsuba) + grip caps: 1 = fittings
    hb = [_ring(bm, [(-0.0052, 0.0185, 0), (0.0052, 0.0185, 0), (0.0052, -0.0185, 0), (-0.0052, -0.0185, 0)], Matrix.Translation((0, 0, z))) for z in (0.004, 0.030)]
    _skin(bm, hb, 1)
    segs = 40
    if st['guard'] == 'mokko':
        shape = lambda a: 0.040 * (1 + 0.10 * math.cos(4 * a))
    else:
        shape = lambda a: 0.033 / max(abs(math.cos(a)), abs(math.sin(a))) ** 0.55
    gz = [(-0.003, 0.94), (-0.0015, 1.0), (0.0015, 1.0), (0.003, 0.94)]
    gr = [_ring(bm, [(shape(2 * math.pi * k / segs) * s * math.sin(2 * math.pi * k / segs) * 0.82,
                      shape(2 * math.pi * k / segs) * s * math.cos(2 * math.pi * k / segs), 0) for k in range(segs)], Matrix.Translation((0, 0, z)))
          for z, s in gz]
    _skin(bm, gr, 1)

    def oval(z, rx, ry, n=20):
        return _ring(bm, [(rx * math.sin(2 * math.pi * k / n), ry * math.cos(2 * math.pi * k / n), 0) for k in range(n)], Matrix.Translation((0, 0, z)))

    _skin(bm, [oval(-0.016, 0.0125, 0.0185), oval(-0.003, 0.0125, 0.0185)], 1)                       # fuchi
    _skin(bm, [oval(-GRIP_L, 0.0118, 0.0172), oval(-GRIP_L + 0.004, 0.0128, 0.0188), oval(-GRIP_L + 0.02, 0.0128, 0.0188)], 1)   # kashira
    # --- grip: 2 = wrap
    _skin(bm, [oval(-GRIP_L + 0.02 + (GRIP_L - 0.036) * i / 10, 0.0118 - 0.0008 * math.sin(math.pi * i / 10), 0.0174 - 0.001 * math.sin(math.pi * i / 10), 24)
               for i in range(11)], 2, False, False)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(38))
    me.materials.append(mat_blade(f'MAT_Blade_{style}', st['pattern']))
    me.materials.append(mat_metal(f'MAT_Fittings_{style}', st['fit']))
    me.materials.append(mat_wrap())
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if st['tassel']:
        tb = bmesh.new()
        bmesh.ops.create_cone(tb, cap_ends=True, segments=8, radius1=0.0035, radius2=0.0035, depth=0.09, matrix=Matrix.Translation((0, 0, -0.045)))
        bmesh.ops.create_cone(tb, cap_ends=True, segments=12, radius1=0.017, radius2=0.007, depth=0.10, matrix=Matrix.Translation((0, 0, -0.14)))
        tm = bpy.data.meshes.new(name + '_Tassel')
        tb.to_mesh(tm)
        tb.free()
        tm.shade_smooth()
        m, h = new_mat('MAT_SwordTassel')
        if h:
            pset(h[0], h[1], color=(0.45, 0.012, 0.012), rough=0.8, sheen=0.3)
        tm.materials.append(m)
        t = bpy.data.objects.new(name + '_Tassel', tm)
        coll.objects.link(t)
        t.parent = ob
        t.location = (0, 0.004, -GRIP_L)
        up = bpy.data.objects.new(name + '_TasselUp', None)        # world-aligned reference: the tassel hangs straight down
        coll.objects.link(up)
        c = t.constraints.new('COPY_ROTATION')
        c.target = up
    return ob
