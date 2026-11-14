"""Scale a Tripo model to real height, count mesh islands, and render gridded front/side orthographic views for joint placement.
   python3 scripts/landmark_glb.py assets/glb/oni_body.glb oni 2.05"""
import bpy, sys, os, math, numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw
path, tag, H = sys.argv[1], sys.argv[2], float(sys.argv[3])
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
ob = next(o for o in bpy.data.objects if o.type == 'MESH')
bpy.context.view_layer.update()
me = ob.data
n = len(me.vertices)
co = np.empty(n * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
M = np.array(ob.matrix_world)
w = co @ M[:3, :3].T + M[:3, 3]
s = H / (w[:, 2].max() - w[:, 2].min())
w = (w - [(w[:, 0].max() + w[:, 0].min()) / 2, 0, w[:, 2].min()]) * s
print('SCALE', round(s, 4), 'bounds', w.min(0).round(3), w.max(0).round(3))
try:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    e = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get('vertices', e); e = e.reshape(-1, 2)
    g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    nc, lab = connected_components(g, directed=False)
    cnt = np.bincount(lab)
    order = np.argsort(-cnt)[:14]
    print('ISLANDS', nc)
    for i in order:
        p = w[lab == i]
        print('  island', i, 'verts', cnt[i], 'lo', p.min(0).round(2), 'hi', p.max(0).round(2))
except Exception as ex:
    print('islands failed', ex)
# arm axis / slices
for x0 in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    m = (w[:, 0] > x0 - 0.01) & (w[:, 0] < x0 + 0.01) & (w[:, 2] > 0.55 * H)
    if m.sum():
        p = w[m]
        print('ARM slice x=%.1f  z %.3f..%.3f  y %.3f..%.3f  n %d' % (x0, p[:, 2].min(), p[:, 2].max(), p[:, 1].min(), p[:, 1].max(), m.sum()))
ob.matrix_world = __import__('mathutils').Matrix.Diagonal((s, s, s, 1)) @ ob.matrix_world
bpy.context.view_layer.update()
sc = bpy.context.scene
wd = bpy.data.worlds.new('w'); sc.world = wd; wd.use_nodes = True
wd.node_tree.nodes['Background'].inputs[0].default_value = (0.6, 0.62, 0.66, 1); wd.node_tree.nodes['Background'].inputs[1].default_value = 1.0
L = bpy.data.lights.new('s', 'SUN'); L.energy = 2.0; lo_ = bpy.data.objects.new('s', L); sc.collection.objects.link(lo_)
cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; SPAN = 2.3; cd.ortho_scale = SPAN
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'CYCLES'; sc.cycles.samples = 8; sc.cycles.use_denoising = True
RES = 1150
sc.render.resolution_x = sc.render.resolution_y = RES
sc.view_settings.view_transform = 'Standard'
ctr = Vector((0, 0, 1.05))
for nm, ang in (('front', 0), ('side', 90)):
    a = math.radians(ang)
    cam.location = ctr + Vector((math.sin(a), -math.cos(a), 0)) * 6
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    lo_.rotation_euler = cam.rotation_euler
    fp = os.path.join(ROOT, 'previews', f't_lm_{tag}_{nm}.png')
    sc.render.filepath = fp; bpy.ops.render.render(write_still=True)
    im = Image.open(fp).convert('RGB'); d = ImageDraw.Draw(im)
    ppm = RES / SPAN
    for k in range(-11, 12):
        v = k * 0.1
        X = RES / 2 + v * ppm
        d.line([(X, 0), (X, RES)], fill=(255, 255, 0) if k % 5 == 0 else (120, 200, 255), width=1)
        if k % 2 == 0: d.text((X + 2, 2), '%.1f' % v, fill=(255, 255, 0))
    for k in range(0, 23):
        z = k * 0.1
        Y = RES / 2 - (z - 1.05) * ppm
        d.line([(0, Y), (RES, Y)], fill=(255, 255, 0) if k % 5 == 0 else (120, 200, 255), width=1)
        d.text((2, Y + 1), '%.1f' % z, fill=(255, 255, 0))
    im.save(fp)
