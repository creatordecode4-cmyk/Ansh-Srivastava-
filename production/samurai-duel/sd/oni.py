"""Character A, the Oni Samurai, built from the user's Tripo model.

The Tripo model is one fused skin: body with mask and hair, armour, hakama, and a sheathed
katana tied to the left hip. The film needs the sword to be drawn, so it must be its own object:

  measured  the line the katana lies on (it becomes the seat of the separate scabbard)
  removed   the katana, its scabbard, the chain and charm that tie it to the hip
  rebuilt   everything below the waist on the wearer's left as a mirror image of the right
            side, which never had a sword on it

The cut runs through the black waist wrap, where a seam does not show. Katana, scabbard and
their tassels are built in sd/weapons.py and placed in sd/fighters.py.
"""
import json
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

from . import core
from . import ronin as surgery          # shared cutting tools live there
from . import scan as scanlib

SRC = os.path.join(core.ASSETS, "user", "glb_5c88c26e", "model.glb")
CACHE = os.path.join(core.ASSETS, "gen", "oni_body.blend")
FEAT = os.path.join(core.ASSETS, "gen", "oni_feat.npz")
HEIGHT = 2.02                    # metres to the tips of the horns; the top of the head is near 1.92

P = dict(
    waist=0.672,                 # model units: just above the grip of the sheathed sword, inside the black waist wrap
    patch_sides=600,
)


def _thickness(s):
    if os.path.exists(FEAT) and os.path.getmtime(FEAT) > os.path.getmtime(SRC):
        f = np.load(FEAT)
        if len(f["thick"]) == s.nf:
            return f["thick"].astype(np.float64)
    thick = s.thickness(0.25)
    os.makedirs(os.path.dirname(FEAT), exist_ok=True)
    np.savez_compressed(FEAT, thick=thick.astype(np.float32))
    return thick


def build_body(verbose=True):
    """Analyse and cut the Tripo model. Returns (object in model units, anchors dict in model units)."""
    t0 = time.time()
    s = scanlib.Scan(SRC, verbose)
    thick = s.smooth(_thickness(s), 2)
    x, y, z = s.fcen.T
    # the sheathed katana: the longest straight thin thing on the wearer's left at hip height
    cand = (x > 0.06) & (z > 0.36) & (z < 0.74) & (thick > 0.003) & (thick < 0.03)
    c, d, a, b, _ = surgery._fit_line(s.fcen[cand], np.random.default_rng(2), tol=0.010, min_len=0.25, tries=2500)
    sword = surgery._near_line(s, (c, d, a, b), 0.032, 0.04)
    keep = ~(sword & (z > P["waist"] - 0.002))                 # whatever of it reaches above the cut; the rest goes with the mirror
    me = surgery._mesh(s, keep, "OniBody")
    me.materials.append(s.me.materials[0])
    me.materials.append(surgery._simple_mat("MAT_Oni_Patch", (0.02, 0.02, 0.022), 0.0, 0.6))
    bm = bmesh.new()
    bm.from_mesh(me)
    surgery._mirror_lower(bm, P["waist"], keep=-1, verbose=verbose)
    surgery._patch(bm, 1, P["patch_sides"], back_plates=False, verbose=verbose)
    bm.to_mesh(me)
    bm.free()
    surgery._drop_small_islands(me, verbose=verbose)
    ob = bpy.data.objects.new("OniBody", me)
    for col in s.ob.users_collection:
        col.objects.link(ob)
    bpy.data.objects.remove(s.ob)
    anchors = dict(top=float(s.co[:, 2].max()), sword=dict(centre=[float(v) for v in c], dir=[float(v) for v in d], t=[a, b]))
    if verbose:
        print(f"  sword line: grip end {np.round(c + d * b, 3)}, tip {np.round(c + d * a, 3)}, length {b - a:.3f}")
        print(f"  body: {len(me.polygons)} faces, {time.time() - t0:.1f}s")
    return ob, anchors


def load_body(col=None, rebuild=False, verbose=True):
    """The cut body in metres (feet on z = 0, facing -Y) plus its anchors in metres. Cached in assets/gen."""
    meta = CACHE.replace(".blend", ".json")
    if rebuild or not (os.path.exists(CACHE) and os.path.exists(meta)) or os.path.getmtime(CACHE) < os.path.getmtime(__file__):
        ob, a = build_body(verbose)
        k = HEIGHT / a["top"]
        ob.data.transform(Matrix.Scale(k, 4))
        a = dict(scale=k, top=a["top"] * k,
                 sword=dict(centre=[v * k for v in a["sword"]["centre"]], dir=a["sword"]["dir"], t=[v * k for v in a["sword"]["t"]]))
        px, cl = surgery._proxy(ob, verbose=verbose, tag="Oni")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        bpy.data.libraries.write(CACHE, {ob, px, cl}, fake_user=True)
        with open(meta, "w") as fh:
            json.dump(a, fh, indent=1)
        for o in (ob, px, cl):
            bpy.data.objects.remove(o)
    with bpy.data.libraries.load(CACHE) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("OniBody", "OniProxy", "OniCollider")]
    obs = {o.name.split(".")[0]: o for o in dst.objects}
    ob = obs["OniBody"]
    (col or bpy.context.scene.collection).objects.link(ob)
    with open(meta) as fh:
        anchors = json.load(fh)
    anchors["proxy"] = obs["OniProxy"].name
    anchors["collider"] = obs["OniCollider"].name
    return ob, anchors
