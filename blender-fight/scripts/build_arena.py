"""STAGE 1 - build the Japanese temple arena and save arena.blend.

Run:  python3 scripts/build_arena.py
Layout (metres, +Y = north):  open fighting area at the origin, torii gate at the north end
with stairs behind it, main temple on the west side, smaller buildings north and east,
stone lanterns and rubble round the edge, cherry trees at the corners.
Any prop can be replaced by dropping a GLB into assets/glb/<name>.glb (see GLB_PROPS).
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from lib import MB, col, pbr, flat, snow, moss, TRS, ROOT, ASSETS

R = math.radians
rng = random.Random(7)
GLB_PROPS = ['stone_lantern', 'broken_stone_lantern', 'torii_gate', 'paper_lantern', 'temple_building', 'cherry_tree']


# =============================================================== materials
def make_materials():
    M = {}
    M['stone'] = moss(pbr('MAT_Stone', 'rock_boulder_dry', 0.7, sat=0.25, val=0.22, rough_mul=0.8), 0.9, 0.35)
    snow(M['stone'], 0.75, 0.80)
    M['stone_wall'] = pbr('MAT_StoneWall', 'japanese_stone_wall', 0.45, sat=0.3, val=0.22, rough_mul=0.75)
    moss(M['stone_wall'], 0.7, 0.55)
    snow(M['stone_wall'], 0.6, 0.85)
    M['dark_wood'] = pbr('MAT_DarkWood', 'weathered_planks', 0.6, val=0.28, rough_mul=0.8)
    M['roof'] = snow(pbr('MAT_RoofTiles', 'ceramic_roof_01', 1.0, sat=0.05, val=0.16, rough_mul=0.55,
                         normal=1.6, coords='UV'), 0.55, 0.60)
    M['black'] = flat('MAT_BlackLacquer', (0.012, 0.012, 0.014), 0.35)
    M['rope'] = flat('MAT_Rope', (0.25, 0.19, 0.10), 0.9)
    M['glow'] = flat('MAT_LanternGlow', (0.6, 0.05, 0.02), 0.5, emit=(1.0, 0.06, 0.015), emit_strength=5.0)
    M['paper'] = make_paper()
    M['red_wood'] = make_red_wood()
    M['floor'] = make_floor()
    M['earth'] = make_earth()
    M['banner'] = make_banner()
    M['bark'] = pbr('MAT_SakuraBark', 'sakura_bark', 0.8, val=0.35)
    snow(M['bark'], 0.5, 0.75)
    M['blossom'] = flat('MAT_Blossom', (0.80, 0.30, 0.48), 0.6, emit=(0.9, 0.22, 0.45), emit_strength=0.10)
    M['petal'] = flat('MAT_Petal', (0.85, 0.42, 0.58), 0.5, emit=(0.9, 0.35, 0.5), emit_strength=0.06)
    M['snowflake'] = flat('MAT_Snowflake', (0.9, 0.9, 0.95), 0.6, emit=(0.8, 0.85, 1.0), emit_strength=0.6)
    M['pine'] = snow(flat('MAT_Pine', (0.006, 0.012, 0.009), 0.95), 0.22, 0.80)
    return M


def make_red_wood():
    """Weathered red paint chipping away to dark timber."""
    m, nt, bsdf, out = lib._new('MAT_RedWood')
    vec, _ = lib._coords(nt, 0.6)
    d = lib._img(nt, os.path.join(lib.TEX, 'weathered_planks', 'Diffuse.jpg'))
    n = lib._img(nt, os.path.join(lib.TEX, 'weathered_planks', 'nor_gl.jpg'), True)
    nt.links.new(vec, d.inputs['Vector']); nt.links.new(vec, n.inputs['Vector'])
    paint = lib._mixc(nt, 1.0, d.outputs['Color'], (2.6, 0.10, 0.07), 'MULTIPLY')
    wood = lib._mixc(nt, 1.0, d.outputs['Color'], (0.20, 0.17, 0.16), 'MULTIPLY')
    v2, _ = lib._coords(nt, 1.0)
    chip = lib._ramp(nt, lib._noise(nt, 5.0, 9.0, v2, 0.7), 0.50, 0.58)
    nt.links.new(lib._mixc(nt, chip, paint, wood), bsdf.inputs['Base Color'])
    nt.links.new(lib._madd(nt, chip, 0.4, 0.30, True), bsdf.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.2
    nt.links.new(n.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], bsdf.inputs['Normal'])
    return snow(m, 0.7, 0.80)


def make_floor():
    """Wet cracked stone slabs: dark stone, mirror-like puddles, slab joints."""
    m, nt, bsdf, out = lib._new('MAT_WetStoneFloor')
    vec, tc = lib._coords(nt, 0.38)
    d = lib._img(nt, os.path.join(lib.TEX, 'stone_tiles_02', 'Diffuse.jpg'))
    r = lib._img(nt, os.path.join(lib.TEX, 'stone_tiles_02', 'Rough.jpg'), True)
    n = lib._img(nt, os.path.join(lib.TEX, 'stone_tiles_02', 'nor_gl.jpg'), True)
    for i in (d, r, n):
        nt.links.new(vec, i.inputs['Vector'])
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    hs.inputs['Saturation'].default_value, hs.inputs['Value'].default_value = 0.35, 0.13
    nt.links.new(d.outputs['Color'], hs.inputs['Color'])
    # big slab joints
    bv, _ = lib._coords(nt, 1.0)
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = 0.5
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.02
    br.inputs['Brick Width'].default_value = 1.6
    br.inputs['Row Height'].default_value = 1.6
    br.inputs['Color1'].default_value = br.inputs['Color2'].default_value = (1, 1, 1, 1)
    br.inputs['Mortar'].default_value = (0, 0, 0, 1)
    nt.links.new(bv, br.inputs['Vector'])
    base = lib._mixc(nt, 1.0, hs.outputs[0], lib._mixc(nt, br.outputs['Color'], (0.25, 0.25, 0.25), (1, 1, 1)), 'MULTIPLY')
    nt.links.new(base, bsdf.inputs['Base Color'])
    # puddles
    pv, _ = lib._coords(nt, 1.0)
    puddle = lib._ramp(nt, lib._noise(nt, 0.30, 6.0, pv, 0.65), 0.50, 0.62)
    rough = lib._madd(nt, r.outputs['Color'], 0.55, 0.06)
    rough = lib._mixc(nt, puddle, rough, (0.02, 0.02, 0.02))
    nt.links.new(rough, bsdf.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(lib._madd(nt, puddle, -1.9, 2.0), nm.inputs['Strength'])
    nt.links.new(n.outputs['Color'], nm.inputs['Color'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 0.04
    nt.links.new(br.outputs['Color'], bump.inputs['Height'])
    nt.links.new(nm.outputs[0], bump.inputs['Normal'])
    nt.links.new(bump.outputs[0], bsdf.inputs['Normal'])
    bsdf.inputs['Coat Weight'].default_value = 0.25
    bsdf.inputs['Coat Roughness'].default_value = 0.05
    return m


def make_earth():
    m, nt, bsdf, out = lib._new('MAT_Earth')
    vec, _ = lib._coords(nt, 1.0)
    nz = lib._noise(nt, 0.25, 6.0, vec)
    nt.links.new(lib._mixc(nt, lib._ramp(nt, nz, 0.42, 0.6), (0.012, 0.011, 0.012), (0.55, 0.57, 0.63)),
                 bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.7
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.5
    nt.links.new(lib._noise(nt, 3.0, 8.0, vec), b.inputs['Height'])
    nt.links.new(b.outputs[0], bsdf.inputs['Normal'])
    return m


def make_paper():
    """Red paper lantern: glowing ribbed paper shell."""
    m, nt, bsdf, out = lib._new('MAT_PaperLantern')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    rib = lib._math(nt, 'SINE', lib._math(nt, 'MULTIPLY', sep.outputs['Z'], 95.0))
    ribn = lib._madd(nt, rib, 0.5, 0.5)
    col_ = lib._mixc(nt, ribn, (0.30, 0.012, 0.008), (0.75, 0.04, 0.02))
    nt.links.new(col_, bsdf.inputs['Base Color'])
    nt.links.new(col_, bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.3
    bsdf.inputs['Roughness'].default_value = 0.6
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.4
    nt.links.new(rib, b.inputs['Height']); nt.links.new(b.outputs[0], bsdf.inputs['Normal'])
    return m


def make_banner():
    """Dark red cloth with a pale five-petal crest in a ring, ragged lower edge (UV mapped)."""
    m, nt, bsdf, out = lib._new('MAT_BannerCloth')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['UV'], sep.inputs[0])
    u, v = sep.outputs['X'], sep.outputs['Y']
    du = lib._math(nt, 'SUBTRACT', u, 0.5)
    dv = lib._math(nt, 'MULTIPLY', lib._math(nt, 'SUBTRACT', v, 0.62), 2.8)
    dist = lib._math(nt, 'SQRT', lib._math(nt, 'ADD', lib._math(nt, 'MULTIPLY', du, du), lib._math(nt, 'MULTIPLY', dv, dv)))
    ang = lib._math(nt, 'ARCTAN2', dv, du)
    lobes = lib._madd(nt, lib._math(nt, 'COSINE', lib._math(nt, 'MULTIPLY', ang, 5.0)), 0.07, 0.17)
    flower = lib._math(nt, 'LESS_THAN', dist, lobes)
    ring = lib._math(nt, 'MULTIPLY', lib._math(nt, 'GREATER_THAN', dist, 0.31), lib._math(nt, 'LESS_THAN', dist, 0.36))
    crest = lib._math(nt, 'MAXIMUM', flower, ring)
    nz = lib._noise(nt, 6.0, 6.0)
    cloth = lib._mixc(nt, nz, (0.10, 0.006, 0.006), (0.30, 0.02, 0.015))
    nt.links.new(lib._mixc(nt, crest, cloth, (0.55, 0.45, 0.33)), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Sheen Weight'].default_value = 0.12
    tat = nt.nodes.new('ShaderNodeTexNoise'); tat.inputs['Scale'].default_value = 14.0
    tv = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(u, tv.inputs[0])
    nt.links.new(tv.outputs[0], tat.inputs['Vector'])
    edge = lib._math(nt, 'MULTIPLY', tat.outputs[0], 0.22)
    nt.links.new(lib._math(nt, 'GREATER_THAN', v, edge), bsdf.inputs['Alpha'])
    return m


# =============================================================== props
def new_asset(name):
    """Unlinked source collection, instanced into the scene with place()."""
    c = bpy.data.collections.get('SRC_' + name) or bpy.data.collections.new('SRC_' + name)
    return c


def place(src, name, loc, rot_z=0.0, scale=1.0, into=None, tilt=(0, 0)):
    e = bpy.data.objects.new(name, None)
    e.instance_type, e.instance_collection = 'COLLECTION', src
    e.empty_display_size = 0.3
    e.location = loc
    e.rotation_euler = (tilt[0], tilt[1], rot_z)
    e.scale = (scale,) * 3
    (into or bpy.context.scene.collection).objects.link(e)
    return e


def try_glb(name, height):
    """Use assets/glb/<name>.glb instead of the procedural prop when the file exists."""
    path = os.path.join(ASSETS, 'glb', name + '.glb')
    if not os.path.exists(path):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    objs = [o for o in bpy.data.objects if o not in before]
    c = new_asset(name)
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    s = height / max(hi.z - lo.z, 1e-6)
    root = bpy.data.objects.new(name + '_root', None)
    c.objects.link(root)
    for o in objs:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.scale = (s,) * 3
    root.location = (-(lo.x + hi.x) / 2 * s, -(lo.y + hi.y) / 2 * s, -lo.z * s)
    print('GLB prop used:', name)
    return c


def point_light(c, name, loc, color, power, radius=0.12):
    L = bpy.data.lights.new(name, 'POINT')
    L.color, L.energy, L.shadow_soft_size = color, power, radius
    o = bpy.data.objects.new(name, L)
    o.location = loc
    c.objects.link(o)
    return o


def build_stone_lantern(M, broken=False):
    name = 'broken_stone_lantern' if broken else 'stone_lantern'
    g = try_glb(name, 1.9 if broken else 2.35)
    c = g or new_asset(name)
    if not g:
        b = MB()
        b.cone(0.60, 0.56, 0.22, (0, 0, 0.11), segs=6)
        b.cone(0.46, 0.40, 0.20, (0, 0, 0.32), segs=6)
        b.cone(0.22, 0.17, 0.42, (0, 0, 0.63), segs=10)
        b.cone(0.25, 0.25, 0.08, (0, 0, 0.86), segs=10)
        b.cone(0.17, 0.15, 0.40, (0, 0, 1.08), segs=10)
        b.cone(0.20, 0.44, 0.14, (0, 0, 1.33), segs=6)
        b.cone(0.45, 0.45, 0.10, (0, 0, 1.45), segs=6)
        # fire box: six posts, top ring, lattice bars
        for i in range(6):
            a = R(60 * i)
            b.cube((0.06, 0.06, 0.38), (0.27 * math.cos(a), 0.27 * math.sin(a), 1.69), (0, 0, a))
            am = R(60 * i + 30)
            mx, my = 0.235 * math.cos(am), 0.235 * math.sin(am)
            b.cube((0.03, 0.27, 0.03), (mx, my, 1.69), (0, 0, am))
            b.cube((0.03, 0.03, 0.36), (mx, my, 1.69), (0, 0, am))
        b.cone(0.31, 0.31, 0.05, (0, 0, 1.90), segs=6)
        tilt = (R(14), R(-9), R(20)) if broken else (0, 0, 0)
        off = (0.10, -0.05, -0.02) if broken else (0, 0, 0)
        b.cone(0.70, 0.66, 0.06, (off[0], off[1], 1.96 + off[2]), tilt, segs=6)
        b.cone(0.66, 0.13, 0.30, (off[0], off[1], 2.14 + off[2]), tilt, segs=6)
        if not broken:
            b.cone(0.09, 0.07, 0.08, (0, 0, 2.32), segs=10)
            b.sphere(0.11, (0, 0, 2.44), (1, 1, 1.25))
        else:
            for i in range(9):
                a, d = rng.uniform(0, 6.28), rng.uniform(0.55, 1.1)
                s = rng.uniform(0.10, 0.28)
                b.cube((s, s * rng.uniform(0.6, 1.2), s * rng.uniform(0.5, 0.9)), (d * math.cos(a), d * math.sin(a), s * 0.3),
                       (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0, 3)))
        b.obj('MESH_' + name, [M['stone']], c, bevel=0.012, rough=0.022, rough_scale=0.22)
        g2 = MB()
        g2.cone(0.215, 0.215, 0.36, (0, 0, 1.69), segs=6)
        o = g2.obj('MESH_' + name + '_glow', [M['glow']], c)
        o.visible_shadow = False
    point_light(c, 'LGT_' + name, (0, 0, 1.69), (1.0, 0.16, 0.05), 420 if not broken else 300)
    return c


def build_paper_lantern(M):
    g = try_glb('paper_lantern', 0.95)
    c = g or new_asset('paper_lantern')
    if not g:
        b = MB()
        b.sphere(0.24, (0, 0, -0.42), (1, 1, 1.45), u=24, v=14)
        o = b.obj('MESH_paper_lantern_shell', [M['paper']], c, smooth=True)
        o.visible_shadow = False
        k = MB()
        k.cone(0.13, 0.15, 0.06, (0, 0, -0.08), segs=20)
        k.cone(0.15, 0.13, 0.06, (0, 0, -0.76), segs=20)
        k.cone(0.008, 0.008, 0.30, (0, 0, 0.10), segs=6)
        k.cone(0.035, 0.012, 0.30, (0, 0, -0.95), segs=8)
        k.obj('MESH_paper_lantern_caps', [M['black']], c, smooth=True)
    point_light(c, 'LGT_paper_lantern', (0, 0, -0.42), (1.0, 0.13, 0.05), 90, 0.10)
    return c


def beam(b, length, depth, height, z, lift, mat=0, n=22, power=2.0):
    """Box beam along X whose ends sweep upward (torii lintels)."""
    half = length / 2
    rings = []
    for i in range(n + 1):
        x = -half + length * i / n
        zz = z + lift * (abs(x) / half) ** power
        rings.append([b.bm.verts.new((x, sy * depth / 2, zz + sz * height / 2)) for sy, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    faces = []
    for i in range(n):
        a, c = rings[i], rings[i + 1]
        for k in range(4):
            faces.append(b.bm.faces.new((a[k], c[k], c[(k + 1) % 4], a[(k + 1) % 4])))
    faces.append(b.bm.faces.new(rings[0]))
    faces.append(b.bm.faces.new(list(reversed(rings[-1]))))
    for f in faces:
        f.material_index = mat
    bmesh.ops.recalc_face_normals(b.bm, faces=faces)


def banner_cloth(M, c, name, w, h, loc, rot_z=0.0, parent=None):
    bm = bmesh.new()
    bm.loops.layers.uv.verify()
    bmesh.ops.create_grid(bm, x_segments=6, y_segments=18, size=0.5, calc_uvs=True,
                          matrix=TRS((0, 0, -h / 2), (R(90), 0, 0), (w, h, 1)))
    for v in bm.verts:
        v.co.y += 0.04 * math.sin(v.co.z * 4.0 + v.co.x * 3.0) * min(1.0, -v.co.z / h * 2)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(M['banner'])
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = bpy.data.objects.new(name, me)
    o.location, o.rotation_euler = loc, (0, 0, rot_z)
    c.objects.link(o)
    if parent:
        o.parent = parent
    return o


def build_torii(M, C):
    g = try_glb('torii_gate', 9.6)
    if g:
        return place(g, 'Torii', (0, 11.5, 0), into=C)
    b = MB()
    half = 3.2
    for sx in (-1, 1):
        b.cone(0.40, 0.33, 6.4, (sx * (half + 0.07), 0, 3.2), (0, R(-2.0 * sx), 0), segs=24, mat=0)
        b.cone(0.62, 0.55, 0.55, (sx * (half + 0.18), 0, 0.28), segs=24, mat=1)
        b.cube((1.5, 1.5, 0.22), (sx * (half + 0.18), 0, 0.11), mat=2)
        b.cube((0.34, 0.9, 0.16), (sx * (half - 0.02), 0, 5.22), mat=0)          # wedges
    b.cube((8.9, 0.26, 0.50), (0, 0, 4.90), mat=0)                                  # nuki
    b.cube((0.30, 0.24, 1.05), (0, 0, 5.68), mat=0)                                 # gakuzuka
    beam(b, 9.3, 0.42, 0.44, 6.42, 0.30)
    beam(b, 10.4, 0.62, 0.42, 6.85, 0.55)
    beam(b, 10.8, 0.86, 0.14, 7.13, 0.62, mat=1)
    o = b.obj('Torii', [M['red_wood'], M['black'], M['stone']], C, bevel=0.02, smooth=True)
    o.location, o.scale = (0, 11.5, 0), (1.3, 1.3, 1.3)
    # shimenawa rope with tassels
    cu = bpy.data.curves.new('ToriiRope', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = '3D', 0.055, 3
    sp = cu.splines.new('POLY'); n = 28
    sp.points.add(n)
    for i in range(n + 1):
        t = i / n * 2 - 1
        sp.points[i].co = (t * (half - 0.25), -0.38, 4.35 - 0.75 * (1 - t * t), 1)
    ro = bpy.data.objects.new('ToriiRope', cu)
    ro.data.materials.append(M['rope']); ro.parent = o
    C.objects.link(ro)
    t = MB()
    for tx in (-1.6, 0.0, 1.6):
        z = 4.35 - 0.75 * (1 - (tx / (half - 0.25)) ** 2)
        t.cone(0.03, 0.10, 0.5, (tx, -0.38, z - 0.32), segs=10)
    to = t.obj('ToriiTassels', [M['rope']], C)
    to.parent = o
    for i, tx in enumerate((-2.2, -0.9, 0.9, 2.2)):
        banner_cloth(M, C, f'ToriiBanner_{i}', 0.55, 1.5 + 0.2 * (i % 2), (tx, 0.0, 4.64), parent=o)
    return o


def roof_mesh(name, Lx, Ly, H, r=0.5, lift=1.0, p=1.4, nu=56, nv=36):
    """Curved hip roof: steep near the ridge, flaring at the eaves, corners turned up."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    grid = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            u, v = i / nu * 2 - 1, j / nv * 2 - 1
            tu = max(0.0, (abs(u) - r) / (1 - r))
            t = max(tu, abs(v))
            z = H * (1 - t) ** p + lift * t ** 3 * (abs(u) * abs(v)) ** 2 + 0.25 * lift * t ** 6
            grid[i, j] = (bm.verts.new((u * Lx / 2, v * Ly / 2, z)), tu >= abs(v), t)
    slope = math.hypot(Ly / 2, H)
    for i in range(nu):
        for j in range(nv):
            q = [grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]]
            f = bm.faces.new([a[0] for a in q])
            side = sum(a[1] for a in q) >= 2
            for lp, a in zip(f.loops, q):
                co = a[0].co
                lp[uvl].uv = ((co.y if side else co.x) / 2.1, (1 - a[2]) * slope / 2.1)
            f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.normal_update(); bm.to_mesh(me); bm.free()
    return me


def build_temple(M, C, name, L, D, plinth, wall_h, roof_h, bays, loc, rot_z, lantern_src, stairs_w=5.0, detail=True):
    """Hall on a stone plinth. Local frame: facade faces -Y, length along X."""
    b = MB()
    ST, SW, RW, DW, BK = 0, 1, 2, 3, 4
    b.cube((L, D, plinth), (0, 0, plinth / 2), mat=SW)
    b.cube((L + 0.2, D + 0.2, 0.14), (0, 0, plinth - 0.07), mat=ST)
    b.cube((L - 0.3, D - 0.3, 0.10), (0, 0, plinth + 0.05), mat=DW)
    # stairs with stepped cheek walls
    n = max(3, round(plinth / 0.2)); rise, run = plinth / n, 0.36
    for k in range(1, n + 1):
        b.cube((stairs_w, run, rise * k), (0, -D / 2 - (n - k + 0.5) * run, rise * k / 2), mat=ST)
    for sx in (-1, 1):
        for j in range(3):
            ln = n * run / 3
            b.cube((0.55, ln + 0.02, plinth * (j + 1) / 3 + 0.3),
                   (sx * (stairs_w / 2 + 0.275), -D / 2 - n * run + ln * (j + 0.5), (plinth * (j + 1) / 3 + 0.3) / 2), mat=SW)
    z0 = plinth + 0.10
    wl, wd = L - 2.6, D - 2.6
    b.cube((wl, wd, wall_h), (0, 0, z0 + wall_h / 2), mat=DW)
    yf = -wd / 2
    xs = [-wl / 2 + wl * i / bays for i in range(bays + 1)]
    for x in xs:
        for y in (yf, wd / 2):
            b.cube((0.34, 0.34, wall_h), (x, y, z0 + wall_h / 2), mat=RW)
    for z, h in ((z0 + wall_h - 0.2, 0.36), (z0 + 1.05, 0.2), (z0 + 0.12, 0.24)):
        b.cube((wl + 0.4, 0.26, h), (0, yf - 0.05, z), mat=RW)
    for sx in (-1, 1):
        b.cube((0.26, wd + 0.4, 0.36), (sx * wl / 2, 0, z0 + wall_h - 0.2), mat=RW)
    if detail:
        for i in range(bays):
            xa, xb = xs[i] + 0.2, xs[i + 1] - 0.2
            cx, w = (xa + xb) / 2, xb - xa
            mid = i == bays // 2 and bays % 2 == 1
            if mid:                                                # doors
                for sx in (-1, 1):
                    b.cube((w / 2 - 0.04, 0.10, wall_h - 0.75), (cx + sx * w / 4, yf - 0.10, z0 + (wall_h - 0.75) / 2 + 0.24), mat=RW)
                    for zz in (0.9, 1.7, 2.5):
                        b.cube((w / 2 - 0.3, 0.14, 0.07), (cx + sx * w / 4, yf - 0.11, z0 + zz), mat=BK)
                continue
            b.cube((w, 0.10, 0.80), (cx, yf - 0.10, z0 + 0.62), mat=RW)       # lower panel
            nb = max(5, int(w / 0.22))
            for k in range(nb + 1):                                           # lattice window
                b.cube((0.05, 0.07, wall_h - 1.6), (xa + w * k / nb, yf - 0.14, z0 + 1.15 + (wall_h - 1.6) / 2), mat=RW)
            for zz in (1.75, 2.35, 2.95):
                if zz < wall_h - 0.5:
                    b.cube((w, 0.07, 0.05), (cx, yf - 0.15, z0 + zz), mat=RW)
        # veranda railing
        ry = -D / 2 + 0.25
        for sx in (-1, 1):
            xa, xb = sx * (stairs_w / 2 + 0.6), sx * (L / 2 - 0.25)
            for zz in (0.45, 0.85):
                b.cube((abs(xb - xa), 0.08, 0.09), ((xa + xb) / 2, ry, z0 + zz), mat=RW)
            npost = int(abs(xb - xa) / 1.5) + 1
            for k in range(npost + 1):
                b.cube((0.13, 0.13, 1.0), (xa + (xb - xa) * k / npost, ry, z0 + 0.5), mat=RW)
    # bracket band under the eaves
    zt = z0 + wall_h
    b.cube((wl + 1.2, wd + 1.2, 0.28), (0, 0, zt + 0.14), mat=DW)
    b.cube((wl + 2.2, wd + 2.2, 0.22), (0, 0, zt + 0.42), mat=RW)
    if detail:
        nbk = int((wl + 2.0) / 0.8)
        for k in range(nbk + 1):
            b.cube((0.24, 0.5, 0.24), (-(wl + 2.0) / 2 + (wl + 2.0) * k / nbk, yf - 0.85, zt + 0.2), mat=RW)
    o = b.obj(name, [M['stone'], M['stone_wall'], M['red_wood'], M['dark_wood'], M['black']], C, bevel=0.015)
    o.location, o.rotation_euler = loc, (0, 0, rot_z)
    over = 2.3
    rme = roof_mesh(name + '_Roof', L - 2.6 + 2 * over, D - 2.6 + 2 * over, roof_h, r=0.55, lift=1.0)
    rme.materials.append(M['roof'])
    ro = bpy.data.objects.new(name + '_Roof', rme)
    ro.parent, ro.location = o, (0, 0, zt + 0.5)
    s = ro.modifiers.new('Solid', 'SOLIDIFY'); s.thickness, s.offset = 0.22, -1
    C.objects.link(ro)
    rb = MB()
    rl = (L - 2.6 + 2 * over) * 0.55
    rb.cube((rl + 0.6, 0.34, 0.5), (0, 0, zt + 0.5 + roof_h + 0.1))
    for sx in (-1, 1):
        rb.cube((0.3, 0.5, 0.95), (sx * (rl / 2 + 0.3), 0, zt + 0.5 + roof_h + 0.28), (0, R(-12 * sx), 0))
    rid = rb.obj(name + '_Ridge', [M['black']], C, bevel=0.03)
    rid.parent = o
    if detail and lantern_src:
        for i, x in enumerate(xs):
            e = place(lantern_src, f'{name}_Lantern_{i}', (x, yf - 1.35, zt - 0.15), into=C)
            e.parent = o
        for i, x in enumerate((xs[0], xs[-1])):
            bn = banner_cloth(M, C, f'{name}_Banner_{i}', 0.6, 2.4, (x, yf - 0.24, zt - 0.5))
            bn.parent = o
    return o


def stairs_block(M, C, name, w, total_h, loc, run=0.36):
    b = MB()
    n = round(total_h / 0.2); rise = total_h / n
    for k in range(1, n + 1):
        b.cube((w, run, rise * k), (0, -(n - k + 0.5) * run, rise * k / 2), mat=0)
    for sx in (-1, 1):
        for j in range(3):
            ln = n * run / 3; h = total_h * (j + 1) / 3 + 0.45
            b.cube((0.8, ln + 0.02, h), (sx * (w / 2 + 0.4), -n * run + ln * (j + 0.5), h / 2), mat=1)
    o = b.obj(name, [M['stone'], M['stone_wall']], C, bevel=0.02)
    o.location = loc
    return o


def build_cherry(M, seed, name):
    """Leaning cherry tree: bezier branch curves + a cloud of blossom discs."""
    g = try_glb('cherry_tree', 7.0) if seed == 1 else None
    if g:
        return g
    r = random.Random(seed)
    c = new_asset(name)
    cu = bpy.data.curves.new(name + '_Branches', 'CURVE')
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = '3D', 1.0, 2, True
    tips = []

    def branch(p, d, length, rad, depth):
        n = 5
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(n - 1)
        pts = []
        for i in range(n):
            bp = sp.bezier_points[i]
            bp.co = p; bp.radius = rad * (1 - 0.55 * i / (n - 1))
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
            pts.append(p.copy())
            d = (d + Vector((r.uniform(-.35, .35), r.uniform(-.35, .35), r.uniform(-.18, .30))) * (0.6 + 0.2 * depth)).normalized()
            p = p + d * length / (n - 1)
        if depth >= 2:
            tips.extend(pts[1:])
        if depth < 4:
            for k in range(r.randint(2, 3) + (1 if depth == 0 else 0)):
                i = r.randint(1 + (depth == 0), n - 1)
                nd = (d + Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.25, 0.7)))).normalized()
                branch(pts[i].copy(), nd, length * r.uniform(0.55, 0.78), sp.bezier_points[i].radius * 0.68, depth + 1)

    branch(Vector((0, 0, -0.2)), Vector((0.35, 0.1, 1)).normalized(), 4.2, 0.26, 0)
    bo = bpy.data.objects.new(name + '_Branches', cu)
    cu.materials.append(M['bark'])
    c.objects.link(bo)
    bm = bmesh.new()
    for tp in tips:
        for _ in range(46):
            ctr = tp + Vector((r.gauss(0, .24), r.gauss(0, .24), r.gauss(0, .17)))
            rot = Euler((r.uniform(0, 6.28), r.uniform(0, 6.28), r.uniform(0, 6.28))).to_matrix().to_4x4()
            bmesh.ops.create_circle(bm, cap_ends=True, segments=5, radius=r.uniform(0.04, 0.065),
                                    matrix=Matrix.Translation(ctr) @ rot)
    me = bpy.data.meshes.new(name + '_Blossom')
    bm.to_mesh(me); bm.free()
    me.materials.append(M['blossom'])
    c.objects.link(bpy.data.objects.new(name + '_Blossom', me))
    return c


def build_pine(M, seed):
    r = random.Random(seed)
    c = new_asset(f'pine_{seed}')
    b = MB()
    h = 15.0
    b.cone(0.35, 0.08, h, (0, 0, h / 2), segs=8, mat=1)
    tiers = 20
    for i in range(tiers):
        t = i / (tiers - 1)
        z = 2.6 + (h - 2.4) * t ** 0.9
        rad = (3.9 * (1 - t) ** 0.85 + 0.35) * r.uniform(0.75, 1.15)
        vs = b.cone(rad, rad * 0.08, 1.9, (r.uniform(-.3, .3), r.uniform(-.3, .3), z),
                    (r.uniform(-.12, .12), r.uniform(-.12, .12), r.uniform(0, 3)), segs=9)
        for v in vs:
            k = r.uniform(0.7, 1.25)
            v.co.x *= k; v.co.y *= k; v.co.z += r.uniform(-.5, .15)
    b.obj(f'MESH_pine_{seed}', [M['pine'], M['bark']], c)
    return c


def load_rocks():
    """Poly Haven rock scans, normalised to ~1 m and kept as linkable source meshes."""
    out = []
    for nm in ('rock_moss_set_01', 'boulder_01'):
        path = os.path.join(ASSETS, 'models', nm, nm + '.gltf')
        if not os.path.exists(path):
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        for o in [o for o in bpy.data.objects if o not in before]:
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            if o.type == 'MESH':
                out.append((o.data, max(o.dimensions) or 1.0))
            bpy.data.objects.remove(o)
    for me, _ in out:
        for m in me.materials:
            if m and not m.get('covered'):
                snow(m, 0.7, 0.72); m['covered'] = True
    return out


# =============================================================== scene assembly
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = 'Arena'
    M = make_materials()
    C = {n: col('COL_' + n) for n in ('Ground', 'Torii', 'Temples', 'Lanterns', 'Props', 'Trees', 'Atmos', 'Lights', 'Cameras', 'FX')}

    # ---- ground: wet courtyard + terraces + surrounding earth
    g = MB()
    g.cube((19.5, 31.0, 0.3), (0, -1.0, -0.15), mat=0)
    g.obj('Ground_Courtyard', [M['floor']], C['Ground'])
    e = MB()
    e.cube((240, 240, 0.2), (0, 0, -0.16), mat=0)
    e.cube((70, 46, 2.0), (0, 41.0, 1.0), mat=1)                       # north terrace
    e.cube((70, 0.5, 0.25), (0, 18.2, 2.1), mat=1)
    eo = e.obj('Ground_Terrain', [M['earth'], M['stone_wall']], C['Ground'], bevel=0.03)
    stairs_block(M, C['Ground'], 'Stairs_North', 7.5, 2.0, (0, 18.0, 0))

    # ---- broken perimeter walls
    w = MB()
    for sx, y0, y1 in ((-1, -16.5, -8.5), (1, -16.5, -1.0), (-1, 11.5, 14.5), (1, 13.5, 14.5)):
        y = y0
        while y < y1:
            ln = rng.uniform(0.9, 1.6)
            if rng.random() > 0.22:
                h = rng.uniform(0.45, 1.25)
                w.cube((0.7, ln - 0.03, h), (sx * 10.1 + rng.uniform(-.05, .05), y + ln / 2, h / 2), (0, 0, rng.uniform(-.04, .04)))
            y += ln
    for x0, x1 in ((-10.1, -3.0), (3.0, 10.1)):
        x = x0
        while x < x1:
            ln = rng.uniform(0.9, 1.6)
            if rng.random() > 0.2:
                h = rng.uniform(0.5, 1.3)
                w.cube((ln - 0.03, 0.7, h), (x + ln / 2, -16.8, h / 2))
            x += ln
    w.obj('Perimeter_Walls', [M['stone_wall']], C['Ground'], bevel=0.03)

    # ---- hero props
    paper = build_paper_lantern(M)
    build_torii(M, C['Torii'])
    tg = try_glb('temple_building', 9.5)
    if tg:
        place(tg, 'Temple_Main', (-17.0, 2.0, 0), R(90), into=C['Temples'])
    else:
        build_temple(M, C['Temples'], 'Temple_Main', 18.0, 10.0, 1.5, 3.7, 4.2, 5, (-17.0, 2.0, 0), R(90), paper)
    build_temple(M, C['Temples'], 'Temple_North', 14.0, 8.5, 1.1, 3.2, 3.6, 5, (4.0, 33.0, 2.0), 0.0, paper, stairs_w=4.0)
    build_temple(M, C['Temples'], 'Temple_East', 12.0, 7.5, 1.0, 3.0, 3.4, 3, (17.5, 7.0, 0), R(-90), paper, stairs_w=3.5)
    build_temple(M, C['Temples'], 'Temple_NorthWest', 10.0, 7.0, 1.0, 3.0, 3.2, 3, (-17.0, 31.0, 2.0), R(20), paper, stairs_w=3.0)

    lan, brk = build_stone_lantern(M), build_stone_lantern(M, broken=True)
    for i, (x, y, rz, src) in enumerate(((-4.6, -7.4, 0.3, lan), (6.4, -3.6, 1.1, lan), (-7.6, 8.6, 0.7, lan),
                                         (7.6, 9.6, 0.2, lan), (8.3, 3.2, 2.0, brk), (-8.2, -12.5, 0.5, brk),
                                         (-5.5, 19.5, 0.0, lan), (5.5, 19.5, 0.4, lan))):
        place(src, f'StoneLantern_{i}', (x, y, 2.0 if y > 18 else 0), rz, into=C['Lanterns'])

    # ---- banners on poles
    for i, (x, y, rz) in enumerate(((-5.0, 13.6, 0.1), (5.0, 13.6, -0.1), (-9.3, -5.5, 1.4), (9.3, 4.5, -1.5),
                                    (-3.9, 13.9, 0.0), (3.9, 13.9, 0.0))):
        p = MB()
        p.cone(0.045, 0.035, 5.2, (0, 0, 2.6), segs=8)
        p.cube((0.95, 0.05, 0.05), (0, 0, 4.9))
        po = p.obj(f'BannerPole_{i}', [M['dark_wood']], C['Props'])
        po.location, po.rotation_euler = (x, y, 0), (rng.uniform(-.04, .04), rng.uniform(-.04, .04), rz)
        bn = banner_cloth(M, C['Props'], f'Banner_{i}', 0.8, 3.0, (0, -0.04, 4.87))
        bn.parent = po

    # ---- rocks + rubble, clustered along the edges
    rocks = load_rocks()
    spots = [(-8.6, -12.5), (-7.2, -9.0), (8.4, -11.0), (8.9, -4.0), (8.6, 2.2), (-8.8, -3.4), (8.2, 12.6), (-8.4, 12.2),
             (-3.6, -15.5), (4.5, -15.8), (-9.0, 6.0), (9.0, 8.0), (-11.5, -14.0), (11.5, -13.0)]
    k = 0
    for sx, sy in spots:
        for _ in range(rng.randint(3, 6)):
            if not rocks:
                break
            me, dim = rng.choice(rocks)
            o = bpy.data.objects.new(f'Rock_{k}', me); k += 1
            s = rng.choice((0.25, 0.4, 0.6, 0.9, 1.5)) / dim
            o.scale = (s * rng.uniform(.8, 1.2), s * rng.uniform(.8, 1.2), s * rng.uniform(.6, 1.0))
            o.location = (sx + rng.gauss(0, 1.0), sy + rng.gauss(0, 1.0), -0.03)
            o.rotation_euler = (rng.uniform(-.2, .2), rng.uniform(-.2, .2), rng.uniform(0, 6.28))
            C['Props'].objects.link(o)
    rb = MB()
    for sx, sy in spots:
        for _ in range(rng.randint(2, 5)):
            s = rng.uniform(0.18, 0.6)
            rb.cube((s, s * rng.uniform(.5, 1.3), s * rng.uniform(.4, .8)), (sx + rng.gauss(0, 1.3), sy + rng.gauss(0, 1.3), s * 0.22),
                    (rng.uniform(-.5, .5), rng.uniform(-.5, .5), rng.uniform(0, 3)))
    rb.obj('Rubble_Blocks', [M['stone']], C['Props'], bevel=0.02, rough=0.04, rough_scale=0.25)

    # ---- trees
    ch = [build_cherry(M, 1, 'cherry_tree'), build_cherry(M, 2, 'cherry_tree_b')]
    for i, (x, y, rz, s, src) in enumerate(((-8.7, -5.2, 0.3, 1.25, 0), (9.0, -0.5, 2.9, 1.25, 1), (12.0, 15.0, 3.6, 1.1, 0),
                                            (-11.5, 14.5, 5.3, 1.1, 1), (-12.5, -9.0, 1.2, 0.95, 1), (13.5, -4.0, 2.2, 1.0, 0),
                                            (-2.0, -21.0, 1.5, 1.3, 0), (9.0, 24.0, 4.0, 1.1, 1))):
        place(ch[src], f'CherryTree_{i}', (x, y, 2.0 if y > 18 else 0), rz, s, into=C['Trees'])
    pines = [build_pine(M, s) for s in (11, 12, 13)]
    i = 0
    for ring, cnt in ((36, 24), (46, 30), (58, 36)):
        for kk in range(cnt):
            a = kk / cnt * 6.283 + rng.uniform(-.1, .1)
            x, y = ring * math.cos(a) * rng.uniform(.9, 1.15), 8 + ring * math.sin(a) * rng.uniform(.9, 1.15)
            if abs(x) < 24 and -24 < y < 44:
                continue
            place(rng.choice(pines), f'Pine_{i}', (x, y, 2.0 if y > 18 else 0), rng.uniform(0, 6.28), rng.uniform(0.8, 1.5), into=C['Trees'])
            i += 1

    build_atmosphere(M, C)
    build_lights(C)
    build_fx(M, C)
    build_cameras(C)
    setup_render(sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'arena.blend'))
    print('saved arena.blend, objects:', len(bpy.data.objects))


def build_atmosphere(M, C):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('WORLD_Night'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(ASSETS, 'hdri', 'kloppenheim_02_puresky_2k.hdr'), check_existing=True)
    tint = lib._mixc(nt, 1.0, env.outputs[0], (0.45, 0.42, 1.0), 'MULTIPLY')
    nt.links.new(tint, bg.inputs[0]); bg.inputs[1].default_value = 0.14

    # blood moon: emissive disc with dark maria, far behind the torii
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=1.0, calc_uvs=True)
    me = bpy.data.meshes.new('Moon'); bm.to_mesh(me); bm.free()
    m, mnt, bsdf, out = lib._new('MAT_BloodMoon')
    vec, _ = lib._coords(mnt, 1.0)
    n1 = lib._noise(mnt, 1.6, 8.0, vec, 0.6); n2 = lib._noise(mnt, 6.0, 6.0, vec, 0.7)
    mix = lib._math(mnt, 'ADD', lib._math(mnt, 'MULTIPLY', n1, 0.75), lib._math(mnt, 'MULTIPLY', n2, 0.25))
    colr = lib._ramp(mnt, mix, 0.36, 0.62, (0.10, 0.002, 0.002, 1), (1.0, 0.045, 0.02, 1))
    em = mnt.nodes.new('ShaderNodeEmission'); em.inputs[1].default_value = 3.2
    mnt.links.new(colr, em.inputs[0]); mnt.links.new(em.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    moon = bpy.data.objects.new('Moon', me)
    moon.location, moon.scale = (52.0, 420.0, 236.0), (47, 47, 47)
    moon.rotation_euler = (R(119), 0, R(-7))
    moon.visible_shadow = False
    C['Atmos'].objects.link(moon)

    # cloud bank drifting across the lower moon
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5, calc_uvs=True)
    cme = bpy.data.meshes.new('Clouds'); bm.to_mesh(cme); bm.free()
    cm, cnt, cb, cout = lib._new('MAT_Clouds')
    cvec, _ = lib._coords(cnt, (5.0, 2.2, 1.0))
    cn = lib._noise(cnt, 1.0, 10.0, cvec, 0.62)
    alpha = lib._ramp(cnt, cn, 0.50, 0.66)
    rim = lib._ramp(cnt, cn, 0.50, 0.57, (0.45, 0.02, 0.015, 1), (0.004, 0.004, 0.008, 1))
    em = cnt.nodes.new('ShaderNodeEmission'); em.inputs[1].default_value = 1.0
    tr = cnt.nodes.new('ShaderNodeBsdfTransparent'); mx = cnt.nodes.new('ShaderNodeMixShader')
    cnt.links.new(rim, em.inputs[0]); cnt.links.new(alpha, mx.inputs[0])
    cnt.links.new(tr.outputs[0], mx.inputs[1]); cnt.links.new(em.outputs[0], mx.inputs[2])
    cnt.links.new(mx.outputs[0], cout.inputs['Surface'])
    cme.materials.append(cm)
    cl = bpy.data.objects.new('Clouds', cme)
    cl.location, cl.scale, cl.rotation_euler = (0, 400.0, 185.0), (620, 260, 1), (R(113), 0, 0)
    cl.visible_shadow = False
    C['Atmos'].objects.link(cl)

    # fog: thin haze everywhere, thick drifting mist near the ground
    f = MB(); f.cube((110, 120, 16), (0, 22, 7.9))
    fm, fnt, fb, fout = lib._new('MAT_Fog')
    fnt.nodes.remove(fb)
    vol = fnt.nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.70, 0.66, 0.85, 1)
    vol.inputs['Anisotropy'].default_value = 0.45
    geo = fnt.nodes.new('ShaderNodeNewGeometry'); sep = fnt.nodes.new('ShaderNodeSeparateXYZ')
    fnt.links.new(geo.outputs['Position'], sep.inputs[0])
    low = lib._ramp(fnt, sep.outputs['Z'], 0.02, 0.24, (1, 1, 1, 1), (0, 0, 0, 1))      # z 0.3m..3.8m of 16m range via /16 below
    zn = lib._math(fnt, 'DIVIDE', sep.outputs['Z'], 16.0)
    fnt.links.new(zn, low.node.inputs[0])
    fv, _ = lib._coords(fnt, 0.09)
    nz = lib._ramp(fnt, lib._noise(fnt, 1.0, 4.0, fv, 0.55), 0.38, 0.75)
    dens = lib._madd(fnt, lib._math(fnt, 'MULTIPLY', low, nz), 0.055, 0.0018)
    fnt.links.new(dens, vol.inputs['Density'])
    fnt.links.new(vol.outputs[0], fout.inputs['Volume'])
    fo = f.obj('Fog_Volume', [fm], C['Atmos'])
    fo.display_type = 'WIRE'


def sun(C, name, color, strength, elev, azim, angle=2.0):
    """azim: compass direction the light comes FROM (0 = north/+Y, 90 = east/+X)."""
    L = bpy.data.lights.new(name, 'SUN')
    L.color, L.energy, L.angle = color, strength, R(angle)
    o = bpy.data.objects.new(name, L)
    d = Vector((math.sin(R(azim)) * math.cos(R(elev)), math.cos(R(azim)) * math.cos(R(elev)), math.sin(R(elev))))
    o.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    C['Lights'].objects.link(o)
    return o


def build_lights(C):
    sun(C, 'LGT_Moon_Key', (0.50, 0.64, 1.0), 0.50, 40, 215, 3.0)      # cold key from front-left
    sun(C, 'LGT_Red_Rim', (1.0, 0.05, 0.025), 0.75, 17, 3, 2.0)         # blood-moon back light
    L = bpy.data.lights.new('LGT_Fill_Violet', 'AREA')
    L.shape, L.size, L.size_y, L.color, L.energy = 'RECTANGLE', 30, 30, (0.45, 0.30, 0.95), 900
    o = bpy.data.objects.new('LGT_Fill_Violet', L); o.location = (0, 6, 16)
    C['Lights'].objects.link(o)


def build_fx(M, C):
    """Falling cherry petals + light snow (particle systems) and petals resting on the floor."""
    sc = bpy.context.scene
    src = col('COL_FX_Sources', C['FX'])
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-.022, -.016, 0), (0, -.02, .006), (.022, -.016, 0), (.026, .012, .003), (0, .02, .008), (-.026, .012, .003))]
    bm.faces.new((vs[0], vs[1], vs[4], vs[5])); bm.faces.new((vs[1], vs[2], vs[3], vs[4]))
    pme = bpy.data.meshes.new('Petal'); bm.to_mesh(pme); bm.free(); pme.materials.append(M['petal'])
    petal = bpy.data.objects.new('FX_Petal_Source', pme); petal.location = (0, 0, -200); src.objects.link(petal)
    s = MB(); s.sphere(0.011, (0, 0, 0), u=6, v=4)
    flake = s.obj('FX_Snow_Source', [M['snowflake']], src); flake.location = (0, 0, -200)

    em = MB(); em.cube((46, 52, 0.01), (0, 2, 13.0))
    emit = em.obj('FX_Emitter', [M['black']], C['FX'])
    emit.show_instancer_for_render = False; emit.show_instancer_for_viewport = False
    for nm, inst, count, grav, size, rnd, brown in (('Petals', petal, 13000, 0.12, 2.0, 0.45, 1.6), ('Snow', flake, 26000, 0.20, 1.5, 0.6, 0.7)):
        md = emit.modifiers.new(nm, 'PARTICLE_SYSTEM')
        ps = md.particle_system.settings
        ps.name = 'PS_' + nm
        ps.count, ps.frame_start, ps.frame_end, ps.lifetime = count, -800, 760, 800
        ps.emit_from, ps.distribution, ps.use_emit_random = 'FACE', 'RAND', True
        ps.normal_factor = 0.0
        ps.object_align_factor = (0, 0, -0.5)
        ps.effector_weights.gravity = grav
        ps.brownian_factor, ps.drag_factor, ps.damping = brown, 0.12, 0.02
        ps.render_type, ps.instance_object = 'OBJECT', inst
        ps.particle_size, ps.size_random = size, rnd
        ps.use_rotations, ps.rotation_mode, ps.rotation_factor_random, ps.phase_factor_random = True, 'NOR', 1.0, 2.0
        ps.angular_velocity_mode, ps.angular_velocity_factor, ps.use_dynamic_rotation = 'RAND', 2.5, True
        md.particle_system.seed = 3 if nm == 'Petals' else 9
        md.particle_system.point_cache.frame_start, md.particle_system.point_cache.frame_end = -800, 760
    for nm, typ, strength, kw in (('FX_Wind', 'WIND', 0.9, {}), ('FX_Turbulence', 'TURBULENCE', 1.6, {'size': 3.5, 'flow': 0.5})):
        bpy.ops.object.effector_add(type=typ, location=(0, 0, 5), rotation=(R(88), 0, R(-70)))
        o = bpy.context.object
        o.name = nm
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        C['FX'].objects.link(o)
        o.field.strength = strength
        for k_, v_ in kw.items():
            setattr(o.field, k_, v_)

    # petals resting on the wet stone, thicker near the edges and trees
    r = random.Random(21)
    bm = bmesh.new()
    for _ in range(5200):
        if r.random() < 0.7:
            side = r.choice((-1, 1))
            x, y = side * (9.3 - abs(r.gauss(0, 2.2))), r.uniform(-16, 13)
            if r.random() < 0.3:
                x, y = r.uniform(-9.5, 9.5), -16 + abs(r.gauss(0, 2.5))
        else:
            x, y = r.uniform(-9.5, 9.5), r.uniform(-16, 13.5)
        s = r.uniform(0.8, 1.5)
        mat = TRS((x, y, 0.004 + r.uniform(0, .004)), (r.uniform(-.15, .15), r.uniform(-.15, .15), r.uniform(0, 6.28)), (s, s, s))
        v2 = [bm.verts.new(mat @ Vector(p)) for p in ((-.022, -.016, 0), (0, -.02, .004), (.022, -.016, 0), (.026, .012, .002), (0, .02, .005), (-.026, .012, .002))]
        bm.faces.new((v2[0], v2[1], v2[4], v2[5])); bm.faces.new((v2[1], v2[2], v2[3], v2[4]))
    gme = bpy.data.meshes.new('Petals_Ground'); bm.to_mesh(gme); bm.free(); gme.materials.append(M['petal'])
    C['FX'].objects.link(bpy.data.objects.new('Petals_Ground', gme))


def cam(C, name, loc, target, lens, fstop=None):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = lens, 36, 0.05, 2000
    o = bpy.data.objects.new(name, cd)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if fstop:
        cd.dof.use_dof, cd.dof.aperture_fstop = True, fstop
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
    C['Cameras'].objects.link(o)
    return o


def build_cameras(C):
    sc = bpy.context.scene
    sc.camera = cam(C, 'CAM_Hero', (-1.4, -11.0, 0.7), (1.0, 6.0, 4.2), 20, fstop=5.6)
    sc.camera.data.dof.focus_distance = 12.0
    cam(C, 'CAM_TopDown', (0.0, -7.0, 46.0), (0.0, 1.5, 0.0), 26)
    cam(C, 'CAM_Torii', (2.5, -3.0, 1.5), (0.0, 12.2, 4.2), 35, fstop=4.0)
    cam(C, 'CAM_Temple', (5.5, -6.0, 1.6), (-12.0, 2.0, 3.5), 28, fstop=4.0)


def setup_render(sc):
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples, sc.cycles.use_denoising = 64, True
    sc.cycles.max_bounces, sc.cycles.diffuse_bounces, sc.cycles.glossy_bounces = 6, 2, 4
    sc.cycles.volume_bounces, sc.cycles.transparent_max_bounces = 0, 12
    for k_, v_ in (('volume_step_rate', 2.0), ('volume_max_steps', 128)):
        if hasattr(sc.cycles, k_):
            setattr(sc.cycles, k_, v_)
    sc.cycles.sample_clamp_indirect, sc.cycles.sample_clamp_direct = 6.0, 0.0
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.fps = 1920, 1080, 24
    sc.frame_start, sc.frame_end = 1, 720
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5


if __name__ == '__main__':
    build()
