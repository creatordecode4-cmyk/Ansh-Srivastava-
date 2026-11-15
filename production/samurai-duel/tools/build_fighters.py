"""Assemble a fighter and render studio turnarounds.

    python3 -I tools/build_fighters.py ronin [--zoom] [--samples N] [--tag NAME] [--rebuild] [--save]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from sd import core, fighters, ronin, studio  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def main():
    who = sys.argv[1]
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB", hide_render=True)
    col = core.collection(who.upper())
    t0 = time.time()
    if "--rebuild" in sys.argv:
        os.path.exists(ronin.CACHE) and os.remove(ronin.CACHE)
    parts = fighters.ronin(lib, col)
    print(f"BUILD {who}: {time.time() - t0:.1f}s, tris {core.tri_count()}")
    studio.world(sc, strength=0.55)
    studio.floor(sc, 0.0)
    n = int(arg("--samples", 32))
    tag = arg("--tag", "", 1, str)
    out = os.path.join(core.OUT, "stage2", f"{who}{tag}.png")
    H = ronin.HEIGHT
    t0 = time.time()
    if "--zoom" in sys.argv:
        studio.turnaround(sc, out.replace(".png", "_head.png"), (0, 0, 1.72), 0.75, azimuths=(0, 60, 180, 300), size=(560, 560), samples=n)
        studio.turnaround(sc, out.replace(".png", "_back.png"), (0, 0, 1.25), 1.5, azimuths=(180, 135, 225), size=(640, 760), samples=n)
    elif "--hero" in sys.argv:      # larger frames for a preview sheet
        studio.turnaround(sc, out, (0, 0, H * 0.54), H * 1.12, width=2.0, azimuths=(0, 40, 180, 215), size=(900, 900), samples=n)
    else:
        studio.turnaround(sc, out, (0, 0, H * 0.54), H * 1.12, width=2.0, size=(640, 640), samples=n)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")
    if "--save" in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(core.OUT, f"{who}.blend"))


main()
