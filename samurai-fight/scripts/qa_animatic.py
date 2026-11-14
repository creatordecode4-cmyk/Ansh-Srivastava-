"""Numeric checks on the built animatic: planted-foot sliding and blade-to-blade distance on contact frames.
python3 scripts/qa_animatic.py build/animatic.blend"""
import bpy, sys, numpy as np
from mathutils import Vector
from mathutils.geometry import intersect_line_line
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
sc = bpy.context.scene
for o in bpy.data.objects:                      # bones and controls only: no mesh deformation needed here
    if o.type == 'MESH':
        for m in o.modifiers:
            m.show_viewport = False
OK, RR, RL = 'Oni_Katana', 'Ronin_Katana_R', 'Ronin_Katana_L'
feet = {n: {s: [] for s in 'LR'} for n in ('Oni', 'Ronin')}
blades = {k: [] for k in (OK, RR, RL)}
rest_h = {n: {s: None for s in 'LR'} for n in ('Oni', 'Ronin')}
for n in ('Oni', 'Ronin'):
    rig = bpy.data.objects[n + '_Rig']
    for s, side in (('L', 'Left'), ('R', 'Right')):
        rest_h[n][s] = rig.data.bones[side + 'Foot'].head_local.z
for f in range(1, 721):
    sc.frame_set(f)
    for n in feet:
        for s in 'LR':
            feet[n][s].append(bpy.data.objects[f'{n}_FOOT_{s}'].matrix_world.translation.copy())
    for k in blades:
        M = bpy.data.objects[k].matrix_world
        blades[k].append((M @ Vector((0, 0, 0.03)), M @ Vector((0, 0, 0.74))))


def seg_dist(a0, a1, b0, b1):
    """Closest distance between two segments."""
    a0, a1, b0, b1 = map(np.array, (a0, a1, b0, b1))
    u, v, w = a1 - a0, b1 - b0, a0 - b0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    D = a * c - b * b
    s = np.clip((b * e - c * d) / D, 0, 1) if D > 1e-9 else 0.0
    t = np.clip((b * s + e) / c, 0, 1)
    s = np.clip((b * t - d) / a, 0, 1)
    return float(np.linalg.norm((a0 + s * u) - (b0 + t * v)))


# intentional slides (frames) declared by the choreography
SLIDES = {'Oni': [(392, 420)], 'Ronin': [(289, 297), (310, 316), (330, 336), (350, 356), (540, 552)]}
PIVOTS = {'Ronin': [(366, 384)]}
for n in feet:
    worst, where, nplanted = 0.0, None, 0
    for s in 'LR':
        P = feet[n][s]
        for i in range(1, 720):
            fr = i + 1
            if P[i].z < rest_h[n][s] + 0.003 and P[i - 1].z < rest_h[n][s] + 0.003:
                if any(a <= fr <= b for a, b in SLIDES.get(n, [])):
                    continue
                nplanted += 1
                d = (P[i].xy - P[i - 1].xy).length
                if d > worst:
                    worst, where = d, (s, fr)
    print(f'QA {n}: planted-foot frames checked {nplanted}; worst slide per frame outside declared skids: {worst * 100:.2f} cm at {where}')
CONTACTS = [(270, 'slow-motion clash'), (308, 'overhead 1'), (328, 'overhead 2'), (348, 'overhead 3'), (383, 'spin slash block'), (450, 'exchange 1'), (466, 'exchange 2'), (482, 'exchange 3')]
for fr, label in CONTACTS:
    o = blades[OK][fr - 1]
    d = {k: seg_dist(o[0], o[1], blades[k][fr - 1][0], blades[k][fr - 1][1]) for k in (RR, RL)}
    print(f'QA contact f{fr} {label}: Oni blade to Ronin R {d[RR] * 100:.1f} cm, to Ronin L {d[RL] * 100:.1f} cm')
