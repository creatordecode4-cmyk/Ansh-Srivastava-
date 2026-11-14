"""Shared helpers for every build script (Blender 5.3 as a Python module, headless).

Conventions used by the whole project:
  * metres, Z up, +Y = north (torii side of the courtyard), +X = east, courtyard floor at z = 0
  * every prop builder returns ONE mesh object (several material slots are fine) whose origin sits on the
    ground at the centre of its footprint, facing -Y (towards the main camera) unless stated otherwise
  * builders create data in the current file only; they never reset the scene and never render
"""
import json
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

FILM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("FILM_DATA") or os.path.join(FILM, "_data")
CACHE = os.path.join(DATA, "cache")
PH = os.path.join(CACHE, "polyhaven")      # Poly Haven downloads: <PH>/<slug>/<slug>_<Map>_2k.jpg
BUILD = os.path.join(DATA, "build")        # stage outputs (.blend)
QC = os.path.join(DATA, "qc")              # preview renders and metrics
REFS = os.path.join(DATA, "refs")          # the user's reference sheets
INPUTS = os.path.join(DATA, "inputs")      # user-supplied models (GLB)

for _d in (BUILD, QC):
    os.makedirs(_d, exist_ok=True)


def load_config(name):
    with open(os.path.join(FILM, "config", name)) as fh:
        return json.load(fh)


def reset_scene(fps=24):
    """Start from an empty file with project units and frame rate. Returns the scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    return scene


def ensure_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj, collection=None):
    col = collection or bpy.context.scene.collection
    if obj.name not in col.objects:
        col.objects.link(obj)
    return obj


def mesh_object(name, mesh, collection=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), materials=()):
    obj = bpy.data.objects.new(name, mesh)
    obj.location, obj.rotation_euler, obj.scale = loc, rot, scale
    for mat in materials:
        obj.data.materials.append(mat)
    return link(obj, collection)


def bm_to_object(name, bm, collection=None, materials=(), **kw):
    """Turn a bmesh into a linked mesh object (the bmesh is freed)."""
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh_object(name, mesh, collection, materials=materials, **kw)


def empty(name, collection=None, loc=(0, 0, 0), size=0.3):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_size = size
    obj.location = loc
    return link(obj, collection)


def update():
    bpy.context.view_layer.update()


def apply_modifiers(obj):
    """Bake the modifier stack into the mesh (keeps materials and UVs)."""
    if not obj.modifiers:
        return obj
    dg = bpy.context.evaluated_depsgraph_get()
    new_mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    obj.modifiers.clear()
    obj.data = new_mesh
    new_mesh.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


def join(objs, name, collection=None):
    """Merge mesh objects into one object named `name`. Modifiers are applied first; material slots are merged.

    The result keeps the world-space shape; its origin is the world origin (0, 0, 0).
    """
    objs = [o for o in objs if o is not None]
    update()
    slot_index = {}
    mats = []
    bm = bmesh.new()
    uv_names = []
    for ob in objs:
        apply_modifiers(ob)
        me = ob.data
        local = []
        for mat in me.materials:
            key = mat.name if mat else None
            if key not in slot_index:
                slot_index[key] = len(mats)
                mats.append(mat)
            local.append(slot_index[key])
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(ob.matrix_world)
        if ob.matrix_world.determinant() < 0:
            bmesh.ops.reverse_faces(tmp, faces=tmp.faces)
        for f in tmp.faces:
            f.material_index = local[f.material_index] if local and f.material_index < len(local) else 0
        tmp_mesh = bpy.data.meshes.new("_tmp_join")
        tmp.to_mesh(tmp_mesh)
        tmp.free()
        tmp_mesh.materials.clear()
        bm.from_mesh(tmp_mesh)
        for uv in me.uv_layers:
            if uv.name not in uv_names:
                uv_names.append(uv.name)
        bpy.data.meshes.remove(tmp_mesh)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for mat in mats:
        mesh.materials.append(mat)
    for ob in objs:
        old = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if old.users == 0:
            bpy.data.meshes.remove(old)
    return mesh_object(name, mesh, collection)


def instance(src, name, collection=None, loc=(0, 0, 0), rot_z=0.0, scale=1.0, rot=None):
    """Linked duplicate: a new object sharing the mesh data of `src` (cheap to render)."""
    obj = bpy.data.objects.new(name, src.data)
    obj.location = loc
    obj.rotation_euler = rot if rot is not None else (0.0, 0.0, rot_z)
    obj.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    for key in src.keys():
        obj[key] = src[key]
    return link(obj, collection)


def set_smooth(obj, angle_deg=35.0):
    """Smooth shading with sharp edges above the given angle."""
    mesh = obj.data
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=math.radians(angle_deg))
    return obj


def bevel(obj, width=0.01, segments=2, angle_deg=30.0):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle_deg)
    return mod


def sock(node, names, out=False):
    """First socket found under any of the given names (covers 4.x/5.x renames such as Fac/Factor)."""
    coll = node.outputs if out else node.inputs
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in coll:
            return coll[n]
    raise KeyError(f"{node.bl_idname}: none of {names} in {[s.name for s in coll]}")


def rng(seed):
    return random.Random(seed)


def world_bbox(objs):
    update()
    lo = Vector((1e18, 1e18, 1e18))
    hi = Vector((-1e18, -1e18, -1e18))
    for ob in objs:
        if ob.type != "MESH":
            continue
        for corner in ob.bound_box:
            p = ob.matrix_world @ Vector(corner)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    return lo, hi


def tri_count(objs):
    total = 0
    for ob in objs:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            total += len(ob.data.loop_triangles)
    return total


def save_blend(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp.blend"
    bpy.ops.wm.save_as_mainfile(filepath=tmp, copy=True, compress=True)
    os.replace(tmp, path)
    return path


def append_objects(blend_path, names=None, collection=None):
    """Append objects (all, or the named ones) from another .blend into the current file."""
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if names is None or n in names]
    out = []
    for obj in dst.objects:
        if obj is not None:
            link(obj, collection)
            out.append(obj)
    return out
