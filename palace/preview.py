"""Character-only preview sheet. python3 preview.py OUT.png clay|mat  frame:az[:dist[:height]] ...   (frame 0 = rest pose)"""
import bpy, os, sys, math, subprocess
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
out, mode, shots = sys.argv[1], sys.argv[2], sys.argv[3:]
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '_work', 'palace_char.blend'))
sc = bpy.context.scene; ch = set(bpy.data.collections['COL_Char'].all_objects)
for ob in sc.objects:
    if ob not in ch: ob.hide_render = True
arm = bpy.data.objects['CHR_Rig']
sc.render.engine = 'CYCLES'; c = sc.cycles; c.device = 'CPU'; c.samples = 20; c.use_denoising = True; c.max_bounces = 3
sc.render.resolution_x = 420; sc.render.resolution_y = 760; sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = 0
w = bpy.data.worlds.new('PW'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (.5, .52, .56, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = .7; sc.world = w
import bmesh
me = bpy.data.meshes.new('G'); bm = bmesh.new(); bmesh.ops.create_grid(bm, size=40); bm.to_mesh(me); g = bpy.data.objects.new('G', me); sc.collection.objects.link(g)
gm = bpy.data.materials.new('G'); gm.use_nodes = True; gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.3, .3, .3, 1); me.materials.append(gm)
sun = bpy.data.objects['LGT_Key_Sun']; sun.hide_render = True
ld = bpy.data.lights.new('K', 'SUN'); ld.energy = 3.5; ld.angle = .1; lo = bpy.data.objects.new('K', ld); sc.collection.objects.link(lo)
if mode == 'clay':
    m = bpy.data.materials.new('Clay'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.5, .5, .5, 1)
    sc.view_layers[0].material_override = m
cd = bpy.data.cameras.new('PC'); cd.lens = 60; cam = bpy.data.objects.new('PC', cd); sc.collection.objects.link(cam); sc.camera = cam
tmp = []
for i, s in enumerate(shots):
    p = s.split(':'); fr = int(p[0]); az = math.radians(float(p[1])); dist = float(p[2]) if len(p) > 2 else 5.6; hz = float(p[3]) if len(p) > 3 else 1.1
    if fr == 0: arm.data.pose_position = 'REST'; sc.frame_set(1); ctr = Vector((0, 0, hz)); head = 0
    else:
        arm.data.pose_position = 'POSE'; sc.frame_set(fr); bpy.context.view_layer.update()
        hm = arm.pose.bones['hips'].matrix; ctr = Vector((hm.translation.x, hm.translation.y, hz)); f = hm.to_3x3() @ Vector((0, 0, -1)); head = math.atan2(f.y, f.x)+math.pi/2
    a = az+head-math.pi/2   # az 0 = front view
    cam.location = ctr+Vector((math.cos(a)*dist, math.sin(a)*dist, .15)); d = ctr-cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    lo.rotation_euler = (Vector((math.cos(a+.9), math.sin(a+.9), .8))).to_track_quat('Z', 'Y').to_euler()
    fp = os.path.join(HERE, '_work', 'chk', 'pv_%d.png' % i); sc.render.filepath = fp; bpy.ops.render.render(write_still=True); tmp.append(fp)
cmd = ['ffmpeg', '-y', '-v', 'error']
for t in tmp: cmd += ['-i', t]
cmd += ['-filter_complex', 'hstack=inputs=%d' % len(tmp), out] if len(tmp) > 1 else [out]
subprocess.run(cmd, check=True)
