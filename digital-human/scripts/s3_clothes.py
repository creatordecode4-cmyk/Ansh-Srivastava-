"""Step 3: clothing in rest pose -- crew-neck T-shirt, loose trousers, low-top sneakers.
Garments are separate meshes (thickness via Solidify after the cloth sim), skinned to the rig.
Reads work/head.blend -> work/clothes.blend
"""
import sys, os, math
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from scipy.spatial import cKDTree, ConvexHull
sys.path.insert(0, os.path.dirname(__file__))
from common import *

rng = np.random.default_rng(11)
bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "head.blend"))
LM = load_json("landmarks.json")
body = bpy.data.objects["GEO_Body"]; rig = bpy.data.objects["RIG_Teen"]
me = body.data
P = np.array([v.co[:] for v in me.vertices]); NV = len(P)
N = np.array([v.normal[:] for v in me.vertices])
C_CHAR = bpy.data.collections["CHAR_Teen"]
C_CLO = coll("CLOTHES", C_CHAR)
J = lambda k: np.array(LM[k])


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def extract(name, vmask, offset_fn, subdiv=1, smooth_iter=0):
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [f for f in bm.faces if not all(vmask[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # drop tiny islands
    seen, islands = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        islands.append(isl)
    big = max(len(i) for i in islands)
    small = [f for isl in islands if len(isl) < 0.05 * big for f in isl]
    if small:
        bmesh.ops.delete(bm, geom=small, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.verts.ensure_lookup_table()
    orig = [v.co.copy() for v in bm.verts]
    for v in bm.verts:
        v.co = Vector(np.array(v.co) + np.array(v.normal) * offset_fn(np.array(v.co)))
    if smooth_iter:
        inner = [v for v in bm.verts if not v.is_boundary]
        for _ in range(smooth_iter):
            bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if subdiv:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=subdiv, use_grid_fill=True, smooth=0.5)
    m = bpy.data.meshes.new(name); bm.to_mesh(m); bm.free()
    for p in m.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, m); C_CLO.objects.link(o)
    return o


def skin_to_body(o):
    for vg in body.vertex_groups:
        if vg.name in rig.data.bones and vg.name not in o.vertex_groups:
            o.vertex_groups.new(name=vg.name)
    dt = o.modifiers.new("DT", "DATA_TRANSFER")
    dt.object = body; dt.use_vert_data = True; dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"; dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier="DT")
    am = o.modifiers.new("Armature", "ARMATURE"); am.object = rig
    o.parent = rig


def set_attr(o, name, vals, typ="FLOAT"):
    a = o.data.attributes.get(name) or o.data.attributes.new(name, typ, "POINT")
    if typ == "FLOAT":
        a.data.foreach_set("value", np.asarray(vals, np.float32).ravel())
    else:
        a.data.foreach_set("vector", np.asarray(vals, np.float32).ravel())


def verts_np(o):
    return np.array([v.co[:] for v in o.data.vertices])


def boundary_mask(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    m = np.array([v.is_boundary for v in bm.verts]); bm.free()
    return m


def vgroup(o, name, w):
    vg = o.vertex_groups.get(name) or o.vertex_groups.new(name=name)
    for i, x in enumerate(w):
        if x > 1e-3:
            vg.add([i], float(x), "REPLACE")
    return vg

# ---------------------------------------------------------------- regions
def arm_t(p, side):
    S = J(f"joint-{side}-shoulder"); E = J(f"joint-{side}-elbow")
    a = E - S
    t = ((p - S) @ a) / (a @ a)
    d = np.linalg.norm(p - (S + np.outer(t, a)), axis=1)
    return t, d

tl, dl = arm_t(P, "l"); tr, dr = arm_t(P, "r")
is_l = P[:, 0] > 0
t_arm = np.where(is_l, tl, tr); d_arm = np.where(is_l, dl, dr)
armish = (t_arm > -0.15) & (d_arm < 0.075) & (np.abs(P[:, 0]) > 0.13)
az = np.degrees(np.arctan2(np.abs(P[:, 0]), -(P[:, 1] + 0.01)))
neckline = np.interp(az, [0, 35, 70, 110, 150, 180], [1.425, 1.433, 1.452, 1.468, 1.478, 1.482])

# ---------------------------------------------------------------- T-shirt
HEM = 0.872
ell_e = np.sqrt((P[:, 0] / 0.088) ** 2 + ((P[:, 1] + 0.012) / 0.080) ** 2)
neck_open = (ell_e < 1.0) & (P[:, 2] > neckline)
tee_mask = (P[:, 2] > HEM) & (P[:, 2] < 1.53) & ~(armish & (t_arm > 0.50)) & ~neck_open & ~((ell_e < 0.8) & (P[:, 2] > 1.47))
tee_mask &= ~((np.abs(P[:, 0]) > 0.24) & ~armish)
kd_body = cKDTree(P)


def tee_off(p):
    i = kd_body.query(p)[1]
    if armish[i]:
        return 0.011 + 0.012 * max(0.0, t_arm[i])
    lower = float(smoothstep(1.18, 0.90, p[2]))
    return 0.009 + 0.022 * lower + 0.005 * float(smoothstep(-0.05, -0.12, p[1]))

tee = extract("GEO_Tshirt", tee_mask, tee_off, subdiv=1, smooth_iter=3)
TV = verts_np(tee)
bmask = boundary_mask(tee)
for i in np.where(bmask)[0]:
    if TV[i, 2] < 1.0:
        TV[i, 2] = HEM + 0.004
for i, v in enumerate(tee.data.vertices):
    v.co = TV[i]
bpts = TV[bmask]
neck_b = bpts[bpts[:, 2] > 1.35]
hem_b = bpts[bpts[:, 2] < 1.0]
slv_b = bpts[(bpts[:, 2] <= 1.35) & (bpts[:, 2] >= 1.0)]
d_neck = cKDTree(neck_b).query(TV)[0]
d_hem = np.minimum(cKDTree(hem_b).query(TV)[0], cKDTree(slv_b).query(TV)[0] if len(slv_b) else 9)
# side + shoulder + armhole seams
ti, di = arm_t(TV, "l"); ti2, di2 = arm_t(TV, "r")
tarm = np.where(TV[:, 0] > 0, ti, ti2)
seam = np.zeros(len(TV))
seam = np.maximum(seam, 1 - smoothstep(0.0, 0.006, np.abs(tarm - 0.02)) * (np.abs(TV[:, 0]) > 0.12))  # armhole ring
side_y = np.interp(TV[:, 2], [0.85, 1.3], [0.005, 0.0])
seam = np.maximum(seam, (1 - smoothstep(0.0, 0.006, np.abs(TV[:, 1] - side_y))) * (np.abs(TV[:, 0]) > 0.08) * (TV[:, 2] < 1.30) * (np.abs(tarm) > 0.05))
set_attr(tee, "rest_pos", TV, "FLOAT_VECTOR")
set_attr(tee, "d_neck", d_neck); set_attr(tee, "d_hem", d_hem); set_attr(tee, "seam", seam)
skin_to_body(tee)
# armpits: arm and torso squeeze the cloth here when the arms come down -> follow the skin
armpit = np.zeros(len(TV))
for side in "lr":
    S = J(f"joint-{side}-shoulder")
    d = np.linalg.norm((TV - (S + np.array([0, 0.0, -0.075]))) / np.array([0.075, 0.09, 0.085]), axis=1)
    armpit = np.maximum(armpit, 1 - smoothstep(0.55, 1.0, d))
vgroup(tee, "pin", np.maximum(0.8 * (1 - smoothstep(0.0, 0.03, d_neck)), 0.9 * armpit))
print("tee verts", len(TV))

# ---------------------------------------------------------------- trousers
WAIST = np.interp(az, [0, 90, 180], [0.952, 0.965, 0.985])
legs_axis = {s: (J(f"joint-{s}-upper-leg"), J(f"joint-{s}-ankle")) for s in "lr"}
tro_mask = (P[:, 2] < WAIST) & (P[:, 2] > 0.150) & ~((np.abs(P[:, 0]) > 0.26)) & ~armish
handish = np.zeros(NV, bool)
for nm in [f"finger{i}-{j}.{s}" for i in range(1, 6) for j in (1, 2, 3) for s in "LR"] + ["wrist.L", "wrist.R", "lowerarm02.L", "lowerarm02.R", "metacarpal1.L", "metacarpal1.R"]:
    vg = body.vertex_groups.get(nm)
    if vg:
        for v in me.vertices:
            for g in v.groups:
                if g.group == vg.index and g.weight > 0.2:
                    handish[v.index] = True
tro_mask &= ~handish


def leg_frame(p):
    s = "l" if p[0] > 0 else "r"
    H, A = legs_axis[s]
    a = A - H
    t = np.clip((p - H) @ a / (a @ a), 0, 1.2)
    c = H + t * a
    return s, t, c


def tro_off(p):
    if p[2] > 0.80:
        return 0.004 + 0.007 * float(smoothstep(0.93, 0.82, p[2]))
    return 0.012


tro = extract("GEO_Trousers", tro_mask, tro_off, subdiv=0)
# loosen legs into straight, slightly tapered tubes (chino / loose fit)
TRV = verts_np(tro)
for i, p in enumerate(TRV):
    if p[2] < 0.84:
        s, t, c = leg_frame(p)
        rv = p - c; rv[2] = 0
        r = np.linalg.norm(rv)
        if r < 1e-6:
            continue
        target = np.interp(p[2], [0.08, 0.30, 0.50, 0.70, 0.84], [0.064, 0.067, 0.072, 0.083, 0.090])
        w = float(smoothstep(0.86, 0.74, p[2]))
        r_new = max(r, (1 - w) * r + w * max(r + 0.006, 0.35 * r + 0.65 * target))
        TRV[i] = c + rv / r * r_new + np.array([0, 0, p[2] - c[2]])
for i, v in enumerate(tro.data.vertices):
    v.co = TRV[i]
# lengthen the hems so they break over the sneakers
bm = bmesh.new(); bm.from_mesh(tro.data)
hem_edges = [e for e in bm.edges if e.is_boundary and all(v.co.z < 0.3 for v in e.verts)]
for v in {v for e in hem_edges for v in e.verts}:
    v.co.z = 0.152
for k in range(1, 4):
    res = bmesh.ops.extrude_edge_only(bm, edges=hem_edges)
    nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in nv:
        A = legs_axis["l" if v.co.x > 0 else "r"][1]
        rv = Vector((v.co.x - A[0], v.co.y - A[1], 0)).normalized()
        r = 0.068 + 0.0015 * k
        v.co = Vector((A[0], A[1] + 0.006, 0)) + rv * r + Vector((0, 0, 0.152 - 0.0195 * k))
    hem_edges = [g for g in res["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary and all(v.co.z < 0.3 for v in g.verts)]
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True, smooth=0.5)
bm.to_mesh(tro.data); bm.free()
for p in tro.data.polygons:
    p.use_smooth = True
TRV = verts_np(tro)
bmask = boundary_mask(tro)
bp = TRV[bmask]
waist_b = bp[bp[:, 2] > 0.5]; hem_b2 = bp[bp[:, 2] < 0.5]
d_waist = cKDTree(waist_b).query(TRV)[0]
d_hem2 = cKDTree(hem_b2).query(TRV)[0]
# pocket opening line (front slant pocket) + side seams + fly
pocket = np.zeros(len(TRV)); seam2 = np.zeros(len(TRV))
for s in (1, -1):
    a0 = np.array([s * 0.095, -0.10, 0.950]); a1 = np.array([s * 0.165, -0.04, 0.80])
    ab = a1 - a0
    t = np.clip(((TRV - a0) @ ab) / (ab @ ab), 0, 1)
    d = np.linalg.norm(TRV - (a0 + np.outer(t, ab)), axis=1)
    pocket = np.maximum(pocket, (1 - smoothstep(0.0, 0.012, d)) * (TRV[:, 1] < 0.0) * (s * TRV[:, 0] > 0))
for i, p in enumerate(TRV):
    if p[2] < 0.86:
        s, t, c = leg_frame(p)
        ang = math.degrees(math.atan2((p[0] - c[0]) * (1 if s == "l" else -1), -(p[1] - c[1])))
        seam2[i] = max(1 - smoothstep(0, 9, abs(abs(ang) - 90)) * 0 - 0, 0)
        seam2[i] = max(1 - float(smoothstep(0.0, 8.0, abs(ang - 90))), 1 - float(smoothstep(0.0, 8.0, abs(ang + 90))))
fly = (1 - smoothstep(0.0, 0.004, np.abs(TRV[:, 0] - 0.018))) * (TRV[:, 1] < 0) * (TRV[:, 2] > 0.835) * (TRV[:, 2] < 0.94)
seam2 = np.maximum(seam2, fly)
set_attr(tro, "rest_pos", TRV, "FLOAT_VECTOR")
set_attr(tro, "d_waist", d_waist); set_attr(tro, "d_hem", d_hem2); set_attr(tro, "pocket", pocket); set_attr(tro, "seam", seam2)
skin_to_body(tro)
vgroup(tro, "pin", 1 - smoothstep(0.010, 0.028, d_waist))
print("trouser verts", len(TRV))

# ---------------------------------------------------------------- sneakers
SOLE_T = 0.024
shoes = []
for s in "lr":
    sx = 1 if s == "l" else -1
    fm = (P[:, 2] < 0.125) & (sx * P[:, 0] > 0.12)
    FP = P[fm]
    cx = float(np.median(FP[:, 0]))
    heel_y = FP[:, 1].max(); toe_y = FP[:, 1].min()

    # ---- parametric shoe last fitted to the foot (loft of super-elliptic sections)
    NU, NM = 64, 48
    L0 = heel_y - toe_y
    ys = heel_y + 0.008 - np.linspace(0, 1, NU) ** 1.0 * (L0 + 0.026)
    A, CX, H = [], [], []
    for y in ys:
        sl = FP[(np.abs(FP[:, 1] - y) < 0.008) & (FP[:, 2] < 0.10)]
        if len(sl) > 3:
            A.append((sl[:, 0].max() - sl[:, 0].min()) / 2); CX.append((sl[:, 0].max() + sl[:, 0].min()) / 2); H.append(sl[:, 2].max())
        else:
            A.append(np.nan); CX.append(np.nan); H.append(np.nan)
    def fill(a):
        a = np.array(a, float); idx = np.arange(len(a)); ok = ~np.isnan(a)
        a = np.interp(idx, idx[ok], a[ok])
        k = np.exp(-0.5 * (np.arange(-6, 7) / 2.5) ** 2); k /= k.sum()
        return np.convolve(np.pad(a, 6, mode="edge"), k, mode="valid")
    A, CX, H = fill(A), fill(CX), fill(H)
    uu = np.linspace(0, 1, NU)
    A = A + 0.0085
    H = np.minimum(H + 0.013, 0.098)
    H = H * (1 - 0.40 * smoothstep(0.62, 1.0, uu)) + 0.012 * smoothstep(0.62, 1.0, uu)  # lower toe box
    H = np.maximum(H, 0.040)
    endf = np.where(uu < 0.5, (1 - ((0.5 - uu) / 0.5) ** 7) ** (1 / 7), (1 - ((uu - 0.5) / 0.5) ** 4.5) ** (1 / 4.5))
    endf = np.clip(endf, 0.0, 1)
    ZB = -0.004
    verts = []
    for i in range(NU):
        a = max(A[i] * endf[i], 0.0005); hh = ZB + (H[i] - ZB) * max(endf[i], 0.35 if 0 < i < NU - 1 else 0.3)
        zm = (hh + ZB) / 2; b = (hh - ZB) / 2
        for j in range(NM):
            th = 2 * math.pi * j / NM - math.pi / 2  # start at bottom centre
            c, s_ = math.cos(th), math.sin(th)
            x = CX[i] + a * np.sign(c) * abs(c) ** (2 / 2.8)
            z = zm + b * np.sign(s_) * abs(s_) ** (2 / (2.2 if s_ > 0 else 5.0))
            verts.append((x, ys[i], max(z, ZB)))
    faces = []
    for i in range(NU - 1):
        for j in range(NM):
            a_ = i * NM + j; b_ = i * NM + (j + 1) % NM
            faces.append((a_, b_, b_ + NM, a_ + NM))
    um = bpy.data.meshes.new(f"GEO_Sneaker_Upper_{s.upper()}")
    um.from_pydata(verts, [], faces)
    bm = bmesh.new(); bm.from_mesh(um)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    # ankle opening (collar): remove top faces around the ankle
    AJ = J(f"joint-{s}-ankle")
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        dx = (c.x - AJ[0]) / 0.040; dy = (c.y - (AJ[1] + 0.012)) / 0.058
        if dx * dx + dy * dy < 1.0 and c.z > 0.045:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(um); bm.free()
    for p in um.polygons:
        p.use_smooth = True
    up = bpy.data.objects.new(um.name, um); C_CLO.objects.link(up)
    UV_ = verts_np(up)
    # shoe-local coords for the shader (u along length 0 heel..1 toe, v across, w height)
    L = heel_y - toe_y + 0.01
    loc = np.stack([(heel_y - UV_[:, 1]) / L, (UV_[:, 0] - cx) * sx, UV_[:, 2]], 1)
    set_attr(up, "shoe_loc", loc, "FLOAT_VECTOR")
    sol = up.modifiers.new("Solidify", "SOLIDIFY"); sol.thickness = 0.005; sol.offset = -1.0; sol.use_rim = True; sol.use_even_offset = True
    sub = up.modifiers.new("Subdivision", "SUBSURF"); sub.levels = 1; sub.render_levels = 2
    # ---- sole: offset convex outline, toe spring, sidewall groove
    low = UV_[UV_[:, 2] < 0.03][:, :2]
    hull = ConvexHull(low)
    poly = low[hull.vertices]
    cen = poly.mean(0)
    # resample outline evenly
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
    ts = np.linspace(0, cum[-1], 97)[:-1]
    outline = np.array([closed[np.searchsorted(cum, t) - 1] + (closed[np.searchsorted(cum, t)] - closed[np.searchsorted(cum, t) - 1]) * ((t - cum[np.searchsorted(cum, t) - 1]) / max(seg[np.searchsorted(cum, t) - 1], 1e-9)) for t in ts])
    nrm2 = outline - cen; nrm2 /= np.linalg.norm(nrm2, axis=1, keepdims=True)
    outline = outline + nrm2 * 0.0045
    rings = [(-SOLE_T, -0.002), (-SOLE_T + 0.004, 0.0), (-0.010, 0.0012), (-0.0075, 0.0004), (-0.0060, 0.0013), (0.004, 0.0008), (0.010, -0.0015), (0.012, -0.004)]
    verts, faces = [], []
    nO = len(outline)
    for zi, (z, dr) in enumerate(rings):
        for k in range(nO):
            q = outline[k] + nrm2[k] * dr
            yy = q[1]
            spring = 0.011 * float(smoothstep(toe_y + 0.07, toe_y - 0.01, yy)) + 0.003 * float(smoothstep(heel_y - 0.05, heel_y + 0.01, yy))
            zz = z + (spring if zi < 2 else spring * 0.4 if zi < 4 else 0)
            verts.append((q[0], q[1], zz))
    for zi in range(len(rings) - 1):
        for k in range(nO):
            a = zi * nO + k; b = zi * nO + (k + 1) % nO
            faces.append((a, b, b + nO, a + nO))
    sm = bpy.data.meshes.new(f"GEO_Sneaker_Sole_{s.upper()}")
    sm.from_pydata(verts, [], faces)
    bm = bmesh.new(); bm.from_mesh(sm)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(sm); bm.free()
    so = bpy.data.objects.new(sm.name, sm); C_CLO.objects.link(so)
    sv = verts_np(so)
    set_attr(so, "shoe_loc", np.stack([(heel_y - sv[:, 1]) / L, (sv[:, 0] - cx) * sx, sv[:, 2]], 1), "FLOAT_VECTOR")
    for p in sm.polygons:
        p.use_smooth = True
    sub = so.modifiers.new("Subdivision", "SUBSURF"); sub.levels = 1; sub.render_levels = 2
    # ---- laces + eyelets on the instep
    bvh_up = BVHTree.FromObject(up, bpy.context.evaluated_depsgraph_get())
    eyelets = {}
    ys = np.linspace(heel_y - 0.105, heel_y - 0.175, 6)
    for k, y in enumerate(ys):
        half = 0.0125 - 0.002 * k / 5
        for side_ in (-1, 1):
            x = cx + sx * (-0.004) + side_ * half
            hit = bvh_up.ray_cast(Vector((x, y, 0.3)), Vector((0, 0, -1)))
            if hit[0] is not None:
                eyelets[(k, side_)] = (np.array(hit[0]), np.array(hit[1]))
    lace_c = bpy.data.curves.new(f"CRV_Laces_{s}", "CURVE"); lace_c.dimensions = "3D"
    lace_c.bevel_depth = 0.0014; lace_c.bevel_resolution = 2
    def add_lace(pts):
        sp = lace_c.splines.new("NURBS"); sp.points.add(len(pts) - 1)
        for i, q in enumerate(pts):
            sp.points[i].co = (*q, 1)
        sp.use_endpoint_u = True; sp.order_u = 3
    for k in range(5):
        for side_ in (-1, 1):
            a = eyelets.get((k, side_)); b = eyelets.get((k + 1, -side_))
            if a is None or b is None:
                continue
            m = (a[0] + b[0]) / 2 + (a[1] + b[1]) / 2 * (0.0035 + 0.001 * (side_ > 0))
            add_lace([a[0] + a[1] * 0.0012, m, b[0] + b[1] * 0.0012])
    # bow at the top eyelets
    a = eyelets.get((0, -1)); b = eyelets.get((0, 1))
    if a is not None and b is not None:
        knot = (a[0] + b[0]) / 2 + (a[1] + b[1]) / 2 * 0.006
        nrm = (a[1] + b[1]) / 2
        for side_ in (-1, 1):
            out = np.array([side_ * 1.0, 0.25, 0]) * np.array([1, 1, 1])
            loop = [knot, knot + out * 0.012 + nrm * 0.006 + np.array([0, -0.004, 0]), knot + out * 0.022 + nrm * 0.002, knot + out * 0.014 + nrm * 0.001 + np.array([0, 0.006, 0]), knot]
            add_lace(loop)
            end = [knot, knot + out * 0.008 + np.array([0, -0.012, -0.004]), knot + out * 0.016 + np.array([0, -0.02, -0.016])]
            add_lace(end)
        add_lace([a[0] + a[1] * 0.001, knot, b[0] + b[1] * 0.001])
    lo = bpy.data.objects.new(f"GEO_Sneaker_Laces_{s.upper()}", lace_c); C_CLO.objects.link(lo)
    # eyelets as small tori
    eye_objs = []
    for (k, side_), (p, n) in eyelets.items():
        bpy.ops.mesh.primitive_torus_add(major_radius=0.0028, minor_radius=0.0008, major_segments=16, minor_segments=6, location=tuple(p + n * 0.0008))
        t = bpy.context.active_object
        t.rotation_euler = Vector(n).to_track_quat("Z", "Y").to_euler()
        eye_objs.append(t)
    with bpy.context.temp_override(active_object=eye_objs[0], selected_editable_objects=eye_objs, object=eye_objs[0]):
        bpy.ops.object.join()
    ey = eye_objs[0]; ey.name = f"GEO_Sneaker_Eyelets_{s.upper()}"; link(ey, C_CLO)
    shoes.append((up, so, lo, ey, s))

# ---------------------------------------------------------------- materials
def mat_tee():
    m = bpy.data.materials.new("MAT_Cotton_Tshirt_Purple")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (1200, 0))
    b = node(nt, "ShaderNodeBsdfPrincipled", (900, 0))
    L.new(b.outputs[0], out.inputs[0])
    rp = node(nt, "ShaderNodeAttribute", (-1200, 0)); rp.attribute_name = "rest_pos"
    dn = node(nt, "ShaderNodeAttribute", (-1200, -250)); dn.attribute_name = "d_neck"
    dh = node(nt, "ShaderNodeAttribute", (-1200, -450)); dh.attribute_name = "d_hem"
    sm = node(nt, "ShaderNodeAttribute", (-1200, -650)); sm.attribute_name = "seam"
    # jersey knit: fine vertical wales + loops
    w1 = node(nt, "ShaderNodeTexWave", (-900, 300), Scale=1400.0, Distortion=1.2, Detail=2.0)
    w1.bands_direction = "X"; w1.wave_profile = "SIN"
    L.new(rp.outputs["Vector"], w1.inputs["Vector"])
    w2 = node(nt, "ShaderNodeTexWave", (-900, 50), Scale=1600.0, Distortion=0.6)
    w2.bands_direction = "Z"; w2.wave_profile = "SIN"
    L.new(rp.outputs["Vector"], w2.inputs["Vector"])
    fz = node(nt, "ShaderNodeTexNoise", (-900, -150), Scale=900.0, Detail=6.0, Roughness=0.7)
    L.new(rp.outputs["Vector"], fz.inputs["Vector"])
    cv = node(nt, "ShaderNodeTexNoise", (-900, 550), Scale=18.0, Detail=3.0)
    L.new(rp.outputs["Vector"], cv.inputs["Vector"])
    col = nt.nodes.new("ShaderNodeMix"); col.data_type = "RGBA"; col.location = (300, 300)
    col.inputs[6].default_value = (0.070, 0.011, 0.25, 1); col.inputs[7].default_value = (0.092, 0.016, 0.30, 1)
    L.new(cv.outputs["Fac"], col.inputs[0])
    L.new(col.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    b.inputs["Sheen Weight"].default_value = 0.10
    b.inputs["Sheen Roughness"].default_value = 0.5
    b.inputs["Sheen Tint"].default_value = (0.55, 0.35, 1.0, 1)
    b.inputs["Specular IOR Level"].default_value = 0.3
    # height: knit + rib on neckband + stitch lines
    mth = lambda op, a, c, loc: _math(nt, op, a, c, loc)
    knit = mth("ADD", mth("MULTIPLY", w1.outputs["Fac"], 0.6, (-600, 300)), mth("MULTIPLY", w2.outputs["Fac"], 0.25, (-600, 100)), (-400, 200))
    knit = mth("ADD", knit, mth("MULTIPLY", fz.outputs["Fac"], 0.5, (-600, -100)), (-250, 150))
    rib = node(nt, "ShaderNodeTexWave", (-900, -900), Scale=420.0); rib.bands_direction = "X"
    L.new(rp.outputs["Vector"], rib.inputs["Vector"])
    band = mth("LESS_THAN", dn.outputs["Fac"], 0.017, (-700, -300))
    knit = mix_f(nt, knit, rib.outputs["Fac"], band, (-100, 0))
    stitch_n = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dn.outputs["Fac"], 0.019, (-700, -380)), None, (-550, -380)), 0.0009, (-400, -380))
    stitch_h = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dh.outputs["Fac"], 0.017, (-700, -480)), None, (-550, -480)), 0.0009, (-400, -480))
    stitch_h2 = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dh.outputs["Fac"], 0.0115, (-700, -560)), None, (-550, -560)), 0.0009, (-400, -560))
    dash = node(nt, "ShaderNodeTexWave", (-900, -1100), Scale=900.0); dash.wave_profile = "SAW"; dash.bands_direction = "DIAGONAL"
    L.new(rp.outputs["Vector"], dash.inputs["Vector"])
    dsh = mth("GREATER_THAN", dash.outputs["Fac"], 0.35, (-700, -1100))
    st = mth("MAXIMUM", mth("MAXIMUM", stitch_n, stitch_h, (-250, -420)), stitch_h2, (-150, -450))
    st = mth("MULTIPLY", st, dsh, (-50, -450))
    seamh = mth("MULTIPLY", sm.outputs["Fac"], -1.5, (-250, -650))
    h = mth("ADD", mth("ADD", knit, mth("MULTIPLY", st, 1.2, (50, -450)), (200, 0)), seamh, (350, 0))
    bump = node(nt, "ShaderNodeBump", (600, -200), Strength=0.35, Distance=0.0004)
    L.new(h, bump.inputs["Height"]); L.new(bump.outputs[0], b.inputs["Normal"])
    return m


def _math(nt, op, a, c, loc, clamp=False):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.location = loc; n.use_clamp = clamp
    for i, src in enumerate((a, c)):
        if src is None:
            continue
        if isinstance(src, (int, float)):
            n.inputs[i].default_value = src
        else:
            nt.links.new(src, n.inputs[i])
    return n.outputs[0]


def mix_f(nt, a, c, f, loc):
    n = nt.nodes.new("ShaderNodeMix"); n.data_type = "FLOAT"; n.location = loc
    for src, sock in ((f, n.inputs[0]), (a, n.inputs[2]), (c, n.inputs[3])):
        if isinstance(src, (int, float)):
            sock.default_value = src
        else:
            nt.links.new(src, sock)
    return n.outputs[0]


def mat_trousers():
    m = bpy.data.materials.new("MAT_Cotton_Twill_Black")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (1200, 0))
    b = node(nt, "ShaderNodeBsdfPrincipled", (900, 0)); L.new(b.outputs[0], out.inputs[0])
    rp = node(nt, "ShaderNodeAttribute", (-1200, 0)); rp.attribute_name = "rest_pos"
    pk = node(nt, "ShaderNodeAttribute", (-1200, -300)); pk.attribute_name = "pocket"
    sm = node(nt, "ShaderNodeAttribute", (-1200, -500)); sm.attribute_name = "seam"
    dh = node(nt, "ShaderNodeAttribute", (-1200, -700)); dh.attribute_name = "d_hem"
    dw = node(nt, "ShaderNodeAttribute", (-1200, -900)); dw.attribute_name = "d_waist"
    tw = node(nt, "ShaderNodeTexWave", (-900, 300), Scale=1100.0, Distortion=0.8, Detail=2.0)
    tw.bands_direction = "DIAGONAL"; tw.wave_profile = "SIN"
    L.new(rp.outputs["Vector"], tw.inputs["Vector"])
    fz = node(nt, "ShaderNodeTexNoise", (-900, 0), Scale=700.0, Detail=6.0)
    L.new(rp.outputs["Vector"], fz.inputs["Vector"])
    cv = node(nt, "ShaderNodeTexNoise", (-900, 600), Scale=9.0, Detail=4.0)
    L.new(rp.outputs["Vector"], cv.inputs["Vector"])
    col = nt.nodes.new("ShaderNodeMix"); col.data_type = "RGBA"; col.location = (300, 300)
    col.inputs[6].default_value = (0.010, 0.010, 0.011, 1); col.inputs[7].default_value = (0.018, 0.017, 0.019, 1)
    L.new(cv.outputs["Fac"], col.inputs[0])
    L.new(col.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.86
    b.inputs["Sheen Weight"].default_value = 0.07
    b.inputs["Sheen Roughness"].default_value = 0.4
    b.inputs["Sheen Tint"].default_value = (0.55, 0.55, 0.6, 1)
    b.inputs["Specular IOR Level"].default_value = 0.12
    mth = lambda op, a, c, loc: _math(nt, op, a, c, loc)
    h = mth("ADD", mth("MULTIPLY", tw.outputs["Fac"], 0.6, (-600, 300)), mth("MULTIPLY", fz.outputs["Fac"], 0.4, (-600, 0)), (-400, 100))
    dash = node(nt, "ShaderNodeTexWave", (-900, -1200), Scale=700.0); dash.wave_profile = "SAW"; dash.bands_direction = "Z"
    L.new(rp.outputs["Vector"], dash.inputs["Vector"])
    dsh = mth("GREATER_THAN", dash.outputs["Fac"], 0.35, (-700, -1200))
    st_hem = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dh.outputs["Fac"], 0.025, (-700, -700)), None, (-550, -700)), 0.0010, (-400, -700))
    st_w = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dw.outputs["Fac"], 0.034, (-700, -900)), None, (-550, -900)), 0.0010, (-400, -900))
    st_w2 = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", dw.outputs["Fac"], 0.003, (-700, -980)), None, (-550, -980)), 0.0010, (-400, -980))
    st = mth("MULTIPLY", mth("MAXIMUM", mth("MAXIMUM", st_hem, st_w, (-250, -800)), st_w2, (-150, -850)), dsh, (-50, -850))
    seam_h = mth("MULTIPLY", sm.outputs["Fac"], -1.2, (-300, -500))
    pocket_h = mth("MULTIPLY", mth("POWER", pk.outputs["Fac"], 3.0, (-600, -300)), -3.0, (-300, -300))
    h = mth("ADD", h, mth("ADD", seam_h, pocket_h, (-100, -400)), (100, 0))
    h = mth("ADD", h, mth("MULTIPLY", st, 1.0, (100, -800)), (250, 0))
    bump = node(nt, "ShaderNodeBump", (600, -200), Strength=0.3, Distance=0.0005)
    L.new(h, bump.inputs["Height"]); L.new(bump.outputs[0], b.inputs["Normal"])
    # darker inside the pocket crease
    dk = mth("MULTIPLY", mth("POWER", pk.outputs["Fac"], 4.0, (0, 500)), 0.7, (150, 500))
    col2 = nt.nodes.new("ShaderNodeMix"); col2.data_type = "RGBA"; col2.location = (600, 300)
    L.new(dk, col2.inputs[0]); L.new(col.outputs[2], col2.inputs[6]); col2.inputs[7].default_value = (0.004, 0.004, 0.005, 1)
    L.new(col2.outputs[2], b.inputs["Base Color"])
    return m


def mat_leather():
    m = bpy.data.materials.new("MAT_Sneaker_Leather_White")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (1200, 0))
    b = node(nt, "ShaderNodeBsdfPrincipled", (900, 0)); L.new(b.outputs[0], out.inputs[0])
    sl = node(nt, "ShaderNodeAttribute", (-1400, 0)); sl.attribute_name = "shoe_loc"
    sep = node(nt, "ShaderNodeSeparateXYZ", (-1200, 0)); L.new(sl.outputs["Vector"], sep.inputs[0])
    u, v, w = sep.outputs
    geo = node(nt, "ShaderNodeNewGeometry", (-1400, 400))
    mth = lambda op, a, c, loc: _math(nt, op, a, c, loc)
    grain = node(nt, "ShaderNodeTexVoronoi", (-900, 400), Scale=900.0); grain.feature = "DISTANCE_TO_EDGE"
    L.new(geo.outputs["Position"], grain.inputs["Vector"])
    crease = node(nt, "ShaderNodeTexNoise", (-900, 150), Scale=180.0, Detail=8.0, Roughness=0.7)
    L.new(geo.outputs["Position"], crease.inputs["Vector"])
    # panel lines: toe cap (u ~ 0.80), side quarter (u ~ 0.45 diagonal), heel counter (u ~ 0.2)
    toe = mth("ABSOLUTE", mth("SUBTRACT", u, mth("ADD", 0.80, mth("MULTIPLY", w, -0.8, (-1000, -300)), (-900, -300)), (-800, -300)), None, (-700, -300))
    quarter = mth("ABSOLUTE", mth("SUBTRACT", u, mth("ADD", 0.40, mth("MULTIPLY", w, 1.6, (-1000, -450)), (-900, -450)), (-800, -450)), None, (-700, -450))
    heelc = mth("ABSOLUTE", mth("SUBTRACT", u, mth("ADD", 0.24, mth("MULTIPLY", w, -1.2, (-1000, -600)), (-900, -600)), (-800, -600)), None, (-700, -600))
    edge = mth("MINIMUM", mth("MINIMUM", toe, quarter, (-550, -400)), heelc, (-450, -450))
    groove = mth("LESS_THAN", edge, 0.004, (-300, -400))
    stitch_line = mth("LESS_THAN", mth("ABSOLUTE", mth("SUBTRACT", edge, 0.011, (-400, -550)), None, (-330, -550)), 0.0018, (-250, -550))
    dash = node(nt, "ShaderNodeTexWave", (-900, -800), Scale=260.0); dash.wave_profile = "SAW"; dash.bands_direction = "Z"
    L.new(geo.outputs["Position"], dash.inputs["Vector"])
    dash2 = node(nt, "ShaderNodeTexWave", (-900, -1000), Scale=260.0); dash2.wave_profile = "SAW"; dash2.bands_direction = "X"
    L.new(geo.outputs["Position"], dash2.inputs["Vector"])
    dd = mth("GREATER_THAN", mth("ADD", dash.outputs["Fac"], dash2.outputs["Fac"], (-700, -900)), 0.9, (-550, -900))
    stitch = mth("MULTIPLY", stitch_line, dd, (-150, -600))
    # perforations on toe cap
    perf = node(nt, "ShaderNodeTexVoronoi", (-900, -1250), Scale=520.0, Randomness=0.0)
    L.new(geo.outputs["Position"], perf.inputs["Vector"])
    holes = mth("MULTIPLY", mth("LESS_THAN", perf.outputs["Distance"], 0.22, (-700, -1250)), mth("GREATER_THAN", u, 0.86, (-700, -1350)), (-550, -1300))
    holes = mth("MULTIPLY", holes, mth("GREATER_THAN", w, 0.035, (-700, -1450)), (-450, -1300))
    h = mth("ADD", mth("MULTIPLY", grain.outputs["Distance"], 0.3, (-600, 400)), mth("MULTIPLY", crease.outputs["Fac"], 0.5, (-600, 150)), (-400, 300))
    h = mth("SUBTRACT", h, mth("MULTIPLY", groove, 1.5, (-150, -400)), (0, 200))
    h = mth("ADD", h, mth("MULTIPLY", stitch, 0.8, (0, -600)), (150, 200))
    h = mth("SUBTRACT", h, mth("MULTIPLY", holes, 2.0, (0, -1300)), (300, 200))
    bump = node(nt, "ShaderNodeBump", (600, -200), Strength=0.35, Distance=0.0006)
    L.new(h, bump.inputs["Height"]); L.new(bump.outputs[0], b.inputs["Normal"])
    # colour: off-white leather, scuffs near toe & sides, grey stitches, dark holes
    sc = node(nt, "ShaderNodeTexNoise", (-900, 800), Scale=60.0, Detail=10.0, Roughness=0.75)
    L.new(geo.outputs["Position"], sc.inputs["Vector"])
    scuff = _mr(nt, sc.outputs["Fac"], 0.62, 0.72, (-600, 800))
    scuff = mth("MULTIPLY", scuff, mth("ADD", mth("MULTIPLY", u, 0.8, (-600, 650)), 0.1, (-450, 650)), (-300, 750))
    c = _mixc(nt, (0.78, 0.77, 0.74, 1), (0.52, 0.48, 0.42, 1), mth("MULTIPLY", scuff, 0.6, (-150, 750)), (0, 700))
    c = _mixc(nt, c, (0.55, 0.55, 0.53, 1), stitch, (200, 600))
    c = _mixc(nt, c, (0.2, 0.2, 0.2, 1), holes, (400, 600))
    L.new(c, b.inputs["Base Color"])
    rough = mth("ADD", 0.42, mth("MULTIPLY", scuff, 0.2, (300, -100)), (450, -100))
    L.new(rough, b.inputs["Roughness"])
    b.inputs["Coat Weight"].default_value = 0.15; b.inputs["Coat Roughness"].default_value = 0.3
    return m


def _mr(nt, x, a, b, loc):
    n = nt.nodes.new("ShaderNodeMapRange"); n.location = loc; n.interpolation_type = "SMOOTHSTEP"
    n.inputs[1].default_value = a; n.inputs[2].default_value = b
    nt.links.new(x, n.inputs[0]); return n.outputs[0]


def _mixc(nt, a, c, f, loc):
    n = nt.nodes.new("ShaderNodeMix"); n.data_type = "RGBA"; n.location = loc
    for src, sock in ((f, n.inputs[0]), (a, n.inputs[6]), (c, n.inputs[7])):
        if isinstance(src, (tuple, float, int)):
            sock.default_value = src
        else:
            nt.links.new(src, sock)
    return n.outputs[2]


def mat_rubber():
    m = bpy.data.materials.new("MAT_Sneaker_Rubber_Sole")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (900, 0))
    b = node(nt, "ShaderNodeBsdfPrincipled", (600, 0)); L.new(b.outputs[0], out.inputs[0])
    geo = node(nt, "ShaderNodeNewGeometry", (-900, 0))
    sep = node(nt, "ShaderNodeSeparateXYZ", (-700, 0)); L.new(geo.outputs["Position"], sep.inputs[0])
    nz = node(nt, "ShaderNodeTexNoise", (-700, 300), Scale=40.0, Detail=8.0)
    L.new(geo.outputs["Position"], nz.inputs["Vector"])
    dirt = _mr(nt, sep.outputs["Z"], SOLE_T * -0.2, SOLE_T * -0.95, (-400, 0))  # dirtier near the ground (rest-space z)
    d2 = _math(nt, "MULTIPLY", dirt, nz.outputs["Fac"], (-200, 100))
    c = _mixc(nt, (0.80, 0.78, 0.73, 1), (0.35, 0.31, 0.26, 1), _math(nt, "MULTIPLY", d2, 0.9, (0, 100)), (200, 100))
    L.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.62
    fine = node(nt, "ShaderNodeTexNoise", (-400, -300), Scale=1500.0, Detail=4.0)
    L.new(geo.outputs["Position"], fine.inputs["Vector"])
    bump = node(nt, "ShaderNodeBump", (300, -300), Strength=0.15, Distance=0.0003)
    L.new(fine.outputs["Fac"], bump.inputs["Height"]); L.new(bump.outputs[0], b.inputs["Normal"])
    return m

M_TEE, M_TRO, M_LEA, M_RUB = mat_tee(), mat_trousers(), mat_leather(), mat_rubber()
M_LACE = bpy.data.materials.new("MAT_Sneaker_Laces")
bl = M_LACE.node_tree.nodes["Principled BSDF"]
bl.inputs["Base Color"].default_value = (0.80, 0.79, 0.76, 1); bl.inputs["Roughness"].default_value = 0.85
bl.inputs["Sheen Weight"].default_value = 0.4
M_EYELET = bpy.data.materials.new("MAT_Sneaker_Eyelets")
be = M_EYELET.node_tree.nodes["Principled BSDF"]
be.inputs["Base Color"].default_value = (0.70, 0.70, 0.68, 1); be.inputs["Roughness"].default_value = 0.4
tee.data.materials.append(M_TEE); tro.data.materials.append(M_TRO)
for up, so, lo, ey, s in shoes:
    up.data.materials.append(M_LEA); so.data.materials.append(M_RUB); lo.data.materials.append(M_LACE); ey.data.materials.append(M_EYELET)
    bpy.context.view_layer.update()
    for o in (up, so, lo, ey):
        mw = o.matrix_world.copy()
        o.parent = rig; o.parent_type = "BONE"; o.parent_bone = "foot." + s.upper()
        bpy.context.view_layer.update(); o.matrix_world = mw

# hide body skin that is fully covered (avoids poke-through, saves render time)
hide = np.zeros(NV)
dk = cKDTree(TV)
hide = np.maximum(hide, tee_mask * (P[:, 2] < neckline - 0.035) * (P[:, 2] > HEM + 0.05) * (~armish | (t_arm < 0.3)))
hide = np.maximum(hide, tro_mask * (P[:, 2] < WAIST - 0.04) * (P[:, 2] > 0.20) * ~handish)
hide = np.maximum(hide, (P[:, 2] < 0.062) * 1.0)
palm = np.zeros(NV)
for nm in [f"finger{i}-{j}.{s}" for i in range(1, 6) for j in (1, 2, 3) for s in "LR"] + [f"metacarpal{i}.{s}" for i in range(1, 5) for s in "LR"]:
    vg = body.vertex_groups.get(nm)
    if vg:
        for v in me.vertices:
            for g in v.groups:
                if g.group == vg.index:
                    palm[v.index] += g.weight
hide = np.maximum(hide, (palm > 0.35) * 1.0)  # hands are inside the pockets
vgroup(body, "hide_under_clothes", hide)
mk = body.modifiers.new("MaskCovered", "MASK"); mk.vertex_group = "hide_under_clothes"; mk.invert_vertex_group = True
# order: Armature -> Mask -> Subdivision
while body.modifiers.find("MaskCovered") > 1:
    with bpy.context.temp_override(object=body):
        bpy.ops.object.modifier_move_up(modifier="MaskCovered")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "clothes.blend"))
print("OK clothes")
