"""STAGE 2 - the two fighters, from the user's Tripo AI models (assets/glb/oni_body.glb, ronin_body.glb).

Each model arrives as one fused, un-rigged mesh in a T-pose. build_oni / build_ronin:
  1. scale it to real height, centre it, stand it on z = 0 and thin the 2M-triangle mesh
  2. fit the shared humanoid skeleton (joints.py)
  3. skin it: bone-heat weights are solved on a clean low-res voxel copy and transferred across,
     then rigid props (hat, sheathed swords) are locked to a single bone
  4. cut the sword hilts (and the Ronin's hat) off into their own objects so they can be hidden / animated
  5. add clean separate katanas for the hands (hidden until drawn)
"""
import bpy, bmesh, math, os, time
import numpy as np
from mathutils import Vector, Matrix
import lib, charlib, joints
from lib import MB, flat, ASSETS
from charlib import build_katana, bone_parent, orient

R = math.radians


# ---------------------------------------------------------------- materials for the hand katanas
def metal(name, color, rough=0.3, metallic=1.0):
    m, nt, bsdf, out = lib._new(name)
    vec, _ = lib._coords(nt, 1.0)
    nz = lib._noise(nt, 40.0, 5.0, vec)
    nt.links.new(lib._mixc(nt, 1.0, (*color, 1), lib._madd(nt, nz, 0.3, 0.75), 'MULTIPLY'), bsdf.inputs['Base Color'])
    nt.links.new(lib._madd(nt, nz, 0.2, rough - 0.1, True), bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = metallic
    return m


def wrap_mat(name, a=(0.01, 0.01, 0.012), b=(0.8, 0.8, 0.78)):
    m, nt, bsdf, out = lib._new(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    ang = lib._math(nt, 'ARCTAN2', sep.outputs['X'], sep.outputs['Y'])
    p = lib._math(nt, 'ADD', lib._math(nt, 'MULTIPLY', sep.outputs['Z'], 120.0), lib._math(nt, 'MULTIPLY', ang, 2.0))
    q = lib._math(nt, 'SUBTRACT', lib._math(nt, 'MULTIPLY', sep.outputs['Z'], 120.0), lib._math(nt, 'MULTIPLY', ang, 2.0))
    d = lib._math(nt, 'MULTIPLY', lib._math(nt, 'SINE', p), lib._math(nt, 'SINE', q))
    nt.links.new(lib._mixc(nt, lib._math(nt, 'GREATER_THAN', d, 0.25), a, b), bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.7
    return m


def pattern_mat(name, base, accent, scale=14.0, thr=0.55, rough=0.16, metallic=1.0):
    """Steel / lacquer with a flowing flame line along the length."""
    m, nt, bsdf, out = lib._new(name)
    vec, _ = lib._coords(nt, (scale, scale, scale * 0.12))
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 1.0
    n.inputs['Detail'].default_value = 2.0; n.inputs['Distortion'].default_value = 1.6
    nt.links.new(vec, n.inputs['Vector'])
    mask = lib._ramp(nt, n.outputs[0], thr, thr + 0.02)
    nt.links.new(lib._mixc(nt, mask, base, accent), bsdf.inputs['Base Color'])
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough
    return m


# ---------------------------------------------------------------- import + clean
def load_tripo(path, name, height, C, ratio=0.5):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    src = next(o for o in bpy.data.objects if o not in before and o.type == 'MESH')
    me = src.data
    me.transform(src.matrix_world)
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    s = height / (co[:, 2].max() - co[:, 2].min())
    T = Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation((-(co[:, 0].max() + co[:, 0].min()) / 2, 0, -co[:, 2].min()))
    me.transform(T)
    src.matrix_world = Matrix.Identity(4)
    if ratio < 1.0:
        d = src.modifiers.new('Dec', 'DECIMATE'); d.ratio = ratio
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    else:
        me2 = me.copy()
    me2.name = name
    me2.polygons.foreach_set('use_smooth', [True] * len(me2.polygons))
    ob = bpy.data.objects.new(name, me2)
    C.objects.link(ob)
    for o in [o for o in bpy.data.objects if o not in before and o is not ob]:
        bpy.data.objects.remove(o)
    for m in me2.materials:
        if m:
            m.name = 'MAT_' + name
    print(f'{name}: {len(me2.vertices)} verts, {len(me2.polygons)} faces')
    return ob


def delete_verts(ob, mask):
    """Remove stray geometry (generation artefacts) from a mesh."""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(mask)[0]], context='VERTS')
    bm.to_mesh(ob.data); bm.free()
    print(f'  {ob.name}: removed {int(mask.sum())} stray vertices')


def verts_np(ob):
    n = len(ob.data.vertices)
    co = np.empty(n * 3, np.float32); ob.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


# ---------------------------------------------------------------- skinning
def skin(ob, arm, C, voxel=0.022, rigid=()):
    """rigid: list of (bone, mask_fn(co) -> bool array); those vertices follow that one bone only."""
    t0 = time.time()
    arm.data.bones['root'].use_deform = False
    tmp = bpy.data.objects.new(ob.name + '_proxy_src', ob.data)
    C.objects.link(tmp)
    rm = tmp.modifiers.new('Remesh', 'REMESH'); rm.mode, rm.voxel_size = 'VOXEL', voxel
    dg = bpy.context.evaluated_depsgraph_get()
    pme = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    # bone heat needs one connected shell: drop any loose voxel islands (stray sword / cloth bits)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ne, nv = len(pme.edges), len(pme.vertices)
    e = np.empty(ne * 2, np.int32); pme.edges.foreach_get('vertices', e); e = e.reshape(-1, 2)
    nc, lab = connected_components(coo_matrix((np.ones(ne), (e[:, 0], e[:, 1])), shape=(nv, nv)), directed=False)
    if nc > 1:
        keep = np.argmax(np.bincount(lab))
        bm = bmesh.new(); bm.from_mesh(pme); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(lab != keep)[0]], context='VERTS')
        bm.to_mesh(pme); bm.free()
        print(f'  proxy: removed {nc - 1} loose islands')
    proxy = bpy.data.objects.new(ob.name + '_proxy', pme)
    C.objects.link(proxy)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    proxy.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    names = [g.name for g in proxy.vertex_groups]
    print(f'  proxy {len(pme.vertices)} verts, groups {len(names)}')
    # transfer weights: inverse-distance blend of the 4 nearest proxy vertices
    from scipy.spatial import cKDTree
    pw = np.zeros((len(pme.vertices), len(names)), np.float32)
    for v in pme.vertices:
        for g in v.groups:
            pw[v.index, g.group] = g.weight
    co = verts_np(ob)
    dist, idx = cKDTree(verts_np(proxy)).query(co, k=4)
    wgt = 1.0 / np.maximum(dist, 1e-5) ** 2
    wgt /= wgt.sum(1, keepdims=True)
    W = (pw[idx] * wgt[:, :, None]).sum(1)
    for bone, fn in rigid:
        m = fn(co)
        W[m] = 0
        W[m, names.index(bone)] = 1
    # keep the 4 strongest influences, normalise
    order = np.argsort(-W, 1)[:, :4]
    top = np.take_along_axis(W, order, 1)
    top[top < 0.02] = 0
    top /= np.maximum(top.sum(1, keepdims=True), 1e-6)
    ob.vertex_groups.clear()
    vgs = [ob.vertex_groups.new(name=n) for n in names]
    for gi in range(len(names)):
        for k in range(4):
            sel = np.nonzero((order[:, k] == gi) & (top[:, k] > 0))[0]
            if not len(sel):
                continue
            wv = np.round(top[sel, k], 2)
            for val in np.unique(wv):
                vgs[gi].add(sel[wv == val].tolist(), float(val), 'REPLACE')
    bpy.data.objects.remove(proxy)
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm
    print(f'  skinned in {time.time() - t0:.0f}s')
    return co


def split_off(ob, mask, name, C):
    """Move the masked vertices' faces into a new object (same skinning, same material)."""
    g = ob.vertex_groups.new(name='CUT_' + name)
    g.add(np.nonzero(mask)[0].tolist(), 1.0, 'REPLACE')
    part = bpy.data.objects.new(name, ob.data.copy())
    C.objects.link(part)
    part.parent = ob.parent
    for vg in ob.vertex_groups:
        part.vertex_groups.new(name=vg.name)
    for target, inv in ((part, False), (ob, True)):
        mk = target.modifiers.new('Mask', 'MASK'); mk.vertex_group, mk.invert_vertex_group = 'CUT_' + name, inv
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(target.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        target.modifiers.remove(mk)
        old = target.data
        target.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    part.data.name = name
    md = part.modifiers.new('Armature', 'ARMATURE'); md.object = ob.parent
    return part


def hand_katana(name, C, mats, arm, side):
    """Clean katana held in the fist: handle crosses the palm, blade leaves the thumb side."""
    ko, so = build_katana(name, C, mats)
    bpy.data.objects.remove(so)
    hb = arm.data.bones['hand.' + side]
    sx = 1 if side == 'L' else -1
    grip = (hb.head_local + hb.tail_local) / 2 + Vector((sx * 0.02, 0, -0.035))
    ko.matrix_world = Matrix.Translation(grip) @ orient((0, -1, 0), (0, 0, -1)) @ Matrix.Translation((0, 0, 0.11))
    bpy.context.view_layer.update()
    bone_parent(ko, arm, 'hand.' + side)
    ko.hide_render = ko.hide_viewport = True
    return ko


# ---------------------------------------------------------------- the two fighters
def build_oni(C):
    ob = load_tripo(os.path.join(ASSETS, 'glb', 'oni_body.glb'), 'Oni_Body', joints.ONI_H, C)
    arm = charlib.make_armature('Oni_Rig', charlib.humanoid_bones(joints.J_ONI), C)
    hilt = lambda c: (c[:, 1] < -0.265) & (c[:, 2] > 1.17) & (c[:, 2] < 1.42) & (c[:, 0] > 0.02) & (c[:, 0] < 0.40)
    saya = lambda c: ((c[:, 1] > 0.235) & (c[:, 2] > 0.62) & (c[:, 2] < 1.12) & (c[:, 0] > 0.05)) | hilt(c)
    head = lambda c: (c[:, 2] > 1.80)
    def whole_sword(c):
        # everything within 5.5 cm of the straight line through the hilt and the scabbard tip
        a, b = c[hilt(c)].mean(0), c[(c[:, 1] > 0.30) & (c[:, 2] > 0.62) & (c[:, 2] < 1.0) & (c[:, 0] > 0.05)].mean(0)
        d = (b - a) / np.linalg.norm(b - a)
        t = (c - a) @ d
        dist = np.linalg.norm((c - a) - np.outer(t, d), axis=1)
        return (dist < 0.055) & (t > -0.35) & (t < np.linalg.norm(b - a) + 0.25) | saya(c)
    co = skin(ob, arm, C, rigid=[('hips', whole_sword), ('head', head)])
    out = {'rig': arm, 'body': ob}
    out['hilt'] = split_off(ob, hilt(co), 'Oni_SheathedHilt', C)
    kmats = [pattern_mat('MAT_Oni_Blade', (0.03, 0.03, 0.035), (0.86, 0.80, 0.62)), metal('MAT_Oni_Gold', (0.83, 0.60, 0.26)),
             wrap_mat('MAT_Oni_Wrap'), metal('MAT_Oni_Fitting', (0.02, 0.02, 0.022), 0.4), metal('MAT_Oni_SayaUnused', (0.02, 0.02, 0.02)),
             flat('MAT_Oni_Cord', (0.5, 0.02, 0.015), 0.8)]
    out['katana'] = hand_katana('Oni_Katana', C, kmats, arm, 'R')
    return out


def build_ronin(C):
    ob = load_tripo(os.path.join(ASSETS, 'glb', 'ronin_body.glb'), 'Ronin_Body', joints.RONIN_H, C)
    c0 = verts_np(ob)
    # the generator left a loose blade shard behind the right arm: cut it away
    delete_verts(ob, (c0[:, 2] > 1.40) & (c0[:, 2] < 1.72) & (((c0[:, 0] < -0.30) & (c0[:, 1] > 0.122)) | ((c0[:, 0] < -0.52) & (c0[:, 1] > 0.095))))
    arm = charlib.make_armature('Ronin_Rig', charlib.humanoid_bones(joints.J_RONIN), C)
    hat = lambda c: (c[:, 2] > 1.868) & (np.hypot(c[:, 0], c[:, 1] + 0.02) < 0.26)
    hilts = lambda c: (c[:, 2] > 1.72) & (np.abs(c[:, 0]) > 0.19) & (c[:, 1] > 0.150)
    swords = lambda c: ((c[:, 1] > 0.165) & (c[:, 2] > 0.80)) | hilts(c)
    head = lambda c: (c[:, 2] > 1.74) & (np.abs(c[:, 0]) < 0.17) & (c[:, 1] < 0.11) | hat(c)
    co = skin(ob, arm, C, rigid=[('head', head), ('chest', swords)])
    out = {'rig': arm, 'body': ob}
    out['hilt_L'] = split_off(ob, hilts(co) & (co[:, 0] > 0), 'Ronin_SheathedHilt_L', C)
    co2 = verts_np(ob)
    out['hilt_R'] = split_off(ob, hilts(co2) & (co2[:, 0] < 0), 'Ronin_SheathedHilt_R', C)
    co3 = verts_np(ob)
    out['hat'] = split_off(ob, hat(co3), 'Ronin_Hat', C)
    kmats = [pattern_mat('MAT_Ronin_Blade', (0.03, 0.03, 0.035), (0.85, 0.86, 0.88)), metal('MAT_Ronin_Fitting', (0.55, 0.56, 0.58)),
             wrap_mat('MAT_Ronin_Wrap'), metal('MAT_Ronin_Dark', (0.02, 0.02, 0.022), 0.4), metal('MAT_Ronin_SayaUnused', (0.02, 0.02, 0.02)),
             flat('MAT_Ronin_Cord', (0.05, 0.05, 0.05), 0.8)]
    for side in ('L', 'R'):
        out['katana_' + side] = hand_katana('Ronin_Katana_' + side, C, kmats, arm, side)
    return out


def draw_swords(ch, drawn=True):
    """Swap between sheathed (fused hilts visible) and drawn (hand katanas visible)."""
    for k, o in ch.items():
        if k.startswith('hilt'):
            o.hide_render = o.hide_viewport = drawn
        if k.startswith('katana'):
            o.hide_render = o.hide_viewport = not drawn
