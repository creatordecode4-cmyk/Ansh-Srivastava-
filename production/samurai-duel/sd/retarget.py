"""Carrying a clip from one Mixamo-named skeleton to another.

A Mixamo download made on its stock character moves that character's skeleton. Ours have the
same bones under the same names but other proportions and a slightly different rest pose (the
Ronin's forearms lean forward, both stand with the feet wider). Every bone is therefore driven
so that it points where the source bone points:

    turn(t)    = source bone's world rotation now x inverse of its rest rotation
    align      = smallest rotation taking our bone's rest direction onto the source's rest direction
    our bone   = turn(t) x align x our rest rotation          (all in world space)

Only the hips also translate: their travel is scaled by the ratio of the two hip heights, so a
longer-legged fighter takes proportionally longer steps and the feet keep their footing.
"""
import os

import bpy
from mathutils import Matrix, Quaternion, Vector

from .rig import P


def import_fbx(path, name=None):
    """Import a Mixamo FBX; returns (armature object, action, [other new objects])."""
    before_o, before_a = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path, use_anim=True, automatic_bone_orientation=False, ignore_leaf_bones=False)
    new = [o for o in bpy.data.objects if o not in before_o]
    arms = [o for o in new if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError(f"no armature in {path}")
    arm = arms[0]
    acts = [a for a in bpy.data.actions if a not in before_a]
    act = acts[0] if acts else None
    if name:
        arm.name = name
        if act:
            act.name = name
    return arm, act, [o for o in new if o is not arm]


def frame_range(action):
    a, b = action.frame_range
    return float(a), float(b)


def _bone_names(arm):
    """Map from the bare Mixamo name ('Hips') to this armature's bone name, whatever its prefix."""
    out = {}
    for b in arm.data.bones:
        out[b.name.split(":")[-1]] = b.name
    return out


def _rest_world(arm, bone_name):
    """Rest orientation of a bone in world space (object rotation included, scale removed)."""
    m = (arm.matrix_world @ arm.data.bones[bone_name].matrix_local).to_3x3()
    return m.normalized()


def _direction(m):
    return (m @ Vector((0, 1, 0))).normalized()          # a Blender bone runs along its local +Y


def plan(src, dst):
    """Per-bone constants for a source/target pair: (bare name, src bone, dst bone, src rest inverse, align x dst rest)."""
    bpy.context.view_layer.update()                      # object transforms set a moment ago must be in matrix_world
    sn, dn = _bone_names(src), _bone_names(dst)
    rows = []
    for bare, dname in dn.items():
        if bare not in sn or bare.endswith("_End") or bare[-1] == "4" and "Hand" in bare:
            continue
        rs, rd = _rest_world(src, sn[bare]), _rest_world(dst, dname)
        align = _direction(rd).rotation_difference(_direction(rs)).to_matrix()
        rows.append((bare, sn[bare], dname, rs.inverted(), align @ rd))
    depth = {b.name: len(b.parent_recursive) for b in dst.data.bones}
    rows.sort(key=lambda r: depth[r[2]])
    hs = (src.matrix_world @ src.data.bones[sn["Hips"]].head_local)
    hd = (dst.matrix_world @ dst.data.bones[dn["Hips"]].head_local)
    return dict(rows=rows, src_hips=sn["Hips"], dst_hips=dn["Hips"], src_rest=hs, dst_rest=hd, scale=hd.z / max(1e-6, hs.z))


def retarget(src, action, dst, name, fps_src=30.0, fps_dst=24.0, start=1, in_place=False, plan_=None):
    """Bake 'action' (playing on src) onto dst as a new action sampled at fps_dst. Returns the action.

    in_place keeps the hips over the starting spot (their height still moves)."""
    sc = bpy.context.scene
    Pn = plan_ or plan(src, dst)
    src.animation_data_create()
    src.animation_data.action = action
    f0, f1 = frame_range(action)
    n = int(round((f1 - f0) * fps_dst / fps_src)) + 1
    dst.animation_data_create()
    new = bpy.data.actions.new(name)
    dst.animation_data.action = new
    dinv = dst.matrix_world.inverted()
    drot = dst.matrix_world.to_3x3().normalized().inverted()
    for pb in dst.pose.bones:
        pb.rotation_mode = "QUATERNION"
    prev = {}
    for k in range(n):
        fs = f0 + k * fps_src / fps_dst
        sc.frame_set(int(fs // 1), subframe=fs % 1.0)
        sm = src.matrix_world
        want = {}
        for bare, sname, dname, rs_inv, base in Pn["rows"]:
            cur = (sm @ src.pose.bones[sname].matrix).to_3x3().normalized()
            want[dname] = drot @ (cur @ rs_inv @ base)                       # target orientation in dst armature space
        hips_w = sm @ src.pose.bones[Pn["src_hips"]].head
        off = (hips_w - Pn["src_rest"]) * Pn["scale"]
        if in_place:
            off.x = off.y = 0.0
        hips_local = dinv @ (Pn["dst_rest"] + off)
        # write local rotations parent first: local = (parent pose x parent rest^-1 x rest)^-1 x wanted
        frame = start + k
        for bare, sname, dname, rs_inv, base in Pn["rows"]:
            pb = dst.pose.bones[dname]
            rest = pb.bone.matrix_local.to_3x3()
            if pb.parent:
                pw = want.get(pb.parent.name)
                if pw is None:
                    pw = pb.parent.bone.matrix_local.to_3x3()
                carried = pw @ pb.parent.bone.matrix_local.to_3x3().inverted() @ rest
            else:
                carried = rest
            q = (carried.inverted() @ want[dname]).to_quaternion()
            if dname in prev and prev[dname].dot(q) < 0:                      # keep the quaternion on the same side: no flips between frames
                q.negate()
            prev[dname] = q.copy()
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if dname == Pn["dst_hips"]:
                # pose-bone location is in the bone's rest frame, relative to its rest head
                pb.location = rest.inverted() @ (hips_local - pb.bone.head_local)
                pb.keyframe_insert("location", frame=frame)
    new.use_fake_user = True
    new["frames"] = n
    return new


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def direction_error(src, dst, bare_names=("LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg", "Spine1", "Head")):
    """Largest angle (degrees) between corresponding bones of src and dst in their current poses."""
    import math
    sn, dn = _bone_names(src), _bone_names(dst)
    worst = (0.0, None)
    for b in bare_names:
        ds = _direction((src.matrix_world @ src.pose.bones[sn[b]].matrix).to_3x3().normalized())
        dd = _direction((dst.matrix_world @ dst.pose.bones[dn[b]].matrix).to_3x3().normalized())
        ang = math.degrees(ds.angle(dd))
        if ang > worst[0]:
            worst = (ang, b)
    return worst
