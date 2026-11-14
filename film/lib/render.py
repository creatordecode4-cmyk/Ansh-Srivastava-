"""Render presets and preview helpers (Cycles on CPU; this machine has no GPU)."""
import math
import os
import time

import bpy
from mathutils import Vector

from . import common


def configure(scene=None, preset="look", motion_blur=False, **overrides):
    """Apply a render preset from config/project.json. Returns the preset dict that was applied."""
    scene = scene or bpy.context.scene
    cfg = common.load_config("project.json")
    p = dict(cfg["render_presets"][preset])
    p.update(overrides)
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = p["resolution"]
    r.resolution_percentage = 100
    r.threads_mode = "FIXED"
    r.threads = 4
    r.use_persistent_data = False
    r.use_motion_blur = motion_blur
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.film_transparent = False
    c = scene.cycles
    c.device = "CPU"
    c.samples = p["samples"]
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.max_bounces = p.get("max_bounces", 6)
    c.diffuse_bounces = min(3, c.max_bounces)
    c.glossy_bounces = min(4, c.max_bounces)
    c.transmission_bounces = min(4, c.max_bounces)
    c.volume_bounces = p.get("volume_bounces", 0)
    c.transparent_max_bounces = 8
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    c.use_animated_seed = True
    scene.view_settings.view_transform = cfg.get("view_transform", "AgX")
    try:
        scene.view_settings.look = cfg.get("look", "None")
    except TypeError:
        scene.view_settings.look = "None"
    return p


_CLAY = None


def clay_material():
    global _CLAY
    mat = bpy.data.materials.get("MAT_Clay")
    if mat is None:
        mat = bpy.data.materials.new("MAT_Clay")
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
        bsdf.inputs["Roughness"].default_value = 0.75
    return mat


def render_still(path, camera=None, preset="look", clay=False, scene=None, frame=None, **overrides):
    """Render one frame to `path` (PNG). Returns seconds taken."""
    scene = scene or bpy.context.scene
    configure(scene, preset, **overrides)
    if camera is not None:
        scene.camera = camera
    if frame is not None:
        scene.frame_set(frame)
    layer = bpy.context.view_layer
    layer.material_override = clay_material() if clay else None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    layer.material_override = None
    return round(time.time() - t0, 1)


def preview_prop(objs, path, view="34", preset="draft", night=False, clay=False, ground=True, resolution=None):
    """Quick isolated preview of one or more objects for the prop authors.

    Adds a temporary camera, lights, world and ground to the current scene, renders, then removes them.
    view: 'front' (camera on -Y), 'side' (+X), 'back' (+Y), '34' (three-quarter), 'top'.
    night=True uses a dark world so emissive parts can be judged.
    """
    scene = bpy.context.scene
    lo, hi = common.world_bbox(objs)
    size = hi - lo
    center = (lo + hi) / 2
    radius = max(size.x, size.y, size.z, 0.2)
    dirs = {"front": (0, -1, 0.12), "side": (1, 0, 0.12), "back": (0, 1, 0.12), "34": (0.75, -1, 0.45), "top": (0, -0.05, 1)}
    d = Vector(dirs[view]).normalized()
    temp = []

    cam_data = bpy.data.cameras.new("_pv_cam")
    cam_data.lens = 60
    cam = bpy.data.objects.new("_pv_cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = center + d * radius * 3.4
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    temp.append(cam)

    def light(name, kind, energy, direction, color=(1, 1, 1), size=None):
        data = bpy.data.lights.new(name, kind)
        data.energy = energy
        data.color = color
        ob = bpy.data.objects.new(name, data)
        scene.collection.objects.link(ob)
        v = Vector(direction).normalized()
        ob.location = center + v * radius * 4
        ob.rotation_euler = (-v).to_track_quat("-Z", "Y").to_euler()
        if size and kind == "AREA":
            data.size = size
        if kind == "SUN":
            data.angle = math.radians(8)
        temp.append(ob)
        return ob

    if night:
        light("_pv_moon", "SUN", 0.6, (0.4, -0.6, 0.9), (0.6, 0.72, 1.0))
        light("_pv_rim", "SUN", 0.5, (-0.3, 0.9, 0.4), (1.0, 0.18, 0.12))
    else:
        light("_pv_key", "SUN", 3.0, d + Vector((0.5, 0.0, 0.8)))
        light("_pv_rim", "SUN", 1.2, -d + Vector((0.0, 0.0, 0.6)), (0.8, 0.9, 1.0))

    old_world = scene.world
    world = bpy.data.worlds.new("_pv_world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    shade = 0.004 if night else 0.32
    bg.inputs[0].default_value = (shade, shade, shade * 1.1, 1)
    scene.world = world

    plane = None
    if ground:
        mesh = bpy.data.meshes.new("_pv_ground")
        s = radius * 12
        mesh.from_pydata([(-s, -s, lo.z), (s, -s, lo.z), (s, s, lo.z), (-s, s, lo.z)], [], [(0, 1, 2, 3)])
        plane = bpy.data.objects.new("_pv_ground", mesh)
        mat = bpy.data.materials.new("_pv_ground")
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        g = 0.03 if night else 0.22
        bsdf.inputs["Base Color"].default_value = (g, g, g, 1)
        bsdf.inputs["Roughness"].default_value = 0.35 if night else 0.8
        mesh.materials.append(mat)
        scene.collection.objects.link(plane)
        temp.append(plane)

    old_cam = scene.camera
    hidden = []
    for ob in scene.objects:
        if ob not in objs and ob not in temp and not ob.hide_render and ob.type in {"MESH", "LIGHT", "CURVE"}:
            if not night or ob.type != "LIGHT":
                ob.hide_render = True
                hidden.append(ob)
    kw = {"resolution": resolution} if resolution else {}
    secs = render_still(path, camera=cam, preset=preset, clay=clay, **kw)
    for ob in hidden:
        ob.hide_render = False
    scene.camera = old_cam
    scene.world = old_world
    for ob in temp:
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
    bpy.data.worlds.remove(world)
    return secs
