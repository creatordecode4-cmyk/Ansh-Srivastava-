"""Watertight outer skin of a messy mesh.

An image-to-3D model that has been cut apart is full of open borders, double layers and faces
pointing either way. Blender's cloth collision pushes cloth toward the side a face points to,
so on such a mesh cloth gets sucked through every badly oriented patch and ends up in a wad.

The skin built here does not depend on the input's face directions at all:
  1. distance from every cell of a voxel grid to the surface (nearest surface point)
  2. cells closer than 'offset' are wall; the outside is whatever a flood fill reaches from a corner
  3. the skin is the border of that outside: a closed surface 'offset' away from the model,
     faces pointing out, enclosed cavities filled
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


def build(me, voxel=0.005, offset=0.005, name="Envelope", verbose=True):
    """Closed skin 'offset' metres outside mesh 'me'. Returns a new mesh (triangles, normals out)."""
    t0 = time.time()
    pts = surface_points(me)
    lo, hi = pts.min(0) - offset - 4 * voxel, pts.max(0) + offset + 4 * voxel
    shape = np.ceil((hi - lo) / voxel).astype(int) + 1
    gx, gy, gz = [lo[k] + np.arange(shape[k]) * voxel for k in range(3)]
    tree = cKDTree(pts)
    far = offset + 3 * voxel
    d = np.full(shape, far, dtype=np.float32)
    for i in range(shape[0]):                                   # slab by slab keeps memory flat
        q = np.stack(np.meshgrid([gx[i]], gy, gz, indexing="ij"), axis=-1).reshape(-1, 3)
        dist, _ = tree.query(q, distance_upper_bound=far, workers=-1)
        d[i] = np.minimum(dist, far).reshape(shape[1], shape[2])
    wall = d < offset
    lab, _ = ndimage.label(~wall)
    outside = lab == lab[0, 0, 0]
    phi = d - offset                                            # > 0 outside, < 0 in the wall
    hidden = ~outside & ~wall                                   # cavities the fill cannot reach: solid
    phi[hidden] = -np.abs(phi[hidden]) - 1e-4
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
    # make the faces point out: the gradient of phi points away from the model
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
    return out
