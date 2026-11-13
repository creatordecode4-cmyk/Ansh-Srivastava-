"""
Stylized Luxury Blue Palace  -  headless Blender (bpy) scene builder.

Run:   python3 build_palace.py                  (full scene, 3 renders, .blend, .glb)
       python3 build_palace.py --stage 1 --preview   (palace only, quick check)
       python3 build_palace.py --time night     (day | sunset | night)

Everything you normally want to change lives in CONFIG just below.
Units are meters. +Z up, the palace front faces -Y.
"""
import bpy, bmesh, sys, os, math, random, argparse, time
from math import pi, sin, cos, radians, hypot
from mathutils import Matrix, Vector

# --------------------------------------------------------------------------
# CONFIG  (colors, sizes, time of day - edit here)
# --------------------------------------------------------------------------
CONFIG = {
    "colors": {                      # sRGB hex
        "wall_low":   "#06208A",     # royal blue, bottom of gradient
        "wall_high":  "#1A4CD6",     # royal blue, top of gradient
        "gold":       "#F2B632",
        "marble":     "#F3ECDD",
        "stone_path": "#E2D3B5",
        "window":     "#FFC65A",
        "water":      "#19D3CF",
        "pool_tile":  "#7FE9E0",
        "lawn":       "#86D958",
        "terrain":    "#74C760",
        "bush":       "#2F8F3B",
        "cypress":    "#1F6B3A",
        "palm_leaf":  "#3FA846",
        "trunk":      "#8A6240",
        "bronze":     "#3A2C22",
        "cushion":    "#FF6F61",
        "flowers":    ["#FF4F8B", "#FFD23F", "#FFFFFF", "#E0392B", "#B565E0"],
    },
    "palace": {"width": 120.0, "depth": 60.0, "dome_top": 45.0},
    "pool_main": {"size": (70.0, 36.0), "center": (0.0, -82.0)},
    "pool_side": {"size": (26.0, 30.0), "center": (66.0, -82.0)},   # mirrored on X
    "channel":   {"width": 6.0, "y0": -158.0, "y1": -103.0},
    "wall":      {"x": 108.0, "y_front": -170.0, "y_back": 52.0},
    "time_of_day": "sunset",
    "outline": False,                # Freestyle toon outline (slower)
    "render": {"res": (1920, 1080), "samples": 32},
}

TIMES = {   # sun elevation/azimuth in degrees, azimuth measured from -Y (front) toward -X
    "sunset": dict(elev=24, azim=38, sun_col="#FFB878", sun_str=4.8, sky=("#FFB36B", "#FF8FA0", "#6C7FD8", "#27358F"),
                   sky_str=1.35, glow=2.6, lamp=1.0, exposure=0.0),
    "day":    dict(elev=48, azim=30, sun_col="#FFF3DC", sun_str=4.5, sky=("#DDF1FF", "#A8D8FF", "#5CA8F5", "#2E6FD6"),
                   sky_str=1.1, glow=1.0, lamp=0.15, exposure=-0.3),
    "night":  dict(elev=30, azim=-40, sun_col="#8FA8FF", sun_str=0.35, sky=("#2B3A7A", "#1B2559", "#0D1436", "#060A1E"),
                   sky_str=0.5, glow=4.0, lamp=2.2, exposure=0.6),
}

HERE = os.path.dirname(os.path.abspath(__file__))
C = CONFIG["colors"]

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def hex_rgb(h):
    """sRGB hex -> linear RGBA tuple."""
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


COLL = {}
def collection(name):
    if name not in COLL:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLL[name] = c
    return COLL[name]


MATS = {}
def mat(name, color, rough=0.5, metal=0.0, emit=None, emit_str=0.0, alpha=1.0):
    """Simple flat Principled material. Reused by name."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    rgba = hex_rgb(color) if isinstance(color, str) else color
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = hex_rgb(emit)
        b.inputs["Emission Strength"].default_value = emit_str
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "DITHERED"
    m.diffuse_color = rgba
    m["flat_rgba"] = list(rgba)          # used when exporting GLB
    MATS[name] = m
    return m


def smooth_profile(p, sub=3):
    """Catmull-Rom resample of a lathe profile [(r, z), ...]."""
    out = []
    for i in range(len(p) - 1):
        p0, p1, p2, p3 = p[max(i - 1, 0)], p[i], p[i + 1], p[min(i + 2, len(p) - 1)]
        for k in range(sub):
            t = k / sub
            pt = []
            for j in (0, 1):
                pt.append(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t
                                 + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3))
            out.append((max(pt[0], 0.0), pt[1]))
    out.append(p[-1])
    return out


def arch_pts(w, h, n=7, x0=0.0, z0=0.0):
    """Pointed (Mughal) arch outline in the XZ plane, counter-clockwise from bottom-left."""
    c, R = w / 4.0, 0.75 * w
    rise = math.sqrt(R * R - c * c)
    hs = max(h - rise, 0.05)
    amax = math.acos(c / R)
    pts = [(-w / 2, 0.0), (w / 2, 0.0)]
    for i in range(n + 1):
        a = amax * i / n
        pts.append((-c + R * cos(a), hs + R * sin(a)))
    for i in range(n - 1, -1, -1):
        a = amax * i / n
        pts.append((c - R * cos(a), hs + R * sin(a)))
    return [(x + x0, z + z0) for x, z in pts]


ONION = smooth_profile([(0.90, 0.0), (1.0, 0.07), (1.10, 0.28), (1.13, 0.50), (1.06, 0.72), (0.90, 0.92),
                        (0.64, 1.10), (0.38, 1.25), (0.18, 1.38), (0.06, 1.50), (0.0, 1.56)], 3)
FINIAL = [(0.0, 0.0), (0.55, 0.0), (0.95, 0.45), (0.55, 0.95), (0.28, 1.15), (0.62, 1.6), (0.28, 2.1),
          (0.14, 2.35), (0.36, 2.75), (0.12, 3.2), (0.06, 4.4), (0.0, 5.0)]


class MB:
    """Tiny mesh builder: collect boxes / lathes / prisms with materials, then make one object."""

    def __init__(self, name):
        self.name, self.v, self.f, self.fm, self.mats = name, [], [], [], []
        self.M = Matrix.Identity(4)

    def at(self, x=0.0, y=0.0, z=0.0, rot=0.0):
        """Set the local frame for following primitives (translation + rotation about Z)."""
        self.M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, "Z")
        return self

    def _add(self, verts, faces, m):
        if m not in self.mats:
            self.mats.append(m)
        mi, b = self.mats.index(m), len(self.v)
        self.v += [tuple(self.M @ Vector(p)) for p in verts]
        self.f += [tuple(i + b for i in f) for f in faces]
        self.fm += [mi] * len(faces)

    def box(self, x0, x1, y0, y1, z0, z1, m):
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self._add(v, f, m)

    def cbox(self, cx, cy, sx, sy, z0, z1, m):
        self.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z1, m)

    def lathe(self, prof, m, segs=16, cx=0.0, cy=0.0, z=0.0, sr=1.0, sz=1.0, phase=0.0):
        v, f, rings = [], [], []
        for r, pz in prof:
            if r * sr < 1e-5:
                rings.append([len(v)])
                v.append((cx, cy, z + pz * sz))
            else:
                rings.append(list(range(len(v), len(v) + segs)))
                for k in range(segs):
                    a = phase + 2 * pi * k / segs
                    v.append((cx + r * sr * cos(a), cy + r * sr * sin(a), z + pz * sz))
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for k in range(segs):
                k2 = (k + 1) % segs
                if len(a) == 1:
                    f.append((a[0], b[k], b[k2]))
                elif len(b) == 1:
                    f.append((a[k], a[k2], b[0]))
                else:
                    f.append((a[k], a[k2], b[k2], b[k]))
        self._add(v, f, m)

    def cyl(self, cx, cy, z0, z1, r, m, segs=16, r2=None, phase=0.0):
        r2 = r if r2 is None else r2
        self.lathe([(0, z0), (r, z0), (r2, z1), (0, z1)], m, segs, cx, cy, phase=phase)

    def prism(self, pts, y0, y1, m):
        """Extrude an XZ outline along Y."""
        n = len(pts)
        v = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
        f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        self._add(v, f, m)

    def finish(self, coll, bevel=0.0, bsegs=2, smooth_angle=38, loc=None, rotz=0.0):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.v, [], self.f)
        for m in self.mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.fm)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.set_sharp_from_angle(angle=radians(smooth_angle))
        me.update()
        ob = bpy.data.objects.new(self.name, me)
        collection(coll).objects.link(ob)
        if loc:
            ob.location = loc
        ob.rotation_euler[2] = rotz
        if bevel > 0:
            md = ob.modifiers.new("Bevel", "BEVEL")
            md.width, md.segments = bevel, bsegs
            md.limit_method, md.angle_limit = "ANGLE", radians(40)
        return ob


def mirror(ob, x=True, y=False):
    """Mirror modifier around the world origin (objects are built in world coords)."""
    md = ob.modifiers.new("Mirror", "MIRROR")
    md.use_axis = (x, y, False)
    md.use_mirror_merge = False
    return ob


def array(ob, count, offset):
    md = ob.modifiers.new("Array", "ARRAY")
    md.count = max(int(count), 1)
    md.use_relative_offset, md.use_constant_offset = False, True
    md.constant_offset_displace = offset
    return ob


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
def make_materials(tod):
    M = {}
    # blue wall: vertical gradient + soft tile pattern
    w = mat("MAT_Wall_Blue", C["wall_low"], rough=0.55)
    nt = w.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.0, 32.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hex_rgb(C["wall_low"])
    ramp.color_ramp.elements[1].color = hex_rgb(C["wall_high"])
    mapn = nt.nodes.new("ShaderNodeMapping")
    mapn.inputs["Location"].default_value = (0.37, 0.37, 0.41)
    mapn.inputs["Scale"].default_value = (0.5, 0.5, 0.5)       # 2 m tiles
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.0
    chk.inputs["Color1"].default_value = (1, 1, 1, 1)
    chk.inputs["Color2"].default_value = (0.80, 0.84, 0.92, 1)   # soft, low contrast
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    L = nt.links.new
    L(geo.outputs["Position"], sep.inputs[0]); L(sep.outputs["Z"], mr.inputs["Value"])
    L(mr.outputs["Result"], ramp.inputs["Fac"])
    L(geo.outputs["Position"], mapn.inputs["Vector"]); L(mapn.outputs["Vector"], chk.inputs["Vector"])
    L(ramp.outputs["Color"], mul.inputs[0]); L(chk.outputs["Color"], mul.inputs[1])
    L(mul.outputs["Vector"], bsdf.inputs["Base Color"])
    mid = [(a + b) / 2 for a, b in zip(hex_rgb(C["wall_low"]), hex_rgb(C["wall_high"]))]
    w["flat_rgba"] = mid
    M["wall"] = w

    M["gold"] = mat("MAT_Gold", C["gold"], rough=0.28, metal=0.85)
    M["marble"] = mat("MAT_Marble", C["marble"], rough=0.35)
    M["path"] = mat("MAT_Stone_Path", C["stone_path"], rough=0.6)
    M["glow"] = mat("MAT_Window_Glow", C["window"], rough=0.4, emit=C["window"], emit_str=tod["glow"])
    M["navy"] = mat("MAT_Recess_Navy", "#081A5C", rough=0.5)
    M["lamp"] = mat("MAT_Lamp_Glow", "#FFE2A8", emit="#FFD08A", emit_str=3.5 * max(tod["lamp"], 0.3))
    M["pool_light"] = mat("MAT_Pool_Light", "#D8FFF8", emit="#9FFFF0", emit_str=3.0 * max(tod["lamp"], 0.3))
    M["tile"] = mat("MAT_Pool_Tile", C["pool_tile"], rough=0.4)
    M["jet"] = mat("MAT_Fountain_Jet", "#E6FDFF", rough=0.2, emit="#A8F2FF", emit_str=0.6, alpha=0.55)

    # water: turquoise, semi transparent, simple wave bump
    wa = mat("MAT_Water", C["water"], rough=0.06, alpha=0.78)
    nt = wa.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.55
    noise.inputs["Detail"].default_value = 1.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    nt.links.new(noise.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    M["water"] = wa
    M["lake"] = mat("MAT_Lake", "#2FA7C9", rough=0.08)

    M["lawn"] = mat("MAT_Lawn", C["lawn"], rough=0.9)
    M["bush"] = mat("MAT_Bush", C["bush"], rough=0.85)
    M["cypress"] = mat("MAT_Cypress", C["cypress"], rough=0.85)
    M["leaf"] = mat("MAT_Palm_Leaf", C["palm_leaf"], rough=0.7)
    M["trunk"] = mat("MAT_Trunk", C["trunk"], rough=0.85)
    M["bronze"] = mat("MAT_Bronze", C["bronze"], rough=0.45, metal=0.6)
    M["cushion"] = mat("MAT_Cushion", C["cushion"], rough=0.8)
    M["white"] = mat("MAT_White", "#FAFAF5", rough=0.6)
    M["soil"] = mat("MAT_Flowerbed", "#3E7A35", rough=0.9)
    M["flowers"] = [mat(f"MAT_Flower_{i}", h, rough=0.6) for i, h in enumerate(C["flowers"])]

    # terrain: green, darker / bluer with height for far hills
    t = mat("MAT_Terrain", C["terrain"], rough=0.95)
    nt = t.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -3.0, 45.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].color, e[1].color = hex_rgb("#C9B57A"), hex_rgb("#3F8C6B")
    e[0].position = 0.0
    mid = ramp.color_ramp.elements.new(0.07)
    mid.color = hex_rgb(C["terrain"])
    nt.links.new(geo.outputs["Position"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"]); nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    M["terrain"] = t
    return M


# --------------------------------------------------------------------------
# reusable building blocks
# --------------------------------------------------------------------------
def build_dome(mb, x, y, z, radius, height, M, segs=24, finial=None, material=None):
    """Onion dome with collar ring and gold finial. `z` is the dome base."""
    m = material or M["gold"]
    mb.lathe([(0, 0), (radius * 1.02, 0), (radius * 1.08, 0.25 * radius * 0.2), (radius * 1.0, 0.1 * radius), (0, 0.1 * radius)],
             M["gold"], segs, x, y, z)                                   # collar
    mb.lathe(ONION, m, segs, x, y, z + 0.06 * radius, sr=radius, sz=height / 1.56)
    fs = finial if finial else radius * 0.2
    mb.lathe(FINIAL, M["gold"], 12, x, y, z + 0.06 * radius + height * 0.985, sr=fs, sz=fs)


def build_chhatri(mb, x, y, z, r, M, cols=8):
    """Small open pavilion: slab, ring of columns, sloped eave, onion dome."""
    mb.cyl(x, y, z, z + 0.35 * r / 2.5 + 0.2, r * 1.15, M["marble"], cols, phase=pi / cols)
    hc = r * 1.15
    z1 = z + 0.35 * r / 2.5 + 0.2
    for k in range(cols):
        a = 2 * pi * k / cols + pi / cols
        px, py = x + r * 0.9 * cos(a), y + r * 0.9 * sin(a)
        mb.cyl(px, py, z1, z1 + hc, r * 0.085, M["marble"], 8)
        mb.cyl(px, py, z1 + hc - 0.12 * r, z1 + hc, r * 0.13, M["gold"], 8)
    z2 = z1 + hc
    mb.lathe([(0, 0), (r * 1.45, 0), (r * 1.45, 0.07 * r), (r * 1.0, 0.3 * r), (0, 0.3 * r)], M["gold"], 16, x, y, z2)   # eave
    mb.cyl(x, y, z2 + 0.3 * r, z2 + 0.5 * r, r * 0.92, M["wall"], 16)                                                  # drum
    build_dome(mb, x, y, z2 + 0.5 * r, r * 0.9, r * 1.25, M, 16)
    return z2


def build_window(mb, x, z, w, h, M):
    """Arched glowing window with gold frame + sill. Facade-local: wall plane at y=0, facing -Y."""
    mb.prism(arch_pts(w + 0.7, h + 0.45, x0=x, z0=z - 0.1), -0.28, 0.1, M["gold"])
    mb.prism(arch_pts(w, h, x0=x, z0=z), -0.36, 0.0, M["glow"])
    mb.box(x - w / 2 - 0.6, x + w / 2 + 0.6, -0.55, 0.0, z - 0.45, z - 0.1, M["marble"])


def build_column(mb, x, y, z0, z1, r, M):
    """Round marble column with base and gold capital."""
    h = z1 - z0
    mb.cyl(x, y, z0, z0 + 0.45, r * 1.5, M["marble"], 12)
    mb.cyl(x, y, z0 + 0.45, z1 - 0.6, r, M["marble"], 12, r2=r * 0.85)
    mb.lathe([(r * 0.85, 0), (r * 1.1, 0.15), (r * 1.6, 0.6), (0, 0.6)], M["gold"], 12, x, y, z1 - 0.6)


def build_jharokha(mb, x, z, M, w=4.2):
    """Projecting balcony with brackets, railing, slim columns and a half-dome roof. Facade-local."""
    d = 2.0
    for i, s in enumerate((0.5, 1.0, 1.5)):                    # stepped bracket
        mb.box(x - w / 2 + 0.3, x + w / 2 - 0.3, -s - 0.2, 0, z - 1.2 + i * 0.4, z - 0.8 + i * 0.4, M["marble"])
    mb.box(x - w / 2, x + w / 2, -d, 0, z, z + 0.3, M["gold"])                      # floor slab
    mb.box(x - w / 2, x + w / 2, -d, -d + 0.2, z + 0.3, z + 1.2, M["marble"])       # railing front
    for sx in (-1, 1):
        mb.box(x + sx * w / 2 - (0.2 if sx > 0 else 0), x + sx * w / 2 + (0.2 if sx < 0 else 0), -d, 0, z + 0.3, z + 1.2, M["marble"])
    for cx in (x - w / 2 + 0.25, x - w / 6, x + w / 6, x + w / 2 - 0.25):
        mb.cyl(cx, -d + 0.25, z + 0.3, z + 3.6, 0.14, M["gold"], 8)
    mb.box(x - w / 2 - 0.4, x + w / 2 + 0.4, -d - 0.4, 0, z + 3.6, z + 3.95, M["gold"])  # eave
    mb.lathe(ONION, M["gold"], 16, x, -d / 2, z + 3.95, sr=w * 0.36, sz=1.6 / 1.56 * 1.3)
    mb.lathe(FINIAL, M["gold"], 8, x, -d / 2, z + 3.95 + 2.0, sr=0.22, sz=0.22)
    mb.prism(arch_pts(w - 1.6, 3.0, x0=x, z0=z + 0.3), -0.2, 0.0, M["glow"])         # door glow


def build_parapet(name, W, D, z, M, step=1.6):
    """Carved-look parapet: one rail+merlon unit repeated with an Array modifier on each roof edge."""
    edges = [((-W / 2, -D / 2 + 0.3, z), 0.0, W), ((W / 2 - 0.3, -D / 2, z), pi / 2, D),
             ((W / 2, D / 2 - 0.3, z), pi, W), ((-W / 2 + 0.3, D / 2, z), -pi / 2, D)]
    for i, (loc, rot, L) in enumerate(edges):
        mb = MB(f"{name}_{'FRBL'[i]}")
        mb.box(0, step, -0.25, 0.25, 0, 0.55, M["marble"])
        mb.prism(arch_pts(1.0, 1.25, n=4, x0=step / 2, z0=0.55), -0.2, 0.2, M["gold"])
        ob = mb.finish("Palace", bevel=0.05, bsegs=1, loc=loc, rotz=rot)
        array(ob, L / step, (step, 0, 0))


def build_tower(M, x, y, r=5.2, z_top=28.0):
    """Corner tower with gold bands, slim glowing windows, balcony ring and chhatri. Mirrored to 4 corners."""
    mb = MB("PAL_Tower_Corner")
    mb.cyl(x, y, 0, 1.2, r * 1.25, M["marble"], 16)
    mb.cyl(x, y, 1.2, z_top, r, M["wall"], 16, r2=r * 0.92)
    for zb in (3.0, 12.0, 20.0):
        mb.cyl(x, y, zb, zb + 0.6, r * 1.06, M["gold"], 16)
    for zf, h in ((5.0, 5.0), (13.6, 4.6), (21.2, 4.4)):
        for k in range(8):
            a = k * pi / 4
            mb.at(x, y, 0, a)
            rr = r * (1 - 0.08 * (zf + h / 2) / z_top) * cos(pi / 16)
            mb.prism(arch_pts(1.6, h + 0.35, n=4, z0=zf - 0.1), -rr - 0.16, -rr + 0.5, M["gold"])
            mb.prism(arch_pts(1.1, h, n=4, z0=zf), -rr - 0.24, -rr + 0.5, M["glow"])
    mb.at()
    mb.lathe([(r * 0.92, 0), (r * 1.35, 0.8), (r * 1.35, 1.2), (0, 1.2)], M["gold"], 16, x, y, z_top)       # balcony ring
    mb.lathe([(r * 1.3, 0), (r * 1.3, 0.9), (r * 1.2, 0.9), (r * 1.2, 0)], M["marble"], 16, x, y, z_top + 1.2)   # railing
    build_chhatri(mb, x, y, z_top + 1.2, r * 0.82, M)
    ob = mb.finish("Palace", bevel=0.06, bsegs=1)
    mirror(ob, x=True, y=True)
    return ob


def build_pool(name, cx, cy, sx, sy, M, mirror_x=False, steps_side=1):
    """Raised marble pool: outer step, border, tiled floor, entry steps, underwater lights + water object."""
    mb = MB(f"POOL_{name}_Basin")
    b = 1.8
    mb.cbox(cx, cy, sx + 2 * b + 5, sy + 2 * b + 5, 0, 0.22, M["marble"])             # outer step
    mb.cbox(cx, cy, sx, sy, 0.22, 0.3, M["tile"])                                      # floor
    for s in (-1, 1):                                                                  # border ring
        mb.cbox(cx, cy + s * (sy / 2 + b / 2), sx + 2 * b, b, 0.22, 0.75, M["marble"])
        mb.cbox(cx + s * (sx / 2 + b / 2), cy, b, sy, 0.22, 0.75, M["marble"])
    yb = cy + steps_side * sy / 2                                                      # entry steps into the water
    for i, top in enumerate((0.62, 0.5, 0.38)):
        mb.cbox(cx, yb - steps_side * (0.5 + i * 0.9), 7.0, 0.9, 0.3, top, M["marble"])
    for sgn in (-1, 1):                                                                # gold handrail posts
        mb.cyl(cx + sgn * 3.6, yb - steps_side * 0.2, 0.75, 1.7, 0.07, M["gold"], 8)
        mb.cyl(cx + sgn * 3.6, yb - steps_side * 0.2, 1.7, 1.86, 0.16, M["gold"], 8)
    n = max(int(sx // 8), 2)                                                           # underwater lights
    for i in range(n):
        lx = cx - sx / 2 + (i + 0.5) * sx / n
        for s in (-1, 1):
            mb.cyl(lx, cy + s * (sy / 2 - 0.9), 0.3, 0.36, 0.42, M["pool_light"], 10)
    for k in range(4):                                                                 # gold corner urns
        ux, uy = cx + (sx / 2 + b / 2) * (1 if k % 2 else -1), cy + (sy / 2 + b / 2) * (1 if k < 2 else -1)
        mb.lathe([(0.3, 0), (0.55, 0.3), (0.3, 0.7), (0.5, 0.95), (0, 0.95)], M["gold"], 10, ux, uy, 0.75)
    basin = mb.finish("Pools", bevel=0.06, bsegs=2)
    wb = MB(f"POOL_{name}_Water")
    wb.cbox(cx, cy, sx, sy, 0.3, 0.58, M["water"])
    water = wb.finish("Pools")
    if mirror_x:
        mirror(basin); mirror(water)
    return basin, water


def build_fountain(mb, x, y, z, s, M):
    mb.lathe([(0, 0), (0.9, 0), (0.75, 0.3), (0.25, 0.5), (0.25, 1.0), (1.3, 1.25), (1.4, 1.45), (0, 1.32)], M["marble"], 12, x, y, z, s, s)
    mb.lathe([(0.3, 1.45), (0.2, 1.6), (0, 1.6)], M["gold"], 8, x, y, z, s, s)
    mb.lathe([(0.06, 1.5), (0.08, 2.7), (0.22, 2.85), (0.5, 2.6), (0.78, 2.0), (0.9, 1.42)], M["jet"], 10, x, y, z, s, s)


def build_palm(mb, x, y, h, rng, M):
    lean_a, lean = rng.uniform(0, 2 * pi), rng.uniform(0.3, 1.2)
    n = 6
    tx = ty = 0.0
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        ox, oy = x + lean * cos(lean_a) * t0 ** 2, y + lean * sin(lean_a) * t0 ** 2
        mb.cyl(ox, oy, h * t0, h * t1 + 0.05, 0.42 - 0.18 * t0, M["trunk"], 8, r2=0.48 - 0.18 * t1)
        tx, ty = x + lean * cos(lean_a) * t1 ** 2, y + lean * sin(lean_a) * t1 ** 2
    mb.lathe([(0, -0.3), (0.5, 0), (0.4, 0.4), (0, 0.6)], M["trunk"], 8, tx, ty, h)
    nf, L = 9, 0.42 * h + 1.2
    a0 = rng.uniform(0, 1)
    for k in range(nf):
        a = a0 + 2 * pi * k / nf
        d, p = Vector((cos(a), sin(a), 0)), Vector((-sin(a), cos(a), 0))
        droop = rng.uniform(0.75, 1.15)
        verts, faces = [], []
        m = 5
        for j in range(m + 1):
            t = j / m
            c = Vector((tx, ty, h + 0.3)) + d * (L * t) + Vector((0, 0, 1.3 * sin(t * pi * 0.75) - 2.6 * droop * t * t))
            wdt = 0.95 * (1 - t) ** 0.55 * (0.35 + 0.65 * min(1.0, t * 4))
            verts += [c - p * wdt - Vector((0, 0, 0.25 * wdt)), c + Vector((0, 0, 0.12)), c + p * wdt - Vector((0, 0, 0.25 * wdt))]
        for j in range(m):
            b = j * 3
            faces += [(b, b + 3, b + 4, b + 1), (b + 1, b + 4, b + 5, b + 2)]
        mb._add([tuple(v) for v in verts], faces, M["leaf"])


def build_cypress(mb, x, y, h, M):
    s = h / 10.5
    mb.cyl(x, y, 0, 1.2 * s, 0.25 * s, M["trunk"], 6)
    mb.lathe(smooth_profile([(0, 0.8), (0.9, 1.1), (1.25, 3), (1.05, 6), (0.55, 9), (0, 10.5)], 2), M["cypress"], 10, x, y, 0, s * 1.15, s)


def build_bush(mb, x, y, r, M, m=None):
    mb.lathe([(0, 0), (0.85, 0.12), (1.1, 0.65), (0.92, 1.25), (0.45, 1.65), (0, 1.75)], m or M["bush"], 10, x, y, 0, r, r)


def build_flower_patch(mb, x, y, r, rng, M):
    mb.lathe([(0, 0), (r, 0), (r, 0.18), (r * 0.6, 0.38), (0, 0.45)], M["soil"], 16, x, y, 0.05)
    mb.lathe([(r, 0), (r + 0.35, 0), (r + 0.35, 0.3), (r, 0.3)], M["marble"], 16, x, y, 0.05)
    for _ in range(int(r * r * 2.2)):
        a, d = rng.uniform(0, 2 * pi), r * 0.92 * math.sqrt(rng.random())
        fz = 0.2 + 0.25 * (1 - d / r)
        mb.lathe([(0, 0), (0.26, 0.1), (0.26, 0.3), (0, 0.42)], rng.choice(M["flowers"]), 6, x + d * cos(a), y + d * sin(a), fz)


def build_lamp(mb, x, y, M, h=4.4):
    mb.lathe([(0.32, 0), (0.32, 0.25), (0.13, 0.5), (0.1, h), (0, h)], M["bronze"], 8, x, y, 0.1)
    mb.lathe([(0.1, 0), (0.28, 0.12), (0.1, 0.25)], M["gold"], 8, x, y, h)
    mb.lathe([(0, 0), (0.3, 0.1), (0.42, 0.42), (0.3, 0.74), (0, 0.84)], M["lamp"], 10, x, y, h + 0.25)
    mb.lathe([(0.2, 0), (0.05, 0.15), (0, 0.4)], M["gold"], 8, x, y, h + 1.05)


def build_lounger(mb, x, y, rot, M):
    mb.at(x, y, 0.12, rot)
    mb.prism([(0, 0.3), (1.35, 0.3), (2.05, 0.95), (1.97, 1.05), (1.3, 0.47), (0, 0.47)], -0.38, 0.38, M["cushion"])
    mb.prism([(-0.05, 0.2), (1.4, 0.2), (1.4, 0.3), (-0.05, 0.3)], -0.42, 0.42, M["white"])
    for lx in (0.1, 1.25):
        for ly in (-0.36, 0.36):
            mb.cbox(lx, ly, 0.08, 0.08, 0, 0.2, M["white"])
    mb.at()


def build_umbrella(mb, x, y, M, m=None):
    mb.cyl(x, y, 0.12, 2.9, 0.06, M["white"], 6)
    mb.cyl(x, y, 0.12, 0.3, 0.35, M["white"], 10)
    mb.lathe([(0, 2.55), (1.9, 2.25), (1.9, 2.15), (0, 2.95)][::-1], m or M["cushion"], 8, x, y, 0.1)
    mb.lathe([(0, 0), (0.1, 0.1), (0, 0.25)], M["gold"], 6, x, y, 3.0)


# --------------------------------------------------------------------------
# STAGE 1  -  palace
# --------------------------------------------------------------------------
def build_palace(M):
    P = CONFIG["palace"]
    W, D = P["width"], P["depth"]
    tiers = [(W, D, 3.0, 12.0), (W - 20, D - 14, 12.6, 20.0), (W - 44, D - 28, 20.6, 27.0)]   # (w, d, z0, z1)

    # plinth + main volumes
    mb = MB("PAL_Plinth")
    mb.cbox(0, 0, W + 16, D + 16, 0, 1.0, M["marble"])
    mb.cbox(0, 0, W + 12, D + 12, 1.0, 3.0, M["marble"])
    mb.cbox(0, 0, W + 12.4, D + 12.4, 2.5, 2.8, M["gold"])
    mb.finish("Palace", bevel=0.15)

    mb = MB("PAL_Main_Body")
    for w, d, z0, z1 in tiers:
        mb.cbox(0, 0, w, d, z0, z1, M["wall"])
    mb.finish("Palace", bevel=0.2)

    mb = MB("PAL_Cornices")
    for i, (w, d, z0, z1) in enumerate(tiers):
        mb.cbox(0, 0, w + 2.4, d + 2.4, z1, z1 + 0.6, M["gold"])            # cornice slab over each floor
        mb.cbox(0, 0, w + 1.2, d + 1.2, z1 + 0.5, z1 + 0.66, M["marble"])   # marble terrace floor
        mb.cbox(0, 0, w + 0.5, d + 0.5, z0, z0 + 0.7, M["marble"])          # base band
        mb.cbox(0, 0, w + 0.3, d + 0.3, z1 - 1.3, z1 - 0.9, M["gold"])      # frieze line
    mb.finish("Palace", bevel=0.1)

    # windows, columns and jharokhas, floor by floor
    win = [(2.6, 5.0, 1.9), (2.4, 4.4, 1.5), (2.2, 3.8, 1.3)]       # (w, h, sill height) per floor
    jx = {1: (-39.0, -21.0, 21.0, 39.0), 2: (-15.0, 15.0)}          # jharokha x positions (must sit on the 6 m window grid)
    wm, cm, jm = MB("PAL_Windows"), MB("PAL_Columns"), MB("PAL_Jharokhas")
    for fi, (w, d, z0, z1) in enumerate(tiers):
        ww, wh, sill = win[fi]
        facades = [(0, -d / 2, 0.0, w), (w / 2, 0, pi / 2, d), (0, d / 2, pi, w), (-w / 2, 0, -pi / 2, d)]
        for si, (fx, fy, rot, L) in enumerate(facades):
            n = int((L - 8) // 6)
            xs = [(-n / 2 + k) * 6.0 for k in range(n + 1)]
            for m_ in (wm, cm, jm):
                m_.at(fx, fy, 0, rot)
            for x in xs:
                if si == 0 and fi < 2 and abs(x) < 14:              # entrance portal takes this space
                    continue
                if si == 0 and any(abs(x - j) < 0.1 for j in jx.get(fi, ())):
                    build_jharokha(jm, x, z0 + sill - 0.3, M)
                    continue
                build_window(wm, x, z0 + sill, ww, wh, M)
            if fi < 2:                                              # colonnade under the cornice
                for x in [xx + 3.0 for xx in xs[:-1]] + [xs[0] - 3.0, xs[-1] + 3.0]:
                    if si == 0 and abs(x) < 13:
                        continue
                    build_column(cm, x, -0.75, z0, z1, 0.42, M)
    assert jm.f, "no jharokhas were placed - check jx against the window grid"
    wm.finish("Palace", bevel=0.04, bsegs=1)
    cm.finish("Palace")
    jm.finish("Palace", bevel=0.04, bsegs=1)

    # parapets (Array modifier)
    for i, (w, d, z0, z1) in enumerate(tiers):
        build_parapet(f"PAL_Parapet_F{i + 1}", w + 2.0, d + 2.0, z1 + 0.6, M)

    # entrance portal (pishtaq) + gate arch
    fy = -D / 2
    mb = MB("PAL_Entrance_Portal")
    mb.box(-12, 12, fy - 4, fy + 1, 3.0, 21.0, M["wall"])
    mb.box(-12.4, 12.4, fy - 4.4, fy + 1, 21.0, 21.7, M["gold"])
    mb.box(-12.3, 12.3, fy - 4.3, fy + 1, 3.0, 3.8, M["marble"])
    mb.at(0, fy - 4, 0)
    mb.prism(arch_pts(15.5, 15.6, n=10, z0=3.6), -0.45, 0.2, M["gold"])          # big gold arch frame
    mb.prism(arch_pts(14.0, 14.6, n=10, z0=3.8), -0.6, 0.2, M["navy"])           # recess
    mb.prism(arch_pts(8.6, 10.2, n=8, z0=3.8), -0.85, 0.2, M["gold"])            # door frame
    mb.prism(arch_pts(7.4, 9.4, n=8, z0=3.8), -1.0, 0.2, M["glow"])              # glowing gate
    for sx in (-1, 1):                                                            # gold border strips + side niches
        mb.box(sx * 11.2 - 0.35, sx * 11.2 + 0.35, -0.3, 0.2, 3.8, 20.4, M["gold"])
        for zz in (5.0, 10.2, 15.4):
            mb.prism(arch_pts(1.5, 3.6, n=4, x0=sx * 9.4, z0=zz), -0.3, 0.2, M["glow"])
    mb.box(-11.5, 11.5, -0.3, 0.2, 19.7, 20.4, M["gold"])
    mb.at()
    for sx in (-1, 1):                                                            # slim engaged minarets
        mb.cyl(sx * 12.6, fy - 4.2, 3.0, 24.0, 1.15, M["marble"], 12, r2=0.95)
        for zb in (9.0, 15.0, 21.0):
            mb.cyl(sx * 12.6, fy - 4.2, zb, zb + 0.4, 1.3, M["gold"], 12)
        build_chhatri(mb, sx * 12.6, fy - 4.2, 24.0, 1.5, M, cols=6)
    mb.finish("Palace", bevel=0.08)
    build_parapet("PAL_Parapet_Portal", 22.0, 4.0, 21.7, M)
    for o in bpy.data.objects:
        if o.name.startswith("PAL_Parapet_Portal"):
            o.location.y += fy - 1.6

    # entrance staircase
    mb = MB("PAL_Entrance_Stairs")
    y0, steps, rise, run, sw = -(D + 12) / 2, 10, 0.3, 0.75, 22.0
    for i in range(steps):
        mb.box(-sw / 2, sw / 2, y0 - (i + 1) * run, y0 + 0.2, 0, 3.0 - i * rise, M["marble"])
    for sx in (-1, 1):
        mb.box(sx * (sw / 2 + 0.7) - 0.7, sx * (sw / 2 + 0.7) + 0.7, y0 - steps * run - 0.6, y0 + 0.2, 0, 3.9, M["marble"])
        mb.box(sx * (sw / 2 + 0.7) - 0.8, sx * (sw / 2 + 0.7) + 0.8, y0 - steps * run - 0.7, y0 + 0.2, 3.9, 4.15, M["gold"])
        mb.lathe([(0, 0), (0.5, 0.1), (0.75, 0.75), (0.5, 1.4), (0, 1.5)], M["lamp"], 12, sx * (sw / 2 + 0.7), y0 - steps * run + 0.3, 4.15)
    mb.box(-3.2, 3.2, y0 - steps * run - 0.05, y0 + 0.2, 0.02, 3.03, mat("MAT_Carpet", "#B3202E", rough=0.9))   # red carpet strip
    mb.finish("Palace", bevel=0.05, bsegs=1)

    # main dome
    top = P["dome_top"]
    zr = tiers[2][3] + 0.6
    mb = MB("PAL_Dome_Main")
    mb.cyl(0, 0, zr, zr + 1.0, 14.0, M["marble"], 32)
    mb.cyl(0, 0, zr + 1.0, zr + 5.0, 12.9, M["wall"], 32)
    mb.cyl(0, 0, zr + 4.3, zr + 5.0, 13.4, M["gold"], 32)
    for k in range(12):
        mb.at(0, 0, 0, k * pi / 6)
        mb.prism(arch_pts(2.3, 3.0, n=5, z0=zr + 1.3), -13.2, -12.5, M["gold"])
        mb.prism(arch_pts(1.7, 2.6, n=5, z0=zr + 1.4), -13.3, -12.5, M["glow"])
    mb.at()
    dome_h = top - (zr + 5.0) - 0.06 * 13.2
    build_dome(mb, 0, 0, zr + 5.0, 13.2, dome_h, M, segs=40, finial=1.25)
    mb.finish("Palace", bevel=0.06, bsegs=1)

    # two smaller domes (Mirror modifier) + roof chhatris (Mirror X+Y)
    mb = MB("PAL_Dome_Side")
    sx_ = 26.5
    mb.cyl(sx_, 0, zr, zr + 0.8, 7.0, M["marble"], 24)
    mb.cyl(sx_, 0, zr + 0.8, zr + 3.6, 5.9, M["wall"], 24)
    mb.cyl(sx_, 0, zr + 3.0, zr + 3.6, 6.2, M["gold"], 24)
    for k in range(8):
        mb.at(sx_, 0, 0, k * pi / 4)
        mb.prism(arch_pts(1.3, 2.0, n=4, z0=zr + 1.0), -6.2, -5.6, M["glow"])
    mb.at()
    build_dome(mb, sx_, 0, zr + 3.6, 6.0, 7.2, M, segs=28, finial=0.75)
    mirror(mb.finish("Palace", bevel=0.05, bsegs=1))

    mb = MB("PAL_Roof_Chhatris")
    build_chhatri(mb, tiers[2][0] / 2 - 2.5, tiers[2][1] / 2 - 2.5, zr, 1.9, M)       # 3rd floor roof corners
    build_chhatri(mb, tiers[1][0] / 2 - 3.5, tiers[1][1] / 2 - 3.0, tiers[1][3] + 0.6, 2.3, M)   # 2nd floor terrace corners
    mirror(mb.finish("Palace", bevel=0.04, bsegs=1), x=True, y=True)

    # four corner towers (one mesh, Mirror X+Y)
    build_tower(M, W / 2 + 1.0, D / 2 + 1.0)


# --------------------------------------------------------------------------
# STAGE 2  -  pools, channel, fountains
# --------------------------------------------------------------------------
def build_pools(M):
    pm, ps, ch = CONFIG["pool_main"], CONFIG["pool_side"], CONFIG["channel"]
    (mx, my), (msx, msy) = pm["center"], pm["size"]
    build_pool("Main", mx, my, msx, msy, M, steps_side=1)
    build_pool("Side", ps["center"][0], ps["center"][1], ps["size"][0], ps["size"][1], M, mirror_x=True, steps_side=1)

    # central channel from the gate plaza to the main pool
    cw, y0, y1 = ch["width"], ch["y0"], ch["y1"]
    mb = MB("POOL_Channel_Basin")
    mb.box(-cw / 2 - 2.6, cw / 2 + 2.6, y0 - 2.6, y1, 0, 0.2, M["marble"])
    mb.box(-cw / 2, cw / 2, y0, y1, 0.2, 0.28, M["tile"])
    for s in (-1, 1):
        mb.box(s * (cw / 2 + 0.5) - 0.5, s * (cw / 2 + 0.5) + 0.5, y0 - 1.0, y1, 0.2, 0.62, M["marble"])
    mb.box(-cw / 2 - 1, cw / 2 + 1, y0 - 1.0, y0, 0.2, 0.62, M["marble"])
    n = int((y1 - y0) // 9)
    for i in range(n):
        fy = y0 + 5 + i * 9.0
        build_fountain(mb, 0, fy, 0.28, 0.75, M)
        for s in (-1, 1):
            mb.cyl(s * (cw / 2 - 0.6), fy + 4.5, 0.28, 0.34, 0.3, M["pool_light"], 8)
    mb.finish("Pools", bevel=0.05, bsegs=1)
    wb = MB("POOL_Channel_Water")
    wb.box(-cw / 2, cw / 2, y0, y1 + 0.5, 0.28, 0.5, M["water"])
    wb.finish("Pools")

    # big fountain in the main pool + 2 smaller ones (mirrored)
    mb = MB("POOL_Fountain_Main")
    build_fountain(mb, mx, my, 0.3, 1.9, M)
    mb.finish("Pools", bevel=0.04, bsegs=1)
    mb = MB("POOL_Fountain_Small")
    build_fountain(mb, mx + msx * 0.3, my, 0.3, 1.3, M)
    build_fountain(mb, ps["center"][0], ps["center"][1], 0.3, 1.3, M)
    mirror(mb.finish("Pools", bevel=0.03, bsegs=1))


# --------------------------------------------------------------------------
# STAGE 3  -  garden + surroundings
# --------------------------------------------------------------------------
def build_garden(M):
    rng = random.Random(7)
    P, pm, ps, ch, wl = CONFIG["palace"], CONFIG["pool_main"], CONFIG["pool_side"], CONFIG["channel"], CONFIG["wall"]
    W, D = P["width"], P["depth"]
    (mx, my), (msx, msy) = pm["center"], pm["size"]
    (sx, sy), (ssx, ssy) = ps["center"], ps["size"]
    py_front = -(D + 16) / 2            # plinth front edge
    y_cross = (ch["y0"] + ch["y1"]) / 2
    wx, wyf, wyb = wl["x"], wl["y_front"], wl["y_back"]

    # stone paths (right half + centre, mirrored on X)
    mb = MB("GDN_Paths")
    z0, z1 = 0.0, 0.14
    mb.box(0, 46, py_front - 22, py_front + 0.5, z0, z1, M["path"])                       # forecourt
    mb.box(4.2, 10.5, ch["y0"] - 3, ch["y1"] + 2, z0, z1, M["path"])                       # walk beside channel
    mb.box(0, 16, wyf + 1, ch["y0"] - 2.6, z0, z1, M["path"])                              # gate plaza
    mb.box(10.5, wx - 6, y_cross - 2.5, y_cross + 2.5, z0, z1, M["path"])                  # cross path
    mb.box(msx / 2 + 4.3, sx - ssx / 2 - 4.3, my - msy / 2 - 4, my + msy / 2 + 4, z0, z1, M["path"])   # deck between pools
    mb.box(0, sx + ssx / 2 + 4.3, my + msy / 2 + 4.3, py_front - 22 + 0.1, z0, z1, M["path"])           # pool top walk
    mb.box(0, sx + ssx / 2 + 4.3, my - msy / 2 - 9, my - msy / 2 - 4.3, z0, z1, M["path"])              # pool bottom walk
    mb.box(sx + ssx / 2 + 4.3, sx + ssx / 2 + 9.5, my - msy / 2 - 9, my + msy / 2 + 9, z0, z1, M["path"])  # outer deck
    mb.box(W / 2 + 10, W / 2 + 15, py_front, D / 2 + 13, z0, z1, M["path"])               # palace side path
    mb.box(0, W / 2 + 15, D / 2 + 9, D / 2 + 13, z0, z1, M["path"])                        # palace back path
    mb.box(wx - 9, wx - 5, wyf + 6, D / 2 + 13, z0, z1, M["path"])                         # perimeter walk
    mb.box(0.0, 3.2, y_cross - 2.5, y_cross + 2.5, 0.55, 0.8, M["marble"])                 # bridge over channel
    mb.box(3.0, 4.6, y_cross - 2.5, y_cross + 2.5, 0.1, 0.8, M["marble"])
    mirror(mb.finish("Garden", bevel=0.04, bsegs=1))

    # lawns
    mb = MB("GDN_Lawns")
    for (x0, x1, y0, y1) in [(11.5, wx - 10, ch["y0"] - 2, y_cross - 3.5), (11.5, wx - 10, y_cross + 3.5, my - msy / 2 - 10),
                             (47, wx - 10, py_front - 21, py_front), (W / 2 + 16, wx - 10, py_front + 1, D / 2 + 13),
                             (17, wx - 10, wyf + 3, ch["y0"] - 3)]:
        mb.box(x0, x1, y0, y1, 0.0, 0.07, M["lawn"])
    mirror(mb.finish("Garden"))

    # round trimmed bushes along the paths
    mb = MB("GDN_Bushes")
    y = ch["y0"]
    while y < ch["y1"] - 1:
        if abs(y - y_cross) > 5:
            build_bush(mb, 12.6, y, 0.95, M)
        y += 3.0
    x = 15.0
    while x < wx - 12:
        for yy in (y_cross - 4.0, y_cross + 4.0):
            build_bush(mb, x, yy, 0.85, M)
        x += 3.2
    x = 49.0
    while x < wx - 12:                                              # hedge in front of the palace wings
        build_bush(mb, x, py_front - 1.6, 1.15, M)
        x += 2.6
    for yy in [py_front + 4 + i * 5.2 for i in range(13)]:          # along palace sides
        build_bush(mb, W / 2 + 17.5, yy, 1.1, M)
    for i in range(9):                                              # big topiary balls around forecourt
        build_bush(mb, 14 + i * 4.0, py_front - 23.2, 1.0, M)
    mirror(mb.finish("Garden"))

    # palms
    mb = MB("GDN_Palms")
    y = ch["y0"] + 4
    while y < ch["y1"] - 10:
        if abs(y - y_cross) > 5:
            build_palm(mb, 14.8, y, rng.uniform(8.5, 10.5), rng, M)
        y += 9.0
    for yy in (my - msy / 2 - 1, my, my + msy / 2 + 1):             # between the pools
        build_palm(mb, (msx / 2 + sx - ssx / 2) / 2 + 0.2, yy, rng.uniform(9, 11), rng, M)
    for xx in (20, 34):                                             # forecourt
        build_palm(mb, xx, py_front - 12, rng.uniform(10, 12), rng, M)
    for yy in (my - 12, my + 12):
        build_palm(mb, sx + ssx / 2 + 12.5, yy, rng.uniform(8.5, 10), rng, M)
    for (xx, yy) in [(40, ch["y0"] + 10), (72, y_cross - 14), (55, y_cross + 12), (86, y_cross + 14)]:
        build_palm(mb, xx, yy, rng.uniform(8, 10.5), rng, M)
    mirror(mb.finish("Garden", smooth_angle=60))

    # cypress trees along the boundary wall and around the palace
    mb = MB("GDN_Cypress")
    y = wyf + 8
    while y < wyb - 4:
        build_cypress(mb, wx - 3.0, y, rng.uniform(9, 12), M)
        y += 7.0
    x = 22.0
    while x < wx - 6:
        build_cypress(mb, x, wyf + 3.4, rng.uniform(8, 10.5), M)
        x += 7.0
    for xx in [8 + i * 9.5 for i in range(10)]:
        build_cypress(mb, xx, wyb - 3.5, rng.uniform(11, 14), M)
    for yy in (py_front - 3, py_front + 20, py_front + 40, py_front + 60):
        build_cypress(mb, W / 2 + 21.5, yy, rng.uniform(10, 12.5), M)
    for xx in (48.5, wx - 12):
        build_cypress(mb, xx, py_front - 19, 9.5, M)
    mirror(mb.finish("Garden"))

    # flower patches
    mb = MB("GDN_Flowers")
    q1y, q2y = (ch["y0"] - 2 + y_cross - 3.5) / 2, (y_cross + 3.5 + my - msy / 2 - 10) / 2
    for (xx, yy, r) in [(34, q1y, 5.0), (70, q1y, 4.2), (34, q2y, 4.2), (70, q2y, 5.0),
                        (60, py_front - 10, 4.0), (82, py_front - 10, 3.2), (W / 2 + 30, 0, 4.5),
                        (52, q1y + 1, 2.4), (52, q2y - 1, 2.4)]:
        build_flower_patch(mb, xx, yy, r, rng, M)
    mirror(mb.finish("Garden", smooth_angle=60))


def build_surroundings(M):
    P, pm, ps, ch, wl = CONFIG["palace"], CONFIG["pool_main"], CONFIG["pool_side"], CONFIG["channel"], CONFIG["wall"]
    (mx, my), (msx, msy) = pm["center"], pm["size"]
    (sx, sy), (ssx, ssy) = ps["center"], ps["size"]
    wx, wyf, wyb = wl["x"], wl["y_front"], wl["y_back"]
    py_front = -(P["depth"] + 16) / 2

    # boundary wall (right half, mirrored)
    mb = MB("SUR_Boundary_Wall")
    def seg(x0, x1, y0, y1):
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        mb.box(x0, x1, y0, y1, 0, 4.0, M["marble"])
        mb.box(x0 - 0.12, x1 + 0.12, y0 - 0.12, y1 + 0.12, 2.5, 3.3, M["wall"])
        mb.box(x0 - 0.2, x1 + 0.2, y0 - 0.2, y1 + 0.2, 4.0, 4.3, M["gold"])
    seg(12, wx, wyf - 0.6, wyf + 0.6)
    seg(wx - 0.6, wx + 0.6, wyf, wyb)
    seg(0, wx, wyb - 0.6, wyb + 0.6)
    posts = [(x, wyf) for x in range(30, int(wx) - 5, 18)] + [(wx, y) for y in range(int(wyf) + 20, int(wyb) - 5, 20)] \
        + [(x, wyb) for x in range(18, int(wx) - 5, 18)]
    for (px, py) in posts:
        mb.cbox(px, py, 2.0, 2.0, 0, 5.0, M["marble"])
        mb.lathe([(0, 0), (1.25, 0), (1.25, 0.3), (0.5, 0.6), (0.75, 1.1), (0.4, 1.6), (0, 1.9)], M["gold"], 10, px, py, 5.0)
    for (px, py) in [(wx, wyf), (wx, wyb)]:                                        # corner pavilions
        mb.cbox(px, py, 5.0, 5.0, 0, 5.6, M["marble"])
        mb.cbox(px, py, 5.2, 5.2, 2.5, 3.3, M["wall"])
        build_chhatri(mb, px, py, 5.6, 2.3, M)
    mirror(mb.finish("Garden", bevel=0.08, bsegs=1))

    # gatehouse with arched opening
    mb = MB("SUR_Gate")
    gw, gh, ow, oh = 26.0, 13.0, 11.0, 9.5
    arch = arch_pts(ow, oh, n=8)
    outline = [(-gw / 2, 0)] + arch[:1] + arch[:1:-1] + [arch[1], (gw / 2, 0), (gw / 2, gh), (-gw / 2, gh)]
    mb.at(0, wyf, 0)
    mb.prism(outline, -2.5, 2.5, M["wall"])
    fr_o, fr_i = arch_pts(ow + 1.6, oh + 0.8, n=8), arch_pts(ow, oh, n=8)
    for y_ in (-2.75, 2.45):                                                       # gold arch trim, both faces
        n_ = len(fr_o)
        v = [(x, y_, z) for x, z in fr_o[1:]] + [(x, y_, z) for x, z in fr_i[1:]] + \
            [(x, y_ + 0.3, z) for x, z in fr_o[1:]] + [(x, y_ + 0.3, z) for x, z in fr_i[1:]]
        k = n_ - 1
        f = []
        for i in range(k - 1):
            f += [(i, i + 1, k + i + 1, k + i), (2 * k + i, 2 * k + i + 1, 3 * k + i + 1, 3 * k + i),
                  (i, i + 1, 2 * k + i + 1, 2 * k + i), (k + i, k + i + 1, 3 * k + i + 1, 3 * k + i)]
        mb._add(v, f, M["gold"])
    mb.box(-gw / 2 - 0.3, gw / 2 + 0.3, -2.8, 2.8, gh, gh + 0.6, M["gold"])
    for s in (-1, 1):                                                              # base band, left open at the arch
        mb.box(min(s * ow / 2, s * (gw / 2 + 0.2)), max(s * ow / 2, s * (gw / 2 + 0.2)), -2.7, 2.7, 0, 0.9, M["marble"])
    mb.box(-ow / 2, ow / 2, -2.6, 2.6, 0, 0.16, M["path"])                         # threshold
    for s in (-1, 1):
        for zz in (2.0, 7.0):
            mb.prism(arch_pts(1.8, 3.6, n=4, x0=s * 9.6, z0=zz), -2.7, 2.7, M["glow"])
        mb.at()
        build_chhatri(mb, s * 9.5, wyf, gh + 0.6, 2.6, M)
        mb.at(0, wyf, 0)
    mb.at()
    build_chhatri(mb, 0, wyf, gh + 0.6, 1.8, M, cols=6)
    mb.finish("Garden", bevel=0.08, bsegs=1)

    # lamp posts: channel rows use Array + Mirror, the rest are placed by hand (mirrored)
    mb = MB("SUR_Lamps_Channel")
    build_lamp(mb, 11.3, ch["y0"] + 0.5, M)
    ob = mb.finish("Garden")
    n = int((ch["y1"] - ch["y0"]) // 13.5) + 1
    array(ob, n, (0, 13.5, 0)); mirror(ob)
    lamp_xy = [(11.3, ch["y0"] + 0.5 + i * 13.5) for i in range(n)]

    extra = [(msx / 2 + 5.5, my - msy / 2 - 5.5), (msx / 2 + 5.5, my + msy / 2 + 5.5),
             (sx + ssx / 2 + 5.5, my - msy / 2 - 5.5), (sx + ssx / 2 + 5.5, my + msy / 2 + 5.5),
             (14, py_front - 2.5), (30, py_front - 2.5), (46, py_front - 2.5), (16, py_front - 21),
             (44, py_front - 21), (P["width"] / 2 + 12.5, py_front + 15), (P["width"] / 2 + 12.5, py_front + 45),
             (wx - 9.8, (ch["y0"] + ch["y1"]) / 2), (60, (ch["y0"] + ch["y1"]) / 2 - 3.2), (13.5, wyf + 6)]
    mb = MB("SUR_Lamps_Garden")
    for (lx, ly) in extra:
        build_lamp(mb, lx, ly, M)
    mirror(mb.finish("Garden"))
    lamp_xy += extra

    # loungers + umbrellas on the decks between and beside the pools
    mb = MB("SUR_Loungers")
    um = MB("SUR_Umbrellas")
    xa = msx / 2 + 6.4                    # facing the main pool
    xb = sx + ssx / 2 + 6.6               # outer deck, facing the side pool
    for i in range(6):
        yy = my - 13.5 + i * 5.4
        build_lounger(mb, xa, yy, 0.0, M)
        build_lounger(mb, xb + 1.4, yy, pi, M)
        if i % 2 == 0:
            build_umbrella(um, xa + 1.0, yy + 2.7, M, M["cushion"] if i % 4 == 0 else M["white"])
            build_umbrella(um, xb + 0.2, yy + 2.7, M, M["white"] if i % 4 == 0 else M["cushion"])
            for (tx_, ty_) in ((xa + 1.9, yy + 2.7), (xb - 0.7, yy + 2.7)):          # side tables
                um.cyl(tx_, ty_, 0.12, 0.55, 0.08, M["white"], 6)
                um.cyl(tx_, ty_, 0.55, 0.62, 0.38, M["gold"], 10)
    mirror(mb.finish("Garden", bevel=0.02, bsegs=1)); mirror(um.finish("Garden"))
    return lamp_xy


# --------------------------------------------------------------------------
# STAGE 4  -  terrain, lake
# --------------------------------------------------------------------------
def terrain_h(x, y):
    wl = CONFIG["wall"]
    dx = max(abs(x) - (wl["x"] + 18), 0.0)
    dy = max(wl["y_front"] - 18 - y, y - (wl["y_back"] + 12), 0.0)
    t = smoothstep(hypot(dx, dy) / 150.0)
    hills = 9 * (0.5 + 0.5 * sin(x * 0.013 + 1.3) * cos(y * 0.011 + 0.4)) + 16 * max(0.0, sin(x * 0.0065 + 2.2) * sin(y * 0.0072 + 1.0))
    h = t * hills
    h += 34 * smoothstep((y - 320) / 170.0) * (0.62 + 0.38 * sin(x * 0.009 + 0.6))      # back ridge
    h *= 0.45 + 0.55 * smoothstep((y + 260) / 200.0)                                      # keep the front low
    e = (x / 165.0) ** 2 + ((y - 195) / 80.0) ** 2                                        # lake bowl behind the palace
    if e < 1.5:
        k = smoothstep((e - 0.85) / 0.65)
        h = -3.0 * (1 - k) + h * k
    return h


def build_terrain(M):
    size, n = 1100.0, 130
    mb = MB("TER_Ground")
    v, f = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = -size / 2 + size * i / n, -size / 2 + 150 + size * j / n
            v.append((x, y, terrain_h(x, y) - 0.02))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            f.append((a, a + 1, a + n + 2, a + n + 1))
    mb._add(v, f, M["terrain"])
    ob = mb.finish("Terrain", smooth_angle=180)
    lk = MB("TER_Lake")
    lk.box(-215, 215, 95, 300, -3.2, -0.55, M["lake"])
    lk.finish("Terrain")
    return ob


def build_temp_ground(M):
    mb = MB("TER_Preview_Ground")
    mb.box(-400, 400, -400, 400, -1.0, -0.02, M["terrain"])
    mb.finish("Terrain")


# --------------------------------------------------------------------------
# lighting, sky, cameras, render settings
# --------------------------------------------------------------------------
def setup_world(tod, sun_vec):
    w = bpy.data.worlds.new("WORLD_Sky_Gradient")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nrm = nt.nodes.new("ShaderNodeVectorMath"); nrm.operation = "NORMALIZE"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -0.05, 0.75
    e = ramp.color_ramp.elements
    cols = [hex_rgb(c) for c in tod["sky"]]
    e[0].position, e[0].color = 0.0, cols[0]
    e[1].position, e[1].color = 1.0, cols[3]
    for pos, c in ((0.14, cols[1]), (0.45, cols[2])):
        el = ramp.color_ramp.elements.new(pos); el.color = c
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = sun_vec
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 10.0; pw.use_clamp = True
    cl = nt.nodes.new("ShaderNodeMath"); cl.operation = "MAXIMUM"; cl.inputs[1].default_value = 0.0
    sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"
    sc.inputs[0].default_value = hex_rgb(tod["sun_col"])[:3]
    add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"
    L = nt.links.new
    L(tc.outputs["Generated"], nrm.inputs[0]); L(nrm.outputs["Vector"], sep.inputs[0])
    L(sep.outputs["Z"], mr.inputs["Value"]); L(mr.outputs["Result"], ramp.inputs["Fac"])
    L(nrm.outputs["Vector"], dot.inputs[0]); L(dot.outputs["Value"], cl.inputs[0]); L(cl.outputs[0], pw.inputs[0])
    L(pw.outputs[0], sc.inputs["Scale"]); L(ramp.outputs["Color"], add.inputs[0]); L(sc.outputs["Vector"], add.inputs[1])
    L(add.outputs["Vector"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = tod["sky_str"]
    bpy.context.scene.world = w


def setup_lights(tod, lamp_xy):
    el, az = radians(tod["elev"]), radians(tod["azim"])
    sun_vec = Vector((-sin(az) * cos(el), -cos(az) * cos(el), sin(el))).normalized()     # points toward the sun
    sd = bpy.data.lights.new("LGT_Sun_Key", "SUN")
    sd.color, sd.energy, sd.angle = hex_rgb(tod["sun_col"])[:3], tod["sun_str"], radians(7)   # wide angle = soft shadows
    so = bpy.data.objects.new("LGT_Sun_Key", sd)
    so.rotation_euler = (-sun_vec).to_track_quat("-Z", "Y").to_euler()
    so.location = sun_vec * 300
    collection("Lights").objects.link(so)
    setup_world(tod, sun_vec)

    def point(name, loc, col, power, radius=0.6):
        d = bpy.data.lights.new(name, "POINT")
        d.color, d.energy, d.shadow_soft_size, d.use_shadow = hex_rgb(col)[:3], power, radius, False
        d.specular_factor = 0.0                                     # no light-blob reflections on water
        o = bpy.data.objects.new(name, d)
        o.location = loc
        collection("Lights").objects.link(o)

    k = tod["lamp"]
    P, pm, ps = CONFIG["palace"], CONFIG["pool_main"], CONFIG["pool_side"]
    for i, (x, y) in enumerate(lamp_xy[::2]):                       # every second lamp gets a real light
        for s in (-1, 1):
            point(f"LGT_Lamp_{i:02d}_{'L' if s < 0 else 'R'}", (s * x, y, 4.9), "#FFC27A", 2500 * k)
    (mx, my), (msx, msy) = pm["center"], pm["size"]
    for i, fx in enumerate((-0.3, 0.0, 0.3)):                       # turquoise pool glow
        point(f"LGT_Pool_Main_{i}", (mx + fx * msx, my, 2.2), "#7FFFF0", 4000 * k, 2.0)
    for s in (-1, 1):
        point(f"LGT_Pool_Side_{'L' if s < 0 else 'R'}", (s * ps["center"][0], ps["center"][1], 2.2), "#7FFFF0", 3000 * k, 2.0)
    fy = -P["depth"] / 2
    for i, x in enumerate((-42, -24, 24, 42)):                      # warm facade wash
        point(f"LGT_Facade_{i}", (x, fy - 7.5, 4.5), "#FFB060", 6000 * k, 1.5)
    point("LGT_Entrance", (0, fy - 9.0, 9.0), "#FFC680", 9000 * k, 1.5)
    point("LGT_Dome_Main", (0, -16, P["dome_top"] - 14), "#FFD9A0", 10000 * k, 2.0)
    return sun_vec


def look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def setup_cameras():
    P, pm = CONFIG["palace"], CONFIG["pool_main"]
    (mx, my), (msx, msy) = pm["center"], pm["size"]
    cams = {}

    def cam(name, loc, target, lens=35, ortho=None):
        d = bpy.data.cameras.new(name)
        d.lens, d.clip_start, d.clip_end = lens, 0.5, 4000
        if ortho:
            d.type, d.ortho_scale = "ORTHO", ortho
        o = bpy.data.objects.new(name, d)
        o.location = loc
        look_at(o, target)
        collection("Camera").objects.link(o)
        cams[name] = o

    cam("CAM_Hero_Front", (0, -163, 27), (0, -18, 14.5), lens=30)
    cam("CAM_Iso_Map", (-330, -330 - 55, 300), (0, -55, 5), ortho=335)
    cam("CAM_Pool_Low", (mx - msx * 0.36, my - msy / 2 - 7.0, 3.2), (6, 0, 17), lens=24)
    bpy.context.scene.camera = cams["CAM_Hero_Front"]
    return cams


def setup_bloom():
    """Bloom on bright lights via the compositor Glare node (EEVEE Next has no built-in bloom)."""
    sc = bpy.context.scene
    try:
        ng = bpy.data.node_groups.new("CMP_Bloom", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        gl.inputs["Type"].default_value = "Bloom"
        gl.inputs["Threshold"].default_value = 2.2
        gl.inputs["Strength"].default_value = 0.35
        gl.inputs["Size"].default_value = 0.45
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
        sc.compositing_node_group = ng
        return True
    except Exception as ex:                                   # keep the build alive on other Blender versions
        print("WARN bloom compositor not set up:", ex)
        return False


def setup_render(tod, preview=False):
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    rx, ry = CONFIG["render"]["res"]
    sc.render.resolution_x, sc.render.resolution_y = (rx // 2, ry // 2) if preview else (rx, ry)
    sc.render.resolution_percentage = 100
    ee.taa_render_samples = 8 if preview else CONFIG["render"]["samples"]
    ee.use_shadows = True
    ee.use_raytracing = True                                  # screen-space reflections (water, gold)
    ee.use_fast_gi = True                                     # ambient occlusion / soft bounce
    for attr, val in (("fast_gi_method", "AMBIENT_OCCLUSION_ONLY"), ("fast_gi_distance", 12.0), ("shadow_ray_count", 2),
                      ("shadow_step_count", 6)):
        try:
            setattr(ee, attr, val)
        except Exception as ex:
            print("WARN eevee", attr, ex)
    vs = sc.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Punchy", "AgX - Medium High Contrast"):
        try:
            vs.look = look
            break
        except Exception:
            pass
    vs.exposure = tod["exposure"]
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    setup_bloom()
    if CONFIG["outline"]:                                     # optional toon outline
        sc.render.use_freestyle = True
        sc.render.line_thickness = 1.2
        vl = bpy.context.view_layer
        ls = vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new("Outline")
        ls.select_silhouette, ls.select_border, ls.select_crease = True, True, False
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.new("Outline")
        ls.linestyle.color = (0.03, 0.05, 0.15)


def render(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {os.path.basename(path)} in {time.time() - t:.0f}s")


def export_glb(path):
    """Procedural colors can't travel in glTF, so swap them for flat colors before export."""
    for m in bpy.data.materials:
        if not m.node_tree or "flat_rgba" not in m:
            continue
        b = m.node_tree.nodes.get("Principled BSDF")
        for inp in ("Base Color", "Normal"):
            for l in list(b.inputs[inp].links):
                m.node_tree.links.remove(l)
        b.inputs["Base Color"].default_value = list(m["flat_rgba"])
    for o in bpy.data.objects:
        o.select_set(False)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True, export_cameras=True,
                              export_lights=False, export_yup=True)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=4, help="1 palace, 2 +pools, 3 +garden, 4 +terrain (final)")
    ap.add_argument("--time", default=CONFIG["time_of_day"], choices=list(TIMES))
    ap.add_argument("--preview", action="store_true", help="half resolution, few samples, hero camera only")
    ap.add_argument("--cams", default="", help="comma list of camera names to render (default: all / hero in preview)")
    ap.add_argument("--outline", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    CONFIG["outline"] = CONFIG["outline"] or a.outline
    tod = TIMES[a.time]
    t0 = time.time()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in ("Palace", "Pools", "Garden", "Terrain", "Lights", "Camera"):
        collection(c)
    M = make_materials(tod)

    build_palace(M);                         print("STAGE 1 palace OK")
    lamp_xy = []
    if a.stage >= 2:
        build_pools(M);                      print("STAGE 2 pools OK")
    if a.stage >= 3:
        build_garden(M)
        lamp_xy = build_surroundings(M);     print("STAGE 3 garden + surroundings OK")
    if a.stage >= 4:
        build_terrain(M);                    print("STAGE 4 terrain OK")
    else:
        build_temp_ground(M)
    setup_lights(tod, lamp_xy)
    cams = setup_cameras()
    setup_render(tod, a.preview)

    dg = bpy.context.evaluated_depsgraph_get()
    tris = sum(len(o.evaluated_get(dg).data.loop_triangles) for o in bpy.data.objects if o.type == "MESH"
               and not o.evaluated_get(dg).data.calc_loop_triangles())
    print(f"SCENE objects={len(bpy.data.objects)} tris={tris} build={time.time() - t0:.1f}s")

    rdir = os.path.join(a.out, "renders")
    os.makedirs(rdir, exist_ok=True)
    final = a.stage >= 4 and not a.preview
    if not a.no_render:
        names = [n for n in a.cams.split(",") if n] or (list(cams) if not a.preview else ["CAM_Hero_Front"])
        for n in names:
            tag = n.replace("CAM_", "").lower()
            fn = f"palace_{tag}.png" if final else f"preview_stage{a.stage}_{tag}.png"
            render(cams[n], os.path.join(rdir, fn))
        bpy.context.scene.camera = cams["CAM_Hero_Front"]
    if final:
        bpy.context.scene.render.filepath = "//renders/palace_"
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(a.out, "palace.blend"), compress=True)
        print("SAVED palace.blend")
        if not a.no_export:
            export_glb(os.path.join(a.out, "palace.glb"))
            print("EXPORTED palace.glb")
    print(f"DONE in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
