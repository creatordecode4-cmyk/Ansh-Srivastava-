"""Stage 3b: assemble the blocking animatic (arena + rigged fighters + choreography + shot cameras).
python3 scripts/build_animatic.py   ->  build/animatic.blend
"""
import bpy, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
B = os.path.join(os.path.dirname(HERE), 'build')
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, 'arena.blend'))
import anim_lib as A, choreo
from mathutils import Vector
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 720
with bpy.data.libraries.load(os.path.join(B, 'characters_ctrl.blend'), link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c.startswith('CHAR_')]
for c in dst.collections:
    sc.collection.children.link(c)
bpy.context.view_layer.update()
oni = A.Actor('Oni', {choreo.OK: 'RL'})
ron = A.Actor('Ronin', {choreo.RR: 'R', choreo.RL: 'L'})
T = choreo.build(oni, ron, sc)

# the fused sheathed handle disappears on the frame the real katana takes over
for nm in ('Oni_Body', 'Oni_BodyLo'):
    mk = bpy.data.objects[nm].modifiers['HandleMask']
    for f, on in ((1, False), (T['oni_draw'] - 1, False), (T['oni_draw'], True)):
        mk.show_render = mk.show_viewport = on
        mk.keyframe_insert('show_render', frame=f)
        mk.keyframe_insert('show_viewport', frame=f)

# effects clock (petals, snow): real time, 30 % speed in the two slow-motion beats
SLOW = [(263, 288, 0.3), (613, 630, 0.3)]
clock = bpy.data.objects['FX_Clock']
clock.driver_remove('location', 2)
t, prev = 0.0, 1
keys = [(1, 0.0)]
for a, b, sp in SLOW:
    t += (a - prev) / 24.0
    keys.append((a, t))
    t += (b - a) / 24.0 * sp
    keys.append((b, t))
    prev = b
keys.append((720, t + (720 - prev) / 24.0))
for f, v in keys:
    clock.location.z = v
    clock.keyframe_insert('location', index=2, frame=f)
for fc in clock.animation_data.action.fcurves if hasattr(clock.animation_data.action, 'fcurves') else []:
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'

# ---------------------------------------------------------------- cameras
CAMS = bpy.data.collections['CAMERAS']


def P(act, frame, bone='Hips'):
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    pb = act.rig.pose.bones[bone]
    return (pb.tail if bone == 'Head' else pb.head).copy()


def shot(name, f0, f1, keys, lens=35.0, shake=0.0):
    """keys: [(frame, loc, aim)], linear camera and target moves between them."""
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    aim = bpy.data.objects.new(name + '_Aim', None)
    CAMS.objects.link(cam)
    CAMS.objects.link(aim)
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.05, 2000
    cd.dof.use_dof = False
    c = cam.constraints.new('TRACK_TO')
    c.target, c.track_axis, c.up_axis = aim, 'TRACK_NEGATIVE_Z', 'UP_Y'
    for f, loc, a in keys:
        cam.location = loc
        aim.location = a
        cam.keyframe_insert('location', frame=f)
        aim.keyframe_insert('location', frame=f)
    if shake > 0:
        act = aim.animation_data.action
        fcs = act.fcurves if hasattr(act, 'fcurves') else [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
        for i, fc in enumerate(fcs):
            m = fc.modifiers.new('NOISE')
            m.scale, m.strength, m.phase = 2.2, shake, 10.0 * i + f0
    mk = sc.timeline_markers.new(name, frame=f0)
    mk.camera = cam
    return cam


V = Vector
shot('S01_Drone', 1, 72, [(1, (0.5, -33, 14), (-2.4, 6, 2.0)), (72, (-1.2, -15.5, 6.5), (-2.3, 7, 2.5))], 28)
shot('S02_OniWalk', 73, 112, [(f, (-2.9, -1.5, 0.30), P(oni, f) + V((0, 0, 0.30))) for f in range(73, 113, 6)] + [(112, (-2.9, -1.5, 0.30), P(oni, 112) + V((0, 0, 0.30)))], 24)
shot('S03_MaskCU', 113, 128, [(f, P(oni, f, 'Head') + V((2.6, -0.40, -0.10)), P(oni, f, 'Head') + V((0, 0, -0.14))) for f in (113, 118, 123, 128)], 90)
shot('S04_HiltCU', 129, 144, [(f, P(oni, f) + V((1.9, 0.95, 0.38)), P(oni, f) + V((0.30, 0.18, 0.24))) for f in (129, 134, 139, 144)], 50)
shot('S05_RoninReveal', 145, 200, [(145, (-2.35, 5.2, 0.45), (-2.0, 10.3, 1.45)), (200, (-2.25, 7.3, 0.75), (-2.0, 10.3, 1.6))], 40)
shot('S06_HatCU', 201, 215, [(201, (-2.6, 7.7, 1.50), (-2.0, 10.3, 1.84)), (215, (-2.55, 8.0, 1.52), (-2.0, 10.3, 1.84))], 85)
shot('S07_Standoff', 216, 240, [(216, (-1.45, -2.3, 1.78), (-2.2, 9.0, 1.30)), (240, (-1.5, -2.0, 1.72), (-2.2, 9.0, 1.30))], 30)
shot('S08_Dash', 241, 262, [(241, (6.6, 5.25, 0.80), (-2.3, 5.25, 1.10)), (262, (6.0, 5.25, 0.80), (-2.3, 5.25, 1.10))], 21)
K = T['clash'][1]
shot('S09_Clash', 263, 288, [(263, (-0.1, 4.2, 0.50), K), (288, (-0.5, 4.5, 0.70), K + V((0, 0.1, 0)))], 35)


def mid(f, z=1.2):
    a, b = P(oni, f), P(ron, f)
    return V(((a.x + b.x) / 2, (a.y + b.y) / 2, z))


orbit = []
for i, f in enumerate(range(289, 361, 6)):
    ang = math.radians(0 + 125 * i / 11)
    c = mid(f)
    orbit.append((f, c + V((math.cos(ang) * 5.0, math.sin(ang) * 5.0, 0.2 + 0.4 * i / 11)), c + V((0, 0, 0.15))))
orbit.append((360, orbit[-1][1], orbit[-1][2]))
shot('S10_Orbit', 289, 360, orbit, 32)
shot('S11_SpinKick', 361, 396, [(361, mid(375) + V((-4.6, -0.6, 0.1)), mid(375)), (396, mid(390) + V((-4.2, -0.9, 0.0)), mid(390))], 32)
s0, s1 = T['slide'][2], T['slide'][3]
shot('S12_Slide', 397, 432, [(f, (s1.x + 1.6, s1.y - 2.4, 0.35), P(oni, f) + V((0, 0, 0.15))) for f in range(397, 433, 5)], 24)
shot('S13a_OTS_Ronin', 433, 456, [(433, P(ron, 450) + V((1.6, 2.4, 0.95)), mid(450, 1.30)), (456, P(ron, 450) + V((1.45, 2.2, 0.95)), mid(450, 1.30))], 32, shake=0.05)
shot('S13b_OTS_Oni', 457, 474, [(457, P(oni, 466) + V((-1.6, -2.4, 0.95)), mid(466, 1.20)), (474, P(oni, 466) + V((-1.45, -2.2, 0.95)), mid(466, 1.20))], 32, shake=0.05)
shot('S13c_LowSide', 475, 504, [(475, mid(482) + V((3.3, -0.3, -0.65)), mid(482, 1.3)), (504, mid(499) + V((3.7, -0.3, -0.65)), mid(499, 1.2))], 28, shake=0.04)
shot('S14_PowerSlash', 505, 552, [(505, mid(520) + V((4.2, -0.8, -0.70)), mid(520, 1.2)), (552, mid(545) + V((4.6, -0.2, -0.70)), mid(545, 1.2))], 22)
shot('S14b_Cape', 553, 576, [(553, P(ron, 560) + V((1.9, -2.3, 0.35)), P(ron, 560) + V((0, 0, 0.35))), (576, P(ron, 576) + V((1.7, -2.1, 0.35)), P(ron, 576) + V((0, 0, 0.35)))], 50)
shot('S15_Crossing', 577, 648, [(577, mid(620) + V((7.6, 0, -0.2)), mid(620, 1.1)), (648, mid(620) + V((6.9, 0, -0.2)), mid(620, 1.1))], 34)
shot('S16_HatSplit', 649, 684, [(649, P(ron, 660, 'Head') + V((-1.0, -2.3, -0.25)), P(ron, 660, 'Head') + V((0, 0, -0.05))), (684, P(ron, 660, 'Head') + V((-0.9, -2.1, -0.25)), P(ron, 660, 'Head') + V((0, 0, -0.05)))], 60)
shot('S17_MaskCrack', 685, 720, [(685, P(oni, 700, 'Head') + V((0.9, 2.3, -0.25)), P(oni, 700, 'Head') + V((0, 0, -0.10))), (720, P(oni, 700, 'Head') + V((0.8, 2.0, -0.25)), P(oni, 700, 'Head') + V((0, 0, -0.10)))], 75)

# fade to black
for f, e in ((1, 0.0), (700, 0.0), (719, -14.0)):
    sc.view_settings.exposure = e
    sc.view_settings.keyframe_insert('exposure', frame=f)

# animatic render mode: light bodies, few samples, no motion blur / DOF
for n in ('Oni', 'Ronin'):
    bpy.data.objects[n + '_Body'].hide_render = True
    bpy.data.objects[n + '_BodyLo'].hide_render = False
    for suf in ('_Body', '_BodyLo'):
        for m in bpy.data.objects[n + suf].modifiers:
            if m.type == 'ARMATURE':
                m.show_viewport = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 512, 288, 100
sc.cycles.samples, sc.cycles.use_denoising = 6, True
sc.cycles.use_adaptive_sampling = False
sc.render.use_motion_blur = False
sc.render.use_persistent_data = True
sc.render.image_settings.file_format = 'PNG'
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(B, 'animatic.blend'))
print('ANIMATIC built; shots:', len(sc.timeline_markers), 'T keys:', sorted(T.keys()))
