"""PBR materials for the night temple courtyard (Cycles, Blender 5.3).

materials.get(name) calls build(name). Every material works on meshes WITHOUT UVs: textures are looked up with
Object coordinates (metres) and BOX projection, normal maps are turned into object-space normals by the node group
FILM_BoxNormal (tangent frames of the three box projections), then converted to world space.

Tuning for the integrator
  * module constants below are the defaults baked into newly built materials
  * every tunable is also a Value node named and labelled like the constant ("Wetness", "Snow Amount", ...);
    set_param("Snow Amount", 0.2) changes it in every material that has it, params(mat) lists them
  * TILE_M holds the mapping scale of every texture: metres covered by one texture tile
"""
import math
import os

import bpy

try:
    from . import common
except ImportError:  # imported as a plain module by the test scripts
    from lib import common

# ----------------------------------------------------------------------------------------------- tunables
RES = "2k"
BOX_BLEND = 0.2

WETNESS = 1.0          # "Wetness": 0 dry .. 1 soaked (coat weight, lower roughness, darker albedo)
PUDDLE_AMOUNT = 0.5    # "Puddle Amount": share of standing water on the floor / ground (0 .. 1)
SNOW_AMOUNT = 0.5      # "Snow Amount": 0 none, 0.5 thin patches on up-facing parts, 1 heavy
MOSS_AMOUNT = 0.6      # "Moss Amount": 0 none .. 1 heavy
CRACK_AMOUNT = 0.65    # "Crack Amount": share of floor slabs broken into pieces
SLAB_TILT = 0.03       # "Slab Tilt": random lean of each floor slab (normal xy units, 0.03 = about 1.7 deg at most)
TILE_PATTERN = 0.0     # "Tile Pattern": painted roof-tile relief; 0 for roofs with modelled tiles (props_temple), 1 for plain roof planes
PAINT_WEAR = 0.55      # "Paint Wear": chipped share of the red lacquer
BLOSSOM_GLOW = 0.0     # "Glow": self-illumination of blossoms / petals (0 = lit by scene lights only)
EMISSION = {           # "Emission Strength" per emissive material
    "MAT_Paper_Lantern": 6.0,
    "MAT_Lantern_Glow": 14.0,
    "MAT_Window_Glow": 1.5,
    "MAT_Moon": 3.0,
}
CREST = {              # crest placement: (height as a fraction of the object's bounding box, radius as a fraction of its width)
    "MAT_Paper_Lantern": (0.50, 0.30),
    "MAT_Banner_Red": (0.62, 0.36),
}

# metres covered by one texture tile (a tuple is x, y, z)
TILE_M = {
    "MAT_Floor_WetStone": {"large_floor_tiles_02": 3.0, "stone_tiles_02": 4.2},
    "MAT_Stone_Mossy": {"mossy_rock": 2.2},
    "MAT_Stone_Block": {"japanese_stone_wall": 1.9},
    "MAT_Wood_Red": {"wood_peeling_paint_weathered": (0.5, 0.5, 1.3)},
    "MAT_Wood_Dark": {"weathered_planks": 2.0},
    "MAT_Roof_Tile": {"roof_tiles_14": 4.0},
    "MAT_Plaster": {"white_plaster_rough_01": 1.5},
    "MAT_Ground_Dark": {"mossy_rock": 5.0},
    "MAT_Bark": {"sakura_bark": 1.6},
    "MAT_Banner_Red": {"rough_linen": 0.45},
}

PI = math.pi


# ----------------------------------------------------------------------------------------------- node helpers
def _s(coll, ident):
    for s in coll:
        if s.identifier == ident:
            return s
    return coll[ident]


def _img(slug, kind):
    path = os.path.join(common.PH, slug, f"{slug}_{kind}_{RES}.jpg")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB" if kind == "Diffuse" else "Non-Color"
    return img


class _G:
    """Small node-graph writer. Methods return output sockets; arguments are sockets or constants."""

    def __init__(self, tree):
        self.nt = tree
        self._i = 0

    def node(self, idname, label=None, **props):
        n = self.nt.nodes.new(idname)
        n.location = (230 * (self._i % 16), -200 * (self._i // 16))
        self._i += 1
        if label:
            n.name = n.label = label
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
            return
        if sock.type == "RGBA":
            v = (v, v, v, 1.0) if isinstance(v, (int, float)) else (tuple(v) + (1.0,))[:4]
        elif sock.type == "VECTOR" and isinstance(v, (int, float)):
            v = (v, v, v)
        sock.default_value = v

    # scalar maths
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for s, v in zip(n.inputs, (a, b, c)):
            self.put(s, v)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def mul(self, a, b, clamp=False):
        return self.math("MULTIPLY", a, b, clamp=clamp)

    def mad(self, a, b, c):
        return self.math("MULTIPLY_ADD", a, b, c)

    def mx(self, a, b):
        return self.math("MAXIMUM", a, b)

    def mn(self, a, b):
        return self.math("MINIMUM", a, b)

    def inv(self, a):
        return self.math("SUBTRACT", 1.0, a, clamp=True)

    def sat(self, a):
        return self.math("ADD", a, 0.0, clamp=True)

    # vector maths
    def vmath(self, op, a, b=None, c=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        self.put(n.inputs[2], c)
        self.put(n.inputs[3], scale)
        return n.outputs[1] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs[0]

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x=0.0, y=0.0, z=0.0):
        n = self.node("ShaderNodeCombineXYZ")
        for s, v in zip(n.inputs, (x, y, z)):
            self.put(s, v)
        return n.outputs[0]

    # mixing
    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_factor=True)
        self.put(_s(n.inputs, "Factor_Float"), fac)
        self.put(_s(n.inputs, "A_Color"), a)
        self.put(_s(n.inputs, "B_Color"), b)
        return _s(n.outputs, "Result_Color")

    def cscale(self, color, f):
        """colour * f (f: number, colour or socket)"""
        return self.mix(1.0, color, f, "MULTIPLY")

    def lerp(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT", clamp_factor=True)
        self.put(_s(n.inputs, "Factor_Float"), fac)
        self.put(_s(n.inputs, "A_Float"), a)
        self.put(_s(n.inputs, "B_Float"), b)
        return _s(n.outputs, "Result_Float")

    def vmix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="VECTOR", clamp_factor=True)
        self.put(_s(n.inputs, "Factor_Float"), fac)
        self.put(_s(n.inputs, "A_Vector"), a)
        self.put(_s(n.inputs, "B_Vector"), b)
        return _s(n.outputs, "Result_Vector")

    def _range(self, kind, v, lo, hi, out_lo, out_hi):
        n = self.node("ShaderNodeMapRange", interpolation_type=kind)
        n.clamp = True
        for s, val in zip(n.inputs, (v, lo, hi, out_lo, out_hi)):
            self.put(s, val)
        return n.outputs[0]

    def smooth(self, v, lo, hi, out_lo=0.0, out_hi=1.0):
        return self._range("SMOOTHSTEP", v, lo, hi, out_lo, out_hi)

    def remap(self, v, lo, hi, out_lo=0.0, out_hi=1.0):
        return self._range("LINEAR", v, lo, hi, out_lo, out_hi)

    # textures
    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0, color=False, dims="3D"):
        n = self.node("ShaderNodeTexNoise", noise_dimensions=dims)
        self.put(n.inputs["Vector"], vec)
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Detail"], detail)
        self.put(n.inputs["Roughness"], rough)
        self.put(n.inputs["Distortion"], distortion)
        return n.outputs[1 if color else 0]

    def voronoi(self, vec, scale, feature="F1", out="Distance", randomness=1.0, dims="3D"):
        n = self.node("ShaderNodeTexVoronoi", feature=feature, voronoi_dimensions=dims)
        self.put(n.inputs["Vector"], vec)
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Randomness"], randomness)
        return n.outputs[out]

    def white(self, vec, color=True):
        n = self.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
        self.put(n.inputs["Vector"], vec)
        return n.outputs[1 if color else 0]

    def lum(self, color):
        n = self.node("ShaderNodeRGBToBW")
        self.put(n.inputs[0], color)
        return n.outputs[0]

    def hsv(self, color, sat=1.0, val=1.0, hue=0.5):
        n = self.node("ShaderNodeHueSaturation")
        self.put(n.inputs["Hue"], hue)
        self.put(n.inputs["Saturation"], sat)
        self.put(n.inputs["Value"], val)
        self.put(n.inputs["Color"], color)
        return n.outputs[0]

    def mapping(self, vec, metres=1.0, loc=(0.0, 0.0, 0.0)):
        n = self.node("ShaderNodeMapping", vector_type="POINT")
        if isinstance(metres, (int, float)):
            metres = (metres, metres, metres)
        self.put(n.inputs["Vector"], vec)
        n.inputs["Location"].default_value = loc
        n.inputs["Scale"].default_value = tuple(1.0 / v for v in metres)
        return n.outputs[0]

    def image(self, slug, kind, vec, projection="BOX", interp="Linear"):
        n = self.node("ShaderNodeTexImage", f"{slug} {kind}", image=_img(slug, kind), projection=projection,
                      interpolation=interp, extension="REPEAT")
        if projection == "BOX":
            n.projection_blend = BOX_BLEND
        self.put(n.inputs[0], vec)
        return n.outputs[0]


def _box_normal_group():
    """Node group: tangent-space normal-map colour sampled with BOX projection -> world-space normal.

    Cycles box projection uses these (u, v) per dominant axis of the object-space normal N:
      X: (+-y, z)   Y: (-+x, z)   Z: (-+y, x)       so the tangent / bitangent of each projection are known.
    Checked against Bump(height) on all six faces of a cube (correlation > 0.9 in every channel).
    """
    name = "FILM_BoxNormal"
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor").default_value = (0.5, 0.5, 1.0, 1.0)
    ng.interface.new_socket("Strength", in_out="INPUT", socket_type="NodeSocketFloat").default_value = 1.0
    ng.interface.new_socket("Normal", in_out="OUTPUT", socket_type="NodeSocketVector")
    g = _G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    nobj = g.node("ShaderNodeTexCoord").outputs["Normal"]
    a = g.vmath("ABSOLUTE", nobj)
    a2 = g.vmath("MULTIPLY", a, a)
    a4 = g.vmath("MULTIPLY", a2, a2)
    a8 = g.vmath("MULTIPLY", a4, a4)
    total = g.vmath("DOT_PRODUCT", a8, (1.0, 1.0, 1.0))
    w = g.vmath("SCALE", a8, scale=g.math("DIVIDE", 1.0, g.mx(total, 1e-6)))
    wx, wy, wz = g.sep(w)
    sx, sy, sz = g.sep(g.vmath("SIGN", nobj))
    cr, cg, _ = g.sep(gin.outputs["Color"])
    r = g.mad(cr, 2.0, -1.0)
    gg = g.mad(cg, 2.0, -1.0)
    px = g.sub(g.mul(wz, gg), g.mul(g.mul(wy, sy), r))
    py = g.mul(g.sub(g.mul(wx, sx), g.mul(wz, sz)), r)
    pz = g.mul(g.add(wx, wy), gg)
    pert = g.vmath("SCALE", g.comb(px, py, pz), scale=gin.outputs["Strength"])
    nn = g.vmath("NORMALIZE", g.vmath("ADD", nobj, pert))
    vt = g.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="OBJECT", convert_to="WORLD")
    g.put(vt.inputs["Vector"], nn)
    g.put(gout.inputs["Normal"], vt.outputs[0])
    return ng


class _Set:
    """Sockets of one texture set."""
    def __init__(self, color, nor, ao, rough):
        self.color, self.nor, self.ao, self.rough = color, nor, ao, rough


_PRINCIPLED = {
    "color": "Base Color", "rough": "Roughness", "metallic": "Metallic", "normal": "Normal", "ior": "IOR",
    "coat": "Coat Weight", "coat_rough": "Coat Roughness", "coat_ior": "Coat IOR", "coat_normal": "Coat Normal",
    "sheen": "Sheen Weight", "sheen_rough": "Sheen Roughness", "sheen_tint": "Sheen Tint",
    "emission": "Emission Color", "strength": "Emission Strength", "spec": "Specular IOR Level",
    "sss": "Subsurface Weight", "sss_radius": "Subsurface Radius", "sss_scale": "Subsurface Scale", "alpha": "Alpha",
}


class _M(_G):
    """One material: Principled BSDF + Output, lazily created coordinate sockets and named Value nodes."""

    def __init__(self, name):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        super().__init__(mat.node_tree)
        self.nt.nodes.clear()
        self.mat = mat
        self.key = name
        self._c = {}
        self._params = {}
        self.out = self.node("ShaderNodeOutputMaterial")
        self.bsdf = self.node("ShaderNodeBsdfPrincipled")
        self.nt.links.new(self.bsdf.outputs[0], self.out.inputs["Surface"])

    def _tc(self):
        if "tc" not in self._c:
            self._c["tc"] = self.node("ShaderNodeTexCoord")
        return self._c["tc"]

    @property
    def obj(self):
        return self._tc().outputs["Object"]

    @property
    def nobj(self):
        return self._tc().outputs["Normal"]

    @property
    def gen(self):
        return self._tc().outputs["Generated"]

    @property
    def geo(self):
        if "geo" not in self._c:
            self._c["geo"] = self.node("ShaderNodeNewGeometry")
        return self._c["geo"]

    @property
    def nz(self):
        """World-space normal Z of the smooth surface (1 = facing the sky)."""
        if "nz" not in self._c:
            self._c["nz"] = self.sep(self.geo.outputs["Normal"])[2]
        return self._c["nz"]

    @property
    def big(self):
        if "big" not in self._c:
            self._c["big"] = self.noise(self.obj, 1.1, detail=3.0, rough=0.6)
        return self._c["big"]

    @property
    def patch(self):
        if "patch" not in self._c:
            self._c["patch"] = self.noise(self.obj, 2.6, detail=3.0, rough=0.6)
        return self._c["patch"]

    @property
    def mid(self):
        if "mid" not in self._c:
            self._c["mid"] = self.noise(self.obj, 6.5, detail=2.0, rough=0.6)
        return self._c["mid"]

    def param(self, label, value):
        if label not in self._params:
            n = self.node("ShaderNodeValue", label)
            n.outputs[0].default_value = value
            self._params[label] = n.outputs[0]
        return self._params[label]

    def attr(self, name, kind="OBJECT"):
        n = self.node("ShaderNodeAttribute", attribute_type=kind, attribute_name=name)
        return n

    def tex(self, slug, kind, metres=None, vec=None, **kw):
        if vec is None:
            metres = metres if metres is not None else TILE_M[self.key][slug]
            key = ("map", str(metres))
            if key not in self._c:
                self._c[key] = self.mapping(self.obj, metres)
            vec = self._c[key]
        return self.image(slug, kind, vec, **kw)

    def pbr(self, slug, metres=None, vec=None, **kw):
        col = self.tex(slug, "Diffuse", metres, vec, **kw)
        nor = self.tex(slug, "nor_gl", metres, vec, **kw)
        ao, rough, _ = self.sep(self.tex(slug, "arm", metres, vec, **kw))
        return _Set(col, nor, ao, rough)

    def box_normal(self, color, strength=1.0):
        n = self.node("ShaderNodeGroup")
        n.node_tree = _box_normal_group()
        self.put(n.inputs["Color"], color)
        self.put(n.inputs["Strength"], strength)
        return n.outputs["Normal"]

    def bump(self, height, normal=None, strength=1.0):
        """height in metres"""
        n = self.node("ShaderNodeBump")
        n.inputs["Distance"].default_value = 1.0
        self.put(n.inputs["Strength"], strength)
        self.put(n.inputs["Height"], height)
        self.put(n.inputs["Normal"], normal)
        return n.outputs[0]

    def surface(self, **kw):
        for k, v in kw.items():
            self.put(self.bsdf.inputs[_PRINCIPLED[k]], v)

    def translucent(self, color, fac):
        """Blend a translucent lobe in so thin cloth / petals glow when lit from behind."""
        tr = self.node("ShaderNodeBsdfTranslucent")
        self.put(tr.inputs["Color"], color)
        mx = self.node("ShaderNodeMixShader")
        self.put(mx.inputs[0], fac)
        self.nt.links.new(self.bsdf.outputs[0], mx.inputs[1])
        self.nt.links.new(tr.outputs[0], mx.inputs[2])
        self.nt.links.new(mx.outputs[0], self.out.inputs["Surface"])


# ----------------------------------------------------------------------------------------------- shared recipes
def _weather(m, color, rough, crevice=0.0, moss_gain=1.0, snow_gain=1.0, shade=1.0, snow_bias=0.0):
    """Moss on up-facing / creviced areas and thin snow on the top-facing ones (world normal Z).

    Returns colour, roughness, extra height (m), cover (1 where moss or snow hides the wet stone).
    """
    nz = m.nz
    big, mid = m.big, m.mid
    # moss
    amt = m.mul(m.param("Moss Amount", MOSS_AMOUNT), moss_gain)
    up = m.smooth(nz, 0.0, 0.9)
    field = m.add(m.add(m.mul(up, 0.55), m.mul(crevice, 0.35)),
                  m.add(m.mad(m.patch, 1.5, -0.75), m.mad(mid, 0.7, -0.35)))
    thr = m.sub(1.15, amt)
    moss = m.mul(m.smooth(m.sub(field, thr), -0.09, 0.09), m.mul(amt, 5.0), clamp=True)
    fuzz = m.noise(m.obj, 70.0, detail=2.0, rough=0.6)
    moss_col = m.mix(mid, (0.014, 0.026, 0.005), (0.060, 0.078, 0.014))
    moss_col = m.mix(m.smooth(fuzz, 0.55, 0.8), moss_col, (0.075, 0.07, 0.02))      # dry yellowish tips
    moss_col = m.cscale(m.cscale(moss_col, m.mad(fuzz, 0.9, 0.5)), shade)
    color = m.mix(moss, color, moss_col)
    rough = m.lerp(moss, rough, 0.92)
    # snow
    s_amt = m.mul(m.param("Snow Amount", SNOW_AMOUNT), snow_gain)
    big2 = m.noise(m.vmath("ADD", m.obj, (13.7, 5.1, 8.3)), 0.9, detail=3.0, rough=0.65)
    s_field = m.add(m.smooth(nz, 0.5, 0.92), m.add(m.mad(big2, 0.5, -0.25), m.mad(m.patch, 0.3, -0.15)))
    s_field = m.add(s_field, snow_bias)
    s_thr = m.sub(1.33, m.mul(s_amt, 0.5))
    snow = m.mul(m.smooth(m.sub(s_field, s_thr), -0.05, 0.05), m.mul(s_amt, 5.0), clamp=True)
    color = m.mix(snow, color, m.cscale((0.78, 0.82, 0.90), m.mad(mid, 0.2, 0.9)))
    rough = m.lerp(snow, rough, 0.6)
    height = m.add(m.mul(moss, m.add(m.mad(mid, 0.004, 0.001), m.mul(fuzz, 0.0015))), m.mul(snow, 0.006))
    cover = m.mx(moss, snow)
    return color, rough, height, cover


def _crest_coords(m):
    """Position relative to the crest centre (dx, dz in local metres) and the crest radius.

    Default: centre of the bounding box in X, CREST height fraction of the box in Z, radius = fraction of the box width.
    An object can override this with custom properties crest_center = [x, y, z] (local metres) and crest_radius (m).
    """
    h_frac, r_frac = CREST[m.key]
    dims = m.vmath("DIVIDE", m.attr("dimensions").outputs["Vector"], m.attr("scale").outputs["Vector"])
    centre = m.comb(0.5, 0.5, m.param("Crest Height", h_frac))
    rel = m.vmath("MULTIPLY", m.vmath("SUBTRACT", m.gen, centre), dims)
    cc = m.attr("crest_center")
    rel = m.vmix(cc.outputs["Alpha"], rel, m.vmath("SUBTRACT", m.obj, cc.outputs["Vector"]))
    dx, _, dz = m.sep(rel)
    radius = m.mul(m.sep(dims)[0], m.param("Crest Radius", r_frac))
    cr = m.attr("crest_radius")
    radius = m.lerp(cr.outputs["Alpha"], radius, cr.outputs[2])
    return dx, dz, radius


def _crest_mask(m, dx, dz, radius):
    """Round family crest (mon): ring, five petals and a centre dot. 1 inside the drawn parts."""
    rho = m.math("DIVIDE", m.math("SQRT", m.add(m.mul(dx, dx), m.mul(dz, dz))), m.mx(radius, 1e-4))
    th = m.math("ARCTAN2", dz, dx)
    ring = m.mul(m.smooth(rho, 0.80, 0.84), m.inv(m.smooth(rho, 0.96, 1.0)))
    a = m.math("WRAP", m.add(th, PI / 2), PI / 5, -PI / 5)
    px = m.sub(m.mul(rho, m.math("COSINE", a)), 0.42)
    py = m.mul(rho, m.math("SINE", a))
    e = m.math("SQRT", m.add(m.math("POWER", m.math("DIVIDE", px, 0.25), 2.0), m.math("POWER", m.math("DIVIDE", py, 0.20), 2.0)))
    petal = m.inv(m.smooth(e, 0.9, 1.05))
    dot = m.inv(m.smooth(rho, 0.08, 0.11))
    return m.mx(ring, m.mx(petal, dot))


# ----------------------------------------------------------------------------------------------- stone
def _floor_wet_stone(m):
    wet = m.param("Wetness", WETNESS)
    pud_amt = m.param("Puddle Amount", PUDDLE_AMOUNT)
    moss_amt = m.param("Moss Amount", MOSS_AMOUNT)
    crack_amt = m.param("Crack Amount", CRACK_AMOUNT)
    tilt_amt = m.param("Slab Tilt", SLAB_TILT)

    # 1 m slabs; joints lie on whole metres of the object X / Y axes (a little wobbly)
    x, y, _ = m.sep(m.obj)
    wr, wg, _ = m.sep(m.noise(m.obj, 2.3, detail=3.0, rough=0.6, color=True))
    xs = m.add(x, m.mad(wr, 0.024, -0.012))
    ys = m.add(y, m.mad(wg, 0.024, -0.012))
    ex = m.math("ABSOLUTE", m.sub(m.math("FRACT", xs), 0.5))
    ey = m.math("ABSOLUTE", m.sub(m.math("FRACT", ys), 0.5))
    edge = m.sub(0.5, m.mx(ex, ey))                     # metres to the nearest joint line
    joint = m.inv(m.smooth(edge, 0.006, 0.020))
    chamfer = m.inv(m.smooth(edge, 0.0, 0.05))
    joint_wide = m.inv(m.smooth(edge, 0.0, 0.10))
    slab_id = m.comb(m.math("FLOOR", xs), m.math("FLOOR", ys), 0.0)
    rnd = m.white(slab_id)
    r1, r2, r3 = m.sep(rnd)

    # slab surface (the texture holds 3 x 3 slabs of 1 m)
    t = m.pbr("large_floor_tiles_02")
    # crack network: irregular paving pieces, shifted randomly per slab so cracks stop at the joints
    cvec = m.mapping(m.vmath("ADD", m.obj, m.vmath("SCALE", rnd, scale=7.3)), TILE_M[m.key]["stone_tiles_02"])
    cdisp = m.tex("stone_tiles_02", "Displacement", vec=cvec)
    cnor = m.tex("stone_tiles_02", "nor_gl", vec=cvec)
    cracked = m.smooth(m.add(r1, crack_amt), 0.85, 1.15)        # per slab: 0 intact .. 1 broken
    crack = m.mul(m.smooth(cdisp, 0.36, 0.24), cracked)
    grooves = m.mx(joint, crack)

    # standing water: low-frequency noise, helped by grooves and by slabs that sit lower
    low = m.noise(m.obj, 0.28, detail=3.0, rough=0.5)
    field = m.add(m.add(low, m.mul(grooves, 0.12)), m.add(m.mad(r3, 0.24, -0.12), m.mad(pud_amt, 0.6, -0.3)))
    field = m.add(field, m.mad(m.noise(m.obj, 1.7, detail=3.0, rough=0.6), 0.16, -0.08))
    puddle = m.mul(m.smooth(field, 0.50, 0.60), wet)

    # colour: near-black basalt, a little cooler than neutral
    macro = m.noise(m.obj, 0.45, detail=2.0, rough=0.5)
    gain = m.mul(m.mad(r2, 0.5, 0.75), m.mad(macro, 0.5, 0.75))
    col = m.cscale(m.hsv(t.color, sat=0.5), (0.27, 0.275, 0.30))
    col = m.cscale(col, gain)
    col = m.cscale(col, m.lerp(m.mul(t.ao, 1.0), 0.6, 1.0))
    col = m.cscale(col, m.lerp(grooves, 1.0, 0.22))
    moss = m.mul(m.mul(joint_wide, m.smooth(m.noise(m.obj, 1.9, detail=3.0, rough=0.6), 0.47, 0.62)), m.mul(moss_amt, 1.5), clamp=True)
    col = m.mix(moss, col, m.mix(m.mid, (0.014, 0.026, 0.005), (0.05, 0.065, 0.012)))
    col = m.cscale(col, m.lerp(wet, 1.6, 1.0))

    # roughness: damp stone 0.2-0.45, dirt in the grooves, 0.02-0.08 in the puddles
    sheen = m.noise(m.obj, 3.1, detail=4.0, rough=0.65)                     # patchy film of water on the damp stone
    damp = m.add(m.remap(t.rough, 0.72, 0.92, 0.20, 0.36), m.smooth(sheen, 0.35, 0.7, -0.04, 0.09))
    rough = m.lerp(wet, m.remap(t.rough, 0.72, 0.92, 0.6, 0.9), damp)
    rough = m.lerp(grooves, rough, 0.65)
    rough = m.lerp(moss, rough, 0.9)
    fine = m.noise(m.obj, 9.0, detail=2.0, rough=0.5)
    rough = m.lerp(puddle, rough, m.mad(fine, 0.06, 0.02))

    # normals: slab relief + paving pieces + a random lean per slab; flattened under water
    tilt = m.vmath("SCALE", m.vmath("SUBTRACT", m.comb(r2, r3, 0.5), (0.5, 0.5, 0.5)), scale=tilt_amt)
    n1 = m.vmath("SUBTRACT", t.nor, (0.5, 0.5, 0.5))
    n2 = m.vmath("SCALE", m.vmath("SUBTRACT", cnor, (0.5, 0.5, 0.5)), scale=m.mul(cracked, 0.45))
    ncol = m.vmath("ADD", m.vmath("ADD", m.vmath("ADD", n1, n2), tilt), (0.5, 0.5, 0.5))
    base_n = m.box_normal(ncol, m.mad(puddle, -0.85, 1.0))
    height = m.add(m.add(m.mul(joint, -0.010), m.mul(crack, -0.005)), m.mul(m.mul(chamfer, chamfer), -0.004))
    base_n = m.bump(height, base_n, strength=m.mad(puddle, -0.7, 1.0))
    coat_n = m.box_normal(ncol, m.mul(m.inv(puddle), 0.45))

    coat = m.mul(wet, m.mul(m.lerp(puddle, 0.55, 1.0), m.lerp(m.mul(moss, m.inv(puddle)), 1.0, 0.2)))
    m.surface(color=col, rough=rough, normal=base_n, coat=coat, coat_rough=m.lerp(puddle, 0.09, 0.02),
              coat_ior=1.33, coat_normal=coat_n)


def _stone_mossy(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("mossy_rock")
    lum = m.lum(t.color)
    grain = m.noise(m.obj, 170.0, detail=1.0, rough=0.5)
    v = m.mul(m.remap(lum, 0.03, 0.35, 0.022, 0.13), m.mad(grain, 0.5, 0.75))
    base = m.cscale((0.93, 0.96, 1.0), v)
    base = m.cscale(base, m.lerp(0.8, 1.0, t.ao))
    base = m.cscale(base, m.lerp(wet, 1.0, 0.62))
    _, g, b = m.sep(t.color)
    lichen = m.smooth(m.sub(g, b), 0.02, 0.10)
    crev = m.mx(m.inv(m.remap(t.ao, 0.6, 0.95)), m.mul(lichen, 0.8))
    rough = m.lerp(wet, t.rough, m.remap(t.rough, 0.65, 0.92, 0.30, 0.58))
    col, rough, h, cover = _weather(m, base, rough, crevice=crev, shade=m.mad(lum, 2.0, 0.7))
    n = m.box_normal(t.nor, 1.0)
    n = m.bump(m.add(h, m.mul(grain, 0.0003)), n)
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, 0.6), m.inv(cover)), coat_rough=0.16, coat_ior=1.33)


def _stone_block(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("japanese_stone_wall")
    base = m.cscale(m.hsv(t.color, sat=0.35), (0.34, 0.35, 0.38))
    base = m.cscale(base, m.lerp(0.75, 1.0, t.ao))
    base = m.cscale(base, m.lerp(wet, 1.0, 0.66))
    crev = m.inv(m.remap(t.ao, 0.45, 0.92))
    rough = m.lerp(wet, t.rough, m.remap(t.rough, 0.7, 0.88, 0.32, 0.6))
    col, rough, h, cover = _weather(m, base, rough, crevice=crev, moss_gain=0.9, snow_gain=0.9)
    n = m.bump(h, m.box_normal(t.nor, 1.0))
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, 0.5), m.inv(cover)), coat_rough=0.18, coat_ior=1.33)


def _ground_dark(m):
    wet = m.param("Wetness", WETNESS)
    pud_amt = m.param("Puddle Amount", PUDDLE_AMOUNT)
    t = m.pbr("mossy_rock")
    lum = m.lum(t.color)
    macro = m.noise(m.obj, 0.11, detail=4.0, rough=0.6)
    patch = m.noise(m.obj, 0.55, detail=3.0, rough=0.6)
    _, g, b = m.sep(t.color)
    mossy = m.smooth(m.add(m.mul(m.smooth(m.sub(g, b), 0.02, 0.10), 0.5), patch), 0.55, 0.85)
    mossy = m.mul(mossy, m.mul(m.param("Moss Amount", MOSS_AMOUNT), 1.6), clamp=True)
    earth = m.mix(macro, (0.020, 0.015, 0.011), (0.007, 0.006, 0.006))
    col = m.mix(mossy, earth, (0.014, 0.027, 0.006))
    col = m.cscale(col, m.mad(lum, 3.0, 0.55))
    col = m.cscale(col, m.lerp(wet, 1.5, 1.0))
    puddle = m.mul(m.smooth(m.add(m.noise(m.obj, 0.2, detail=3.0, rough=0.5), m.mad(pud_amt, 0.5, -0.25)), 0.56, 0.66), wet)
    rough = m.lerp(puddle, m.lerp(wet, 0.95, m.remap(t.rough, 0.65, 0.92, 0.5, 0.85)), 0.06)
    col, rough, h, cover = _weather(m, col, rough, moss_gain=0.0, snow_gain=0.8)
    n = m.bump(h, m.box_normal(t.nor, m.mad(puddle, -0.6, 0.8)))
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, m.lerp(puddle, 0.25, 1.0)), m.inv(cover)),
              coat_rough=m.lerp(puddle, 0.2, 0.03), coat_ior=1.33)


def _plaster(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("white_plaster_rough_01")
    lum = m.lum(t.color)
    x, y, z = m.sep(m.obj)
    streak = m.noise(m.comb(m.mul(x, 3.0), m.mul(y, 3.0), m.mul(z, 0.35)), 1.0, detail=3.0, rough=0.6)
    v = m.mul(m.remap(lum, 0.07, 0.30, 0.20, 0.50), m.mad(streak, 0.5, 0.72))
    col = m.cscale((1.0, 0.955, 0.87), v)
    col = m.cscale(col, m.lerp(m.mul(m.big, wet), 1.0, 0.72))
    rough = m.lerp(wet, t.rough, m.remap(t.rough, 0.6, 0.96, 0.55, 0.85))
    col, rough, h, cover = _weather(m, col, rough, crevice=m.inv(m.remap(t.ao, 0.8, 0.95)), moss_gain=0.45, snow_gain=0.7)
    n = m.bump(h, m.box_normal(t.nor, 0.8))
    m.surface(color=col, rough=rough, normal=n)


# ----------------------------------------------------------------------------------------------- wood, roof, bark
def _wood_red(m):
    wet = m.param("Wetness", WETNESS)
    wear = m.param("Paint Wear", PAINT_WEAR)
    t = m.pbr("wood_peeling_paint_weathered")
    lum = m.lum(t.color)
    bare = m.smooth(lum, 0.055, 0.11)                      # the photo's bare-wood flakes
    zone = m.smooth(m.add(m.big, m.mad(wear, 0.6, -0.3)), 0.38, 0.62)
    specks = m.smooth(m.add(m.noise(m.obj, 7.0, detail=4.0, rough=0.7), m.mad(wear, 0.2, -0.1)), 0.64, 0.70)
    chip = m.mul(m.mx(m.mul(bare, zone), specks), m.mul(wear, 4.0), clamp=True)
    fine = m.noise(m.obj, 16.0, detail=2.0, rough=0.5)
    lacquer = m.mix(m.mid, (0.20, 0.009, 0.010), (0.40, 0.022, 0.016))
    lacquer = m.cscale(lacquer, m.mad(fine, 0.5, 0.75))
    wood = m.cscale((0.040, 0.031, 0.027), m.mad(lum, 5.0, 0.55))
    col = m.mix(chip, lacquer, wood)
    z = m.sep(m.obj)[2]
    col = m.cscale(col, m.smooth(m.add(z, m.mul(fine, 0.3)), 0.0, 0.7, 0.5, 1.0))   # splash-zone grime near the ground
    col = m.cscale(col, m.lerp(0.6, 1.0, t.ao))
    rough = m.lerp(chip, m.lerp(wet, 0.5, m.mad(fine, 0.2, 0.22)), 0.75)
    col, rough, h, cover = _weather(m, col, rough, crevice=chip, moss_gain=0.3, snow_gain=1.0)
    n = m.box_normal(t.nor, 0.8)
    n = m.bump(m.add(h, m.mul(chip, -0.0007)), n)
    coat = m.mul(m.mul(m.lerp(wet, 0.25, 0.6), m.inv(chip)), m.inv(cover))
    m.surface(color=col, rough=rough, normal=n, coat=coat, coat_rough=0.14, coat_ior=1.45)


def _wood_dark(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("weathered_planks")
    col = m.cscale(m.hsv(t.color, sat=0.6), (0.52, 0.52, 0.56))
    col = m.cscale(col, m.lerp(0.5, 1.0, t.ao))
    col = m.cscale(col, m.mad(m.big, 0.5, 0.75))
    col = m.cscale(col, m.lerp(wet, 1.0, 0.7))
    rough = m.lerp(wet, 0.78, m.mad(m.mid, 0.25, 0.38))
    col, rough, h, cover = _weather(m, col, rough, crevice=m.inv(m.remap(t.ao, 0.7, 0.95)), moss_gain=0.35, snow_gain=0.9)
    n = m.bump(h, m.box_normal(t.nor, 1.0))
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, 0.3), m.inv(cover)), coat_rough=0.2, coat_ior=1.33)


def _roof_tile(m):
    """Dark ceramic tiles. Not box-projected: tile rows must run down the slope, so the lookup uses
    u = along the eave, v = up the slope, chosen from the object-space normal (works on all four sides of a hip roof)."""
    wet = m.param("Wetness", WETNESS)
    pattern = m.param("Tile Pattern", TILE_PATTERN)
    size = TILE_M[m.key]["roof_tiles_14"]
    nx, ny, _ = m.sep(m.nobj)
    along_x = m.math("GREATER_THAN", m.math("ABSOLUTE", nx), m.mul(m.math("ABSOLUTE", ny), 1.8))
    sx = m.mad(m.math("GREATER_THAN", nx, 0.0), 2.0, -1.0)
    sy = m.mad(m.math("GREATER_THAN", ny, 0.0), 2.0, -1.0)
    x, y, z = m.sep(m.obj)
    u = m.lerp(along_x, x, y)
    v = m.lerp(along_x, m.sub(z, m.mul(sy, y)), m.sub(z, m.mul(sx, x)))
    uv = m.vmath("SCALE", m.comb(u, m.math("DIVIDE", v, 1.2), 0.0), scale=1.0 / size)
    col_t = m.image("roof_tiles_14", "Diffuse", uv, projection="FLAT")
    nor_t = m.image("roof_tiles_14", "nor_gl", uv, projection="FLAT")
    ao, rough_t, _ = m.sep(m.image("roof_tiles_14", "arm", uv, projection="FLAT"))
    # tangent frame of that lookup
    tan0 = m.vmix(along_x, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    bit0 = m.comb(m.mul(along_x, m.mul(sx, -1.0)), m.mul(m.inv(along_x), m.mul(sy, -1.0)), 1.0)
    nrm = m.nobj
    tan = m.vmath("NORMALIZE", m.vmath("SUBTRACT", tan0, m.vmath("SCALE", nrm, scale=m.vmath("DOT_PRODUCT", nrm, tan0))))
    bit = m.vmath("NORMALIZE", m.vmath("SUBTRACT", bit0, m.vmath("SCALE", nrm, scale=m.vmath("DOT_PRODUCT", nrm, bit0))))
    cr, cg, _ = m.sep(nor_t)
    pert = m.vmath("ADD", m.vmath("SCALE", tan, scale=m.mad(cr, 2.0, -1.0)), m.vmath("SCALE", bit, scale=m.mad(cg, 2.0, -1.0)))
    nn = m.vmath("NORMALIZE", m.vmath("ADD", nrm, m.vmath("SCALE", pert, scale=m.mul(pattern, 1.0))))
    vt = m.node("ShaderNodeVectorTransform", vector_type="NORMAL", convert_from="OBJECT", convert_to="WORLD")
    m.put(vt.inputs["Vector"], nn)

    lum = m.lum(col_t)
    island = m.geo.outputs["Random Per Island"]               # modelled tiles are separate islands: vary them one by one
    stain = m.noise(m.obj, 3.3, detail=4.0, rough=0.65)
    v_col = m.mul(m.lerp(pattern, 0.035, m.remap(lum, 0.01, 0.16, 0.012, 0.075)), m.mad(m.big, 0.5, 0.75))
    v_col = m.mul(v_col, m.mul(m.mad(island, 0.7, 0.65), m.mad(stain, 0.8, 0.6)))
    col = m.cscale((0.90, 0.95, 1.05), v_col)
    valley = m.mul(m.inv(m.remap(ao, 0.6, 0.95)), pattern)
    col = m.cscale(col, m.lerp(valley, 1.0, 0.45))
    col = m.cscale(col, m.lerp(wet, 1.3, 1.0))
    rough = m.lerp(wet, 0.6, m.add(m.mad(m.mid, 0.2, 0.2), m.mul(island, 0.12)))
    rough = m.lerp(valley, rough, 0.6)
    col, rough, h, cover = _weather(m, col, rough, crevice=valley, moss_gain=0.55, snow_gain=1.1, snow_bias=m.mul(valley, 0.25))
    n = m.bump(h, vt.outputs[0])
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, 0.6), m.inv(cover)), coat_rough=0.12, coat_ior=1.4)


def _bark(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("sakura_bark")
    col = m.cscale(m.hsv(t.color, sat=0.55), (0.30, 0.27, 0.27))
    col = m.cscale(col, m.lerp(0.5, 1.0, t.ao))
    col = m.cscale(col, m.lerp(wet, 1.0, 0.68))
    rough = m.lerp(wet, t.rough, m.remap(t.rough, 0.45, 0.8, 0.35, 0.65))
    col, rough, h, cover = _weather(m, col, rough, crevice=m.inv(m.remap(t.ao, 0.75, 0.95)), moss_gain=0.6, snow_gain=1.0)
    n = m.bump(h, m.box_normal(t.nor, 1.3))
    m.surface(color=col, rough=rough, normal=n, coat=m.mul(m.mul(wet, 0.4), m.inv(cover)), coat_rough=0.2, coat_ior=1.33)


# ----------------------------------------------------------------------------------------------- metal, rope, pine
def _metal_dark(m):
    wet = m.param("Wetness", WETNESS)
    n1 = m.noise(m.obj, 9.0, detail=4.0, rough=0.65)
    fine = m.noise(m.obj, 90.0, detail=2.0, rough=0.5)
    rust = m.mul(m.smooth(m.add(m.mul(n1, 0.5), m.mul(m.big, 0.8)), 0.70, 0.88), 0.85)
    col = m.mix(rust, m.cscale((0.045, 0.045, 0.052), m.mad(fine, 0.6, 0.7)), m.mix(fine, (0.030, 0.012, 0.007), (0.065, 0.025, 0.011)))
    rough = m.lerp(rust, m.mad(n1, 0.3, 0.25), 0.8)
    n = m.bump(m.add(m.mul(fine, 0.0003), m.mul(rust, 0.0006)))
    m.surface(color=col, rough=rough, metallic=m.inv(rust), normal=n, coat=m.mul(wet, 0.3), coat_rough=0.1, coat_ior=1.33)


def _gold(m):
    n1 = m.noise(m.obj, 5.0, detail=4.0, rough=0.6)
    fine = m.noise(m.obj, 110.0, detail=2.0, rough=0.5)
    tarnish = m.smooth(m.add(m.mul(n1, 0.6), m.mul(m.big, 0.6)), 0.42, 0.85)
    col = m.mix(tarnish, (0.78, 0.50, 0.17), (0.20, 0.125, 0.045))
    col = m.cscale(col, m.mad(fine, 0.4, 0.8))
    rough = m.lerp(tarnish, m.mad(fine, 0.15, 0.24), 0.6)
    m.surface(color=col, rough=rough, metallic=m.lerp(tarnish, 1.0, 0.7), normal=m.bump(m.mul(fine, 0.0003)))


def _rope(m):
    wet = m.param("Wetness", WETNESS)
    x, y, z = m.sep(m.obj)
    # straw fibres: fine stripes along a diagonal, broken by noise
    wave = m.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL", wave_profile="SIN")
    m.put(wave.inputs["Vector"], m.obj)
    m.put(wave.inputs["Scale"], 55.0)
    m.put(wave.inputs["Distortion"], 2.5)
    m.put(wave.inputs["Detail"], 2.0)
    m.put(wave.inputs["Detail Scale"], 3.0)
    fibre = wave.outputs[1]
    fine = m.noise(m.obj, 60.0, detail=3.0, rough=0.6)
    col = m.mix(fibre, (0.16, 0.115, 0.05), (0.42, 0.32, 0.15))
    col = m.cscale(col, m.mad(m.mid, 0.6, 0.65))
    col = m.cscale(col, m.lerp(wet, 1.0, 0.6))
    col, rough, h, cover = _weather(m, col, 0.85, moss_gain=0.3, snow_gain=0.9)
    n = m.bump(m.add(h, m.add(m.mul(fibre, 0.0012), m.mul(fine, 0.0006))))
    m.surface(color=col, rough=rough, normal=n, sheen=0.25, sheen_rough=0.5)


def _pine_dark(m):
    fine = m.noise(m.obj, 14.0, detail=3.0, rough=0.7)
    col = m.mix(m.mid, (0.006, 0.013, 0.009), (0.020, 0.040, 0.020))
    col = m.cscale(col, m.mad(fine, 0.8, 0.6))
    col, rough, h, cover = _weather(m, col, 0.7, moss_gain=0.0, snow_gain=0.9)
    m.surface(color=col, rough=rough, normal=m.bump(m.add(h, m.mul(fine, 0.004))), sheen=0.2, sheen_rough=0.5)


# ----------------------------------------------------------------------------------------------- emissive
def _paper_lantern(m):
    strength = m.param("Emission Strength", EMISSION[m.key])
    dx, dz, radius = _crest_coords(m)
    ny = m.sep(m.nobj)[1]
    crest = m.mul(_crest_mask(m, dx, dz, radius), m.smooth(m.math("ABSOLUTE", ny), 0.25, 0.5))
    z = m.sep(m.obj)[2]
    rib = m.smooth(m.math("ABSOLUTE", m.sub(m.math("FRACT", m.math("DIVIDE", z, 0.03)), 0.5)), 0.40, 0.47)   # a rib every 3 cm
    gz = m.sep(m.gen)[2]
    ends = m.smooth(m.math("ABSOLUTE", m.mad(gz, 2.0, -1.0)), 0.35, 1.0)        # darker towards the caps
    fibre = m.noise(m.obj, 45.0, detail=3.0, rough=0.6)
    facing = m.node("ShaderNodeLayerWeight")
    facing.inputs["Blend"].default_value = 0.35
    hot = m.inv(facing.outputs["Facing"])                                      # 1 where the flame is seen straight on
    core = m.mul(m.math("POWER", m.smooth(hot, 0.6, 1.0), 2.0), m.inv(ends))   # the flame seen through the paper
    glow = m.mul(m.mul(m.lerp(ends, 1.0, 0.4), m.lerp(rib, 1.0, 0.55)), m.mul(m.mad(fibre, 0.3, 0.85), m.mad(core, 0.5, 0.13)))
    glow = m.mul(glow, m.lerp(crest, 1.0, 0.01))
    emit = m.mix(core, (1.0, 0.03, 0.012), (1.0, 0.13, 0.03))
    paper = m.mix(crest, m.cscale((0.55, 0.035, 0.025), m.mad(fibre, 0.3, 0.85)), (0.006, 0.005, 0.005))
    paper = m.cscale(paper, m.lerp(rib, 1.0, 0.6))
    n = m.bump(m.add(m.mul(rib, 0.0012), m.mul(fibre, 0.0002)))
    m.surface(color=paper, rough=0.62, normal=n, emission=emit, strength=m.mul(strength, glow), sheen=0.15)


def _lantern_glow(m):
    """Fire window of a stone lantern: deep red pane with a hot red-orange spot in front of the flame.
    The flame position is read from the object's light_socket custom property (local point); without it the spot
    follows the view direction."""
    strength = m.param("Emission Strength", EMISSION[m.key])
    facing = m.node("ShaderNodeLayerWeight")
    facing.inputs["Blend"].default_value = 0.3
    hot = m.inv(facing.outputs["Facing"])
    flame = m.noise(m.obj, 16.0, detail=3.0, rough=0.6)
    sock = m.attr("light_socket")
    to_p = m.vmath("NORMALIZE", m.vmath("SUBTRACT", m.obj, sock.outputs["Vector"]))
    aligned = m.math("ABSOLUTE", m.vmath("DOT_PRODUCT", to_p, m.nobj))
    spot = m.lerp(sock.outputs["Alpha"], m.smooth(hot, 0.8, 1.0), m.smooth(aligned, 0.88, 0.995))
    core = m.mul(spot, m.mad(flame, 0.6, 0.7), clamp=True)
    emit = m.mix(core, (1.0, 0.03, 0.012), (1.0, 0.24, 0.035))
    glow = m.mul(m.mad(core, 1.1, 0.10), m.mad(flame, 0.5, 0.75))
    m.surface(color=(0.25, 0.03, 0.02), rough=0.5, emission=emit, strength=m.mul(strength, glow))


def _window_glow(m):
    strength = m.param("Emission Strength", EMISSION[m.key])
    lamps = m.noise(m.obj, 0.7, detail=2.0, rough=0.5)                          # uneven lamps behind the paper
    fibre = m.noise(m.obj, 30.0, detail=3.0, rough=0.6)
    glow = m.mul(m.smooth(lamps, 0.3, 0.75, 0.22, 1.0), m.mad(fibre, 0.3, 0.85))
    emit = m.mix(lamps, (1.0, 0.035, 0.015), (1.0, 0.11, 0.03))
    m.surface(color=(0.30, 0.07, 0.04), rough=0.7, emission=emit, strength=m.mul(strength, glow))


def _moon(m):
    strength = m.param("Emission Strength", EMISSION[m.key])
    d = m.vmath("NORMALIZE", m.obj)                                            # any sphere radius works
    maria = m.smooth(m.noise(d, 1.5, detail=5.0, rough=0.6, distortion=0.6), 0.47, 0.62)
    mottling = m.noise(d, 7.0, detail=6.0, rough=0.75)
    crater = m.smooth(m.voronoi(d, 11.0, feature="F1"), 0.0, 0.28)             # dark crater floors, lighter rims
    rays = m.smooth(m.noise(d, 3.5, detail=6.0, rough=0.8), 0.6, 0.8)
    v = m.lerp(maria, 1.0, 0.33)
    v = m.mul(v, m.mad(mottling, 1.1, 0.42))
    v = m.mul(v, m.lerp(crater, 0.62, 1.0))
    v = m.mul(v, m.mad(rays, 0.35, 1.0))
    facing = m.node("ShaderNodeLayerWeight")
    facing.inputs["Blend"].default_value = 0.5
    v = m.mul(v, m.lerp(facing.outputs["Facing"], 1.0, 0.7))                   # slight limb darkening
    emit = m.mix(maria, (1.0, 0.10, 0.05), (1.0, 0.025, 0.02))
    m.surface(color=(0.0, 0.0, 0.0), rough=1.0, spec=0.0, emission=emit, strength=m.mul(strength, v))


# ----------------------------------------------------------------------------------------------- cloth, plants, snow
def _banner_red(m):
    wet = m.param("Wetness", WETNESS)
    t = m.pbr("rough_linen")
    weave = m.remap(m.lum(t.color), 0.25, 0.52, 0.6, 1.15)
    fade = m.noise(m.obj, 1.6, detail=4.0, rough=0.65)
    red = m.mix(fade, (0.17, 0.008, 0.012), (0.34, 0.022, 0.022))
    dx, dz, radius = _crest_coords(m)
    crest = m.mul(_crest_mask(m, dx, dz, radius), m.smooth(m.noise(m.obj, 11.0, detail=3.0, rough=0.7), 0.25, 0.5, 0.45, 1.0))
    col = m.mix(crest, red, (0.42, 0.33, 0.22))
    gz = m.sep(m.gen)[2]
    hem = m.mul(m.smooth(m.add(gz, m.mad(m.mid, 0.2, -0.1)), 0.50, 0.12), 0.8)   # dirt soaking up from the hem
    col = m.mix(hem, col, (0.022, 0.012, 0.010))
    col = m.cscale(col, weave)
    col = m.cscale(col, m.lerp(wet, 1.0, 0.75))
    n = m.box_normal(t.nor, 0.7)
    m.surface(color=col, rough=m.lerp(wet, 0.9, 0.75), normal=n, sheen=0.3, sheen_rough=0.5, sheen_tint=(1.0, 0.5, 0.45))
    m.translucent(m.cscale(col, 1.3), 0.22)


def _petals(m, base_a, base_b, base_c):
    glow = m.param("Glow", BLOSSOM_GLOW)
    info = m.node("ShaderNodeObjectInfo")
    rnd = m.math("FRACT", m.add(m.geo.outputs["Random Per Island"], m.mul(info.outputs["Random"], 7.31)))
    col = m.mix(m.smooth(rnd, 0.0, 0.6), base_a, base_b)
    col = m.mix(m.smooth(rnd, 0.75, 1.0), col, base_c)
    col = m.cscale(col, m.mad(m.noise(m.obj, 3.0, detail=2.0), 0.3, 0.85))
    m.surface(color=col, rough=0.55, sheen=0.3, sheen_rough=0.4, emission=col, strength=glow)
    m.translucent(col, 0.35)


def _blossom(m):
    _petals(m, (0.80, 0.42, 0.52), (0.90, 0.62, 0.70), (0.93, 0.82, 0.85))


def _petal(m):
    _petals(m, (0.84, 0.48, 0.58), (0.92, 0.66, 0.73), (0.94, 0.84, 0.87))


def _snow(m):
    fine = m.noise(m.obj, 55.0, detail=3.0, rough=0.7)
    lump = m.noise(m.obj, 6.0, detail=3.0, rough=0.6)
    col = m.cscale((0.80, 0.84, 0.91), m.mad(lump, 0.25, 0.85))
    n = m.bump(m.add(m.mul(fine, 0.0015), m.mul(lump, 0.012)))
    m.surface(color=col, rough=m.mad(fine, 0.2, 0.45), normal=n, sheen=0.4, sheen_rough=0.35)


_BUILDERS = {
    "MAT_Floor_WetStone": _floor_wet_stone,
    "MAT_Stone_Mossy": _stone_mossy,
    "MAT_Stone_Block": _stone_block,
    "MAT_Wood_Red": _wood_red,
    "MAT_Wood_Dark": _wood_dark,
    "MAT_Roof_Tile": _roof_tile,
    "MAT_Plaster": _plaster,
    "MAT_Paper_Lantern": _paper_lantern,
    "MAT_Lantern_Glow": _lantern_glow,
    "MAT_Window_Glow": _window_glow,
    "MAT_Banner_Red": _banner_red,
    "MAT_Metal_Dark": _metal_dark,
    "MAT_Gold": _gold,
    "MAT_Rope": _rope,
    "MAT_Bark": _bark,
    "MAT_Blossom": _blossom,
    "MAT_Petal": _petal,
    "MAT_Snow": _snow,
    "MAT_Ground_Dark": _ground_dark,
    "MAT_Moon": _moon,
    "MAT_Pine_Dark": _pine_dark,
}

_VIEWPORT = {  # solid-view colours
    "MAT_Floor_WetStone": (0.035, 0.035, 0.04), "MAT_Stone_Mossy": (0.07, 0.075, 0.07), "MAT_Stone_Block": (0.09, 0.09, 0.095),
    "MAT_Wood_Red": (0.33, 0.03, 0.025), "MAT_Wood_Dark": (0.045, 0.03, 0.025), "MAT_Roof_Tile": (0.03, 0.032, 0.036),
    "MAT_Plaster": (0.42, 0.4, 0.37), "MAT_Paper_Lantern": (0.8, 0.06, 0.04), "MAT_Lantern_Glow": (1.0, 0.2, 0.05),
    "MAT_Window_Glow": (0.6, 0.12, 0.05), "MAT_Banner_Red": (0.3, 0.02, 0.02), "MAT_Metal_Dark": (0.03, 0.03, 0.035),
    "MAT_Gold": (0.7, 0.5, 0.2), "MAT_Rope": (0.45, 0.36, 0.2), "MAT_Bark": (0.05, 0.035, 0.03),
    "MAT_Blossom": (0.9, 0.55, 0.65), "MAT_Petal": (0.92, 0.62, 0.7), "MAT_Snow": (0.85, 0.87, 0.9),
    "MAT_Ground_Dark": (0.02, 0.022, 0.02), "MAT_Moon": (0.8, 0.05, 0.03), "MAT_Pine_Dark": (0.01, 0.018, 0.014),
}


# ----------------------------------------------------------------------------------------------- public API
def build(name):
    """Build the named material in the current file and return it (None for an unknown name)."""
    fn = _BUILDERS.get(name)
    if fn is None:
        return None
    m = _M(name)
    try:
        fn(m)
    except Exception:
        bpy.data.materials.remove(m.mat)
        raise
    mat = m.mat
    mat.diffuse_color = (*_VIEWPORT.get(name, (0.5, 0.5, 0.5)), 1.0)
    mat["pbr"] = True
    return mat


def params(mat):
    """{label: value} of the tunable Value nodes of a material."""
    if mat is None or mat.node_tree is None:
        return {}
    return {n.label: n.outputs[0].default_value for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeValue" and n.label}


def set_param(label, value, materials=None):
    """Set the Value node called `label` in the given materials (default: all). Returns how many were changed."""
    count = 0
    for mat in (materials if materials is not None else bpy.data.materials):
        if mat is None or mat.node_tree is None:
            continue
        node = mat.node_tree.nodes.get(label)
        if node is not None and node.bl_idname == "ShaderNodeValue":
            node.outputs[0].default_value = value
            count += 1
    return count
