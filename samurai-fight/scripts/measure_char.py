"""Print landmark measurements of a prepared T-pose character (metres, facing -Y).
python3 scripts/measure_char.py build/characters.blend Oni
"""
import bpy, sys, numpy as np
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
name = sys.argv[2]
me = bpy.data.objects[name + '_Body'].data
co = np.empty(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
x, y, z = co[:, 0], co[:, 1], co[:, 2]
print(f'M {name} bbox', np.round(co.min(0), 3), np.round(co.max(0), 3))
# torso/leg cross-sections: width (x), depth (y) by height, restricted to the body column
for h in np.arange(0.05, 2.0, 0.1):
    s = (np.abs(z - h) < 0.02)
    c = s & (np.abs(x) < 0.45)
    if c.sum() < 20:
        continue
    print(f'M z={h:.2f}  x[{x[c].min():+.2f},{x[c].max():+.2f}]  y[{y[c].min():+.2f},{y[c].max():+.2f}]  ymid {0.5*(y[c].min()+y[c].max()):+.3f}  n={int(c.sum())}')
# arms: cross-section by |x|
for side, sg in (('R(-x)', -1), ('L(+x)', 1)):
    for d in np.arange(0.20, 1.0, 0.08):
        s = (np.abs(sg * x - d) < 0.015) & (z > 1.1)
        if s.sum() < 10:
            continue
        print(f'M arm {side} |x|={d:.2f}  z[{z[s].min():.2f},{z[s].max():.2f}] zmid {0.5*(z[s].min()+z[s].max()):.3f}  y[{y[s].min():+.2f},{y[s].max():+.2f}] ymid {0.5*(y[s].min()+y[s].max()):+.3f} n={int(s.sum())}')
# feet
for side, sg in (('R(-x)', -1), ('L(+x)', 1)):
    s = (z < 0.10) & (sg * x > 0)
    print(f'M foot {side} x[{x[s].min():+.2f},{x[s].max():+.2f}] xmid {np.median(x[s]):+.3f}  y[{y[s].min():+.2f},{y[s].max():+.2f}]')
