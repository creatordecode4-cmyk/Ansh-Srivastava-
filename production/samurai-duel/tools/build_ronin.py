"""Cut the Ronin out of the Tripo model and render a studio turnaround of what is kept.

    python3 -I tools/build_ronin.py [--samples N] [--tag NAME]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sd import core, ronin, studio  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def main():
    sc = core.reset_scene()
    t0 = time.time()
    body, anchors = ronin.load_body(rebuild="--rebuild" in sys.argv)
    print("ANCHORS", anchors)
    print(f"BUILD {time.time() - t0:.1f}s")
    studio.world(sc, strength=0.55)
    studio.floor(sc, 0.0)
    tag = arg("--tag", "", 1, str)
    out = os.path.join(core.OUT, "stage2", f"ronin_body{tag}.png")
    t0 = time.time()
    n = int(arg("--samples", 32))
    if "--zoom" in sys.argv:        # close looks at the places that were cut
        studio.turnaround(sc, out.replace(".png", "_head.png"), (0, 0, 1.72), 0.62, azimuths=(0, 60, 180, 300), size=(560, 560), samples=n)
        studio.turnaround(sc, out.replace(".png", "_back.png"), (0, 0, 1.38), 0.95, azimuths=(180, 135, 225), size=(620, 620), samples=n)
        studio.turnaround(sc, out.replace(".png", "_hips.png"), (0, 0, 0.98), 0.85, azimuths=(0, 90, 180, 270), size=(560, 560), samples=n)
        studio.turnaround(sc, out.replace(".png", "_sides.png"), (0, 0, 0.95), 0.62, azimuths=(90, 270, 300), size=(760, 760), samples=n)
    else:
        studio.turnaround(sc, out, (0, 0, ronin.HEIGHT * 0.52), ronin.HEIGHT * 1.04, width=2.1, size=(640, 640), samples=n)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")


main()
