"""Torii gate, modelled from TORII GATE (front + side view) in refs/arena_props.png.

Red lacquered pillars on stone bases, black roofed top lintel with up-swept ends, lower tie
beam, short support posts front and back, and a straw rope with tassels and a small banner.
Built by code so every line stays straight: an AI mesh would wobble against the moon.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

from . import core, layout, mats


def _curved_beam(name, length, width, height, z, rise, col, power=2.4, nseg=48, taper_end=1.0):
    """Beam along X whose ends sweep upward (the classic lintel curve)."""
    xs = np.linspace(-length / 2, length / 2, nseg)
    lift = rise * (np.abs(xs) / (length / 2)) ** power
    P = np.zeros((nseg, 4, 3))
    for k, (sy, sz) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)]):
        P[:, k, 0] = xs
        P[:, k, 1] = sy * width / 2
        P[:, k, 2] = z + lift + sz * height / 2 * (1.0 + (taper_end - 1.0) * (np.abs(xs) / (length / 2)) ** 2)
    ob = core.grid_obj(name, P, col, close_v=True)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if e.calc_face_angle(0) > 0.9], offset=0.012, segments=2, profile=0.5, affect="EDGES")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def _stone_base(name, col, w1=1.25, h1=0.42, w2=0.92, h2=0.45, seed=0):
    a = core.box(name + "_a", (w1, w1, h1), (0, 0, h1 / 2), col, bevel=0.05, segs=3)
    b = core.box(name + "_b", (w2, w2, h2), (0, 0, h1 + h2 / 2), col, bevel=0.07, segs=3)
    ob = core.join([a, b], name)
    core.subdivide(ob, 2, simple=True)
    core.displace(ob, 0.035, 0.22, "CLOUDS", 3)
    core.smooth(ob, 60)
    core.set_mat(ob, mats.stone_block())
    return ob, h1 + h2


def _rope(name, a, b, sag, radius, col, n=40):
    a, b = Vector(a), Vector(b)
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    ob = core.tube(name, pts, radius, col, segs=10)
    core.smooth(ob, 60)
    core.set_mat(ob, mats.rope())
    return ob, pts


def build(lib, name="PROP_Torii"):
    """Returns one master object (origin on the ground between the pillars, facing -Y / south)."""
    T = layout.TORII
    H, sp, beam = T["height"], T["pillar_spacing"], T["beam"]
    parts = []
    red, black = mats.red_lacquer(), mats.black_lacquer()

    cap_h, top_h, low_h = 0.10, 0.26, 0.30          # roof cap, upper lintel (kasagi), lower lintel (shimaki)
    rise = 0.36
    z_low = H - rise - cap_h - top_h - low_h / 2    # centre height of the lower lintel at mid span
    pillar_top = z_low - low_h / 2 + 0.05
    for sx in (-1, 1):
        base, bh = _stone_base(f"{name}_base", lib, seed=sx)
        base.location.x = sx * sp / 2
        parts.append(core.apply_transform(base))
        lean = math.radians(1.4) * -sx               # pillars lean slightly toward each other
        h = pillar_top - bh
        prof = [(0.0, 0.0), (0.285, 0.0), (0.285, 0.02), (0.27, h * 0.5), (0.25, h), (0.0, h)]
        pil = core.lathe(f"{name}_pillar", prof, 28, lib, cap=False)
        core.set_mat(pil, red)
        pil.location = (sx * sp / 2, 0, bh)
        pil.rotation_euler = (0, lean, 0)
        parts.append(core.apply_transform(core.smooth(pil, 50)))
        band = core.lathe(f"{name}_band", [(0.3, 0.0), (0.305, 0.03), (0.3, 0.62), (0.285, 0.66)], 28, lib, cap=False)
        core.set_mat(band, black)
        band.location = (sx * sp / 2, 0, bh)
        band.rotation_euler = (0, lean, 0)
        parts.append(core.apply_transform(core.smooth(band, 50)))
        # short support posts front and back, tied to the main pillar
        for sy in (-1, 1):
            sb, sbh = _stone_base(f"{name}_sbase", lib, 0.62, 0.22, 0.46, 0.2)
            sb.location = (sx * sp / 2, sy * 1.05, 0)
            parts.append(core.apply_transform(sb))
            ph = 2.75
            post = core.lathe(f"{name}_post", [(0.0, 0), (0.135, 0), (0.125, ph), (0.0, ph)], 16, lib, cap=False)
            core.set_mat(post, red)
            post.location = (sx * sp / 2, sy * 1.05, sbh)
            parts.append(core.apply_transform(core.smooth(post, 50)))
            cap = core.box(f"{name}_postcap", (0.46, 0.46, 0.09), (sx * sp / 2, sy * 1.05, sbh + ph + 0.045), lib, bevel=0.02)
            core.set_mat(cap, black)
            parts.append(core.apply_transform(cap))
            for tz in (1.55, 2.35):
                tie = core.box(f"{name}_tie", (0.13, 1.25, 0.16), (sx * sp / 2, sy * 0.55, tz), lib, bevel=0.012)
                core.set_mat(tie, red)
                parts.append(core.apply_transform(tie))

    # lower tie beam passing through the pillars, with wedges
    z_nuki = z_low - 1.45
    nuki = core.box(f"{name}_nuki", (beam * 0.92, 0.2, 0.34), (0, 0, z_nuki), lib, bevel=0.015)
    core.set_mat(nuki, red)
    parts.append(core.apply_transform(nuki))
    for sx in (-1, 1):
        for off in (-0.36, 0.36):
            wd = core.box(f"{name}_wedge", (0.09, 0.3, 0.2), (sx * sp / 2 + off, 0, z_nuki + 0.02), lib, bevel=0.012)
            core.set_mat(wd, black)
            parts.append(core.apply_transform(wd))
    strut_h = (z_low - low_h / 2) - (z_nuki + 0.17)
    strut = core.box(f"{name}_strut", (0.34, 0.16, strut_h), (0, 0, z_nuki + 0.17 + strut_h / 2), lib, bevel=0.015)
    core.set_mat(strut, red)
    parts.append(core.apply_transform(strut))
    plaque = core.box(f"{name}_plaque", (0.42, 0.05, 0.62), (0, -0.11, z_nuki + 0.17 + strut_h / 2), lib, bevel=0.01)
    core.set_mat(plaque, black)
    parts.append(core.apply_transform(plaque))

    low = _curved_beam(f"{name}_shimaki", beam * 0.95, 0.34, low_h, z_low, rise * 0.85, lib)
    core.set_mat(low, red)
    top = _curved_beam(f"{name}_kasagi", beam, 0.46, top_h, z_low + low_h / 2 + top_h / 2, rise, lib, taper_end=1.25)
    core.set_mat(top, black)
    roof = _curved_beam(f"{name}_roof", beam * 1.02, 0.66, cap_h, z_low + low_h / 2 + top_h + cap_h / 2, rise * 1.08, lib)
    core.set_mat(roof, mats.roof_tile())
    for o in (low, top, roof):
        parts.append(core.smooth(o, 45))

    # straw rope with tassels, hung between the pillars under the tie beam
    zr = z_nuki - 0.42
    rope, pts = _rope(f"{name}_rope", (-sp / 2 + 0.2, -0.3, zr), (sp / 2 - 0.2, -0.3, zr), 0.55, 0.055, lib)
    parts.append(rope)
    for t in (0.2, 0.5, 0.8):
        p = pts[int(t * (len(pts) - 1))]
        tas = core.lathe(f"{name}_tassel", [(0.0, 0.0), (0.03, 0.0), (0.075, -0.36), (0.06, -0.4), (0.0, -0.4)], 12, lib, cap=False)
        tas.location = (p.x, p.y, p.z - 0.04)
        core.set_mat(tas, mats.rope())
        parts.append(core.apply_transform(core.smooth(tas, 60)))

    ob = core.join(parts, name)
    return ob
