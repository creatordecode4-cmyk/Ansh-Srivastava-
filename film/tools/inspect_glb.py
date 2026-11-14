"""Inspect a GLB/FBX model: print stats and render front/side/back/three-quarter views.

Usage: python3 -I inspect_glb.py <model path> <output dir> [--samples N] [--res WxH]
Writes <stem>_front.png, _side.png, _back.png, _34.png and <stem>_stats.json into the output dir.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def world_bbox(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for corner in ob.bound_box:
            p = ob.matrix_world @ Vector(corner)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    return lo, hi


def main():
    args = sys.argv[1:]
    path, out_dir = args[0], args[1]
    samples = 24
    res = (560, 800)
    if "--samples" in args:
        samples = int(args[args.index("--samples") + 1])
    if "--res" in args:
        w, h = args[args.index("--res") + 1].split("x")
        res = (int(w), int(h))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit("unsupported format " + ext)

    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH"]
    stats = {"file": os.path.basename(path), "bytes": os.path.getsize(path), "objects": []}
    total_tris = 0
    for ob in scene.objects:
        entry = {"name": ob.name, "type": ob.type, "parent": ob.parent.name if ob.parent else None}
        if ob.type == "MESH":
            me = ob.data
            me.calc_loop_triangles()
            tris = len(me.loop_triangles)
            total_tris += tris
            entry.update(
                verts=len(me.vertices),
                tris=tris,
                uv_layers=[uv.name for uv in me.uv_layers],
                color_attrs=[c.name for c in me.color_attributes],
                vertex_groups=len(ob.vertex_groups),
                materials=[],
            )
            for slot in ob.material_slots:
                mat = slot.material
                if not mat:
                    continue
                imgs = []
                if mat.node_tree:
                    for node in mat.node_tree.nodes:
                        if node.type == "TEX_IMAGE" and node.image:
                            links = [l.to_socket.name for out in node.outputs for l in out.links]
                            imgs.append({"image": node.image.name, "size": list(node.image.size), "feeds": links})
                entry["materials"].append({"name": mat.name, "images": imgs})
        stats["objects"].append(entry)
    lo, hi = world_bbox(meshes)
    size = hi - lo
    stats["total_tris"] = total_tris
    stats["bbox_min"] = [round(v, 4) for v in lo]
    stats["bbox_max"] = [round(v, 4) for v in hi]
    stats["size_xyz"] = [round(v, 4) for v in size]
    stats["armatures"] = [o.name for o in scene.objects if o.type == "ARMATURE"]
    stats["actions"] = [a.name for a in bpy.data.actions]

    # --- render setup ---
    center = (lo + hi) / 2
    radius = max(size.x, size.y, size.z)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.35, 0.35, 0.36, 1)
    bg.inputs[1].default_value = 1.0

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 2.5
    sun_data.angle = math.radians(20)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)

    aspect = res[0] / res[1]
    views = {
        "front": (0, -1, 0),
        "side": (1, 0, 0),
        "back": (0, 1, 0),
        "34": (0.7, -0.7, 0.25),
    }
    outputs = {}
    for name, direction in views.items():
        d = Vector(direction).normalized()
        cam.location = center + d * radius * 3
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        # fit ortho scale to the silhouette seen from this direction
        horiz = max(size.x, size.y) if name == "34" else (size.x if abs(d.y) > 0.5 else size.y)
        cam_data.ortho_scale = max(horiz, size.z * aspect) * 1.12
        sun.rotation_euler = (d * 1.0 + Vector((0.3, 0, 0.8))).to_track_quat("Z", "Y").to_euler()
        out = os.path.join(out_dir, f"{stem}_{name}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        outputs[name] = out
    stats["renders"] = outputs
    with open(os.path.join(out_dir, f"{stem}_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    print("STATS_JSON " + json.dumps({k: v for k, v in stats.items() if k != "renders"}))


if __name__ == "__main__":
    main()
