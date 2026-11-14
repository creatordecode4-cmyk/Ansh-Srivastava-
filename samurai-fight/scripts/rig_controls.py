"""Stage 3a: animation controls on top of the skinned rigs.
python3 scripts/rig_controls.py build/characters_rigged.blend build/characters_ctrl.blend

Per character (all children of <Name>_Root, which places the character in the world):
  FOOT_L / FOOT_R    world-space foot targets (leg IK + foot rotation) -> planted feet cannot slide
  KNEE_L / KNEE_R    knee pole targets
  Katana objects     the SWORD is the master: animate the blade, the hands follow it
  GRIP_*             children of a katana; arm IK + hand rotation follow them
  ELBOW_L / ELBOW_R  elbow pole targets
  Hips, Spine*, Neck, Head, Shoulders, fingers: plain FK pose bones
"""
import bpy, sys, os, math
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weapons as W

src, out = sys.argv[1], sys.argv[2]
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
vl = bpy.context.view_layer

# katana -> which hands hold it and how far below the guard each hand sits (metres along the grip)
SWORDS = {
    'Oni': [('Oni_Katana', 'Oni', {'Right': 0.075, 'Left': 0.205})],
    'Ronin': [('Ronin_Katana_R', 'Ronin', {'Right': 0.08}), ('Ronin_Katana_L', 'Ronin', {'Left': 0.08})],
}
GRIP_CURL = (58, 72, 55)          # finger-block curl in degrees for a closed grip
# fused sheathed-sword handles: (segment start at the pommel, segment end, radius, length to hide) in rest space
HANDLES = {'Oni': [((0.115, -0.47, 1.30), (0.38, 0.52, 0.67), 0.062, 0.31)]}


def empty(name, coll, parent, matrix_world, size=0.08, kind='PLAIN_AXES'):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type, e.empty_display_size = kind, size
    coll.objects.link(e)
    e.parent = parent
    e.matrix_world = matrix_world
    return e


def grip_rest_sword_matrix(rig, side, d):
    """World matrix the katana has when this hand holds it in the T-pose (hammer grip, blade out of the thumb side,
    cutting edge toward the knuckles)."""
    hand, mid = rig.data.bones[side + 'Hand'], rig.data.bones[side + 'HandFingers1']
    wrist, knuckle = rig.matrix_world @ hand.head_local, rig.matrix_world @ mid.head_local
    palm = wrist + (knuckle - wrist) * 0.85 + Vector((0, 0, -0.030))
    if side == 'Right':
        X, Y, Z = Vector((0, 0, -1)), Vector((1, 0, 0)), Vector((0, -1, 0))
    else:
        X, Y, Z = Vector((0, 0, 1)), Vector((-1, 0, 0)), Vector((0, -1, 0))
    M = Matrix((X, Y, Z)).transposed().to_4x4()
    M.translation = palm + Z * d
    return M


def calibrate_pole(rig, bone, upper):
    """Pick the IK pole angle that leaves the upper bone's rest twist untouched."""
    pb = rig.pose.bones[bone]
    c = pb.constraints['IK']
    rest = rig.data.bones[upper].matrix_local.to_quaternion()
    best = None
    for ang in range(-180, 180, 15):
        c.pole_angle = math.radians(ang)
        vl.update()
        q = rig.pose.bones[upper].matrix.to_quaternion()
        err = rest.rotation_difference(q).angle
        if best is None or err < best[0]:
            best = (err, ang)
    c.pole_angle = math.radians(best[1])
    vl.update()
    return best


for name in ('Oni', 'Ronin'):
    coll = bpy.data.collections['CHAR_' + name]
    rig = bpy.data.objects[name + '_Rig']
    root = empty(name + '_Root', coll, None, Matrix.Identity(4), 0.5, 'CIRCLE')
    root.rotation_mode = 'XYZ'
    rig.parent = root
    RW = rig.matrix_world
    report = []
    for side in ('Left', 'Right'):
        s = side[0]
        # ---- legs
        foot_b, leg_b, up_b = rig.data.bones[side + 'Foot'], rig.data.bones[side + 'Leg'], rig.data.bones[side + 'UpLeg']
        foot = empty(f'{name}_FOOT_{s}', coll, root, RW @ foot_b.matrix_local, 0.12, 'ARROWS')
        knee = empty(f'{name}_KNEE_{s}', coll, root, Matrix.Translation(RW @ leg_b.head_local + Vector((0, -0.7, 0))), 0.06, 'SPHERE')
        pb = rig.pose.bones[side + 'Leg']
        c = pb.constraints.new('IK')
        c.target, c.chain_count, c.pole_target, c.use_stretch = foot, 2, knee, False
        cr = rig.pose.bones[side + 'Foot'].constraints.new('COPY_ROTATION')
        cr.target = foot
        report.append((side + 'Leg',) + calibrate_pole(rig, side + 'Leg', side + 'UpLeg'))
        # ---- arms: every hand has its own free target; a keyable constraint snaps it onto a sword grip
        fore_b, hand_b = rig.data.bones[side + 'ForeArm'], rig.data.bones[side + 'Hand']
        elbow = empty(f'{name}_ELBOW_{s}', coll, root, Matrix.Translation(RW @ fore_b.head_local + Vector((0, 0.5, -0.45))), 0.06, 'SPHERE')
        hand = empty(f'{name}_HAND_{s}', coll, root, RW @ hand_b.matrix_local, 0.07, 'CUBE')
        hand.rotation_mode = 'QUATERNION'
        pb = rig.pose.bones[side + 'ForeArm']
        c = pb.constraints.new('IK')
        c.target, c.chain_count, c.pole_target, c.use_stretch = hand, 2, elbow, False
        cr = rig.pose.bones[side + 'Hand'].constraints.new('COPY_ROTATION')
        cr.target = hand
        vl.update()
        report.append((side + 'ForeArm',) + calibrate_pole(rig, side + 'ForeArm', side + 'Arm'))
        for k in range(3):
            rig.pose.bones[f'{side}HandFingers{k + 1}'].rotation_mode = 'XYZ'
    # ---- swords: the katana is the master, GRIP_* ride on it, HAND_* copy them while "Grip" influence is 1
    for sname, style, hands in SWORDS[name]:
        kat = W.build_katana(coll, sname, style)
        kat.rotation_mode = 'QUATERNION'
        kat.parent = root
        first = True
        for side, d in hands.items():
            s = side[0]
            S_rest = grip_rest_sword_matrix(rig, side, d)
            if first:                       # park the sword in this hand's T-pose grip
                kat.matrix_world = S_rest
                first = False
                vl.update()
            hand_rest = RW @ rig.data.bones[side + 'Hand'].matrix_local
            grip = empty(f'{name}_GRIP_{s}', coll, kat, Matrix.Identity(4), 0.05, 'CUBE')
            grip.matrix_parent_inverse = Matrix.Identity(4)
            grip.matrix_local = S_rest.inverted() @ hand_rest
            ct = bpy.data.objects[f'{name}_HAND_{s}'].constraints.new('COPY_TRANSFORMS')
            ct.name, ct.target, ct.influence = 'Grip', grip, 1.0
    # ---- handle of the sheathed (fused) sword: hidden by a mask once the real katana is drawn
    for seg_a, seg_b, radius, length in HANDLES.get(name, []):
        import numpy as np
        me = bpy.data.objects[name + '_Body'].data
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        A_, B_ = np.array(seg_a), np.array(seg_b)
        ab = B_ - A_
        L_ = float(np.linalg.norm(ab))
        t = ((co - A_) @ ab) / (L_ * L_)
        dist = np.linalg.norm(co - (A_ + np.clip(t, 0, 1)[:, None] * ab), axis=1)
        sel = np.nonzero((dist < radius) & (t * L_ < length) & (t > -0.05))[0]
        vg = bpy.data.objects[name + '_Body'].vertex_groups.get('SheathHandle') or bpy.data.objects[name + '_Body'].vertex_groups.new(name='SheathHandle')
        vg.add(sel.tolist(), 1.0, 'REPLACE')
        mk = bpy.data.objects[name + '_Body'].modifiers.new('HandleMask', 'MASK')
        mk.vertex_group, mk.invert_vertex_group = 'SheathHandle', True
        mk.show_render = mk.show_viewport = False
        print(f'CTRL {name}: sheath-handle group {len(sel)} verts', flush=True)
    # ---- light copy of the body for fast animatic renders (same vertex groups, same armature)
    body = bpy.data.objects[name + '_Body']
    lo = body.copy()
    lo.data = body.data.copy()
    lo.name = name + '_BodyLo'
    coll.objects.link(lo)
    lo.modifiers.clear()
    dm = lo.modifiers.new('dec', 'DECIMATE')
    dm.ratio = 45000 / len(lo.data.polygons)
    lm = bpy.data.meshes.new_from_object(lo.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    lo.modifiers.clear()
    old = lo.data
    lo.data = lm
    bpy.data.meshes.remove(old)
    lm.name = name + '_BodyLo'
    if 'SheathHandle' in lo.vertex_groups:
        mk = lo.modifiers.new('HandleMask', 'MASK')
        mk.vertex_group, mk.invert_vertex_group = 'SheathHandle', True
        mk.show_render = mk.show_viewport = False
    am = lo.modifiers.new('Armature', 'ARMATURE')
    am.object = rig
    lo.hide_render = True
    lo.hide_viewport = True
    vl.update()
    print(f'CTRL {name}: pole calibration (bone, residual rad, angle deg):', [(b, round(e, 3), a) for b, e, a in report], flush=True)

bpy.ops.wm.save_as_mainfile(filepath=out)
print('CTRL saved', out)
