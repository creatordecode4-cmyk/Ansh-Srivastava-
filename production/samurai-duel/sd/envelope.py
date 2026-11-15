"""Watertight outer skin of a messy mesh.

An image-to-3D model that has been cut apart is full of open borders, double layers and faces
pointing either way. Blender's cloth collision pushes cloth toward the side a face points to,
so on such a mesh cloth gets sucked through every badly oriented patch and ends up in a wad.

The skin built here does not depend on the input's face directions at all:
  1. distance from every cell of a voxel grid to the surface (nearest surface point)
  2. the outside is whatever a flood fill reaches from a corner without passing within 'seal'
     of the surface, grown back toward the surface afterwards
  3. the skin is the border of that outside: a closed surface 'offset' away from the model,
     faces pointing out, the body solid, narrow openings plugged
"""
import time

import bpy
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage import measure


def surface_points(me, max_edge=0.006):
    """Vertices and face centres, plus extra points inside triangles that are larger than max_edge."""
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    tri = np.empty(nt * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    P = co[tri.reshape(-1, 3)]
    e = np.maximum.reduce([np.linalg.norm(P[:, 0] - P[:, 1], axis=1), np.linalg.norm(P[:, 1] - P[:, 2], axis=1), np.linalg.norm(P[:, 2] - P[:, 0], axis=1)])
    pts = [co, P.mean(axis=1)]
    big = P[e > max_edge]
    if len(big):
        n = int(min(12, np.ceil(np.percentile(e[e > max_edge], 99) / max_edge)))      # a few huge patch faces must not set the density for all
        for i in range(n + 1):
            for j in range(n + 1 - i):
                a, b = i / n, j / n
                pts.append(big[:, 0] * a + big[:, 1] * b + big[:, 2] * (1 - a - b))
    return np.concatenate(pts)


def build(me, voxel=0.005, offset=0.005, seal=0.02, name="Envelope", verbose=True):
    """Closed, solid skin 'offset' metres outside mesh 'me'. Returns a new mesh (triangles, normals out).

    seal: openings narrower than twice this are plugged, so that slits left by cutting the model
    apart do not let the 'outside' flood into the hollow body. Without it the result is a
    double-walled shell, which is useless for automatic skin weights."""
    t0 = time.time()
    pts = surface_points(me)
    seal = max(seal, offset)
    lo, hi = pts.min(0) - seal - 4 * voxel, pts.max(0) + seal + 4 * voxel
    shape = np.ceil((hi - lo) / voxel).astype(int) + 1
    gx, gy, gz = [lo[k] + np.arange(shape[k]) * voxel for k in range(3)]
    tree = cKDTree(pts)
    far = seal + 3 * voxel
    d = np.full(shape, far, dtype=np.float32)
    for i in range(shape[0]):                                   # slab by slab keeps memory flat
        q = np.stack(np.meshgrid([gx[i]], gy, gz, indexing="ij"), axis=-1).reshape(-1, 3)
        dist, _ = tree.query(q, distance_upper_bound=far, workers=-1)
        d[i] = np.minimum(dist, far).reshape(shape[1], shape[2])
    # the outside as seen through thick walls: it cannot get through any opening narrower than 2 * seal
    lab, _ = ndimage.label(d >= seal)
    outside = lab == lab[0, 0, 0]
    del lab
    # then let it come back in toward the surface, but no deeper into an opening than (seal - offset)
    back = ndimage.distance_transform_edt(~outside).astype(np.float32) * voxel
    phi = np.minimum(d - offset, (seal - offset) - back + voxel)        # > 0 outside, < 0 inside the solid
    del back
    verts, faces, _, _ = measure.marching_cubes(phi, level=0.0, spacing=(voxel, voxel, voxel))
    verts = verts + lo
    out = bpy.data.meshes.new(name)
    out.vertices.add(len(verts))
    out.vertices.foreach_set("co", verts.reshape(-1).astype(np.float32))
    out.loops.add(len(faces) * 3)
    out.loops.foreach_set("vertex_index", faces.reshape(-1).astype(np.int32))
    out.polygons.add(len(faces))
    out.polygons.foreach_set("loop_start", np.arange(0, len(faces) * 3, 3, dtype=np.int32))
    out.polygons.foreach_set("loop_total", np.full(len(faces), 3, dtype=np.int32))
    out.update(calc_edges=True)
    P = verts[faces]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    vol = float((P.mean(axis=1) * n).sum() / 6.0)
    if vol < 0:
        out.flip_normals()
    out.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    if verbose:
        print(f"  envelope: grid {tuple(int(v) for v in shape)}, {len(pts)} surface points, {len(faces)} faces, "
              f"enclosed volume {abs(vol) * 1000:.1f} litres, {time.time() - t0:.1f}s")
    return out


def simplify(me, faces=30000, smooth=2, name=None):
    """Thinned and lightly smoothed copy (still closed, still pointing out)."""
    import bmesh
    ob = bpy.data.objects.new("tmp_env", me)
    bpy.context.scene.collection.objects.link(ob)
    d = ob.modifiers.new("dec", "DECIMATE")
    d.ratio = min(1.0, faces / max(1, len(me.polygons)))
    if smooth:
        s = ob.modifiers.new("smooth", "SMOOTH")
        s.factor, s.iterations = 0.5, smooth
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    out.name = name or me.name + "_low"
    bpy.data.objects.remove(ob)
    bm = bmesh.new()                                   # marching cubes can leave a pinhole or two
    bm.from_mesh(out)
    rim = [e for e in bm.edges if e.is_boundary]
    if rim:
        bmesh.ops.holes_fill(bm, edges=rim, sides=0)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(out)
    bm.free()
    return out
