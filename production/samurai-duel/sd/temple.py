"""Architecture: stone stairs, the temple hall, the ruined corridor and small roofed structures.

References: TEMPLE WALL SECTION and TEMPLE STAIR SECTION in refs/arena_props.png, plus the
building massing in the top-down layout. Structures are built in a local frame whose front
faces -Y, then placed and rotated as a group.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from . import core, mats, roofs
from .core import BoxBatch

INTERIOR_GLOW = (1.0, 0.12, 0.035)


def _rough(ob, strength=0.03, scale=0.25, levels=2):
    core.subdivide(ob, levels, simple=True)
    core.displace(ob, strength, scale, "CLOUDS", 3)
    return core.smooth(ob, 60)


def stair_section(lib, name="PROP_Stairs", width=3.4, steps=9, rise=0.17, run=0.30, walls=True, wall_w=0.55, seed=0):
    """Stone stairs climbing toward +Y. Origin: centre of the bottom edge, on the ground."""
    r = core.rng(seed)
    bb = BoxBatch()
    for i in range(steps):
        n_blocks = max(2, round(width / 1.3))
        edges = sorted([-width / 2] + [(-width / 2 + width * (k + r.uniform(-0.15, 0.15)) / n_blocks) for k in range(1, n_blocks)] + [width / 2])
        for k in range(n_blocks):
            x0, x1 = edges[k] + 0.006, edges[k + 1] - 0.006
            top = (i + 1) * rise + r.uniform(-0.006, 0.004)
            bb.add((x1 - x0, run + 0.035, top + 0.3), ((x0 + x1) / 2, (i + 0.5) * run + r.uniform(-0.006, 0.006), top / 2 - 0.15),
                   rot=(r.gauss(0, 0.004), r.gauss(0, 0.004), r.gauss(0, 0.004)), bevel=0.022)
    if walls:
        for sx in (-1, 1):
            i = 0
            while i < steps:
                span = min(r.choice([2, 2, 3]), steps - i)
                top = (i + span) * rise + r.uniform(0.32, 0.42)
                bb.add((wall_w, span * run + 0.02, top + 0.3), (sx * (width / 2 + wall_w / 2), (i + span / 2) * run, top / 2 - 0.15),
                       rot=(0, 0, r.gauss(0, 0.006)), bevel=0.035)
                i += span
            top = steps * rise + 0.36
            bb.add((wall_w + 0.12, 0.62, top + 0.3), (sx * (width / 2 + wall_w / 2), steps * run + 0.26, top / 2 - 0.15), bevel=0.04)
    ob = bb.to_object(name, lib, mats.stone_block())
    _rough(ob, 0.022, 0.2, 2)
    return ob


def _lattice(bb, x0, x1, z0, z1, y, pitch=0.115, bar=0.03, rails=3):
    n = max(2, int((x1 - x0) / pitch))
    for i in range(n + 1):
        bb.add((bar, bar, z1 - z0), (x0 + (x1 - x0) * i / n, y, (z0 + z1) / 2))
    for j in range(rails):
        bb.add((x1 - x0, bar * 0.8, bar), ((x0 + x1) / 2, y, z0 + (z1 - z0) * (j + 0.5) / rails))


def hall(lib, col, name="Temple", width=12.5, depth=9.0, platform=1.9, deck=2.3, stair_width=3.4, stair_steps=11,
         wall_h=4.3, roof_rise=4.4, overhang=1.9, detail=True, loc=(0, 0, 0), yaw=0.0, seed=0, glow_strength=0.2):
    """Temple hall. Facade along X at y=0 facing -Y; returns (root empty, anchor dict in local coords)."""
    r = core.rng(seed)
    objs = []
    W, D, P = width, depth, platform
    px0, px1, py0, py1 = -W / 2 - deck, W / 2 + deck, -deck, D + deck * 0.6

    # --- stone platform with a cap course
    stone = BoxBatch()
    stone.add((px1 - px0, py1 - py0, P - 0.14 + 0.5), ((px0 + px1) / 2, (py0 + py1) / 2, (P - 0.14) / 2 - 0.25), bevel=0.04)
    stone.add((px1 - px0 + 0.16, py1 - py0 + 0.16, 0.16), ((px0 + px1) / 2, (py0 + py1) / 2, P - 0.08), bevel=0.03)
    plat = stone.to_object(name + "_platform", col, mats.stone_block())
    core.subdivide(plat, 4 if detail else 2, simple=True)
    core.displace(plat, 0.035, 0.3, "CLOUDS", 3)
    core.smooth(plat, 60)
    objs.append(plat)

    run = 0.30
    st = stair_section(col, name + "_stairs", stair_width, stair_steps, P / stair_steps, run, seed=seed + 3)
    st.location = (0, py0 - stair_steps * run, 0)
    objs.append(st)

    # --- timber frame
    red, dark = BoxBatch(), BoxBatch()
    bays_w, bays_d = max(3, round(W / 2.1)), max(2, round(D / 2.25))
    xs = [-W / 2 + W * i / bays_w for i in range(bays_w + 1)]
    ys = [D * j / bays_d for j in range(bays_d + 1)]
    pillars = [(x, 0.0) for x in xs] + [(x, D) for x in xs] + [(-W / 2, y) for y in ys[1:-1]] + [(W / 2, y) for y in ys[1:-1]]
    pil_objs = []
    for (x, y) in pillars:
        p = core.lathe(name + "_pillar", [(0.0, 0), (0.2, 0), (0.2, 0.03), (0.19, wall_h * 0.5), (0.175, wall_h), (0.0, wall_h)], 18, col, cap=False)
        p.location = (x, y, P)
        pil_objs.append(core.apply_transform(p))
        stone_p = core.lathe(name + "_plinth", [(0.0, 0), (0.29, 0), (0.3, 0.06), (0.25, 0.13), (0.0, 0.13)], 18, col, cap=False)
        stone_p.location = (x, y, P - 0.02)
        core.set_mat(stone_p, mats.stone_block())
        objs.append(core.apply_transform(core.smooth(stone_p, 50)))
    pil = core.join(pil_objs, name + "_pillars")
    core.set_mat(pil, mats.red_lacquer())
    objs.append(core.smooth(pil, 50))

    zt = P + wall_h
    for (xa, ya, xb, yb) in ((-W / 2, 0, W / 2, 0), (-W / 2, D, W / 2, D), (-W / 2, 0, -W / 2, D), (W / 2, 0, W / 2, D)):
        ext = 0.35
        d = Vector((xb - xa, yb - ya, 0)).normalized() * ext
        red.beam((xa - d.x, ya - d.y, zt - 0.02), (xb + d.x, yb + d.y, zt - 0.02), 0.3, 0.32, bevel=0.015)      # head beam
        red.beam((xa, ya, zt - 0.62), (xb, yb, zt - 0.62), 0.16, 0.24, bevel=0.012)                              # upper tie
        red.beam((xa, ya, P + 0.95), (xb, yb, P + 0.95), 0.14, 0.18, bevel=0.012)                                # dado rail
        red.beam((xa, ya, P + 0.1), (xb, yb, P + 0.1), 0.2, 0.2, bevel=0.012)                                    # sill
        dark.beam((xa - d.x * 0.6, ya - d.y * 0.6, zt + 0.36), (xb + d.x * 0.6, yb + d.y * 0.6, zt + 0.36), 0.46, 0.44, bevel=0.02)   # bracket band
    # bracket blocks on each pillar and between
    for (x, y) in pillars:
        red.add((0.5, 0.5, 0.16), (x, y, zt + 0.2), bevel=0.02)
        red.add((0.7, 0.7, 0.13), (x, y, zt + 0.52), bevel=0.02)

    # --- wall infill: solid dado, lattice above, glowing interior behind
    glow = BoxBatch()
    def infill(xa, ya, xb, yb, door=False, back=False):
        a, b = Vector((xa, ya)), Vector((xb, yb))
        t = (b - a).normalized()
        n = Vector((-t.y, t.x))                      # outward normal (bays are walked clockwise seen from above)
        L = (b - a).length
        ang = math.atan2(t.y, t.x)
        mid = (a + b) / 2
        inner = mid - n * 0.09
        z_lo, z_hi = P + 0.2, zt - 0.74
        if back:
            dark.add((L - 0.3, 0.08, z_hi - z_lo + 0.5), (mid.x, mid.y, (z_lo + z_hi) / 2), rot=(0, 0, ang))
            return
        if not door:
            dark.add((L - 0.36, 0.07, 0.72), (mid.x, mid.y, P + 0.57), rot=(0, 0, ang))            # dado panel
            z_lo = P + 1.05
        tmp = BoxBatch()
        _lattice(tmp, -L / 2 + 0.24, L / 2 - 0.24, z_lo, z_hi, 0.0, pitch=0.105 if door else 0.125, rails=5 if door else 3)
        lat = tmp.to_object("lat", col)
        lat.location = (mid.x + n.x * 0.02, mid.y + n.y * 0.02, 0)
        lat.rotation_euler = (0, 0, ang)
        core.apply_transform(lat)
        lattices.append(lat)
        glow.add((L - 0.4, 0.02, z_hi - z_lo), (inner.x, inner.y, (z_lo + z_hi) / 2), rot=(0, 0, ang))

    lattices = []
    mid_bay = bays_w // 2
    for i in range(bays_w):
        infill(xs[i + 1], 0, xs[i], 0, door=(i in (mid_bay - 1, mid_bay) if bays_w % 2 == 0 else i == mid_bay))
    for j in range(bays_d):
        infill(-W / 2, ys[j], -W / 2, ys[j + 1])
        infill(W / 2, ys[j + 1], W / 2, ys[j])
    for i in range(bays_w):
        infill(xs[i], D, xs[i + 1], D, back=True)
    lat = core.join(lattices, name + "_lattice")
    core.set_mat(lat, mats.dark_wood())
    objs.append(lat)
    g = glow.to_object(name + "_glow", col, mats.interior_glow(f"MAT_Interior_Glow_{name}", INTERIOR_GLOW, glow_strength))
    g.visible_shadow = False
    objs.append(g)

    # --- wooden deck and railing
    deckb = BoxBatch()
    deckb.add((px1 - px0 - 0.3, py1 - py0 - 0.3, 0.09), ((px0 + px1) / 2, (py0 + py1) / 2, P + 0.045), bevel=0.01)
    dk = deckb.to_object(name + "_deck", col, mats.deck_wood())
    objs.append(dk)
    rail_z = P + 0.09
    posts_done = set()
    def rail(xa, ya, xb, yb):
        L = math.hypot(xb - xa, yb - ya)
        n = max(1, round(L / 1.6))
        for i in range(n + 1):
            x, y = xa + (xb - xa) * i / n, ya + (yb - ya) * i / n
            key = (round(x, 2), round(y, 2))
            if key in posts_done:      # corner shared by two runs: one post only
                continue
            posts_done.add(key)
            red.add((0.1, 0.1, 0.95), (x, y, rail_z + 0.475), bevel=0.01)
            dark.add((0.15, 0.15, 0.07), (x, y, rail_z + 0.98), bevel=0.015)
        for h in (0.42, 0.82):
            red.beam((xa, ya, rail_z + h), (xb, yb, rail_z + h), 0.06, 0.07)
    ex, ey = px0 + 0.22, py0 + 0.22
    rail(ex, ey, -stair_width / 2 - 0.3, ey)
    rail(stair_width / 2 + 0.3, ey, -ex, ey)
    rail(ex, ey, ex, py1 - 0.22)
    rail(-ex, ey, -ex, py1 - 0.22)

    objs.append(red.to_object(name + "_frame_red", col, mats.red_lacquer()))
    objs.append(dark.to_object(name + "_frame_dark", col, mats.dark_wood()))

    # --- roof
    a, b = W / 2 + overhang, D / 2 + overhang
    shape = roofs.RoofShape(a, b, roof_rise, "irimoya", sag=1.42, gable_q=0.42, lift=0.6)
    wall_line = float(shape.height(0.0, b - overhang))
    z0 = zt + 0.6 - wall_line + 0.16
    roof = roofs.build(name + "_roof", shape, z0, col, detail=detail, overhang=overhang, seed=seed)
    roof.location = (0, D / 2, 0)
    objs.append(roof)

    root = core.group(name, col, objs, loc=loc, yaw=yaw)
    eave_z = z0 + float(shape.height(0.0, b)) - 0.2
    anchors = dict(
        lanterns=[(x, -overhang * 0.72, zt + 0.1) for x in xs],
        banners=[(-stair_width / 2 - 1.1, py0 - 0.3, 0.0), (stair_width / 2 + 1.1, py0 - 0.3, 0.0)],
        stair_foot=(0.0, py0 - stair_steps * run, 0.0), eave_z=eave_z, roof_top=z0 + roof_rise,
    )
    return root, anchors


def corridor(lib, col, start, end, width=2.6, name="Corridor", post_h=2.9, ruined=True, seed=5):
    """Roofed colonnade from start to end (world XY). The west side has collapsed in places."""
    r = core.rng(seed)
    a, b = Vector((*start, 0)), Vector((*end, 0))
    L = (b - a).length
    yaw = math.atan2((b - a).y, (b - a).x)
    red, stone = BoxBatch(), BoxBatch()
    n = max(2, round(L / 2.4))
    stone.add((L + 0.8, width + 0.9, 0.5), (0, 0, 0.0), bevel=0.04)
    for i in range(n + 1):
        x = -L / 2 + L * i / n
        for sy in (-1, 1):
            broken = ruined and sy == 1 and r.random() < 0.3
            h = post_h * (r.uniform(0.35, 0.7) if broken else 1.0)
            red.add((0.2, 0.2, h), (x, sy * width / 2, 0.25 + h / 2), rot=(r.gauss(0, 0.05) if broken else 0, r.gauss(0, 0.05) if broken else 0, 0), bevel=0.015)
            stone.add((0.42, 0.42, 0.2), (x, sy * width / 2, 0.3), bevel=0.03)
        red.beam((x, -width / 2 - 0.3, post_h + 0.2), (x, width / 2 + 0.3, post_h + 0.2), 0.16, 0.2)
    for sy in (-1, 1):
        red.beam((-L / 2 - 0.3, sy * width / 2, post_h + 0.32), (L / 2 + 0.3, sy * width / 2, post_h + 0.32), 0.2, 0.24, bevel=0.012)
        red.beam((-L / 2, sy * width / 2, 1.1), (L / 2, sy * width / 2, 1.1), 0.07, 0.09)
    shape = roofs.RoofShape(L / 2 + 0.5, width / 2 + 0.95, 1.35, "gable", sag=1.3, lift=0.25)
    holes = [(r.uniform(-L / 2, L / 2), r.uniform(0.2, width / 2 + 0.6), r.uniform(0.7, 1.5)) for _ in range(4)] if ruined else None
    roof = roofs.build(name + "_roof", shape, post_h + 0.45, col, detail=True, overhang=0.9, holes=holes, seed=seed)
    frame = red.to_object(name + "_frame", col, mats.red_lacquer())
    base = stone.to_object(name + "_base", col, mats.stone_block())
    _rough(base, 0.025, 0.25, 2)
    mid = (a + b) / 2
    return core.group(name, col, [frame, base, roof], loc=(mid.x, mid.y, 0), yaw=yaw)


def shed(lib, col, pos, yaw, size=(3.0, 3.2), name="Shed", post_h=2.6, rise=1.5, style="hip", seed=0):
    """Small roofed structure (gate house, well roof): four posts and a tiled roof."""
    w, d = size
    red, stone = BoxBatch(), BoxBatch()
    for sx in (-1, 1):
        for sy in (-1, 1):
            red.add((0.2, 0.2, post_h), (sx * w / 2, sy * d / 2, post_h / 2), bevel=0.015)
            stone.add((0.44, 0.44, 0.22), (sx * w / 2, sy * d / 2, 0.08), bevel=0.03)
        red.beam((sx * w / 2, -d / 2 - 0.25, post_h), (sx * w / 2, d / 2 + 0.25, post_h), 0.18, 0.22)
    for sy in (-1, 1):
        red.beam((-w / 2 - 0.25, sy * d / 2, post_h + 0.12), (w / 2 + 0.25, sy * d / 2, post_h + 0.12), 0.18, 0.22)
        red.beam((-w / 2, sy * d / 2, 1.0), (w / 2, sy * d / 2, 1.0), 0.07, 0.09)
    shape = roofs.RoofShape(w / 2 + 0.9, d / 2 + 0.9, rise, style, sag=1.4, lift=0.3)
    roof = roofs.build(name + "_roof", shape, post_h + 0.25, col, detail=True, overhang=0.85, seed=seed)
    frame = red.to_object(name + "_frame", col, mats.red_lacquer())
    base = stone.to_object(name + "_base", col, mats.stone_block())
    _rough(base, 0.02, 0.2, 2)
    return core.group(name, col, [frame, base, roof], loc=(pos[0], pos[1], 0), yaw=yaw)
