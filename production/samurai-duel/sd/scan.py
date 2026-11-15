"""Taking an image-to-3D model apart.

Tripo and similar tools return one fused surface: hat, cape, swords and body are a single skin
with one texture. This module measures things per face so regions can be told apart and cut:

  texture(face)   colour / metalness sampled from the model's own maps at the face's UV centre
  thickness(face) how far the surface is from the opposite wall (thin = hanging cloth, hat brim)
  smooth()        averaging over neighbouring faces, to remove texture speckle
  components()    connected patches of a mask, with their surface areas

Everything works on welded vertices (glTF splits vertices along UV seams).
"""
import os
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy import sparse
from scipy.sparse import csgraph


class Scan:
    def __init__(self, path, verbose=True):
        t0 = time.time()
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == "MESH"]
        if len(meshes) != 1:
            raise RuntimeError(f"expected one mesh in {path}, found {len(meshes)}")
        self.ob = meshes[0]
        bpy.context.view_layer.update()
        self.me = me = self.ob.data
        me.transform(self.ob.matrix_world)
        self.ob.matrix_world.identity()
        for o in new:
            if o is not self.ob:
                bpy.data.objects.remove(o)
        nv, nl, nf = len(me.vertices), len(me.loops), len(me.polygons)
        co = np.empty(nv * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        self.co = co.reshape(-1, 3).astype(np.float64)
        lv = np.empty(nl, dtype=np.int32)
        me.loops.foreach_get("vertex_index", lv)
        lt = np.empty(nf, dtype=np.int32)
        me.polygons.foreach_get("loop_total", lt)
        if not (lt == 3).all():
            raise RuntimeError("scan must be triangulated")
        self.tri = lv.reshape(-1, 3)
        uv = np.empty(nl * 2, dtype=np.float32)
        me.uv_layers[0].data.foreach_get("uv", uv)
        self.uv = uv.reshape(-1, 3, 2)
        _, widx = np.unique(self.co, axis=0, return_inverse=True)
        self.widx = widx.reshape(-1).astype(np.int64)
        self.nw = int(self.widx.max()) + 1
        self.wtri = self.widx[self.tri]
        P = self.co[self.tri]
        self.fcen = P.mean(axis=1)
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        ln = np.linalg.norm(n, axis=1)
        self.farea = ln * 0.5
        self.fnorm = n / np.maximum(ln, 1e-20)[:, None]
        self.nf = nf
        self._adj = None
        self.images = {im.name: im for im in bpy.data.images if im.size[0]}
        if verbose:
            lo, hi = self.co.min(0), self.co.max(0)
            print(f"SCAN {os.path.basename(path)}: {nf} tris, {self.nw} welded verts, bounds {np.round(lo, 3)} .. {np.round(hi, 3)}, {time.time() - t0:.1f}s")

    # ---------------------------------------------------------------- texture features
    def image(self, key):
        """Pixel array (H, W, 4) of the model's texture whose name contains key."""
        for name, im in self.images.items():
            if key in name:
                a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
                im.pixels.foreach_get(a)
                return a.reshape(im.size[1], im.size[0], 4)
        raise KeyError(key)

    def texture(self, key):
        """(nf, 3) colour at each face's UV centre. Blender image rows start at the bottom, like UVs."""
        a = self.image(key)
        h, w = a.shape[:2]
        fuv = self.uv.mean(axis=1)
        x = np.clip((fuv[:, 0] % 1.0) * w, 0, w - 1).astype(int)
        y = np.clip((fuv[:, 1] % 1.0) * h, 0, h - 1).astype(int)
        return a[y, x, :3].astype(np.float64)

    # ---------------------------------------------------------------- neighbourhood
    @property
    def adj(self):
        """Sparse face-to-face adjacency through shared (welded) edges."""
        if self._adj is None:
            w = self.wtri
            e = np.concatenate([w[:, [0, 1]], w[:, [1, 2]], w[:, [2, 0]]])
            e.sort(axis=1)
            key = e[:, 0] * self.nw + e[:, 1]
            face = np.tile(np.arange(self.nf), 3)
            order = np.argsort(key, kind="stable")
            ks, fs = key[order], face[order]
            same = ks[1:] == ks[:-1]
            a, b = fs[:-1][same], fs[1:][same]
            m = sparse.coo_matrix((np.ones(len(a) * 2, dtype=np.float32), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(self.nf, self.nf))
            self._adj = m.tocsr()
        return self._adj

    def smooth(self, values, iters=4):
        """Average a per-face value with its neighbours, area-weighted."""
        v = np.asarray(values, dtype=np.float64)
        w = self.farea + 1e-12
        A = self.adj
        for _ in range(iters):
            num = A @ (v * w) + v * w
            den = A @ w + w
            v = num / den
        return v

    def grow(self, mask, steps=1):
        m = np.asarray(mask, dtype=bool)
        for _ in range(steps):
            m = m | ((self.adj @ m.astype(np.float32)) > 0)
        return m

    def shrink(self, mask, steps=1):
        return ~self.grow(~np.asarray(mask, dtype=bool), steps)

    def components(self, mask):
        """Label connected patches of mask. Returns (label per face or -1, area per label), largest first."""
        idx = np.flatnonzero(mask)
        lab = np.full(self.nf, -1, dtype=np.int64)
        if len(idx) == 0:
            return lab, np.zeros(0)
        sub = self.adj[idx][:, idx]
        n, l = csgraph.connected_components(sub, directed=False)
        area = np.bincount(l, weights=self.farea[idx], minlength=n)
        order = np.argsort(-area)
        rank = np.empty(n, dtype=np.int64)
        rank[order] = np.arange(n)
        lab[idx] = rank[l]
        return lab, area[order]

    def despeckle(self, mask, min_area):
        """Flip patches of either value that are smaller than min_area."""
        m = np.asarray(mask, dtype=bool).copy()
        for val in (True, False):
            lab, area = self.components(m == val)
            small = np.flatnonzero(area < min_area)
            if len(small):
                m[np.isin(lab, small)] = not val
        return m

    # ---------------------------------------------------------------- thickness
    def thickness(self, max_dist=0.25, eps=1e-4):
        """Distance from each face centre to the first surface hit going inward (the wall behind it)."""
        t0 = time.time()
        bvh = BVHTree.FromObject(self.ob, bpy.context.evaluated_depsgraph_get())
        out = np.full(self.nf, max_dist, dtype=np.float64)
        cen, nor = self.fcen, self.fnorm
        rc = bvh.ray_cast
        for i in range(self.nf):
            n = nor[i]
            hit = rc(Vector(cen[i] - n * eps), Vector(-n), max_dist)
            if hit[0] is not None:
                out[i] = hit[3]
        print(f"  thickness: {time.time() - t0:.1f}s")
        return out

    # ---------------------------------------------------------------- output
    def paint(self, colors, name="scan_paint"):
        """Write one colour per face into a colour attribute and show it with a flat emission material."""
        me = self.me
        ca = me.color_attributes.get(name) or me.color_attributes.new(name, "BYTE_COLOR", "CORNER")
        rgba = np.ones((self.nf * 3, 4), dtype=np.float32)
        rgba[:, :3] = np.repeat(np.asarray(colors, dtype=np.float32), 3, axis=0)
        ca.data.foreach_set("color", rgba.reshape(-1))
        m = bpy.data.materials.get("MAT_ScanPaint")
        if m is None:
            m = bpy.data.materials.new("MAT_ScanPaint")
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            o = nt.nodes.new("ShaderNodeOutputMaterial")
            e = nt.nodes.new("ShaderNodeEmission")
            a = nt.nodes.new("ShaderNodeVertexColor")
            a.layer_name = name
            nt.links.new(a.outputs[0], e.inputs[0])
            nt.links.new(e.outputs[0], o.inputs[0])
        return m
