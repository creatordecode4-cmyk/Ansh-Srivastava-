"""Character B, the Cyber Ronin, built from the user's Tripo model.

The Tripo model is one fused skin: body, kasa hat, two sheathed katanas, a short cape and a
waist cloth with long tails. The film needs the hat to be lifted and split, the swords to be
drawn and the cloth to move, so the model is taken apart here:

  kept      the robot body with its helmet, the cowl round the neck, the waist wrap and its knot
  removed   hat, both katanas, a stray third scabbard, every thin hanging sheet of cloth and
            the strands those sheets leave behind
  rebuilt   everything below the waist on the right side as a mirror of the left (the right
            thigh was fused inside a bundle of cloth), and the crown of the helmet (it was
            inside the hat)
  patched   the holes the swords left in the back armour

What is removed is replaced by separate objects built in sd/kasa.py, sd/weapons.py and
sd/garments.py, placed with the measurements returned in the anchors.

Regions are found from two measurements per face (see sd/scan.py): metalness from the model's
own texture (cloth is the only non-metal light surface) and wall thickness (hanging cloth and
the hat are thin sheets, the body is not).
"""
import json
import math
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from scipy import sparse
from scipy.sparse import csgraph

from . import core
from . import scan as scanlib

SRC = os.path.join(core.ASSETS, "user", "glb_f2a316b1", "model.glb")
CACHE = os.path.join(core.ASSETS, "gen", "ronin_body.blend")
FEAT = os.path.join(core.ASSETS, "gen", "ronin_feat.npz")
HEIGHT = 1.86                    # metres to the top of the rebuilt helmet crown

P = dict(
    cloth_metal=0.14, cloth_lum=0.30,         # cloth: non-metal and light
    thin=0.018,                               # wall thickness below this = a hanging sheet (model units, the model is ~1 tall)
    strand=0.012,                             # thin dark leftovers along the edges of removed sheets
    hat_z=0.925,
    sword_radius=0.024, sword_extend=0.03,
    waist=0.645,                              # below this height (top of the waist wrap) the right side is rebuilt from the left
    crown=0.014,                              # height of the helmet crown above the cut rim (it must fit inside the hat)
    patch_sides=900,
)


# ----------------------------------------------------------------------------- measuring
def _features(s):
    """Per-face metalness, brightness and wall thickness (cached: the ray casts take a while)."""
    if os.path.exists(FEAT) and os.path.getmtime(FEAT) > os.path.getmtime(SRC):
        f = np.load(FEAT)
        if len(f["thick"]) == s.nf:
            return f["metal"], f["lum"], f["thick"]
    rm, bc = s.texture("_rm"), s.texture("basecolor")
    metal, lum, thick = rm[:, 2], bc.mean(axis=1), s.thickness(0.25)
    os.makedirs(os.path.dirname(FEAT), exist_ok=True)
    np.savez_compressed(FEAT, metal=metal.astype(np.float32), lum=lum.astype(np.float32), thick=thick.astype(np.float32))
    return metal, lum, thick


def _fit_line(pts, rng, tol=0.011, min_len=0.25, tries=1500):
    """Best straight line through a cloud (RANSAC, then a least-squares refit). Returns (centre, dir, t0, t1, inliers)."""
    best_n, best = 0, None
    for _ in range(tries):
        a, b = pts[rng.integers(len(pts), size=2)]
        d = b - a
        ln = np.linalg.norm(d)
        if ln < min_len:
            continue
        d = d / ln
        v = pts - a
        n = int((np.linalg.norm(v - np.outer(v @ d, d), axis=1) < tol).sum())
        if n > best_n:
            best_n, best = n, (a.copy(), d.copy())
    if best is None:
        return None
    a, d = best
    v = pts - a
    inl = np.linalg.norm(v - np.outer(v @ d, d), axis=1) < tol * 1.1
    Q = pts[inl]
    c = Q.mean(0)
    d = np.linalg.svd(Q - c, full_matrices=False)[2][0]
    d = d if d[2] > 0 else -d                         # pointing up, toward the grip
    t = (Q - c) @ d
    return c, d, float(t.min()), float(t.max()), inl


def _near_line(s, line, radius, extend):
    c, d, t0, t1 = line[:4]
    v = s.fcen - c
    t = v @ d
    dist = np.linalg.norm(v - np.outer(t, d), axis=1)
    return (dist < radius) & (t > t0 - extend) & (t < t1 + extend)


def _labels(s, verbose=True):
    metal, lum, thick = _features(s)
    metal, lum, thick = s.smooth(metal, 6), s.smooth(lum, 4), s.smooth(thick, 2)
    x, y, z = s.fcen.T
    cloth = s.despeckle((metal < P["cloth_metal"]) & (lum > P["cloth_lum"]), 4e-4)
    sheet = s.despeckle(cloth & (thick < P["thin"]), 3e-4)
    lab, _ = s.components((thick < P["thin"]) & (z > P["hat_z"]) & ~cloth)
    hat = lab == 0
    hc = np.array([np.average(x[hat], weights=s.farea[hat]), np.average(y[hat], weights=s.farea[hat])])
    hat_r = float(np.hypot(x[hat] - hc[0], y[hat] - hc[1]).max())

    # the two katanas: straight lines through the thin metal carried behind the back
    rng = np.random.default_rng(1)
    cand = (~cloth) & (thick > 0.004) & (thick < 0.034) & (y > 0.045) & (z > 0.25) & ~hat
    pts = s.fcen[cand]
    lines = []
    for _ in range(2):
        c, d, t0, t1, inl = _fit_line(pts, rng)
        lines.append((c, d, t0, t1))
        pts = pts[~inl]
    sword = np.zeros(s.nf, dtype=bool)
    for ln in lines:
        sword |= _near_line(s, ln, P["sword_radius"], P["sword_extend"]) & (thick < 0.045) & ~cloth
    # a third, short scabbard the generator invented at the back of the right hip: not in the design
    box = (~cloth) & ~sword & (thick > 0.004) & (thick < 0.034) & (x < -0.07) & (y > 0.03) & (z > 0.36) & (z < 0.62)
    stray = np.zeros(s.nf, dtype=bool)
    if box.sum() > 2000:
        third = _fit_line(s.fcen[box], rng, tol=0.010, min_len=0.08, tries=800)
        if third is not None and third[3] - third[2] > 0.09:
            stray = _near_line(s, third, 0.021, 0.02) & (thick < 0.04) & ~cloth & (x < -0.05)
    sword = s.despeckle(sword | stray, 2e-4) & ~hat

    # strands: thin dark slivers that touch a removed sheet (the torn edge of that sheet)
    thin_dark = (~cloth) & (thick < P["strand"]) & ~hat & ~sword
    lab, area = s.components(thin_dark)
    touch = s.grow(sheet, 2)
    strand = np.zeros(s.nf, dtype=bool)
    hits = np.unique(lab[touch & (lab >= 0)])
    for k in hits:
        if area[k] < 0.012:
            strand |= lab == k
    bc = s.texture("basecolor")
    cloth_rgb = [float(v) for v in np.average(bc[cloth & ~sheet], axis=0, weights=s.farea[cloth & ~sheet])]
    if verbose:
        print(f"  cloth colour (sRGB texture mean) {np.round(cloth_rgb, 3)}")
        print(f"  labels: cloth {cloth.mean():.2f} sheet {sheet.mean():.2f} hat {hat.mean():.3f} swords {sword.mean():.3f} strands {strand.mean():.4f} of faces; hat radius {hat_r:.3f}")
    return dict(cloth=cloth, sheet=sheet, hat=hat, sword=sword, strand=strand, thick=thick, hat_centre=hc, hat_radius=hat_r, lines=lines, cloth_rgb=cloth_rgb)


# ----------------------------------------------------------------------------- cutting
def _mesh(s, keep, name, cloth=None):
    """New welded mesh from the kept faces (UVs stay per corner, so the texture still fits).
    cloth: per-face flag stored as the integer face attribute 'cloth'."""
    used, inv = np.unique(s.wtri[keep].reshape(-1), return_inverse=True)
    wco = np.zeros((s.nw, 3))
    wco[s.widx] = s.co
    tri = inv.reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(used))
    me.vertices.foreach_set("co", wco[used].reshape(-1))
    me.loops.add(len(tri) * 3)
    me.loops.foreach_set("vertex_index", tri.reshape(-1).astype(np.int32))
    me.polygons.add(len(tri))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tri) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(tri), 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.uv_layers.new(name="UVMap").data.foreach_set("uv", s.uv[keep].reshape(-1))
    me.polygons.foreach_set("use_smooth", np.ones(len(tri), dtype=bool))
    if cloth is not None:
        at = me.attributes.new("cloth", "INT", "FACE")
        at.data.foreach_set("value", cloth[keep].astype(np.int32))
    return me


def _islands(me):
    """Connected-island id per face and face count per island."""
    nl = len(me.loops)
    lv = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    face_of_loop = np.repeat(np.arange(len(ls)), lt)
    first = lv[ls][face_of_loop]                                   # link every corner's vertex to its face's first vertex
    nv = len(me.vertices)
    g = sparse.coo_matrix((np.ones(nl, dtype=np.int8), (lv, first)), shape=(nv, nv))
    n, lab = csgraph.connected_components(g, directed=False)
    fl = lab[lv[ls]]
    return fl, np.bincount(fl, minlength=n)


def _drop_small_islands(me, min_faces=3000, protect=(), verbose=True):
    """Delete loose scraps. Faces whose material index is in 'protect' always stay."""
    fl, cnt = _islands(me)
    mi = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", mi)
    small = np.flatnonzero((cnt[fl] < min_faces) & ~np.isin(mi, protect))
    if len(small):
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in small], context="FACES")
        bm.to_mesh(me)
        bm.free()
    if verbose:
        print(f"  islands: {len(cnt)} found, removed {len(small)} faces in small ones")


def _boundary_loops(bm, pick):
    """Closed loops of boundary edges whose edges satisfy pick(edge); each as an ordered list of verts."""
    edges = [e for e in bm.edges if e.is_boundary and pick(e)]
    by_vert = {}
    for e in edges:
        for v in e.verts:
            by_vert.setdefault(v, []).append(e)
    seen, loops = set(), []
    for e0 in edges:
        if e0 in seen:
            continue
        loop, e, v = [], e0, e0.verts[0]
        while e is not None and e not in seen:
            seen.add(e)
            loop.append(v)
            v = e.other_vert(v)
            nxt = [k for k in by_vert.get(v, []) if k not in seen]
            e = nxt[0] if nxt else None
        loops.append(loop)
    return loops


def _mirror_lower(bm, zm, verbose=True):
    """Rebuild the right side below z = zm as a mirror image of the left side."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zm), plane_no=(0, 0, 1), dist=1e-7)
    low = [f for f in bm.faces if f.calc_center_median().z < zm]
    lg = set()
    for f in low:
        lg.add(f)
        lg.update(f.edges)
        lg.update(f.verts)
    bmesh.ops.bisect_plane(bm, geom=list(lg), plane_co=(0, 0, 0), plane_no=(1, 0, 0), dist=1e-7)
    right = [f for f in bm.faces if (c := f.calc_center_median()).z < zm and c.x < 0]
    bmesh.ops.delete(bm, geom=right, context="FACES")
    left = [f for f in bm.faces if (c := f.calc_center_median()).z < zm and c.x > 0]
    dup = bmesh.ops.duplicate(bm, geom=left)["geom"]
    dverts = [g for g in dup if isinstance(g, bmesh.types.BMVert)]
    dfaces = [g for g in dup if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=dverts)
    bmesh.ops.reverse_faces(bm, faces=dfaces)
    seam = [v for v in bm.verts if abs(v.co.x) < 2e-6 and v.co.z < zm + 1e-5]
    for v in seam:
        v.co.x = 0.0
    bmesh.ops.remove_doubles(bm, verts=seam, dist=1e-6)
    # stitch the waistline on the right: the mirrored half ends on the plane z = zm, and so does the
    # original torso above it, but their outlines differ by the model's own asymmetry. Pull every
    # mirrored border vertex onto the nearest point of the torso's border, then weld.
    from scipy.spatial import cKDTree
    upper, lower = [], []
    for v in bm.verts:
        if abs(v.co.z - zm) < 1e-5 and v.co.x < -1e-6 and v.is_boundary:
            above = any(f.calc_center_median().z > zm for f in v.link_faces)
            (upper if above else lower).append(v)
    moved = 0
    if upper and lower:
        tree = cKDTree(np.array([v.co[:] for v in upper]))
        d, idx = tree.query(np.array([v.co[:] for v in lower]))
        for v, dist, i in zip(lower, d, idx):
            if dist < 0.035:
                v.co = upper[i].co
                moved += 1
        bmesh.ops.remove_doubles(bm, verts=upper + lower, dist=1e-6)
    if verbose:
        print(f"  mirror: removed {len(right)} faces on the right, mirrored {len(left)} from the left, welded {len(seam)} seam verts, "
              f"stitched {moved} of {len(lower)} waist verts")


def _crown_fit(bm, centre, rim_z):
    """Smoothed outline (centre, level, three Fourier harmonics of radius) of the helmet's open rim."""
    cx, cy = centre
    loops = _boundary_loops(bm, lambda e: min(v.co.z for v in e.verts) > rim_z - 0.035 and
                            all(math.hypot(v.co.x - cx, v.co.y - cy) < 0.09 for v in e.verts))
    if not loops:
        return None
    rim = max(loops, key=len)
    pts = np.array([v.co[:] for v in rim])
    mx, my, zt = pts[:, 0].mean(), pts[:, 1].mean(), float(np.percentile(pts[:, 2], 20))
    ang = np.arctan2(pts[:, 1] - my, pts[:, 0] - mx)
    rad = np.hypot(pts[:, 0] - mx, pts[:, 1] - my)
    A = np.stack([np.ones_like(ang)] + [f(k * ang) for k in (1, 2, 3) for f in (np.cos, np.sin)], axis=1)
    return dict(mx=float(mx), my=float(my), zt=zt, coef=np.linalg.lstsq(A, rad, rcond=None)[0], n=len(rim), r=float(rad.mean()))


def _crown(bm, fit, height, mat_index, rings=20, segs=128, verbose=True):
    """The top of the helmet was inside the hat and does not exist: cap it with a smooth plate
    that follows the smoothed rim and laps a few millimetres over its ragged edge."""
    if fit is None:
        print("  crown: no open rim found")
        return 0.0
    mx, my, zt = fit["mx"], fit["my"], fit["zt"]
    phi = np.linspace(0, 2 * math.pi, segs, endpoint=False)
    r = (np.stack([np.ones_like(phi)] + [f(k * phi) for k in (1, 2, 3) for f in (np.cos, np.sin)], axis=1) @ fit["coef"]) * 1.035
    lap = 0.004
    apex_z = zt + height
    prev, made = None, []
    for k in range(rings + 1):
        th = (k / rings) * math.pi / 2
        rho, up = math.cos(th) ** 0.85, math.sin(th)
        if k == rings:
            apex = bm.verts.new((mx, my, apex_z))
            for i in range(segs):
                made.append(bm.faces.new((prev[i], prev[(i + 1) % segs], apex)))
            break
        ring = [bm.verts.new((mx + r[i] * rho * math.cos(phi[i]), my + r[i] * rho * math.sin(phi[i]), zt - lap + (height + lap) * up)) for i in range(segs)]
        if prev is not None:
            for i in range(segs):
                j = (i + 1) % segs
                made.append(bm.faces.new((prev[i], prev[j], ring[j], ring[i])))
        prev = ring
    for f in made:
        f.material_index, f.smooth = mat_index, True
    bm.normal_update()
    if sum(f.normal.z for f in made) < 0:
        bmesh.ops.reverse_faces(bm, faces=made)
    if verbose:
        print(f"  crown: rim of {fit['n']} verts at z {zt:.4f}, mean radius {fit['r']:.4f}, apex {apex_z:.4f}")
    return apex_z


def _patch(bm, mat_index, sides, verbose=True):
    """Close the holes left in the armour; long ragged borders (cloth edges) stay open."""
    n0 = len(bm.faces)
    border = [e for e in bm.edges if e.is_boundary]
    bmesh.ops.holes_fill(bm, edges=border, sides=sides)
    bm.faces.ensure_lookup_table()
    new = bm.faces[n0:]
    for f in new:
        f.material_index = mat_index
        f.smooth = True
    bmesh.ops.triangulate(bm, faces=new)
    # the wounds the swords left in the back plates are not clean loops (their rims touch
    # themselves), so the simple fill skips them: close what is left open on the upper back
    back = [e for e in bm.edges if e.is_boundary and all(v.co.y > 0.05 and 0.66 < v.co.z < 0.84 and abs(v.co.x) < 0.14 for v in e.verts)]
    n1 = len(bm.faces)
    if back:
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=back)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n1:]:
            f.material_index = mat_index
            f.smooth = True
    if verbose:
        print(f"  patch: {len(border)} border edges, filled {len(new)} holes and {len(bm.faces) - n1} back-plate triangles, "
              f"{sum(1 for e in bm.edges if e.is_boundary)} border edges left open")


def _simple_mat(name, color, metallic, rough):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Metallic"].default_value = metallic
        b.inputs["Roughness"].default_value = rough
    return m


def build_body(verbose=True):
    """Analyse and cut the Tripo model. Returns (object in model units, anchors dict in model units)."""
    t0 = time.time()
    s = scanlib.Scan(SRC, verbose)
    L = _labels(s, verbose)
    z = s.fcen[:, 2]
    keep = ~(L["hat"] | L["sword"] | L["sheet"] | L["strand"])
    lab, area = s.components(keep)
    keep &= lab == 0                                         # loose scraps go; the right foot's separate sole goes with the mirror
    me = _mesh(s, keep, "RoninBody", L["cloth"])
    me.materials.append(s.me.materials[0])
    me.materials.append(_simple_mat("MAT_Ronin_Patch", (0.03, 0.03, 0.033), 1.0, 0.45))
    me.materials.append(_simple_mat("MAT_Ronin_Crown", (0.62, 0.63, 0.65), 0.85, 0.3))
    rim_z = float(z[keep & (np.hypot(s.fcen[:, 0] - L["hat_centre"][0], s.fcen[:, 1] - L["hat_centre"][1]) < 0.06)].max())
    bm = bmesh.new()
    bm.from_mesh(me)
    _mirror_lower(bm, P["waist"], verbose)
    fit = _crown_fit(bm, L["hat_centre"], rim_z)
    _patch(bm, 1, P["patch_sides"], verbose)              # this also puts a flat lid on the helmet, under the crown
    top = _crown(bm, fit, P["crown"], 2, verbose=verbose)
    bm.to_mesh(me)
    bm.free()
    _drop_small_islands(me, protect=(2,), verbose=verbose)
    ob = bpy.data.objects.new("RoninBody", me)
    for c in s.ob.users_collection:
        c.objects.link(ob)
    bpy.data.objects.remove(s.ob)
    anchors = dict(
        hat_centre=[float(v) for v in L["hat_centre"]], hat_radius=L["hat_radius"], hat_z=[float(z[L["hat"]].min()), float(z[L["hat"]].max())],
        helmet_rim=rim_z, helmet_top=top or rim_z, helmet_radius=float(fit["r"]) if fit else 0.04, cloth_rgb=L["cloth_rgb"],
        swords=[dict(centre=[float(v) for v in c], dir=[float(v) for v in d], t=[a, b]) for c, d, a, b in L["lines"]],
    )
    if verbose:
        print(f"  body: {len(me.polygons)} faces, helmet rim {rim_z:.4f}, crown {anchors['helmet_top']:.4f}, {time.time() - t0:.1f}s")
    return ob, anchors


def _proxy(ob, verbose=True):
    """Stand-ins for the body in metres: a watertight outer skin 5 mm outside the surface (what
    cloth collides with, and what the auto-rigger is given) at two densities."""
    from . import envelope
    full = envelope.build(ob.data, voxel=0.005, offset=0.005, name="RoninSkin", verbose=verbose)
    low = envelope.simplify(full, faces=24000, smooth=2, name="RoninCollider")
    mid = envelope.simplify(full, faces=90000, smooth=1, name="RoninProxy")
    bpy.data.meshes.remove(full)
    if verbose:
        print(f"  stand-ins: proxy {len(mid.polygons)} faces, collider {len(low.polygons)} faces")
    return bpy.data.objects.new("RoninProxy", mid), bpy.data.objects.new("RoninCollider", low)


def _scaled(a, k):
    return dict(
        scale=k, hat_centre=[v * k for v in a["hat_centre"]], hat_radius=a["hat_radius"] * k, hat_z=[v * k for v in a["hat_z"]],
        helmet_rim=a["helmet_rim"] * k, helmet_top=a["helmet_top"] * k, helmet_radius=a["helmet_radius"] * k, cloth_rgb=a["cloth_rgb"],
        swords=[dict(centre=[v * k for v in s_["centre"]], dir=s_["dir"], t=[v * k for v in s_["t"]]) for s_ in a["swords"]],
    )


def load_body(col=None, rebuild=False, verbose=True):
    """The cut body in metres (feet on z = 0, facing -Y) plus its anchors in metres. Cached in assets/gen."""
    meta = CACHE.replace(".blend", ".json")
    if rebuild or not (os.path.exists(CACHE) and os.path.exists(meta)) or os.path.getmtime(CACHE) < os.path.getmtime(__file__):
        ob, anchors = build_body(verbose)
        k = HEIGHT / anchors["helmet_top"]
        ob.data.transform(Matrix.Scale(k, 4))
        anchors = _scaled(anchors, k)
        px, cl = _proxy(ob, verbose=verbose)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        bpy.data.libraries.write(CACHE, {ob, px, cl}, fake_user=True)
        with open(meta, "w") as fh:
            json.dump(anchors, fh, indent=1)
        for o in (ob, px, cl):
            bpy.data.objects.remove(o)
    with bpy.data.libraries.load(CACHE) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("RoninBody", "RoninProxy", "RoninCollider")]
    obs = {o.name.split(".")[0]: o for o in dst.objects}
    ob = obs["RoninBody"]
    (col or bpy.context.scene.collection).objects.link(ob)
    with open(meta) as fh:
        anchors = json.load(fh)
    anchors["proxy"] = obs["RoninProxy"].name       # closed skin, 90k faces (for the auto-rigger); not linked to a collection yet
    anchors["collider"] = obs["RoninCollider"].name   # the same skin at 24k faces (for cloth); not linked either
    return ob, anchors
