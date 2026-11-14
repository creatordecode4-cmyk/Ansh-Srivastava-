"""Stone lantern (intact and broken), from STONE LANTERN / BROKEN STONE LANTERN in refs/arena_props.png.

Stack from the ground: three rough base slabs, a tapering shaft of piled rock, a platform,
the fire box with a red glow behind a stone lattice, a pagoda roof with up-swept corners and
a jewel finial. The master is a collection (stone mesh + glow core + light) that is instanced.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import core, mats

GLOW = (1.0, 0.11, 0.035)


def _rough(ob, strength=0.035, scale=0.2, levels=2):
    core.subdivide(ob, levels, simple=True)
    core.displace(ob, strength, scale, "CLOUDS", 3)
    core.displace(ob, strength * 0.35, scale * 0.3, "CLOUDS", 2)
    return ob


def _roof(name, col, half=0.55, peak=0.34, lift=0.11, thick=0.07, n=33):
    """Square pagoda roof as a height field: concave slope, corners sweeping up."""
    u = np.linspace(-half, half, n)
    X, Y = np.meshgrid(u, u, indexing="ij")
    d = np.maximum(np.abs(X), np.abs(Y)) / half
    Z = peak * (1.0 - d) ** 1.55 + lift * (np.minimum(np.abs(X), np.abs(Y)) / half) ** 3 * d ** 2
    P = np.zeros((n + 2, n + 2, 3))
    P[1:-1, 1:-1, 0], P[1:-1, 1:-1, 1], P[1:-1, 1:-1, 2] = X, Y, Z
    P[0, 1:-1], P[-1, 1:-1], P[1:-1, 0], P[1:-1, -1] = P[1, 1:-1], P[-2, 1:-1], P[1:-1, 1], P[1:-1, -2]
    P[0, 0], P[0, -1], P[-1, 0], P[-1, -1] = P[1, 1], P[1, -2], P[-2, 1], P[-2, -2]
    ring = np.ones((n + 2, n + 2), bool)
    ring[1:-1, 1:-1] = False
    P[ring, 2] -= thick
    P[ring, 0] *= 0.97
    P[ring, 1] *= 0.97
    ob = core.grid_obj(name, P, col)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def stone_lantern(lib, broken=False, name=None, seed=1, height=2.6, power=260.0):
    name = name or ("PROP_StoneLantern_Broken" if broken else "PROP_StoneLantern")
    r = core.rng(seed + (50 if broken else 0))
    master = bpy.data.collections.new(name)
    lib.children.link(master)
    tmp = core.collection("_tmp_build")
    parts = []
    k = height / 2.6
    z = 0.0
    # base slabs
    for wdt, h in ((1.02, 0.22), (0.84, 0.21), (0.68, 0.19)):
        b = core.box("b", (wdt * k, wdt * k * r.uniform(0.94, 1.0), h * k), (r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), z + h * k / 2), tmp, bevel=0.045 * k, segs=3, rot=(0, 0, r.uniform(-0.12, 0.12)))
        parts.append(core.apply_transform(_rough(b, 0.04 * k, 0.22)))
        z += h * k * 0.97
    # shaft: piled rock, tapering upward
    lean = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)).normalized() * (0.07 if broken else 0.012)
    shaft_h, n_rocks = 0.74 * k, 5
    for i in range(n_rocks):
        t = i / (n_rocks - 1)
        wdt = (0.6 - 0.24 * t) * k * r.uniform(0.92, 1.06)
        h = shaft_h / n_rocks * 1.25
        off = lean * (z - 0.6 * k)
        rock = core.prism("r", r.choice([5, 6, 7]), wdt / 2, wdt / 2 * r.uniform(0.82, 0.95), h, (off.x + r.uniform(-0.03, 0.03), off.y + r.uniform(-0.03, 0.03), z - 0.02), tmp, bevel=0.05 * k, rot_z=r.uniform(0, 3.14), segs=2)
        parts.append(core.apply_transform(_rough(rock, 0.06 * k, 0.16)))
        z += shaft_h / n_rocks
    top = Vector((lean.x * (z - 0.6 * k), lean.y * (z - 0.6 * k), 0))
    tilt = (lean.y * -1.2, lean.x * 1.2, r.uniform(-0.1, 0.1))
    # platform (wider top than bottom)
    plat = core.prism("p", 4, 0.3 * k * 1.414, 0.37 * k * 1.414, 0.17 * k, (top.x, top.y, z), tmp, bevel=0.03 * k, rot_z=math.pi / 4)
    plat.rotation_euler = (tilt[0], tilt[1], math.pi / 4 + tilt[2])
    parts.append(core.apply_transform(_rough(plat, 0.025 * k, 0.15)))
    z += 0.17 * k
    # fire box: corner posts, rails and a window lattice on each side
    fb, fh = 0.48 * k, 0.44 * k
    cage = []
    missing = r.randrange(4) if broken else -1
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        if i == missing:
            continue
        cage.append(core.box("c", (0.085 * k, 0.085 * k, fh), (sx * (fb / 2 - 0.04 * k), sy * (fb / 2 - 0.04 * k), fh / 2), tmp, bevel=0.012))
    for zz in (0.035 * k, fh - 0.035 * k):
        cage.append(core.box("c", (fb, fb, 0.07 * k), (0, 0, zz), tmp, bevel=0.015))
    for ax in range(4):
        a = ax * math.pi / 2
        n = Vector((math.cos(a), math.sin(a), 0)) * (fb / 2 - 0.03 * k)
        t = Vector((-math.sin(a), math.cos(a), 0))
        for off in (-0.085 * k, 0.085 * k):   # vertical bars
            c = n + t * off
            cage.append(core.box("c", (0.022 * k,) * 2 + (fh - 0.1 * k,), (c.x, c.y, fh / 2), tmp))
        bar = core.box("c", (0.02 * k, fb - 0.14 * k, 0.022 * k), (n.x, n.y, fh / 2), tmp)   # horizontal bar
        bar.rotation_euler.z = a
        cage.append(bar)
    cage = core.join([core.apply_transform(c) for c in cage], "cage")
    _rough(cage, 0.008 * k, 0.1, 1)
    cage.location = (top.x, top.y, z)
    cage.rotation_euler = tilt
    parts.append(core.apply_transform(cage))
    box_z = z
    z += fh
    # roof + finial
    roof = _roof("roof", tmp, 0.56 * k, 0.34 * k, 0.11 * k, 0.08 * k)
    core.displace(roof, 0.03 * k, 0.16, "CLOUDS", 3)
    if broken:   # a corner has been knocked off
        bm = bmesh.new()
        bm.from_mesh(roof.data)
        ang = r.uniform(0, 6.28)
        nrm = Vector((math.cos(ang), math.sin(ang), 0.35)).normalized()
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=nrm * 0.3 * k, plane_no=nrm, clear_outer=True)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bm.to_mesh(roof.data)
        bm.free()
        core.displace(roof, 0.012 * k, 0.05, "CLOUDS", 2)
    roof.location = (top.x, top.y, z - 0.01)
    roof.rotation_euler = (tilt[0] * (2.5 if broken else 1), tilt[1] * (2.5 if broken else 1), tilt[2])
    parts.append(core.apply_transform(roof))
    z += 0.3 * k
    fin_prof = [(0.0, 0.0), (0.15, 0.0), (0.16, 0.05), (0.09, 0.08), (0.12, 0.13), (0.125, 0.17), (0.07, 0.2), (0.1, 0.25), (0.135, 0.32), (0.11, 0.4), (0.03, 0.47), (0.0, 0.49)]
    fin = core.lathe("fin", [(a * k, b * k) for a, b in fin_prof], 16, tmp, cap=False)
    _rough(fin, 0.012 * k, 0.1, 1)
    if broken:   # finial has fallen and lies beside the base
        fin.location = (0.75 * k, -0.35 * k, 0.1 * k)
        fin.rotation_euler = (1.45, 0.3, 0.8)
    else:
        fin.location = (top.x, top.y, z)
        fin.rotation_euler = tilt
    parts.append(core.apply_transform(fin))
    if broken:   # rubble that came off it
        for i in range(7):
            s = r.uniform(0.12, 0.3) * k
            a, d = r.uniform(0, 6.28), r.uniform(0.5, 1.15) * k
            rk = core.prism("rk", r.choice([4, 5, 6]), s, s * r.uniform(0.5, 0.9), s * r.uniform(0.6, 1.1), (math.cos(a) * d, math.sin(a) * d, -0.02), tmp, bevel=0.03, rot_z=r.uniform(0, 6))
            rk.rotation_euler.x = r.uniform(-0.5, 0.5)
            parts.append(core.apply_transform(_rough(rk, 0.05 * k, 0.14)))

    stone = core.join(parts, name + "_stone")
    core.smooth(stone, 55)
    core.set_mat(stone, mats.stone_lantern())
    core.link(stone, master)

    # glow core + actual light (the mesh gives the visible ember, the lamp lights the scene)
    core_ob = core.box(name + "_glow", (fb * 0.62, fb * 0.62, fh * 0.6), (top.x, top.y, box_z + fh * 0.45), master, bevel=0.03)
    core.set_mat(core_ob, mats.emission("MAT_Lantern_Glow", GLOW, 55.0 if not broken else 32.0))
    core_ob.visible_shadow = False
    ld = bpy.data.lights.new(name + "_light", "POINT")
    ld.color, ld.energy, ld.shadow_soft_size = GLOW, power * (0.55 if broken else 1.0), 0.09
    lo = bpy.data.objects.new(name + "_light", ld)
    lo.location = (top.x, top.y, box_z + fh * 0.5)
    master.objects.link(lo)
    return master
