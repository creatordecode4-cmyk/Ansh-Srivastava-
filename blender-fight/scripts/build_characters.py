"""STAGE 2 - build both fighters into characters.blend and render turnaround sheets.
  python3 scripts/build_characters.py [--views front,34,side,back] [--res 480x860] [--spp 40] [--only oni|ronin] [--tpose]
"""
import bpy, os, sys, math, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, charlib, characters
from lib import col, flat, ROOT
from mathutils import Vector
R = math.radians

ap = argparse.ArgumentParser()
ap.add_argument('--views', default='front,34,side,back'); ap.add_argument('--res', default='480x860')
ap.add_argument('--spp', type=int, default=40); ap.add_argument('--only', default='')
ap.add_argument('--tpose', action='store_true'); ap.add_argument('--norender', action='store_true')
ap.add_argument('--tag', default='t'); ap.add_argument('--close', action='store_true')
a = ap.parse_args()

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C_oni, C_ronin, C_stage = col('COL_Oni'), col('COL_Ronin'), col('COL_Studio')
chars = {}
if a.only in ('', 'ronin'):
    chars['ronin'] = (characters.build_ronin(C_ronin), C_ronin)
if a.only in ('', 'oni'):
    chars['oni'] = (characters.build_oni(C_oni), C_oni)

if not a.tpose:
    for name, (ch, _) in chars.items():
        arm = ch['rig']
        charlib.pose(arm, [('upper_arm.L', 'Y', 64), ('upper_arm.R', 'Y', -64), ('forearm.L', 'Y', 12), ('forearm.R', 'Y', -12),
                           ('fingers1.L', 'Y', 25), ('fingers1.R', 'Y', -25), ('fingers2.L', 'Y', 30), ('fingers2.R', 'Y', -30),
                           ('thigh.L', 'Y', -4), ('thigh.R', 'Y', 4)])

# studio
st = lib.MB(); st.cube((30, 30, 0.1), (0, 0, -0.05)); st.cube((30, 0.1, 14), (0, 6, 7))
st.obj('Studio_Backdrop', [flat('MAT_Backdrop', (0.20, 0.20, 0.21), 0.9)], C_stage)
w = bpy.data.worlds.new('WORLD_Studio'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.5, 0.52, 0.56, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.35
def area(name, loc, target, size, energy, color=(1, 1, 1)):
    L = bpy.data.lights.new(name, 'AREA'); L.size, L.energy, L.color = size, energy, color
    o = bpy.data.objects.new(name, L); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); C_stage.objects.link(o); return o
key = area('LGT_Key', (-3.0, -4.5, 3.8), (0, 0, 1.1), 3.0, 380)
fill = area('LGT_Fill', (4.0, -3.5, 1.8), (0, 0, 1.0), 4.0, 120, (0.8, 0.88, 1.0))
rim = area('LGT_Rim', (1.5, 4.5, 3.2), (0, 0, 1.3), 2.5, 420, (1.0, 0.92, 0.85))
pivot = bpy.data.objects.new('LightPivot', None); C_stage.objects.link(pivot)
for o in (key, fill, rim):
    o.parent = pivot

cd = bpy.data.cameras.new('CAM_Sheet'); cd.lens = 70
cam = bpy.data.objects.new('CAM_Sheet', cd); C_stage.objects.link(cam); sc.camera = cam
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.spp; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 5
sc.view_settings.view_transform = 'AgX'
w_, h_ = map(int, a.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y = w_, h_
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'characters.blend'))
print('built', {k: len(c.all_objects) for k, (_, c) in chars.items()})

ANG = {'front': 0, '34': 35, 'side': 90, 'back': 180, '34b': 215}
if not a.norender:
    for name, (ch, c) in chars.items():
        for other, (_, oc) in chars.items():
            oc.hide_render = other != name
        for v in a.views.split(','):
            ang = R(ANG[v])
            tgt = Vector((0, 0, (1.86 if name == 'oni' else 1.76) if a.close else 1.10))
            dist = 2.4 if a.close else 5.3
            cam.location = tgt + Vector((math.sin(ang) * dist, -math.cos(ang) * dist, 0.12 if a.close else 0.25))
            cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
            pivot.rotation_euler = (0, 0, ang)
            sc.render.filepath = os.path.join(ROOT, 'previews', f'{a.tag}_{name}_{v}.png')
            t = time.time(); bpy.ops.render.render(write_still=True)
            print('RENDER', name, v, '%.1fs' % (time.time() - t))
