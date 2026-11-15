"""Render a fighter's sword and scabbard laid out like the parts sheet, plus close-ups.

    python3 tools/weapon_test.py oni|ronin [--size W H] [--samples N] [--close] [--tag NAME]
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sd import core, render, studio, weapons  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def lay_flat(ob, z):
    """Sheet layout: length along world X, the +X flat toward the camera (-Y), edge down."""
    ob.rotation_euler = (0, 0, -math.pi / 2)
    ob.location = (0, 0, z)


def main():
    who = sys.argv[1]
    spec = weapons.ONI if who == "oni" else weapons.RONIN
    W, H = arg("--size", [1600, 620], 2, int)
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB")
    t0 = time.time()
    k, ki = weapons.katana(lib, f"PROP_Katana_{spec['tag']}", spec)
    s, si = weapons.scabbard(lib, f"PROP_Saya_{spec['tag']}", spec)
    print(f"BUILD {time.time() - t0:.1f}s tris {core.tri_count()}")
    for ob, z in ((k, 0.17), (s, -0.10)):
        lay_flat(ob, z)
    for nm in ki["tassels"] + si["tassels"]:                 # tassels were placed in sword space: carry them along
        t = bpy.data.objects[nm]
        parent = k if nm in ki["tassels"] else s
        local = Vector(t.location)
        t.location = (local.y, -local.x, local.z + parent.location.z)
    studio.world(sc, strength=0.45)
    studio.key(sc, (0.3, 0, 0.05), azimuth=-25, elevation=55, distance=2.2, power=150, size=1.4)
    # long soft cards on the camera side, above and below, so the polished steel has something to mirror
    studio.key(sc, (0.3, 0, 0.05), azimuth=0, elevation=-22, distance=2.4, power=22, size=2.6, name="LGT_CardLow")
    studio.key(sc, (0.3, 0, 0.05), azimuth=0, elevation=18, distance=2.4, power=14, size=2.6, name="LGT_CardHigh")
    render.setup(sc, W, H, int(arg("--samples", 96)), 0.02)
    sc.view_settings.exposure = 0.0
    ctr = Vector(((spec["blade"] - spec["grip"]) / 2, 0, 0.0))
    span = spec["blade"] + spec["grip"] + 0.12
    cam = studio.camera(sc, ctr, 0, 0, 6.0, ortho=span)
    tag = arg("--tag", "", 1, str)
    out = os.path.join(core.OUT, "stage2", f"weapons_{who}{tag}.png")
    t0 = time.time()
    render.still(sc, out, cam)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")
    if "--close" in sys.argv:
        sc.render.resolution_x, sc.render.resolution_y = 1400, 700
        for name, c, scale in (("guard", Vector((-0.03, 0, 0.14)), 0.42), ("point", Vector((spec["blade"] - 0.17, 0, 0.19)), 0.40),
                               ("saya_mouth", Vector((0.12, 0, -0.12)), 0.46), ("saya_end", Vector((spec["blade"] - 0.17, 0, -0.07)), 0.46)):
            cam.data.ortho_scale = scale
            studio.aim(cam, c, 0, 0, 6.0)
            p = os.path.join(core.OUT, "stage2", f"weapons_{who}{tag}_{name}.png")
            render.still(sc, p, cam)
            print("RENDER", p)


main()
