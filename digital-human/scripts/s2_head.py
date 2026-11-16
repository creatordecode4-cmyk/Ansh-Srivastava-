"""Step 2: skin shader + region masks, eyes, eyelashes, eyebrows, scalp hair, peach fuzz.
All built in rest pose and bound to the head bone.  Reads work/body.blend -> work/head.blend
"""
import sys, os, math, random
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix, kdtree
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(__file__))
from common import *

rng = np.random.default_rng(7)
random.seed(7)
bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "body.blend"))
LM = load_json("landmarks.json")
body = bpy.data.objects["GEO_Body"]
rig = bpy.data.objects["RIG_Teen"]
me = body.data
P = np.array([v.co[:] for v in me.vertices])
N = np.array([v.normal[:] for v in me.vertices])
C_CHAR = bpy.data.collections["CHAR_Teen"]
C_HEAD = coll("HEAD", C_CHAR)
C_HAIR = coll("HAIR", C_CHAR)

# ---------------------------------------------------------------- landmarks
E = {s: np.array(LM[f"eye_{s}_center"]) for s in "lr"}  # l = character left (+x)
NOSE = P[(np.abs(P[:, 0]) < 0.0015) & (P[:, 2] > 1.55) & (P[:, 2] < 1.65)]
NOSE = NOSE[np.argmin(NOSE[:, 1])]
LIP_Z = NOSE[2] - 0.0295  # lip seam (measured from the midline profile)
HC = np.array([0.0, -0.055, 1.66])  # rough head centre
print("nose tip", NOSE, "lip z", LIP_Z)

bvh = BVHTree.FromPolygons([tuple(v) for v in P], [tuple(p.vertices) for p in me.polygons])


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def ell(p, c, r):
    """soft ellipsoid weight 1 at centre -> 0 at radius r (vector)"""
    d = np.sqrt((((p - c) / r) ** 2).sum(-1))
    return 1 - smoothstep(0.6, 1.0, d)

# ---------------------------------------------------------------- scalp / hairline
rel = P - HC
az = np.degrees(np.arctan2(np.abs(rel[:, 0]), -rel[:, 1]))  # 0 front, 90 side, 180 back
HL = [(0, 1.704), (30, 1.698), (48, 1.684), (62, 1.660), (72, 1.610), (80, 1.605), (86, 1.630),
      (92, 1.656), (108, 1.656), (118, 1.622), (135, 1.580), (155, 1.558), (180, 1.550)]
zh = np.interp(az, [a for a, _ in HL], [z for _, z in HL])
scalp = smoothstep(zh - 0.002, zh + 0.012, P[:, 2]) * (P[:, 2] > 1.5)
# keep ears bald: ear vertices stick out laterally
ear = (np.abs(P[:, 0]) > 0.070) & (P[:, 2] < 1.660) & (P[:, 2] > 1.57) & (az > 80) & (az < 125)
scalp[ear] = 0
hairline_dist = zh  # store for later

# ---------------------------------------------------------------- skin masks (RGBA): red, freckle, oil, lip
pf = P.copy()
lipx = np.clip(np.abs(pf[:, 0]) / 0.0245, 0, 1)
up_h = 0.0095 * np.sqrt(np.clip(1 - lipx ** 2.2, 0, 1)) + 0.0006
lo_h = 0.0115 * np.sqrt(np.clip(1 - lipx ** 2.0, 0, 1)) + 0.0006
dz = pf[:, 2] - LIP_Z
lip = np.where(dz > 0, 1 - smoothstep(up_h * 0.75, up_h * 1.12, dz), 1 - smoothstep(lo_h * 0.75, lo_h * 1.12, -dz))
lip *= (1 - smoothstep(0.85, 1.05, lipx)) * (pf[:, 1] < NOSE[1] + 0.035) * (np.abs(dz) < 0.02)
red = 0.85 * ell(pf, NOSE + [0, 0.004, -0.002], np.array([0.016, 0.02, 0.016]))
for sx in (-1, 1):
    red = np.maximum(red, 0.45 * ell(pf, np.array([sx * 0.044, -0.135, NOSE[2] + 0.002]), np.array([0.026, 0.03, 0.022])))
    red = np.maximum(red, 0.35 * ell(pf, np.array([sx * 0.016, -0.150, E["l"][2] + 0.0]), np.array([0.008, 0.02, 0.01])))  # inner eye corners
earw = ((np.abs(pf[:, 0]) > 0.066) & (pf[:, 2] < 1.675) & (pf[:, 2] > 1.565) & (az > 78) & (az < 130)).astype(float)
red = np.maximum(red, 0.75 * earw)
# knuckles / fingers / elbows / knees via bone weights
def vg_weights(names):
    w = np.zeros(len(P))
    for nm in names:
        vg = body.vertex_groups.get(nm)
        if vg is None:
            continue
        for v in me.vertices:
            for g in v.groups:
                if g.group == vg.index:
                    w[v.index] += g.weight
    return np.clip(w, 0, 1)
fing = vg_weights([f"finger{i}-{j}.{s}" for i in range(1, 6) for j in (1, 2, 3) for s in "LR"])
red = np.maximum(red, 0.5 * fing)
freck = ell(pf, np.array([0, -0.165, NOSE[2] + 0.014]), np.array([0.07, 0.07, 0.03]))
freck = np.maximum(freck, 0.5 * ell(pf, np.array([0, -0.15, 1.69]), np.array([0.06, 0.05, 0.02])))
freck *= (pf[:, 1] < -0.10) * (1 - lip)
freck = np.maximum(freck, 0.25 * smoothstep(1.40, 1.46, pf[:, 2]) * smoothstep(-0.02, 0.06, -pf[:, 1]) * (pf[:, 2] < 1.52))  # shoulders/chest light
oil = np.maximum(ell(pf, np.array([0, -0.16, 1.69]), np.array([0.035, 0.04, 0.03])), ell(pf, NOSE + [0, 0.01, 0.01], np.array([0.016, 0.03, 0.035])))
oil = np.maximum(oil, 0.7 * ell(pf, np.array([0, -0.155, LIP_Z - 0.03]), np.array([0.02, 0.03, 0.015])))
masks = np.stack([red, freck, oil, lip], 1).astype(np.float32)
ca = me.color_attributes.new("masks", "FLOAT_COLOR", "POINT")
ca.data.foreach_set("color", masks.ravel())
ra = me.attributes.new("rest_pos", "FLOAT_VECTOR", "POINT")
ra.data.foreach_set("vector", P.astype(np.float32).ravel())

# ---------------------------------------------------------------- skin material
def mat_skin():
    m = bpy.data.materials.new("MAT_Skin")
    nt = m.node_tree; nt.nodes.clear()
    L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (1400, 0))
    bs = node(nt, "ShaderNodeBsdfPrincipled", (1100, 0))
    bs.subsurface_method = "RANDOM_WALK_SKIN"
    L.new(bs.outputs[0], out.inputs["Surface"])
    pos = node(nt, "ShaderNodeAttribute", (-1400, 0)); pos.attribute_name = "rest_pos"
    msk = node(nt, "ShaderNodeAttribute", (-1400, -300)); msk.attribute_name = "masks"
    sep = node(nt, "ShaderNodeSeparateColor", (-1200, -300)); L.new(msk.outputs["Color"], sep.inputs[0])
    R_, G_, B_, A_ = sep.outputs[0], sep.outputs[1], sep.outputs[2], msk.outputs["Alpha"]

    def mix(a, b, f, loc, blend="MIX"):
        n = nt.nodes.new("ShaderNodeMix"); n.data_type = "RGBA"; n.blend_type = blend; n.location = loc
        for src, sock in ((f, n.inputs[0]), (a, n.inputs[6]), (b, n.inputs[7])):
            if isinstance(src, (float, int)):
                sock.default_value = src
            elif isinstance(src, tuple):
                sock.default_value = src
            else:
                L.new(src, sock)
        return n.outputs[2]

    def math_(op, a, b=None, loc=(0, 0), clamp=False):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.location = loc; n.use_clamp = clamp
        for i, src in enumerate((a, b)):
            if src is None:
                continue
            if isinstance(src, (float, int)):
                n.inputs[i].default_value = src
            else:
                L.new(src, n.inputs[i])
        return n.outputs[0]

    # blotchy tone variation
    n1 = node(nt, "ShaderNodeTexNoise", (-1000, 400), Scale=35.0, Detail=6.0, Roughness=0.6)
    L.new(pos.outputs["Vector"], n1.inputs["Vector"])
    n2 = node(nt, "ShaderNodeTexNoise", (-1000, 650), Scale=180.0, Detail=4.0, Roughness=0.55)
    L.new(pos.outputs["Vector"], n2.inputs["Vector"])
    base = mix((0.46, 0.27, 0.20, 1), (0.53, 0.33, 0.25, 1), n1.outputs["Fac"], (-700, 400))
    base = mix(base, (0.48, 0.27, 0.21, 1), math_("MULTIPLY", n2.outputs["Fac"], 0.35, (-800, 650)), (-500, 450))
    # redness (nose, cheeks, ears, knuckles)
    redn = node(nt, "ShaderNodeTexNoise", (-1000, 150), Scale=90.0, Detail=3.0)
    L.new(pos.outputs["Vector"], redn.inputs["Vector"])
    rf = math_("MULTIPLY", R_, math_("ADD", math_("MULTIPLY", redn.outputs["Fac"], 0.6), 0.45), (-700, 150), clamp=True)
    base = mix(base, (0.58, 0.20, 0.16, 1), math_("MULTIPLY", rf, 0.6), (-300, 300))
    # freckles: voronoi spots with random size, gated per cell
    vor = node(nt, "ShaderNodeTexVoronoi", (-1000, -600), Scale=420.0, Randomness=1.0)
    L.new(pos.outputs["Vector"], vor.inputs["Vector"])
    sepc = node(nt, "ShaderNodeSeparateColor", (-800, -650)); L.new(vor.outputs["Color"], sepc.inputs[0])
    cellr = sepc.outputs[0]
    on = math_("LESS_THAN", cellr, 0.42, (-650, -700))
    size = math_("ADD", math_("MULTIPLY", sepc.outputs[1], 0.25), 0.12, (-650, -800))
    spot = math_("SUBTRACT", 1.0, math_("DIVIDE", vor.outputs["Distance"], size, (-560, -650), clamp=False), (-500, -650), clamp=True)
    spot = math_("POWER", spot, 0.6, (-470, -650))
    fr2 = node(nt, "ShaderNodeTexNoise", (-1000, -900), Scale=60.0); L.new(pos.outputs["Vector"], fr2.inputs["Vector"])
    fmask = math_("MULTIPLY", G_, smoothstep_node(nt, fr2.outputs["Fac"], 0.42, 0.62, (-650, -950)), (-450, -900))
    freck_f = math_("MULTIPLY", math_("MULTIPLY", on, spot, (-350, -700)), fmask, (-200, -700))
    freck_f = math_("MULTIPLY", freck_f, math_("ADD", math_("MULTIPLY", sepc.outputs[2], 0.45), 0.35), (-50, -700))
    base = mix(base, (0.36, 0.18, 0.10, 1), math_("MULTIPLY", freck_f, 0.95), (-100, 300))
    # lips
    lipn = node(nt, "ShaderNodeTexNoise", (-700, -1100), Scale=900.0, Detail=2.0)
    L.new(pos.outputs["Vector"], lipn.inputs["Vector"])
    base = mix(base, (0.48, 0.17, 0.15, 1), math_("MULTIPLY", A_, 0.8), (100, 300))
    L.new(base, bs.inputs["Base Color"])
    # roughness: dry cheeks 0.52, oily T-zone 0.34, lips 0.36, fine noise
    rn = node(nt, "ShaderNodeTexNoise", (-500, -200), Scale=140.0, Detail=5.0)
    L.new(pos.outputs["Vector"], rn.inputs["Vector"])
    rough = math_("ADD", 0.52, math_("MULTIPLY", math_("SUBTRACT", rn.outputs["Fac"], 0.5), 0.14), (-300, -200))
    rough = math_("SUBTRACT", rough, math_("MULTIPLY", B_, 0.14), (-150, -200))
    rough = math_("SUBTRACT", rough, math_("MULTIPLY", A_, 0.10), (0, -200), clamp=True)
    L.new(rough, bs.inputs["Roughness"])
    bs.inputs["Subsurface Weight"].default_value = 1.0
    bs.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.22)
    bs.inputs["Subsurface Scale"].default_value = 0.0034
    bs.inputs["Subsurface IOR"].default_value = 1.4
    bs.inputs["Subsurface Anisotropy"].default_value = 0.8
    bs.inputs["Specular IOR Level"].default_value = 0.42
    bs.inputs["IOR"].default_value = 1.4
    L.new(math_("ADD", 0.0, math_("MULTIPLY", B_, 0.12), (300, -350)), bs.inputs["Coat Weight"])
    bs.inputs["Coat Roughness"].default_value = 0.33
    bs.inputs["Sheen Weight"].default_value = 0.06
    bs.inputs["Sheen Roughness"].default_value = 0.35
    bs.inputs["Sheen Tint"].default_value = (1.0, 0.92, 0.88, 1)
    # micro detail: pores + fine wrinkles + bumps (bump-mapped, rest-pose space)
    pv = node(nt, "ShaderNodeTexVoronoi", (-500, -1300), Scale=1700.0, Randomness=0.9)
    pv.feature = "SMOOTH_F1"
    L.new(pos.outputs["Vector"], pv.inputs["Vector"])
    wr = node(nt, "ShaderNodeTexNoise", (-500, -1550), Scale=650.0, Detail=8.0, Roughness=0.7)
    L.new(pos.outputs["Vector"], wr.inputs["Vector"])
    big = node(nt, "ShaderNodeTexNoise", (-500, -1800), Scale=55.0, Detail=4.0)
    L.new(pos.outputs["Vector"], big.inputs["Vector"])
    h = math_("ADD", math_("MULTIPLY", pv.outputs["Distance"], 1.0), math_("MULTIPLY", wr.outputs["Fac"], 0.55), (-250, -1400))
    h = math_("ADD", h, math_("MULTIPLY", big.outputs["Fac"], 0.25), (-100, -1450))
    mid = node(nt, "ShaderNodeTexNoise", (-500, -2050), Scale=260.0, Detail=6.0, Roughness=0.65)
    L.new(pos.outputs["Vector"], mid.inputs["Vector"])
    h = math_("ADD", h, math_("MULTIPLY", mid.outputs["Fac"], 0.45), (-50, -1500))
    b1 = node(nt, "ShaderNodeBump", (100, -1300), Strength=0.22, Distance=0.00035)
    # pores stronger on nose/cheeks (freckle mask region) and T-zone
    L.new(math_("ADD", 0.22, math_("MULTIPLY", math_("ADD", G_, B_), 0.12), (-100, -1150), clamp=False), b1.inputs["Strength"])
    L.new(h, b1.inputs["Height"])
    lipw = node(nt, "ShaderNodeTexWave", (-300, -1700), Scale=600.0, Distortion=4.0, Detail=3.0)
    lipw.wave_profile = "SIN"; lipw.bands_direction = "Z"
    L.new(pos.outputs["Vector"], lipw.inputs["Vector"])
    b2 = node(nt, "ShaderNodeBump", (300, -1500), Distance=0.0002)
    L.new(math_("MULTIPLY", A_, 0.35, (100, -1650)), b2.inputs["Strength"])
    L.new(lipw.outputs["Fac"], b2.inputs["Height"])
    L.new(b1.outputs["Normal"], b2.inputs["Normal"])
    L.new(b2.outputs["Normal"], bs.inputs["Normal"])
    L.new(b2.outputs["Normal"], bs.inputs["Coat Normal"])
    return m


def smoothstep_node(nt, x, a, b, loc):
    n = nt.nodes.new("ShaderNodeMapRange"); n.location = loc
    n.interpolation_type = "SMOOTHSTEP"
    n.inputs["From Min"].default_value = a; n.inputs["From Max"].default_value = b
    nt.links.new(x, n.inputs["Value"])
    return n.outputs[0]

skin = mat_skin()
me.materials.clear(); me.materials.append(skin)
sub = body.modifiers.new("Subdivision", "SUBSURF")
sub.levels = 1; sub.render_levels = 2; sub.quality = 3

# ---------------------------------------------------------------- eyes
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
loops = {}
for s in "lr":
    c = E[s]
    dv = P - c
    dd = np.linalg.norm(dv, axis=1)
    facing = (N * (-dv)).sum(1) / np.maximum(dd, 1e-9)  # >0: surface faces the eyeball (socket lining)
    lining = (dd < 0.02) & (facing > 0.3)
    margin = []
    for i in np.where(lining & (dv[:, 1] < -0.004))[0]:
        if any(facing[e.other_vert(bm.verts[i]).index] < 0.0 for e in bm.verts[i].link_edges):
            margin.append(i)
    loops[s] = P[margin]
bm.free()


def ordered_loop(pts, c):
    ang = np.arctan2(pts[:, 2] - c[2], pts[:, 0] - c[0])
    return pts[np.argsort(ang)], np.sort(ang)

EYE_R = {}
for s in "lr":
    d = np.linalg.norm(loops[s] - E[s], axis=1)
    dv = P - E[s]; dd = np.linalg.norm(dv, axis=1)
    facing = (N * (-dv)).sum(1) / np.maximum(dd, 1e-9)
    lin = (dd < 0.02) & (facing > 0.5)
    EYE_R[s] = float(np.percentile(dd[lin], 20))
    print("eye", s, "lid verts", len(loops[s]), "lid radius median %.4f helper %.4f" % (EYE_R[s], LM[f"eye_{s}_radius"]))


def sph_mesh(name, R, c, iris_r, kind):
    """kind 'ball': sclera + recessed iris disc; 'cornea': sclera shell + corneal dome"""
    segs, rings = 96, 64
    verts, uvw = [], []
    fwd = np.array([0, -1.0, 0])
    phi_i = math.asin(iris_r / R)
    for i in range(rings + 1):
        phi = math.pi * i / rings
        for j in range(segs):
            th = 2 * math.pi * j / segs
            dirp = np.array([math.cos(th), 0, math.sin(th)])  # perpendicular plane basis (x,z)
            if kind == "ball":
                if phi < phi_i:
                    r = iris_r * (phi / phi_i)
                    ax = R * math.cos(phi_i) - 0.00045 + 0.00035 * (1 - r / iris_r) ** 1.5
                    p = c + fwd * ax + dirp * r
                    rn = r / iris_r
                else:
                    p = c + fwd * R * math.cos(phi) + dirp * R * math.sin(phi)
                    rn = 1 + (phi - phi_i) / (math.pi - phi_i)
            else:
                Rs = R + 0.00025
                phi_l = phi_i + math.radians(3)
                rho_l = Rs * math.sin(phi_l); zl = Rs * math.cos(phi_l)
                Rc = 0.62 * R
                zc = zl - math.sqrt(Rc * Rc - rho_l * rho_l)
                if phi < phi_l:
                    rho = rho_l * (phi / phi_l)
                    ax = zc + math.sqrt(Rc * Rc - rho * rho)
                    p = c + fwd * ax + dirp * rho
                else:
                    p = c + fwd * Rs * math.cos(phi) + dirp * Rs * math.sin(phi)
                rn = phi / math.pi
            verts.append(p); uvw.append((rn, j / segs, 0))
    faces = []
    for i in range(rings):
        for j in range(segs):
            a = i * segs + j; b = i * segs + (j + 1) % segs
            faces.append((a, a + segs, b + segs, b))
    m = bpy.data.meshes.new(name)
    m.from_pydata([tuple(v) for v in verts], [], faces)
    a = m.attributes.new("eye_uv", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.array(uvw, np.float32).ravel())
    for p in m.polygons:
        p.use_smooth = True
    bmm = bmesh.new(); bmm.from_mesh(m)
    bmesh.ops.remove_doubles(bmm, verts=bmm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bmm, faces=bmm.faces)
    bmm.to_mesh(m); bmm.free()
    o = bpy.data.objects.new(name, m)
    C_HEAD.objects.link(o)
    return o


def mat_eye():
    m = bpy.data.materials.new("MAT_Eye_Sclera_Iris")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (1200, 0))
    bs = node(nt, "ShaderNodeBsdfPrincipled", (900, 0))
    L.new(bs.outputs[0], out.inputs[0])
    at = node(nt, "ShaderNodeAttribute", (-1200, 0)); at.attribute_name = "eye_uv"
    sp = node(nt, "ShaderNodeSeparateXYZ", (-1000, 0)); L.new(at.outputs["Vector"], sp.inputs[0])
    r, a = sp.outputs[0], sp.outputs[1]
    # polar coords -> fibre texture coords
    cx = node(nt, "ShaderNodeCombineXYZ", (-800, 200))
    L.new(a, cx.inputs["X"]); L.new(r, cx.inputs["Y"])
    sc = nt.nodes.new("ShaderNodeMapping"); sc.location = (-650, 200)
    sc.inputs["Scale"].default_value = (90.0, 4.0, 1.0)
    L.new(cx.outputs[0], sc.inputs["Vector"])
    fib = node(nt, "ShaderNodeTexNoise", (-450, 300), Scale=1.0, Detail=10.0, Roughness=0.65, Distortion=0.4)
    L.new(sc.outputs[0], fib.inputs["Vector"])
    fib2 = node(nt, "ShaderNodeTexNoise", (-450, 0), Scale=2.5, Detail=6.0, Roughness=0.6)
    L.new(sc.outputs[0], fib2.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-200, 300)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.30; cr.elements[0].color = (0.028, 0.050, 0.026, 1)
    cr.elements[1].position = 0.75; cr.elements[1].color = (0.13, 0.20, 0.085, 1)
    e = cr.elements.new(0.52); e.color = (0.065, 0.11, 0.05, 1)
    L.new(fib.outputs["Fac"], ramp.inputs[0])
    # radial zones: pupil / amber collarette / green / limbal ring / sclera
    zr = nt.nodes.new("ShaderNodeValToRGB"); zr.location = (-200, -250)
    z = zr.color_ramp; z.interpolation = "EASE"
    z.elements[0].position = 0.0; z.elements[0].color = (0, 0, 0, 1)
    z.elements[1].position = 1.0; z.elements[1].color = (0, 0, 0, 1)
    L.new(r, zr.inputs[0])
    # build colour by mixing
    def mixc(a_, b_, f, loc):
        n = nt.nodes.new("ShaderNodeMix"); n.data_type = "RGBA"; n.location = loc
        for src, sock in ((f, n.inputs[0]), (a_, n.inputs[6]), (b_, n.inputs[7])):
            if isinstance(src, (tuple, float)):
                sock.default_value = src
            else:
                L.new(src, sock)
        return n.outputs[2]

    def mr(x, a_, b_, loc, inv=False):
        n = nt.nodes.new("ShaderNodeMapRange"); n.location = loc; n.interpolation_type = "SMOOTHSTEP"
        n.inputs[1].default_value = a_; n.inputs[2].default_value = b_
        if inv:
            n.inputs[3].default_value = 1.0; n.inputs[4].default_value = 0.0
        L.new(x, n.inputs[0]); return n.outputs[0]
    col = ramp.outputs["Color"]
    amber = mixc((0.17, 0.12, 0.045, 1), (0.10, 0.08, 0.03, 1), fib2.outputs["Fac"], (0, 500))
    am = nt.nodes.new("ShaderNodeMath"); am.operation = "MULTIPLY"; am.inputs[1].default_value = 0.7; L.new(mr(r, 0.6, 0.4, (0, 350)), am.inputs[0])
    col = mixc(col, amber, am.outputs[0], (200, 300))   # collarette near pupil
    col = mixc(col, (0.012, 0.025, 0.012, 1), mr(r, 0.80, 0.99, (200, 100)), (400, 300))  # limbal ring
    col = mixc(col, (0.004, 0.004, 0.004, 1), mr(r, 0.335, 0.31, (400, 100)), (600, 300))  # pupil
    # sclera with veins + pinkish edges
    vn = node(nt, "ShaderNodeTexNoise", (-450, -500), Scale=14.0, Detail=12.0, Roughness=0.7, Distortion=1.5)
    L.new(at.outputs["Vector"], vn.inputs["Vector"])
    vein = mr(vn.outputs["Fac"], 0.505, 0.5, (-200, -500))
    vein2 = nt.nodes.new("ShaderNodeMath"); vein2.operation = "MULTIPLY"; vein2.location = (0, -500)
    L.new(vein, vein2.inputs[0]); L.new(mr(r, 1.12, 1.45, (-200, -650)), vein2.inputs[1])
    scl = mixc((0.62, 0.56, 0.52, 1), (0.60, 0.42, 0.39, 1), mr(r, 1.15, 1.6, (200, -650)), (400, -400))
    scl = mixc(scl, (0.55, 0.12, 0.10, 1), vein2.outputs[0], (600, -400))
    col = mixc(col, scl, mr(r, 0.995, 1.04, (600, 100)), (800, 200))
    L.new(col, bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.35
    bs.inputs["Subsurface Weight"].default_value = 0.25
    bs.inputs["Subsurface Radius"].default_value = (1.0, 0.5, 0.4)
    bs.inputs["Subsurface Scale"].default_value = 0.002
    # iris relief bump
    bmp = node(nt, "ShaderNodeBump", (600, -200), Strength=0.4, Distance=0.0002)
    L.new(fib.outputs["Fac"], bmp.inputs["Height"]); L.new(bmp.outputs[0], bs.inputs["Normal"])
    return m


def mat_cornea():
    m = bpy.data.materials.new("MAT_Eye_Cornea")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (800, 0))
    g = node(nt, "ShaderNodeBsdfPrincipled", (300, 100))
    g.inputs["Base Color"].default_value = (1, 1, 1, 1)
    g.inputs["Roughness"].default_value = 0.0
    g.inputs["Transmission Weight"].default_value = 1.0
    g.inputs["IOR"].default_value = 1.376
    tr = node(nt, "ShaderNodeBsdfTransparent", (300, -150))
    lp = node(nt, "ShaderNodeLightPath", (0, 300))
    mx = node(nt, "ShaderNodeMixShader", (550, 0))
    L.new(lp.outputs["Is Shadow Ray"], mx.inputs[0])
    L.new(g.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs[0])
    return m


def mat_simple(name, col, rough=0.4, sss=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = 0.003
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.05
    return m

M_EYE, M_CORNEA = mat_eye(), mat_cornea()
M_CAR = mat_simple("MAT_Eye_Caruncle", (0.72, 0.36, 0.33, 1), 0.25, 0.6, 0.8)
M_TEAR = mat_simple("MAT_Eye_Tearline", (0.9, 0.8, 0.78, 1), 0.02, 0.0, 1.0)
M_TEAR.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 0.9
eye_objs = []
for s in "lr":
    R = EYE_R[s] - 0.0002
    c = E[s].copy()
    iris = 0.50 * R
    ball = sph_mesh(f"GEO_Eye_{s.upper()}", R, c, iris, "ball"); ball.data.materials.append(M_EYE)
    corn = sph_mesh(f"GEO_Cornea_{s.upper()}", R, c, iris, "cornea"); corn.data.materials.append(M_CORNEA)
    eye_objs += [ball, corn]
    pts, ang = ordered_loop(loops[s], c)
    sx = 1 if s == "l" else -1
    # caruncle: inner corner = lid vertex closest to midline
    inner = pts[np.argmin(np.abs(pts[:, 0]))]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=tuple(inner + np.array([sx * 0.0018, 0.0022, -0.0003])))
    car = bpy.context.active_object; car.name = f"GEO_Caruncle_{s.upper()}"
    car.scale = (0.0021, 0.0016, 0.0023); bpy.ops.object.shade_smooth()
    car.data.materials.append(M_CAR); link(car, C_HEAD); eye_objs.append(car)
    # tear-line along lower lid margin (thin wet tube)
    lower = pts[(pts[:, 2] < c[2] - 0.0015)]
    lower = lower[np.argsort(lower[:, 0])]
    cu = bpy.data.curves.new(f"CRV_Tear_{s}", "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("POLY"); sp.points.add(len(lower) - 1)
    for i, p in enumerate(lower):
        q = p + (c - p) * 0.06
        sp.points[i].co = (*q, 1)
    cu.bevel_depth = 0.00035; cu.bevel_resolution = 2
    to = bpy.data.objects.new(f"GEO_Tearline_{s.upper()}", cu); C_HEAD.objects.link(to)
    to.data.materials.append(M_TEAR); eye_objs.append(to)

# ---------------------------------------------------------------- curves helpers
def make_curves(name, strands, radii, mat, attrs=None):
    """strands: list of (K,3) arrays (same K), radii: (K,) or per-strand scale"""
    K = strands[0].shape[0]
    cv = bpy.data.hair_curves.new(name)
    cv.add_curves([K] * len(strands))
    pos = np.concatenate(strands).astype(np.float32)
    cv.attributes["position"].data.foreach_set("vector", pos.ravel())
    ra = cv.attributes.new("radius", "FLOAT", "POINT")
    ra.data.foreach_set("value", np.asarray(radii, np.float32).ravel())
    for an, vals in (attrs or {}).items():
        a = cv.attributes.new(an, "FLOAT", "CURVE"); a.data.foreach_set("value", np.asarray(vals, np.float32))
    o = bpy.data.objects.new(name, cv)
    C_HAIR.objects.link(o)
    cv.materials.append(mat)
    return o


def mat_hair(name, melanin, redness, rough, rad_rough, coat=0.05, rand_col=0.12, lighten_attr=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (600, 0))
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled"); h.location = (300, 0)
    h.model = "CHIANG"; h.parametrization = "MELANIN"
    h.inputs["Melanin"].default_value = melanin
    h.inputs["Melanin Redness"].default_value = redness
    h.inputs["Roughness"].default_value = rough
    h.inputs["Radial Roughness"].default_value = rad_rough
    h.inputs["Coat"].default_value = coat
    h.inputs["Random Color"].default_value = rand_col
    h.inputs["Random Roughness"].default_value = 0.15
    if lighten_attr:
        at = node(nt, "ShaderNodeAttribute", (-200, 0)); at.attribute_name = lighten_attr
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (0, 0)
        mr.inputs[3].default_value = melanin; mr.inputs[4].default_value = melanin - 0.10
        L.new(at.outputs["Fac"], mr.inputs[0]); L.new(mr.outputs[0], h.inputs["Melanin"])
    L.new(h.outputs[0], out.inputs[0])
    return m


def surf(p):
    loc, nrm, idx, dist = bvh.find_nearest(Vector(p))
    return np.array(loc), np.array(nrm)


def push_out(path, min_off):
    for i in range(1, len(path)):
        loc, nrm, idx, dist = bvh.find_nearest(Vector(path[i]))
        if loc is None:
            continue
        loc = np.array(loc); nrm = np.array(nrm)
        dv = path[i] - loc
        sd = np.dot(dv, nrm)
        if sd < min_off:
            path[i] = path[i] + nrm * (min_off - sd)
    return path


def sample_on_faces(weight_v, count, extra_filter=None):
    """area*weight sampling of points on body tris; returns points, normals, bary-weights"""
    tris = []
    for p in me.polygons:
        vs = list(p.vertices)
        for k in range(1, len(vs) - 1):
            tris.append((vs[0], vs[k], vs[k + 1]))
    tris = np.array(tris)
    w = weight_v[tris].mean(1)
    a = np.linalg.norm(np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]]), axis=1) * 0.5
    pr = a * w
    pr = pr / pr.sum()
    pick = rng.choice(len(tris), size=count, p=pr)
    u = rng.random((count, 2)); flip = u.sum(1) > 1; u[flip] = 1 - u[flip]
    t = tris[pick]
    pts = P[t[:, 0]] * (1 - u[:, :1] - u[:, 1:]) + P[t[:, 1]] * u[:, :1] + P[t[:, 2]] * u[:, 1:]
    nrm = N[t[:, 0]] * (1 - u[:, :1] - u[:, 1:]) + N[t[:, 1]] * u[:, :1] + N[t[:, 2]] * u[:, 1:]
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    wv = weight_v[t[:, 0]] * (1 - u[:, 0] - u[:, 1]) + weight_v[t[:, 1]] * u[:, 0] + weight_v[t[:, 2]] * u[:, 1]
    return pts, nrm, wv


def tangentize(d, n):
    d = d - n * np.dot(d, n)
    l = np.linalg.norm(d)
    return d / l if l > 1e-9 else d

# ---------------------------------------------------------------- scalp hair (guides + clumped children)
WHORL = np.array([0.018, 0.012, 1.742])
N_GUIDE, N_CHILD, K = 2600, 60000, 20


def comb_dir(p, n):
    v = tangentize(p - WHORL, n)
    front = smoothstep(-0.08, -0.13, p[1])  # front region -> sweep to character's right (-x) and down onto forehead
    v = v + front * np.array([-0.35, -0.15, -0.25])
    side = smoothstep(0.045, 0.07, abs(p[0])) * (1 - front)
    v = v + side * np.array([0, 0.05, -0.6])
    return tangentize(v, n)


def grow(root, n, length, lift_deg, layer, wave_amp, wave_len, phase, curl_dir):
    pts = [root + n * 0.0004]
    d = np.cos(np.radians(lift_deg)) * comb_dir(root, n) + np.sin(np.radians(lift_deg)) * n
    d /= np.linalg.norm(d)
    seg = length / (K - 1)
    for i in range(1, K):
        t = i / (K - 1)
        p = pts[-1] + d * seg
        loc, nn = surf(p)
        c = comb_dir(p, nn)
        g = np.array([0, 0, -1.0]) * (0.45 + 0.6 * smoothstep(1.66, 1.6, p[2]) + 0.4 * t)
        d = d + 0.55 * c * seg / 0.01 * 0.25 + g * seg / 0.01 * 0.12
        # lie down progressively but keep volume layer
        dist = np.dot(p - loc, nn)
        target = 0.003 + layer
        d = d + nn * (target - dist) * 18.0 * seg
        d /= np.linalg.norm(d)
        pts.append(p)
    pts = np.array(pts)
    # waves / loose curls perpendicular to the strand
    T = np.gradient(pts, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    b1 = np.cross(T, n); b1 /= (np.linalg.norm(b1, axis=1, keepdims=True) + 1e-9)
    b2 = np.cross(T, b1)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    ramp = smoothstep(0.0, 0.35 * length, s)[:, None]
    ang = phase + 2 * np.pi * s / wave_len
    pts = pts + ramp * wave_amp * (np.cos(ang)[:, None] * b1 + curl_dir * 0.65 * np.sin(ang)[:, None] * b2)
    return push_out(pts, 0.0025)


def hair_len(p):
    t = np.clip((p[2] - 1.60) / (1.745 - 1.60), 0, 1)
    L = 0.030 + 0.055 * t ** 1.1
    if p[1] < -0.09:
        L += 0.012  # fringe
    if p[2] < 1.63 and p[1] > -0.02:
        L *= 0.8  # nape shorter
    return L

g_pts, g_n, g_w = sample_on_faces(scalp, N_GUIDE)
guides = []
for i in range(N_GUIDE):
    p, n = g_pts[i], g_n[i]
    top = smoothstep(1.66, 1.72, p[2])
    L = hair_len(p) * rng.uniform(0.9, 1.15) * (0.75 + 0.25 * g_w[i])
    guides.append(grow(p, n, L, lift_deg=8 + 16 * top, layer=rng.uniform(0.0, 0.002 + 0.009 * top),
                       wave_amp=rng.uniform(0.0035, 0.006) * (0.45 + 0.7 * top), wave_len=rng.uniform(0.042, 0.06),
                       phase=rng.uniform(0, 6.28), curl_dir=rng.choice([-1, 1])))
kd = kdtree.KDTree(N_GUIDE)
for i, p in enumerate(g_pts):
    kd.insert(Vector(p), i)
kd.balance()
c_pts, c_n, c_w = sample_on_faces(scalp ** 1.5, N_CHILD)
children, radii, hl_attr = [], [], []
tK = np.linspace(0, 1, K)
for i in range(N_CHILD):
    p, n, w = c_pts[i], c_n[i], c_w[i]
    _, gi, _ = kd.find(Vector(p))
    G = guides[gi]
    off = p - g_pts[gi]
    lf = rng.uniform(0.82, 1.0) * (0.7 + 0.3 * w)
    # resample guide along its length to lf
    s = np.linspace(0, lf, K) * (K - 1)
    i0 = np.floor(s).astype(int).clip(0, K - 2); fr = (s - i0)[:, None]
    g = G[i0] * (1 - fr) + G[i0 + 1] * fr
    clump = (0.58 + 0.17 * rng.random()) * tK[:, None] ** 1.1
    c = g + off * (1 - clump)
    c += (rng.normal(0, 1, 3) * 0.0008 + rng.normal(0, 1, (K, 3)) * 0.00008) * tK[:, None]
    if rng.random() < 0.012:  # flyaways
        c += np.outer(tK ** 2, rng.normal(0, 1, 3)) * rng.uniform(0.006, 0.016)
    c[0] = p + n * 0.0003
    children.append(c)
    rr = (0.000038 * (1 - tK) + 0.000012 * tK) * (0.6 + 0.4 * w)
    radii.append(rr)
    hl_attr.append(1 - w)
print("pushing children out of scalp ...")
for i in range(N_CHILD):
    children[i] = push_out(children[i], 0.0012)
M_HAIR = mat_hair("MAT_Hair_Scalp", 0.975, 0.25, 0.34, 0.4, coat=0.06, rand_col=0.1, lighten_attr="hairline")
hair_obj = make_curves("HAIR_Scalp", children, np.concatenate(radii), M_HAIR, {"hairline": hl_attr})

# ---------------------------------------------------------------- eyebrows
brows, brad = [], []
for s in "lr":
    sx = 1 if s == "l" else -1
    ez = E[s][2]
    for k in range(750):
        u = rng.random() ** 0.85
        x = sx * (0.0105 + 0.051 * u)
        zc = ez + 0.0195 + 0.0045 * math.sin(math.pi * min(u / 0.75, 1) * 0.5) - 0.0075 * max(0, u - 0.65) ** 1.5 * 6
        h = 0.0105 * (1 - u) + 0.0042 * u
        v = rng.normal(0, 0.32) * h
        if abs(v) > 0.5 * h:
            continue
        hit = bvh.ray_cast(Vector((x, -0.4, zc + v)), Vector((0, 1, 0)))
        if hit[0] is None:
            continue
        root = np.array(hit[0]); n = np.array(hit[1])
        d2 = np.array([sx * (0.15 + 1.0 * smoothstep(0.05, 0.3, u)), 0, 1.0 - 1.2 * smoothstep(0.05, 0.35, u) - 0.35 * smoothstep(0.6, 1.0, u)])
        d2 += rng.normal(0, 0.15, 3); d2[1] = 0
        d = tangentize(d2, n) * math.cos(math.radians(14)) + n * math.sin(math.radians(14))
        L = rng.uniform(0.0055, 0.0095) * (0.8 if u < 0.15 else 1.0)
        pts = [root]
        for j in range(1, 5):
            p = pts[-1] + d * L / 4
            loc, nn = surf(p)
            d = tangentize(d, nn) * 0.85 + nn * 0.08; d /= np.linalg.norm(d)
            pts.append(p)
        brows.append(push_out(np.array(pts), 0.0003))
        brad.append(np.linspace(0.000045, 0.000012, 5))
M_BROW = mat_hair("MAT_Hair_Brows", 0.95, 0.3, 0.35, 0.4, rand_col=0.2)
brow_obj = make_curves("HAIR_Eyebrows", brows, np.concatenate(brad), M_BROW)

# ---------------------------------------------------------------- eyelashes (from MakeHuman lash-strip helpers)
lashes, lrad = [], []
for s_ in "lr":
    for k in (1, 2):
        idx = np.array(LM[f"lash_{s_}_{k}_idx"]); V_ = np.array(LM[f"lash_{s_}_{k}_verts"])
        g2l = {int(g): i for i, g in enumerate(idx)}
        dist = np.array([bvh.find_nearest(Vector(v))[3] for v in V_])
        root_v = dist < np.median(dist)
        faces = [[g2l[i] for i in f] for f in LM[f"lash_{s_}_{k}_faces"]]
        upper = V_[:, 2].mean() > E[s_][2]
        quads = []
        for f in faces:
            if len(f) != 4:
                continue
            rv = [root_v[i] for i in f]
            if sum(rv) != 2:
                continue
            for j in range(4):  # rotate so f[0],f[1] are root, f[3]~f[0], f[2]~f[1]
                ff = f[j:] + f[:j]
                if root_v[ff[0]] and root_v[ff[1]]:
                    quads.append(ff); break
        n_l = 240 if upper else 55
        print("lash strip", s_, k, "upper" if upper else "lower", "quads", len(quads))
        for q in range(n_l):
            a_, b_, c_, d_ = quads[rng.integers(len(quads))]
            u = rng.random()
            r0 = V_[a_] * (1 - u) + V_[b_] * u
            t0 = V_[d_] * (1 - u) + V_[c_] * u
            vec = t0 - r0
            L = np.linalg.norm(vec) * rng.uniform(0.65, 1.05) * (1.25 if upper else 0.5)
            dirv = vec / np.linalg.norm(vec)
            up = np.array([0, 0, 1.0 if upper else -1.0])
            seg = []
            for j in range(6):
                t = j / 5
                pnt = r0 + dirv * L * t + up * L * 0.28 * t * t + rng.normal(0, 0.00012, 3) * t
                seg.append(pnt)
            lashes.append(np.array(seg))
            lrad.append(np.linspace(0.00005, 0.000012, 6))
M_LASH = mat_hair("MAT_Hair_Lashes", 0.95, 0.3, 0.3, 0.35, rand_col=0.05)
lash_obj = make_curves("HAIR_Eyelashes", lashes, np.concatenate(lrad), M_LASH)

# ---------------------------------------------------------------- peach fuzz (vellus hair) on the face
face_w = ((P[:, 1] < -0.06) & (P[:, 2] > 1.515) & (az < 85)).astype(float)
face_w *= 1 - scalp
face_w *= 1 - masks[:, 3]
for s in "lr":
    face_w *= np.linalg.norm(P - E[s], axis=1) > EYE_R[s] + 0.006
face_w *= smoothstep(1.515, 1.53, P[:, 2])
fz_pts, fz_n, fz_w = sample_on_faces(face_w, 26000)
fuzz, frad = [], []
for i in range(len(fz_pts)):
    p, n = fz_pts[i], fz_n[i]
    d2 = np.array([np.sign(p[0]) * 0.4, 0, -1.0]) + rng.normal(0, 0.35, 3)
    d = tangentize(d2, n) * math.cos(math.radians(18)) + n * math.sin(math.radians(18))
    L = rng.uniform(0.0012, 0.0028)
    fuzz.append(np.array([p, p + d * L * 0.5, p + d * L + n * 0.0001]))
    frad.append([0.0000075, 0.000005, 0.000003])
M_FUZZ = mat_hair("MAT_Hair_PeachFuzz", 0.28, 0.5, 0.35, 0.4, rand_col=0.3)
fuzz_obj = make_curves("HAIR_PeachFuzz", fuzz, np.concatenate(frad), M_FUZZ)

# ---------------------------------------------------------------- bind everything to the head bone
bpy.context.view_layer.update()
for o in eye_objs + [hair_obj, brow_obj, lash_obj, fuzz_obj]:
    mw = o.matrix_world.copy()
    o.parent = rig; o.parent_type = "BONE"; o.parent_bone = "head"
    bpy.context.view_layer.update()
    o.matrix_world = mw
save_json("head_info.json", {"eye_r": EYE_R, "lip_z": LIP_Z, "nose": NOSE.tolist()})
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "head.blend"))
print("OK head: strands", len(children), "brows", len(brows), "lashes", len(lashes), "fuzz", len(fuzz))
