"""Assemble the arena from the layout: every prop is a master in PROPS_LIB, placed as instances."""
import math
import time

import bpy
import numpy as np
from mathutils import Vector

from . import core, dressing, env, floor, fx, lantern, layout, mats, nature, temple, torii
from .core import BoxBatch


def ground_z(x, y):
    """Height of the walkable ground (courtyard, low torii terrace, upper terrace)."""
    fs, bs = layout.FRONT_STEPS, layout.BACK_STAIRS
    y_t1 = fs["y_bottom"] + fs["steps"] * fs["run"]
    if y < y_t1:
        return 0.0
    if y < bs["y_bottom"] + 0.5 or (abs(x) < bs["half_width"] + 0.6 and y < bs["y_bottom"] + bs["steps"] * bs["run"]):
        return layout.TERRACE1_Z
    return layout.TERRACE2_Z


def _north_terraces(lib, col):
    fs, bs = layout.FRONT_STEPS, layout.BACK_STAIRS
    objs = []
    y_t1 = fs["y_bottom"] + fs["steps"] * fs["run"]
    y_t2 = bs["y_bottom"] + 0.5
    y_top = bs["y_bottom"] + bs["steps"] * bs["run"]
    z1, z2 = layout.TERRACE1_Z, layout.TERRACE2_Z
    bb = BoxBatch()
    # low terrace the torii stands on (kerb on both sides of the front steps)
    bb.add((64, y_t2 - y_t1 + 0.4, z1 + 0.6), (0, (y_t1 + y_t2) / 2 + 0.2, z1 / 2 - 0.3), bevel=0.03)
    # upper terrace with a recess for the back stairs
    hw = bs["half_width"] + 0.62
    for sx in (-1, 1):
        bb.add((32 - hw, 60, z2 + 0.6), (sx * (hw + (32 - hw) / 2), y_t2 + 30, z2 / 2 - 0.3), bevel=0.05)
    bb.add((2 * hw + 0.2, 60 - (y_top - y_t2), z2 + 0.6), (0, y_top + (60 - (y_top - y_t2)) / 2, z2 / 2 - 0.3), bevel=0.05)
    ter = bb.to_object("Terrace_North", col, mats.stone_block())
    core.subdivide(ter, 5, simple=True)
    core.displace(ter, 0.05, 0.45, "CLOUDS", 3)
    core.smooth(ter, 60)
    objs.append(ter)
    front = temple.stair_section(col, "Stairs_ToriiFront", fs["half_width"] * 2, fs["steps"], fs["rise"], fs["run"], walls=False, seed=2)
    front.location = (0, fs["y_bottom"], 0)
    back = temple.stair_section(col, "Stairs_ToriiBack", bs["half_width"] * 2, bs["steps"], bs["rise"], bs["run"], walls=True, seed=4)
    back.location = (0, bs["y_bottom"], z1)
    return objs + [front, back]


def _south_side(lib, col):
    """Roofed boundary wall with a gate at the south end (not in the reference panel; backdrop for reverse angles)."""
    from . import roofs
    sw = layout.SOUTH_WALL
    y, h = sw["y"], sw["height"]
    objs = []
    for (xa, xb) in ((sw["x0"], sw["gate_x"] - sw["gate_w"] / 2), (sw["gate_x"] + sw["gate_w"] / 2, sw["x1"])):
        L, mid = xb - xa, (xa + xb) / 2
        stone, wood = BoxBatch(), BoxBatch()
        stone.add((L, 0.75, 0.9), (mid, y, 0.3), bevel=0.04)
        wood.add((L, 0.42, h - 0.7), (mid, y, 0.7 + (h - 0.7) / 2), bevel=0.015)
        n = max(2, round(L / 2.2))
        for i in range(n + 1):
            wood.add((0.2, 0.52, h - 0.65), (xa + L * i / n, y, 0.7 + (h - 0.65) / 2), bevel=0.012)
        so = stone.to_object("SouthWall_base", col, mats.stone_block())
        core.subdivide(so, 3, simple=True)
        core.displace(so, 0.03, 0.3, "CLOUDS", 3)
        core.smooth(so, 60)
        wo = wood.to_object("SouthWall_wall", col, mats.red_wood())
        shape = roofs.RoofShape(L / 2 + 0.15, 0.85, 0.5, "gable", sag=1.25, lift=0.12)
        rf = roofs.build("SouthWall_roof", shape, h + 0.02, col, detail=True, overhang=0.5, rafters=False)
        rf.location = (mid, y, 0)
        objs += [so, wo, rf]
    temple.shed(lib, col, (sw["gate_x"], y), 0.0, (sw["gate_w"] - 0.3, 2.6), name="SouthGate", post_h=3.6, rise=1.7, style="gable", seed=33)
    return objs


def _scatter_rocks(lib, col, rocks, seed=12):
    r = core.rng(seed)
    n = 0
    for (x0, y0, x1, y1, dens) in layout.RUBBLE:
        xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        area = (xb - xa) * (yb - ya)
        for _ in range(int(area * 4.5 * dens)):
            x, y = r.uniform(xa, xb), r.uniform(ya, yb)
            fa = layout.FIGHT_AREA
            if fa["x0"] < x < fa["x1"] and fa["y0"] < y < fa["y1"]:
                continue
            src = r.choice(rocks)
            target = r.choices([r.uniform(0.12, 0.3), r.uniform(0.3, 0.7), r.uniform(0.7, 1.25)], [6, 3, 1])[0]
            s = target / max(0.05, src.get("size", 1.0))
            ob = core.instance(src, f"Rock_{n:03d}", col, (x, y, ground_z(x, y) - 0.03 * target), (r.uniform(-0.4, 0.4), r.uniform(-0.4, 0.4), r.uniform(0, 6.28)), s)
            n += 1
    return n


def build(detail=True, particles=True, verbose=True):
    t0 = time.time()
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB", hide_render=True)
    arena = core.collection("ARENA")
    C = {k: core.collection(k, arena) for k in ("FLOOR", "TORII", "TEMPLE", "EAST", "LANTERNS", "DRESSING", "ROCKS", "TREES", "BACKGROUND")}
    envc = core.collection("ENV")
    fxc = core.collection("FX")
    camc = core.collection("CAMERAS")

    def log(msg):
        if verbose:
            print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    floor.build(lib, C["FLOOR"])
    log("floor")
    _north_terraces(lib, C["TORII"])
    tor = torii.build(lib)
    T = layout.TORII
    core.instance(tor, "Torii", C["TORII"], (T["pos"][0], T["pos"][1], layout.TERRACE1_Z), (0, 0, T["yaw"]))
    hb = [dressing.hanging_banner(lib, f"PROP_HangingBanner_{i + 1}", (0.52, 2.3 + 0.35 * (i % 2)), seed=i) for i in range(2)]
    for i, fx_ in enumerate((-0.86, -0.52, 0.5, 0.84)):
        core.instance(hb[i % 2], f"Banner_Torii_{i + 1}", C["DRESSING"], (T["pos"][0] + fx_ * tor["nuki_half"], T["pos"][1] - 0.02, layout.TERRACE1_Z + tor["nuki_z"]))
    torii_lantern_x = (-0.28, 0.28)
    log("torii + terraces")

    tp = layout.TEMPLE
    hall, anc = temple.hall(lib, C["TEMPLE"], "Temple", tp["width"], tp["depth"], tp["platform"], tp["deck"], tp["stair_width"], tp["stair_steps"],
                            wall_h=tp["wall_h"], roof_rise=tp["roof_rise"], detail=detail, loc=(*tp["facade_mid"], 0), yaw=tp["yaw"] + math.pi / 2)
    rear, _ = temple.hall(lib, C["BACKGROUND"], "RearHall", 15.0, 9.0, 1.2, 2.0, 4.0, 7, wall_h=4.6, roof_rise=5.2, detail=False,
                          loc=(*layout.REAR_HALL["pos"], layout.TERRACE2_Z), yaw=0.0, seed=7, glow_strength=0.16)
    log("temple halls")
    cor = layout.CORRIDOR
    temple.corridor(lib, C["EAST"], cor["start"], cor["end"], cor["width"])
    for i, s in enumerate(layout.SMALL_ROOFS):
        temple.shed(lib, C["EAST" if s["pos"][0] > 0 else "TEMPLE"], s["pos"], s["yaw"], s["size"], name=f"Shed_{i + 1}", seed=20 + i)
    _south_side(lib, C["BACKGROUND"])
    log("corridor + sheds + south wall")

    intact = lantern.stone_lantern(lib, broken=False, height=2.9)
    broken = lantern.stone_lantern(lib, broken=True, height=2.9)
    for i, (x, y, yaw, brk) in enumerate(layout.LANTERNS):
        core.instance(broken if brk else intact, f"StoneLantern_{'ABCDEF'[i]}", C["LANTERNS"], (x, y, ground_z(x, y)), (0, 0, yaw))
    log("stone lanterns")

    # paper lanterns under the temple eaves, banners by the stairs and the torii
    pl = dressing.paper_lantern(lib)
    bn = dressing.banner(lib)
    hm = hall.matrix_world
    bpy.context.view_layer.update()
    hm = hall.matrix_world.copy()
    for i, p in enumerate(anc["lanterns"]):
        wp = hm @ Vector(p)
        core.instance(pl, f"PaperLantern_T{i + 1}", C["DRESSING"], wp)
    for i, fx_ in enumerate(torii_lantern_x):      # two paper lanterns under the torii tie beam: motivated red light on the gate
        core.instance(pl, f"PaperLantern_G{i + 1}", C["DRESSING"], (T["pos"][0] + fx_ * tor["nuki_half"], T["pos"][1] - 0.05, layout.TERRACE1_Z + tor["nuki_z"]))
    for i, p in enumerate(anc["banners"]):
        wp = hm @ Vector(p)
        core.instance(bn, f"Banner_T{i + 1}", C["DRESSING"], wp, (0, 0, hall.rotation_euler.z + (0.2 if i else -0.2)))
    for i, (x, y, yaw) in enumerate(((-4.6, 9.0, 0.15), (4.6, 9.0, -0.15), (-6.4, 9.2, 0.3), (6.4, 9.2, -0.3))):
        core.instance(bn, f"Banner_G{i + 1}", C["DRESSING"], (x, y, ground_z(x, y)), (0, 0, yaw))
    log("paper lanterns + banners")

    rocks = nature.rock_set(lib)
    n = _scatter_rocks(lib, C["ROCKS"], rocks)
    log(f"rocks: {len(rocks)} masters, {n} instances")

    for i, (x, y, h, cr) in enumerate(layout.CHERRY):
        nature.cherry_tree(lib, C["TREES"], seed=i + 1, height=h, crown=cr, loc=(x, y, ground_z(x, y)), yaw=i * 1.3, density=1.0 if detail else 0.4)
    for i, (x, y, h, cr, dens) in enumerate(layout.FRAMING_TREES):
        nature.cherry_tree(lib, C["TREES"], seed=40 + i, height=h, crown=cr, name=f"Cherry_Frame_{i + 1}", loc=(x, y, 0), yaw=i * 2.1,
                           density=dens if detail else dens * 0.6)
    pines = [nature.pine_tree(lib, seed=s, height=h) for s, h in ((1, 13.0), (2, 16.0), (3, 11.0), (4, 14.5))]
    r = core.rng(31)
    placed = 0
    while placed < 46:
        ang, rad = r.uniform(0, 6.28), r.uniform(33, 62)
        x, y = math.cos(ang) * rad, math.sin(ang) * rad + 6
        if y < -30:
            continue
        core.instance(r.choice(pines), f"Pine_{placed:02d}", C["BACKGROUND"], (x, y, ground_z(x, y) - 0.3), (0, 0, r.uniform(0, 6.28)), r.uniform(0.8, 1.35))
        placed += 1
    log("trees")

    env.world(sc)
    env.moon(envc)
    env.lights(envc)
    env.fog(envc)
    log("environment")
    if particles:
        fx.falling(lib, fxc)
        fx.ground_petals(lib, fxc)
        log("particles")

    tmp = bpy.data.collections.get("_tmp_build")
    if tmp:
        for o in list(tmp.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(tmp)
    cams = cameras(sc, camc)
    sc.frame_start, sc.frame_end = 1, 720
    log("done")
    return sc, cams


def cameras(sc, col):
    out = {}
    # hero still: low angle from the south-east, matching the framing of refs/arena.png
    hc = layout.HERO_CAM
    cd = bpy.data.cameras.new("CAM_Hero")
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = hc["lens"], 36.0, 0.05, 3000.0
    cd.dof.use_dof = True
    cd.dof.focus_distance = hc["focus"]
    cd.dof.aperture_fstop = hc["fstop"]
    cam = bpy.data.objects.new("CAM_Hero", cd)
    cam.location = hc["pos"]
    core.look_at(cam, hc["target"])
    col.objects.link(cam)
    out["hero"] = cam
    # top-down layout view, same framing as the TOP-DOWN LAYOUT reference panel
    td = bpy.data.cameras.new("CAM_TopDown")
    td.lens, td.sensor_width, td.clip_end = 36.0, 36.0, 400.0     # slight tilt like the reference panel, so lantern glows show
    tcam = bpy.data.objects.new("CAM_TopDown", td)
    cx, cy = layout.w(410, 193.5)
    tcam.location = (cx, cy - 11.0, 45.0)
    core.look_at(tcam, (cx, cy + 1.0, 0.0))
    col.objects.link(tcam)
    out["topdown"] = tcam
    sc.camera = cam
    return out
