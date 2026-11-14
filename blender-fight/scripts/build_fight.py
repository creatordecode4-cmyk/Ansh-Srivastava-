"""STAGE 3 - animate the fight: load fight_base_<tag>.blend, bake both fighters, cameras and sparks, save fight_scene_<tag>.blend
  python3 scripts/build_fight.py --tag preview
"""
import bpy, os, sys, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, fighters, anim, joints, choreo, shots, fx
from lib import col, ROOT
ap = argparse.ArgumentParser(); ap.add_argument('--tag', default='preview'); a = ap.parse_args()
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, f'fight_base_{a.tag}.blend'))
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 720
oni = anim.Fighter('Oni', fighters.collect('Oni'), joints.J_ONI, True)
ron = anim.Fighter('Ronin', fighters.collect('Ronin'), joints.J_RONIN, False)
EV = choreo.choreograph(oni, ron)
oni.bake(1, 720); ron.bake(1, 720)
SO = {f: oni.state(f) for f in range(1, 721)}
SR = {f: ron.state(f) for f in range(1, 721)}
shots.build_cameras(SO, SR, EV, bpy.data.collections['COL_Cameras'])
fx.build_sparks(EV, col('COL_FX_Sparks', bpy.data.collections['COL_FX']))
# report blade contact accuracy at every clash
for fe, P, s, ts in EV:
    best = 9.0
    for st in (SO[fe], SR[fe]):
        for k in ('R', 'L'):
            if 'tip_' + k in st:
                g, t = st['guard_' + k], st['tip_' + k]
                d = (t - g).normalized(); u = max(0.0, min((t - g).length, (P - g).dot(d)))
                best = min(best, (g + d * u - P).length)
    print(f'  clash f{fe}: nearest blade {best * 100:.1f} cm from the contact point')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, f'fight_scene_{a.tag}.blend'))
print('saved fight_scene_%s.blend in %.0fs' % (a.tag, time.time() - t0))
