"""Import a GLB, print its stats and render a 4-view contact sheet.
python3 -I inspect_glb.py <file.glb> <out.png> [--spp 16]
"""
import bpy, sys, math, os
from mathutils import Vector

path, out = sys.argv[1], sys.argv[2]
spp = int(sys.argv[sys.argv.index('--spp') + 1]) if '--spp' in sys.argv else 16
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
sc = bpy.context.scene
meshes = [o for o in sc.objects if o.type == 'MESH']
print('STAT file', os.path.basename(path))
print('STAT objects', [(o.name, o.type) for o in sc.objects][:12], 'armatures', sum(o.type == 'ARMATURE' for o in sc.objects))
lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in meshes:
    me = o.data
    print('STAT mesh', o.name, 'verts', len(me.vertices), 'faces', len(me.polygons), 'mats', [m.name for m in me.materials],
          'uv', [u.name for u in me.uv_layers], 'vcol', len(me.color_attributes), 'rot', [round(a, 2) for a in o.rotation_euler], 'scale', [round(s, 3) for s in o.scale])
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
print('STAT bbox lo', [round(v, 3) for v in lo], 'hi', [round(v, 3) for v in hi], 'size', [round(v, 3) for v in (hi - lo)])
for im in bpy.data.images:
    print('STAT image', im.name, im.size[:], im.colorspace_settings.name)
for m in bpy.data.materials:
    if m.node_tree:
        b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if b:
            print('STAT material', m.name, {k: (b.inputs[k].is_linked, round(b.inputs[k].default_value, 2) if not b.inputs[k].is_linked and k != 'Normal' else '-')
                                           for k in ('Metallic', 'Roughness', 'Normal')}, 'basecolor linked', b.inputs['Base Color'].is_linked)

# --- 4-view contact sheet (front, right, back, 3/4), neutral studio light
c, size = (lo + hi) / 2, (hi - lo)
H = max(size)
sc.render.engine = 'CYCLES'
sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.device = spp, True, 'CPU'
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('w')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.22, 0.22, 0.24, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
for nm, d, e in (('key', (-0.5, -0.8, -0.5), 3.5), ('fill', (0.8, -0.4, -0.3), 1.2), ('back', (0.2, 0.9, -0.4), 2.0)):
    l = bpy.data.lights.new(nm, 'SUN')
    l.energy, l.angle = e, math.radians(15)
    ob = bpy.data.objects.new(nm, l)
    ob.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(ob)
cd = bpy.data.cameras.new('cam')
cd.type, cd.ortho_scale = 'ORTHO', H * 1.12
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 560, 760
cd.ortho_scale = max(size.z * 1.08, max(size.x, size.y) * 1.08 * 760 / 560)
views = {'front': (0, -1, 0), 'right': (1, 0, 0), 'back': (0, 1, 0), 'q34': (0.7, -0.7, 0.25)}
base = os.path.splitext(out)[0]
for k, d in views.items():
    d = Vector(d).normalized()
    cam.location = c + d * (H * 4)
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{base}_{k}.png'
    bpy.ops.render.render(write_still=True)
print('STAT rendered', base)
