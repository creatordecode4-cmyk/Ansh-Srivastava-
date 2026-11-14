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
        # ---- arms: pole below/behind the elbow
        fore_b = rig.data.bones[side + 'ForeArm']
        empty(f'{name}_ELBOW_{s}', coll, root, Matrix.Translation(RW @ fore_b.head_local + Vector((0, 0.5, -0.45))), 0.06, 'SPHERE')
    # ---- swords and grips
    for sname, style, hands in SWORDS[name]:
        kat = W.build_katana(coll, sname, style)
        kat.rotation_mode = 'XYZ'
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
            pb = rig.pose.bones[side + 'ForeArm']
            c = pb.constraints.new('IK')
            c.target, c.chain_count, c.use_stretch = grip, 2, False
            c.pole_target = bpy.data.objects[f'{name}_ELBOW_{s}']
            cr = rig.pose.bones[side + 'Hand'].constraints.new('COPY_ROTATION')
            cr.target = grip
            vl.update()
            report.append((side + 'ForeArm',) + calibrate_pole(rig, side + 'ForeArm', side + 'Arm'))
            sign = -1 if side == 'Left' else 1
            for k, deg in enumerate(GRIP_CURL):
                fb = rig.pose.bones[f'{side}HandFingers{k + 1}']
                fb.rotation_mode = 'XYZ'
                fb.rotation_euler = (0, 0, sign * math.radians(deg))
    # a hand whose grip sits on a sword parked in the OTHER hand cannot be calibrated in the T-pose: mirror the good side
    ang = {b: (e, a_) for b, e, a_ in report}
    for side, other in (('Left', 'Right'), ('Right', 'Left')):
        k, ko = side + 'ForeArm', other + 'ForeArm'
        if k in ang and ko in ang and ang[k][0] > 0.5 and ang[ko][0] < 0.5:
            rig.pose.bones[k].constraints['IK'].pole_angle = math.radians(-180 - ang[ko][1])
            report.append((k + ' (mirrored)', 0.0, -180 - ang[ko][1]))
    for pb in rig.pose.bones:
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_mode = 'XYZ'
    vl.update()
    print(f'CTRL {name}: pole calibration (bone, residual rad, angle deg):', [(b, round(e, 3), a) for b, e, a in report], flush=True)

bpy.ops.wm.save_as_mainfile(filepath=out)
print('CTRL saved', out)
