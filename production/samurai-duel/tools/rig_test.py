"""Build a fighter's skeleton, skin the body and render test poses.

    python3 -I tools/rig_test.py ronin|oni [--samples N] [--tag NAME] [--proxy]
--proxy renders the watertight skin instead of the detailed body (fast check of the weights).
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from sd import core, mats, oni, rig, ronin, studio  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


ACTION = {   # turns about world axes, degrees: X = left-right, Y = front-back, Z = up
    "Spine1": (8, 0, 14), "Spine2": (4, 0, 10), "Head": (0, 0, -18),
    "LeftArm": (0, 62, 0), "LeftForeArm": (0, 0, -75), "RightArm": (0, -48, -30), "RightForeArm": (0, 0, 95),
    "LeftUpLeg": (-42, 0, 8), "LeftLeg": (62, 0, 0), "RightUpLeg": (22, 0, -6), "RightLeg": (28, 0, 0),
}
FIST = {}
for s_, sg in (("Left", 1), ("Right", -1)):
    for f in ("Index", "Middle", "Ring", "Pinky"):
        for k, a in ((1, 62), (2, 78), (3, 55)):
            FIST[f"{s_}Hand{f}{k}"] = (0, sg * a, 0)
    FIST[f"{s_}HandThumb1"] = (0, sg * 20, sg * 25)
    FIST[f"{s_}HandThumb2"] = (0, sg * 25, sg * 30)
    FIST[f"{s_}HandThumb3"] = (0, sg * 20, sg * 30)


def main():
    who = sys.argv[1]
    src = oni if who == "oni" else ronin
    n = int(arg("--samples", 24))
    sc = core.reset_scene()
    col = core.collection(who.upper())
    t0 = time.time()
    body, A = src.load_body(col)
    px = bpy.data.objects[A["proxy"]]
    col.objects.link(px)
    print(f"LOAD {time.time() - t0:.1f}s", flush=True)
    t0 = time.time()
    J, hands = rig.joints(who, px.data, body.data)
    arm = rig.armature(who.capitalize() + "_Rig", J, col)
    names, Wp, missing = rig.skin_proxy(arm, px)
    print(f"  proxy skinned: {len(names)} bones, {missing} of {len(px.data.vertices)} verts without weights, {time.time() - t0:.1f}s", flush=True)
    t0 = time.time()
    use_proxy = "--proxy" in sys.argv
    if use_proxy:
        body.hide_render = True
        core.set_mat(px, mats.clay())
    else:
        rig.skin_body(arm, body, px, names, Wp, J, hands)
        px.hide_render = True
        print(f"  body skinning {time.time() - t0:.1f}s", flush=True)
    studio.world(sc, strength=0.3)
    studio.floor(sc, 0.0)
    tag = arg("--tag", "", 1, str)
    out = os.path.join(core.OUT, "stage3", f"rig_{who}{tag}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    H = src.HEIGHT
    t0 = time.time()
    rig.pose(arm, ACTION)
    studio.turnaround(sc, out + "_action.png", (0, -0.1, H * 0.5), H * 1.05, width=1.9, azimuths=(0, 60, 180, 270), size=(640, 720), samples=n)
    if not use_proxy:
        rig.rest_pose(arm)
        rig.pose(arm, FIST)
        hx = abs(J["LeftHand"][0]) + 0.1
        studio.turnaround(sc, out + "_fistL.png", (hx, 0, J["LeftHand"][2] - 0.03), 0.42, azimuths=(0, 180), size=(640, 480), samples=n, elevation=25)
        studio.turnaround(sc, out + "_fistR.png", (-hx, 0, J["RightHand"][2] - 0.03), 0.42, azimuths=(0, 180), size=(640, 480), samples=n, elevation=25)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")


main()
