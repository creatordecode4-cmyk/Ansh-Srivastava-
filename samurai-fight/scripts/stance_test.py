"""Studio render of the guard stances. python3 scripts/stance_test.py <ctrl.blend> <out_prefix> [res] [spp]"""
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stances as S
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
prefix = sys.argv[2]
res = int(sys.argv[3]) if len(sys.argv) > 3 else 640
spp = int(sys.argv[4]) if len(sys.argv) > 4 else 12
VIEWS = (('q34', -40), ('side', 0)) if '--two' in sys.argv else (('front', -90), ('q34', -35), ('side', 0), ('back', 115))
sc = bpy.context.scene
w = bpy.data.worlds.new('studio'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.19, 0.19, 0.21, 1)
rigl = bpy.data.objects.new('lights', None); sc.collection.objects.link(rigl)
for nm, d, e in (('key', (0.45, 0.75, -0.5), 3.2), ('fill', (-0.8, 0.45, -0.25), 1.1), ('rim', (-0.2, -0.9, -0.35), 2.2)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy, l.angle = e, math.radians(12)
    o = bpy.data.objects.new(nm, l); o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler(); o.parent = rigl
    sc.collection.objects.link(o)
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type, cd.ortho_scale = 'ORTHO', 2.6
sc.render.resolution_x, sc.render.resolution_y = res, res
sc.render.engine = 'CYCLES'; sc.cycles.samples = spp; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
for name in ('Oni', 'Ronin'):
    S.apply(name, S.STANCES[name + '_guard'])
    for ob in sc.objects:
        if ob.type in ('MESH', 'ARMATURE'):
            ob.hide_render = not ob.name.startswith(name)
    for k, az in VIEWS:
        a = math.radians(az); d = Vector((math.cos(a), math.sin(a), 0.12)).normalized()
        cam.location = Vector((0, -0.1, 1.05)) + d * 8
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        rigl.rotation_euler = (0, 0, a + math.radians(90))
        sc.render.filepath = f'{prefix}_{name}_{k}.png'
        bpy.ops.render.render(write_still=True)
    print('STANCE', name)
