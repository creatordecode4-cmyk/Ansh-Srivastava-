"""Fast check of the choreography without the arena: renders small side-view frames of both fighters.
python3 scripts/choreo_strip.py <out_prefix> <frame,frame,...> [--top]"""
import bpy, sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
B = os.path.join(os.path.dirname(HERE), 'build')
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, 'characters_ctrl.blend'))
import anim_lib as A, choreo
from mathutils import Vector
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 720
oni = A.Actor('Oni', {choreo.OK: 'RL'}); ron = A.Actor('Ronin', {choreo.RR: 'R', choreo.RL: 'L'})
t0 = time.time(); T = choreo.build(oni, ron, sc); print('STRIP keyed in %.1fs' % (time.time() - t0), flush=True)
for n in ('Oni', 'Ronin'):
    for suf, hide in (('_Body', True), ('_BodyLo', False)):
        o = bpy.data.objects[n + suf]; o.hide_render = hide
w = bpy.data.worlds.new('s'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.2, 0.2, 0.22, 1)
for nm, d, e in (('k', (-0.6, 0.3, -0.6), 3.0), ('f', (0.7, -0.4, -0.3), 1.2)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy = e
    o = bpy.data.objects.new(nm, l); o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 5, 0))
cd = bpy.data.cameras.new('c'); cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type = 'ORTHO'
sc.render.engine = 'CYCLES'; sc.cycles.samples = 5; sc.cycles.use_denoising = True; sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = 400, 240
FOCUS = 'oni' if '--oni' in sys.argv else ('ron' if '--ron' in sys.argv else 'both')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
prefix, frames = args[-2], [int(f) for f in args[-1].split(',')]
sc.render.resolution_x, sc.render.resolution_y = (400, 240) if '--small' not in sys.argv else (320, 200)
t0 = time.time()
for f in frames:
    sc.frame_set(f)
    ho, hr = oni.rig.pose.bones['Hips'].head, ron.rig.pose.bones['Hips'].head
    c = (ho + hr) / 2; span = max(3.4, (ho - hr).length + 2.6)
    if f < 216: c = ho.copy() if f < 180 else hr.copy(); span = 3.4
    if FOCUS == 'oni': c, span = ho.copy(), 3.2
    if FOCUS == 'ron': c, span = hr.copy(), 3.2
    cd.ortho_scale = span
    if '--top' in sys.argv:
        cam.location = (c.x, c.y, 20); cam.rotation_euler = (0, 0, math.radians(-90))
    else:
        cam.location = (c.x + 12, c.y, 1.05); cam.rotation_euler = (math.radians(90), 0, math.radians(90))     # from the east, looking west
        if f < 160: cam.location = (c.x, c.y - 12, 1.05); cam.rotation_euler = (math.radians(90), 0, 0)
        if '--q34' in sys.argv:
            d = Vector((0.75, 0.66 if FOCUS != 'ron' else -0.66, 0.15)).normalized()      # in front of the focused fighter
            cam.location = Vector((c.x, c.y, 1.05)) + d * 12; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{prefix}_{f:03d}.png'; bpy.ops.render.render(write_still=True)
print('STRIP rendered %d frames in %.1fs' % (len(frames), time.time() - t0))
# QA numbers
import numpy as np
for name, act in (('Oni', oni), ('Ronin', ron)):
    worst = 0
    for s in 'LR':
        ks = act.feet[s]
        for a, b in zip(ks, ks[1:]):
            if a[3] < 0.003 and b[3] < 0.003 and (a[1] - b[1]).length > 1e-4 and (b[0] - a[0]) > 0:
                worst = max(worst, (a[1] - b[1]).length)
    print(f'STRIP {name}: largest ground-contact foot displacement between consecutive keys (slides are intentional): {worst:.2f} m')
