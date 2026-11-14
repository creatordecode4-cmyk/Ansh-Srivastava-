"""Render a deformation test pose of the rigged characters. python3 scripts/pose_test.py <rigged.blend> <out_prefix>"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import posing as P
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
prefix = sys.argv[2]
sc = bpy.context.scene
w = bpy.data.worlds.new('studio'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.19, 0.19, 0.21, 1)
rigl = bpy.data.objects.new('lights', None); sc.collection.objects.link(rigl)
for nm, d, e in (('key', (0.45, 0.75, -0.5), 3.2), ('fill', (-0.8, 0.45, -0.25), 1.1), ('rim', (-0.2, -0.9, -0.35), 2.2)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy, l.angle = e, math.radians(12)
    o = bpy.data.objects.new(nm, l); o.rotation_euler = Vector(d).normalized().to_track_quat('-Z', 'Y').to_euler(); o.parent = rigl
    sc.collection.objects.link(o)
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.type, cd.ortho_scale = 'ORTHO', 2.25
sc.render.resolution_x, sc.render.resolution_y = 760, 900
sc.render.engine = 'CYCLES'; sc.cycles.samples = 16; sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
for name in ('Oni', 'Ronin'):
    rig = bpy.data.objects[name + '_Rig']
    P.pose(rig, P.TEST_POSE)
    for ob in sc.objects:
        if ob.type in ('MESH', 'ARMATURE'):
            ob.hide_render = not ob.name.startswith(name)
    for k, az in (('front', -90), ('q34', -40), ('back', 110)):
        a = math.radians(az); d = Vector((math.cos(a), math.sin(a), 0.0))
        cam.location = Vector((0, 0, 1.02)) + d * 8
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        rigl.rotation_euler = (0, 0, a + math.radians(90))
        sc.render.filepath = f'{prefix}_{name}_{k}.png'
        bpy.ops.render.render(write_still=True)
    print('POSETEST', name)
