"""The Ronin's kasa hat, from KASA HAT (TOP VIEW / SIDE VIEW) in refs/ronin_parts.png.

A shallow cone of pale panels (radial seams, three overlapping rings), a faceted metal cap at
the apex, a wire rim, dark ribbed underside, a head band and two strap arms.

Built whole and also as two pre-cut halves on the same origin: the film swaps the whole hat for
the halves on the frame the blade passes through it, so the split needs no simulation of tearing.
Origin: on the axis at rim height. +Z up, the wearer's front is -Y.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import charmats as cm
from . import core
from .mats import NT, _new, get

SPEC = dict(radius=0.235, rise=0.105, thick=0.006, seams=36, rings=(0.36, 0.60, 0.83), cap_r=0.060, cap_h=0.050,
            band_r=0.094, band_h=0.050, strap_x=0.090, strap_drop=0.17, cut_yaw=math.radians(8.0), cut_offset=0.012)


def _panel_mat(name, base, rough, seams, rings, radius, ribs=False):
    """Seams are drawn in the shader from the object's own polar coordinates: crisp at any distance."""
    def build(name):
        m, nt, b = _new(name)
        tc = nt.new("ShaderNodeTexCoord")
        sep = nt.new("ShaderNodeSeparateXYZ")
        nt.link(tc.outputs["Object"], sep.inputs[0])
        x, y = sep.outputs[0], sep.outputs[1]
        r = nt.math("SQRT", nt.math("ADD", nt.math("MULTIPLY", x, x), nt.math("MULTIPLY", y, y)))
        ang = nt.math("ARCTAN2", y, x)
        cell = nt.math("FRACT", nt.math("ADD", nt.math("MULTIPLY", ang, seams / (2 * math.pi)), 0.5))
        d_ang = nt.math("MULTIPLY", nt.math("ABSOLUTE", nt.math("SUBTRACT", cell, 0.5)), nt.math("MULTIPLY", r, 2 * math.pi / seams))   # metres from the nearest seam
        line = nt.map_range(d_ang, 0.0, 0.0016 if not ribs else 0.004, 1.0, 0.0)
        for rr in rings:
            line = nt.math("MAXIMUM", line, nt.map_range(nt.math("ABSOLUTE", nt.math("SUBTRACT", r, rr * radius)), 0.0, 0.0018, 1.0, 0.0))
        grain = nt.noise(nt.coords("Object", 1.0), 180.0, 3.0, 0.6)
        streak = nt.noise(nt.coords("Object", (6.0, 6.0, 40.0)), 3.0, 3.0, 0.6)                # rain streaks down the slope
        col = nt.mix(nt.map_range(streak, 0.35, 0.75, 0.0, 0.35), (*base, 1), tuple(c * 0.55 for c in base) + (1,))
        col = nt.mix(nt.math("MULTIPLY", line, 0.75 if not ribs else -0.6), col, (0.05, 0.05, 0.055, 1) if not ribs else (0.3, 0.3, 0.31, 1))
        nt.put(b.inputs["Base Color"], col)
        nt.put(b.inputs["Roughness"], nt.map_range(grain, 0.3, 0.7, rough * 0.8, rough * 1.25))
        b.inputs["Coat Weight"].default_value = 0.25 if not ribs else 0.0
        b.inputs["Coat Roughness"].default_value = 0.2
        h = nt.math("ADD", nt.math("MULTIPLY", line, -1.0 if not ribs else 1.0), nt.math("MULTIPLY", grain, 0.12))
        nt.link(nt.bump(h, 0.6, 0.0012), b.inputs["Normal"])
        return m

    return get(name, build)


def _core_mat():
    """What the blade exposes: pale layered fibre."""
    def build(name):
        m, nt, b = _new(name)
        lay = nt.noise(nt.coords("Object", (30.0, 30.0, 900.0)), 1.0, 3.0, 0.6)
        nt.put(b.inputs["Base Color"], nt.mix(nt.map_range(lay, 0.3, 0.7), (0.52, 0.44, 0.30, 1), (0.74, 0.68, 0.52, 1)))
        b.inputs["Roughness"].default_value = 0.8
        nt.link(nt.bump(lay, 0.5, 0.0008), b.inputs["Normal"])
        return m

    return get("MAT_Kasa_Core", build)


def _shell(name, S, col):
    R, H, th = S["radius"], S["rise"], S["thick"]
    r_in = S["cap_r"] * 0.9
    step = 0.0024
    prof_top = []
    rings = [x * R for x in S["rings"]]
    rs = sorted(set(list(np.linspace(r_in, R, 34)) + [x - 0.0006 for x in rings] + [x + 0.0006 for x in rings]))
    for r in rs:
        z = H * (1.0 - r / R) ** 0.94 + th                      # a slightly swelling slope, as in the side view
        z += step * sum(1 for x in rings if r < x)               # each upper ring of panels laps over the next
        prof_top.append((r, z))
    prof = prof_top + [(R + 0.0015, th * 0.5)]                   # rounded lip
    for r in reversed(np.linspace(r_in, R, 24)):
        prof.append((r, H * (1.0 - r / R) ** 0.94))
    ob = core.lathe(name, prof, 180, col, cap=True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return core.smooth(ob, 30)


def _fittings(name, S, col):
    R, H, th = S["radius"], S["rise"], S["thick"]
    parts = []
    zc = H * (1.0 - S["cap_r"] / R) ** 0.94 + th
    cr, ch = S["cap_r"], S["cap_h"]
    collar = core.lathe(name + "_collar", [(cr * 1.22, zc - 0.006), (cr * 1.24, zc + 0.004), (cr * 1.12, zc + 0.012), (cr * 1.0, zc + 0.013)], 64, col, cap=False)
    core.set_mat(core.smooth(collar, 35), cm.silver())
    parts.append(collar)
    cone = core.prism(name + "_cap", 12, cr, 0.004, ch, (0, 0, zc + 0.011), col, bevel=0.0012)
    core.set_mat(core.smooth(core.apply_transform(cone), 20), cm.silver())
    parts.append(cone)
    rim = core.lathe(name + "_rim", [(R + 0.0015 + 0.0042 * math.cos(a), th * 0.5 + 0.0042 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)] +
                     [(R + 0.0015 + 0.0042, th * 0.5)], 180, col, cap=False)
    core.set_mat(core.smooth(rim, 60), cm.silver())
    parts.append(rim)
    br, bh = S["band_r"], S["band_h"]
    zb = H * (1.0 - br / R) ** 0.94
    band = core.lathe(name + "_band", [(br, zb + 0.004), (br + 0.004, zb + 0.004), (br + 0.004, zb - bh), (br + 0.002, zb - bh - 0.003), (br, zb - bh), (br, zb + 0.004)], 72, col, cap=False)
    core.set_mat(core.smooth(band, 40), cm.black_steel())
    parts.append(band)
    for sx in (-1, 1):                                             # strap arms hanging from the band, silver tipped
        bb = core.BoxBatch()
        x0 = sx * S["strap_x"]
        pts = [Vector((x0, 0.0, zb - bh + 0.012)), Vector((x0 * 1.03, -0.006, zb - bh - 0.04)), Vector((x0 * 1.0, -0.016, zb - bh - 0.09)),
               Vector((x0 * 0.9, -0.03, zb - bh - S["strap_drop"] + 0.03))]
        for a, c in zip(pts[:-1], pts[1:]):
            bb.beam(a, c, 0.024, 0.0065, bevel=0.002)
        arm = bb.to_object(name + "_strap", col, cm.black_steel())
        parts.append(core.smooth(arm, 40))
        tip = core.BoxBatch()
        tip.beam(pts[-1], pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.03, 0.021, 0.006, bevel=0.002)
        parts.append(core.smooth(tip.to_object(name + "_tip", col, cm.silver()), 40))
    return parts


def _split_materials(ob, S):
    """Top faces get the pale panels, the underside the dark ribbed lining."""
    top = _panel_mat("MAT_Kasa_Panels", (0.70, 0.70, 0.72), 0.42, S["seams"], S["rings"], S["radius"])
    under = _panel_mat("MAT_Kasa_Lining", (0.085, 0.085, 0.09), 0.6, S["seams"], (), S["radius"], ribs=True)
    me = ob.data
    me.materials.clear()
    me.materials.append(top)
    me.materials.append(under)
    R, H, th = S["radius"], S["rise"], S["thick"]
    for p in me.polygons:                      # below the middle of the shell's thickness = lining
        c = p.center
        r = min(R, math.hypot(c.x, c.y))
        p.material_index = 1 if c.z < H * (1.0 - r / R) ** 0.94 + th * 0.5 and r < R - 0.0005 else 0


def _half(src, name, col, plane_co, plane_no, keep_positive):
    """One side of the hat after the cut, with the cut faces closed and given the core material."""
    me = src.data.copy()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=plane_co, plane_no=plane_no,
                                 clear_inner=keep_positive, clear_outer=not keep_positive)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    n0 = len(bm.faces)
    bmesh.ops.holes_fill(bm, edges=cut)
    bm.faces.ensure_lookup_table()
    core_i = len(me.materials)
    for f in bm.faces[n0:]:
        f.material_index = core_i
        f.smooth = False
    bm.to_mesh(me)
    bm.free()
    me.materials.append(_core_mat())
    return ob


def build(lib, name="PROP_Kasa", spec=None):
    """Returns dict(whole=object, halves=(left, right), spec=...). All three share one origin."""
    S = dict(SPEC, **(spec or {}))
    shell = _shell(name + "_shell", S, lib)
    _split_materials(shell, S)
    whole = core.join([shell] + _fittings(name, S, lib), name)
    n = Vector((math.cos(S["cut_yaw"]), math.sin(S["cut_yaw"]), 0.0))          # the cut runs front to back, a touch off the axis
    co = n * S["cut_offset"]
    left = _half(whole, name + "_HalfL", lib, co, n, keep_positive=False)
    right = _half(whole, name + "_HalfR", lib, co, n, keep_positive=True)
    for o in (whole, left, right):
        o["cut_normal"] = n[:]
        o["radius"] = S["radius"]
    return dict(whole=whole, halves=(left, right), spec=S)
