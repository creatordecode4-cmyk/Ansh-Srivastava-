"""Cut the Oni out of the Tripo model and render a studio turnaround of what is kept.

    python3 -I tools/build_oni.py [--samples N] [--tag NAME] [--rebuild] [--zoom]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from sd import core, oni, studio  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def main():
    sc = core.reset_scene()
    t0 = time.time()
    body, anchors = oni.load_body(rebuild="--rebuild" in sys.argv)
    print("ANCHORS", anchors)
    print(f"BUILD {time.time() - t0:.1f}s")
    studio.world(sc, strength=0.5)
    studio.floor(sc, 0.0)
    n = int(arg("--samples", 32))
    out = os.path.join(core.OUT, "stage2", f"oni_body{arg('--tag', '', 1, str)}.png")
    t0 = time.time()
    if "--zoom" in sys.argv:
        studio.turnaround(sc, out.replace(".png", "_hips.png"), (0, 0, 1.2), 0.95, azimuths=(0, 60, 90, 150, 180), size=(560, 560), samples=n, exposure=-0.4)
    else:
        studio.turnaround(sc, out, (0, 0, oni.HEIGHT * 0.5), oni.HEIGHT * 1.04, width=2.1, size=(640, 640), samples=n, exposure=-0.4)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")


main()
