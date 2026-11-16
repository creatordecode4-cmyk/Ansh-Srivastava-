"""Step 1: realistic base body from the MakeHuman/MPFB2 base mesh (CC0) + morph targets.
Teen male (~17 y), slim, 1.75 m. Builds armature from MPFB2 default rig + skin weights.
Writes work/body.blend and work/landmarks.json.
"""
import sys, os, gzip, json, math
import numpy as np
import bpy, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from common import *

T = os.path.join(MPFB, "targets")

# ---------------------------------------------------------------- parse OBJ
V, VT, F, FT, FG = [], [], [], [], []
group = None
for line in open(os.path.join(MPFB, "3dobjs", "base.obj")):
    if line.startswith("v "):
        V.append([float(x) for x in line.split()[1:4]])
    elif line.startswith("vt "):
        VT.append([float(x) for x in line.split()[1:3]])
    elif line.startswith("g "):
        group = line.split()[1]
    elif line.startswith("f "):
        vs, ts = [], []
        for tok in line.split()[1:]:
            p = tok.split("/")
            vs.append(int(p[0]) - 1)
            ts.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
        F.append(vs); FT.append(ts); FG.append(group)
V = np.array(V, dtype=np.float64)
print("base verts", V.shape, "faces", len(F))


def load_target(rel):
    p = os.path.join(T, rel)
    if not p.endswith(".gz"):
        p += ".target.gz"
    d = np.zeros_like(V)
    txt = gzip.open(p).read().decode()
    for ln in txt.splitlines():
        s = ln.split()
        if len(s) == 4 and not ln.startswith("#"):
            d[int(s[0])] = [float(s[1]), float(s[2]), float(s[3])]
    return d

# ---------------------------------------------------------------- macro weights (MakeHuman formulas)
GENDER, AGE_Y, MUSCLE, WEIGHT, PROP, HEIGHT = 1.0, 17.0, 0.52, 0.36, 0.75, 0.62
age = (AGE_Y - 1.0) / 48.0  # MakeHuman: 0 -> 1y, 0.5 -> 25y
w_gender = {"male": GENDER, "female": 1 - GENDER}
young = max(0.0, (age - 0.1875) * 3.2) if age < 0.5 else 1 - (age - 0.5) * 2
w_age = {"baby": max(0.0, 1 - age * 5.3333), "young": young,
         "child": max(0.0, min(1.0, 5.3333 * age) - young), "old": 0.0}


def tri(v, lo, mid, hi):
    a = max(0.0, 1 - 2 * v); c = max(0.0, 2 * v - 1)
    return {lo: a, mid: 1 - a - c, hi: c}

w_mus = tri(MUSCLE, "minmuscle", "averagemuscle", "maxmuscle")
w_wt = tri(WEIGHT, "minweight", "averageweight", "maxweight")
w_prop = {"idealproportions": max(0.0, (PROP - 0.5) * 2), "uncommonproportions": max(0.0, (0.5 - PROP) * 2)}
w_h = {"maxheight": max(0.0, (HEIGHT - 0.5) * 2), "minheight": max(0.0, (0.5 - HEIGHT) * 2)}
print("age weights", w_age, "muscle", w_mus, "weight", w_wt)

D = np.zeros_like(V)
for g, wg in w_gender.items():
    for a, wa in w_age.items():
        if wg * wa < 1e-4:
            continue
        D += load_target(f"macrodetails/caucasian-{g}-{a}") * (wg * wa)
        for m, wm in w_mus.items():
            for wt, ww in w_wt.items():
                w = wg * wa * wm * ww
                if w < 1e-4:
                    continue
                D += load_target(f"macrodetails/universal-{g}-{a}-{m}-{wt}") * w
                for pn, pw in w_prop.items():
                    if pw * w > 1e-4:
                        D += load_target(f"macrodetails/proportions/{g}-{a}-{m}-{wt}-{pn}") * (w * pw)
                for hn, hw in w_h.items():
                    if hw * w > 1e-4:
                        D += load_target(f"macrodetails/height/{g}-{a}-{m}-{wt}-{hn}") * (w * hw)

# ---------------------------------------------------------------- face / identity details (subtle)
DETAIL = {
    "head/head-age-decr": 0.25,          # youthful skull
    "head/head-oval": 0.35,
    "head/head-scale-horiz-decr": 0.30,
    "head/head-scale-vert-decr": 0.45,
    "head/head-scale-depth-decr": 0.30,
    "neck/neck-scale-vert-incr": 0.25,
    "chin/chin-width-decr": 0.25,
    "chin/chin-prominent-incr": 0.15,
    "cheek/l-cheek-bones-incr": 0.15, "cheek/r-cheek-bones-incr": 0.12,
    "nose/nose-point-width-decr": 0.3,
    "nose/nose-scale-horiz-decr": 0.2,
    "nose/nose-point-up": 0.15,
    "mouth/mouth-angles-up": 0.25,
    "eyebrows/eyebrows-trans-down": 0.15,
    "expression/units/caucasian/eye-left-slit": 0.14, "expression/units/caucasian/eye-right-slit": 0.14,
    # soft closed-mouth smile
    "expression/units/caucasian/mouth-corner-puller": 0.22,
    "expression/units/caucasian/mouth-compression": 0.35,
    # natural asymmetry
    "asym/asym-eye-1-l": 0.25, "asym/asym-brown-1-r": 0.3, "asym/asym-mouth-1-l": 0.25,
    "asym/asym-nose-2-r": 0.25, "asym/asym-jaw-1-l": 0.2, "asym/asym-cheek-1-r": 0.25,
    "asym/asym-ear-1-l": 0.3,
}
for rel, w in DETAIL.items():
    try:
        D += load_target(rel) * w
    except FileNotFoundError:
        print("missing target", rel)
V = V + D

# MakeHuman (dm, Y-up, facing +Z)  ->  Blender (m, Z-up, facing -Y)
P = np.stack([V[:, 0], -V[:, 2], V[:, 1]], 1) * 0.1
body_idx = np.arange(13380)
zmin = P[body_idx, 2].min(); zmax = P[body_idx, 2].max()
s = 1.75 / (zmax - zmin)
P = (P - np.array([0, 0, zmin])) * s
cx = P[body_idx, 0].mean()
P[:, 0] -= 0.0  # keep symmetric axis x=0
print("height before scale %.3f m, scale %.3f" % ((zmax - zmin), s))

# ---------------------------------------------------------------- landmarks from helper geometry
groups = json.load(open(os.path.join(MPFB, "mesh_metadata", "basemesh_vertex_groups.json")))


def gidx(name):
    out = []
    for a, b in groups[name]:
        out += list(range(a, b + 1))
    return np.array(out)

LM = {}
for gname in groups:
    if gname.startswith("joint-"):
        LM[gname] = P[gidx(gname)].mean(0).tolist()
for side in "lr":
    e = P[gidx(f"helper-{side}-eye")]
    c = e.mean(0)
    LM[f"eye_{side}_center"] = c.tolist()
    LM[f"eye_{side}_radius"] = float(np.linalg.norm(e - c, axis=1).mean())
    for k in (1, 2):
        idx = gidx(f"helper-{side}-eyelashes-{k}")
        LM[f"lash_{side}_{k}_verts"] = P[idx].tolist()
        LM[f"lash_{side}_{k}_idx"] = idx.tolist()
# eyelash helper faces (for strip direction)
for side in "lr":
    for k in (1, 2):
        nm = f"helper-{side}-eyelashes-{k}"
        LM[f"lash_{side}_{k}_faces"] = [f for f, g in zip(F, FG) if g == nm]
hair_idx = gidx("helper-hair")
LM["helper_hair"] = P[hair_idx].tolist()
LM["helper_hair_faces"] = [[int(i - hair_idx[0]) for i in f] for f, g in zip(F, FG) if g == "helper-hair"]
tights = gidx("helper-tights")
LM["tights_offset"] = int(tights[0])
LM["tights_verts"] = P[tights].tolist()
LM["tights_faces"] = [[int(i - tights[0]) for i in f] for f, g in zip(F, FG) if g == "helper-tights"]
LM["scale"] = s
save_json("landmarks.json", LM)

# ---------------------------------------------------------------- build body mesh
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 1.0
C_CHAR = coll("CHAR_Teen")
C_BODY = coll("BODY", C_CHAR)

bf = [(f, t) for f, t, g in zip(F, FT, FG) if g == "body"]
me = bpy.data.meshes.new("ME_Body")
me.from_pydata(P[:13380].tolist(), [], [f for f, _ in bf])
uv = me.uv_layers.new(name="UVMap")
loop_uv = []
for f, t in bf:
    for ti in t:
        loop_uv.extend(VT[ti])
uv.data.foreach_set("uv", loop_uv)
me.validate(); me.update()
for p in me.polygons:
    p.use_smooth = True
body = bpy.data.objects.new("GEO_Body", me)
C_BODY.objects.link(body)

# vertex groups for body regions (useful downstream)
for gname in ("Left", "Right", "Mid"):
    vg = body.vertex_groups.new(name="side_" + gname)
    vg.add([int(i) for i in gidx(gname) if i < 13380], 1.0, "REPLACE")

# ---------------------------------------------------------------- armature
rig = json.load(open(os.path.join(MPFB, "rigs", "standard", "rig.default.json")))


def jpos(spec):
    st = spec["strategy"]
    if st == "CUBE":
        return Vector(LM[spec["cube_name"]])
    if st == "VERTEX":
        return Vector(P[spec["vertex_index"]].tolist())
    if st == "MEAN":
        return Vector(P[spec["vertex_indices"]].mean(0).tolist())
    raise ValueError(st)

arm_data = bpy.data.armatures.new("ARM_Teen")
arm = bpy.data.objects.new("RIG_Teen", arm_data)
C_CHAR.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
for name, b in rig.items():
    e = eb.new(name)
    e.head = jpos(b["head"]); e.tail = jpos(b["tail"])
    if (e.tail - e.head).length < 1e-4:
        e.tail = e.head + Vector((0, 0, 0.01))
    e.roll = b.get("roll", 0.0)
for name, b in rig.items():
    if b.get("parent"):
        eb[name].parent = eb[b["parent"]]
        eb[name].use_connect = b.get("use_connect", False)
bpy.ops.object.mode_set(mode="OBJECT")
arm_data.display_type = "STICK"

W = json.load(open(os.path.join(MPFB, "rigs", "standard", "weights.default.json")))["weights"]
for bone, lst in W.items():
    vg = body.vertex_groups.new(name=bone)
    for vi, w in lst:
        if vi < 13380:
            vg.add([vi], w, "ADD")
mod = body.modifiers.new("Armature", "ARMATURE"); mod.object = arm
body.parent = arm

# rest-pose copy of vertex positions for clothing generation
np.save(os.path.join(WORK, "body_rest.npy"), P[:13380])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "body.blend"))
print("OK body", len(me.vertices), "bones", len(arm_data.bones))
