"""Render one Stage 2 prop under studio light.

    python3 tools/s2_prop.py kasa|kasa_split|kasa_under [--az A] [--el E] [--size W H] [--samples N] [--tag T]
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sd import core, render, studio  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def main():
    which = sys.argv[1]
    W, H = arg("--size", [900, 700], 2, int)
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB")
    t0 = time.time()
    az, el, floor_z = -25.0, 22.0, None
    if which.startswith("kasa"):
        from sd import kasa
        k = kasa.build(lib)
        if which == "kasa_split":
            k["whole"].hide_render = True
            n = Vector(k["whole"]["cut_normal"])
            for h, s in zip(k["halves"], (-1, 1)):
                h.location = n * s * 0.05
                h.rotation_euler = (0, math.radians(14) * s, 0)
        else:
            for h in k["halves"]:
                h.hide_render = True
        if which == "kasa_under":
            el = -28.0
        else:
            floor_z = -0.24
    print(f"BUILD {which}: {time.time() - t0:.2f}s tris {core.tri_count()}")
    bpy.context.view_layer.update()
    pts = []
    for inst in bpy.context.evaluated_depsgraph_get().object_instances:
        o = inst.object
        if o.type == "MESH" and not o.hide_render:
            pts += [inst.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr, size = (lo + hi) / 2, (hi - lo).length
    studio.world(sc, strength=0.6)
    studio.key(sc, ctr, azimuth=-40, elevation=50, distance=size * 2.2, power=60 * size * size * 4, size=size * 1.2)
    if floor_z is not None:
        studio.floor(sc, floor_z)
    render.setup(sc, W, H, int(arg("--samples", 64)), 0.03)
    sc.view_settings.exposure = 0.0
    cam = studio.camera(sc, ctr, arg("--az", az), arg("--el", el), size * arg("--dist", 2.6), lens=70)
    out = os.path.join(core.OUT, "stage2", f"prop_{which}{arg('--tag', '', 1, str)}.png")
    t0 = time.time()
    render.still(sc, out, cam)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")


main()
