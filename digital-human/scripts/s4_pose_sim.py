"""Step 4: relaxed contrapposto pose (hands in pockets) + cloth simulation of T-shirt and trousers.
Frame 1 = A-pose rest, frame 30 = final pose, cloth simulated 1..60 and frozen at 60.
Reads work/clothes.blend -> work/posed.blend
"""
import sys, os, math
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix, Quaternion
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SIM = os.environ.get("DH_NOSIM") is None
bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "clothes.blend"))
sc = bpy.context.scene
LM = load_json("landmarks.json")
rig = bpy.data.objects["RIG_Teen"]; body = bpy.data.objects["GEO_Body"]
tee = bpy.data.objects["GEO_Tshirt"]; tro = bpy.data.objects["GEO_Trousers"]
SOLE_T = 0.024
F_REST, F_POSE, F_END = -20, 0, 40
sc.frame_start, sc.frame_end = 1, F_END
rig.location.z = SOLE_T
pbs = rig.pose.bones
for pb in pbs:
    pb.rotation_mode = "QUATERNION"
upd = bpy.context.view_layer.update
upd()


def rot_world(name, axis, deg, pivot=None):
    pb = pbs[name]
    M = pb.matrix.copy()
    pv = Vector(pivot) if pivot is not None else M.to_translation()
    R = Matrix.Translation(pv) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-pv)
    pb.matrix = R @ M
    upd()


def move_world(name, d):
    pb = pbs[name]
    pb.matrix = Matrix.Translation(Vector(d)) @ pb.matrix
    upd()

# ---------------------------------------------------------------- torso: weight on the character's RIGHT leg
PELVIS = Vector(LM["joint-pelvis"])
move_world("root", (-0.024, 0.004, -0.006))
rot_world("root", "Y", 5.0, PELVIS)       # left hip drops
rot_world("root", "Z", -6.0, PELVIS)      # left hip swings forward
rot_world("spine05", "Y", -3.0); rot_world("spine04", "Y", -2.0)
rot_world("spine03", "Y", -2.0); rot_world("spine03", "Z", 3.0)
rot_world("spine02", "Y", -1.5); rot_world("spine02", "Z", 2.5); rot_world("spine02", "X", 2.0)
rot_world("spine01", "Z", 2.0); rot_world("spine01", "X", -2.0)
for s, sg in (("L", 1), ("R", -1)):
    rot_world(f"clavicle.{s}", "Y", sg * 3.0)  # shoulders relaxed down
rot_world("neck01", "X", 4.0); rot_world("neck02", "Y", 2.0)
rot_world("head", "Y", 4.0); rot_world("head", "X", -4.0); rot_world("head", "Z", 2.0)
ROOT_DELTA = pbs["root"].matrix @ rig.data.bones["root"].matrix_local.inverted()

# ---------------------------------------------------------------- IK helper (solve, then bake to FK)
def empty(name, loc):
    e = bpy.data.objects.new(name, None); e.location = loc; sc.collection.objects.link(e); return e


def solve_ik(tip_bone, chain, target, pole, pole_angle=-90):
    t = empty("TGT_" + tip_bone, target)
    p = empty("POLE_" + tip_bone, pole)
    upd()
    c = pbs[tip_bone].constraints.new("IK")
    c.target = t; c.pole_target = p; c.chain_count = chain; c.pole_angle = math.radians(pole_angle)
    c.iterations = 500
    upd()
    names = []
    b = pbs[tip_bone]
    for _ in range(chain):
        names.append(b.name); b = b.parent
    names = names[::-1]
    mats = {n: pbs[n].matrix.copy() for n in names}
    pbs[tip_bone].constraints.remove(c)
    upd()
    for n in names:
        pbs[n].matrix = mats[n]; upd()
    bpy.data.objects.remove(t); bpy.data.objects.remove(p)


def world_target(rest_pt):
    return Vector(rest_pt)  # armature space == world (rig at origin, lifted only)

# legs ---------------------------------------------------------
AL = Vector(LM["joint-l-ankle"]); AR = Vector(LM["joint-r-ankle"])
solve_ik("lowerleg02.R", 4, Vector((-0.112, -0.006, 0.071)), Vector((-0.13, -1.0, 0.5)), pole_angle=-90)
solve_ik("lowerleg02.L", 4, Vector((0.098, -0.092, 0.071)), Vector((0.10, -1.0, 0.55)), pole_angle=-90)


def set_bone_world_rot(name, R):
    pb = pbs[name]
    rest = rig.data.bones[name].matrix_local
    head = pb.matrix.to_translation()
    M = R.to_4x4() @ rest
    M.translation = head
    pb.matrix = M; upd()

set_bone_world_rot("foot.R", Matrix.Rotation(math.radians(-7), 3, "Z"))
set_bone_world_rot("foot.L", Matrix.Rotation(math.radians(16), 3, "Z"))


def sole_min(side):
    o = bpy.data.objects[f"GEO_Sneaker_Sole_{side}"]
    return min((o.matrix_world @ v.co).z for v in o.data.vertices)

# plant both soles exactly on the floor (iterate IK target height)
LEG = {"R": [Vector((-0.112, -0.006, 0.071)), Vector((-0.13, -1.0, 0.5)), -7],
       "L": [Vector((0.098, -0.092, 0.071)), Vector((0.10, -1.0, 0.55)), 16]}
for it in range(4):
    for sd in ("R", "L"):
        z = sole_min(sd)
        if abs(z) > 0.0015:
            LEG[sd][0].z -= z
            solve_ik(f"lowerleg02.{sd}", 4, LEG[sd][0], LEG[sd][1], pole_angle=-90)
            set_bone_world_rot(f"foot.{sd}", Matrix.Rotation(math.radians(LEG[sd][2]), 3, "Z"))
print("sole min after fit", sole_min("L"), sole_min("R"))
print("knee check R", pbs["lowerleg01.R"].head, "L", pbs["lowerleg01.L"].head)

# arms: wrists at the front pocket openings ---------------------
targets = {}
for s, sx in (("L", 1), ("R", -1)):
    wrist_rest = Vector((sx * 0.142, -0.100, 0.905))
    tip_rest = Vector((sx * 0.135, -0.088, 0.80))
    w = ROOT_DELTA @ wrist_rest; tp = ROOT_DELTA @ tip_rest
    targets[s] = (w, tp)
    solve_ik(f"lowerarm02.{s}", 4, w, Vector((sx * 0.55, 0.30, 1.10)), pole_angle=(-90 if s == "L" else -90))
    # hand: point fingers down into the pocket
    pb = pbs[f"wrist.{s}"]
    cur = (pb.tail - pb.head).normalized()
    want = (tp - pb.head).normalized()
    q = cur.rotation_difference(want)
    head = pb.head.copy()
    M = q.to_matrix().to_4x4() @ pb.matrix
    M.translation = head
    pb.matrix = M; upd()
    # twist so the thumb points forward (palm against the thigh)
    best = None
    for ang in range(-180, 180, 10):
        Mt = Matrix.Translation(head) @ Matrix.Rotation(math.radians(ang), 4, want) @ Matrix.Translation(-head) @ M
        pb.matrix = Mt; upd()
        th = pbs[f"finger1-3.{s}"].tail
        score = -th.y - 0.3 * abs(th.x - head.x)
        if best is None or score > best[0]:
            best = (score, ang, Mt.copy())
    pb.matrix = best[2]; upd()
    print("wrist", s, "twist", best[1])
    # relaxed finger curl toward the thigh
    leg_c = (pbs[f"upperleg02.{s}"].head + pbs[f"upperleg02.{s}"].tail) / 2
    for f in range(1, 6):
        for j in (1, 2, 3):
            n = f"finger{f}-{j}.{s}"
            if n not in pbs:
                continue
            amt = 12 if f == 1 else 22
            bb = pbs[n]
            base = bb.rotation_quaternion.copy()
            res = []
            for sg in (1, -1):
                bb.rotation_quaternion = base @ Quaternion((1, 0, 0), math.radians(sg * amt)); upd()
                res.append(((pbs[f"finger{f}-3.{s}"].tail - leg_c).length, sg))
            sg = min(res)[1]
            bb.rotation_quaternion = base @ Quaternion((1, 0, 0), math.radians(sg * amt)); upd()

# ---------------------------------------------------------------- keyframes: rest (1) -> pose (F_POSE)
pose = {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy()) for pb in pbs}
rig.animation_data_create()
act = bpy.data.actions.new("AN_Teen_RestToPockets"); rig.animation_data.action = act
for pb in pbs:
    pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0)
    pb.keyframe_insert("location", frame=F_REST); pb.keyframe_insert("rotation_quaternion", frame=F_REST)
    pb.location, pb.rotation_quaternion = pose[pb.name]
    pb.keyframe_insert("location", frame=F_POSE); pb.keyframe_insert("rotation_quaternion", frame=F_POSE)
sc.frame_set(F_POSE)

# ---------------------------------------------------------------- collision proxies
C_SIM = coll("SIM_HELPERS")
def body_proxy(name, drop_groups, thick_out):
    m = body.data.copy(); o = bpy.data.objects.new(name, m); C_SIM.objects.link(o)
    o.parent = rig
    for md in list(o.modifiers):
        o.modifiers.remove(md)
    for vg in body.vertex_groups:
        o.vertex_groups.new(name=vg.name)
    # copy weights
    for v in body.data.vertices:
        for g in v.groups:
            o.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    bm = bmesh.new(); bm.from_mesh(m)
    dl = bm.verts.layers.deform.active
    kill = []
    for v in bm.verts:
        w = sum(v[dl].get(body.vertex_groups[gn].index, 0.0) for gn in drop_groups if gn in body.vertex_groups)
        if w > 0.25 or v.co.z > 1.56:
            kill.append(v)
    bmesh.ops.delete(bm, geom=kill, context="VERTS"); bm.to_mesh(m); bm.free()
    a = o.modifiers.new("Armature", "ARMATURE"); a.object = rig
    c = o.modifiers.new("Collision", "COLLISION")
    o.collision.thickness_outer = thick_out; o.collision.thickness_inner = 0.002; o.collision.cloth_friction = 8
    o.hide_render = True
    return o

hand_g = [f"finger{i}-{j}.{s}" for i in range(1, 6) for j in (1, 2, 3) for s in "LR"] + [f"metacarpal{i}.{s}" for i in range(1, 5) for s in "LR"] + ["wrist.L", "wrist.R"]
fore_g = hand_g + ["lowerarm01.L", "lowerarm01.R", "lowerarm02.L", "lowerarm02.R"]
C_TEE = coll("SIM_COLLIDE_TEE", C_SIM); C_TRO = coll("SIM_COLLIDE_TROUSERS", C_SIM)
pa = body_proxy("SIM_Proxy_Tee", hand_g, 0.004); link(pa, C_TEE)
pb_ = body_proxy("SIM_Proxy_Trousers", fore_g, 0.003); link(pb_, C_TRO)
for o in bpy.data.objects:
    if o.name.startswith("GEO_Sneaker_Upper") or o.name.startswith("GEO_Sneaker_Sole"):
        o.modifiers.new("Collision", "COLLISION"); o.collision.thickness_outer = 0.003
        C_TRO.objects.link(o)

# growing hand colliders (pocket bulge): posed hand mesh, scaled up from inside the thigh
upd()
deps = bpy.context.evaluated_depsgraph_get()
sc.frame_set(F_POSE)
ev = body.evaluated_get(deps)
for md in body.modifiers:
    if md.type in ("SUBSURF", "MASK"):
        md.show_viewport = False
upd(); deps = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(deps)
emesh = ev.to_mesh()
Wh = {s: np.zeros(len(body.data.vertices)) for s in "LR"}
for v in body.data.vertices:
    for g in v.groups:
        gn = body.vertex_groups[g.group].name
        if gn in hand_g:
            Wh[gn[-1]][v.index] += g.weight
EP = np.array([(rig.matrix_world @ v.co)[:] for v in emesh.vertices])
for md in body.modifiers:
    md.show_viewport = True
for s, sx in (("L", 1), ("R", -1)):
    idx = np.where(Wh[s] > 0.5)[0]
    pts = EP[idx]
    cen = pts.mean(0)
    leg = np.array((pbs[f"upperleg02.{s}"].head + pbs[f"upperleg02.{s}"].tail) / 2) + np.array([0, 0, SOLE_T])
    inside = cen + (leg - cen) * 0.55
    m = bpy.data.meshes.new(f"SIM_HandBulge_{s}")
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p - inside)
    bm.verts.ensure_lookup_table()
    hull = bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(m); bm.free()
    o = bpy.data.objects.new(m.name, m); C_TRO.objects.link(o)
    o.location = inside
    o.modifiers.new("Collision", "COLLISION"); o.collision.thickness_outer = 0.004
    o.hide_render = True
    o.scale = (0.1, 0.1, 0.1); o.keyframe_insert("scale", frame=3)
    o.scale = (1.05, 1.05, 1.05); o.keyframe_insert("scale", frame=16)

# ---------------------------------------------------------------- cloth
def cloth(o, coll_, mass, tens, shear, bend, qual=7):
    md = o.modifiers.new("Cloth", "CLOTH")
    s = md.settings
    s.quality = qual; s.mass = mass
    s.tension_stiffness = tens; s.compression_stiffness = tens; s.shear_stiffness = shear; s.bending_stiffness = bend
    s.tension_damping = 5; s.compression_damping = 5; s.shear_damping = 5; s.air_damping = 1.0
    s.vertex_group_mass = "pin"; s.pin_stiffness = 1.0
    if o.vertex_groups.get("grow"):
        s.vertex_group_shrink = "grow"; s.shrink_min = 0.0; s.shrink_max = -0.13
    c = md.collision_settings
    c.collision_quality = 5; c.distance_min = 0.0025; c.collection = coll_
    c.use_self_collision = False
    md.point_cache.frame_start = 1; md.point_cache.frame_end = F_END
    return md

TRV = np.array([v.co[:] for v in tro.data.vertices])
gvg = tro.vertex_groups.new(name="grow")
for i, p in enumerate(TRV):
    w = float(np.clip((0.40 - p[2]) / 0.25, 0, 1))
    if w > 0:
        gvg.add([i], w, "REPLACE")
def run_and_freeze(o):
    import time
    t0 = time.time()
    for f in range(0, F_END + 1):
        sc.frame_set(f)
        if f % 10 == 0:
            print("sim", o.name, "frame", f, "%.0fs" % (time.time() - t0), flush=True)
    deps = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(deps)
    nm = bpy.data.meshes.new_from_object(e, preserve_all_data_layers=True, depsgraph=deps)
    o.modifiers["Cloth"].show_viewport = False; upd()
    deps2 = bpy.context.evaluated_depsgraph_get()
    sk = np.array([v.co[:] for v in o.evaluated_get(deps2).to_mesh().vertices])
    o.evaluated_get(deps2).to_mesh_clear()
    rest = np.array([v.co[:] for v in o.data.vertices])
    bm = bmesh.new(); bm.from_mesh(nm); bm.verts.ensure_lookup_table()
    sim = np.array([v.co[:] for v in bm.verts])
    bad = np.zeros(len(sim), bool)
    for ed in bm.edges:
        a_, b_ = ed.verts[0].index, ed.verts[1].index
        lr = np.linalg.norm(rest[a_] - rest[b_]) + 1e-6
        if np.linalg.norm(sim[a_] - sim[b_]) > 1.6 * lr or np.linalg.norm(sk[a_] - sk[b_]) > 1.6 * lr:
            bad[a_] = bad[b_] = True
    bad |= np.linalg.norm(sim - sk, axis=1) > 0.05
    for _ in range(3):
        nb = bad.copy()
        for ed in bm.edges:
            a_, b_ = ed.verts[0].index, ed.verts[1].index
            if bad[a_] or bad[b_]:
                nb[a_] = nb[b_] = True
        bad = nb
    print(o.name, "repaired verts", int(bad.sum()), flush=True)
    for i in np.where(bad)[0]:
        bm.verts[i].co = Vector(sk[i])
    badi = np.where(bad)[0]
    nbrs = {i: [e.other_vert(bm.verts[i]).index for e in bm.verts[i].link_edges] for i in badi}
    pos = np.array([v.co[:] for v in bm.verts])
    for _ in range(60):  # harmonic fill of the damaged patch from its good surroundings (boundaries included)
        newp = pos.copy()
        for i in badi:
            newp[i] = pos[nbrs[i]].mean(0) if nbrs[i] else pos[i]
        pos = newp
    for i in badi:
        bm.verts[i].co = Vector(pos[i])
    bm.to_mesh(nm); bm.free()
    old = o.data
    o.modifiers.clear()
    o.data = nm
    bpy.data.meshes.remove(old)

if SIM:
    cloth(tro, C_TRO, 0.28, 18, 8, 0.8)
    run_and_freeze(tro)
    # frozen trousers become a collider for the T-shirt hem
    tro_col = bpy.data.objects.new("SIM_TrousersCollider", tro.data.copy()); C_TEE.objects.link(tro_col)
    tro_col.parent = rig; tro_col.matrix_world = tro.matrix_world.copy()
    tro_col.modifiers.new("Collision", "COLLISION"); tro_col.collision.thickness_outer = 0.004
    tro_col.hide_render = True
    sc.frame_set(0)
    cloth(tee, C_TEE, 0.14, 7, 3, 0.05)
    run_and_freeze(tee)

# thickness + smoothing on garments
for o, th in ((tee, 0.0016), (tro, 0.0020)):
    so = o.modifiers.new("Solidify", "SOLIDIFY"); so.thickness = th; so.offset = 1.0; so.use_even_offset = False; so.thickness_clamp = 0.5; so.use_quality_normals = True
    sb = o.modifiers.new("Subdivision", "SUBSURF"); sb.levels = 1; sb.render_levels = 2
# hide helpers
for o in C_SIM.all_objects:
    if o.name.startswith("SIM_"):
        o.hide_render = True; o.hide_viewport = True
sc.frame_set(F_END)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "posed.blend"))
print("OK posed")
