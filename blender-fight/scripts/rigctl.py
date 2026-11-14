"""Control rig on top of the humanoid skeleton: IK feet and hands with pole targets.

add_controls(arm) adds, per side:
  ctl_foot / ctl_hand  - free control bones (copies of the foot / hand bone); the leg and arm reach them by IK
                         and the foot / hand copy their rotation, so a planted foot cannot slide
  pole_knee / pole_elbow - aim the knee and elbow
Pole angles are calibrated numerically so that the rest pose is left unchanged.
"""
import bpy, math
from mathutils import Vector, Matrix

SIDES = ('L', 'R')


def add_controls(arm):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for s in SIDES:
        for src, ctl in (('foot.' + s, 'ctl_foot.' + s), ('hand.' + s, 'ctl_hand.' + s)):
            b = eb.new(ctl)
            b.head, b.tail, b.roll = eb[src].head, eb[src].tail, eb[src].roll
            b.use_deform = False
        k = eb.new('pole_knee.' + s)
        k.head = eb['shin.' + s].head + Vector((0, -0.9, 0)); k.tail = k.head + Vector((0, -0.12, 0)); k.use_deform = False
        e = eb.new('pole_elbow.' + s)
        e.head = eb['forearm.' + s].head + Vector((0, 0.7, -0.15)); e.tail = e.head + Vector((0, 0.12, 0)); e.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')
    pb = arm.pose.bones
    for s in SIDES:
        for bone, ctl, pole in (('shin.' + s, 'ctl_foot.' + s, 'pole_knee.' + s), ('forearm.' + s, 'ctl_hand.' + s, 'pole_elbow.' + s)):
            c = pb[bone].constraints.new('IK'); c.name = 'IK'
            c.target, c.subtarget, c.chain_count = arm, ctl, 2
            c.pole_target, c.pole_subtarget = arm, pole
            c.use_stretch = False
            for p in (pb[bone], pb[bone].parent):
                p.ik_stretch = 0.0
        for bone, ctl in (('foot.' + s, 'ctl_foot.' + s), ('hand.' + s, 'ctl_hand.' + s)):
            c = pb[bone].constraints.new('COPY_ROTATION'); c.name = 'CopyRot'
            c.target, c.subtarget = arm, ctl
            c.target_space = c.owner_space = 'WORLD'
    _calibrate(arm)


def _calibrate(arm):
    """Find the pole angle of each IK chain that keeps the middle joint where it rests."""
    pb = arm.pose.bones
    for s in SIDES:
        for bone in ('shin.' + s, 'forearm.' + s):
            c = pb[bone].constraints['IK']
            rest = arm.data.bones[bone].head_local.copy()
            best = (1e9, 0.0)
            for coarse in (range(-180, 180, 15), None):
                angles = coarse if coarse else [best[1] + d for d in range(-14, 15, 2)]
                for a in angles:
                    c.pole_angle = math.radians(a)
                    bpy.context.view_layer.update()
                    err = (pb[bone].head - rest).length
                    if err < best[0]:
                        best = (err, a)
            c.pole_angle = math.radians(best[1])
            print(f'  pole {bone}: {best[1]:.0f} deg, rest error {best[0] * 1000:.1f} mm')
    bpy.context.view_layer.update()
