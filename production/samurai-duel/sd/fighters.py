"""Assembles the two fighters from their parts.

Each fighter is a root empty with separate child objects: body, weapons, scabbards, hat, cloth.
Everything stands in the rest pose (T-pose), feet on z = 0, facing -Y, in metres.
"""
import math

import bpy
from mathutils import Matrix, Vector

from mathutils.bvhtree import BVHTree

from . import core, garments, kasa, weapons
from . import oni as oni_src
from . import ronin as ronin_src


def _mirrored_copy(ob, name, lib, axis=(0, 0, 1)):
    """Mirror-image twin of a sword or scabbard. Along Z: same fittings on the same face, curve
    the other way. Along X: same curve, knob and cords on the other face."""
    me = ob.data.copy()
    me.transform(Matrix.Scale(-1, 4, axis))
    me.flip_normals()
    twin = bpy.data.objects.new(name, me)
    lib.objects.link(twin)
    for k in ob.keys():
        twin[k] = ob[k]
    return twin


def _frame(origin, y_axis, x_hint):
    """4x4 matrix with local +Y along y_axis and local +X as close to x_hint as it can be."""
    y = Vector(y_axis).normalized()
    x = (Vector(x_hint) - y * Vector(x_hint).dot(y)).normalized()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def ronin(lib, col, name="RONIN", cloth=True, sim_frames=220):
    """Cyber Ronin: cut Tripo body + kasa hat (whole and pre-cut halves) + two sheathed katanas on
    the back + simulated cape and waist tails (draped here in the rest pose)."""
    body, A = ronin_src.load_body(col)
    parts = {"body": body, "anchors": A}

    # --- hat: same brim radius and position as the one that was cut away, lifted 2 cm to clear the crown
    R = max(A["hat_radius"], 0.26)                 # the generator shrank the hat; the sheet's brim is about 0.55 m across
    hr = A["helmet_radius"]
    spec = kasa.scaled(R, band_r=hr + 0.034, band_h=0.026, strap_x=hr + 0.036, strap_drop=0.15, strap_out=(1.0, 1.1, 1.24, 1.32))
    k = kasa.build(lib, "PROP_Kasa", spec)
    hat_pos = Vector((A["hat_centre"][0], A["hat_centre"][1], A["hat_z"][0] + 0.02))
    whole = core.instance(k["whole"], "Ronin_Kasa", col, hat_pos)
    halves = [core.instance(h, f"Ronin_Kasa_Half{s}", col, hat_pos) for h, s in zip(k["halves"], "LR")]
    for h in halves:                               # the halves take over on the frame the hat is cut
        h.hide_render = h.hide_viewport = True
    parts.update(hat=whole, hat_halves=halves, hat_spec=k["spec"])

    # --- katanas: sheathed, crossed on the back along the lines measured from the model
    spec_k = weapons.RONIN
    sword, _ = weapons.katana(lib, "PROP_Katana_Ronin", spec_k)
    saya, _ = weapons.scabbard(lib, "PROP_Saya_Ronin", spec_k)
    sword_m = _mirrored_copy(sword, "PROP_Katana_Ronin_L", lib)
    saya_m = _mirrored_copy(saya, "PROP_Saya_Ronin_L", lib)
    parts["katanas"], parts["sayas"] = [], []
    straps = []
    grip_len = spec_k["grip"] + 0.012
    for i, sw in enumerate(A["swords"]):
        c, d = Vector(sw["centre"]), Vector(sw["dir"])
        mouth = c + d * (sw["t"][1] - grip_len) + Vector((0, 0.028 + 0.008 * i, 0))     # clear of the back, one over the other
        m = _frame(mouth, -d, (0, 1, 0))
        tip_x = (c + d * sw["t"][0]).x
        z_axis = m.to_3x3() @ Vector((0, 0, 1))
        outward = z_axis.x * (1 if tip_x > 0 else -1) > 0            # the curve should carry the tip away from the spine
        ks = core.instance(sword if outward else sword_m, f"Ronin_Katana_{i + 1}", col)
        ss = core.instance(saya if outward else saya_m, f"Ronin_Saya_{i + 1}", col)
        ks.matrix_world = m
        ss.matrix_world = m
        parts["katanas"].append(ks)
        parts["sayas"].append(ss)
        straps.append((mouth, mouth - d * (spec_k["blade"] + 0.02)))

    # --- cloth: the panels drape themselves over a collision stand-in of the body
    drapes = []
    if cloth:
        sim = core.collection(name + "_SIM", hide_render=True)
        soft = bpy.data.objects[A["proxy"]]         # the 90k skin: thinned to 24k it grows flipped slivers and the cloth climbs them
        sim.objects.link(soft)
        garments.collider(soft)
        w = garments.Wearer(soft)
        rgb = A["cloth_rgb"]
        tone = [((c + 0.055) / 1.055) ** 2.4 * 1.35 for c in rgb]                 # texture mean has shading baked in: lift it back to the cloth's own tone
        skirt = garments.ronin_skirt(sim, w, garments.fabric("MAT_Ronin_Skirt", tone, 0.5, 0.8, dirt=0.75))
        tails = garments.ronin_tails(sim, w, garments.fabric("MAT_Ronin_Tails", tone, 0.15, 0.85, dirt=0.75))
        cape = garments.ronin_cape(sim, w, garments.fabric("MAT_Ronin_Cape", tone, 0.72, 1.12, dirt=0.7), straps)
        sims = [cape] + skirt + tails
        garments.settle(bpy.context.scene, sim_frames, report=40)
        for ob in sims:
            drapes.append(garments.freeze(ob, ob.name.replace("_sim", ""), col))
        parts.update(cape=drapes[0], skirt=drapes[1:3], tails=drapes[3:], sim=sims, collider=soft)
        # the scabbards ride on top of the cape: push each one out until it clears the cloth under it
        bpy.context.view_layer.update()
        bvh = BVHTree.FromObject(drapes[0], bpy.context.evaluated_depsgraph_get())
        for ks, ss in zip(parts["katanas"], parts["sayas"]):
            need = 0.0
            m = ss.matrix_world
            for t in [i / 24 for i in range(25)]:
                p = m @ Vector((0, t * 0.75, 0))
                hit = bvh.ray_cast(Vector((p.x, 2.0, p.z)), Vector((0, -1, 0)), 4.0)
                if hit[0] is not None:
                    need = max(need, hit[0].y + 0.021 - p.y)
            for o in (ks, ss):
                o.matrix_world.translation.y += need
            parts.setdefault("saya_lift", []).append(need)

    root = core.group(name, col, [body, whole] + halves + parts["katanas"] + parts["sayas"] + drapes)
    parts["root"] = root
    return parts


def oni(lib, col, name="ONI"):
    """Oni Samurai: cut Tripo body + katana in its scabbard at the left hip, worn edge up, with
    the red cords and tassels as their own objects."""
    body, A = oni_src.load_body(col)
    parts = {"body": body, "anchors": A}
    spec = weapons.ONI
    sword, ki = weapons.katana(lib, "PROP_Katana_Oni", spec)
    saya, si = weapons.scabbard(lib, "PROP_Saya_Oni", spec)
    saya_w = _mirrored_copy(saya, "PROP_Saya_Oni_Worn", lib, axis=(1, 0, 0))      # knob and cords on the outer face when worn on the left

    sw = A["sword"]
    c, d = Vector(sw["centre"]), Vector(sw["dir"])               # d runs from the scabbard's tip to the pommel
    pommel = c + d * sw["t"][1]
    mouth = pommel - d * (spec["grip"] + 0.012)
    m = _frame(mouth, -d, (-1, 0, 0))                            # +Y toward the tip, cutting edge up
    # the hip was rebuilt after the sword was removed: move the scabbard out until it clears the body
    sim = core.collection(name + "_SIM", hide_render=True)
    px = bpy.data.objects[A["proxy"]]
    sim.objects.link(px)
    bpy.context.view_layer.update()
    bvh = BVHTree.FromObject(px, bpy.context.evaluated_depsgraph_get())
    need = 0.0
    for i in range(41):
        p = mouth - d * (i / 40) * (spec["blade"] + 0.02)
        hit = bvh.ray_cast(Vector((2.0, p.y, p.z)), Vector((-1, 0, 0)), 4.0)
        if hit[0] is not None:
            need = max(need, hit[0].x + 0.022 - p.x)             # skin of the stand-in + half the scabbard's thickness
    m.translation.x += need
    ks = core.instance(sword, "Oni_Katana", col)
    ss = core.instance(saya_w, "Oni_Saya", col)
    ks.matrix_world = m
    ss.matrix_world = m
    tassels = []
    for nm, flip in [(n_, 1) for n_ in ki["tassels"]] + [(n_, -1) for n_ in si["tassels"]]:
        t = bpy.data.objects[nm]
        local = Vector(t.location)
        local.x *= flip                                           # the worn scabbard is the mirror image
        ti = core.instance(t, "Oni_" + nm.replace("PROP_", ""), col, m @ local)
        tassels.append(ti)
    parts.update(katana=ks, saya=ss, tassels=tassels, saya_shift=need, collider=px)
    parts["root"] = core.group(name, col, [body, ks, ss] + tassels)
    return parts
