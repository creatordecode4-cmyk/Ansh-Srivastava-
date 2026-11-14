"""Neutral studio turnaround of one prepared character (front, side, back, 3/4).
python3 scripts/render_turnaround.py build/characters.blend Oni out_prefix [--spp 24] [--res 620x900]
"""
import bpy, sys, math
from mathutils import Vector

blend, name, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
spp = int(sys.argv[sys.argv.index('--spp') + 1]) if '--spp' in sys.argv else 24
res = sys.argv[sys.argv.index('--res') + 1] if '--res' in sys.argv else '620x900'
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
for ob in sc.objects:
    ob.hide_render = not ob.name.startswith(name)
ob = bpy.data.objects[name + '_Body']
co = [ob.matrix_world @ v.co for v in ob.data.vertices[::50]]
lo = Vector([min(c[i] for c in co) for i in range(3)])
hi = Vector([max(c[i] for c in co) for i in range(3)])
c, size = (lo + hi) / 2, hi - lo
w = bpy.data.worlds.new('studio')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.19, 0.19, 0.21, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
rig = bpy.data.objects.new('rig', None)
sc.collection.objects.link(rig)
for nm, d, e in (('key', (0.45, 0.75, -0.5), 3.2), ('fill', (-0.8, 0.45, -0.25), 1.1), ('rim', (-0.2, -0.9, -0.35), 2.2)):
    l = bpy.data.lights.new(nm, 'SUN')
    l.energy, l.angle = e, math.radians(12)
    o = bpy.data.objects.new(nm, l)
    o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler()
    o.parent = rig
    sc.collection.objects.link(o)
cd = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
W, H = map(int, res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
cd.type = 'ORTHO'
cd.ortho_scale = max(size.z * 1.06, 1.25 * W / H * 1.0, size.z * 1.06)
cd.ortho_scale = size.z * 1.06 if W < H else size.x * 1.06
sc.render.engine = 'CYCLES'
sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.device = spp, True, 'CPU'
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = False
views = {'front': -90, 'side': 0, 'back': 90, 'q34': -55}          # camera azimuth in degrees (front = -Y)
for k, az in views.items():
    a = math.radians(az)
    d = Vector((math.cos(a), math.sin(a), 0.0))
    cam.location = c + d * 8
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    rig.rotation_euler = (0, 0, a + math.radians(90))               # lights travel with the camera
    sc.render.filepath = f'{prefix}_{k}.png'
    bpy.ops.render.render(write_still=True)
print('TURNAROUND done', name, 'faces', len(ob.data.polygons))
