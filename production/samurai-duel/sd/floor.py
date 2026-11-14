"""Courtyard floor: a set of 4 cracked flagstone variants instanced over the paved area,
the dirt underneath, and a thin water film that turns every dip and crack into a puddle.

Reference: FLOOR TILE SET in refs/arena_props.png (square slabs broken into polygons).
"""
import math

import bpy
import numpy as np

from . import core, layout, mats
from .core import fbm2, smoothstep


def make_tile(name, seed, col, size=1.17, thick=0.16, n=48, cells=6, crack_w=0.016, crack_depth=0.02):
    """One flagstone: top surface is a height field with a Voronoi crack network; each broken
    piece sits at a slightly different height and tilt, like a slab that has really cracked."""
    rs = np.random.RandomState(seed)
    u = np.linspace(-size / 2, size / 2, n)
    X, Y = np.meshgrid(u, u, indexing="ij")
    sites = rs.uniform(-size / 2, size / 2, (cells, 2))
    wx = X + 0.05 * (fbm2(X * 5, Y * 5, 3, seed) - 0.5)
    wy = Y + 0.05 * (fbm2(X * 5 + 31, Y * 5 + 17, 3, seed + 5) - 0.5)
    d = np.sqrt((wx[..., None] - sites[:, 0]) ** 2 + (wy[..., None] - sites[:, 1]) ** 2)
    order = np.sort(d, axis=-1)
    cell = np.argmin(d, axis=-1)
    edge = order[..., 1] - order[..., 0]
    crack = 1.0 - smoothstep(0.0, crack_w, edge)
    cz = rs.normal(0, 0.0022, cells)
    tx, ty = rs.normal(0, 0.007, cells), rs.normal(0, 0.007, cells)
    Z = cz[cell] + tx[cell] * (X - sites[cell, 0]) + ty[cell] * (Y - sites[cell, 1])
    Z -= crack_depth * crack * (0.6 + 0.8 * fbm2(X * 3, Y * 3, 2, seed + 2))
    Z += 0.0035 * (fbm2(X * 11, Y * 11, 4, seed + 3) - 0.5)          # stone grain
    Z -= 0.007 * fbm2(X * 1.4 + seed, Y * 1.4, 2, seed + 9)            # shallow dishing -> puddles
    e = np.minimum(size / 2 - np.abs(X), size / 2 - np.abs(Y))
    Z -= 0.014 * (1.0 - smoothstep(0.0, 0.04, e))                      # worn, rounded border
    chip = fbm2(X * 4.5, Y * 4.5, 3, seed + 21)
    Z -= 0.03 * smoothstep(0.6, 0.78, chip) * (1.0 - smoothstep(0.0, 0.14, e))  # chipped edges

    # add a skirt ring so the slab has sides
    P = np.zeros((n + 2, n + 2, 3))
    P[1:-1, 1:-1, 0], P[1:-1, 1:-1, 1], P[1:-1, 1:-1, 2] = X, Y, Z
    P[0, 1:-1], P[-1, 1:-1], P[1:-1, 0], P[1:-1, -1] = P[1, 1:-1], P[-2, 1:-1], P[1:-1, 1], P[1:-1, -2]
    P[0, 0], P[0, -1], P[-1, 0], P[-1, -1] = P[1, 1], P[1, -2], P[-2, 1], P[-2, -2]
    ring = np.ones((n + 2, n + 2), bool)
    ring[1:-1, 1:-1] = False
    P[ring, 2] = -thick
    ob = core.grid_obj(name, P, col)
    core.smooth(ob, 50)
    core.set_mat(ob, mats.stone_slab())
    return ob


def tile_set(lib):
    """The 4 master tiles (few cracks -> shattered)."""
    specs = [dict(cells=3, crack_w=0.012), dict(cells=5), dict(cells=7, crack_depth=0.024), dict(cells=10, crack_w=0.02, crack_depth=0.028)]
    return [make_tile(f"PROP_FloorTile_{i + 1:02d}", 11 + i * 7, lib, **s) for i, s in enumerate(specs)]


def _in_rubble(x, y, pad=0.0):
    for (x0, y0, x1, y1, dens) in layout.RUBBLE:
        if min(x0, x1) - pad <= x <= max(x0, x1) + pad and min(y0, y1) - pad <= y <= max(y0, y1) + pad:
            return dens
    return 0.0


def build(lib, col, seed=3):
    r = core.rng(seed)
    tiles = tile_set(lib)
    p, t = layout.PAVED, layout.TILE
    nx, ny = round((p["x1"] - p["x0"]) / t), round((p["y1"] - p["y0"]) / t)
    count = 0
    for i in range(nx):
        for j in range(ny):
            x, y = p["x0"] + (i + 0.5) * t, p["y0"] + (j + 0.5) * t
            dens = _in_rubble(x, y)
            edge = min(i, nx - 1 - i) == 0
            if dens and r.random() < 0.45 * dens:
                continue  # missing slab: bare ground shows through
            broken = dens > 0 or edge
            k = r.choice([2, 3]) if broken else r.choices([0, 1, 2, 3], [4, 4, 3, 1])[0]
            ob = core.instance(tiles[k], f"FloorTile_{i:02d}_{j:02d}", col)
            jit = 0.05 if broken else 0.008
            ob.location = (x + r.uniform(-jit, jit), y + r.uniform(-jit, jit), r.gauss(0, 0.012 if broken else 0.0028) - (0.02 if broken else 0.0))
            tilt = 0.035 if broken else 0.0035
            ob.rotation_euler = (r.gauss(0, tilt), r.gauss(0, tilt), r.choice([0, 1, 2, 3]) * math.pi / 2 + r.gauss(0, 0.05 if broken else 0.004))
            ob.scale = (r.choice([-1, 1]), 1, 1)  # mirrored copies double the variety
            count += 1

    # dirt everywhere under and around the paving
    n = 160
    u = np.linspace(-70, 70, n)
    X, Y = np.meshgrid(u, u, indexing="ij")
    Z = -0.045 + 0.05 * (fbm2(X * 0.35, Y * 0.35, 4, 5) - 0.5)
    inside = (X > p["x0"] - 0.5) & (X < p["x1"] + 0.5) & (Y > p["y0"] - 0.5) & (Y < p["y1"] + 0.5)
    Z[inside] = np.minimum(Z[inside], -0.03)
    ground = core.grid_obj("Ground_Dirt", np.stack([X, Y, Z], -1), col)
    core.smooth(ground, 180)
    core.set_mat(ground, mats.ground_dirt())

    # standing water: one flat sheet; wherever the stone dips below it there is a puddle
    water = core.mesh_obj("Water_Film", [(p["x0"] - 2, p["y0"] - 2, 0), (p["x1"] + 2, p["y0"] - 2, 0), (p["x1"] + 2, p["y1"] + 0.4, 0), (p["x0"] - 2, p["y1"] + 0.4, 0)], [(0, 1, 2, 3)], col)
    water.location.z = -0.0055
    core.set_mat(water, mats.water_film())
    water.visible_shadow = False
    return dict(tiles=tiles, count=count, ground=ground, water=water)
