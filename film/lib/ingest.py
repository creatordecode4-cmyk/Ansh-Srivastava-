"""Bring image-to-3D models (Tripo GLB) into the project: import, clean, scale, decimate, cache as .blend.

Tripo exports arrive as one very dense mesh (about 2 million triangles) with a 1k base colour, roughness/metal and
normal texture, standing on z = 0 and facing -Y after Blender's glTF import.
"""
import hashlib
import os

import bpy
from mathutils import Matrix, Vector

from . import common

LIB = os.path.join(common.BUILD, "ingested")


def _file_key(path, target_height, max_tris):
    st = os.stat(path)
    raw = f"{os.path.basename(path)}|{st.st_size}|{target_height}|{max_tris}|v2"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def import_glb(path):
    """Import a GLB and return the new mesh objects."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in new:
        if o.type != "MESH":
            # keep transforms of parents by baking them into children first
            for child in o.children:
                mw = child.matrix_world.copy()
                child.parent = None
                child.matrix_world = mw
            bpy.data.objects.remove(o, do_unlink=True)
    return meshes


def bake_transform(obj):
    """Apply the object's transform to its mesh so location/rotation/scale become identity."""
    common.update()
    mesh = obj.data
    mesh.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    mesh.update()


def normalize(obj, target_height=None, ground=True, center_xy=True):
    """Scale to `target_height` metres, put the lowest point on z = 0 and centre the footprint on the origin."""
    bake_transform(obj)
    lo, hi = common.world_bbox([obj])
    size = hi - lo
    scale = (target_height / size.z) if target_height and size.z > 1e-6 else 1.0
    offset = Vector((-(lo.x + hi.x) / 2 if center_xy else 0.0, -(lo.y + hi.y) / 2 if center_xy else 0.0, -lo.z if ground else 0.0))
    obj.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(offset))
    obj.data.update()
    return scale


def decimate(obj, max_tris):
    """Reduce the triangle count to at most `max_tris` (collapse decimation keeps UVs)."""
    tris = common.tri_count([obj])
    if tris <= max_tris:
        return tris
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max_tris / tris
    mod.use_collapse_triangulate = True
    common.apply_modifiers(obj)
    return common.tri_count([obj])


def emissive_from_red(mat, strength=6.0, threshold=0.25):
    """Make the saturated red parts of the base-colour texture glow (lantern windows painted into the texture)."""
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    link = next((l for l in nt.links if l.to_node == bsdf and l.to_socket.name == "Base Color"), None) if bsdf else None
    if not link:
        return False
    color = link.from_socket
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(color, sep.inputs[0])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(sep.outputs[1], mx.inputs[0])
    nt.links.new(sep.outputs[2], mx.inputs[1])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    nt.links.new(sep.outputs[0], sub.inputs[0])
    nt.links.new(mx.outputs[0], sub.inputs[1])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = threshold
    ramp.inputs["From Max"].default_value = threshold + 0.25
    ramp.inputs["To Min"].default_value = 0.0
    ramp.inputs["To Max"].default_value = strength
    nt.links.new(sub.outputs[0], ramp.inputs["Value"])
    nt.links.new(color, common.sock(bsdf, ["Emission Color", "Emission"]))
    nt.links.new(ramp.outputs["Result"], bsdf.inputs["Emission Strength"])
    return True


def ingest(path, name, target_height=None, max_tris=150000, collection=None, use_cache=True):
    """Import a GLB as one clean object called `name`. Results are cached in <build>/ingested/ as .blend files."""
    os.makedirs(LIB, exist_ok=True)
    cache = os.path.join(LIB, f"{name}_{_file_key(path, target_height, max_tris)}.blend")
    if use_cache and os.path.exists(cache):
        objs = common.append_objects(cache, names=[name], collection=collection)
        if objs:
            return objs[0]
    meshes = import_glb(path)
    if not meshes:
        raise RuntimeError(f"no mesh in {path}")
    obj = meshes[0] if len(meshes) == 1 else common.join(meshes, name)
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    common.link(obj, collection)
    obj.name = name
    obj.data.name = name
    normalize(obj, target_height)
    tris = decimate(obj, max_tris)
    obj.data.shade_smooth()
    obj["source_file"] = os.path.basename(path)
    obj["tris"] = tris
    for img in bpy.data.images:
        if img.source == "FILE" and not img.packed_file and img.filepath:
            try:
                img.pack()
            except RuntimeError:
                pass
    if use_cache:
        bpy.data.libraries.write(cache, {obj}, compress=True)
    return obj
