"""Connected-shell analysis of an image-to-3D mesh: are accessories separate islands?
python3 -I analyze_glb.py <file.glb>
"""
import bpy, sys, numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[1])
ob = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
me = ob.data
n = len(me.vertices)
co = np.empty(n * 3, dtype=np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(n, 3)
M = np.array(ob.matrix_world, dtype=np.float32)
co = co @ M[:3, :3].T + M[:3, 3]
e = np.empty(len(me.edges) * 2, dtype=np.int32)
me.edges.foreach_get('vertices', e)
e = e.reshape(-1, 2)
# glTF import splits vertices at UV seams: weld by position first so islands mean real shells
key = np.round(co * 20000).astype(np.int64)
_, inv = np.unique(key, axis=0, return_inverse=True)
inv = inv.ravel()
nw = inv.max() + 1
g = coo_matrix((np.ones(len(e), dtype=np.int8), (inv[e[:, 0]], inv[e[:, 1]])), shape=(nw, nw))
nc, lab = connected_components(g, directed=False)
lab_v = lab[inv]
sizes = np.bincount(lab_v)
order = np.argsort(-sizes)
print(f'ISL verts {n} welded {nw} shells {nc}')
for k in order[:14]:
    p = co[lab_v == k]
    lo, hi = p.min(0), p.max(0)
    print(f'ISL shell {k:5d} verts {sizes[k]:8d} ({100 * sizes[k] / n:5.1f}%) lo {np.round(lo, 3)} hi {np.round(hi, 3)}')
print('ISL shells with <200 verts:', int((sizes < 200).sum()), ' total verts in them:', int(sizes[sizes < 200].sum()))
