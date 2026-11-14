"""STAGE 3 base scene: arena + both rigged fighters with IK controls, no animation yet.
  python3 scripts/fight_base.py --tag preview --ratio 0.10     (light meshes, for animation previews)
  python3 scripts/fight_base.py --tag final   --ratio 0.5
Writes fight_base_<tag>.blend
"""
import bpy, os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, fighters
from lib import col, ROOT
ap = argparse.ArgumentParser(); ap.add_argument('--tag', default='preview'); ap.add_argument('--ratio', type=float, default=0.10)
a = ap.parse_args()
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'arena.blend'))
fighters.build_oni(col('COL_Oni'), a.ratio)
fighters.build_ronin(col('COL_Ronin'), a.ratio)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, f'fight_base_{a.tag}.blend'))
print('saved', f'fight_base_{a.tag}.blend')
