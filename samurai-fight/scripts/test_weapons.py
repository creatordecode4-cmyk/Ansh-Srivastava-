"""Studio render of the procedural katanas for a look check. python3 scripts/test_weapons.py out.png"""
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weapons as W
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
a = W.build_katana(sc.collection, 'Katana_Oni', 'Oni')
b = W.build_katana(sc.collection, 'Katana_Ronin', 'Ronin')
for ob, z in ((a, 0.10), (b, -0.10)):
    ob.rotation_euler = (0, math.radians(90), 0)       # blade along +X, flat side up, edge toward -Y
    ob.location = (-0.24, z, 0)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.20, 0.20, 0.22, 1)
for nm, d, e in (('k', (-0.3, 0.5, -0.8), 4.0), ('f', (0.6, -0.4, -0.6), 1.5), ('t', (0.1, 0.1, -1), 1.5)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy, l.angle = e, math.radians(25)
    o = bpy.data.objects.new(nm, l); o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler(); sc.collection.objects.link(o)
cd = bpy.data.cameras.new('c'); cd.type, cd.ortho_scale = 'ORTHO', 1.12
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0.0, 0, 3); cam.rotation_euler = (0, 0, 0)
sc.render.engine = 'CYCLES'; sc.cycles.samples = 48; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x, sc.render.resolution_y = 1600, 520
sc.render.filepath = sys.argv[-1]
bpy.ops.render.render(write_still=True)
print('WEAPON faces', len(a.data.polygons), len(b.data.polygons))
