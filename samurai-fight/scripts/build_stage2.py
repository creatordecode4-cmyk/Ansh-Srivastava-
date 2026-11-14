"""Stage 2: bring the prepared characters and the katanas into the arena for a scale and lighting check.
python3 scripts/build_stage2.py   ->  build/stage2.blend   (needs build/arena.blend and build/characters.blend)
"""
import bpy, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
B = os.path.join(ROOT, 'build')
bpy.ops.wm.open_mainfile(filepath=os.path.join(B, 'arena.blend'))
import weapons as W
from mathutils import Vector
sc = bpy.context.scene
with bpy.data.libraries.load(os.path.join(B, 'characters.blend'), link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c.startswith('CHAR_')]
for c in dst.collections:
    sc.collection.children.link(c)
oni, ronin = bpy.data.objects['Oni_Body'], bpy.data.objects['Ronin_Body']
# standoff marks on the court (fight centre is (0, 1)); the characters face each other along X
oni.location, oni.rotation_euler = (-3.2, 1.0, 0.0), (0, 0, math.radians(90))
ronin.location, ronin.rotation_euler = (3.2, 1.0, 0.0), (0, 0, math.radians(-90))
wc = bpy.data.collections.new('WEAPONS')
sc.collection.children.link(wc)
for nm, style, loc in (('Katana_Oni', 'Oni', (-2.2, 0.2, 0.0)), ('Katana_Ronin_R', 'Ronin', (2.2, 0.4, 0.0)), ('Katana_Ronin_L', 'Ronin', (2.3, 1.7, 0.0))):
    k = W.build_katana(wc, nm, style)
    # planted tip-down in the stone for the still (they move to the hands in Stage 3)
    k.location = (loc[0], loc[1], 0.70)
    k.rotation_euler = (math.radians(180 + 6), math.radians(4), math.radians(70))
cd = bpy.data.cameras.new('CAM_Standoff')
cam = bpy.data.objects.new('CAM_Standoff', cd)
bpy.data.collections['CAMERAS'].objects.link(cam)
cam.location = (0.3, -8.6, 1.35)
cam.rotation_euler = (Vector((0.0, 1.0, 1.2)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
cd.lens, cd.dof.use_dof, cd.dof.focus_distance, cd.dof.aperture_fstop = 38.0, True, 9.7, 4.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(B, 'stage2.blend'))
print('STAGE2 built')
