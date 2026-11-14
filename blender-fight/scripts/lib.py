"""Shared helpers for the temple-fight Blender scripts (mesh builder + PBR materials)."""
import bpy, bmesh, math, os
from mathutils import Matrix, Euler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ASSETS = os.path.join(ROOT, 'assets')
TEX = os.path.join(ASSETS, 'tex')


# ---------------------------------------------------------------- collections
def col(name, parent=None, linked=True):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if linked:
        p = parent or bpy.context.scene.collection
        if c.name not in p.children:
            p.children.link(c)
    return c


def TRS(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1))


# ---------------------------------------------------------------- mesh builder
class MB:
    """Accumulates primitives into one mesh, one material index per primitive."""

    def __init__(self):
        self.bm = bmesh.new()

    def _tag(self, verts, mat):
        faces = set()
        for v in verts:
            faces.update(v.link_faces)
        for f in faces:
            f.material_index = mat
        return verts

    def cube(self, size, loc, rot=(0, 0, 0), mat=0):
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=TRS(loc, rot, size))
        return self._tag(r['verts'], mat)

    def cone(self, r1, r2, h, loc, rot=(0, 0, 0), segs=16, mat=0, scale=(1, 1, 1)):
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                  radius1=r1, radius2=max(r2, 1e-4), depth=h, matrix=TRS(loc, rot, scale))
        return self._tag(r['verts'], mat)

    def sphere(self, r, loc, scale=(1, 1, 1), mat=0, u=16, v=10):
        r_ = bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=r,
                                       matrix=TRS(loc, (0, 0, 0), scale))
        return self._tag(r_['verts'], mat)

    def obj(self, name, mats, c, bevel=0.0, smooth=False, rough=0.0, rough_scale=0.4):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        if smooth:
            me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
            me.set_sharp_from_angle(angle=math.radians(35))
        o = bpy.data.objects.new(name, me)
        c.objects.link(o)
        if bevel:
            b = o.modifiers.new('Bevel', 'BEVEL')
            b.width, b.segments, b.limit_method, b.angle_limit = bevel, 2, 'ANGLE', math.radians(40)
        if rough:
            s = o.modifiers.new('Subdiv', 'SUBSURF')
            s.subdivision_type, s.levels, s.render_levels = 'SIMPLE', 2, 2
            t = bpy.data.textures.get('TX_Rough') or bpy.data.textures.new('TX_Rough', 'CLOUDS')
            t.noise_scale = rough_scale
            d = o.modifiers.new('Displace', 'DISPLACE')
            d.texture, d.strength, d.texture_coords, d.mid_level = t, rough, 'LOCAL', 0.5
        return o


# ---------------------------------------------------------------- materials
def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes['Principled BSDF'], nt.nodes['Material Output']


def _img(nt, path, non_color=False, box=True):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = 'Non-Color'
    if box:
        n.projection, n.projection_blend = 'BOX', 0.25
    return n


def _math(nt, op, a=None, b=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation, n.use_clamp = op, clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _madd(nt, a, mul, add, clamp=False):
    """a * mul + add"""
    o = _math(nt, 'MULTIPLY_ADD', a, mul, clamp=clamp)
    o.node.inputs[2].default_value = add
    return o


def _mixc(nt, fac, a, b, blend='MIX'):
    n = nt.nodes.new('ShaderNodeMix')
    n.data_type, n.blend_type = 'RGBA', blend
    for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = (*v, 1) if len(v) == 3 else v
        else:
            nt.links.new(v, sock)
    return n.outputs[2]


def _noise(nt, scale, detail=4.0, vec=None, rough=0.55):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    if vec is not None:
        nt.links.new(vec, n.inputs['Vector'])
    return n.outputs[0]


def _ramp(nt, fac, p0, p1, c0=(0, 0, 0, 1), c1=(1, 1, 1, 1)):
    n = nt.nodes.new('ShaderNodeValToRGB')
    e = n.color_ramp.elements
    e[0].position, e[0].color = p0, c0
    e[1].position, e[1].color = p1, c1
    nt.links.new(fac, n.inputs[0])
    return n.outputs[0]


def _coords(nt, scale, kind='Object'):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    s = scale if isinstance(scale, (tuple, list)) else (scale,) * 3
    mp.inputs['Scale'].default_value = s
    nt.links.new(tc.outputs[kind], mp.inputs['Vector'])
    return mp.outputs[0], tc


def pbr(name, tex, scale=1.0, tint=(1, 1, 1), sat=1.0, val=1.0, rough_mul=1.0, rough_add=0.0,
        normal=1.0, coords='Object', metallic=0.0):
    """Principled material from a Poly Haven texture set, box-projected so no UVs are needed."""
    m, nt, bsdf, out = _new(name)
    vec, _ = _coords(nt, scale, coords)
    box = coords != 'UV'
    d = _img(nt, os.path.join(TEX, tex, 'Diffuse.jpg'), box=box)
    r = _img(nt, os.path.join(TEX, tex, 'Rough.jpg'), True, box=box)
    n = _img(nt, os.path.join(TEX, tex, 'nor_gl.jpg'), True, box=box)
    for i in (d, r, n):
        nt.links.new(vec, i.inputs['Vector'])
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    hs.inputs['Saturation'].default_value, hs.inputs['Value'].default_value = sat, val
    nt.links.new(d.outputs['Color'], hs.inputs['Color'])
    base = _mixc(nt, 1.0, hs.outputs[0], tint, 'MULTIPLY')
    nt.links.new(base, bsdf.inputs['Base Color'])
    rr = _math(nt, 'MULTIPLY_ADD', r.outputs['Color'], rough_mul, clamp=True)
    rr.node.inputs[2].default_value = rough_add
    nt.links.new(rr, bsdf.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = normal
    nt.links.new(n.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs[0], bsdf.inputs['Normal'])
    bsdf.inputs['Metallic'].default_value = metallic
    return m


def flat(name, color, rough=0.6, emit=None, emit_strength=0.0, metallic=0.0, alpha=1.0):
    m, nt, bsdf, out = _new(name)
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Alpha'].default_value = alpha
    if emit:
        bsdf.inputs['Emission Color'].default_value = (*emit, 1)
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    return m


def add_cover(mat, color, rough=0.6, thr=0.72, soft=0.18, noise_scale=2.5, amount=1.0, sss=0.0):
    """Lay snow / moss on up-facing surfaces: mixes a second BSDF in by world normal Z + noise."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    src = out.inputs['Surface'].links[0].from_socket
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Normal'], sep.inputs[0])
    vec, _ = _coords(nt, 1.0, 'Object')
    nz = _noise(nt, noise_scale, 5.0, vec)
    z2 =_math(nt, 'ADD', sep.outputs['Z'], _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', nz, 0.5), 0.7))
    fac = _ramp(nt, z2, thr, thr + soft)
    fac = _math(nt, 'MULTIPLY', fac, amount, clamp=True)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = (0.02, 0.02, 0.03)
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


SNOW = (0.80, 0.82, 0.88)
MOSS = (0.035, 0.055, 0.012)


def snow(mat, amount=0.8, thr=0.78):
    return add_cover(mat, SNOW, rough=0.55, thr=thr, amount=amount, noise_scale=1.3, sss=0.3)


def moss(mat, amount=0.9, thr=0.45):
    return add_cover(mat, MOSS, rough=0.95, thr=thr, soft=0.3, amount=amount, noise_scale=4.0)
