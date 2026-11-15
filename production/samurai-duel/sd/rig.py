"""Skeletons for the fighters.

The armature uses Mixamo's bone names and hierarchy (65 bones with fingers), so clips downloaded
from Mixamo on its stock character can be carried over bone by bone (sd/retarget.py). It is built
here rather than by Mixamo's auto-rigger because the joints can be read off our own models:

  joints    measured on the watertight skin by slicing it: arm and leg centre lines, wrists,
            knees, ankles; finger chains measured on the detailed hand
  weights   Blender's bone-heat solve on the watertight skin (it needs a clean closed mesh),
            carried over to the detailed body by nearest-point lookup; fingers are skinned
            directly on the detailed hand by distance to each finger bone

Left is the wearer's left, the +X side: the fighters face -Y.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from scipy.spatial import cKDTree

from . import core

P = "mixamorig:"
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")

# Per fighter: where along each limb the joints sit (metres, rest pose). Centre lines are measured;
# these numbers only say at which height or reach to measure them.
SPEC = dict(
    ronin=dict(
        hips=(-0.02, 1.00), up_leg=(0.105, -0.02, 0.93), knee_z=0.52, ankle_z=0.105, ankle_back=0.02,
        toe=(-0.085, 0.035), toe_end=(-0.158, 0.03),
        spine=((-0.02, 1.10), (-0.01, 1.22), (0.0, 1.36)), neck=(0.02, 1.59), head=(0.01, 1.69), head_top=1.865,
        clavicle=(0.06, 0.02, 1.55), shoulder_x=0.195, elbow_x=0.475, wrist_x=0.71,
    ),
    oni=dict(
        hips=(-0.03, 1.08), up_leg=(0.115, -0.03, 1.00), knee_z=0.56, ankle_z=0.125, ankle_back=0.02,
        toe=(-0.075, 0.04), toe_end=(-0.142, 0.03),
        spine=((-0.035, 1.18), (-0.03, 1.31), (-0.01, 1.45)), neck=(0.02, 1.66), head=(0.01, 1.77), head_top=1.95,
        clavicle=(0.07, 0.02, 1.62), shoulder_x=0.225, elbow_x=0.465, wrist_x=0.76,
    ),
)


# ----------------------------------------------------------------------------- measuring
def _tris(me):
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64), t.reshape(-1, 3)


def _section(co, tri, axis, value):
    """Points where triangle edges cross the plane (axis = value)."""
    Q = co[tri]
    d = Q[:, :, axis] - value
    pts = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        m = (d[:, a] * d[:, b]) < 0
        t = d[m, a] / (d[m, a] - d[m, b])
        pts.append(Q[m, a] + (Q[m, b] - Q[m, a]) * t[:, None])
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def _mid(v):
    return 0.5 * (float(v.min()) + float(v.max()))


def _hand(co, side, wrist, elbow):
    """Finger joints of one hand, measured on the detailed mesh. Returns {finger: [4 points]} and the hand frame.

    The hand is described in its own frame: u along the hand (wrist to fingertips), v across it
    from the thumb side to the little finger, w out of the back of the hand."""
    W, E = np.array(wrist), np.array(elbow)
    f = (W - E) / np.linalg.norm(W - E)
    near = co[(np.linalg.norm(co - W, axis=1) < 0.34) & ((co - W) @ f > -0.01)]
    reach = (near - W) @ f
    tip_c = near[reach > np.percentile(reach, 97)].mean(axis=0)
    a = (tip_c - W) / np.linalg.norm(tip_c - W)
    n = np.array([0.0, 0.0, 1.0]) - a * a[2]
    n /= np.linalg.norm(n)
    lat = side * np.cross(n, a)                                  # toward the little finger on either hand
    u, v, w = (near - W) @ a, (near - W) @ lat, (near - W) @ n
    Lh = float(np.percentile(u, 99.8))

    # the four fingers: the widest unbroken run across the hand at 72 % of its length (the thumb does not reach that far)
    band = np.sort(v[np.abs(u - 0.72 * Lh) < 0.004])
    gaps = np.flatnonzero(np.diff(band) > 0.012)
    runs = np.split(band, gaps + 1)
    run = max(runs, key=lambda r: r[-1] - r[0])
    v0, v1 = float(run[0]), float(run[-1])
    bw = (v1 - v0) / 4.0
    vc = 0.5 * (v0 + v1)

    def follow(u_from, v_from):
        """Walk out along one finger from its knuckle, re-centring on the finger at every step,
        so that fingers which fan out or lean together are still followed to their own tips."""
        path, vv, ww = [], v_from, None
        for uu in np.arange(u_from, Lh * 1.03, 0.004):
            m = (np.abs(u - uu) < 0.004) & (np.abs(v - vv) < 0.55 * bw)
            if m.sum() < 5:
                break
            vs = np.sort(v[m])
            runs_ = np.split(vs, np.flatnonzero(np.diff(vs) > 0.0025) + 1)       # separate fingers that share the window
            r = min(runs_, key=lambda q: abs(0.5 * (q[0] + q[-1]) - vv))
            if r[-1] - r[0] < 1.25 * bw:                                         # a single finger, not two touching ones
                vv = float(np.clip(0.5 * (r[0] + r[-1]), vv - 0.0015, vv + 0.0015))
            mm = m & (v >= r[0] - 1e-6) & (v <= r[-1] + 1e-6)
            ww = _mid(w[mm]) if mm.any() else ww
            path.append((uu, vv, ww if ww is not None else 0.0))
        return np.array(path)

    out = {}
    knuckle = dict(Index=0.53, Middle=0.52, Ring=0.50, Pinky=0.47)
    for k, name in enumerate(("Index", "Middle", "Ring", "Pinky")):
        vi = v0 + (k + 0.5) * bw
        path = follow(knuckle[name] * Lh, vc + (vi - vc) * 0.9)
        if len(path) < 4:                                                        # should not happen: fall back to a straight finger
            path = np.array([(knuckle[name] * Lh + t * 0.35 * Lh, vi, 0.0) for t in (0, 0.5, 1.0, 1.0)])
        length = path[-1, 0] - path[0, 0]
        pts = []
        for t in (0.0, 0.48, 0.78, 1.0):
            uu = path[0, 0] + length * t - (0.003 if t == 1.0 else 0.0)
            vv = float(np.interp(uu, path[:, 0], path[:, 1]))
            ww = float(np.interp(uu, path[:, 0], path[:, 2]))
            pts.append(W + a * uu + lat * vv + n * ww)
        out[name] = pts
    # thumb: the part of the hand that sticks out on the thumb side, short of the knuckles
    th = (v < v0 - 0.1 * bw) & (u > 0.08 * Lh) & (u < 0.85 * Lh)
    d_th = -lat * 0.8 + a * 0.6
    d_th /= np.linalg.norm(d_th)
    if th.sum() > 20:
        far = (near[th] - W) @ d_th
        tip = near[th][far > np.percentile(far, 97)].mean(axis=0)
    else:
        tip = W + a * 0.5 * Lh + lat * (v0 - 1.2 * bw)
    wmid = _mid(w[(u > 0.1 * Lh) & (u < 0.25 * Lh)])
    base = W + a * 0.14 * Lh + lat * (v0 + 0.55 * bw) + n * (wmid - 0.004)
    out["Thumb"] = [base + (tip - base) * t for t in (0.0, 0.42, 0.74, 1.0)]
    return out, dict(a=a, lat=lat, n=n, W=W, Lh=Lh, v0=v0, v1=v1, bw=bw)


def joints(who, proxy_me, body_me, verbose=True):
    """Joint positions (metres, rest pose) keyed by Mixamo bone name without the prefix."""
    S = SPEC[who]
    co, tri = _tris(proxy_me)
    nb = len(body_me.vertices)
    bco = np.empty(nb * 3, dtype=np.float32)
    body_me.vertices.foreach_get("co", bco)
    bco = bco.reshape(-1, 3).astype(np.float64)
    J, hands = {}, {}
    J["Hips"] = (0.0, S["hips"][0], S["hips"][1])
    for nm, (y, z) in zip(("Spine", "Spine1", "Spine2"), S["spine"]):
        J[nm] = (0.0, y, z)
    J["Neck"] = (0.0, *S["neck"])
    J["Head"] = (0.0, *S["head"])
    J["HeadTop_End"] = (0.0, S["head"][0], S["head_top"])
    for side, tag in ((1, "Left"), (-1, "Right")):
        def arm_at(x):
            s = _section(co, tri, 0, side * x)
            s = s[s[:, 2] > S["clavicle"][2] - 0.17]              # the arm, not the flank below it
            return (side * x, _mid(s[:, 1]), _mid(s[:, 2]))

        def leg_at(z):
            s = _section(co, tri, 2, z)
            s = s[s[:, 0] * side > 0.02]
            return (_mid(s[:, 0]), _mid(s[:, 1]), z)

        cx, cy, cz = S["clavicle"]
        J[tag + "Shoulder"] = (side * cx, cy, cz)
        J[tag + "Arm"] = arm_at(S["shoulder_x"] + 0.06)
        J[tag + "Arm"] = (side * S["shoulder_x"], J[tag + "Arm"][1], J[tag + "Arm"][2])       # centre line taken just outside the torso
        J[tag + "ForeArm"] = arm_at(S["elbow_x"])
        J[tag + "Hand"] = arm_at(S["wrist_x"])
        fingers, frame = _hand(bco, side, J[tag + "Hand"], J[tag + "ForeArm"])
        hands[tag] = frame
        for fn, pts in fingers.items():
            for k, p in enumerate(pts):
                J[f"{tag}Hand{fn}{k + 1}"] = tuple(float(c) for c in p)
        ux, uy, uz = S["up_leg"]
        J[tag + "UpLeg"] = (side * ux, uy, uz)
        J[tag + "Leg"] = leg_at(S["knee_z"])
        ax, ay, az = leg_at(S["ankle_z"])
        J[tag + "Foot"] = (ax, ay + S["ankle_back"], az)
        J[tag + "ToeBase"] = (ax + side * 0.012, S["toe"][0], S["toe"][1])
        J[tag + "Toe_End"] = (ax + side * 0.02, S["toe_end"][0], S["toe_end"][1])
    if verbose:
        for k in ("LeftArm", "LeftForeArm", "LeftHand", "LeftHandMiddle1", "LeftHandMiddle4", "LeftHandThumb1", "LeftHandThumb4",
                  "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightFoot"):
            print(f"    {k:16s} {np.round(J[k], 3)}")
        print(f"    hand length L {hands['Left']['Lh']:.3f} R {hands['Right']['Lh']:.3f}; finger band L {hands['Left']['bw']:.4f} R {hands['Right']['bw']:.4f}")
    return J, hands


# ----------------------------------------------------------------------------- armature
def _chain():
    """(bone, parent, tail joint or None, deform) for the whole Mixamo skeleton."""
    B = [("Hips", None, "Spine", True), ("Spine", "Hips", "Spine1", True), ("Spine1", "Spine", "Spine2", True),
         ("Spine2", "Spine1", "Neck", True), ("Neck", "Spine2", "Head", True), ("Head", "Neck", "HeadTop_End", True),
         ("HeadTop_End", "Head", None, False)]
    for s in ("Left", "Right"):
        B += [(s + "Shoulder", "Spine2", s + "Arm", True), (s + "Arm", s + "Shoulder", s + "ForeArm", True),
              (s + "ForeArm", s + "Arm", s + "Hand", True), (s + "Hand", s + "ForeArm", s + "HandMiddle1", True)]
        for f in FINGERS:
            for k in (1, 2, 3):
                B.append((f"{s}Hand{f}{k}", f"{s}Hand{f}{k - 1}" if k > 1 else s + "Hand", f"{s}Hand{f}{k + 1}", True))
            B.append((f"{s}Hand{f}4", f"{s}Hand{f}3", None, False))
        B += [(s + "UpLeg", "Hips", s + "Leg", True), (s + "Leg", s + "UpLeg", s + "Foot", True),
              (s + "Foot", s + "Leg", s + "ToeBase", True), (s + "ToeBase", s + "Foot", s + "Toe_End", True),
              (s + "Toe_End", s + "ToeBase", None, False)]
    return B


def armature(name, J, col):
    """Armature object with Mixamo bone names; rest pose = the model's own T-pose."""
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    col.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    made = {}
    for bone, parent, tail, deform in _chain():
        b = eb.new(P + bone)
        b.head = Vector(J[bone])
        if tail:
            b.tail = Vector(J[tail])
        else:                                       # end bones: a short stub continuing the parent
            pb = made[parent]
            b.tail = b.head + (pb.tail - pb.head).normalized() * 0.03
        if (b.tail - b.head).length < 1e-4:
            b.tail = b.head + Vector((0, 0, 0.02))
        b.use_deform = deform
        if parent:
            b.parent = made[parent]
            b.use_connect = False
        made[bone] = b
    bpy.ops.armature.select_all(action="SELECT")
    bpy.ops.armature.calculate_roll(type="GLOBAL_POS_Z")
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)
    arm.display_type = "STICK"
    return ob


# ----------------------------------------------------------------------------- skinning
def _is_finger(name):
    return "Hand" in name and any(f in name for f in FINGERS)


def skin_proxy(arm, proxy):
    """Bone-heat weights on the watertight skin. Finger bones sit out: the skin's fingers are fused."""
    fingers = [b for b in arm.data.bones if _is_finger(b.name) and b.use_deform]
    for b in fingers:
        b.use_deform = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    proxy.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for b in fingers:
        b.use_deform = True
    proxy.select_set(False)
    arm.select_set(False)
    names = [b.name for b in arm.data.bones if b.use_deform and not _is_finger(b.name)]
    nv = len(proxy.data.vertices)
    W = np.zeros((nv, len(names)), dtype=np.float32)
    idx = {proxy.vertex_groups[n].index: k for k, n in enumerate(names) if n in proxy.vertex_groups}
    for v in proxy.data.vertices:
        for g in v.groups:
            k = idx.get(g.group)
            if k is not None:
                W[v.index, k] = g.weight
    unweighted = int((W.sum(axis=1) < 1e-4).sum())
    return names, W, unweighted


def _seg_dist(Pp, a, b):
    """Distance from points Pp to segment ab, and the parameter along it."""
    ab = b - a
    t = np.clip(((Pp - a) @ ab) / max(1e-12, float(ab @ ab)), 0.0, 1.0)
    return np.linalg.norm(Pp - (a + t[:, None] * ab), axis=1), t


def skin_body(arm, body, proxy, names, Wp, J, hands, verbose=True):
    """Carry the weights over to the detailed mesh and skin the fingers on it directly."""
    nv = len(body.data.vertices)
    co = np.empty(nv * 3, dtype=np.float32)
    body.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    pco = np.empty(len(proxy.data.vertices) * 3, dtype=np.float32)
    proxy.data.vertices.foreach_get("co", pco)
    d, i = cKDTree(pco.reshape(-1, 3)).query(co, k=4, workers=-1)
    w = 1.0 / np.maximum(d, 1e-5) ** 2
    w /= w.sum(axis=1, keepdims=True)
    W = np.einsum("vk,vkb->vb", w.astype(np.float32), Wp[i])
    W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-8)
    cols = {n: k for k, n in enumerate(names)}
    extra_names, extra = [], []
    for tag in ("Left", "Right"):
        H = hands[tag]
        hk = cols[P + tag + "Hand"]
        sel = np.flatnonzero((W[:, hk] > 0.02) & (((co - H["W"]) @ H["a"]) > 0.25 * H["Lh"]))
        if len(sel) == 0:
            continue
        Q = co[sel]
        bones = [(f"{tag}Hand{f}{k}", np.array(J[f"{tag}Hand{f}{k}"]), np.array(J[f"{tag}Hand{f}{k + 1}"])) for f in FINGERS for k in (1, 2, 3)]
        palm_a, palm_b = np.array(J[tag + "Hand"]), np.array(J[tag + "HandMiddle1"])
        dist = np.stack([_seg_dist(Q, palm_a, palm_b)[0]] + [_seg_dist(Q, a_, b_)[0] for _, a_, b_ in bones], axis=1)
        share = 1.0 / np.maximum(dist, 1e-4) ** 8
        # the palm keeps the knuckle area: a finger takes over only past its own first joint
        for c, (bn, a_, b_) in enumerate(bones):
            if bn.endswith("1") and "Thumb" not in bn:
                along = (Q - a_) @ ((b_ - a_) / np.linalg.norm(b_ - a_))
                ramp = np.clip((along + 0.012) / 0.018, 0.0, 1.0)
                fam = slice(c + 1, c + 4)
                share[:, fam] *= (ramp * ramp * (3 - 2 * ramp))[:, None]
        share /= share.sum(axis=1, keepdims=True)
        h = W[sel, hk].copy()
        W[sel, hk] = h * share[:, 0]
        for c, (bn, _, _) in enumerate(bones):
            col = np.zeros(nv, dtype=np.float32)
            col[sel] = h * share[:, c + 1]
            extra_names.append(P + bn)
            extra.append(col)
    all_names = list(names) + extra_names
    Wall = np.concatenate([W] + [e[:, None] for e in extra], axis=1) if extra else W
    # keep the four strongest bones per vertex
    if Wall.shape[1] > 4:
        order = np.argsort(-Wall, axis=1)[:, :4]
        top = np.take_along_axis(Wall, order, axis=1)
        top /= np.maximum(top.sum(axis=1, keepdims=True), 1e-8)
    else:
        order = np.tile(np.arange(Wall.shape[1]), (nv, 1))
        top = Wall
    for g in list(body.vertex_groups):
        body.vertex_groups.remove(g)
    gi = [body.vertex_groups.new(name=n).index for n in all_names]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    dl = bm.verts.layers.deform.verify()
    gi = np.array(gi)
    for vert, o_, t_ in zip(bm.verts, order, top):
        dv = vert[dl]
        for k in range(len(o_)):
            if t_[k] > 0.004:
                dv[int(gi[o_[k]])] = float(t_[k])
    bm.to_mesh(body.data)
    bm.free()
    m = body.modifiers.new("Armature", "ARMATURE")
    m.object = arm
    body.parent = arm
    if verbose:
        print(f"    body skinned: {nv} verts, {len(all_names)} bones, mean distance to the skin {d[:, 0].mean() * 1000:.1f} mm")
    return all_names


def pose(arm, rotations):
    """Set pose-bone rotations from {bone name without prefix: (x, y, z) degrees about WORLD axes},
    each applied on top of whatever the bone inherits from its parent. Turning about world axes
    keeps test poses readable whatever each bone's roll is."""
    order = sorted(rotations, key=lambda n: len(arm.pose.bones[P + n].parent_recursive))
    for name in order:
        bpy.context.view_layer.update()
        pb = arm.pose.bones[P + name]
        pb.rotation_mode = "QUATERNION"
        rest = pb.bone.matrix_local.to_3x3()                      # rest orientation in armature space
        if pb.parent:
            carried = pb.parent.matrix.to_3x3() @ pb.parent.bone.matrix_local.to_3x3().inverted() @ rest
        else:
            carried = rest
        turn = Euler([math.radians(a) for a in rotations[name]]).to_matrix()
        pb.rotation_quaternion = (carried.inverted() @ turn @ carried).to_quaternion()
    bpy.context.view_layer.update()


def hold_rest(arm, name, yaw=0.0):
    """Pose a bone so that it keeps its rest orientation (turned by yaw degrees about the vertical),
    whatever its parents are doing. Used to keep feet flat on the ground and heads level."""
    bpy.context.view_layer.update()
    pb = arm.pose.bones[P + name]
    pb.rotation_mode = "QUATERNION"
    rest = pb.bone.matrix_local.to_3x3()
    carried = pb.parent.matrix.to_3x3() @ pb.parent.bone.matrix_local.to_3x3().inverted() @ rest
    want = Matrix.Rotation(math.radians(yaw), 3, "Z") @ rest
    pb.rotation_quaternion = (carried.inverted() @ want).to_quaternion()
    bpy.context.view_layer.update()


def ground(arm, feet=("LeftFoot", "RightFoot")):
    """Move the hips straight down or up until the lower ankle is back at its rest height."""
    bpy.context.view_layer.update()
    lift = min(arm.pose.bones[P + f].head.z - arm.data.bones[P + f].head_local.z for f in feet)
    hips = arm.pose.bones[P + "Hips"]
    hips.location = Vector(hips.location) + hips.bone.matrix_local.to_3x3().inverted() @ Vector((0, 0, -lift))
    bpy.context.view_layer.update()
    return lift


def key_pose(arm, frame):
    """Keyframe every bone's rotation and the hips' position."""
    for pb in arm.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    arm.pose.bones[P + "Hips"].keyframe_insert("location", frame=frame)


def rest_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


# ----------------------------------------------------------------------------- cached, ready-to-use rig
def build(who, col, verbose=True):
    """Body, watertight skin and skeleton of one fighter, skinned. Returns dict(arm, body, proxy, joints, hands)."""
    from . import oni, ronin
    src = oni if who == "oni" else ronin
    body, A = src.load_body(col, verbose=verbose)
    px = bpy.data.objects[A["proxy"]]
    col.objects.link(px)
    J, hands = joints(who, px.data, body.data, verbose)
    arm = armature(who.capitalize() + "_Rig", J, col)
    names, Wp, missing = skin_proxy(arm, px)
    if verbose:
        print(f"    skin weighted: {len(names)} bones, {missing} of {len(px.data.vertices)} verts without weights")
    skin_body(arm, body, px, names, Wp, J, hands, verbose)
    px.hide_render = True
    px.display_type = "WIRE"
    return dict(arm=arm, body=body, proxy=px, joints=J, hands=hands, anchors=A)


LIGHT = False        # True: load skeleton and collision skin only (no body mesh, no textures) - enough to bake and measure a performance


def load(who, col=None, rebuild=False, verbose=True):
    """The rigged fighter, from assets/gen/<who>_rig.blend when that is up to date.
    With rig.LIGHT set the heavy body is left in the file and the collision skin stands in for it."""
    import json
    import os
    import time

    from . import oni, ronin
    src = oni if who == "oni" else ronin
    cache = os.path.join(core.ASSETS, "gen", f"{who}_rig.blend")
    meta = cache.replace(".blend", ".json")
    col = col or bpy.context.scene.collection
    stale = (not os.path.exists(cache) or not os.path.exists(meta) or os.path.getmtime(cache) < os.path.getmtime(__file__)
             or not os.path.exists(src.CACHE) or os.path.getmtime(cache) < os.path.getmtime(src.CACHE)
             or os.path.getmtime(src.CACHE) < os.path.getmtime(src.__file__))
    names = (who.capitalize() + "_Rig", src.__name__.split(".")[-1].capitalize() + "Body", who.capitalize() + "Proxy")
    if rebuild or stale:
        t0 = time.time()
        tmp = core.collection("_rig_build")
        R = build(who, tmp, verbose)
        R["arm"].name, R["body"].name, R["proxy"].name = names
        hands = {k: {kk: (vv.tolist() if hasattr(vv, "tolist") else vv) for kk, vv in v.items()} for k, v in R["hands"].items()}
        A = {k: v for k, v in R["anchors"].items() if k not in ("proxy", "collider")}
        with open(meta, "w") as fh:
            json.dump(dict(joints=R["joints"], hands=hands, anchors=A), fh, indent=1)
        bpy.data.libraries.write(cache, {R["arm"], R["body"], R["proxy"]}, fake_user=True)
        for o in (R["body"], R["proxy"], R["arm"]):
            bpy.data.objects.remove(o)
        stray = bpy.data.objects.get(R["anchors"].get("collider", ""))
        if stray is not None and not stray.users_collection:
            bpy.data.objects.remove(stray)
        bpy.data.collections.remove(tmp)
        if verbose:
            print(f"  rig cached: {os.path.getsize(cache) / 1e6:.0f} MB, {time.time() - t0:.1f}s")
    wanted = [n for n in names if not (LIGHT and n == names[1])]
    with bpy.data.libraries.load(cache) as (lib_src, lib_dst):
        lib_dst.objects = [n for n in lib_src.objects if n in wanted]
    obs = {o.name.split(".")[0]: o for o in lib_dst.objects}
    for o in obs.values():
        col.objects.link(o)
    with open(meta) as fh:
        M = json.load(fh)
    px = obs[names[2]]
    px.hide_render = True
    return dict(arm=obs[names[0]], body=obs.get(names[1], px), proxy=px, joints=M["joints"], hands=M["hands"], anchors=M["anchors"])
