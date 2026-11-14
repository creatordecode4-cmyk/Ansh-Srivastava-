"""STAGE 2 - the two fighters, modelled procedurally on a shared humanoid skeleton.

build_ronin(collection) / build_oni(collection) return a dict with the armature and the
separate prop objects (katanas, scabbards, cape, waist cloth, hat halves, mask, hair, hakama).
Characters are built in a T-pose facing -Y, left side = +X, feet on z = 0.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
import lib, charlib
from lib import MB, flat, TRS
from charlib import tube, torus, tbox, Rig, orient, build_katana, skin_rings

R = math.radians
TAU = 6.2832


def sstep(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def interp(keys, x):
    """Smooth piecewise interpolation through sorted (x, v1, v2, ...) keys."""
    if x <= keys[0][0]:
        return keys[0][1:]
    for k0, k1 in zip(keys, keys[1:]):
        if x <= k1[0]:
            t = sstep(x, k0[0], k1[0])
            return tuple(a + (b - a) * t for a, b in zip(k0[1:], k1[1:]))
    return keys[-1][1:]


# =============================================================== materials
def armor_mat(name, color, rough=0.38, metallic=0.0, dirt=0.75, coat=0.0):
    """Painted / metal plate with grime gathering in the creases (ambient-occlusion mask)."""
    m, nt, bsdf, out = lib._new(name)
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = 0.035
    ao.samples = 4
    vec, _ = lib._coords(nt, 1.0)
    nz = lib._noise(nt, 22.0, 6.0, vec, 0.65)
    crease = lib._ramp(nt, ao.outputs['AO'], 0.35, 0.95)
    wear = lib._madd(nt, nz, 0.25, 0.80)
    c = lib._mixc(nt, 1.0, (*color, 1), wear, 'MULTIPLY')
    c = lib._mixc(nt, lib._madd(nt, crease, -dirt, dirt), c, tuple(v * 0.12 for v in color))
    nt.links.new(c, bsdf.inputs['Base Color'])
    nt.links.new(lib._madd(nt, nz, 0.22, rough - 0.11, True), bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Coat Weight'].default_value = coat
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.08
    nt.links.new(lib._noise(nt, 90.0, 4.0, vec), b.inputs['Height']); nt.links.new(b.outputs[0], bsdf.inputs['Normal'])
    return m


def cloth_mat(name, color, tatter=0.16, holes=True, rough=0.85):
    """Woven cloth (UV: v = 0 at the hem) with a ragged, torn lower edge."""
    m, nt, bsdf, out = lib._new(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['UV'], sep.inputs[0])
    u, v = sep.outputs['X'], sep.outputs['Y']
    vec, _ = lib._coords(nt, 1.0)
    nz = lib._noise(nt, 7.0, 6.0, vec, 0.6)
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion'); ao.inputs['Distance'].default_value = 0.12; ao.samples = 4
    base = lib._mixc(nt, 1.0, (*color, 1), lib._madd(nt, nz, 0.35, 0.72), 'MULTIPLY')
    nt.links.new(lib._mixc(nt, 1.0, base, lib._ramp(nt, ao.outputs['AO'], 0.25, 1.0, (0.30, 0.30, 0.33, 1), (1, 1, 1, 1)), 'MULTIPLY'), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Sheen Weight'].default_value = 0.12
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 260.0
    wv.inputs['Distortion'].default_value = 1.5
    nt.links.new(vec, wv.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.25
    nt.links.new(wv.outputs[0], b.inputs['Height']); nt.links.new(b.outputs[0], bsdf.inputs['Normal'])
    cu = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(u, cu.inputs[0])
    t1 = nt.nodes.new('ShaderNodeTexNoise'); t1.inputs['Scale'].default_value = 24.0; t1.inputs['Detail'].default_value = 3.0
    nt.links.new(cu.outputs[0], t1.inputs['Vector'])
    alpha = lib._math(nt, 'GREATER_THAN', v, lib._math(nt, 'MULTIPLY', t1.outputs[0], tatter))
    if holes:
        h = lib._noise(nt, 26.0, 2.0, vec, 0.4)
        hole = lib._math(nt, 'MULTIPLY', lib._math(nt, 'GREATER_THAN', h, 0.70), lib._math(nt, 'LESS_THAN', v, 0.30))
        alpha = lib._math(nt, 'MULTIPLY', alpha, lib._math(nt, 'SUBTRACT', 1.0, hole))
    nt.links.new(alpha, bsdf.inputs['Alpha'])
    return m


def wrap_mat(name, a=(0.01, 0.01, 0.012), b=(0.8, 0.8, 0.78)):
    """Katana handle: diamond wrap pattern."""
    m, nt, bsdf, out = lib._new(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    ang = lib._math(nt, 'ARCTAN2', sep.outputs['X'], sep.outputs['Y'])
    p = lib._math(nt, 'ADD', lib._math(nt, 'MULTIPLY', sep.outputs['Z'], 120.0), lib._math(nt, 'MULTIPLY', ang, 2.0))
    q = lib._math(nt, 'SUBTRACT', lib._math(nt, 'MULTIPLY', sep.outputs['Z'], 120.0), lib._math(nt, 'MULTIPLY', ang, 2.0))
    d = lib._math(nt, 'MULTIPLY', lib._math(nt, 'SINE', p), lib._math(nt, 'SINE', q))
    nt.links.new(lib._mixc(nt, lib._math(nt, 'GREATER_THAN', d, 0.25), a, b), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.7
    bmp = nt.nodes.new('ShaderNodeBump'); bmp.inputs['Strength'].default_value = 0.5
    nt.links.new(d, bmp.inputs['Height']); nt.links.new(bmp.outputs[0], bsdf.inputs['Normal'])
    return m


def pattern_mat(name, base, accent, scale=9.0, thr=0.56, rough=0.18, metallic=0.0, accent_metal=0.0, stretch=(1, 1, 0.22)):
    """Lacquer / steel with a flowing flame pattern (scabbards and blades)."""
    m, nt, bsdf, out = lib._new(name)
    vec, _ = lib._coords(nt, tuple(scale * s for s in stretch))
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 1.0
    n.inputs['Detail'].default_value = 2.0; n.inputs['Distortion'].default_value = 1.6
    nt.links.new(vec, n.inputs['Vector'])
    mask = lib._ramp(nt, n.outputs[0], thr, thr + 0.02)
    nt.links.new(lib._mixc(nt, mask, base, accent), bsdf.inputs['Base Color'])
    nt.links.new(lib._madd(nt, mask, accent_metal - metallic, metallic), bsdf.inputs['Metallic'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Coat Weight'].default_value = 0.5
    return m


def vcol_mat(name, base, tip, start=0.55, end=0.8, rough=0.45, only_marked=False):
    """Colour changes toward the tip of each swept strand (hair tips, horn tips)."""
    m, nt, bsdf, out = lib._new(name)
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'tcol'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(vc.outputs['Color'], sep.inputs[0])
    f = lib._ramp(nt, sep.outputs[0], start, end)
    if only_marked:
        f = lib._math(nt, 'MULTIPLY', f, lib._math(nt, 'GREATER_THAN', sep.outputs[1], 0.5))
    shade = lib._madd(nt, sep.outputs[0], 0.35, 0.70)
    c = lib._mixc(nt, f, (*base, 1), (*tip, 1))
    nt.links.new(lib._mixc(nt, 1.0, c, shade, 'MULTIPLY'), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    return m


def gradient_hakama():
    """Black hakama fading to red at the hem, with black flames licking up through the red."""
    m, nt, bsdf, out = lib._new('MAT_Oni_Hakama')
    geo = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Object'], sep.inputs[0])
    z = sep.outputs['Z']
    vec, _ = lib._coords(nt, (7.0, 7.0, 2.6))
    fl = nt.nodes.new('ShaderNodeTexNoise'); fl.inputs['Scale'].default_value = 1.0
    fl.inputs['Detail'].default_value = 2.5; fl.inputs['Distortion'].default_value = 1.8
    nt.links.new(vec, fl.inputs['Vector'])
    red_zone = lib._ramp(nt, lib._math(nt, 'ADD', z, lib._madd(nt, fl.outputs[0], 0.22, -0.11)), 0.30, 0.52,
                         (1, 1, 1, 1), (0, 0, 0, 1))
    flames = lib._math(nt, 'MULTIPLY', lib._ramp(nt, fl.outputs[0], 0.60, 0.63), lib._ramp(nt, z, 0.10, 0.20))
    red = lib._math(nt, 'MULTIPLY', red_zone, lib._math(nt, 'SUBTRACT', 1.0, flames), clamp=True)
    nz = lib._noise(nt, 30.0, 4.0)
    c = lib._mixc(nt, red, (0.012, 0.012, 0.014), (0.50, 0.018, 0.012))
    nt.links.new(lib._mixc(nt, 1.0, c, lib._madd(nt, nz, 0.3, 0.8), 'MULTIPLY'), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.82
    bsdf.inputs['Sheen Weight'].default_value = 0.12
    return m


def skin_mat():
    m, nt, bsdf, out = lib._new('MAT_Oni_Skin')
    vec, _ = lib._coords(nt, 1.0)
    nz = lib._noise(nt, 40.0, 5.0, vec)
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion'); ao.inputs['Distance'].default_value = 0.05; ao.samples = 4
    c = lib._mixc(nt, lib._ramp(nt, ao.outputs['AO'], 0.45, 1.0), (0.42, 0.30, 0.30), (0.74, 0.68, 0.66))
    nt.links.new(lib._mixc(nt, 1.0, c, lib._madd(nt, nz, 0.12, 0.92), 'MULTIPLY'), bsdf.inputs['Base Color'])
    nt.links.new(lib._madd(nt, nz, 0.2, 0.38), bsdf.inputs['Roughness'])
    bsdf.inputs['Subsurface Weight'].default_value = 0.2
    bsdf.inputs['Subsurface Radius'].default_value = (0.012, 0.006, 0.004)
    return m


def hat_mat():
    m, nt, bsdf, out = lib._new('MAT_Ronin_Kasa')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    x, y = sep.outputs['X'], sep.outputs['Y']
    ang = lib._math(nt, 'ARCTAN2', y, x)
    rad = lib._math(nt, 'SQRT', lib._math(nt, 'ADD', lib._math(nt, 'MULTIPLY', x, x), lib._math(nt, 'MULTIPLY', y, y)))
    ribs = lib._math(nt, 'ABSOLUTE', lib._math(nt, 'SINE', lib._math(nt, 'MULTIPLY', ang, 16.0)))
    rings = lib._math(nt, 'ABSOLUTE', lib._math(nt, 'SINE', lib._math(nt, 'MULTIPLY', rad, 34.0)))
    line = lib._math(nt, 'MINIMUM', lib._ramp(nt, ribs, 0.0, 0.07), lib._ramp(nt, rings, 0.0, 0.10))
    nz = lib._noise(nt, 30.0, 5.0)
    c = lib._mixc(nt, line, (0.25, 0.25, 0.26), (0.62, 0.62, 0.64))
    nt.links.new(lib._mixc(nt, 1.0, c, lib._madd(nt, nz, 0.2, 0.86), 'MULTIPLY'), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.5; b.inputs['Distance'].default_value = 0.01
    nt.links.new(line, b.inputs['Height']); nt.links.new(b.outputs[0], bsdf.inputs['Normal'])
    return m


# =============================================================== shared pieces
def drape(name, collection, mat, z_fn, shape_fn, th0, th1, nth=72, ns=28, ripple=0.014, nrip=9, seed=0):
    """Hanging cloth sheet wrapped round the body. theta: 0 = left (+X), 90 = back, 270 = front.
    z_fn(s, th) -> height, shape_fn(s, th) -> ellipse radii (a, b); s runs 0 (top) .. 1 (hem)."""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, TAU) for _ in range(4)]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    closed = abs((th1 - th0) - 360) < 1e-3
    cols = nth if closed else nth + 1
    grid = {}
    for i in range(cols):
        th = R(th0 + (th1 - th0) * i / nth)
        for j in range(ns + 1):
            s = j / ns
            a, b = shape_fn(s, th)
            f = math.sin(nrip * th + ph[0] + 2.0 * s) + 0.6 * math.sin((nrip * 1.7) * th + ph[1] - 3 * s) + 0.35 * math.sin((nrip * 3.1) * th + ph[2])
            d = ripple * (0.15 + s) * f
            grid[i, j] = bm.verts.new(((a + d) * math.cos(th), (b + d) * math.sin(th), z_fn(s, th) + 0.25 * d))
    for i in range(nth):
        for j in range(ns):
            i2 = (i + 1) % cols
            f = bm.faces.new((grid[i, j], grid[i, j + 1], grid[i2, j + 1], grid[i2, j]))
            f.smooth = True
            for lp, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                lp[uvl].uv = (ii / nth, 1 - jj / ns)
    me = bpy.data.meshes.new(name)
    bm.normal_update(); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    collection.objects.link(o)
    return o


def join_meshes(name, objs, collection):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    mats = []
    for o in objs:
        off = len(mats)
        for m in o.data.materials:
            mats.append(m)
        tmp = bmesh.new(); tmp.from_mesh(o.data)
        tl = tmp.loops.layers.uv.active
        vmap = {v: bm.verts.new(o.matrix_world @ v.co) for v in tmp.verts}
        for f in tmp.faces:
            nf = bm.faces.new([vmap[v] for v in f.verts])
            nf.smooth, nf.material_index = f.smooth, off + f.material_index
            if tl:
                for a, b in zip(nf.loops, f.loops):
                    a[uvl].uv = b[tl].uv
        tmp.free()
        bpy.data.objects.remove(o)
    me = bpy.data.meshes.new(name)
    bm.normal_update(); bm.to_mesh(me); bm.free()
    uniq = []
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    collection.objects.link(o)
    return o


def place_obj(ob, loc, z_dir, y_hint=(0, 0, 1)):
    ob.matrix_world = Matrix.Translation(loc) @ orient(z_dir, y_hint)
    bpy.context.view_layer.update()


# =============================================================== CYBER RONIN
J_RONIN = dict(hip=1.00, hip_x=0.10, knee=0.53, ankle=0.09, spine=1.10, chest=1.28, neck=1.55, head=1.62, top=1.86,
               sh_z=1.50, sh_x=0.20, elbow=0.50, wrist=0.77, knuckle=0.86, tip=0.95)


def build_ronin(C):
    W, K, JT, VIS = 0, 1, 2, 3
    mats = [armor_mat('MAT_Ronin_Armor', (0.60, 0.61, 0.64), 0.36, dirt=0.85, coat=0.2),
            armor_mat('MAT_Ronin_Frame', (0.022, 0.023, 0.026), 0.42, metallic=1.0, dirt=0.3),
            armor_mat('MAT_Ronin_Joint', (0.07, 0.07, 0.075), 0.30, metallic=1.0, dirt=0.5),
            flat('MAT_Ronin_Visor', (0.004, 0.004, 0.006), 0.06)]
    rg = Rig('Ronin', J_RONIN, C)
    X90, Y90 = (R(90), 0, 0), (0, R(90), 0)

    h = rg.mb('hips')
    h.cube((0.24, 0.15, 0.13), (0, 0, 1.02), mat=K)
    tbox(h, (0.12, 0.03, 0.15), (0, -0.088, 1.00), mat=W, top=(1.5, 1))
    tbox(h, (0.17, 0.03, 0.12), (0, 0.088, 1.02), mat=W, top=(1.2, 1))
    h.cone(0.138, 0.138, 0.05, (0, 0, 1.088), segs=24, mat=K, scale=(1, 0.72, 1))
    for sx in (1, -1):
        tbox(h, (0.032, 0.15, 0.17), (sx * 0.138, 0, 1.00), mat=W, top=(1, 1.15))
        h.sphere(0.07, (sx * 0.10, 0, 1.0), mat=JT)

    s = rg.mb('spine')
    s.cone(0.092, 0.100, 0.20, (0, 0, 1.19), segs=20, mat=K, scale=(1, 0.75, 1))
    for z in (1.125, 1.18, 1.235):
        s.cone(0.118, 0.118, 0.04, (0, 0, z), segs=24, mat=JT, scale=(1, 0.72, 1))
    tbox(s, (0.10, 0.025, 0.05), (0, -0.094, 1.150), mat=W, top=(1.1, 1))
    tbox(s, (0.12, 0.025, 0.05), (0, -0.097, 1.212), mat=W, top=(1.1, 1))

    c = rg.mb('chest')
    tbox(c, (0.30, 0.17, 0.26), (0, 0, 1.40), mat=K, top=(1.22, 1.0))
    for sx in (1, -1):
        tbox(c, (0.17, 0.07, 0.155), (sx * 0.098, -0.105, 1.445), (R(-8), 0, sx * R(7)), W, top=(1.08, 0.75))
        tbox(c, (0.05, 0.05, 0.05), (sx * 0.150, -0.10, 1.535), mat=W, top=(0.8, 0.8))
        c.cone(0.014, 0.014, 0.012, (sx * 0.042, -0.140, 1.325), X90, 12, JT)
        c.cube((0.034, 0.13, 0.17), (sx * 0.158, 0, 1.37), mat=K)
        c.sphere(0.062, (sx * 0.20, 0, 1.50), mat=JT)
        tbox(c, (0.10, 0.045, 0.20), (sx * 0.085, 0.118, 1.43), (0, 0, -sx * R(8)), W, top=(1.2, 1))
    tbox(c, (0.165, 0.035, 0.09), (0, -0.120, 1.325), mat=W, top=(1.12, 1))
    torus(c, 0.046, 0.013, (0, -0.138, 1.438), X90, 24, 8, K)
    c.cone(0.036, 0.030, 0.018, (0, -0.136, 1.438), X90, 20, JT)
    c.cone(0.016, 0.016, 0.024, (0, -0.140, 1.438), X90, 12, VIS)
    torus(c, 0.085, 0.024, (0, 0.005, 1.552), (R(8), 0, 0), 24, 8, W, scale=(1.12, 1, 1))
    c.cube((0.11, 0.06, 0.22), (0, 0.145, 1.40), mat=K)

    n = rg.mb('neck')
    n.cone(0.046, 0.042, 0.10, (0, 0, 1.59), segs=16, mat=JT)
    for z in (1.575, 1.605):
        torus(n, 0.047, 0.008, (0, 0, z), major=18, minor=6, mat=K)

    hd = rg.mb('head')
    hd.sphere(0.104, (0, 0.004, 1.735), (0.94, 1.08, 1.10), K, 24, 14)
    hd.sphere(0.119, (0, 0.016, 1.768), (0.97, 1.12, 0.88), W, 24, 14)
    hd.sphere(0.112, (0, -0.036, 1.716), (0.80, 1.0, 0.80), VIS, 24, 14)
    tbox(hd, (0.19, 0.07, 0.030), (0, -0.108, 1.790), (R(-22), 0, 0), W, top=(0.8, 0.8))
    tbox(hd, (0.085, 0.05, 0.05), (0, -0.112, 1.640), (R(12), 0, 0), W, top=(1.5, 1))
    tbox(hd, (0.028, 0.21, 0.04), (0, 0.005, 1.872), mat=W, top=(0.7, 0.8))
    for sx in (1, -1):
        tbox(hd, (0.034, 0.12, 0.105), (sx * 0.094, -0.05, 1.683), (0, 0, -sx * R(16)), W, top=(1, 0.68))
        hd.cone(0.036, 0.030, 0.03, (sx * 0.110, 0.012, 1.722), Y90, 16, K)
        hd.cone(0.016, 0.016, 0.04, (sx * 0.112, 0.012, 1.722), Y90, 10, JT)
        tube(hd, [(sx * 0.105, 0.0, 1.80), (sx * 0.14, -0.008, 1.84), (sx * 0.165, -0.012, 1.885)], 0.007, 8, K)   # hat struts

    for side, sx in (('L', 1), ('R', -1)):
        z = 1.50
        a = rg.mb('upper_arm.' + side)
        a.cone(0.043, 0.040, 0.30, (sx * 0.35, 0.01, z), Y90, 16, K)
        a.sphere(0.096, (sx * 0.215, 0, z + 0.03), (1.0, 1.06, 0.82), W, 20, 12)
        tbox(a, (0.13, 0.18, 0.026), (sx * 0.270, 0, z + 0.068), (0, sx * R(22), 0), W, top=(0.85, 0.85))
        tbox(a, (0.10, 0.16, 0.022), (sx * 0.330, 0, z + 0.040), (0, sx * R(38), 0), W, top=(0.85, 0.85))
        tbox(a, (0.14, 0.03, 0.08), (sx * 0.385, -0.047, z), mat=W, top=(1, 0.8))
        tbox(a, (0.14, 0.08, 0.028), (sx * 0.385, 0.005, z + 0.046), mat=W, top=(0.9, 0.8))
        for bx in (0.245, 0.30):
            a.cone(0.010, 0.010, 0.012, (sx * bx, -0.06, z + 0.07), (R(50), 0, 0), 10, JT)
        f = rg.mb('forearm.' + side)
        f.sphere(0.052, (sx * 0.50, 0.02, z), mat=JT)
        tbox(f, (0.075, 0.05, 0.075), (sx * 0.512, 0.062, z), mat=W, top=(0.8, 0.8))
        f.cone(0.036, 0.030, 0.27, (sx * 0.635, 0.008, z), (0, sx * R(90), 0), 14, K)
        f.cone(0.062, 0.046, 0.20, (sx * 0.655, 0.004, z), (0, sx * R(90), 0), 8, W)
        tbox(f, (0.17, 0.034, 0.032), (sx * 0.650, 0.0, z + 0.058), mat=W, top=(0.85, 0.7))
        for bx in (0.565, 0.75):
            torus(f, 0.040, 0.009, (sx * bx, 0.005, z), Y90, 16, 6, K)
        hn = rg.mb('hand.' + side)
        hn.sphere(0.033, (sx * 0.772, 0, z), mat=JT)
        hn.cube((0.088, 0.088, 0.030), (sx * 0.817, 0, z), mat=K)
        tbox(hn, (0.066, 0.072, 0.012), (sx * 0.817, 0, z + 0.020), mat=W, top=(0.85, 0.85))
        f1, f2, th = rg.mb('fingers1.' + side), rg.mb('fingers2.' + side), rg.mb('thumb.' + side)
        for fy in (-0.033, -0.011, 0.011, 0.033):
            f1.cube((0.046, 0.018, 0.020), (sx * 0.8825, fy, z), mat=K)
            f1.cube((0.030, 0.019, 0.006), (sx * 0.880, fy, z + 0.012), mat=W)
            f2.cube((0.042, 0.016, 0.018), (sx * 0.927, fy, z), mat=K)
        tube(th, [(sx * 0.795, -0.03, z - 0.008), (sx * 0.825, -0.058, z - 0.014), (sx * 0.852, -0.080, z - 0.02)], [0.013, 0.012, 0.010], 8, K)

        t = rg.mb('thigh.' + side)
        x = sx * 0.10
        t.cone(0.060, 0.050, 0.42, (x, -0.01, 0.765), segs=16, mat=K)
        tbox(t, (0.105, 0.045, 0.31), (x, -0.072, 0.79), (R(-3), 0, 0), W, top=(1.28, 1))
        tbox(t, (0.036, 0.12, 0.28), (x + sx * 0.066, -0.005, 0.80), mat=W, top=(1, 1.2))
        tbox(t, (0.09, 0.03, 0.2), (x, 0.065, 0.80), mat=W, top=(1.2, 1))
        sh = rg.mb('shin.' + side)
        sh.cone(0.056, 0.056, 0.125, (x, -0.02, 0.53), Y90, 18, JT)
        tbox(sh, (0.088, 0.05, 0.105), (x, -0.082, 0.538), mat=W, top=(0.8, 0.8))
        sh.cone(0.040, 0.050, 0.40, (x, 0.0, 0.31), segs=14, mat=K)
        tbox(sh, (0.095, 0.105, 0.35), (x, -0.012, 0.295), mat=W, top=(1.28, 1.30))
        for q in (-1, 1):
            tbox(sh, (0.028, 0.10, 0.20), (x + q * 0.066, 0.02, 0.365), mat=W, top=(1, 1.1))
        tbox(sh, (0.07, 0.03, 0.16), (x, 0.085, 0.36), mat=K, top=(1.2, 1))
        ft = rg.mb('foot.' + side)
        ft.sphere(0.043, (x, 0.02, 0.092), mat=JT)
        tbox(ft, (0.098, 0.165, 0.072), (x, -0.03, 0.045), mat=W, top=(0.82, 0.78))
        ft.cube((0.104, 0.195, 0.02), (x, -0.033, 0.010), mat=K)
        tbox(ft, (0.07, 0.06, 0.06), (x, 0.075, 0.045), mat=K, top=(0.8, 0.6))
        to = rg.mb('toe.' + side)
        tbox(to, (0.098, 0.088, 0.05), (x, -0.172, 0.036), mat=W, top=(0.9, 0.55))
        to.cube((0.104, 0.086, 0.02), (x, -0.172, 0.010), mat=K)
    rg.finish(mats, bevel=0.005)

    out = {'rig': rg.arm}
    # ---- kasa hat, built as two halves so it can split in the final shot
    hm = hat_mat()
    for side, a0 in (('L', -90), ('R', 90)):
        bm = bmesh.new()
        prof = [(0.0, 0.150), (0.045, 0.142), (0.062, 0.118), (0.17, 0.072), (0.29, 0.030), (0.39, 0.0), (0.40, -0.012)]
        rings = []
        for i in range(25):
            th = R(a0 + 180 * i / 24)
            rings.append([bm.verts.new((r_ * math.cos(th), r_ * math.sin(th), z_)) for r_, z_ in prof])
        mb = MB(); mb.bm.free(); mb.bm = bm
        skin_rings(mb, rings, 0, cap=False, flip=(a0 == 90))
        ho = mb.obj('Ronin_Hat_' + side, [hm], C, smooth=True)
        sm = ho.modifiers.new('Solid', 'SOLIDIFY'); sm.thickness, sm.offset = 0.012, -1
        ho.matrix_world = Matrix.Translation((0, -0.015, 1.878)) @ Euler((R(-8), 0, 0)).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        rg.attach(ho, 'head')
        out['hat_' + side] = ho

    # ---- cape: cowl round the neck, long on the left / back, short on the right front
    cm = cloth_mat('MAT_Ronin_Cloth', (0.58, 0.58, 0.60))
    hem = lambda th: 0.98 - 0.40 * math.cos(th - R(35))
    def cape_z(s, th):
        if s < 0.18:
            return 1.615 - 0.105 * sstep(s, 0, 0.18)
        return 1.51 + (hem(th) - 1.51) * (s - 0.18) / 0.82
    def cape_shape(s, th):
        left = max(0.0, math.cos(th)) ** 1.5
        k = sstep(s, 0.0, 0.2)
        a = 0.105 + (0.175 + 0.17 * left) * k + (0.05 + 0.05 * left) * s
        b = 0.105 + 0.085 * k + 0.05 * s
        return a, b
    cape = drape('Ronin_Cape', C, cm, cape_z, cape_shape, 0, 360, 150, 48, ripple=0.030, nrip=7, seed=4)
    sc = MB()
    torus(sc, 0.118, 0.046, (0, 0.0, 1.585), (R(10), R(-6), 0), 30, 10, 0, scale=(1.18, 1.0, 0.75), lump=0.22, seed=3)
    torus(sc, 0.105, 0.036, (0.01, 0.01, 1.625), (R(-6), R(8), 0), 26, 10, 0, scale=(1.1, 1.0, 0.7), lump=0.25, seed=5)
    scarf = sc.obj('Ronin_Scarf', [flat('MAT_Ronin_ClothSolid', (0.50, 0.50, 0.52), 0.85)], C, smooth=True)
    cape = join_meshes('Ronin_Cape', [cape, scarf], C)
    rg.attach(cape, 'chest')
    out['cape'] = cape

    # ---- waist cloth: knotted sash with hanging, torn panels
    def panel(nm, th0, th1, hemz, seed):
        zf = lambda s, th: 1.075 + (hemz - 1.075) * s + 0.025 * math.sin(3 * th + seed) * s
        sf = lambda s, th: (0.165 + 0.085 * s ** 0.7, 0.125 + 0.09 * s ** 0.7)
        return drape(nm, C, cm, zf, sf, th0, th1, max(6, int((th1 - th0) / 4)), 26, ripple=0.018, nrip=13, seed=seed)
    parts = [panel('p0', 48, 132, 0.40, 1), panel('p1', -28, 44, 0.54, 2), panel('p2', 136, 206, 0.48, 3),
             panel('p3', 282, 304, 0.38, 4), panel('p4', 236, 256, 0.50, 5)]
    k = MB()
    torus(k, 0.150, 0.036, (0, 0, 1.075), (0, 0, 0), 30, 10, 0, scale=(1.08, 0.80, 1.0), lump=0.2, seed=8)
    k.sphere(0.052, (0.0, -0.150, 1.07), (1.2, 0.8, 0.9))
    for sx in (1, -1):
        tube(k, [(sx * 0.02, -0.155, 1.07), (sx * 0.09, -0.185, 1.11), (sx * 0.14, -0.165, 1.06), (sx * 0.06, -0.150, 1.05)],
             [0.03, 0.036, 0.032, 0.026], 10, 0)
    parts.append(k.obj('knot', [flat('MAT_Ronin_ClothSolid2', (0.50, 0.50, 0.52), 0.85)], C, smooth=True))
    wc = join_meshes('Ronin_WaistCloth', parts, C)
    rg.attach(wc, 'hips')
    out['waist_cloth'] = wc

    # ---- twin katanas crossed on the back
    kmats = [pattern_mat('MAT_Ronin_Blade', (0.03, 0.03, 0.035), (0.85, 0.86, 0.88), 14.0, 0.55, 0.16, 1.0, 1.0, (1, 1, 0.12)),
             armor_mat('MAT_Ronin_Fitting', (0.55, 0.56, 0.58), 0.3, metallic=1.0, dirt=0.4), wrap_mat('MAT_Ronin_Wrap'),
             mats[K], pattern_mat('MAT_Ronin_Saya', (0.012, 0.012, 0.014), (0.75, 0.75, 0.77), 10.0, 0.60, 0.2), mats[JT]]
    for side, sx in (('L', 1), ('R', -1)):
        ko, so = build_katana(f'Ronin_Katana_{side}', C, kmats)
        ko.parent = so
        place_obj(so, (-sx * 0.25, 0.185 + 0.014 * sx, 1.66), (sx * 0.52, 0.03, -0.85), (1, 0, 0.3))
        rg.attach(so, 'chest')
        out['katana_' + side], out['saya_' + side] = ko, so
    return out


# =============================================================== ONI SAMURAI
J_ONI = dict(hip=1.04, hip_x=0.11, knee=0.56, ankle=0.09, spine=1.12, chest=1.34, neck=1.62, head=1.70, top=1.94,
             sh_z=1.575, sh_x=0.235, elbow=0.56, wrist=0.84, knuckle=0.93, tip=1.03)
TORSO = [(0.96, .165, .115), (1.06, .165, .110), (1.14, .160, .106), (1.24, .178, .116), (1.34, .206, .130),
         (1.44, .236, .142), (1.52, .246, .140), (1.585, .222, .124), (1.63, .135, .094), (1.665, .072, .070), (1.74, .062, .064)]


def torso_bump(x, z, front):
    """Muscle relief (metres, along the surface normal)."""
    g = lambda v, c, w: math.exp(-((v - c) / w) ** 2)
    d = 0.0
    ax = abs(x)
    if front:
        pec = g(ax, 0.105, 0.085) * (g(z, 1.475, 0.060) if z > 1.475 else g(z, 1.475, 0.045))
        d += 0.036 * pec
        d -= 0.012 * g(x, 0, 0.016) * sstep(z, 1.36, 1.42) * (1 - sstep(z, 1.55, 1.60))        # sternum line
        d += 0.012 * g(ax, 0.10, 0.07) * g(z, 1.59, 0.03)                                          # clavicles
        if 1.09 < z < 1.40:                                                                        # abdominals
            rows = 0.5 + 0.5 * math.cos(TAU * (z - 1.105) / 0.076)
            d += 0.018 * (rows ** 0.5) * g(ax, 0.043, 0.030) * sstep(z, 1.09, 1.13) * (1 - sstep(z, 1.36, 1.40))
            d -= 0.009 * g(x, 0, 0.012)
        d += 0.008 * g(ax, 0.150, 0.03) * g(z, 1.25, 0.10)                                         # obliques
    else:
        d -= 0.012 * g(x, 0, 0.022) * sstep(z, 1.10, 1.20) * (1 - sstep(z, 1.56, 1.62))            # spine groove
        d += 0.016 * g(ax, 0.11, 0.07) * g(z, 1.50, 0.07)                                          # shoulder blades
        d += 0.010 * g(ax, 0.07, 0.05) * g(z, 1.60, 0.04)                                          # traps
        d += 0.008 * g(ax, 0.06, 0.03) * g(z, 1.22, 0.10)                                          # erectors
    return d


def torso_point(th, z, offset=0.0):
    a, b = interp(TORSO, z)
    x, y = a * math.cos(th), b * math.sin(th)
    n = Vector((x / (a * a), y / (b * b), 0)).normalized()
    d = torso_bump(x, z, y < 0) + offset
    return Vector((x, y, z)) + n * d, n


def ribbon(mb, pts, normals, width, thick, mat, closed=True):
    n = len(pts)
    rings = []
    for i in range(n):
        t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        b = t.cross(normals[i]).normalized()
        p, nr = pts[i], normals[i]
        rings.append([mb.bm.verts.new(p - b * width / 2), mb.bm.verts.new(p + b * width / 2),
                      mb.bm.verts.new(p + b * width / 2 + nr * thick), mb.bm.verts.new(p - b * width / 2 + nr * thick)])
    skin_rings(mb, rings, mat, cap=not closed, closed=closed, smooth=False, flip=True)


def build_oni_body(C, mats):
    """Skinned torso + arms: analytic muscle loft, fused with a voxel remesh, weights painted by formula."""
    mb = MB()
    nz, nt_ = 96, 96
    rings = []
    for j in range(nz + 1):
        z = 0.96 + (1.74 - 0.96) * j / nz
        rings.append([mb.bm.verts.new(torso_point(TAU * i / nt_, z)[0]) for i in range(nt_)])
    skin_rings(mb, rings)
    ARM = [(0.17, .084), (0.235, .094), (0.30, .080), (0.40, .071), (0.50, .054), (0.56, .049), (0.64, .056), (0.74, .046), (0.86, .036)]
    for sx in (1, -1):
        arings = []
        for j in range(57):
            x = 0.17 + (0.86 - 0.17) * j / 56
            r = interp(ARM, x)[0]
            ring = []
            for i in range(28):
                a = TAU * i / 28
                dy, dz = math.cos(a), math.sin(a)
                bump = 0.014 * math.exp(-((x - 0.40) / 0.07) ** 2) * max(0, -dy * 0.6 + dz * 0.8) \
                     + 0.010 * math.exp(-((x - 0.39) / 0.08) ** 2) * max(0, dy * 0.8 - dz * 0.6) \
                     + 0.010 * math.exp(-((x - 0.63) / 0.06) ** 2) * max(0, dz)
                ring.append(mb.bm.verts.new((sx * x, 0.008 + dy * (r + bump) * (1 if sx > 0 else 1), 1.575 + dz * (r + bump))))
            arings.append(ring if sx > 0 else ring[::-1])
        skin_rings(mb, arings)
        mb.sphere(0.098, (sx * 0.240, 0.005, 1.580), (1.12, 1.0, 0.98), u=24, v=14)
    raw = mb.obj('Oni_Body_raw', [], C)
    rm = raw.modifiers.new('Remesh', 'REMESH'); rm.mode, rm.voxel_size, rm.use_smooth_shade = 'VOXEL', 0.0075, True
    sm = raw.modifiers.new('Smooth', 'SMOOTH'); sm.factor, sm.iterations = 0.5, 5
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(raw.evaluated_get(dg))
    bpy.data.objects.remove(raw)
    me.name = 'Oni_Body'
    SKIN, BLACK = 0, 1
    for m in (mats['skin'], mats['black']):
        me.materials.append(m)
    for p in me.polygons:
        c = p.center
        p.use_smooth = True
        left_black = c.x > 0.200 and (c.z > 1.485 or c.x > 0.262)
        p.material_index = BLACK if (left_black or c.x < -0.435 or c.z < 1.0) else SKIN
    body = bpy.data.objects.new('Oni_Body', me)
    C.objects.link(body)

    # harness straps hugging the chest (skinned together with the body)
    st = MB()
    def loop(z_of_x, n=110, keep=None):
        pts, nrm = [], []
        for i in range(n):
            th = TAU * i / n
            z = 1.40
            for _ in range(4):
                a, b = interp(TORSO, z)
                z = min(1.635, max(1.0, z_of_x(a * math.cos(th), b * math.sin(th))))
            p, nn = torso_point(th, z, 0.004)
            pts.append(p); nrm.append(nn)
        return pts, nrm
    for fn in (lambda x, y: 1.375 + 0.0 * x, lambda x, y: 1.43 - 1.22 * x):
        p, nn = loop(fn)
        ribbon(st, p, nn, 0.036, 0.007, 0)
    p, nn = loop(lambda x, y: 1.43 + 1.22 * x)
    keep = [i for i in range(len(p)) if p[i].z > 1.39]
    seg = [i for i in keep]
    # upper half of the mirrored strap only (runs over the left shoulder)
    order = sorted(seg, key=lambda i: (math.atan2(p[i].y, p[i].x - 0.05)))
    ribbon(st, [p[i] for i in order], [nn[i] for i in order], 0.036, 0.007, 0, closed=False)
    straps = st.obj('Oni_Straps', [mats['leather']], C)
    body = join_meshes('Oni_Body', [body, straps], C)
    for p_ in body.data.polygons:
        if p_.material_index < 2:
            p_.use_smooth = True
    return body


def skin_oni_body(body, arm):
    """Formula-driven vertex weights (no bone-heat solve needed)."""
    vg = {n: body.vertex_groups.new(name=n) for n in ('hips', 'spine', 'chest', 'neck', 'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R')}
    for v in body.data.vertices:
        x, y, z = v.co
        ax = abs(x)
        side = 'L' if x > 0 else 'R'
        w_arm = sstep(ax, 0.185, 0.275) * (1.0 if ax > 0.275 else sstep(z, 1.42, 1.50))
        w_fore = sstep(ax, 0.52, 0.60)
        w = {}
        w['forearm.' + side] = w_arm * w_fore
        w['upper_arm.' + side] = w_arm * (1 - w_fore)
        rest = 1 - w_arm
        n_ = sstep(z, 1.60, 1.67)
        c_ = sstep(z, 1.27, 1.40) * (1 - n_)
        s_ = sstep(z, 1.06, 1.17) * (1 - sstep(z, 1.27, 1.40))
        h_ = 1 - sstep(z, 1.06, 1.17)
        for k_, val in (('neck', n_), ('chest', c_), ('spine', s_), ('hips', h_)):
            w[k_] = rest * val
        tot = sum(w.values()) or 1.0
        for k_, val in w.items():
            if val > 1e-4:
                vg[k_].add([v.index], val / tot, 'REPLACE')
    md = body.modifiers.new('Armature', 'ARMATURE')
    md.object = arm
    body.parent = arm


def build_oni(C):
    BLK, GOLD, RED, WHT, EYE, LEA = 0, 1, 2, 3, 4, 5
    M = {'skin': skin_mat(),
         'black': flat('MAT_Oni_BlackCloth', (0.012, 0.012, 0.014), 0.8),
         'leather': armor_mat('MAT_Oni_Leather', (0.016, 0.016, 0.018), 0.42, dirt=0.3, coat=0.3),
         'gold': armor_mat('MAT_Oni_Gold', (0.83, 0.60, 0.26), 0.30, metallic=1.0, dirt=0.75),
         'red': armor_mat('MAT_Oni_RedRope', (0.55, 0.018, 0.012), 0.75, dirt=0.7),
         'white': flat('MAT_Oni_Bone', (0.82, 0.80, 0.74), 0.35),
         'eye': flat('MAT_Oni_Eye', (1.0, 0.85, 0.4), 0.3, emit=(1.0, 0.75, 0.35), emit_strength=6.0)}
    mats = [M['black'], M['gold'], M['red'], M['white'], M['eye'], M['leather']]
    rg = Rig('Oni', J_ONI, C)
    X90, Y90 = (R(90), 0, 0), (0, R(90), 0)
    out = {'rig': rg.arm}

    body = build_oni_body(C, M)
    skin_oni_body(body, rg.arm)
    out['body'] = body

    # ---- hips: obi, twisted red rope belt with bow and tassels, hip armour
    h = rg.mb('hips')
    h.cone(0.176, 0.170, 0.13, (0, 0, 1.085), segs=32, mat=BLK, scale=(1, 0.70, 1))
    for i, z in enumerate((1.065, 1.105)):
        torus(h, 0.182, 0.026, (0, 0, z), (0, 0, i * 0.3), 36, 10, RED, scale=(1.0, 0.72, 1.0), lump=0.16, seed=i)
    h.sphere(0.045, (0, -0.158, 1.085), (1.1, 0.8, 1.0), RED)
    for sx in (1, -1):
        tube(h, [(sx * 0.02, -0.160, 1.085), (sx * 0.10, -0.185, 1.125), (sx * 0.155, -0.165, 1.085), (sx * 0.10, -0.150, 1.05), (sx * 0.02, -0.158, 1.08)],
             [0.024, 0.026, 0.026, 0.024, 0.022], 10, RED)
        tube(h, [(sx * 0.03, -0.165, 1.06), (sx * 0.055, -0.185, 0.97), (sx * 0.065, -0.19, 0.88)], 0.017, 10, RED)
        h.cone(0.022, 0.026, 0.045, (sx * 0.066, -0.19, 0.862), segs=14, mat=GOLD)
        tube(h, [(sx * 0.066, -0.19, 0.84), (sx * 0.068, -0.192, 0.80), (sx * 0.070, -0.195, 0.70)], [0.02, 0.034, 0.040], 12, RED)
        for j, (zz, xx) in enumerate(((0.95, 0.262), (0.79, 0.300))):
            tbox(h, (0.03, 0.17, 0.17), (sx * xx, 0.0, zz), (0, sx * R(7), 0), LEA, top=(1, 0.9))
            tbox(h, (0.034, 0.18, 0.022), (sx * xx, 0.0, zz - 0.085), (0, sx * R(7), 0), GOLD)
            for yy in (-0.055, 0.0, 0.055):
                h.sphere(0.011, (sx * (xx + 0.018), yy, zz + 0.03), mat=GOLD, u=10, v=6)
    n = rg.mb('neck')
    n.cone(0.070, 0.064, 0.09, (0, 0.002, 1.695), segs=20, mat=BLK)

    # ---- chest: harness ring
    c = rg.mb('chest')
    p, nn = torso_point(R(270 - 9), 1.385, 0.012)
    torus(c, 0.030, 0.007, p, X90, 22, 8, GOLD)

    # ---- arms: bicep bands, gold swirl, bracers, gloves
    for side, sx in (('L', 1), ('R', -1)):
        z = 1.575
        a = rg.mb('upper_arm.' + side)
        if sx < 0:
            for k_, (bx, col_) in enumerate(((0.415, RED), (0.432, WHT), (0.449, RED))):
                torus(a, 0.069, 0.010, (sx * bx, 0.008, z), Y90, 22, 8, col_)
        else:
            cx = Vector((0.250, 0.002, 1.585))
            pts = []
            for i in range(40):
                t = i / 39
                ang, rad = t * TAU * 2.2, 0.012 + 0.045 * t
                d = Vector((0.55, -math.cos(ang) * rad / 0.094, 0.55 + math.sin(ang) * rad / 0.094)).normalized()
                pts.append(cx + Vector((d.x * 0.104, d.y * 0.098, d.z * 0.094)))
            tube(a, pts, 0.0065, 8, GOLD)
        f = rg.mb('forearm.' + side)
        f.cone(0.056, 0.044, 0.23, (sx * 0.715, 0.004, z), (0, sx * R(90), 0), 18, LEA)
        for bx, rr in ((0.605, 0.058), (0.825, 0.046)):
            torus(f, rr, 0.009, (sx * bx, 0.004, z), Y90, 20, 8, GOLD)
        for i, (bx, ln, up_) in enumerate(((0.66, 0.13, 0.058), (0.74, 0.12, 0.052), (0.79, 0.09, 0.047))):
            tbox(f, (ln, 0.075, 0.016), (sx * bx, 0.004, z + up_), (0, -sx * R(10), 0), GOLD, top=(0.7, 0.55))
            tbox(f, (ln, 0.016, 0.07), (sx * bx, -up_ + 0.004, z), (0, 0, sx * R(10)), GOLD, top=(0.7, 0.6))
        hn = rg.mb('hand.' + side)
        tube(hn, [(sx * 0.835, 0, z), (sx * 0.88, 0, z), (sx * 0.935, 0, z)], [(0.046, 0.022), (0.048, 0.022), (0.044, 0.018)], 14, BLK, up=(0, 1, 0))
        tbox(hn, (0.07, 0.075, 0.012), (sx * 0.885, 0, z + 0.022), mat=GOLD, top=(0.8, 0.8))
        f1, f2, th = rg.mb('fingers1.' + side), rg.mb('fingers2.' + side), rg.mb('thumb.' + side)
        for fy, ln in ((-0.034, 0.92), (-0.011, 1.0), (0.012, 0.97), (0.034, 0.82)):
            x0, x1, x2 = 0.93, 0.93 + 0.05 * ln, 0.93 + 0.10 * ln
            tube(f1, [(sx * x0, fy, z), (sx * x1, fy, z)], 0.0115, 8, BLK)
            f1.sphere(0.0118, (sx * x1, fy, z), mat=BLK, u=8, v=6)
            tube(f2, [(sx * x1, fy, z), (sx * x2, fy, z - 0.002)], [0.011, 0.0095], 8, BLK)
            f2.sphere(0.0095, (sx * x2, fy, z - 0.002), mat=BLK, u=8, v=6)
        tube(th, [(sx * 0.865, -0.03, z - 0.008), (sx * 0.90, -0.062, z - 0.014), (sx * 0.93, -0.085, z - 0.02)], [0.015, 0.013, 0.011], 8, BLK)

    # ---- legs (hidden by the hakama, kept as cloth collision shapes) and feet
    for side, sx in (('L', 1), ('R', -1)):
        x = sx * 0.11
        t = rg.mb('thigh.' + side); tube(t, [(x, 0, 1.04), (x, -0.02, 0.56)], [0.085, 0.060], 12, BLK)
        s = rg.mb('shin.' + side); tube(s, [(x, -0.02, 0.56), (x, 0.01, 0.30), (x, 0.02, 0.10)], [0.058, 0.056, 0.040], 12, BLK)
        ft = rg.mb('foot.' + side)
        tube(ft, [(x, 0.06, 0.05), (x, 0.0, 0.055), (x, -0.07, 0.048), (x, -0.13, 0.040)], [(0.036, 0.036), (0.043, 0.042), (0.046, 0.036), (0.047, 0.028)], 14, BLK, up=(1, 0, 0))
        ft.cube((0.108, 0.20, 0.022), (x, -0.03, 0.011), mat=RED)
        torus(ft, 0.046, 0.008, (x, 0.02, 0.105), (0, 0, 0), 18, 6, RED)
        for q in (-1, 1):
            tube(ft, [(x + q * 0.05, 0.02, 0.022), (x + q * 0.04, -0.03, 0.085), (x + q * 0.006, -0.125, 0.07)], 0.007, 6, RED)
        to = rg.mb('toe.' + side)
        tube(to, [(x, -0.13, 0.040), (x, -0.18, 0.034), (x, -0.215, 0.026)], [(0.047, 0.028), (0.045, 0.024), (0.03, 0.016)], 14, BLK, up=(1, 0, 0))
        to.cube((0.108, 0.10, 0.022), (x, -0.18, 0.011), mat=RED)
        tube(to, [(x + 0.006, -0.125, 0.07), (x + 0.008, -0.17, 0.045)], 0.007, 6, RED)

    # ---- head: black hood under the mask
    hd = rg.mb('head')
    hd.sphere(0.104, (0, 0.012, 1.82), (0.93, 1.06, 1.14), BLK, 24, 14)
    rg.finish(mats, bevel=0.003)

    out['mask'] = rg.attach(build_oni_mask(C, M), 'head')
    out['hair'] = rg.attach(build_oni_hair(C), 'head')
    out['hakama'] = rg.attach(build_hakama(C), 'hips')

    kmats = [pattern_mat('MAT_Oni_Blade', (0.025, 0.025, 0.03), (0.86, 0.80, 0.62), 14.0, 0.55, 0.16, 1.0, 1.0, (1, 1, 0.12)),
             M['gold'], wrap_mat('MAT_Oni_Wrap'), M['leather'],
             pattern_mat('MAT_Oni_Saya', (0.010, 0.010, 0.012), (0.80, 0.62, 0.30), 10.0, 0.60, 0.2, 0.0, 1.0), M['red']]
    ko, so = build_katana('Oni_Katana', C, kmats, tassel=True)
    ko.parent = so
    place_obj(so, (0.205, -0.20, 1.115), (0.10, 0.90, -0.42), (0, 0, 1))
    rg.attach(so, 'hips')
    out['katana'], out['saya'] = ko, so
    return out


MASK_C = Vector((0, 0.012, 1.815))


def mask_point(u, v, off=0.0):
    """u: -1..1 left-right, v: -1..1 chin-forehead. Returns a point on the sculpted oni face."""
    g = lambda q, c, w: math.exp(-((q - c) / w) ** 2)
    phi, psi = u * R(98), v * R(72)
    d = Vector((math.sin(phi) * math.cos(psi), -math.cos(phi) * math.cos(psi), math.sin(psi)))
    au = abs(u)
    h = 0.0
    h += 0.024 * g(v, 0.30 + 0.20 * au, 0.11) * (0.55 + 0.45 * sstep(au, 0.05, 0.5)) * (1 - sstep(au, 0.75, 1.0))   # angry brow
    h -= 0.020 * g(au, 0.36, 0.17) * g(v, 0.14, 0.085)                                                               # eye sockets
    h += 0.040 * g(u, 0, 0.10 + 0.05 * sstep(-v, -0.2, 0.1)) * sstep(-v, -0.34, 0.06) * (1 - sstep(-v, 0.08, 0.17)) # nose
    h += 0.018 * g(au, 0.56, 0.20) * g(v, -0.04, 0.15)                                                               # cheekbones
    h += 0.014 * g(v, -0.20, 0.05) * (1 - sstep(au, 0.45, 0.7))                                                      # upper lip / snarl
    h += 0.022 * g(v, -0.80, 0.14) * (1 - sstep(au, 0.35, 0.8))                                                      # chin
    h += 0.010 * g(v, 0.72, 0.2) * g(u, 0, 0.5)                                                                      # forehead
    mouth = (1 - sstep(au, 0.36, 0.50)) * sstep(v, -0.66, -0.60) * (1 - sstep(v, -0.30, -0.25))
    h -= 0.030 * mouth
    return MASK_C + Vector((d.x * 0.110, d.y * 0.128, d.z * 0.137)) + d * (h + off), d, mouth


def build_oni_mask(C, M):
    mb = MB()
    RED, DARK, WHT, EYE, GOLD = 0, 1, 2, 3, 4
    nu, nv = 72, 72
    grid = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            grid[i, j] = mb.bm.verts.new(mask_point(i / nu * 2 - 1, j / nv * 2 - 1)[0])
    for i in range(nu):
        for j in range(nv):
            f = mb.bm.faces.new((grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
            f.smooth = True
            mouth = mask_point((i + .5) / nu * 2 - 1, (j + .5) / nv * 2 - 1)[2]
            f.material_index = DARK if mouth > 0.6 else RED
    for sx in (1, -1):
        p, d, _ = mask_point(sx * 0.36, 0.145, -0.004)
        mb.sphere(0.017, p, (1.5, 0.5, 0.55), EYE, 14, 8)
        # horns
        b, d, _ = mask_point(sx * 0.40, 0.74, -0.008)
        tube(mb, [b, b + Vector((sx * 0.040, -0.020, 0.10)), b + Vector((sx * 0.095, -0.050, 0.20)), b + Vector((sx * 0.135, -0.095, 0.30)), b + Vector((sx * 0.150, -0.150, 0.385))],
             [0.036, 0.031, 0.023, 0.013, 0.0], 14, 5, tcol=(mb.bm.loops.layers.color.get('tcol') or mb.bm.loops.layers.color.new('tcol'), 1.0))
        torus(mb, 0.030, 0.007, b + Vector((sx * 0.003, -0.002, 0.012)), (R(12), sx * R(15), 0), 16, 6, GOLD)
        # tusks and fangs
        for uu, vv, ln, dirz in ((0.30, -0.30, 0.050, -1), (0.39, -0.60, 0.075, 1)):
            p, d, _ = mask_point(sx * uu, vv, -0.012)
            tube(mb, [p, p + d * 0.012 + Vector((0, 0, dirz * ln * 0.5)), p + d * 0.016 + Vector((0, 0, dirz * ln))], [0.012, 0.009, 0.0], 10, WHT)
        # brow paint strokes
        pts = [mask_point(sx * (0.12 + 0.5 * t), 0.44 + 0.20 * t + 0.03 * math.sin(t * 3.14), 0.004)[0] for t in [q / 9 for q in range(10)]]
        tube(mb, pts, [0.004 + 0.006 * math.sin(3.14 * q / 9) for q in range(10)], 8, WHT)
        pts = [mask_point(sx * (0.30 + 0.34 * t), -0.02 - 0.20 * t, 0.003)[0] for t in [q / 7 for q in range(8)]]
        tube(mb, pts, [0.003 + 0.005 * math.sin(3.14 * q / 7) for q in range(8)], 8, WHT)
    for k in range(7):                                                # teeth
        for vv, hgt in ((-0.31, 0.018), (-0.59, 0.016)):
            p, d, _ = mask_point(-0.24 + 0.08 * k, vv, -0.020)
            mb.cube((0.011, 0.008, hgt), p, mat=WHT)
    pts = []                                                           # forehead swirl
    for i in range(26):
        t = i / 25
        ang, rad = t * TAU * 1.6, 0.03 + 0.13 * t
        pts.append(mask_point(rad * math.cos(ang) * 0.9, 0.70 + rad * math.sin(ang) * 0.8, 0.003)[0])
    tube(mb, pts, 0.0045, 8, WHT)
    mm, nt, bsdf, o_ = lib._new('MAT_Oni_Horn')
    horn = vcol_mat('MAT_Oni_HornGrad', (0.84, 0.82, 0.76), (0.60, 0.02, 0.015), 0.35, 0.70, 0.3)
    bpy.data.materials.remove(mm)
    lacquer = armor_mat('MAT_Oni_MaskRed', (0.50, 0.016, 0.012), 0.24, dirt=0.85, coat=0.6)
    ob = mb.obj('Oni_Mask', [lacquer, flat('MAT_Oni_MouthDark', (0.02, 0.004, 0.004), 0.7), M['white'], M['eye'], M['gold'], horn], C, smooth=True)
    sd = ob.modifiers.new('Solid', 'SOLIDIFY'); sd.thickness, sd.offset = 0.006, -1
    return ob


def build_oni_hair(C):
    rnd = random.Random(12)
    mb = MB()
    layer = mb.bm.loops.layers.color.new('tcol')
    ctr = Vector((0, 0.012, 1.825))
    def strand(root, d, length, r0, droop=1.0, n=7, flat_=0.5):
        pts, p, dd = [], root.copy(), d.normalized()
        for i in range(n):
            pts.append(p.copy())
            dd = (dd + Vector((rnd.uniform(-.18, .18), rnd.uniform(-.1, .22), -0.30 * droop)) * (0.5 + 0.12 * i)).normalized()
            p = p + dd * length / (n - 1)
        rad = [(r0 * (1 - (i / (n - 1)) ** 1.3), r0 * flat_ * (1 - (i / (n - 1)) ** 1.3)) for i in range(n)]
        tube(mb, pts, rad, 7, 0, tcol=(layer, 1.0 if rnd.random() < 0.3 else 0.0))
    for _ in range(120):                                              # mane: back, sides and top
        az, el = rnd.uniform(R(-115), R(115)), rnd.uniform(R(-25), R(80))
        d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        root = ctr + Vector((d.x * 0.098, d.y * 0.112, d.z * 0.122))
        strand(root, d + Vector((0, 0.5, 0.15)), rnd.uniform(0.24, 0.58), rnd.uniform(0.020, 0.034))
    for i in range(18):                                               # fringe framing the mask
        sx = 1 if i % 2 else -1
        az = sx * rnd.uniform(R(105), R(165))
        el = rnd.uniform(R(15), R(70))
        d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        root = ctr + Vector((d.x * 0.104, d.y * 0.118, d.z * 0.128))
        strand(root, d + Vector((sx * 0.5, -0.1, 0.5)), rnd.uniform(0.16, 0.30), rnd.uniform(0.016, 0.026), droop=0.9)
    knot = Vector((0, 0.085, 1.955))
    for _ in range(34):                                               # high ponytail plume
        d = Vector((rnd.uniform(-.45, .45), rnd.uniform(0.25, 1.0), rnd.uniform(0.55, 1.2)))
        strand(knot + Vector((rnd.uniform(-.02, .02), rnd.uniform(-.02, .02), 0)), d, rnd.uniform(0.34, 0.66), rnd.uniform(0.022, 0.034), droop=1.25, n=8)
    torus(mb, 0.036, 0.012, knot + Vector((0, 0.004, 0.012)), (R(-25), 0, 0), 20, 8, 1)
    hair = vcol_mat('MAT_Oni_Hair', (0.80, 0.80, 0.84), (0.55, 0.02, 0.02), 0.45, 0.8, 0.42, only_marked=True)
    gold = bpy.data.materials.get('MAT_Oni_Gold')
    return mb.obj('Oni_Hair', [hair, gold], C, smooth=True)


def build_hakama(C):
    mb = MB()
    LEG = [(1.00, .10, .135, .150), (0.80, .14, .175, .190), (0.55, .175, .200, .215), (0.30, .190, .210, .225), (0.17, .16, .15, .16), (0.11, .115, .072, .080)]
    keys = sorted(LEG)
    for sx in (1, -1):
        rings = []
        for j in range(49):
            z = 1.00 - (1.00 - 0.11) * j / 48
            cx, a, b = interp(keys, z)
            pleat = 0.04 * sstep(z, 0.16, 0.40)
            ring = []
            for i in range(64):
                th = TAU * i / 64
                k = 1 + pleat * math.cos(11 * th + sx)
                ring.append(mb.bm.verts.new((sx * cx + a * k * math.cos(th), b * k * math.sin(th), z)))
            rings.append(ring)
        skin_rings(mb, rings, 0, cap=True, flip=True)
    yoke = []
    for j in range(13):
        s = j / 12
        z = 1.12 - 0.20 * s
        a, b = 0.178 + 0.075 * s, 0.128 + 0.050 * s
        yoke.append([mb.bm.verts.new((a * (1 + 0.025 * s * math.cos(14 * th)) * math.cos(th), b * (1 + 0.025 * s * math.cos(14 * th)) * math.sin(th), z))
                     for th in [TAU * i / 72 for i in range(72)]])
    skin_rings(mb, yoke, 0, cap=False, flip=True)
    return mb.obj('Oni_Hakama', [gradient_hakama()], C, smooth=True)
