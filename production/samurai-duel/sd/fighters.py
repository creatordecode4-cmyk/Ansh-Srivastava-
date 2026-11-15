"""Assembles the two fighters from their parts.

Each fighter is a root empty with separate child objects: body, weapons, scabbards, hat, cloth.
Everything stands in the rest pose (T-pose), feet on z = 0, facing -Y, in metres.
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import core, kasa, weapons
from . import ronin as ronin_src


def _mirrored_copy(ob, name, lib):
    """Left-handed twin of a sword or scabbard: same fittings on the same face, curve the other way."""
    me = ob.data.copy()
    me.transform(Matrix.Scale(-1, 4, (0, 0, 1)))
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


def ronin(lib, col, name="RONIN"):
    """Cyber Ronin: cut Tripo body + kasa hat (whole and pre-cut halves) + two sheathed katanas on the back."""
    body, A = ronin_src.load_body(col)
    parts = {"body": body, "anchors": A}

    # --- hat: same brim radius and position as the one that was cut away, lifted 2 cm to clear the crown
    R = A["hat_radius"]
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

    root = core.group(name, col, [body, whole] + halves + parts["katanas"] + parts["sayas"])
    parts["root"] = root
    return parts
