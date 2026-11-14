"""STAGE 2 check - both Tripo fighters standing in the arena (saves fight_scene.blend and renders a still).
  python3 scripts/render_standoff.py --res 1280x720 --spp 64 --out previews/stage2_standoff.png
"""
import bpy, os, sys, math, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, charlib, fighters
from lib import col, ROOT
from mathutils import Vector
R = math.radians
ap = argparse.ArgumentParser()
ap.add_argument('--res', default='960x540'); ap.add_argument('--spp', type=int, default=32)
ap.add_argument('--out', default='previews/t_standoff.png'); ap.add_argument('--nofx', action='store_true')
a = ap.parse_args()

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'arena.blend'))
sc = bpy.context.scene
oni = fighters.build_oni(col('COL_Oni'))
ronin = fighters.build_ronin(col('COL_Ronin'))
for ch in (oni, ronin):
    charlib.pose(ch['rig'], [('upper_arm.L', 'Y', 64), ('upper_arm.R', 'Y', -64), ('forearm.L', 'Y', 12), ('forearm.R', 'Y', -12),
                             ('fingers1.L', 'Y', 25), ('fingers1.R', 'Y', -25), ('fingers2.L', 'Y', 30), ('fingers2.R', 'Y', -30)])
    fighters.draw_swords(ch, False)
oni['rig'].location, oni['rig'].rotation_euler = (-1.75, 1.0, 0), (0, 0, R(68))
ronin['rig'].location, ronin['rig'].rotation_euler = (1.75, 1.5, 0), (0, 0, R(-112))

cd = bpy.data.cameras.new('CAM_Standoff'); cd.lens, cd.sensor_width = 35, 36
cam = bpy.data.objects.new('CAM_Standoff', cd); bpy.data.collections['COL_Cameras'].objects.link(cam)
cam.location = (0.2, -5.6, 0.8)
tgt = Vector((0.0, 1.3, 1.9))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
cd.dof.use_dof, cd.dof.focus_distance, cd.dof.aperture_fstop = True, 6.9, 2.8
sc.camera = cam
# character lights: cold key from camera-left, red kicker from behind
def spot(name, loc, target, energy, color, size=1.2, blend=0.6, angle=50):
    L = bpy.data.lights.new(name, 'SPOT'); L.energy, L.color, L.shadow_soft_size, L.spot_blend, L.spot_size = energy, color, size, blend, R(angle)
    o = bpy.data.objects.new(name, L); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.data.collections['COL_Lights'].objects.link(o)
spot('LGT_Char_Key', (-5.0, -7.0, 5.5), (0, 1.3, 1.2), 3200, (0.62, 0.75, 1.0))
spot('LGT_Char_Rim', (0.5, 8.5, 5.5), (0, 1.3, 1.3), 2200, (1.0, 0.10, 0.05), 0.8, angle=32)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'fight_scene.blend'))

w, h = map(int, a.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.cycles.samples = a.spp
sc.render.use_motion_blur = False
emit = bpy.data.objects.get('FX_Emitter')
if a.nofx:
    for m in emit.modifiers: m.show_render = False
else:
    for f in range(-800, 2): sc.frame_set(f)
sc.frame_set(1)
sc.render.filepath = os.path.join(ROOT, a.out)
t = time.time(); bpy.ops.render.render(write_still=True)
print('RENDER standoff %s %dspp: %.1fs' % (a.res, a.spp, time.time() - t))
