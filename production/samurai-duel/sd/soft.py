"""Secondary motion for cloth that is part of a fused body mesh (the Oni's hakama).

The Oni's trousers came out of the image-to-3D model as one skin with his legs, so they move
like painted-on armour: every vertex follows a leg bone rigidly. Cutting a million-triangle
skin loose and simulating it is not practical, and it would also change the approved look.

Instead a coarse copy of the trousers' outer surface (a 'cage', taken from the watertight skin)
is simulated as cloth that is softly tied to where the skeleton would put it: tight at the belt
and at the gathered cuffs, loose over thigh and knee. It lags, swings and settles like heavy
cloth, and the detailed mesh rides on the cage through a Surface Deform modifier.
"""
import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import core


def _co(me):
    a = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3).astype(np.float64)


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _shin_dist(co, J):
    """Distance of every point from the nearer shin's axis (knee to ankle, continued below the ankle)."""
    out = np.full(len(co), 1e9)
    for tag in ("Left", "Right"):
        a, b = np.array(J[tag + "Leg"]), np.array(J[tag + "Foot"])
        ab = b - a
        t = np.clip(((co - a) @ ab) / (ab @ ab), 0.0, 1.4)
        out = np.minimum(out, np.linalg.norm(co - (a + t[:, None] * ab), axis=1))
    return out


def hakama(arm, body, proxy, J, col, top=1.05, cuff=0.205, faces=5200, loose=0.11, verbose=True):
    """Cage + cloth for the Oni's trousers. Returns the cage object (to be simulated like a cloth panel).

    loose  strength of the tie to the skeleton in the loosest part, as a share of a firm tie.
           0.11 lets the balloon of the trousers swing at about 1.5 cycles a second."""
    # --- the cage: the watertight skin between cuff and belt, thinned out
    me = proxy.data.copy()
    tmp = bpy.data.objects.new("tmp_cage", me)
    col.objects.link(tmp)
    if not len(tmp.vertex_groups):                      # group names live on the mesh in current Blender; older files keep them on the object
        for g in proxy.vertex_groups:
            tmp.vertex_groups.new(name=g.name)
    co = _co(me)
    ankle = (co[:, 2] < cuff + 0.06) & (_shin_dist(co, J) < 0.08)        # the bare ankle below the gathered cuff
    drop = (co[:, 2] > top + 0.03) | (co[:, 2] < cuff - 0.005) | ankle
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.flatnonzero(drop)], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    d = tmp.modifiers.new("dec", "DECIMATE")
    d.ratio = min(1.0, faces / max(1, len(me.polygons)))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cme = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    cme.name = "Oni_HakamaCage"
    cage = bpy.data.objects.new("Oni_HakamaCage", cme)
    col.objects.link(cage)
    if not len(cage.vertex_groups):
        for g in tmp.vertex_groups:
            cage.vertex_groups.new(name=g.name)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    cage.parent = arm
    am = cage.modifiers.new("Armature", "ARMATURE")
    am.object = arm
    # --- how firmly each part is tied to the skeleton: belt and cuffs tight, the balloon between them loose
    cc = _co(cme)
    z = cc[:, 2]
    tie = np.maximum(_smooth(z, top - 0.20, top - 0.02), 1.0 - _smooth(z, cuff + 0.02, cuff + 0.22))
    tie = (loose + (1.0 - loose) * tie) ** 0.25         # Blender uses the 4th power of the weight as the tie's strength
    tie[z > top - 0.02] = 1.0
    pin = cage.vertex_groups.new(name="pin")
    for i, w in enumerate(tie):
        pin.add([i], float(w), "REPLACE")
    cl = cage.modifiers.new("Cloth", "CLOTH")
    s = cl.settings
    edge = float(np.mean([(cme.vertices[e.vertices[0]].co - cme.vertices[e.vertices[1]].co).length for e in cme.edges]))
    s.quality = 8
    s.mass = 0.3 * (edge / 0.1) ** 2                    # same cloth as the Ronin's panels, on this mesh's spacing
    s.tension_stiffness = s.compression_stiffness = 15.0
    s.shear_stiffness = 5.0
    s.bending_stiffness = 2.0                           # heavy pleated cloth keeps its folds
    s.tension_damping = s.compression_damping = s.shear_damping = 5.0
    s.bending_damping = 0.5
    s.air_damping = s.mass * 9.81 / 3.5
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    s.use_dynamic_mesh = True                           # the rest shape is wherever the skeleton puts the trousers now
    s.effector_weights.gravity = 0.35                   # the modelled shape already hangs: only part of the weight is added again
    cl.collision_settings.use_collision = False
    cl.collision_settings.use_self_collision = False
    cage.hide_render = True
    cage.display_type = "WIRE"
    # --- the detailed mesh rides on the cage
    bc = _co(body.data)
    zb = bc[:, 2]
    w = (1.0 - _smooth(zb, top - 0.07, top + 0.01)) * _smooth(zb, cuff - 0.005, cuff + 0.03)
    low = zb < cuff + 0.07
    w[low] *= _smooth(_shin_dist(bc[low], J), 0.062, 0.085)              # not the ankle inside the cuff
    sel = np.flatnonzero(w > 0.004)
    vg = body.vertex_groups.get("soft") or body.vertex_groups.new(name="soft")
    for lo in np.unique(np.round(w[sel], 2)):                            # few distinct weights: add them in batches
        idx = sel[np.round(w[sel], 2) == lo]
        vg.add([int(i) for i in idx], float(lo), "REPLACE")
    sd = body.modifiers.new("Hakama", "SURFACE_DEFORM")
    sd.target = cage
    sd.vertex_group = "soft"
    sd.use_sparse_bind = True
    sd.falloff = 4.0
    cl.show_viewport = False                            # bind against the cage as the skeleton holds it at rest
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=body, active_object=body, selected_objects=[body]):
        bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    cl.show_viewport = True
    if verbose:
        print(f"    hakama cage: {len(cme.vertices)} verts, {len(cme.polygons)} faces, spacing {edge * 100:.1f} cm; "
              f"{len(sel)} body verts ride on it; bound: {sd.is_bound}")
    return cage
