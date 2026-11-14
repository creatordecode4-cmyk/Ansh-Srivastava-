"""Material library. Master materials carry the MAT_ prefix.

Look targets taken from refs/arena.png: dark wet stone, chipped red lacquer, dark timber,
light snow on up-facing surfaces, moss in the damp places, red emissive paper lanterns.

Textures are Poly Haven CC0 maps, box-projected in object space (no UV unwrap needed) with
bump taken from the height map, which stays correct under box projection.
"""
import math

import bpy

from . import polyhaven as ph

_cache = {}


class NT:
    """Small node-tree builder so material code reads as formulas instead of socket plumbing."""

    def __init__(self, tree, clear=False):
        self.t = tree
        if clear:
            for n in list(tree.nodes):
                tree.nodes.remove(n)

    def new(self, kind, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.t.links.new(a, b)

    def put(self, sock, v):
        """Connect or assign: v may be a socket, a number or a colour tuple."""
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif isinstance(v, (int, float)):
            sock.default_value = v if sock.type in ("VALUE", "INT") else (v, v, v, 1.0)[: len(sock.default_value)]
        else:
            v = tuple(v)
            if sock.type == "RGBA" and len(v) == 3:
                v = (*v, 1.0)
            sock.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.new("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if c is not None:
            self.put(n.inputs[2], c)
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.new("ShaderNodeMixRGB", blend_type=blend)
        self.put(n.inputs[0], fac)
        self.put(n.inputs[1], a)
        self.put(n.inputs[2], b)
        return n.outputs[0]

    def ramp(self, fac, stops, interp="LINEAR"):
        """stops: [(position, value or colour), ...]"""
        n = self.new("ShaderNodeValToRGB")
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for e, (pos, col) in zip(cr.elements, stops):
            e.position = pos
            e.color = (col, col, col, 1.0) if isinstance(col, (int, float)) else (*col[:3], 1.0)
        self.put(n.inputs[0], fac)
        return n.outputs[0]

    def map_range(self, v, a, b, c=0.0, d=1.0, smooth=True):
        n = self.new("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR")
        self.put(n.inputs[0], v)
        n.inputs[1].default_value, n.inputs[2].default_value = a, b
        n.inputs[3].default_value, n.inputs[4].default_value = c, d
        return n.outputs[0]

    def coords(self, kind="Object", scale=1.0, offset=(0, 0, 0), rand_offset=0.0):
        tc = self.new("ShaderNodeTexCoord")
        mp = self.new("ShaderNodeMapping")
        self.link(tc.outputs[kind], mp.inputs[0])
        s = scale if isinstance(scale, (tuple, list)) else (scale,) * 3
        mp.inputs["Scale"].default_value = s
        mp.inputs["Location"].default_value = offset
        if rand_offset:  # different placement per instance so repeated props don't look cloned
            oi = self.new("ShaderNodeObjectInfo")
            vm = self.new("ShaderNodeVectorMath", operation="SCALE")
            comb = self.new("ShaderNodeCombineXYZ")
            for i in range(3):
                self.link(oi.outputs["Random"], comb.inputs[i])
            self.link(comb.outputs[0], vm.inputs[0])
            vm.inputs["Scale"].default_value = rand_offset
            self.link(vm.outputs[0], mp.inputs["Location"])
        return mp.outputs[0]

    def image(self, path, vec, colorspace="sRGB", box=True, blend=0.25):
        im = bpy.data.images.load(path, check_existing=True)
        im.colorspace_settings.name = colorspace
        n = self.new("ShaderNodeTexImage", image=im)
        if box:
            n.projection = "BOX"
            n.projection_blend = blend
        self.link(vec, n.inputs[0])
        return n

    def noise(self, vec, scale=5.0, detail=4.0, rough=0.55, distortion=0.0, color=False):
        n = self.new("ShaderNodeTexNoise")
        if vec is not None:
            self.link(vec, n.inputs[0])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs[1 if color else 0]

    def voronoi(self, vec, scale=5.0, feature="F1", randomness=1.0, out=0):
        n = self.new("ShaderNodeTexVoronoi", feature=feature)
        if vec is not None:
            self.link(vec, n.inputs[0])
        n.inputs["Scale"].default_value = scale
        n.inputs["Randomness"].default_value = randomness
        return n.outputs[out]

    def world_normal_z(self):
        g = self.new("ShaderNodeNewGeometry")
        s = self.new("ShaderNodeSeparateXYZ")
        self.link(g.outputs["Normal"], s.inputs[0])
        return s.outputs[2]

    def world_pos(self):
        return self.new("ShaderNodeNewGeometry").outputs["Position"]

    def bump(self, height, strength=0.4, distance=0.02, normal=None):
        n = self.new("ShaderNodeBump")
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = distance
        self.put(n.inputs["Height"], height)
        if normal is not None:
            self.link(normal, n.inputs["Normal"])
        return n.outputs[0]

    def hsv(self, col, h=0.5, s=1.0, v=1.0):
        n = self.new("ShaderNodeHueSaturation")
        n.inputs["Hue"].default_value = h
        n.inputs["Saturation"].default_value = s
        n.inputs["Value"].default_value = v
        self.put(n.inputs["Color"], col)
        return n.outputs[0]


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = NT(m.node_tree)
    b = m.node_tree.nodes["Principled BSDF"]
    return m, nt, b


def get(name, builder, *a, **kw):
    """Build a master material once per .blend."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = builder(name, *a, **kw)
    return m


# Global look knobs (0..1) so the weathering stays consistent across props.
LOOK = {"wet": 0.85, "snow": 0.55, "moss": 0.5}


def surface(
    name,
    asset=None,
    size=1.0,
    tint=(1, 1, 1),
    value=1.0,
    sat=1.0,
    base=None,
    rough=1.0,
    rough_min=0.25,
    bump=0.5,
    bump_dist=0.02,
    wet=None,
    snow=None,
    moss=None,
    res="2k",
    rand_offset=0.0,
    extra=None,
    metallic=0.0,
):
    """Weathered PBR surface: texture -> tint -> moss in damp spots -> wet film -> snow on top.

    extra(nt, bsdf, state) may edit the colour before weathering (e.g. paint over wood).
    """
    wet = LOOK["wet"] if wet is None else wet
    snow = LOOK["snow"] if snow is None else snow
    moss = LOOK["moss"] if moss is None else moss
    m, nt, b = _new(name)
    vec = nt.coords("Object", 1.0 / size, rand_offset=rand_offset)
    state = {"vec": vec}
    if asset:
        maps = ph.texture(asset, res, maps=("Diffuse", "Rough", "Displacement", "Mask"))
        col = nt.image(maps["Diffuse"], vec).outputs[0]
        rgh = nt.image(maps["Rough"], vec, "Non-Color").outputs[0]
        hgt = nt.image(maps["Displacement"], vec, "Non-Color").outputs[0] if "Displacement" in maps else None
        state["maps"] = maps
    else:
        col, rgh, hgt = base or (0.5, 0.5, 0.5), 0.6, None
    if isinstance(col, bpy.types.NodeSocket):
        col = nt.hsv(col, 0.5, sat, value)
        col = nt.mix(1.0, col, (*tint, 1.0), "MULTIPLY")
    state.update(col=col, rough=rgh, height=hgt)
    if extra:
        extra(nt, b, state)
        col, rgh, hgt = state["col"], state["rough"], state["height"]

    wpos = nt.world_pos()
    nz = nt.world_normal_z()
    big = nt.noise(wpos, 0.35, 5.0, 0.6)  # metre-scale breakup shared by all layers
    fine = nt.noise(wpos, 9.0, 4.0, 0.6)

    # moss: prefers up-facing, sheltered, low-frequency patches
    if moss > 0:
        mcol = nt.mix(nt.noise(wpos, 40.0, 3.0, 0.7), (0.035, 0.07, 0.012, 1), (0.10, 0.14, 0.03, 1))
        mmask = nt.math("MULTIPLY", nt.map_range(big, 0.62 - 0.22 * moss, 0.72 - 0.12 * moss), nt.map_range(nz, -0.2, 0.6))
        mmask = nt.math("MULTIPLY", mmask, nt.map_range(fine, 0.35, 0.6))
        col = nt.mix(mmask, col, mcol)
        rgh = nt.mix(mmask, rgh, 0.85)
        state["moss_mask"] = mmask

    rgh = nt.math("MAXIMUM", nt.math("MULTIPLY", rgh, rough), rough_min)

    # wet film: darker, saturated base under a smooth clear coat
    if wet > 0:
        wmask = nt.map_range(nt.noise(wpos, 0.8, 3.0, 0.5), 0.25, 0.7, 0.55 * wet, wet)
        col = nt.mix(nt.math("MULTIPLY", wmask, 0.45), col, (0, 0, 0, 1))
        nt.put(b.inputs["Coat Weight"], wmask)
        b.inputs["Coat Roughness"].default_value = 0.06
        b.inputs["Coat IOR"].default_value = 1.33
        rgh = nt.math("MULTIPLY", rgh, nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", wmask, 0.45)))

    normal = nt.bump(hgt, bump, bump_dist) if hgt is not None else None

    # snow settles on up-facing faces, broken up so it reads as a light dusting
    if snow > 0:
        thr = 0.92 - 0.5 * snow
        smask = nt.map_range(nt.math("ADD", nz, nt.math("MULTIPLY", nt.math("SUBTRACT", big, 0.5), 0.5)), thr, thr + 0.18)
        smask = nt.math("MULTIPLY", smask, nt.map_range(fine, 0.25, 0.55, 0.35, 1.0))
        col = nt.mix(smask, col, (0.78, 0.80, 0.84, 1))
        rgh = nt.mix(smask, rgh, 0.55)
        if wet > 0:
            nt.put(b.inputs["Coat Weight"], nt.math("MULTIPLY", wmask, nt.math("SUBTRACT", 1.0, smask)))
        sn = nt.bump(nt.noise(wpos, 60.0, 3.0, 0.7), 0.25, 0.01, normal)
        state["snow_mask"] = smask
        normal = sn

    nt.put(b.inputs["Base Color"], col)
    nt.put(b.inputs["Roughness"], rgh)
    b.inputs["Metallic"].default_value = metallic
    if normal is not None:
        nt.link(normal, b.inputs["Normal"])
    return m


# ----------------------------------------------------------------------------- stone
def stone_slab():
    return get("MAT_Stone_Slab", surface, "dark_rock_02", size=1.6, tint=(0.78, 0.82, 0.92), value=0.55, sat=0.35,
               rough=0.9, rough_min=0.18, bump=0.9, bump_dist=0.012, wet=1.0, snow=0.12, moss=0.35, rand_offset=7.0)


def stone_lantern():
    return get("MAT_Stone_Lantern", surface, "lichen_rock", size=1.3, tint=(0.8, 0.84, 0.9), value=0.6, sat=0.3,
               rough=1.0, rough_min=0.3, bump=1.0, bump_dist=0.03, moss=0.85, rand_offset=3.0)


def stone_block():
    return get("MAT_Stone_Block", surface, "japanese_stone_wall", size=2.2, tint=(0.75, 0.78, 0.86), value=0.42, sat=0.3,
               rough=1.0, rough_min=0.3, bump=1.0, bump_dist=0.03, moss=0.6)


def stone_rock():
    return get("MAT_Stone_Rock", surface, "dark_rock", size=1.2, tint=(0.85, 0.88, 0.95), value=0.9, sat=0.4,
               rough=1.0, rough_min=0.28, bump=1.0, bump_dist=0.03, moss=0.7, rand_offset=5.0)


def ground_dirt():
    return get("MAT_Ground_Dirt", surface, None, base=(0.018, 0.016, 0.014), rough=1.0, rough_min=0.5, wet=0.9, snow=0.25, moss=0.9)


# ----------------------------------------------------------------------------- wood / lacquer
def _paint_over_wood(paint, worn=0.55):
    def extra(nt, b, st):
        mask = nt.image(st["maps"]["Mask"], st["vec"], "Non-Color").outputs[0]
        chips = nt.map_range(nt.noise(nt.world_pos(), 2.2, 6.0, 0.7), 0.42 - 0.2 * worn, 0.62)  # larger bare patches
        keep = nt.math("MULTIPLY", mask, nt.math("SUBTRACT", 1.0, nt.math("MULTIPLY", chips, 0.8)))
        wood = nt.mix(1.0, st["col"], (0.32, 0.26, 0.22, 1), "MULTIPLY")
        st["col"] = nt.mix(keep, wood, (*paint, 1.0))
        st["rough"] = nt.mix(keep, st["rough"], 0.38)

    return extra


def red_lacquer():
    return get("MAT_Wood_RedLacquer", surface, "wood_peeling_paint_weathered", size=1.4, value=0.8, sat=0.8,
               rough=1.0, rough_min=0.22, bump=0.8, bump_dist=0.01, moss=0.15, extra=_paint_over_wood((0.33, 0.012, 0.012)))


def black_lacquer():
    return get("MAT_Wood_BlackLacquer", surface, "wood_peeling_paint_weathered", size=1.4, value=0.7, sat=0.6,
               rough=1.0, rough_min=0.2, bump=0.7, bump_dist=0.01, moss=0.25, extra=_paint_over_wood((0.012, 0.012, 0.014), 0.3))


def dark_wood():
    return get("MAT_Wood_Dark", surface, "weathered_planks", size=1.8, tint=(0.75, 0.55, 0.5), value=0.5, sat=0.8,
               rough=1.0, rough_min=0.3, bump=0.8, bump_dist=0.012, moss=0.2, snow=0.35)


def red_wood():
    return get("MAT_Wood_RedStain", surface, "weathered_planks", size=1.8, tint=(0.95, 0.22, 0.18), value=0.75, sat=1.0,
               rough=1.0, rough_min=0.28, bump=0.8, bump_dist=0.012, moss=0.15, snow=0.35)


def deck_wood():
    return get("MAT_Wood_Deck", surface, "dark_wooden_planks", size=2.0, tint=(0.8, 0.62, 0.55), value=0.55, sat=0.8,
               rough=0.9, rough_min=0.2, bump=0.8, bump_dist=0.012, wet=1.0, moss=0.2, snow=0.3)


def bark():
    return get("MAT_Bark_Sakura", surface, "sakura_bark", size=0.9, value=0.45, sat=0.7, rough=1.0, rough_min=0.4,
               bump=1.0, bump_dist=0.03, moss=0.45, snow=0.4, wet=0.6)


def roof_tile():
    return get("MAT_Roof_Tile", surface, None, base=(0.022, 0.026, 0.032), rough=1.0, rough_min=0.22, wet=0.9, snow=0.75, moss=0.55)


def rope():
    return get("MAT_Rope_Straw", surface, None, base=(0.30, 0.22, 0.11), rough=1.0, rough_min=0.7, wet=0.3, snow=0.4, moss=0.0)


def iron():
    return get("MAT_Metal_Iron", surface, None, base=(0.02, 0.02, 0.022), rough=1.0, rough_min=0.35, wet=0.6, snow=0.3, moss=0.0, metallic=1.0)


# ----------------------------------------------------------------------------- emissive / special
def emission(name, color, strength):
    def build(name):
        m, nt, b = _new(name)
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = strength
        b.inputs["Roughness"].default_value = 0.6
        return m

    return get(name, build)


def clay():
    def build(name):
        m, nt, b = _new(name)
        b.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
        b.inputs["Roughness"].default_value = 0.75
        return m

    return get("MAT_Clay", build)


def water_film():
    """Thin standing water: mirror-like at grazing angles, clear when looking straight down."""

    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree, clear=True)
        out = nt.new("ShaderNodeOutputMaterial")
        wpos = nt.world_pos()
        ripple = nt.bump(nt.noise(wpos, 6.0, 2.0, 0.5), 0.02, 0.01)
        gl = nt.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.012
        nt.link(ripple, gl.inputs["Normal"])
        tr = nt.new("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = (0.82, 0.86, 0.9, 1)
        fr = nt.new("ShaderNodeFresnel")
        fr.inputs["IOR"].default_value = 1.33
        nt.link(ripple, fr.inputs["Normal"])
        mx = nt.new("ShaderNodeMixShader")
        nt.link(nt.math("ADD", nt.math("MULTIPLY", fr.outputs[0], 1.0), 0.03, clamp=True), mx.inputs[0])
        nt.link(tr.outputs[0], mx.inputs[1])
        nt.link(gl.outputs[0], mx.inputs[2])
        nt.link(mx.outputs[0], out.inputs["Surface"])
        return m

    return get("MAT_Water_Film", build)
