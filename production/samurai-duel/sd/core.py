"""Shared helpers for building the scene with headless bpy (Blender 5.x).

Conventions: Z up, metres. +Y is north (toward the torii), +X is east.
Every prop is built once as a master object/collection and reused through instancing.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "out")
REFS = os.path.join(HERE, "refs")


# ----------------------------------------------------------------------------- scene / collections
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.render.fps = 24
    return sc


def collection(name, parent=None, hide_render=False):
    """Get or create a collection linked under parent (scene root by default)."""
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    col.hide_render = hide_render
    return col


def link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def depsgraph():
    return bpy.context.evaluated_depsgraph_get()


# ----------------------------------------------------------------------------- mesh building
def mesh_obj(name, verts, faces, col=None, edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    if col is not None:
        col.objects.link(ob)
    return ob


def grid_obj(name, P, col=None, close_u=False, close_v=False):
    """Mesh from an (nu, nv, 3) array of points (quads between neighbours)."""
    P = np.asarray(P, dtype=np.float64)
    nu, nv = P.shape[:2]
    idx = np.arange(nu * nv).reshape(nu, nv)
    iu = np.arange(nu) if close_u else np.arange(nu - 1)
    iv = np.arange(nv) if close_v else np.arange(nv - 1)
    a = idx[np.ix_(iu, iv)]
    b = idx[np.ix_((iu + 1) % nu, iv)]
    c = idx[np.ix_((iu + 1) % nu, (iv + 1) % nv)]
    d = idx[np.ix_(iu, (iv + 1) % nv)]
    faces = np.stack([a, b, c, d], axis=-1).reshape(-1, 4)
    me = bpy.data.meshes.new(name)
    me.vertices.add(nu * nv)
    me.vertices.foreach_set("co", P.reshape(-1))
    me.loops.add(len(faces) * 4)
    me.loops.foreach_set("vertex_index", faces.reshape(-1))
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, len(faces) * 4, 4))
    me.polygons.foreach_set("loop_total", np.full(len(faces), 4))
    me.update(calc_edges=True)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    if col is not None:
        col.objects.link(ob)
    return ob


def box(name, size, loc=(0, 0, 0), col=None, bevel=0.0, segs=2, rot=(0, 0, 0)):
    """Axis-aligned box centred on loc. bevel > 0 rounds the edges (real things have no razor edges)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    if col is not None:
        col.objects.link(ob)
    return ob


def prism(name, n, r_bot, r_top, h, loc=(0, 0, 0), col=None, bevel=0.0, rot_z=0.0, segs=2):
    """n-sided prism / frustum standing on z=0 (local)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=r_bot, radius2=r_top, depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    if col is not None:
        col.objects.link(ob)
    return ob


def lathe(name, profile, segments=32, col=None, loc=(0, 0, 0), cap=True):
    """Surface of revolution around Z from a list of (radius, z) points."""
    prof = np.asarray(profile, dtype=np.float64)
    ang = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    P = np.zeros((segments, len(prof), 3))
    P[:, :, 0] = np.cos(ang)[:, None] * prof[None, :, 0]
    P[:, :, 1] = np.sin(ang)[:, None] * prof[None, :, 0]
    P[:, :, 2] = prof[None, :, 1]
    ob = grid_obj(name, P, col, close_u=True)
    if cap:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.to_mesh(ob.data)
        bm.free()
    ob.location = loc
    return ob


def tube(name, pts, radii, col=None, segs=10, cap=True):
    """Tube along a polyline with per-point radius (branches, ropes, poles)."""
    pts = [Vector(p) for p in pts]
    if isinstance(radii, (int, float)):
        radii = [radii] * len(pts)
    P = np.zeros((len(pts), segs, 3))
    up = Vector((0, 0, 1))
    prev_n = None
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t.normalize()
        if prev_n is None:
            ref = up if abs(t.dot(up)) < 0.95 else Vector((1, 0, 0))
            n = t.cross(ref).normalized()
        else:  # parallel transport keeps the tube from twisting
            n = (prev_n - t * prev_n.dot(t))
            n = n.normalized() if n.length > 1e-6 else t.orthogonal().normalized()
        b = t.cross(n).normalized()
        prev_n = n
        for j in range(segs):
            a = 2 * math.pi * j / segs
            P[i, j] = p + (n * math.cos(a) + b * math.sin(a)) * radii[i]
    ob = grid_obj(name, P, col, close_v=True)
    if cap:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        bm.to_mesh(ob.data)
        bm.free()
    return ob


def join(objs, name=None):
    """Join objects into the first one (keeps material slots)."""
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    dg = depsgraph()
    bm = bmesh.new()
    mats = []
    base = objs[0]
    inv = base.matrix_world.inverted()
    for o in objs:
        me = o.data
        offset = len(bm.verts)
        slot_map = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            slot_map.append(mats.index(m))
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(inv @ o.matrix_world)
        tmp_me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(tmp_me)
        tmp.free()
        nfaces_before = len(bm.faces)
        bm.from_mesh(tmp_me)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[nfaces_before:]:
            f.material_index = slot_map[f.material_index] if slot_map and f.material_index < len(slot_map) else 0
        bpy.data.meshes.remove(tmp_me)
    me = bpy.data.meshes.new(name or base.name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    old = [o.data for o in objs]
    base.data = me
    if name:
        base.name = name
    for o in objs[1:]:
        bpy.data.objects.remove(o)
    for m in old:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return base


def apply_transform(ob):
    """Bake object transform into the mesh (so modifiers and box-mapped textures see real scale)."""
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    return ob


def apply_modifiers(ob):
    """Replace the mesh by its evaluated (modifier-applied) result."""
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(depsgraph())
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=depsgraph())
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        if isinstance(old, bpy.types.Mesh):
            bpy.data.meshes.remove(old)
        elif isinstance(old, bpy.types.Curve):
            bpy.data.curves.remove(old)
    return ob


def smooth(ob, angle=40.0):
    me = ob.data
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(angle))
    return ob


def subdivide(ob, levels=1, simple=False, apply=True):
    m = ob.modifiers.new("subd", "SUBSURF")
    m.levels = m.render_levels = levels
    m.subdivision_type = "SIMPLE" if simple else "CATMULL_CLARK"
    return apply_modifiers(ob) if apply else ob


_tex_cache = {}


def noise_tex(kind="CLOUDS", scale=0.25, depth=2, seed=0):
    key = (kind, round(scale, 4), depth)
    t = _tex_cache.get(key)
    if t is None or t.name not in bpy.data.textures:
        t = bpy.data.textures.new(f"TEX_{kind}_{scale:.3f}", kind)
        if hasattr(t, "noise_scale"):
            t.noise_scale = scale
        if hasattr(t, "noise_depth"):
            t.noise_depth = depth
        _tex_cache[key] = t
    return t


def displace(ob, strength=0.05, scale=0.3, kind="CLOUDS", depth=2, mid=0.5, direction="NORMAL", apply=True, offset=None):
    """Rough up a surface with a procedural texture (rock, weathered wood, hand-made tiles)."""
    m = ob.modifiers.new("disp", "DISPLACE")
    m.texture = noise_tex(kind, scale, depth)
    m.strength = strength
    m.mid_level = mid
    m.direction = direction
    m.texture_coords = "GLOBAL" if offset is None else "OBJECT"
    if offset is not None:
        m.texture_coords_object = offset
    return apply_modifiers(ob) if apply else ob


def bevel_mod(ob, width=0.01, segments=2, angle=35.0, apply=True):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    return apply_modifiers(ob) if apply else ob


def solidify(ob, thickness=0.02, offset=-1.0, apply=True):
    m = ob.modifiers.new("solid", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    return apply_modifiers(ob) if apply else ob


def set_mat(ob, mat, index=None):
    me = ob.data
    if index is None:
        me.materials.clear()
        me.materials.append(mat)
    else:
        while len(me.materials) <= index:
            me.materials.append(None)
        me.materials[index] = mat
    return ob


def tri_count(objs=None):
    dg = depsgraph()
    n = 0
    for inst in dg.object_instances:
        o = inst.object
        if o.type == "MESH":
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n


# ----------------------------------------------------------------------------- instancing
def instance(src, name, col, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    """Instance a master object (linked mesh data) or a master collection (collection instance)."""
    if isinstance(src, bpy.types.Collection):
        ob = bpy.data.objects.new(name, None)
        ob.instance_type = "COLLECTION"
        ob.instance_collection = src
        ob.empty_display_size = 0.3
    else:
        ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
    col.objects.link(ob)
    return ob


def face_instancer(name, src_obj, transforms, col):
    """Many instances of src_obj driven by one carrier mesh (one triangle per instance).

    transforms: iterable of (location, 3x3 rotation matrix, scale). Cheap for tens of thousands.
    """
    verts, faces = [], []
    s3 = math.sqrt(3) / 2
    base = [Vector((-1.0, -s3 * 2 / 3, 0)), Vector((1.0, -s3 * 2 / 3, 0)), Vector((0.0, s3 * 4 / 3, 0))]
    for loc, rot, sc in transforms:
        i = len(verts)
        for b in base:
            verts.append(Vector(loc) + rot @ (b * sc))
        faces.append((i, i + 1, i + 2))
    carrier = mesh_obj(name, verts, faces, col)
    carrier.instance_type = "FACES"
    carrier.use_instance_faces_scale = True
    carrier.instance_faces_scale = 1.0 / (0.5 * 2.0 * s3 * 2) ** 0.5
    carrier.show_instancer_for_render = False
    carrier.show_instancer_for_viewport = False
    child = bpy.data.objects.new(name + "_src", src_obj.data)
    col.objects.link(child)
    child.parent = carrier
    return carrier


# ----------------------------------------------------------------------------- misc
def rng(seed):
    return random.Random(seed)


def look_at(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    q = d.to_track_quat("-Z", "Y")
    ob.rotation_euler = q.to_euler()
    ob.rotation_euler.rotate_axis("Z", roll)
    return ob


def rot_z(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return Vector((v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2] if len(v) > 2 else 0.0))


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise2(x, y, seed=0):
    """Cheap tileable-free 2D value noise on numpy arrays (for baking detail into meshes)."""
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    xf, yf = x - xi, y - yi

    def h(a, b):
        n = (a * 374761393 + b * 668265263 + seed * 2147483647) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0

    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    return (h(xi, yi) * (1 - u) + h(xi + 1, yi) * u) * (1 - v) + (h(xi, yi + 1) * (1 - u) + h(xi + 1, yi + 1) * u) * v


def fbm2(x, y, octaves=4, seed=0):
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        out = out + amp * value_noise2(x * 2 ** o, y * 2 ** o, seed + o * 17)
        tot += amp
        amp *= 0.5
    return out / tot
