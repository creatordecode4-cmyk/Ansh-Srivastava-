"""Toolkit smoke test: Oni walks four steps and settles into guard. Prints foot-slide numbers, renders a strip.
python3 scripts/anim_test.py <out.png>"""
import bpy, sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
B = os.path.join(os.path.dirname(HERE), 'build')
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, 'characters_ctrl.blend'))
import anim_lib as A
from mathutils import Vector
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 120
oni = A.Actor('Oni', {'Oni_Katana': 'RL'})
t0 = time.time()
face = 0.0
# start standing at x=-3, feet side by side
oni.plant('L', 1, (-3.0, 0.13), face + 8)
oni.plant('R', 1, (-3.0, -0.13), face - 8)
relaxed = lambda s: ((0.30 if s == 'L' else -0.30, 0.02, 0.92), (0.05 if s == 'L' else -0.05, 0.15, -1), (-1 if s == 'L' else 1, 0, 0))
free = dict(hands={'L': relaxed('L'), 'R': relaxed('R')}, grip={'L': 0, 'R': 0}, curl={'L': 0.35, 'R': 0.35}, show={'Oni_Katana': False})
oni.key(1, (-3.0, 0), face, **free)
def pose(fr, k, pos, side):
    sg = 1 if side == 'L' else -1          # swinging leg; the opposite arm comes forward
    sw = 0.22 if k % 2 == 0 else 0.0
    return dict(hands={'L': ((0.31, -sg * sw, 0.93), (0.05, 0.15, -1), (-1, 0, 0)), 'R': ((-0.31, sg * sw, 0.93), (-0.05, 0.15, -1), (1, 0, 0))},
                look=(pos.x + 6, pos.y, 1.6))
oni.travel(1, 65, (-3.0, 0), (0.0, 0), face, 4, lead='R', pose=pose, end_stance={'R': (-0.17, 0.36, -8), 'L': (0.27, -0.38, 50)})
guard = {'Oni_Katana': ('local', (0.0, 0.44, 1.07), (0.0, 0.90, 0.43), (0, 0.43, -0.90))}
oni.key(80, (0.0, 0), face, hips=dict(z=0.85, yaw=16, pitch=6), sw=guard, grip={'L': 1, 'R': 1}, curl={'L': 1, 'R': 1}, show={'Oni_Katana': True}, spine=(-10, 3, 0), look=(6, 0, 1.6))
oni.key(100, (0.0, 0), face, hips=dict(z=0.85, yaw=16, pitch=6), sw=guard, spine=(-10, 3, 0), look=(6, 0, 1.6))
print('ANIM keyed in %.1fs' % (time.time() - t0))
for f in (17, 33):
    sc.frame_set(f); bpy.context.view_layer.update()
    pb = oni.rig.pose.bones
    up = (pb['Spine2'].tail - pb['Hips'].head).normalized()
    print('ANIM f%d hips %s chest-up %s head-hips dx %.3f  handL %s' % (f, [round(v, 2) for v in pb['Hips'].head], [round(v, 2) for v in up], pb['Head'].head.x - pb['Hips'].head.x, [round(v, 2) for v in oni.o('HAND_L').matrix_world.translation]))
    for s in 'LR':
        print('ANIM    foot', s, [round(v, 2) for v in oni.o('FOOT_' + s).matrix_world.translation])
# QA: foot slide while planted (ankle below rest + 1 cm and next frame also planted)
worst = 0
for s in 'LR':
    ob = oni.o('FOOT_' + s); prev = None
    for f in range(1, 101):
        sc.frame_set(f)
        p = ob.matrix_world.translation.copy()
        planted = p.z < oni.ankle_h[s] + 0.004
        if prev is not None and planted and prev[1]:
            worst = max(worst, (p.xy - prev[0].xy).length)
        prev = (p, planted)
print('ANIM worst planted-foot slide per frame: %.4f m' % worst)
# strip render with the light bodies
for n in ('Oni', 'Ronin'):
    for suf, hide in (('_Body', True), ('_BodyLo', n != 'Oni')):
        o = bpy.data.objects[n + suf]; o.hide_render = hide
        for m in o.modifiers: m.show_viewport = True
    if n == 'Ronin':
        for o in bpy.data.objects:
            if o.name.startswith('Ronin'): o.hide_render = True
w = bpy.data.worlds.new('s'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.2, 0.2, 0.22, 1)
for nm, d, e in (('k', (0.4, 0.7, -0.5), 3.0), ('f', (-0.7, 0.5, -0.3), 1.2)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy = e
    o = bpy.data.objects.new(nm, l); o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type, cd.ortho_scale = 'ORTHO', 2.7
cam.location = (-1.5, -8, 1.05); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.engine = 'CYCLES'; sc.cycles.samples = 6; sc.cycles.use_denoising = True; sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = 300, 300
out = sys.argv[-1]; frames = [1, 9, 17, 25, 33, 41, 49, 57, 65, 72, 80, 100]
t0 = time.time()
for f in frames:
    sc.frame_set(f)
    oni_x = oni.rig.pose.bones['Hips'].head.x
    cam.location.x = oni_x
    sc.render.filepath = out.replace('.png', f'_{f:03d}.png'); bpy.ops.render.render(write_still=True)
print('ANIM rendered %d frames in %.1fs' % (len(frames), time.time() - t0))
