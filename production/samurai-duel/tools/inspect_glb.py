"""Look inside an image-to-3D model (GLB) and render a four-view turnaround of it.

    python3 -I tools/inspect_glb.py <model.glb> <out.png> [--size 480 720] [--samples 24] [--clay]

Prints the object tree (triangles, bounds, materials, texture sizes, armatures) and writes one
sheet with front / three-quarter / side / back views under neutral light. Run with -I: the model
is a downloaded file, so nothing from its folder may be imported.
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


def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def report(objs):
    bpy.context.view_layer.update()
    pts = []
    for o in objs:
        line = f"  {o.type:8s} {o.name[:40]:40s} parent={o.parent.name if o.parent else '-'}"
        if o.type == "MESH":
            me = o.data
            tris = sum(len(p.vertices) - 2 for p in me.polygons)
            line += f" verts={len(me.vertices)} tris={tris} uv={len(me.uv_layers)} vcol={len(me.color_attributes)} mats={[m.name if m else None for m in me.materials]}"
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        if o.type == "ARMATURE":
            line += f" bones={len(o.data.bones)}"
        print(line)
    for im in bpy.data.images:
        if im.size[0]:
            print(f"  IMAGE {im.name[:40]:40s} {im.size[0]}x{im.size[1]} {im.colorspace_settings.name}")
    for m in bpy.data.materials:
        if m.node_tree:
            kinds = sorted({n.bl_idname.replace('ShaderNode', '') for n in m.node_tree.nodes})
            print(f"  MATERIAL {m.name[:30]:30s} {kinds}")
    print("  actions:", [a.name for a in bpy.data.actions])
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    print("  BOUNDS lo", [round(v, 3) for v in lo], "hi", [round(v, 3) for v in hi], "size", [round(v, 3) for v in (hi - lo)])
    return lo, hi


def main():
    path, out = sys.argv[1], sys.argv[2]
    W, H = arg("--size", [480, 720], 2, int)
    sc = core.reset_scene()
    t0 = time.time()
    objs = load(path)
    print(f"IMPORT {os.path.basename(path)}: {time.time() - t0:.1f}s, {len(objs)} objects")
    lo, hi = report(objs)
    ctr, size = (lo + hi) / 2, hi - lo

    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.44, 0.48, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    g = core.box("ground", (60, 60, 0.02), (ctr.x, ctr.y, lo.z - 0.01), sc.collection)
    core.set_mat(g, mats.clay())
    render.setup(sc, W, H, int(arg("--samples", 24)), 0.05)
    sc.view_settings.exposure = 0.0
    if "--clay" in sys.argv:
        render.clay_override(sc)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 85
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 2.6, math.radians(8)
    sc.collection.objects.link(sun)
    # distance so that the tallest extent fits the frame with a margin
    fit = max(size.z / 0.82, max(size.x, size.y) / 0.82 * (H / W))
    dist = fit * cam.data.lens / 36.0 * (W / H if H > W else 1.0) * (36.0 / 36.0)
    dist = (fit / 2) / math.tan(math.atan((36.0 * H / W / 2) / cam.data.lens)) if H >= W else (fit / 2) / math.tan(math.atan(18.0 / cam.data.lens))
    cam.data.clip_end = dist * 4 + 100
    from PIL import Image
    views = [("front", 0), ("three-quarter", 35), ("side", 90), ("back", 180)]
    if "--views" in sys.argv:
        views = [(f"az{int(a)}", a) for a in arg("--views", [0], sys.argv[sys.argv.index("--views") + 1:].index("--end") if "--end" in sys.argv else 1)]
    tiles = []
    front = arg("--front", 0.0)          # extra yaw if the model does not face -Y
    for name, az in views:
        a = math.radians(az + front)
        cam.location = ctr + Vector((math.sin(a), -math.cos(a), 0.12)) * dist
        core.look_at(cam, ctr)
        la = a - math.radians(35)
        d = Vector((math.sin(la) * 0.7, -math.cos(la) * 0.7, 0.75)).normalized()
        sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        p = out.replace(".png", f"_{name}.png")
        render.still(sc, p, cam)
        tiles.append(Image.open(p).convert("RGB"))
        os.remove(p)
    sheet = Image.new("RGB", (W * len(tiles), H))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * W, 0))
    sheet.save(out)
    print("SHEET", out, sheet.size)


main()
