"""Render one prop on a neutral stage to check it against the reference sheet.

    python3 tools/prop_test.py <builder> [--clay] [--size W H] [--samples N] [--dist D] [--height Z]
builders: tiles, torii, lantern, lantern_broken, paper_lantern, banner, stairs, rocks, cherry, temple, corridor
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from sd import core, mats, render  # noqa: E402


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def stage(sc, clay):
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.7, 1) if clay else (0.035, 0.045, 0.07, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.6 if clay else 1.0
    def sun(name, rot, col, e):
        d = bpy.data.lights.new(name, "SUN")
        d.color, d.energy, d.angle = col, e, math.radians(4)
        o = bpy.data.objects.new(name, d)
        o.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(o)
    sun("key", (52, 0, 35), (1, 0.97, 0.92) if clay else (0.62, 0.75, 1.0), 3.0 if clay else 1.6)
    if not clay:
        sun("rim", (70, 0, 200), (1.0, 0.12, 0.06), 2.2)
    if "--neutral" in sys.argv:
        for o in sc.objects:
            if o.type == "LIGHT" and o.name == "key":
                o.data.color, o.data.energy = (1, 0.97, 0.93), 3.0
            if o.type == "LIGHT" and o.name == "rim":
                o.data.color, o.data.energy = (0.8, 0.85, 1.0), 1.0
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.55, 0.65, 1)


def main():
    which = sys.argv[1]
    clay = "--clay" in sys.argv
    W, H = arg("--size", [960, 720], 2, int)
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB")
    col = core.collection("STAGE")
    t0 = time.time()
    objs = []
    if which == "tiles":
        from sd import floor
        for i, t in enumerate(floor.tile_set(lib)):
            t.location = ((i % 2) * 1.2 - 0.6, (i // 2) * 1.2 - 0.6, 0)
        from sd import mats as M
        wat = core.mesh_obj("w", [(-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0)], [(0, 1, 2, 3)], col)
        wat.location.z = -0.0055
        core.set_mat(wat, M.water_film())
        wat.visible_shadow = False
    elif which == "torii":
        from sd import torii
        torii.build(lib)
    elif which in ("lantern", "lantern_broken"):
        from sd import lantern
        lantern.stone_lantern(lib, broken=which.endswith("broken"))
    elif which == "paper_lantern":
        from sd import dressing
        dressing.paper_lantern(lib)
    elif which == "banner":
        from sd import dressing
        dressing.banner(lib)
    elif which == "stairs":
        from sd import temple
        temple.stair_section(lib)
    elif which == "rocks":
        from sd import nature
        for i, r in enumerate(nature.rock_set(lib)):
            r.location = ((i % 5) * 1.3 - 2.6, (i // 5) * 1.3 - 1.3, 0)
    elif which == "cherry":
        from sd import nature
        nature.cherry_tree(lib, col, seed=int(arg("--seed", 1)), height=arg("--h", 6.0), crown=arg("--crown", 3.2))
    elif which == "temple":
        from sd import temple
        temple.hall(lib, col)
    elif which == "corridor":
        from sd import temple
        temple.corridor(lib, col, (0, -8), (0, 8))
    print(f"BUILD {which}: {time.time() - t0:.1f}s")

    # frame everything that was built
    bpy.context.view_layer.update()
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:
        o = inst.object
        if o.type == "MESH" and o.name != "w":
            m = inst.matrix_world
            pts += [m @ Vector(c) for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr, size = (lo + hi) / 2, (hi - lo).length
    print("BOUNDS", [round(v, 2) for v in lo], [round(v, 2) for v in hi], "tris", core.tri_count())
    if which != "tiles":
        g = core.box("ground", (60, 60, 0.02), (ctr.x, ctr.y, lo.z - 0.01), col)
        core.set_mat(g, mats.clay())
    stage(sc, clay)
    render.setup(sc, W, H, int(arg("--samples", 48)), 0.04)
    if clay:
        render.clay_override(sc)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = arg("--lens", 50)
    dist = arg("--dist", size * 1.25)
    az = math.radians(arg("--az", -28))
    el = math.radians(arg("--el", 12))
    cam.location = ctr + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    core.look_at(cam, ctr + Vector((0, 0, arg("--up", 0.0))))
    out = os.path.join(core.OUT, "props", f"{which}{'_clay' if clay else ''}{arg('--tag', '', 1, str)}.png")
    t0 = time.time()
    render.still(sc, out, cam)
    print(f"RENDER {out}: {time.time() - t0:.1f}s")


main()
