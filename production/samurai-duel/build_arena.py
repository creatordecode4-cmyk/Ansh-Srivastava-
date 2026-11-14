"""Build the arena and render Stage 1 passes.

    python3 build_arena.py [--fast] [--save] [--pass beauty clay topdown] [--size W H] [--samples N]
                           [--no-fog] [--no-particles] [--tag NAME] [--exposure EV] [--anim FRAMES] [--push METRES]

--fast    lighter geometry for quick look-dev (low-res roofs, fewer blossoms)
--save    write out/arena.blend
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from sd import arena, core, render  # noqa: E402


def arg(flag, default=None, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def passes():
    if "--pass" not in sys.argv:
        return []
    i = sys.argv.index("--pass")
    out = []
    for v in sys.argv[i + 1:]:
        if v.startswith("--"):
            break
        out.append(v)
    return out


def main():
    fast = "--fast" in sys.argv
    W, H = arg("--size", [960, 540], 2, int)
    samples = int(arg("--samples", 48))
    tag = arg("--tag", "", 1, str)
    sc, cams = arena.build(detail=not fast, particles="--no-particles" not in sys.argv)
    print("TRIS", core.tri_count())
    if "--no-fog" in sys.argv:
        bpy.data.objects["FOG_Volume"].hide_render = True
    render.setup(sc, W, H, samples, 0.03)
    sc.view_settings.exposure = arg("--exposure", 0.4)
    if "--no-bloom" not in sys.argv:
        render.bloom(sc)
    if "--save" in sys.argv:
        path = os.path.join(core.OUT, "arena.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print("SAVED", path)
    for p in passes():
        t0 = time.time()
        out = os.path.join(core.OUT, "stage1", f"{p}{tag}.png")
        render.render_pass(sc, cams, p, out)
        print(f"RENDER {p} -> {out}: {time.time() - t0:.1f}s", flush=True)
    n = arg("--anim", None, 1, int)
    if n:   # short motion test: slow push-in on the hero camera, frames rendered in order so particles simulate
        from mathutils import Vector
        cam = cams["hero"]
        sc.camera = cam
        fwd = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        cam.keyframe_insert("location", frame=1)
        cam.location = cam.location + fwd * arg("--push", 0.8)
        cam.keyframe_insert("location", frame=n)
        sc.frame_start, sc.frame_end = 1, n
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = 0.5
        d = os.path.join(core.OUT, "stage1", f"anim{tag}")
        os.makedirs(d, exist_ok=True)
        sc.render.filepath = os.path.join(d, "f_")
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        print(f"ANIM {n} frames -> {d}: {time.time() - t0:.1f}s ({(time.time() - t0) / n:.1f}s/frame)", flush=True)


main()
