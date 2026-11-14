"""Import a GLB, print stats and render front / side / back / 3-4 views.  python3 scripts/inspect_glb.py assets/glb/x.glb tag"""
import bpy, sys, os, math
from mathutils import Vector
path, tag = sys.argv[1], sys.argv[2]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
bpy.context.view_layer.update()
lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in bpy.data.objects:
    print('OBJ', o.type, o.name, 'parent', o.parent.name if o.parent else None, 'verts', len(o.data.vertices) if o.type == 'MESH' else '-',
          'faces', len(o.data.polygons) if o.type == 'MESH' else '-', 'mats', [m.name for m in o.data.materials] if o.type == 'MESH' else '-')
    if o.type == 'MESH':
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    if o.type == 'ARMATURE':
        print('  BONES', len(o.data.bones), [b.name for b in o.data.bones][:40])
print('BOUNDS lo', tuple(round(v, 3) for v in lo), 'hi', tuple(round(v, 3) for v in hi), 'size', tuple(round(v, 3) for v in hi - lo))
for im in bpy.data.images:
    print('IMG', im.name, tuple(im.size))
print('ACTIONS', [a.name for a in bpy.data.actions])
sc = bpy.context.scene
ctr = (lo + hi) / 2; size = max(hi - lo)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.6, 0.62, 0.66, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
L = bpy.data.lights.new('s', 'SUN'); L.energy = 2.5; lo_ = bpy.data.objects.new('s', L); sc.collection.objects.link(lo_)
cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = size * 1.12
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'CYCLES'; sc.cycles.samples = 12; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 420, 420
sc.view_settings.view_transform = 'Standard'
for nm, ang in (('front', 0), ('side', 90), ('back', 180), ('34', 40)):
    a = math.radians(ang)
    cam.location = ctr + Vector((math.sin(a), -math.cos(a), 0.08)) * size * 3
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    lo_.rotation_euler = cam.rotation_euler
    sc.render.filepath = os.path.join(ROOT, 'previews', f't_{tag}_{nm}.png')
    bpy.ops.render.render(write_still=True)
