"""
WATERFALL VALLEY - photoreal Cycles build (Steps 2-5 on top of the Step 1 layout).

  Materials : procedural PBR (displacement + bump + roughness variation), strata cliffs, moss, golden
              lichen, dirt, wet rock near water, glacial turquoise water (transmission + volume), foam.
  Vegetation: weeping foreground tree with ~100k real leaf meshes (curved, folded, crumpled, 0.3 mm thick,
              size +-30 %, per-leaf colour, veins, translucency + SSS, waxy coat, spots, dry edges,
              insect holes), needle-cluster conifers, leafy bushes, Geometry Nodes grass (random scale
              0.8-1.2 and rotation), tall wild grass at the river edge.
  Light     : Nishita sky + clouds, warm sun lamp with soft shadows, path-traced GI, volumetric haze
              (god rays through the leaves), waterfall mist volume.
  Animation : 480 frames @ 24 fps - eased camera glide, 7 birds with flapping wings, looping wind on leaves,
              bushes and grass, flowing water and falling waterfall.
  Camera    : 36 mm full-frame sensor, shallow-ish DOF, chromatic aberration + glare in the compositor
              (grain, vignette and the final grade are added by ffmpeg when encoding).

Run (Blender 4.2 LTS; see the Colab notebook):
  blender -b -P final_scene.py -- --save waterfall_final.blend [--still 1 --out preview.png] [--preview]
"""
import math
import os
import random
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_waterfall_scene as wf  # noqa: E402

# ------------------------------------------------------------------ CONFIG
SAMPLES_FINAL = 64
SAMPLES_PREVIEW = 24
SUN_AZIMUTH = 48.0        # degrees right of the camera axis (just outside the frame, top-right)
SUN_ELEVATION = 30.0
SUN_STRENGTH = 4.5
SKY_STRENGTH = 0.30
EXPOSURE = 0.0
HAZE_DENSITY = 0.0012
FSTOP = 2.2
GRASS_DENSITY = 40.0      # tufts per m2 at full weight
LEAF_STRANDS_PER_BRANCH = 46
MOTION_BLUR = True
FPS, FRAMES = 24, 480

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, cast=str):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS) and not ARGS[i + 1].startswith("--"):
            return cast(ARGS[i + 1])
        return True
    return default


def lin(h):
    """'#RRGGBB' (sRGB) -> linear RGBA."""
    c = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, 1.0)


def mx(x):
    return wf.mx(x)


# ------------------------------------------------------------------ NODE HELPERS
class NB:
    """Tiny node-tree builder for shader and geometry-node trees."""

    def __init__(self, nt):
        self.nt = nt

    def n(self, t, **kw):
        node = self.nt.nodes.new(t)
        for k, v in kw.items():
            try:
                setattr(node, k, v)
            except (AttributeError, TypeError) as e:
                print("WARN", t, k, e)
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif v is not None:
            sock.default_value = v

    def setin(self, node, names, v):
        for nm in (names if isinstance(names, (list, tuple)) else (names,)):
            s = node.inputs.get(nm)
            if s is not None:
                self.put(s, v)
                return s
        print("WARN missing input", node.bl_idname, names)

    def math(self, op, a, b=None, c=None, clamp=False):
        node = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.put(node.inputs[0], a)
        if b is not None:
            self.put(node.inputs[1], b)
        if c is not None:
            self.put(node.inputs[2], c)
        return node.outputs[0]

    def vmath(self, op, a, b=None):
        node = self.n("ShaderNodeVectorMath", operation=op)
        self.put(node.inputs[0], a)
        if b is not None:
            self.put(node.inputs[1], b)
        return node.outputs["Value"] if op in ("DOT_PRODUCT", "DISTANCE", "LENGTH") else node.outputs["Vector"]

    def xyz(self, x=0.0, y=0.0, z=0.0):
        node = self.n("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(node.inputs[i], v)
        return node.outputs[0]

    def sep(self, v):
        node = self.n("ShaderNodeSeparateXYZ")
        self.put(node.inputs[0], v)
        return node.outputs

    def ramp(self, fac, stops):
        node = self.n("ShaderNodeValToRGB")
        self.put(node.inputs["Fac"], fac)
        els = node.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (pos, col) in zip(els, stops):
            el.position = pos
            el.color = col if len(col) == 4 else (*col, 1.0)
        return node.outputs["Color"]

    def ramp_f(self, fac, a, b):
        """Smooth 0..1 step of fac between a and b (as a float)."""
        return self._maprange(fac, a, b)

    def _maprange(self, fac, a, b):
        node = self.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self.put(node.inputs["Value"], fac)
        node.inputs["From Min"].default_value = a
        node.inputs["From Max"].default_value = b
        return node.outputs["Result"]

    def mix(self, fac, a, b, blend="MIX"):
        node = self.n("ShaderNodeMixRGB", blend_type=blend)
        self.put(node.inputs["Fac"], fac)
        self.put(node.inputs["Color1"], a)
        self.put(node.inputs["Color2"], b)
        return node.outputs["Color"]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dist=0.0, w=None):
        node = self.n("ShaderNodeTexNoise")
        if w is not None:
            node.noise_dimensions = "4D"
            self.put(node.inputs["W"], w)
        self.put(node.inputs["Vector"], vec)
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = rough
        node.inputs["Distortion"].default_value = dist
        return node

    def voronoi(self, vec, scale, feature="F1", rand=1.0):
        node = self.n("ShaderNodeTexVoronoi", feature=feature)
        self.put(node.inputs["Vector"], vec)
        node.inputs["Scale"].default_value = scale
        node.inputs["Randomness"].default_value = rand
        return node

    def driver(self, sock, expr):
        fc = sock.driver_add("default_value")
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = expr
        return fc


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    mat.node_tree.nodes.clear()
    b = NB(mat.node_tree)
    out = b.n("ShaderNodeOutputMaterial")
    return mat, b, out


def principled(b, **inputs):
    p = b.n("ShaderNodeBsdfPrincipled")
    names = {
        "base": ("Base Color",), "rough": ("Roughness",), "metal": ("Metallic",), "ior": ("IOR",),
        "alpha": ("Alpha",), "normal": ("Normal",), "spec": ("Specular IOR Level", "Specular"),
        "sss": ("Subsurface Weight", "Subsurface"), "sss_radius": ("Subsurface Radius",),
        "sss_scale": ("Subsurface Scale",), "trans": ("Transmission Weight", "Transmission"),
        "coat": ("Coat Weight", "Clearcoat"), "coat_rough": ("Coat Roughness", "Clearcoat Roughness"),
        "sheen": ("Sheen Weight", "Sheen"),
    }
    for k, v in inputs.items():
        b.setin(p, names[k], v)
    return p


def set_displacement(mat):
    for target in (mat, getattr(mat, "cycles", None)):
        try:
            target.displacement_method = "BOTH"
            return
        except Exception:
            pass


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def subsurf(obj, render_levels, simple=True):
    m = obj.modifiers.new("Subdiv", "SUBSURF")
    m.subdivision_type = "SIMPLE" if simple else "CATMULL_CLARK"
    m.levels = 0
    m.render_levels = render_levels
    return m


def link_obj(obj, coll):
    coll.objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, coll, uvs=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        for loop in me.loops:
            uvl.data[loop.index].uv = uvs[loop.vertex_index]
    if smooth and faces:
        try:
            me.shade_smooth()
        except AttributeError:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    obj = bpy.data.objects.new(name, me)
    if coll is not None:
        coll.objects.link(obj)
    return obj


def point_cloud_obj(name, pts, attrs, coll):
    """Vertex-only mesh with named point attributes (for Geometry Nodes instancing)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(pts, [], [])
    for aname, (atype, values) in attrs.items():
        a = me.attributes.new(aname, atype, "POINT")
        flat = []
        for v in values:
            flat.extend(v) if isinstance(v, (tuple, list, Vector)) else flat.append(v)
        a.data.foreach_set("vector" if atype == "FLOAT_VECTOR" else "value", flat)
    me.update()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    return obj


def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(c)
    return c


# ------------------------------------------------------------------ MATERIALS
def mat_terrain():
    mat, b, out = new_material("MAT_Ground")
    tc = b.n("ShaderNodeTexCoord").outputs["Object"]
    e = b.n("ShaderNodeAttribute", attribute_name="e", attribute_type="GEOMETRY").outputs["Fac"]
    geo = b.n("ShaderNodeNewGeometry")
    nz = b.sep(geo.outputs["Normal"])[2]
    big = b.noise(tc, 0.15, 5, 0.6).outputs["Fac"]
    fine = b.noise(tc, 6.0, 6, 0.6).outputs["Fac"]
    stones = b.voronoi(tc, 2.2)
    pebbles = b.voronoi(tc, 9.0)
    # soil / grass floor under the grass blades
    soil = b.mix(big, lin("#4a5a22"), lin("#6b6a33"))
    soil = b.mix(b.math("MULTIPLY", fine, 0.6), soil, lin("#3b3423"))
    # steep earth
    earth = b.mix(fine, lin("#6e6250"), lin("#8a7c66"))
    steep = b.ramp_f(nz, 0.86, 0.72)
    col = b.mix(steep, soil, earth)
    # gravel band at the river edge, wet and dark close to the waterline
    gravel = b.mix(pebbles.outputs["Distance"], lin("#8f897d"), lin("#5f5a52"))
    gravel = b.mix(b.math("MULTIPLY", b.noise(tc, 20.0, 3).outputs["Fac"], 0.5), gravel, lin("#b2ab9c"))
    gmask = b.ramp_f(e, 3.0, 1.2)
    col = b.mix(gmask, col, gravel)
    bed = b.mix(stones.outputs["Distance"], lin("#5b5141"), lin("#3a3f2e"))
    bed = b.mix(b.math("MULTIPLY", big, 0.7), bed, lin("#2d4a3a"))         # algae
    bmask = b.ramp_f(e, 0.0, -0.6)
    col = b.mix(bmask, col, bed)
    wet = b.math("MULTIPLY", b.ramp_f(e, 1.4, 0.2), 1.0)
    col = b.mix(b.math("MULTIPLY", wet, 0.45), col, (0.0, 0.0, 0.0, 1.0))
    rough = b.math("SUBTRACT", b.math("ADD", 0.82, b.math("MULTIPLY", fine, 0.15)), b.math("MULTIPLY", wet, 0.65))
    height = b.math("ADD", b.math("MULTIPLY", fine, 0.5),
                    b.math("MULTIPLY", b.math("ADD", gmask, bmask), b.math("SUBTRACT", 1.0, pebbles.outputs["Distance"])))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.04
    b.link(height, bump.inputs["Height"])
    p = principled(b, base=col, rough=rough, normal=bump.outputs["Normal"], spec=0.4)
    disp = b.n("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.08
    disp.inputs["Midlevel"].default_value = 0.4
    b.link(height, disp.inputs["Height"])
    b.link(p.outputs[0], out.inputs["Surface"])
    b.link(disp.outputs[0], out.inputs["Displacement"])
    set_displacement(mat)
    return mat


def mat_cliff(fall_xy):
    mat, b, out = new_material("MAT_Cliff_Strata")
    pos = b.n("ShaderNodeTexCoord").outputs["Object"]
    geo = b.n("ShaderNodeNewGeometry")
    nz = b.sep(geo.outputs["Normal"])[2]
    wave = b.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    b.link(pos, wave.inputs["Vector"])
    wave.inputs["Scale"].default_value = 0.045
    wave.inputs["Distortion"].default_value = 7.0
    wave.inputs["Detail"].default_value = 4.0
    strata = wave.outputs["Fac"]
    col = b.ramp(strata, [(0.0, lin("#8d8273")), (0.3, lin("#b5a58a")), (0.55, lin("#9a8d7a")),
                          (0.75, lin("#c2ad86")), (1.0, lin("#7a7268"))])
    big = b.noise(pos, 0.08, 5, 0.6).outputs["Fac"]
    fine = b.noise(pos, 3.0, 8, 0.65).outputs["Fac"]
    col = b.mix(b.math("MULTIPLY", big, 0.5), col, lin("#6d665c"), "MULTIPLY")
    cracks = b.voronoi(pos, 0.35, "DISTANCE_TO_EDGE").outputs["Distance"]
    crack_m = b.ramp_f(cracks, 0.06, 0.0)
    col = b.mix(b.math("MULTIPLY", crack_m, 0.8), col, lin("#2e2a25"))
    # vertical dirt streaks
    smap = b.n("ShaderNodeMapping")
    b.link(pos, smap.inputs["Vector"])
    smap.inputs["Scale"].default_value = (1.0, 1.0, 0.08)
    streak = b.ramp_f(b.noise(smap.outputs[0], 0.6, 4).outputs["Fac"], 0.5, 0.75)
    col = b.mix(b.math("MULTIPLY", streak, 0.45), col, lin("#4a4338"))
    # golden lichen and moss on ledges
    lich = b.ramp_f(b.noise(pos, 0.9, 6, 0.7).outputs["Fac"], 0.6, 0.68)
    col = b.mix(b.math("MULTIPLY", lich, 0.75), col, lin("#c49a3c"))
    moss_m = b.math("MULTIPLY", b.ramp_f(nz, 0.35, 0.75), b.ramp_f(big, 0.35, 0.55))
    moss = b.mix(fine, lin("#3e5a1c"), lin("#5f7a28"))
    col = b.mix(moss_m, col, moss)
    # wet, dark rock in the waterfall spray
    d = b.vmath("DISTANCE", pos, (fall_xy[0], fall_xy[1], 12.0))
    wet = b.ramp_f(d, 22.0, 8.0)
    col = b.mix(b.math("MULTIPLY", wet, 0.55), col, (0.0, 0.0, 0.0, 1.0))
    rough = b.math("SUBTRACT", b.math("ADD", 0.78, b.math("MULTIPLY", fine, 0.18)), b.math("MULTIPLY", wet, 0.6))
    height = b.math("ADD", b.math("MULTIPLY", strata, 0.45), b.math("MULTIPLY", fine, 0.35))
    height = b.math("SUBTRACT", height, b.math("MULTIPLY", crack_m, 0.35))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    bump.inputs["Distance"].default_value = 0.15
    b.link(b.math("ADD", height, b.math("MULTIPLY", moss_m, 0.2)), bump.inputs["Height"])
    p = principled(b, base=col, rough=rough, normal=bump.outputs["Normal"], spec=0.35)
    disp = b.n("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.6
    disp.inputs["Midlevel"].default_value = 0.5
    b.link(height, disp.inputs["Height"])
    b.link(p.outputs[0], out.inputs["Surface"])
    b.link(disp.outputs[0], out.inputs["Displacement"])
    set_displacement(mat)
    return mat


def mat_boulder():
    mat, b, out = new_material("MAT_Boulder_Granite")
    oi = b.n("ShaderNodeObjectInfo")
    tc = b.n("ShaderNodeTexCoord").outputs["Object"]
    rnd = oi.outputs["Random"]
    pos = b.vmath("ADD", tc, b.vmath("MULTIPLY", b.xyz(rnd, rnd, rnd), (37.0, 53.0, 71.0)))   # unique per boulder
    geo = b.n("ShaderNodeNewGeometry")
    nz = b.sep(geo.outputs["Normal"])[2]
    wz = b.sep(geo.outputs["Position"])[2]
    mott = b.noise(pos, 1.2, 6, 0.6).outputs["Fac"]
    speck = b.voronoi(pos, 35.0).outputs["Distance"]
    col = b.mix(mott, lin("#8c8a84"), lin("#b3b0a8"))
    col = b.mix(b.math("MULTIPLY", b.ramp_f(speck, 0.12, 0.0), 0.7), col, lin("#3c3a37"))
    col = b.mix(b.math("MULTIPLY", b.ramp_f(speck, 0.9, 1.0), 0.4), col, lin("#e6e2d8"))
    dirt = b.ramp_f(b.noise(pos, 2.5, 4).outputs["Fac"], 0.55, 0.7)
    col = b.mix(b.math("MULTIPLY", dirt, 0.5), col, lin("#6b5d47"))
    lich = b.ramp_f(b.noise(pos, 3.0, 5, 0.7).outputs["Fac"], 0.66, 0.72)
    col = b.mix(b.math("MULTIPLY", lich, 0.5), col, lin("#c9b37a"))
    moss_m = b.math("MULTIPLY", b.ramp_f(nz, 0.5, 0.85), b.ramp_f(mott, 0.4, 0.6))
    moss = b.mix(b.noise(pos, 25.0, 3).outputs["Fac"], lin("#2f4614"), lin("#58722a"))
    col = b.mix(moss_m, col, moss)
    wet = b.ramp_f(wz, 0.45, 0.05)
    col = b.mix(b.math("MULTIPLY", wet, 0.5), col, (0.0, 0.0, 0.0, 1.0))
    rough = b.math("SUBTRACT", b.math("ADD", 0.7, b.math("MULTIPLY", moss_m, 0.25)), b.math("MULTIPLY", wet, 0.55))
    fine = b.noise(pos, 14.0, 6).outputs["Fac"]
    height = b.math("ADD", b.math("MULTIPLY", mott, 0.6), b.math("MULTIPLY", fine, 0.25))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.02
    b.link(b.math("ADD", height, b.math("MULTIPLY", moss_m, b.math("MULTIPLY", fine, 0.8))), bump.inputs["Height"])
    p = principled(b, base=col, rough=rough, normal=bump.outputs["Normal"], spec=0.4)
    disp = b.n("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.06
    disp.inputs["Midlevel"].default_value = 0.5
    b.link(height, disp.inputs["Height"])
    b.link(p.outputs[0], out.inputs["Surface"])
    b.link(disp.outputs[0], out.inputs["Displacement"])
    set_displacement(mat)
    return mat


def mat_mountain():
    mat, b, out = new_material("MAT_Mountain")
    pos = b.n("ShaderNodeTexCoord").outputs["Object"]
    geo = b.n("ShaderNodeNewGeometry")
    nz = b.sep(geo.outputs["Normal"])[2]
    wz = b.sep(geo.outputs["Position"])[2]
    n1 = b.noise(pos, 0.02, 8, 0.6).outputs["Fac"]
    rock = b.mix(n1, lin("#5e626b"), lin("#8a8a8c"))
    forest = b.mix(n1, lin("#1c2a17"), lin("#2c3a20"))
    col = b.mix(b.ramp_f(b.math("ADD", wz, b.math("MULTIPLY", n1, 40.0)), 70.0, 110.0), forest, rock)
    snow_m = b.math("MULTIPLY", b.ramp_f(b.math("ADD", wz, b.math("MULTIPLY", n1, 60.0)), 140.0, 170.0), b.ramp_f(nz, 0.45, 0.7))
    col = b.mix(snow_m, col, lin("#eef2f6"))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 4.0
    b.link(b.noise(pos, 0.08, 10, 0.65).outputs["Fac"], bump.inputs["Height"])
    p = principled(b, base=col, rough=b.math("SUBTRACT", 0.9, b.math("MULTIPLY", snow_m, 0.4)), normal=bump.outputs["Normal"])
    b.link(p.outputs[0], out.inputs["Surface"])
    return mat


def mat_water():
    mat, b, out = new_material("MAT_Water_Glacial")
    pos = b.n("ShaderNodeTexCoord").outputs["Object"]
    mp = b.n("ShaderNodeMapping")
    b.link(pos, mp.inputs["Vector"])
    loc_fc = mp.inputs["Location"].driver_add("default_value", 1)
    loc_fc.driver.expression = "frame * 0.045"                 # flow toward the camera (-Y in object space)
    w = b.n("ShaderNodeValue")
    wfc = w.outputs[0].driver_add("default_value")
    wfc.driver.expression = "frame * 0.012"
    r1 = b.noise(mp.outputs[0], 0.9, 4, 0.55, w=w.outputs[0]).outputs["Fac"]
    r2 = b.noise(mp.outputs[0], 5.0, 3, 0.5, w=b.math("MULTIPLY", w.outputs[0], 2.3)).outputs["Fac"]
    h = b.math("ADD", b.math("MULTIPLY", r1, 0.7), b.math("MULTIPLY", r2, 0.3))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.05
    b.link(h, bump.inputs["Height"])
    water = principled(b, base=(1.0, 1.0, 1.0, 1.0), rough=0.04, ior=1.333, trans=1.0, spec=0.5, normal=bump.outputs["Normal"])
    foam_attr = b.n("ShaderNodeAttribute", attribute_name="foam", attribute_type="GEOMETRY").outputs["Fac"]
    fn = b.noise(mp.outputs[0], 3.0, 5, 0.6, w=w.outputs[0]).outputs["Fac"]
    foam = b.math("MULTIPLY", foam_attr, b.ramp_f(fn, 0.45, 0.62), clamp=True)
    foam_sh = principled(b, base=(0.92, 0.95, 0.96, 1.0), rough=0.55, sss=0.3, normal=bump.outputs["Normal"])
    mixs = b.n("ShaderNodeMixShader")
    b.link(foam, mixs.inputs["Fac"])
    b.link(water.outputs[0], mixs.inputs[1])
    b.link(foam_sh.outputs[0], mixs.inputs[2])
    b.link(mixs.outputs[0], out.inputs["Surface"])
    absorb = b.n("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (0.30, 0.78, 0.74, 1.0)
    absorb.inputs["Density"].default_value = 0.9
    scat = b.n("ShaderNodeVolumeScatter")
    scat.inputs["Color"].default_value = (0.55, 0.92, 0.90, 1.0)
    scat.inputs["Density"].default_value = 0.06
    scat.inputs["Anisotropy"].default_value = 0.3
    add = b.n("ShaderNodeAddShader")
    b.link(absorb.outputs[0], add.inputs[0])
    b.link(scat.outputs[0], add.inputs[1])
    b.link(add.outputs[0], out.inputs["Volume"])
    return mat


def mat_waterfall(speed):
    mat, b, out = new_material(f"MAT_Waterfall_{speed}")
    uv = b.n("ShaderNodeTexCoord").outputs["UV"]
    mp = b.n("ShaderNodeMapping")
    b.link(uv, mp.inputs["Vector"])
    mp.inputs["Scale"].default_value = (18.0, 2.2, 1.0)
    fc = mp.inputs["Location"].driver_add("default_value", 1)
    fc.driver.expression = f"-frame * {0.11 * speed:.4f}"      # streaks fall down (v grows downward)
    w = b.n("ShaderNodeValue")
    wf_ = w.outputs[0].driver_add("default_value")
    wf_.driver.expression = "frame * 0.02"
    n1 = b.noise(mp.outputs[0], 1.0, 6, 0.6, w=w.outputs[0]).outputs["Fac"]
    n2 = b.noise(mp.outputs[0], 4.0, 4, 0.6, w=w.outputs[0]).outputs["Fac"]
    streak = b.math("ADD", b.math("MULTIPLY", n1, 0.65), b.math("MULTIPLY", n2, 0.35))
    u, v, _ = b.sep(uv)
    edge = b.math("MULTIPLY", b.ramp_f(u, 0.0, 0.12), b.ramp_f(u, 1.0, 0.88))
    alpha = b.math("MULTIPLY", edge, b.ramp_f(b.math("ADD", streak, b.math("MULTIPLY", v, 0.25)), 0.35, 0.62))
    col = b.mix(streak, (0.70, 0.80, 0.82, 1.0), (0.97, 0.98, 0.98, 1.0))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    b.link(streak, bump.inputs["Height"])
    p = principled(b, base=col, rough=0.3, ior=1.333, trans=0.35, sss=0.35, sss_scale=0.05, normal=bump.outputs["Normal"])
    tr = b.n("ShaderNodeBsdfTransparent")
    mixs = b.n("ShaderNodeMixShader")
    b.link(alpha, mixs.inputs["Fac"])
    b.link(tr.outputs[0], mixs.inputs[1])
    b.link(p.outputs[0], mixs.inputs[2])
    b.link(mixs.outputs[0], out.inputs["Surface"])
    try:
        mat.blend_method = "HASHED"
    except Exception:
        pass
    return mat


def mat_volume(name, density, color, aniso, noise_mist=False):
    mat, b, out = new_material(name)
    vol = b.n("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = color
    vol.inputs["Anisotropy"].default_value = aniso
    if noise_mist:
        pos = b.n("ShaderNodeTexCoord").outputs["Generated"]
        w = b.n("ShaderNodeValue")
        fc = w.outputs[0].driver_add("default_value")
        fc.driver.expression = "frame * 0.015"
        mp = b.n("ShaderNodeMapping")
        b.link(pos, mp.inputs["Vector"])
        lfc = mp.inputs["Location"].driver_add("default_value", 2)
        lfc.driver.expression = "-frame * 0.002"            # mist drifts upward
        nz = b.noise(mp.outputs[0], 3.0, 4, 0.6, w=w.outputs[0]).outputs["Fac"]
        gz = b.sep(pos)[2]
        dens = b.math("MULTIPLY", b.ramp_f(nz, 0.42, 0.7), b.ramp_f(gz, 0.9, 0.05))
        b.link(b.math("MULTIPLY", dens, density), vol.inputs["Density"])
    else:
        vol.inputs["Density"].default_value = density
    b.link(vol.outputs[0], out.inputs["Volume"])
    return mat


def mat_leaf(name, deep, fresh, glow=0.38, dry_amt=0.45, hole_amt=0.12):
    """Thin-leaf PBR: per-leaf colour, veins, spots, dry edges, insect holes, translucency, waxy coat."""
    mat, b, out = new_material(name)
    uv = b.n("ShaderNodeTexCoord").outputs["UV"]
    u, v, _ = b.sep(uv)
    oi = b.n("ShaderNodeObjectInfo")
    rnd = oi.outputs["Random"]
    rnd2 = b.math("FRACT", b.math("MULTIPLY", rnd, 17.31))
    rnd3 = b.math("FRACT", b.math("MULTIPLY", rnd, 53.7))
    cu = b.math("ABSOLUTE", b.math("SUBTRACT", u, 0.5))                 # 0 at midrib, 0.5 at edge
    edge = b.math("MULTIPLY", cu, 2.0)
    t = b.math("ADD", b.math("ADD", b.math("MULTIPLY", v, 0.5), b.math("MULTIPLY", edge, 0.3)),
               b.math("MULTIPLY", b.math("SUBTRACT", rnd, 0.5), 0.6))
    col = b.ramp(t, [(0.0, deep), (0.55, b_mid(deep, fresh)), (1.0, fresh)])
    hs = b.n("ShaderNodeHueSaturation")
    b.link(col, hs.inputs["Color"])
    b.link(b.math("ADD", 0.5, b.math("MULTIPLY", b.math("SUBTRACT", rnd2, 0.5), 0.05)), hs.inputs["Hue"])
    b.link(b.math("ADD", 0.82, b.math("MULTIPLY", rnd3, 0.3)), hs.inputs["Value"])
    col = hs.outputs["Color"]
    # veins: midrib + lateral veins
    midrib = b.ramp_f(cu, 0.035, 0.0)
    lat = b.math("SINE", b.math("MULTIPLY", b.math("SUBTRACT", b.math("MULTIPLY", v, 13.0), b.math("MULTIPLY", cu, 5.0)), 6.2832))
    lat = b.math("MULTIPLY", b.ramp_f(lat, 0.85, 1.0), b.ramp_f(cu, 0.45, 0.2))
    veins = b.math("MAXIMUM", midrib, b.math("MULTIPLY", lat, 0.6))
    col = b.mix(b.math("MULTIPLY", veins, 0.35), col, b.mix(0.5, col, (0.85, 0.9, 0.55, 1.0)))
    # spots on some leaves
    spots = b.ramp_f(b.voronoi(uv, 22.0).outputs["Distance"], 0.09, 0.03)
    spot_on = b.ramp_f(rnd2, 0.72, 0.8)
    col = b.mix(b.math("MULTIPLY", spots, spot_on), col, lin("#4a3216"))
    # dry edges
    dry = b.math("MULTIPLY", b.ramp_f(edge, 0.72, 0.98), b.ramp_f(b.noise(uv, 7.0, 4).outputs["Fac"], 0.4, 0.6))
    dry = b.math("MULTIPLY", dry, b.math("MULTIPLY", b.ramp_f(rnd3, 0.55, 0.75), dry_amt * 2.0))
    col = b.mix(b.math("MINIMUM", dry, 1.0), col, lin("#8c6a2a"))
    # insect holes (alpha) on a few leaves
    holes = b.ramp_f(b.voronoi(uv, 7.0).outputs["Distance"], 0.13, 0.10)
    hole_on = b.ramp_f(rnd3, 1.0 - hole_amt, 1.0 - hole_amt + 0.01)
    alpha = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", holes, hole_on), clamp=True)
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.002
    b.link(b.math("SUBTRACT", 1.0, veins), bump.inputs["Height"])
    p = principled(b, base=col, rough=0.42, spec=0.5, sss=0.12, sss_scale=0.002, coat=0.12, coat_rough=0.3,
                   normal=bump.outputs["Normal"])
    tl = b.n("ShaderNodeBsdfTranslucent")
    b.link(b.mix(0.25, col, (0.85, 0.85, 0.3, 1.0)), tl.inputs["Color"])
    b.link(bump.outputs["Normal"], tl.inputs["Normal"])
    m1 = b.n("ShaderNodeMixShader")
    m1.inputs["Fac"].default_value = glow
    b.link(p.outputs[0], m1.inputs[1])
    b.link(tl.outputs[0], m1.inputs[2])
    tr = b.n("ShaderNodeBsdfTransparent")
    m2 = b.n("ShaderNodeMixShader")
    b.link(alpha, m2.inputs["Fac"])
    b.link(tr.outputs[0], m2.inputs[1])
    b.link(m1.outputs[0], m2.inputs[2])
    b.link(m2.outputs[0], out.inputs["Surface"])
    return mat


def b_mid(a, c):
    return tuple((a[i] + c[i]) * 0.5 for i in range(3)) + (1.0,)


def mat_grass():
    mat, b, out = new_material("MAT_Grass")
    uv = b.n("ShaderNodeTexCoord").outputs["UV"]
    _, v, _ = b.sep(uv)
    oi = b.n("ShaderNodeObjectInfo")
    rnd = oi.outputs["Random"]
    col = b.ramp(v, [(0.0, lin("#1f3a0c")), (0.45, lin("#4f8a1c")), (0.85, lin("#86b83a")), (1.0, lin("#b9c96a"))])
    hs = b.n("ShaderNodeHueSaturation")
    b.link(col, hs.inputs["Color"])
    b.link(b.math("ADD", 0.48, b.math("MULTIPLY", rnd, 0.05)), hs.inputs["Hue"])
    b.link(b.math("ADD", 0.8, b.math("MULTIPLY", b.math("FRACT", b.math("MULTIPLY", rnd, 11.0)), 0.35)), hs.inputs["Value"])
    col = b.mix(b.ramp_f(b.math("FRACT", b.math("MULTIPLY", rnd, 37.0)), 0.93, 0.95), hs.outputs["Color"], lin("#b9a463"))
    p = principled(b, base=col, rough=0.45, spec=0.45, sss=0.08, sss_scale=0.002)
    tl = b.n("ShaderNodeBsdfTranslucent")
    b.link(col, tl.inputs["Color"])
    m = b.n("ShaderNodeMixShader")
    m.inputs["Fac"].default_value = 0.3
    b.link(p.outputs[0], m.inputs[1])
    b.link(tl.outputs[0], m.inputs[2])
    b.link(m.outputs[0], out.inputs["Surface"])
    return mat


def mat_needles():
    mat, b, out = new_material("MAT_Conifer_Needles")
    oi = b.n("ShaderNodeObjectInfo")
    rnd = oi.outputs["Random"]
    col = b.mix(rnd, lin("#16301a"), lin("#2d4a24"))
    p = principled(b, base=col, rough=0.5, spec=0.45, coat=0.08)
    tl = b.n("ShaderNodeBsdfTranslucent")
    b.link(col, tl.inputs["Color"])
    m = b.n("ShaderNodeMixShader")
    m.inputs["Fac"].default_value = 0.18
    b.link(p.outputs[0], m.inputs[1])
    b.link(tl.outputs[0], m.inputs[2])
    b.link(m.outputs[0], out.inputs["Surface"])
    return mat


def mat_bark(name="MAT_Bark", tint="#4b4036"):
    mat, b, out = new_material(name)
    pos = b.n("ShaderNodeTexCoord").outputs["Object"]
    mp = b.n("ShaderNodeMapping")
    b.link(pos, mp.inputs["Vector"])
    mp.inputs["Scale"].default_value = (6.0, 6.0, 0.9)
    fiss = b.voronoi(mp.outputs[0], 3.0, "DISTANCE_TO_EDGE").outputs["Distance"]
    n = b.noise(pos, 8.0, 6).outputs["Fac"]
    col = b.mix(n, lin(tint), lin("#7d7264"))
    col = b.mix(b.ramp_f(fiss, 0.08, 0.0), col, lin("#1d1915"))
    moss = b.ramp_f(b.noise(pos, 1.5, 4).outputs["Fac"], 0.55, 0.65)
    col = b.mix(b.math("MULTIPLY", moss, 0.6), col, lin("#4b6122"))
    bump = b.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 0.02
    b.link(b.math("ADD", fiss, b.math("MULTIPLY", n, 0.3)), bump.inputs["Height"])
    p = principled(b, base=col, rough=0.85, normal=bump.outputs["Normal"])
    b.link(p.outputs[0], out.inputs["Surface"])
    return mat


def mat_simple(name, color, rough=0.8):
    mat, b, out = new_material(name)
    p = principled(b, base=color, rough=rough)
    b.link(p.outputs[0], out.inputs["Surface"])
    return mat


# ------------------------------------------------------------------ ASSET MESHES (real geometry)
def leaf_geometry(seed, width=0.16, fold=0.10, curl=0.18, crumple=0.025, ovate=0.0, rows=14, cols=6):
    """Unit-length leaf: stem at origin, length along +Y, width along X, folded at the midrib,
    curled along its length and slightly crumpled."""
    rnd = random.Random(seed)
    verts, uvs = [], []
    for j in range(rows + 1):
        v = j / rows
        prof = math.sin(math.pi * min(1.0, v * (1.0 + ovate))) ** 0.85 * (1.0 - 0.35 * v * (1 - ovate))
        w = width * max(prof, 0.0) + 0.004
        for i in range(cols + 1):
            u = i / cols
            x = (u - 0.5) * 2 * w
            z = fold * abs(x) / max(width, 1e-3) * 0.5        # V-fold along the midrib
            z += curl * v * v                                 # curl along the length
            z += crumple * wf.vnoise(x * 40 + seed, v * 25, 0.5, seed) * (0.3 + v)
            y = v + 0.02 * wf.vnoise(x * 30, v * 10, 1.5, seed + 1)
            verts.append((x, y, z))
            uvs.append((u, v))
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i)
             for j in range(rows) for i in range(cols)]
    rnd.random()
    return verts, faces, uvs


def grass_tuft_geometry(seed, blades=24, hmin=0.15, hmax=0.45, wbase=0.005, spread=0.06):
    rnd = random.Random(seed)
    verts, faces, uvs = [], [], []
    for _ in range(blades):
        a = rnd.uniform(0, math.tau)
        ox, oy = math.cos(a) * rnd.uniform(0, spread), math.sin(a) * rnd.uniform(0, spread)
        h = rnd.uniform(hmin, hmax)
        lean = rnd.uniform(0.15, 0.55) * h
        dx, dy = math.cos(a + rnd.uniform(-0.6, 0.6)), math.sin(a + rnd.uniform(-0.6, 0.6))
        px, py = -dy, dx
        twist = rnd.uniform(-0.6, 0.6)
        base = len(verts)
        segs = 5
        for s in range(segs + 1):
            t = s / segs
            w = wbase * (1 - t) ** 0.9 + 0.0004
            cx, cy, cz = ox + dx * lean * t * t, oy + dy * lean * t * t, h * (t - 0.18 * t * t * lean / h)
            ca, sa = math.cos(twist * t), math.sin(twist * t)
            qx, qy = px * ca - py * sa, px * sa + py * ca
            verts += [(cx - qx * w, cy - qy * w, cz), (cx + qx * w, cy + qy * w, cz)]
            uvs += [(0.0, t), (1.0, t)]
        for s in range(segs):
            i0 = base + 2 * s
            faces.append((i0, i0 + 1, i0 + 3, i0 + 2))
    return verts, faces, uvs


def needle_cluster_geometry(seed, needles=34, nlen=0.12, nw=0.006):
    """A fir/spruce twig: axis along +Y (length 1), needles spiralling around it."""
    rnd = random.Random(seed)
    verts, faces = [], []
    for k in range(needles):
        t = 0.05 + 0.9 * k / needles
        th = k * 2.399 + rnd.uniform(-0.2, 0.2)
        d = Vector((math.cos(th) * 0.85, 0.45 + rnd.uniform(-0.1, 0.2), math.sin(th) * 0.55 + 0.25)).normalized()
        side = d.cross(Vector((0, 1, 0))).normalized() * nw
        p0 = Vector((0, t, 0))
        p1 = p0 + d * nlen * rnd.uniform(0.75, 1.15)
        b = len(verts)
        verts += [tuple(p0 - side), tuple(p0 + side), tuple(p1 + side * 0.2), tuple(p1 - side * 0.2)]
        faces.append((b, b + 1, b + 2, b + 3))
    b = len(verts)                                                # twig
    verts += [(-0.006, 0, 0), (0.006, 0, 0), (0.002, 1.0, 0), (-0.002, 1.0, 0)]
    faces.append((b, b + 1, b + 2, b + 3))
    return verts, faces


def euler_from_dir(d, roll):
    q = Vector(d).normalized().to_track_quat("Y", "Z") @ Quaternion((0, 1, 0), roll)
    e = q.to_euler("XYZ")
    return (e.x, e.y, e.z)


# ------------------------------------------------------------------ GEOMETRY NODES
def gn_interface(ng, inputs, with_geo_out=True):
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for name, stype in inputs:
        ng.interface.new_socket(name=name, in_out="INPUT", socket_type=stype)
    if with_geo_out:
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")


def set_mod_inputs(mod, values):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, "item_type", "SOCKET") == "SOCKET" and item.in_out == "INPUT" and item.name in values:
            mod[item.identifier] = values[item.name]


def to_rotation(b, vec):
    try:
        node = b.n("FunctionNodeEulerToRotation")
        b.link(vec, node.inputs[0])
        return node.outputs[0]
    except RuntimeError:
        return vec


def random_value(b, dtype, lo, hi, seed):
    node = b.n("FunctionNodeRandomValue", data_type=dtype)
    idx = {"FLOAT_VECTOR": (0, 1, 0), "FLOAT": (2, 3, 1), "INT": (4, 5, 2)}[dtype]
    node.inputs[idx[0]].default_value = lo
    node.inputs[idx[1]].default_value = hi
    node.inputs["Seed"].default_value = seed
    return node.outputs[idx[2]]


def named(b, name, dtype):
    node = b.n("GeometryNodeInputNamedAttribute", data_type=dtype)
    node.inputs["Name"].default_value = name
    return node.outputs[0]


def wave(b, t, omega, phase, amp):
    return b.math("MULTIPLY", b.math("SINE", b.math("ADD", b.math("MULTIPLY", t, omega), phase)), amp)


def gn_scatter_group():
    """Points with attributes rot/scl/phase/amp -> swaying, fluttering instances from a collection."""
    ng = bpy.data.node_groups.new("GN_WindInstances", "GeometryNodeTree")
    gn_interface(ng, [("Instances", "NodeSocketCollection"), ("Wind", "NodeSocketFloat")])
    b = NB(ng)
    gi, go = b.n("NodeGroupInput"), b.n("NodeGroupOutput")
    t = b.n("GeometryNodeInputSceneTime").outputs["Seconds"]
    ph = named(b, "phase", "FLOAT")
    amp = b.math("MULTIPLY", named(b, "amp", "FLOAT"), gi.outputs["Wind"])
    w1, w2, w3 = 2 * math.pi * 3 / 20, 2 * math.pi * 8 / 20, 2 * math.pi * 2 / 20     # loops every 20 s
    ox = b.math("MULTIPLY", b.math("ADD", wave(b, t, w1, ph, 0.6), wave(b, t, w2, b.math("MULTIPLY", ph, 1.7), 0.22)), amp)
    oy = b.math("MULTIPLY", wave(b, t, w3, b.math("MULTIPLY", ph, 0.7), 0.45), amp)
    sp = b.n("GeometryNodeSetPosition")
    b.link(gi.outputs["Geometry"], sp.inputs["Geometry"])
    b.link(b.xyz(ox, oy, 0.0), sp.inputs["Offset"])
    ci = b.n("GeometryNodeCollectionInfo")
    b.link(gi.outputs["Instances"], ci.inputs["Collection"])
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = b.n("GeometryNodeInstanceOnPoints")
    b.link(sp.outputs[0], iop.inputs["Points"])
    b.link(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    b.link(random_value(b, "INT", 0, 99, 11), iop.inputs["Instance Index"])
    b.link(to_rotation(b, named(b, "rot", "FLOAT_VECTOR")), iop.inputs["Rotation"])
    scl = named(b, "scl", "FLOAT")
    b.link(b.xyz(scl, scl, scl), iop.inputs["Scale"])
    flutter = b.math("MULTIPLY", wave(b, t, 2 * math.pi * 22 / 20, b.math("MULTIPLY", ph, 5.0), 0.14), gi.outputs["Wind"])
    rot = b.n("GeometryNodeRotateInstances")
    b.link(iop.outputs[0], rot.inputs["Instances"])
    b.link(to_rotation(b, b.xyz(flutter, 0.0, 0.0)), rot.inputs["Rotation"])
    rot.inputs["Local Space"].default_value = True
    b.link(rot.outputs[0], go.inputs[0])
    return ng


def gn_grass_group():
    ng = bpy.data.node_groups.new("GN_GrassScatter", "GeometryNodeTree")
    gn_interface(ng, [("Ground", "NodeSocketObject"), ("Tufts", "NodeSocketCollection"),
                      ("Wild", "NodeSocketCollection"), ("Density", "NodeSocketFloat")])
    b = NB(ng)
    gi, go = b.n("NodeGroupInput"), b.n("NodeGroupOutput")
    oi = b.n("GeometryNodeObjectInfo", transform_space="RELATIVE")
    b.link(gi.outputs["Ground"], oi.inputs["Object"])
    t = b.n("GeometryNodeInputSceneTime").outputs["Seconds"]
    join = b.n("GeometryNodeJoinGeometry")
    for attr, coll_name, dens_mul, seed, smin, smax in (("grass", "Tufts", 1.0, 3, 0.8, 1.2), ("wild", "Wild", 0.25, 7, 0.8, 1.25)):
        dist = b.n("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
        b.link(oi.outputs["Geometry"], dist.inputs["Mesh"])
        b.link(b.math("MULTIPLY", named(b, attr, "FLOAT"), b.math("MULTIPLY", gi.outputs["Density"], dens_mul)), dist.inputs["Density"])
        dist.inputs["Seed"].default_value = seed
        ci = b.n("GeometryNodeCollectionInfo")
        b.link(gi.outputs[coll_name], ci.inputs["Collection"])
        ci.inputs["Separate Children"].default_value = True
        ci.inputs["Reset Children"].default_value = True
        iop = b.n("GeometryNodeInstanceOnPoints")
        b.link(dist.outputs["Points"], iop.inputs["Points"])
        b.link(ci.outputs[0], iop.inputs["Instance"])
        iop.inputs["Pick Instance"].default_value = True
        b.link(random_value(b, "INT", 0, 99, seed + 1), iop.inputs["Instance Index"])
        b.link(to_rotation(b, b.xyz(0.0, 0.0, random_value(b, "FLOAT", 0.0, 6.283, seed + 2))), iop.inputs["Rotation"])
        s = random_value(b, "FLOAT", smin, smax, seed + 3)
        b.link(b.xyz(s, s, s), iop.inputs["Scale"])
        p = b.sep(b.n("GeometryNodeInputPosition").outputs[0])
        ph = b.math("ADD", b.math("MULTIPLY", p[0], 0.35), b.math("MULTIPLY", p[1], 0.21))
        sx = b.math("ADD", wave(b, t, 2 * math.pi * 5 / 20, ph, 0.09), wave(b, t, 2 * math.pi * 12 / 20, b.math("MULTIPLY", ph, 2.0), 0.035))
        sy = wave(b, t, 2 * math.pi * 4 / 20, b.math("MULTIPLY", ph, 0.8), 0.06)
        rot = b.n("GeometryNodeRotateInstances")
        b.link(iop.outputs[0], rot.inputs["Instances"])
        b.link(to_rotation(b, b.xyz(sx, sy, 0.0)), rot.inputs["Rotation"])
        b.link(rot.outputs[0], join.inputs[0])
    b.link(join.outputs[0], go.inputs[0])
    return ng


# ------------------------------------------------------------------ CURVES (trunks, branches, twigs)
def curve_obj(name, splines, coll, mat, resolution=3):
    """splines: list of (points[(x,y,z)], radii[])"""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 1.0
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    for pts, radii in splines:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for p, r, cp in zip(pts, radii, sp.points):
            cp.co = (p[0], p[1], p[2], 1.0)
            cp.radius = r
    obj = bpy.data.objects.new(name, cu)
    coll.objects.link(obj)
    cu.materials.append(mat)
    return obj


def catmull3(pts, samples):
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            out.append(Vector(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                           + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in range(3))))
    out.append(Vector(pts[-1]))
    return out


# ------------------------------------------------------------------ BUILD
def build():
    wf.USE_CLAY_OVERRIDE = False
    wf.SAVE_BLEND = False
    wf.RENDER_STILL_IN_BACKGROUND = False
    wf.main()
    scene = bpy.context.scene
    vl = bpy.context.view_layer
    vl.material_override = None
    C = {c.name: c for c in bpy.data.collections}
    rnd = random.Random(2026)

    assets = collection("_Assets")

    # --- remove blockout proxies, remember their placement
    pines, bushes = [], []
    for o in list(bpy.data.objects):
        if o.name.startswith("Pine_"):
            pines.append((Vector(o.location), o.scale.z))
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.name.startswith("Bush_"):
            bushes.append((Vector(o.location), o.scale.y))
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.name == "River_Surface":
            bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)

    # --- terrain: attributes (river edge distance, grass density) + ground material
    terrain = bpy.data.objects["Terrain_Valley"]
    me = terrain.data
    cam_path = [(0, -2), (mx(3.5), 24), (mx(8), 40)]
    e_vals, g_vals, w_vals = [], [], []
    for vert in me.vertices:
        x, y, z = vert.co
        d, rw = wf.river_info(x, y)
        e = d - rw
        e_vals.append(e)
        visible = abs(x) < 28 + max(y, 0) * 0.65 and -6 < y < 110
        dcam = min(math.hypot(x - cx, y - cy) for cx, cy in cam_path)
        fall = max(0.12, 1.0 - dcam / 90.0)
        slope_ok = vert.normal.z > 0.72
        g = (1.0 if (e > 1.6 and slope_ok and visible and z > 0.15) else 0.0) * fall
        g_vals.append(g)
        w_vals.append(1.0 if (1.0 < e < 4.5 and visible and y < 95) else 0.0)
    for name, vals in (("e", e_vals), ("grass", g_vals), ("wild", w_vals)):
        a = me.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)
    assign(terrain, mat_terrain())
    subsurf(terrain, 2)

    # --- cliffs, rocks, mountains
    fall_xy = (mx(44), 100)
    cliff_mat = mat_cliff(fall_xy)
    for name in ("Cliff_Left_Centre", "Cliff_Right"):
        o = bpy.data.objects[name]
        assign(o, cliff_mat)
        subsurf(o, 2)
    rock_mat = mat_boulder()
    for o in bpy.data.objects:
        if o.name.startswith(("Boulder", "Pebble")):
            if not o.data.materials or o.data.materials[0] != rock_mat:
                assign(o, rock_mat)
            subsurf(o, 2 if o.name.startswith("Boulder_Hero") else 1, simple=False)
    assign(bpy.data.objects["Terrain_Mountains"], mat_mountain())

    # --- water: grid with foam attribute, solidified so the glacial volume works
    rocks_in_water = []
    for o in bpy.data.objects:
        if o.name.startswith("Boulder"):
            dims = o.dimensions
            if o.location.z - dims.z * 0.3 < 0.2 < o.location.z + dims.z * 0.6:
                rocks_in_water.append((o.location.x, o.location.y, max(dims.x, dims.y) * 0.5))
    wfm = bpy.data.objects["Waterfall_Main"]
    zmin = min(vv.co.z for vv in wfm.data.vertices)
    low = [vv.co for vv in wfm.data.vertices if vv.co.z < zmin + 0.3]
    fb = wfm.matrix_world @ (sum(low, Vector()) / len(low))     # base of the falls
    step, xs0, ys0, nx, ny = 0.5, -45.0, -30.0, 201, 271
    verts, foam, hgt = [], [], []
    for i in range(nx):
        for j in range(ny):
            x, y = xs0 + i * step, ys0 + j * step
            verts.append((x, y, 0.0))
            hgt.append(wf.terrain_h(x, y))
            f = 0.0
            for rx, ry, rr_ in rocks_in_water:
                f += max(0.0, 1.0 - max(0.0, math.hypot(x - rx, y - ry) - rr_ * 0.9) / 1.6)
            f += max(0.0, 1.0 - math.hypot(x - fb.x, y - fb.y) / 10.0) * 1.5
            d, rw = wf.river_info(x, y)
            f += max(0.0, 1.0 - abs(d - rw) / 1.0) * 0.35
            foam.append(min(f, 1.0))
    faces = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            q = (i * ny + j, (i + 1) * ny + j, (i + 1) * ny + j + 1, i * ny + j + 1)
            if min(hgt[k] for k in q) < 0.25:
                faces.append(q)
    water = mesh_obj("Water_River", verts, faces, C["Water"], smooth=True)
    water.data.attributes.new("foam", "FLOAT", "POINT").data.foreach_set("value", foam)
    sol = water.modifiers.new("Depth", "SOLIDIFY")
    sol.thickness = 2.2
    sol.offset = -1.0
    assign(water, mat_water())

    # --- waterfalls: UVs + animated material
    for name, cols, speed in (("Waterfall_Main", 24, 1.0), ("Waterfall_Strand", 6, 1.2)):
        o = bpy.data.objects[name]
        rows = len(o.data.vertices) // (cols + 1)
        uvs = [(i / cols, j / (rows - 1)) for i in range(cols + 1) for j in range(rows)]
        uvl = o.data.uv_layers.new(name="UVMap")
        for loop in o.data.loops:
            uvl.data[loop.index].uv = uvs[loop.vertex_index]
        assign(o, mat_waterfall(speed))
        subsurf(o, 1, simple=False)

    # --- atmosphere: valley haze + waterfall mist
    def box(name, cx, cy, cz, sx, sy, sz, mat, coll):
        vs = [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-0.5, 0.5) for dy in (-0.5, 0.5) for dz in (-0.5, 0.5)]
        fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        o = mesh_obj(name, vs, fs, coll, smooth=False)
        assign(o, mat)
        return o
    box("VOL_Haze", 0, 520, 200, 2000, 1200, 460, mat_volume("MAT_Haze", HAZE_DENSITY, (0.78, 0.86, 1.0, 1.0), 0.55), C["Lights"])
    box("VOL_FallMist", fb.x, fb.y - 3, 7, 34, 18, 20,
        mat_volume("MAT_Mist", 0.09, (1.0, 1.0, 1.0, 1.0), 0.3, noise_mist=True), C["Water"])

    # --- world: Nishita sky + clouds, sun lamp
    az, el = math.radians(mx(SUN_AZIMUTH)), math.radians(SUN_ELEVATION)
    sdir = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    world = bpy.data.worlds.new("WLD_Nishita")
    try:
        world.use_nodes = True
    except Exception:
        pass
    world.node_tree.nodes.clear()
    b = NB(world.node_tree)
    wout = b.n("ShaderNodeOutputWorld")
    sky = b.n("ShaderNodeTexSky")
    for st in ("NISHITA", "MULTIPLE_SCATTERING", "SINGLE_SCATTERING"):
        try:
            sky.sky_type = st
            break
        except TypeError:
            continue
    for k, v in (("sun_disc", False), ("sun_elevation", el), ("sun_rotation", -az), ("altitude", 800.0),
                 ("air_density", 1.0), ("dust_density", 1.6), ("ozone_density", 1.0)):
        try:
            setattr(sky, k, v)
        except Exception as ex:
            print("WARN sky", k, ex)
    dirv = b.n("ShaderNodeTexCoord").outputs["Generated"]
    dx, dy, dz = b.sep(dirv)
    den = b.math("ADD", b.math("MAXIMUM", dz, 0.0), 0.08)
    cp = b.xyz(b.math("DIVIDE", dx, den), b.math("DIVIDE", dy, den), 0.0)
    cl = b.noise(cp, 0.55, 6, 0.6).outputs["Fac"]
    cmask = b.math("MULTIPLY", b.ramp_f(cl, 0.56, 0.72), b.ramp_f(dz, 0.03, 0.25))
    bw = b.n("ShaderNodeRGBToBW")
    b.link(sky.outputs["Color"], bw.inputs["Color"])
    cloud_col = b.math("MULTIPLY", bw.outputs[0], 1.9)
    skycol = b.mix(b.math("MULTIPLY", cmask, 0.85), sky.outputs["Color"], b.xyz(cloud_col, cloud_col, cloud_col))
    bg = b.n("ShaderNodeBackground")
    b.link(skycol, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = SKY_STRENGTH
    b.link(bg.outputs[0], wout.inputs["Surface"])
    scene.world = world
    sun = bpy.data.objects["LGT_Sun_Key"]
    sun.data.energy = SUN_STRENGTH
    sun.data.angle = math.radians(1.2)
    sun.data.color = (1.0, 0.93, 0.82)
    sun.rotation_euler = (-sdir).to_track_quat("-Z", "Y").to_euler()

    # --- asset collections
    def asset_coll(name):
        return collection(name, assets)
    leaf_tree = asset_coll("LeafTree")
    leaf_bush = asset_coll("LeafBush")
    tufts = asset_coll("GrassTufts")
    wild = asset_coll("GrassWild")
    needles = asset_coll("Needles")
    mat_lt = mat_leaf("MAT_Leaf_Weeping", lin("#4C8C2B"), lin("#B5D334"))
    mat_lb = mat_leaf("MAT_Leaf_Bush", lin("#2c5418"), lin("#6e9a2a"), glow=0.3, dry_amt=0.3, hole_amt=0.06)
    for k, (fold, curl, crum, wdt, ov) in enumerate([(0.10, 0.18, 0.02, 0.15, 0.0), (0.16, 0.30, 0.03, 0.13, 0.0),
                                                      (0.06, 0.10, 0.04, 0.17, 0.0), (0.12, -0.12, 0.03, 0.14, 0.0)]):
        v, f, uv = leaf_geometry(100 + k, wdt, fold, curl, crum, ov)
        o = mesh_obj(f"Leaf_Lance_{k}", v, f, leaf_tree, uvs=uv)
        s = o.modifiers.new("Thickness", "SOLIDIFY")
        s.thickness = 0.006
        s.offset = 0.0
        assign(o, mat_lt)
    for k, (fold, curl, crum, wdt, ov) in enumerate([(0.12, 0.15, 0.03, 0.30, 0.35), (0.18, 0.25, 0.04, 0.26, 0.25),
                                                      (0.08, -0.1, 0.03, 0.32, 0.4)]):
        v, f, uv = leaf_geometry(200 + k, wdt, fold, curl, crum, ov)
        o = mesh_obj(f"Leaf_Ovate_{k}", v, f, leaf_bush, uvs=uv)
        s = o.modifiers.new("Thickness", "SOLIDIFY")
        s.thickness = 0.008
        assign(o, mat_lb)
    gmat = mat_grass()
    for k in range(4):
        v, f, uv = grass_tuft_geometry(300 + k)
        assign(mesh_obj(f"GrassTuft_{k}", v, f, tufts, uvs=uv), gmat)
    for k in range(2):
        v, f, uv = grass_tuft_geometry(400 + k, blades=14, hmin=0.55, hmax=1.0, wbase=0.007, spread=0.1)
        assign(mesh_obj(f"GrassWild_{k}", v, f, wild, uvs=uv), gmat)
    nmat = mat_needles()
    for k in range(3):
        v, f = needle_cluster_geometry(500 + k)
        assign(mesh_obj(f"NeedleTwig_{k}", v, f, needles, smooth=False), nmat)
    bark = mat_bark()
    ng_wind = gn_scatter_group()

    def scatter(name, pts, rots, scls, phases, amps, inst_coll, coll, wind=1.0):
        o = point_cloud_obj(name, pts, {"rot": ("FLOAT_VECTOR", rots), "scl": ("FLOAT", scls),
                                        "phase": ("FLOAT", phases), "amp": ("FLOAT", amps)}, coll)
        mod = o.modifiers.new("Instances", "NODES")
        mod.node_group = ng_wind
        set_mod_inputs(mod, {"Instances": inst_coll, "Wind": wind})
        return o

    # --- foreground weeping tree (top-right)
    side = -1 if wf.MIRROR_X else 1
    bx = mx(19)
    g0 = wf.terrain_h(bx, 20)
    trunk_pts = [(bx, 20, g0 - 0.5), (bx - 0.5 * side, 20.4, g0 + 4), (bx - 2 * side, 21, g0 + 8), (bx - 4 * side, 21.5, g0 + 11)]
    trunk = catmull3(trunk_pts, 8)
    splines = [(trunk, [0.42 * (1 - 0.7 * i / len(trunk)) for i in range(len(trunk))])]
    twigs, L_pts, L_rot, L_scl, L_ph, L_amp = [], [], [], [], [], []
    trng = random.Random(77)
    rr = trng.uniform

    def add_leaf(p, d, scl, amp):
        L_pts.append(tuple(p))
        L_rot.append(euler_from_dir(d, rr(0, math.tau)))
        L_scl.append(scl)
        L_ph.append(rr(0, math.tau))
        L_amp.append(amp)

    for _ in range(11):
        s = trunk[int(rr(0.55, 0.999) * (len(trunk) - 1))]
        ang = rr(-0.9, 1.0)
        ln = rr(4.5, 8.0)
        d = Vector((-math.cos(ang) * side, math.sin(ang) * 0.9, 0.0)).normalized()
        p1 = s + d * ln * 0.4 + Vector((0, 0, rr(1.5, 3.0)))
        p2 = s + d * ln * 0.75 + Vector((0, 0, rr(1.0, 2.5)))
        p3 = s + d * ln + Vector((0, 0, rr(-0.5, 1.0)))
        br = catmull3([tuple(s), tuple(p1), tuple(p2), tuple(p3)], 8)
        r0 = rr(0.07, 0.14)
        splines.append((br, [r0 * (1 - 0.85 * i / len(br)) + 0.008 for i in range(len(br))]))
        for _ in range(LEAF_STRANDS_PER_BRANCH):
            t = rr(0.25, 1.0)
            a = br[int(t * (len(br) - 1))]
            L = rr(1.0, 2.2) + t * rr(1.5, 3.2)
            ph = rr(0, math.tau)
            drift = Vector((rr(-0.25, 0.25), rr(-0.25, 0.25), 0))
            n = int(L / 0.04)
            tw = []
            for k in range(n + 1):
                f = k / n
                p = a + Vector((drift.x * f * L + math.sin(f * 4 + ph) * 0.06, drift.y * f * L, -f * L))
                if k % 6 == 0:
                    tw.append(p)
                for _ in range(2):
                    out = Vector((rr(-1, 1), rr(-1, 1), 0)).normalized()
                    dleaf = (Vector((0, 0, -1)) + out * rr(0.4, 1.1)).normalized()
                    add_leaf(p + out * 0.01, dleaf, 0.05 * rr(0.7, 1.3), 0.03 + 0.22 * f * L / 4.5)
            if len(tw) >= 2:
                twigs.append((tw, [0.004] * len(tw)))
            for _ in range(10):
                q = a + Vector((rr(-0.6, 0.6), rr(-0.6, 0.6), rr(-0.3, 0.4)))
                add_leaf(q, Vector((rr(-1, 1), rr(-1, 1), rr(-1, 0.3))), 0.05 * rr(0.7, 1.3), 0.02)
    tree = collection("Tree_Foreground", C["Vegetation"])
    for o in (curve_obj("Tree_TrunkBranches", splines, tree, bark, 4), curve_obj("Tree_Twigs", twigs, tree, bark, 1)):
        o.data.bevel_resolution = 1 if o.name.endswith("Twigs") else 4
    scatter("Tree_Leaves", L_pts, L_rot, L_scl, L_ph, L_amp, leaf_tree, C["Leaves"])
    print("tree leaves:", len(L_pts))

    # --- bushes (leaf clumps + dark core)
    core_mat = mat_simple("MAT_BushCore", lin("#18260f"), 0.9)
    bp, br_, bs, bph, bam = [], [], [], [], []
    cv, cf = wf.icosphere(2)
    for (loc, sc) in bushes:
        r = 0.9 * sc
        core = mesh_obj("Bush_Core", [(x * r * 0.75, y * r * 0.75, max(z, -0.2) * r * 0.5 + r * 0.35) for x, y, z in cv], cf, C["Vegetation"])
        core.location = loc
        assign(core, core_mat)
        for _ in range(int(900 * r * r + 200)):
            u, vv = rr(0, math.tau), math.acos(rr(-0.2, 1.0))
            rad = r * rr(0.55, 1.0) ** 0.33
            off = Vector((math.cos(u) * math.sin(vv) * rad * 1.1, math.sin(u) * math.sin(vv) * rad * 1.1, math.cos(vv) * rad * 0.7 + r * 0.3))
            p = loc + off
            d = (off.normalized() + Vector((0, 0, 0.4)) + Vector((rr(-0.5, 0.5), rr(-0.5, 0.5), rr(-0.5, 0.5)))).normalized()
            bp.append(tuple(p)); br_.append(euler_from_dir(d, rr(0, math.tau)))
            bs.append(0.075 * rr(0.7, 1.3)); bph.append(rr(0, math.tau)); bam.append(0.025 * (off.z / (r + 0.01)))
    scatter("Bush_Leaves", bp, br_, bs, bph, bam, leaf_bush, C["Leaves"], wind=0.8)

    # --- conifers: 4 variants (trunk + whorled branches + needle twigs), placed as collection instances
    variants = []
    for k in range(4):
        vc = collection(f"PineVar_{k}", assets)
        prng = random.Random(900 + k)
        H = 16.0
        sp = [([(prng.uniform(-0.05, 0.05), prng.uniform(-0.05, 0.05), z * 0.5) for z in range(int(H / 0.5) + 1)],
               [0.34 * (1 - z * 0.5 / H) ** 0.8 + 0.02 for z in range(int(H / 0.5) + 1)])]
        npts, nrot, nscl = [], [], []
        z = 1.8
        while z < H - 0.4:
            f = z / H
            nb = prng.randint(5, 7)
            L = 4.4 * (1 - f) ** 0.9 + 0.35
            for i in range(nb):
                a = i / nb * math.tau + prng.uniform(-0.3, 0.3) + z * 1.3
                d = Vector((math.cos(a), math.sin(a), 0))
                pts = []
                for s in range(9):
                    t = s / 8
                    pts.append(Vector((0, 0, z)) + d * L * t + Vector((0, 0, -0.35 * L * t * t + 0.12 * L * t * f)))
                sp.append(([tuple(p) for p in pts], [0.05 * (1 - t / 8) + 0.006 for t in range(9)]))
                steps = max(2, int(L / 0.17))
                for s in range(steps):
                    t = (s + 0.5) / steps
                    p = pts[min(8, int(t * 8))]
                    tang = (pts[min(8, int(t * 8) + 1)] - pts[max(0, int(t * 8) - 1)]).normalized()
                    lat = tang.cross(Vector((0, 0, 1))).normalized()
                    for sgn in (-1, 0, 1):
                        dd = (tang + lat * sgn * 0.9 + Vector((0, 0, prng.uniform(-0.3, 0.1)))).normalized()
                        npts.append(tuple(p + lat * sgn * 0.05))
                        nrot.append(euler_from_dir(dd, prng.uniform(-0.6, 0.6)))
                        nscl.append(0.26 * prng.uniform(0.8, 1.3) * (1 - 0.3 * t))
            z += prng.uniform(0.38, 0.55)
        for _ in range(60):                                          # leader tip
            p = Vector((prng.uniform(-0.2, 0.2), prng.uniform(-0.2, 0.2), H - prng.uniform(0, 1.2)))
            npts.append(tuple(p))
            nrot.append(euler_from_dir(Vector((prng.uniform(-1, 1), prng.uniform(-1, 1), 1.2)), prng.uniform(0, 6)))
            nscl.append(0.2)
        curve_obj(f"PineVar_{k}_Wood", sp, vc, bark, 2)
        scatter(f"PineVar_{k}_Needles", npts, nrot, nscl, [0.0] * len(npts), [0.0] * len(npts), needles, vc, wind=0.0)
        variants.append(vc)
    for i, (loc, h) in enumerate(pines):
        e = bpy.data.objects.new(f"Pine_{i:03d}", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = variants[i % 4]
        e.location = loc
        e.rotation_euler = (0, 0, rnd.uniform(0, math.tau))
        s = h / 16.0
        e.scale = (s * rnd.uniform(0.9, 1.1), s * rnd.uniform(0.9, 1.1), s)
        C["Vegetation"].objects.link(e)

    # --- grass (Geometry Nodes on a helper object that reads the terrain)
    gobj = mesh_obj("Grass_Scatter", [], [], C["Vegetation"], smooth=False)
    mod = gobj.modifiers.new("Grass", "NODES")
    mod.node_group = gn_grass_group()
    set_mod_inputs(mod, {"Ground": terrain, "Tufts": tufts, "Wild": wild, "Density": GRASS_DENSITY})

    # --- birds (7): bodies + flapping wings driven by expressions, keyed flight paths
    bird_mat = mat_simple("MAT_Bird", lin("#2a221c"), 0.7)
    bv, bf = wf.icosphere(2)
    body_v = [(x * 0.07, y * 0.2, z * 0.06) for x, y, z in bv]
    wing_v = [(0, 0.06, 0), (0, -0.07, 0), (0.42, -0.12, 0.01), (0.55, -0.02, 0.02), (0.3, 0.05, 0.005)]
    wing_f = [(0, 1, 2, 4), (4, 2, 3)]
    flocks = [((-90, 70, 30), (10, 60, 46), (110, 85, 40), -1, 19, 3, 3.5),
              ((120, 110, 50), (0, 120, 58), (-110, 95, 36), 3, 18, 2, 4.0),
              ((-160, 140, 70), (20, 160, 80), (160, 130, 62), 6, 16, 2, 3.0)]
    bi = 0
    for (a, m, c, t0, dur, n, spread) in flocks:
        for _ in range(n):
            off = Vector((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), rnd.uniform(-spread * 0.4, spread * 0.4)))
            path = catmull3([Vector((mx(a[0]), a[1], a[2])) + off, Vector((mx(m[0]), m[1], m[2])) + off,
                             Vector((mx(c[0]), c[1], c[2])) + off], 60)
            body = mesh_obj(f"Bird_{bi}", body_v, bf, C["Birds"])
            assign(body, bird_mat)
            body.scale = (1.6, 1.6, 1.6)
            ph, fr = rnd.uniform(0, 50), rnd.uniform(0.62, 0.8)
            for sgn in (1, -1):
                wing = mesh_obj(f"Bird_{bi}_Wing{'L' if sgn > 0 else 'R'}", [(x * sgn, y, z) for x, y, z in wing_v], wing_f, C["Birds"])
                assign(wing, bird_mat)
                wing.parent = body
                fc = wing.driver_add("rotation_euler", 1)
                fc.driver.expression = f"{sgn} * sin((frame + {ph:.1f}) * {fr:.3f}) * 0.6"
            t0b, durb = t0 + rnd.uniform(-0.6, 0.6), dur * rnd.uniform(0.95, 1.05)
            for fr_ in range(1, FRAMES + 1, 2):
                u = min(max(((fr_ - 1) / FPS - t0b) / durb, 0.0), 1.0)
                k = min(int(u * (len(path) - 1)), len(path) - 2)
                p, q = path[k], path[k + 1]
                body.location = p
                vel = q - p
                body.rotation_euler = (0.0, 0.0, math.atan2(vel.y, vel.x) - math.pi / 2)
                body.keyframe_insert("location", frame=fr_)
                body.keyframe_insert("rotation_euler", frame=fr_)
            bi += 1

    # --- camera: eased glide forward + rise, DOF on the mid-ground
    cam = bpy.data.objects["CAM_Main"]
    cam.data.sensor_width = 36.0
    cam.data.lens = wf.CAM_LENS
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = FSTOP
    cam.data.dof.aperture_blades = 7
    pos_path = catmull3([(0, -2, 1.8), (mx(0.8), 10, 3.2), (mx(3.5), 24, 6.2), (mx(6.5), 34, 9.5), (mx(8), 40, 12)], 60)
    tgt_path = catmull3([(0, 100, 12.3), (mx(4), 100, 12.5), (mx(12), 100, 13.5), (mx(18), 100, 14), (mx(20), 100, 13)], 60)

    def sample(path, u):
        x = u * (len(path) - 1)
        k = min(int(x), len(path) - 2)
        return path[k].lerp(path[k + 1], x - k)

    prev = None
    for fr_ in range(1, FRAMES + 1):
        t = (fr_ - 1) / (FRAMES - 1)
        u = t * t * t * (t * (t * 6 - 15) + 10)
        p, q = sample(pos_path, u), sample(tgt_path, u)
        cam.location = p
        prev = (q - p).to_track_quat("-Z", "Y").to_euler("XYZ", prev) if prev else (q - p).to_track_quat("-Z", "Y").to_euler()
        cam.rotation_euler = prev
        cam.data.dof.focus_distance = 22.0 + 14.0 * u
        cam.keyframe_insert("location", frame=fr_)
        cam.keyframe_insert("rotation_euler", frame=fr_)
        cam.data.dof.keyframe_insert("focus_distance", frame=fr_)

    # --- hide the asset library from direct rendering
    vl.layer_collection.children["_Assets"].exclude = True
    setup_render(scene, final=True)
    setup_compositor(scene)
    return scene


def setup_render(scene, final=True):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
    r.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAMES
    cy = scene.cycles
    cy.samples = SAMPLES_FINAL if final else SAMPLES_PREVIEW
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    for k, v in (("max_bounces", 8), ("diffuse_bounces", 3), ("glossy_bounces", 3), ("transmission_bounces", 8),
                 ("volume_bounces", 1), ("transparent_max_bounces", 24), ("caustics_reflective", False),
                 ("caustics_refractive", False), ("blur_glossy", 1.0), ("volume_step_rate", 2.0), ("volume_max_steps", 256)):
        try:
            setattr(cy, k, v)
        except Exception:
            pass
    r.use_motion_blur = MOTION_BLUR
    r.motion_blur_shutter = 0.5
    r.use_persistent_data = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.compression = 15
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = EXPOSURE


def setup_compositor(scene):
    """Glare (fog glow) + subtle chromatic aberration. Grain, vignette and grade come from ffmpeg."""
    try:
        scene.use_nodes = True
        nt = scene.node_tree
        nt.nodes.clear()
        b = NB(nt)
        rl = b.n("CompositorNodeRLayers")
        gl = b.n("CompositorNodeGlare")
        for k, v in (("glare_type", "FOG_GLOW"), ("quality", "HIGH"), ("threshold", 1.2), ("size", 7), ("mix", -0.8)):
            try:
                setattr(gl, k, v)
            except Exception:
                pass
        ld = b.n("CompositorNodeLensdist")
        try:
            ld.use_fit = True
        except Exception:
            pass
        b.setin(ld, ("Dispersion",), 0.01)
        comp = b.n("CompositorNodeComposite")
        b.link(rl.outputs["Image"], gl.inputs["Image"])
        b.link(gl.outputs["Image"], ld.inputs["Image"])
        b.link(ld.outputs["Image"], comp.inputs["Image"])
    except Exception as ex:
        print("WARN compositor skipped:", ex)


def enable_gpu(scene):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = dev
            except TypeError:
                continue
            for fn in ("refresh_devices", "get_devices"):
                if hasattr(prefs, fn):
                    getattr(prefs, fn)()
                    break
            gpus = [d for d in prefs.devices if d.type == dev]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == dev
                scene.cycles.device = "GPU"
                print("GPU:", dev, [d.name for d in gpus])
                return dev
    except Exception as ex:
        print("WARN gpu:", ex)
    print("GPU not found - rendering on CPU")
    return "CPU"


def main():
    scene = build()
    save = arg("--save")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save))
        print("saved", save)
    still = arg("--still", None, int)
    if still:
        enable_gpu(scene)
        if arg("--preview"):
            scene.render.resolution_percentage = 50
            scene.cycles.samples = SAMPLES_PREVIEW
        scene.frame_set(still)
        scene.render.filepath = os.path.abspath(arg("--out", f"still_{still:04d}.png"))
        bpy.ops.render.render(write_still=True)
        print("rendered", scene.render.filepath)


if __name__ == "__main__":
    main()
