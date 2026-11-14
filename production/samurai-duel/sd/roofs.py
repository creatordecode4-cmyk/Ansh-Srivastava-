"""Japanese tiled roofs as height fields: concave slopes, eaves that sweep up at the corners,
rows of round cover tiles, ridge beams, hip ridges and rafters under the eaves.

Local frame: X along the ridge, Y across. (a, b) are the half sizes of the eave rectangle.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import core, mats

PITCH = 0.272  # spacing of the round tile rows


class RoofShape:
    def __init__(self, a, b, rise, style="irimoya", sag=1.42, hip=1.0, gable_q=0.4, lift=0.55):
        self.a, self.b, self.R, self.style = a, b, rise, style
        self.sag, self.hip, self.q, self.lift = sag, hip, gable_q, lift
        self.xg = a - b * hip * gable_q ** (1.0 / sag) if style == "irimoya" else (a - b * hip if style == "hip" else a)
        self.yg = b * (1.0 - gable_q ** (1.0 / sag)) if style == "irimoya" else 0.0

    def height(self, X, Y, with_side=False):
        a, b, R = self.a, self.b, self.R
        X, Y = np.asarray(X, float), np.asarray(Y, float)
        sy = np.clip((b - np.abs(Y)) / b, 0, 1)
        hm = R * sy ** self.sag
        if self.style == "gable":
            h, on_main, sx = hm, np.ones_like(hm, bool), np.ones_like(hm)
        else:
            sx = np.clip((a - np.abs(X)) / (b * self.hip), 0, 1)
            he = R * sx ** self.sag
            if self.style == "hip":
                h, on_main = np.minimum(hm, he), hm <= he
            else:
                gable = he >= self.q * R
                h = np.where(gable, hm, np.minimum(hm, he))
                on_main = gable | (hm <= he)
        ex = (np.abs(X) / a) ** 3 * (1 - sy) ** 2
        ey = (np.abs(Y) / b) ** 3 * (1 - sx) ** 2 if self.style != "gable" else 0.0
        h = h + self.lift * np.maximum(ex, ey)
        return (h, on_main) if with_side else h


def _tile_relief(shape, X, Y, on_main, amp=0.042, course=0.3):
    """Round cover tiles running down the slope plus the small step of each tile course."""
    across = np.where(on_main, X, Y)
    down = np.where(on_main, np.abs(Y), np.abs(X))
    t = (across / PITCH) % 1.0
    half = 0.2
    bump = amp * np.sqrt(np.clip(1.0 - ((t - 0.5) / half) ** 2, 0, 1))
    step = 0.014 * ((down / course) % 1.0)
    return bump + step


def build(name, shape, z0, col, detail=True, thickness=0.16, rafters=True, overhang=1.6, holes=None, seed=0):
    """Returns the joined roof object (tiles + ridges + underside + rafters)."""
    a, b = shape.a, shape.b
    parts = []
    dx = PITCH / 8 if detail else PITCH * 1.5
    nx, ny = int(round(2 * a / dx)) + 1, int(round(2 * b / dx)) + 1
    xs, ys = np.linspace(-a, a, nx), np.linspace(-b, b, ny)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    H, on_main = shape.height(X, Y, with_side=True)
    Z = H + (_tile_relief(shape, X, Y, on_main) if detail else 0.0)
    P = np.stack([X, Y, z0 + Z], -1)
    top = core.grid_obj(name + "_tiles", P, col)
    if holes:  # ruined roof: knock out patches
        bm = bmesh.new()
        bm.from_mesh(top.data)
        dead = [f for f in bm.faces if any((f.calc_center_median().x - hx) ** 2 + (f.calc_center_median().y - hy) ** 2 < hr ** 2 for hx, hy, hr in holes)]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(top.data)
        bm.free()
    core.set_mat(top, mats.roof_tile())
    core.smooth(top, 50)
    parts.append(top)

    # underside (soffit boards) and the eave edge
    m = 28
    ux, uy = np.linspace(-a, a, max(8, int(2 * a / 0.4))), np.linspace(-b, b, max(8, int(2 * b / 0.4)))
    UX, UY = np.meshgrid(ux, uy, indexing="ij")
    UZ = z0 + shape.height(UX, UY) - thickness
    under = core.grid_obj(name + "_under", np.stack([UX, UY[:, ::-1], UZ[:, ::-1]], -1), col)
    core.set_mat(under, mats.dark_wood())
    parts.append(under)
    # fascia: a band closing the gap between tiles and underside along the eave rectangle
    ring = []
    n_e = 80
    for t in np.linspace(-a, a, n_e):
        ring.append((t, -b))
    for t in np.linspace(-b, b, n_e)[1:]:
        ring.append((a, t))
    for t in np.linspace(a, -a, n_e)[1:]:
        ring.append((t, b))
    for t in np.linspace(b, -b, n_e)[1:-1]:
        ring.append((-a, t))
    ring = np.array(ring)
    hz = z0 + shape.height(ring[:, 0], ring[:, 1])
    F = np.zeros((len(ring), 2, 3))
    F[:, 0] = np.stack([ring[:, 0], ring[:, 1], hz + 0.05], -1)
    F[:, 1] = np.stack([ring[:, 0], ring[:, 1], hz - thickness], -1)
    fascia = core.grid_obj(name + "_fascia", F, col, close_u=True)
    core.solidify(fascia, 0.05, 0.0)
    core.set_mat(fascia, mats.red_lacquer())
    parts.append(fascia)

    def ridge_tube(pts, r0, r1=None, up=0.0):
        r1 = r0 if r1 is None else r1
        n = len(pts)
        pp, rr = [], []
        for i, (x, y) in enumerate(pts):
            t = i / (n - 1)
            z = z0 + float(shape.height(x, y)) + r0 * 0.55 + up * t ** 4
            pp.append((x, y, z))
            rr.append(r0 + (r1 - r0) * t)
        ob = core.tube(name + "_ridge", pp, rr, col, segs=10)
        core.set_mat(ob, mats.roof_tile())
        return core.smooth(ob, 60)

    # main ridge
    xr = shape.xg
    if xr > 0.3:
        rb = core.box(name + "_ridgebeam", (2 * xr + 0.5, 0.42, 0.5), (0, 0, z0 + shape.R + 0.2), col, bevel=0.1, segs=3)
        core.set_mat(rb, mats.roof_tile())
        parts.append(core.apply_transform(rb))
        for sx in (-1, 1):  # end ornaments
            orn = core.box(name + "_oni", (0.16, 0.6, 0.75), (sx * (xr + 0.25), 0, z0 + shape.R + 0.33), col, bevel=0.06, segs=2)
            core.set_mat(orn, mats.roof_tile())
            parts.append(core.apply_transform(orn))
    if shape.style != "gable":
        for sx in (-1, 1):
            for sy in (-1, 1):
                x_top, y_top = (sx * shape.xg, sy * shape.yg) if shape.style == "irimoya" else (sx * shape.xg, 0.0)
                pts = [(x_top + (sx * a - x_top) * t, y_top + (sy * b - y_top) * t) for t in np.linspace(0, 1, 16)]
                parts.append(ridge_tube(pts, 0.14, 0.1, up=0.22))
    if shape.style in ("irimoya", "gable"):
        for sx in (-1, 1):
            ylim = shape.yg if shape.style == "irimoya" else b
            xedge = shape.xg if shape.style == "irimoya" else a
            for sy in (-1, 1):  # verge ridges down the gable edge
                pts = [(sx * (xedge - 0.05), sy * ylim * t) for t in np.linspace(0.02, 1, 12)]
                parts.append(ridge_tube(pts, 0.12, 0.1))
            if shape.style == "irimoya":   # gable wall
                tri = [(sx * (xedge - 0.12), -ylim, z0 + shape.q * shape.R), (sx * (xedge - 0.12), ylim, z0 + shape.q * shape.R), (sx * (xedge - 0.12), 0, z0 + shape.R)]
                g = core.mesh_obj(name + "_gable", tri, [(0, 1, 2)], col)
                core.solidify(g, 0.06, 0.0)
                core.set_mat(g, mats.dark_wood())
                parts.append(g)

    if rafters:
        bm = bmesh.new()
        step = 0.36
        def add(p0, p1, wdt=0.075, hgt=0.1):
            p0, p1 = Vector(p0), Vector(p1)
            d = p1 - p0
            mat = Vector((0, 0, 1)).rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
            geom = bmesh.ops.create_cube(bm, size=1.0)["verts"]
            L = d.length
            q = Vector((1, 0, 0)).rotation_difference(d.normalized())
            for v in geom:
                v.co = q @ Vector((v.co.x * L, v.co.y * wdt, v.co.z * hgt)) + (p0 + p1) / 2
        for sy in (-1, 1):
            for x in np.arange(-a + 0.5, a - 0.5 + 1e-6, step):
                y0, y1 = sy * (b - overhang - 0.1), sy * (b - 0.04)
                add((x, y0, z0 + float(shape.height(x, y0)) - thickness - 0.06), (x, y1, z0 + float(shape.height(x, y1)) - thickness - 0.06))
        if shape.style != "gable":
            for sx in (-1, 1):
                for y in np.arange(-b + 0.5, b - 0.5 + 1e-6, step):
                    x0, x1 = sx * (a - overhang - 0.1), sx * (a - 0.04)
                    add((x0, y, z0 + float(shape.height(x0, y)) - thickness - 0.06), (x1, y, z0 + float(shape.height(x1, y)) - thickness - 0.06))
        me = bpy.data.meshes.new(name + "_rafters")
        bm.to_mesh(me)
        bm.free()
        raf = bpy.data.objects.new(name + "_rafters", me)
        col.objects.link(raf)
        core.set_mat(raf, mats.red_lacquer())
        parts.append(raf)
    return core.join(parts, name)
