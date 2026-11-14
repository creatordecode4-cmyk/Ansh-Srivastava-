"""Stage 3a check: both rigged characters in their guard stances, facing each other in the arena.
python3 scripts/build_standoff.py  ->  build/standoff.blend  (needs arena.blend + characters_ctrl.blend)
"""
import bpy, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
B = os.path.join(os.path.dirname(HERE), 'build')
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, 'arena.blend'))
import stances as S
from mathutils import Vector
sc = bpy.context.scene
with bpy.data.libraries.load(os.path.join(B, 'characters_ctrl.blend'), link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c.startswith('CHAR_')]
for c in dst.collections:
    sc.collection.children.link(c)
bpy.context.view_layer.update()
for name in ('Oni', 'Ronin'):
    S.apply(name, S.STANCES[name + '_guard'])
# the fight line runs along X through the court centre (0, 1): Oni on the west side, Ronin on the east
for name, x, rz in (('Oni', -1.9, 90), ('Ronin', 1.9, -90)):
    root = bpy.data.objects[name + '_Root']
    root.location, root.rotation_euler = (x, 1.0, 0.0), (0, 0, math.radians(rz))
cd = bpy.data.cameras.new('CAM_Standoff')
cam = bpy.data.objects.new('CAM_Standoff', cd)
bpy.data.collections['CAMERAS'].objects.link(cam)
cam.location = (0.25, -5.3, 0.95)
cam.rotation_euler = (Vector((0.0, 1.0, 1.08)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
cd.lens, cd.dof.use_dof, cd.dof.focus_distance, cd.dof.aperture_fstop = 32.0, True, 6.3, 3.2
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(B, 'standoff.blend'))
print('STANDOFF built')
