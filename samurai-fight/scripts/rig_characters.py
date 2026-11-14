"""Stage 3a: skeleton + skin weights for the two prepared characters.
python3 scripts/rig_characters.py build/characters.blend build/characters_rigged.blend

Bone names follow the Mixamo convention (Hips, Spine, LeftArm, ...) so Mixamo clips can be retargeted
onto this rig later. Characters face -Y, so the character's Left is +X.
Weights: bone-heat on a light proxy of the watertight shell, copied to the 400k mesh by nearest vertex,
then accessories that must stay stiff (sheathed swords) are made rigid to one bone.
"""
import bpy, sys, math, time
import numpy as np
from mathutils import Vector
from scipy.spatial import cKDTree

src, out = sys.argv[1], sys.argv[2]
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
vl = bpy.context.view_layer

# joint positions measured on the T-pose meshes (metres). Left side given; right is mirrored in X.
JOINTS = {
    'Oni': dict(
        Hips=(0, 0.00, 1.00), Spine=(0, 0.00, 1.10), Spine1=(0, -0.01, 1.22), Spine2=(0, -0.01, 1.36),
        Neck=(0, 0.02, 1.60), Head=(0, 0.02, 1.68), HeadTop_End=(0, 0.02, 1.88),
        Shoulder=(0.045, 0.03, 1.535), Arm=(0.205, 0.045, 1.56), ForeArm=(0.50, 0.05, 1.54), Hand=(0.795, 0.03, 1.515),
        HandMid=(0.895, 0.02, 1.50), Fing1=(0.925, 0.02, 1.497), Fing2=(0.955, 0.02, 1.494), FingEnd=(0.985, 0.02, 1.49),
        UpLeg=(0.11, 0.00, 0.98), Leg=(0.205, -0.02, 0.54), Foot=(0.30, 0.06, 0.10), ToeBase=(0.30, -0.07, 0.03), Toe_End=(0.30, -0.155, 0.03)),
    'Ronin': dict(
        Hips=(0, 0.02, 1.02), Spine=(0, 0.02, 1.12), Spine1=(0, 0.03, 1.25), Spine2=(0, 0.04, 1.40),
        Neck=(0, 0.06, 1.66), Head=(0, 0.06, 1.74), HeadTop_End=(0, 0.06, 1.94),
        Shoulder=(0.045, 0.07, 1.60), Arm=(0.21, 0.09, 1.63), ForeArm=(0.52, 0.085, 1.612), Hand=(0.80, -0.02, 1.592),
        HandMid=(0.90, -0.045, 1.583), Fing1=(0.93, -0.05, 1.58), Fing2=(0.96, -0.055, 1.577), FingEnd=(0.995, -0.06, 1.574),
        UpLeg=(0.11, 0.03, 1.00), Leg=(0.20, 0.01, 0.55), Foot=(0.30, 0.07, 0.11), ToeBase=(0.30, -0.07, 0.03), Toe_End=(0.30, -0.17, 0.03)),
}
# (bone, head joint, tail joint, parent, connected)
CENTRE = [('Hips', 'Hips', 'Spine', None), ('Spine', 'Spine', 'Spine1', 'Hips'), ('Spine1', 'Spine1', 'Spine2', 'Spine'),
          ('Spine2', 'Spine2', 'Neck', 'Spine1'), ('Neck', 'Neck', 'Head', 'Spine2'), ('Head', 'Head', 'HeadTop_End', 'Neck')]
SIDE = [('Shoulder', 'Shoulder', 'Arm', 'Spine2'), ('Arm', 'Arm', 'ForeArm', 'Shoulder'), ('ForeArm', 'ForeArm', 'Hand', 'Arm'),
        ('Hand', 'Hand', 'HandMid', 'ForeArm'), ('HandFingers1', 'HandMid', 'Fing1', 'Hand'), ('HandFingers2', 'Fing1', 'Fing2', 'HandFingers1'),
        ('HandFingers3', 'Fing2', 'FingEnd', 'HandFingers2'),
        ('UpLeg', 'UpLeg', 'Leg', 'Hips'), ('Leg', 'Leg', 'Foot', 'UpLeg'), ('Foot', 'Foot', 'ToeBase', 'Leg'), ('ToeBase', 'ToeBase', 'Toe_End', 'Foot')]
# sheathed swords that must not bend: (segment start, segment end, radius, bone)
RIGID = {
    'Oni': [((0.14, -0.44, 1.28), (0.38, 0.52, 0.67), 0.075, 'Hips')],
    'Ronin': [],
}


def co_array(me):
    a = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def build_armature(name):
    J = JOINTS[name]
    arm = bpy.data.armatures.new(name + '_Rig')
    ob = bpy.data.objects.new(name + '_Rig', arm)
    bpy.data.collections['CHAR_' + name].objects.link(ob)
    vl.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones

    def add(bname, h, t, parent, sx=1):
        b = eb.new(bname)
        b.head = (J[h][0] * sx, J[h][1], J[h][2])
        b.tail = (J[t][0] * sx, J[t][1], J[t][2])
        if parent:
            b.parent = eb[parent]
            b.use_connect = (b.head - eb[parent].tail).length < 1e-4
        return b

    for bname, h, t, p in CENTRE:
        add(bname, h, t, p)
    for side, sx in (('Left', 1), ('Right', -1)):
        for bname, h, t, p in SIDE:
            add(side + bname, h, t, p if p in ('Spine2', 'Hips') else side + p, sx)
    for b in eb:                                   # consistent rolls: Z of every bone as close to world -Y (forward) as possible
        b.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.show_in_front = True
    return ob


def skin(name, rig):
    t0 = time.time()
    body = bpy.data.objects[name + '_Body']
    # light proxy of the same closed shell for bone-heat weighting
    proxy = body.copy()
    proxy.data = body.data.copy()
    proxy.name = name + '_WeightProxy'
    bpy.data.collections['CHAR_' + name].objects.link(proxy)
    m = proxy.modifiers.new('dec', 'DECIMATE')
    m.ratio = 30000 / len(proxy.data.polygons)
    dg = bpy.context.evaluated_depsgraph_get()
    pm = bpy.data.meshes.new_from_object(proxy.evaluated_get(dg))
    proxy.modifiers.clear()
    old = proxy.data
    proxy.data = pm
    bpy.data.meshes.remove(old)
    for o in sc.objects:
        o.select_set(False)
    proxy.select_set(True)
    rig.select_set(True)
    vl.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    groups = [g.name for g in proxy.vertex_groups]
    nb = len(groups)
    W = np.zeros((len(pm.vertices), nb), dtype=np.float32)
    for v in pm.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    empty = int((W.sum(1) < 1e-4).sum())
    print(f'RIG {name}: bone-heat on {len(pm.vertices)} proxy verts, groups {nb}, unweighted {empty}, {time.time() - t0:.0f}s', flush=True)
    pco = co_array(pm)
    good = W.sum(1) > 1e-4
    tree = cKDTree(pco[good])
    Wg = W[good]
    bco = co_array(body.data)
    d, idx = tree.query(bco, k=4)
    w = 1.0 / np.maximum(d, 1e-5) ** 2
    w /= w.sum(1, keepdims=True)
    BW = np.einsum('nk,nkb->nb', w, Wg[idx])
    # rigid accessories
    for a, b, r, bone in RIGID[name]:
        a, b = np.array(a), np.array(b)
        ab = b - a
        t = np.clip(((bco - a) @ ab) / (ab @ ab), 0, 1)
        dist = np.linalg.norm(bco - (a + t[:, None] * ab), axis=1)
        f = np.clip((r * 1.6 - dist) / (r * 0.6), 0, 1)[:, None]          # 1 inside r, fading to 0 at 1.6 r
        onehot = np.zeros(nb, dtype=np.float32)
        onehot[groups.index(bone)] = 1
        BW = BW * (1 - f) + onehot * f
        print(f'RIG {name}: rigid to {bone}: {int((f > 0.5).sum())} verts', flush=True)
    BW[BW < 0.01] = 0
    BW /= np.maximum(BW.sum(1, keepdims=True), 1e-8)
    body.vertex_groups.clear()
    for gi, gname in enumerate(groups):
        vg = body.vertex_groups.new(name=gname)
        col = BW[:, gi]
        nz = np.nonzero(col)[0]
        # group vertices by rounded weight so add() is called on batches, not one vertex at a time
        q = np.round(col[nz] * 200).astype(np.int32)
        for val in np.unique(q):
            vg.add(nz[q == val].tolist(), float(val) / 200, 'REPLACE')
    am = body.modifiers.new('Armature', 'ARMATURE')
    am.object = rig
    body.parent = rig
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(pm)
    print(f'RIG {name}: weights copied to {len(bco)} verts, {time.time() - t0:.0f}s', flush=True)


for nm in ('Oni', 'Ronin'):
    rig = build_armature(nm)
    skin(nm, rig)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('RIG saved', out)
