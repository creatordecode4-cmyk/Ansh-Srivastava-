"""Rocks, cherry blossom trees and background pines.

Rocks: Poly Haven CC0 scans plus angular rubble blocks made here (BROKEN ROCK DEBRIS on the
props sheet). Cherry trees: a branching skeleton turned into tubes, with blossom clusters
instanced on the outer branches (CHERRY BLOSSOM TREE BRANCH on the props sheet).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from . import core, mats
from . import polyhaven as ph
from .mats import NT

PETAL_TIP_A = (0.90, 0.66, 0.74, 1)     # pale pink petal blade (two tones, picked per cluster)
PETAL_TIP_B = (0.80, 0.50, 0.62, 1)
PETAL_HEART = (0.52, 0.10, 0.22, 1)     # deep magenta at the flower centre
PETAL_GLOW = 0.035
# rounded sakura petal with the notch at the tip (x across, y along, z = cupping), unit length
PETAL_OUTLINE = [(0.0, 0.0, 0.0), (-0.30, 0.22, 0.06), (-0.47, 0.50, 0.14), (-0.42, 0.78, 0.24), (-0.20, 0.97, 0.32), (0.0, 0.86, 0.28),
                 (0.20, 0.97, 0.32), (0.42, 0.78, 0.24), (0.47, 0.50, 0.14), (0.30, 0.22, 0.06)]


# ----------------------------------------------------------------------------- rocks
def _import_rocks(asset, lib, prefix):
    path = ph.model(asset, "1k")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    out = []
    for o in new:
        if o.type != "MESH" or len(o.data.polygons) < 20:
            continue
        bpy.context.view_layer.update()
        me = o.data.copy()
        me.transform(o.matrix_world)
        co = np.array([v.co[:] for v in me.vertices])
        lo, hi = co.min(0), co.max(0)
        me.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2] - 0.12 * (hi[2] - lo[2]))))
        ob = bpy.data.objects.new(f"{prefix}_{len(out) + 1:02d}", me)
        lib.objects.link(ob)
        core.set_mat(ob, mats.stone_rock())
        ob["size"] = float(max(hi - lo))
        out.append(ob)
    for o in new:
        bpy.data.objects.remove(o)
    return out


def _rubble_block(lib, name, seed):
    """Angular chunk of broken masonry: a block with corners sheared off."""
    r = core.rng(seed)
    sx, sy, sz = r.uniform(0.35, 0.95), r.uniform(0.3, 0.7), r.uniform(0.22, 0.5)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    for _ in range(r.randint(2, 4)):
        n = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.2, 1))).normalized()
        co = n * r.uniform(0.18, 0.34) * min(sx, sy, sz) * 1.6
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=n, clear_outer=True)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=(0, 0, sz / 2 - 0.05), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    lib.objects.link(ob)
    core.bevel_mod(ob, 0.02, 2, 25)
    core.subdivide(ob, 2, simple=True)
    core.displace(ob, 0.035, 0.18, "CLOUDS", 3)
    core.smooth(ob, 50)
    core.set_mat(ob, mats.stone_rock())
    ob["size"] = max(sx, sy, sz)
    return ob


def rock_set(lib):
    """Master rocks: scanned boulders and stones + angular rubble blocks."""
    rocks = []
    for asset, prefix in (("rock_moss_set_01", "PROP_Rock_A"), ("rock_moss_set_02", "PROP_Rock_B"), ("rock_07", "PROP_Rock_C"), ("rock_09", "PROP_Rock_D")):
        try:
            rocks += _import_rocks(asset, lib, prefix)
        except Exception as e:  # scans are optional: rubble blocks alone still dress the set
            print("rock import failed", asset, e)
    rocks += [_rubble_block(lib, f"PROP_Rubble_{i + 1:02d}", 40 + i) for i in range(7)]
    return rocks


# ----------------------------------------------------------------------------- cherry trees
def _petal_mat():
    """Sakura petal: pale, slightly bluish pink that deepens to magenta at the flower centre
    (the UV map runs 0 at the petal base to 1 at the notched tip)."""
    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree)
        b = m.node_tree.nodes["Principled BSDF"]
        oi = nt.new("ShaderNodeObjectInfo")
        uv = nt.new("ShaderNodeUVMap")
        sep = nt.new("ShaderNodeSeparateXYZ")
        nt.link(uv.outputs[0], sep.inputs[0])
        tip = nt.mix(oi.outputs["Random"], PETAL_TIP_A, PETAL_TIP_B)
        col = nt.mix(nt.map_range(sep.outputs[1], 0.02, 0.6), PETAL_HEART, tip)
        nt.put(b.inputs["Base Color"], col)
        b.inputs["Roughness"].default_value = 0.6
        b.inputs["Subsurface Weight"].default_value = 0.5     # thin petals let light through
        b.inputs["Subsurface Radius"].default_value = (0.02, 0.008, 0.01)
        b.inputs["Subsurface Scale"].default_value = 1.0
        b.inputs["Sheen Weight"].default_value = 0.2
        nt.put(b.inputs["Emission Color"], col)          # a whisper of self-light so shaded blossoms do not go black
        b.inputs["Emission Strength"].default_value = PETAL_GLOW
        return m

    return mats.get("MAT_Petal_Sakura", build)


def _petal_uv(x, y):
    return (x + 0.5, y)


def petal_mesh(name, lib, length=0.03, width=0.022):
    """One cupped petal with a notched tip."""
    k = width / (0.94 * length)
    verts = [(x * length * k, y * length, z * length) for x, y, z in PETAL_OUTLINE]
    ob = core.mesh_obj(name, verts, [(0, i + 1, i) for i in range(1, len(verts) - 1)], lib)
    uvl = ob.data.uv_layers.new(name="UVMap")
    for lp in ob.data.loops:
        x, y, _ = PETAL_OUTLINE[lp.vertex_index]
        uvl.data[lp.index].uv = _petal_uv(x, y)
    core.smooth(ob, 180)
    core.set_mat(ob, _petal_mat())
    return ob


def blossom_cluster(lib, name="PROP_BlossomCluster", flowers=16, radius=0.2, seed=0):
    """A puff of five-petal flowers; instanced thousands of times per tree."""
    ob = bpy.data.objects.get(name)
    if ob:
        return ob
    r = core.rng(seed)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for _ in range(flowers):
        c = Vector((r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 1)))
        c = c.normalized() * radius * r.random() ** 0.5
        axis = (c.normalized() + Vector((r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(-0.2, 0.9)))).normalized()
        q = Vector((0, 0, 1)).rotation_difference(axis).to_matrix()
        fr = r.uniform(0.035, 0.055)
        for k in range(5):
            a = k * 2 * math.pi / 5 + r.uniform(-0.15, 0.15)
            rot = q @ Matrix.Rotation(a, 3, "Z")
            vs = [bm.verts.new(c + rot @ Vector((x * fr, y * fr, z * fr))) for x, y, z in PETAL_OUTLINE]
            for i in range(1, len(vs) - 1):
                f = bm.faces.new((vs[0], vs[i + 1], vs[i]))
                for lp, j in zip(f.loops, (0, i + 1, i)):
                    lp[uvl].uv = _petal_uv(*PETAL_OUTLINE[j][:2])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    lib.objects.link(ob)
    core.smooth(ob, 180)
    core.set_mat(ob, _petal_mat())
    return ob


def cherry_tree(lib, col, seed=1, height=6.0, crown=3.2, name=None, density=1.0, loc=(0, 0, 0), yaw=0.0):
    """Sakura: short thick trunk, a few big limbs spreading into a wide umbrella, side branches
    all along each limb, twigs that droop, and blossom clusters crowding the outer wood."""
    name = name or f"Cherry_{seed:02d}"
    r = core.rng(seed * 101 + 7)
    branches = []   # (points, radii, depth)

    def path(p, d, length, rad, depth, n, up, wobble, taper=0.72):
        pts, rr = [p.copy()], [rad]
        cur, dirn = p.copy(), d.normalized()
        for i in range(n):
            wob = Vector((r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 0.5))) * wobble
            dirn = (dirn + wob + Vector((0, 0, up))).normalized()
            cur = cur + dirn * (length / n)
            pts.append(cur.copy())
            rr.append(max(0.006, rad * (1 - taper * (i + 1) / n)))
        branches.append((pts, rr, depth))
        return pts, rr

    def side_dir(tangent, az, ang):
        side = Matrix.Rotation(az, 3, tangent) @ tangent.orthogonal().normalized()
        return (tangent * math.cos(ang) + side * math.sin(ang)).normalized()

    def laterals(pts, rr, depth, length, count):
        """Side branches all along a parent, shorter toward its tip."""
        if depth > 3:
            return
        for k in range(count):
            t = (k + r.uniform(0.3, 0.9)) / count * 0.9 + 0.08
            i = min(len(pts) - 2, int(t * (len(pts) - 1)))
            f = t * (len(pts) - 1) - i
            p = pts[i].lerp(pts[i + 1], f)
            tan = (pts[i + 1] - pts[i]).normalized()
            d = side_dir(tan, r.uniform(0, 6.28), r.uniform(0.6, 1.15))
            ln = length * (1.0 - 0.55 * t) * r.uniform(0.7, 1.1)
            rad = max(0.008, rr[i] * r.uniform(0.38, 0.52))
            cp, cr = path(p, d, ln, rad, depth, 5 if depth < 3 else 4, 0.12 if depth < 2 else -0.16, 0.2)
            laterals(cp, cr, depth + 1, ln * 0.5, max(2, int(count * 0.75)))

    trunk_r = 0.055 * height ** 0.95
    lean = Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 1)).normalized()
    tp, tr = path(Vector((0, 0, -0.15)), lean, height * 0.24, trunk_r, 0, 4, 0.3, 0.07, taper=0.3)
    limbs = r.randint(4, 6)
    for k in range(limbs):
        az = k * 2 * math.pi / limbs + r.uniform(-0.35, 0.35)
        el = r.uniform(0.5, 0.95)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        lp, lr = path(tp[-1] - Vector((0, 0, 0.1)), d, height * r.uniform(0.75, 0.95), tr[-1] * r.uniform(0.5, 0.66), 1, 7, 0.1, 0.16, taper=0.8)
        laterals(lp, lr, 2, height * 0.45, 8)

    # fit the skeleton to the requested crown radius and height
    allp = [p for b_ in branches for p in b_[0]]
    cr = max(math.hypot(p.x, p.y) for p in allp) or 1.0
    hz = max(p.z for p in allp) or 1.0
    sxy, sz = crown / cr, height / hz
    for pts, rr, depth in branches:
        for p in pts:
            p.x *= sxy
            p.y *= sxy
            if p.z > 0:
                p.z *= sz

    tmp = core.collection("_tmp_build")
    tubes = [core.tube("br", pts, rr, tmp, segs=10 if depth < 2 else (6 if depth < 3 else 4), cap=False) for pts, rr, depth in branches]
    wood = core.join(tubes, name + "_wood")
    core.smooth(wood, 70)
    core.set_mat(wood, mats.bark())
    core.link(wood, col)

    cluster = blossom_cluster(lib)
    spots = []
    for pts, rr, depth in branches:
        if depth < 2:
            continue
        for i in range(len(pts) - 1):
            seg = pts[i + 1] - pts[i]
            for _ in range(max(1, int(seg.length / 0.055 * density * (0.6 if depth == 2 else 1.0)))):
                spots.append(pts[i] + seg * r.random() + Vector((r.gauss(0, 0.2), r.gauss(0, 0.2), r.gauss(0, 0.16))))
    xf = [(s, Euler((r.uniform(0, 6.28), r.uniform(0, 6.28), r.uniform(0, 6.28))).to_matrix(), r.uniform(0.7, 1.3)) for s in spots]
    bl = core.face_instancer(name + "_blossoms", cluster, xf, col)
    root = core.group(name, col, [wood, bl], loc=loc, yaw=yaw)
    root["blossoms"] = len(spots)
    print(f"  {name}: {len(branches)} branches, {len(spots)} blossom clusters")
    return root


# ----------------------------------------------------------------------------- pines (far background silhouettes)
def pine_tree(lib, name="PROP_Pine", seed=0, height=12.0):
    """Conifer for the tree line: whorls of drooping, uneven boughs so the outline is ragged."""
    r = core.rng(seed)
    tmp = core.collection("_tmp_build")
    lean = (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3))
    trunk = core.tube("trunk", [(0, 0, 0), (lean[0] * 0.5, lean[1] * 0.5, height * 0.5), (lean[0], lean[1], height)], [0.3, 0.17, 0.03], tmp, segs=8)
    core.set_mat(trunk, mats.bark())
    bm = bmesh.new()
    tiers = r.randint(10, 13)
    for i in range(tiers):
        t = i / (tiers - 1)
        z = height * (0.2 + 0.78 * t)
        rmax = height * 0.23 * (1 - t) ** 0.85 + 0.3
        n = r.randint(5, 7)
        a0 = r.uniform(0, 6.28)
        for k in range(n):
            if r.random() < 0.12:
                continue                      # missing bough
            L = rmax * r.uniform(0.7, 1.2)
            az = a0 + k * 2 * math.pi / n + r.uniform(-0.3, 0.3)
            droop = r.uniform(0.2, 0.55)
            geom = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)["verts"]
            m = (Matrix.Translation((lean[0] * t, lean[1] * t, z)) @ Matrix.Rotation(az, 4, "Z") @ Matrix.Rotation(droop, 4, "Y")
                 @ Matrix.Translation((L * 0.5, 0, 0)) @ Matrix.Diagonal((L * 0.56, L * r.uniform(0.26, 0.4), L * r.uniform(0.09, 0.16), 1.0)))
            bmesh.ops.transform(bm, matrix=m, verts=geom)
    geom = bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.45, radius2=0.02, depth=height * 0.12)["verts"]
    bmesh.ops.translate(bm, vec=(lean[0], lean[1], height * 1.0), verts=geom)
    me = bpy.data.meshes.new("foliage")
    bm.to_mesh(me)
    bm.free()
    foliage = bpy.data.objects.new("foliage", me)
    tmp.objects.link(foliage)
    core.subdivide(foliage, 1, simple=True)
    core.displace(foliage, 0.45, 0.55, "CLOUDS", 3)
    core.displace(foliage, 0.16, 0.14, "CLOUDS", 2)
    core.set_mat(foliage, mats.get("MAT_Pine_Foliage", mats.surface, None, base=(0.010, 0.02, 0.013), rough=1.0, rough_min=0.6, wet=0.2, snow=0.5, moss=0.0))
    ob = core.join([trunk, foliage], f"{name}_{seed:02d}")
    core.smooth(ob, 60)
    core.link(ob, lib)
    return ob
