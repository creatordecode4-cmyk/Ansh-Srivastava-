"""Shared helpers for the samurai-fight Blender build (headless bpy 5.x)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

# ---------------------------------------------------------------- layout map
# Top-down layout (arena_breakdown.png, panel cropped at x845 y540 and scaled 3x)
# was traced in pixels. 35 px = 1 m. +Y = north = toward the torii gate.
PXM = 35.0


def px(x, y, z=0.0):
    return Vector(((x - 1380.0) / PXM, (730.0 - y) / PXM, z))


# ---------------------------------------------------------------- collections
def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def exclude_coll(name):
    def walk(lc):
        if lc.name == name:
            lc.exclude = True
            return True
        return any(walk(ch) for ch in lc.children)
    walk(bpy.context.view_layer.layer_collection)


def instance(src_coll, loc, rot_z=0.0, scale=1.0, into=None, name=None, tilt=(0.0, 0.0)):
    e = bpy.data.objects.new(name or ("I_" + src_coll.name), None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = src_coll
    e.location = loc
    e.rotation_euler = (tilt[0], tilt[1], rot_z)
    e.scale = (scale,) * 3
    e.empty_display_size = 0.5
    (into or bpy.context.scene.collection).objects.link(e)
    return e


# ---------------------------------------------------------------- mesh helpers
def mesh_obj(name, bm, coll, mats=(), smooth=False, sharp_deg=None, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
        if sharp_deg:
            me.set_sharp_from_angle(angle=math.radians(sharp_deg))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if bevel > 0:
        b = ob.modifiers.new('bevel', 'BEVEL')
        b.width = bevel
        b.segments = 2
        b.limit_method = 'ANGLE'
        b.angle_limit = math.radians(40)
    return ob


def add_box(bm, size, loc=(0, 0, 0), rot=None, mat_index=0):
    m = Matrix.Translation(loc) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    faces = {f for v in r['verts'] for f in v.link_faces}
    for f in faces:
        f.material_index = mat_index
    return r['verts']


def add_cyl(bm, r1, r2, h, loc=(0, 0, 0), segs=12, rot=None, base=True, mat_index=0, tris=False):
    """Cone/cylinder along Z. If base=True loc is the centre of the bottom cap."""
    z = h / 2 if base else 0.0
    m = Matrix.Translation(loc) @ (rot or Matrix.Identity(4)) @ Matrix.Translation((0, 0, z))
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=tris, segments=segs,
                              radius1=r1, radius2=r2, depth=h, matrix=m)
    faces = {f for v in r['verts'] for f in v.link_faces}
    for f in faces:
        f.material_index = mat_index
    return r['verts']


def subdivide(bm, cuts=1):
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)


def rockify(bm, amp=0.04, scale=2.0, seed=0.0, verts=None):
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    bm.normal_update()
    moves = []
    for v in (verts or bm.verts):
        n = noise.fractal(v.co * scale + off, 1.0, 2.0, 4)
        moves.append((v, v.normal * (n * amp)))
    for v, d in moves:
        v.co += d


def uv_box_project(bm, scale=1.0):
    """Cheap per-face box UVs in metres."""
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for l in f.loops:
            l[uv].uv = (l.vert.co[a] * scale, l.vert.co[b] * scale)


# ---------------------------------------------------------------- node helpers
class NT:
    def __init__(self, mat_or_tree):
        self.t = getattr(mat_or_tree, 'node_tree', mat_or_tree)
        self.nodes, self.links = self.t.nodes, self.t.links

    def new(self, typ, **props):
        n = self.nodes.new(typ)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.links.new(a, b)

    def _set(self, sock, val):
        if hasattr(val, 'is_linked') or hasattr(val, 'links'):
            self.links.new(val, sock)
        elif isinstance(val, (tuple, list)) and len(val) == 3 and sock.type == 'RGBA':
            sock.default_value = (*val, 1.0)
        else:
            sock.default_value = val

    def coords(self, kind='Object'):
        return self.new('ShaderNodeTexCoord').outputs[kind]

    def mapping(self, vec, scale=(1, 1, 1), loc=(0, 0, 0)):
        m = self.new('ShaderNodeMapping')
        m.inputs['Scale'].default_value = scale
        m.inputs['Location'].default_value = loc
        self.links.new(vec, m.inputs['Vector'])
        return m.outputs[0]

    def noise(self, vec, scale=5.0, detail=8.0, rough=0.6):
        n = self.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        if vec is not None:
            self.links.new(vec, n.inputs['Vector'])
        return n.outputs[0]

    def voronoi_edge(self, vec, scale=2.0):
        n = self.new('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
        n.inputs['Scale'].default_value = scale
        if vec is not None:
            self.links.new(vec, n.inputs['Vector'])
        return n.outputs[0]

    def ramp(self, fac, stops, interp='LINEAR'):
        r = self.new('ShaderNodeValToRGB')
        cr = r.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for e, (p, c) in zip(cr.elements, stops):
            e.position = p
            e.color = (c, c, c, 1.0) if isinstance(c, (int, float)) else (*c, 1.0)
        self.links.new(fac, r.inputs[0])
        return r.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        m = self.new('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        self._set(m.inputs[0], fac)
        self._set(m.inputs[6], a)
        self._set(m.inputs[7], b)
        return m.outputs[2]

    def math(self, op, a, b=None, clamp=False):
        m = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        self._set(m.inputs[0], a)
        if b is not None:
            self._set(m.inputs[1], b)
        return m.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0):
        m = self.new('ShaderNodeMapRange')
        self.links.new(v, m.inputs[0])
        m.inputs[1].default_value, m.inputs[2].default_value = a, b
        m.inputs[3].default_value, m.inputs[4].default_value = c, d
        return m.outputs[0]

    def sep(self, vec):
        s = self.new('ShaderNodeSeparateXYZ')
        self.links.new(vec, s.inputs[0])
        return s.outputs

    def bump(self, height, strength=0.3, distance=0.05, normal=None):
        b = self.new('ShaderNodeBump')
        b.inputs['Strength'].default_value = strength
        b.inputs['Distance'].default_value = distance
        self.links.new(height, b.inputs['Height'])
        if normal is not None:
            self.links.new(normal, b.inputs['Normal'])
        return b.outputs[0]

    def up_mask(self, lo=0.6, hi=0.95):
        g = self.new('ShaderNodeNewGeometry')
        return self.maprange(self.sep(g.outputs['Normal'])[2], lo, hi)


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = NT(m)
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    return m, (nt, bsdf)


def pset(nt, bsdf, **kw):
    names = {'color': 'Base Color', 'rough': 'Roughness', 'metal': 'Metallic', 'normal': 'Normal',
             'emit': 'Emission Color', 'estr': 'Emission Strength', 'alpha': 'Alpha',
             'sheen': 'Sheen Weight', 'sss': 'Subsurface Weight', 'trans': 'Transmission Weight',
             'coat': 'Coat Weight', 'ior': 'IOR'}
    for k, v in kw.items():
        nt._set(bsdf.inputs[names[k]], v)


def _snow_moss(nt, col, rough, co, moss=0.0, snow=0.0):
    """Layer moss + snow dusting on up-facing surfaces. Returns (color, roughness)."""
    if moss > 0:
        m = nt.math('MULTIPLY', nt.up_mask(0.2, 0.8), nt.ramp(nt.noise(co, 2.2, 6), [(0.5 - 0.25 * moss, 0.0), (0.62, 1.0)]))
        col = nt.mix(m, col, nt.mix(nt.noise(co, 30, 3), (0.025, 0.045, 0.012), (0.07, 0.085, 0.02)))
        rough = nt.mix(m, rough, (0.75, 0.75, 0.75))
    if snow > 0:
        s = nt.math('MULTIPLY', nt.up_mask(0.55, 0.9), nt.ramp(nt.noise(co, 1.3, 9, 0.7), [(0.56 - 0.3 * snow, 0.0), (0.66 - 0.2 * snow, 1.0)]))
        col = nt.mix(s, col, (0.62, 0.66, 0.74))
        rough = nt.mix(s, rough, (0.55, 0.55, 0.55))
    return col, rough


def mat_stone(name='MAT_Stone', base=(0.075, 0.075, 0.085), moss=0.6, snow=0.5, wet=0.5, bump=0.5):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    n1, n2 = nt.noise(co, 2.5, 10, 0.65), nt.noise(co, 22, 5, 0.6)
    crack = nt.ramp(nt.voronoi_edge(nt.mix(0.08, co, nt.noise(co, 3, 4)), 1.8), [(0.0, 1.0), (0.035, 0.0)])
    lo, hi = tuple(c * 0.45 for c in base), tuple(c * 1.5 for c in base)
    col = nt.mix(nt.ramp(n1, [(0.3, 0.0), (0.7, 1.0)]), lo, hi)
    col = nt.mix(nt.math('MULTIPLY', crack, 0.85), col, (0.008, 0.008, 0.01))
    rough = nt.mix(n2, (0.18 + 0.3 * (1 - wet),) * 3, (0.55,) * 3)
    col, rough = _snow_moss(nt, col, rough, co, moss, snow)
    hgt = nt.math('SUBTRACT', nt.math('ADD', n1, nt.math('MULTIPLY', n2, 0.35)), crack)
    pset(nt, b, color=col, rough=rough, normal=nt.bump(hgt, bump, 0.06))
    return m


def mat_floor(name='MAT_FloorSlab'):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    g = nt.new('ShaderNodeNewGeometry')
    n1, n2 = nt.noise(co, 1.1, 10, 0.7), nt.noise(co, 35, 4, 0.6)
    warp = nt.mix(0.12, co, nt.noise(co, 2.0, 5))
    crack = nt.ramp(nt.voronoi_edge(warp, 0.9), [(0.0, 1.0), (0.018, 0.0)])
    crack2 = nt.ramp(nt.voronoi_edge(warp, 3.1), [(0.0, 1.0), (0.012, 0.0)])
    crack2 = nt.math('MULTIPLY', crack2, nt.ramp(nt.noise(co, 0.5, 2), [(0.5, 0.0), (0.6, 1.0)]))
    cracks = nt.math('MAXIMUM', crack, crack2)
    col = nt.mix(nt.ramp(n1, [(0.25, 0.0), (0.75, 1.0)]), (0.03, 0.03, 0.036), (0.11, 0.105, 0.12))
    col = nt.mix(nt.math('MULTIPLY', g.outputs['Random Per Island'], 0.35), col, (0.035, 0.03, 0.04))
    col = nt.mix(cracks, col, (0.004, 0.004, 0.005))
    puddle = nt.ramp(nt.noise(co, 0.33, 5, 0.55), [(0.40, 1.0), (0.50, 0.0)])
    rough = nt.mix(puddle, nt.mix(n1, (0.20,) * 3, (0.46,) * 3), (0.04,) * 3)
    hgt = nt.math('SUBTRACT', nt.math('ADD', nt.math('MULTIPLY', n1, 0.6), nt.math('MULTIPLY', n2, 0.2)), nt.math('MULTIPLY', cracks, 1.5))
    hgt = nt.mix(puddle, hgt, nt.math('MULTIPLY', hgt, 0.15))
    pset(nt, b, color=col, rough=rough, normal=nt.bump(hgt, 0.8, 0.08))
    return m


def mat_ground(name='MAT_Ground'):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    n1, n2 = nt.noise(co, 0.6, 10, 0.7), nt.noise(co, 14, 6, 0.65)
    col = nt.mix(n1, (0.012, 0.012, 0.014), (0.045, 0.04, 0.04))
    rough = nt.mix(nt.ramp(n1, [(0.4, 0.0), (0.55, 1.0)]), (0.08,) * 3, (0.6,) * 3)
    col, rough = _snow_moss(nt, col, rough, co, 0.5, 0.75)
    pset(nt, b, color=col, rough=rough, normal=nt.bump(nt.math('ADD', n1, nt.math('MULTIPLY', n2, 0.5)), 0.6, 0.1))
    return m


def mat_water(name='MAT_WaterFilm'):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    rip = nt.noise(co, 9.0, 3, 0.5)
    pset(nt, b, color=(0.004, 0.004, 0.006), rough=0.0, normal=nt.bump(rip, 0.04, 0.01))
    return m


def mat_lacquer(name='MAT_RedLacquer', red=(0.30, 0.022, 0.018)):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    n1, n2 = nt.noise(co, 3.5, 10, 0.75), nt.noise(nt.mapping(co, (20, 20, 2)), 4, 5)
    chip = nt.ramp(n1, [(0.52, 0.0), (0.6, 1.0)])
    col = nt.mix(nt.noise(co, 1.2, 4), tuple(c * 0.55 for c in red), red)
    col = nt.mix(chip, col, (0.022, 0.014, 0.014))
    rough = nt.mix(chip, (0.28,) * 3, (0.6,) * 3)
    col, rough = _snow_moss(nt, col, rough, co, 0.0, 0.55)
    pset(nt, b, color=col, rough=rough, normal=nt.bump(nt.math('ADD', nt.math('MULTIPLY', chip, 0.5), nt.math('MULTIPLY', n2, 0.3)), 0.35, 0.03))
    return m


def mat_wood_dark(name='MAT_WoodDark', base=(0.04, 0.026, 0.022)):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    grain = nt.noise(nt.mapping(co, (14, 14, 1.2)), 5, 6, 0.6)
    col = nt.mix(grain, tuple(c * 0.5 for c in base), tuple(c * 1.5 for c in base))
    rough = nt.mix(grain, (0.3,) * 3, (0.6,) * 3)
    col, rough = _snow_moss(nt, col, rough, co, 0.0, 0.4)
    pset(nt, b, color=col, rough=rough, normal=nt.bump(grain, 0.3, 0.02))
    return m


def mat_roof(name='MAT_RoofTile'):
    """Needs UVs in metres: u along the eave, v up the slope."""
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co, uv = nt.coords('Object'), nt.coords('UV')
    u, v, _ = nt.sep(uv)
    rib = nt.math('ABSOLUTE', nt.math('SINE', nt.math('MULTIPLY', u, math.pi / 0.30)))
    rib = nt.math('POWER', rib, 0.45)
    course = nt.math('FRACT', nt.math('MULTIPLY', v, 1 / 0.38))
    n1 = nt.noise(co, 4, 8)
    col = nt.mix(n1, (0.018, 0.02, 0.026), (0.05, 0.055, 0.065))
    col = nt.mix(nt.math('MULTIPLY', nt.math('SUBTRACT', 1.0, rib), 0.7), col, (0.006, 0.006, 0.008))
    rough = nt.mix(n1, (0.2,) * 3, (0.45,) * 3)
    col, rough = _snow_moss(nt, col, rough, co, 0.25, 0.8)
    hgt = nt.math('ADD', rib, nt.math('MULTIPLY', course, 0.35))
    pset(nt, b, color=col, rough=rough, normal=nt.bump(hgt, 0.9, 0.06))
    return m


def mat_window(name='MAT_WindowGlow', strength=2.0, cell=0.22):
    """Emissive paper window behind a wooden lattice. UVs in metres."""
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    u, v, _ = nt.sep(nt.coords('UV'))
    fu = nt.math('FRACT', nt.math('MULTIPLY', u, 1 / cell))
    fv = nt.math('FRACT', nt.math('MULTIPLY', v, 1 / cell))
    bar = nt.math('MAXIMUM', nt.math('LESS_THAN', fu, 0.26), nt.math('LESS_THAN', fv, 0.26))
    glow = nt.mix(nt.noise(nt.coords('Object'), 1.5, 3), (1.0, 0.035, 0.01), (1.0, 0.11, 0.025))
    pset(nt, b, color=nt.mix(bar, (0.25, 0.03, 0.02), (0.02, 0.012, 0.01)), rough=0.6,
         emit=nt.mix(bar, glow, (0, 0, 0)), estr=strength)
    return m


def mat_emit(name, color, strength, rib=False):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    col = color
    if rib:
        z = nt.sep(nt.coords('Object'))[2]
        r = nt.math('ABSOLUTE', nt.math('SINE', nt.math('MULTIPLY', z, math.pi / 0.045)))
        col = nt.mix(nt.math('POWER', r, 0.3), tuple(c * 0.25 for c in color), color)
    pset(nt, b, color=tuple(c * 0.5 for c in color), rough=0.6, emit=col, estr=strength)
    return m


def mat_banner(name='MAT_Banner'):
    """Red cloth with a round crest and a torn lower edge. UV 0..1, v=0 at the bottom."""
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    m.use_backface_culling = False
    uv, co = nt.coords('UV'), nt.coords('Object')
    u, v, _ = nt.sep(uv)
    # crest centre (0.5, 0.62), aspect 1:3.6
    dx = nt.math('SUBTRACT', u, 0.5)
    dy = nt.math('MULTIPLY', nt.math('SUBTRACT', v, 0.62), 3.6)
    r = nt.math('SQRT', nt.math('ADD', nt.math('MULTIPLY', dx, dx), nt.math('MULTIPLY', dy, dy)))
    ring = nt.math('LESS_THAN', nt.math('ABSOLUTE', nt.math('SUBTRACT', r, 0.34)), 0.03)
    ang = nt.math('ARCTAN2', dy, dx)
    seg = 2 * math.pi / 5
    a2 = nt.math('SUBTRACT', nt.math('MODULO', nt.math('ADD', ang, 10 * seg + seg / 2), seg), seg / 2)
    pxx = nt.math('SUBTRACT', nt.math('MULTIPLY', r, nt.math('COSINE', a2)), 0.17)
    pyy = nt.math('MULTIPLY', r, nt.math('SINE', a2))
    petal = nt.math('LESS_THAN', nt.math('SQRT', nt.math('ADD', nt.math('MULTIPLY', pxx, pxx), nt.math('MULTIPLY', pyy, pyy))), 0.085)
    crest = nt.math('MAXIMUM', ring, nt.math('MAXIMUM', petal, nt.math('LESS_THAN', r, 0.05)))
    n1 = nt.noise(co, 6, 8, 0.7)
    col = nt.mix(n1, (0.10, 0.008, 0.008), (0.28, 0.02, 0.018))
    col = nt.mix(nt.math('MULTIPLY', crest, 0.85), col, (0.55, 0.42, 0.25))
    tear = nt.math('GREATER_THAN', v, nt.math('MULTIPLY', nt.noise(nt.mapping(uv, (9, 1.2, 1)), 3, 4, 0.8), 0.22))
    holes = nt.math('LESS_THAN', nt.noise(co, 9, 3), 0.72)
    pset(nt, b, color=col, rough=0.8, sheen=0.12, alpha=nt.math('MULTIPLY', tear, holes))
    return m


def mat_blossom(name='MAT_Blossom'):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    m.use_backface_culling = False
    g = nt.new('ShaderNodeNewGeometry')
    col = nt.mix(g.outputs['Random Per Island'], (0.62, 0.30, 0.46), (0.95, 0.72, 0.82))
    tr = nt.new('ShaderNodeBsdfTranslucent')
    nt.link(col, tr.inputs['Color'])
    pset(nt, b, color=col, rough=0.55, sheen=0.3)
    mx = nt.new('ShaderNodeMixShader')
    mx.inputs[0].default_value = 0.45
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    nt.link(b.outputs[0], mx.inputs[1])
    nt.link(tr.outputs[0], mx.inputs[2])
    nt.link(mx.outputs[0], out.inputs['Surface'])
    return m


def mat_simple(name, color, rough=0.6, metal=0.0, bump=0.0, bump_scale=20.0, snow=0.0):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    n = nt.noise(co, bump_scale, 6, 0.6)
    col = nt.mix(n, tuple(c * 0.6 for c in color), tuple(c * 1.3 for c in color))
    r = nt.mix(n, (rough * 0.8,) * 3, (min(1.0, rough * 1.2),) * 3)
    col, r = _snow_moss(nt, col, r, co, 0.0, snow)
    kw = dict(color=col, rough=r, metal=metal)
    if bump > 0:
        kw['normal'] = nt.bump(n, bump, 0.03)
    pset(nt, b, **kw)
    return m


def mat_moon(name='MAT_BloodMoon', strength=1.6):
    m, h = new_mat(name)
    if not h:
        return m
    nt, b = h
    co = nt.coords('Object')
    n1 = nt.noise(co, 1.7, 10, 0.72)
    n2 = nt.noise(co, 7.0, 6, 0.6)
    maria = nt.ramp(nt.math('ADD', nt.math('MULTIPLY', n1, 0.8), nt.math('MULTIPLY', n2, 0.2)), [(0.38, 0.0), (0.62, 1.0)])
    col = nt.mix(maria, (0.30, 0.004, 0.003), (1.0, 0.045, 0.02))
    lw = nt.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    limb = nt.math('POWER', nt.math('SUBTRACT', 1.0, lw.outputs['Facing']), 0.6)
    pset(nt, b, color=(0, 0, 0), rough=1.0, emit=col, estr=nt.math('MULTIPLY', limb, strength))
    return m


def mat_fog(name, density, aniso=0.55, color=(0.8, 0.82, 1.0)):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = NT(m)
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    v = nt.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = density
    v.inputs['Anisotropy'].default_value = aniso
    v.inputs['Color'].default_value = (*color, 1.0)
    nt.link(v.outputs[0], out.inputs['Volume'])
    return m


def mat_cloud(name='MAT_Cloud', moon_uv=(0.08, 0.11)):
    """Backlit night clouds on a big card behind the set. Object coords run -0.5..0.5."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = NT(m)
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    co = nt.coords('Object')
    x, y, _ = nt.sep(co)
    n = nt.noise(nt.mapping(co, (1.0, 2.3, 1.0)), 5.0, 12, 0.62)
    edge = nt.math('MULTIPLY', nt.maprange(nt.math('ABSOLUTE', x), 0.5, 0.3), nt.maprange(nt.math('ABSOLUTE', y), 0.5, 0.25))
    alpha = nt.math('MULTIPLY', nt.ramp(n, [(0.47, 0.0), (0.66, 1.0)]), edge)
    dx, dy = nt.math('SUBTRACT', x, moon_uv[0]), nt.math('MULTIPLY', nt.math('SUBTRACT', y, moon_uv[1]), 0.5)
    d = nt.math('SQRT', nt.math('ADD', nt.math('MULTIPLY', dx, dx), nt.math('MULTIPLY', dy, dy)))
    glow = nt.ramp(d, [(0.0, 1.0), (0.22, 0.0)])
    thin = nt.ramp(n, [(0.5, 1.0), (0.8, 0.0)])
    col = nt.mix(nt.math('MULTIPLY', glow, thin), (0.004, 0.004, 0.009), (0.5, 0.035, 0.02))
    em = nt.new('ShaderNodeEmission')
    nt.link(col, em.inputs['Color'])
    tr = nt.new('ShaderNodeBsdfTransparent')
    mx = nt.new('ShaderNodeMixShader')
    nt.link(alpha, mx.inputs[0])
    nt.link(tr.outputs[0], mx.inputs[1])
    nt.link(em.outputs[0], mx.inputs[2])
    nt.link(mx.outputs[0], out.inputs['Surface'])
    return m
