"""Stage 1a: arena BLOCKOUT (clay pass).

Builds every arena element as a named placeholder ("PH_<prop>") at its final position,
so image-to-3D GLBs can later be swapped in by name and instanced.
Run:  python3 scripts/build_arena.py            -> renders clay hero + top-down previews
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
random.seed(7)


# ---------- helpers ----------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def put(obj, c, name):
    obj.name = name
    for u in list(obj.users_collection):
        u.objects.unlink(obj)
    c.objects.link(obj)
    return obj


def apply():
    """Bake the active object's transform into its mesh (origin -> world origin)."""
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def box(c, name, loc, size, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    apply()
    return put(o, c, name)


def cyl(c, name, loc, r, h, r2=None, verts=16, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r if r2 is None else r2,
                                    depth=h, location=loc, rotation=rot)
    apply()
    return put(bpy.context.object, c, name)


def roof(c, name, loc, sx, sy, h, top=0.25):
    """Hipped roof: 4-sided frustum scaled to footprint sx * sy."""
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=math.sqrt(0.5), radius2=math.sqrt(0.5) * top,
                                    depth=1, location=loc, rotation=(0, 0, math.radians(45)))
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    o.scale = (sx, sy, h)
    apply()
    return put(o, c, name)


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def instance(src, c, name, loc, rot_z=0.0, scale=1.0):
    o = src.copy()  # linked duplicate: shares mesh data = instancing
    o.name = name
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    o.scale = (scale,) * 3
    c.objects.link(o)
    return o


# ---------- prop placeholders (origin at ground centre) ----------
def make_lantern(c, name, broken=False):
    parts = [box(c, "t", (0, 0, 0.15), (1.0, 1.0, 0.3)),
             box(c, "t", (0, 0, 0.42), (0.75, 0.75, 0.25)),
             cyl(c, "t", (0, 0, 1.05), 0.3, 1.0, r2=0.22, verts=8),
             box(c, "t", (0, 0, 1.62), (0.8, 0.8, 0.15)),
             box(c, "t", (0, 0, 1.95), (0.5, 0.5, 0.5))]
    if broken:
        parts.append(roof(c, "t", (0.12, 0.05, 2.33), 1.0, 0.9, 0.28, top=0.3))
        parts[-1].rotation_euler = (math.radians(14), math.radians(-9), 0.3)
    else:
        parts += [roof(c, "t", (0, 0, 2.36), 1.25, 1.25, 0.32, top=0.2),
                  cyl(c, "t", (0, 0, 2.66), 0.12, 0.28, verts=8),
                  cyl(c, "t", (0, 0, 2.86), 0.16, 0.12, r2=0.04, verts=8)]
    return join(parts, name)


def make_torii(c, name, w, h):
    px = w * 0.36
    parts = []
    for s in (-1, 1):
        parts.append(cyl(c, "t", (s * px, 0, h * 0.44), 0.36, h * 0.88, r2=0.3, verts=20))
        parts.append(box(c, "t", (s * px, 0, 0.3), (1.0, 1.0, 0.6)))
    parts += [box(c, "t", (0, 0, h * 0.72), (w * 0.95, 0.3, 0.45)),      # nuki (lower beam)
              box(c, "t", (0, 0, h * 0.80), (0.4, 0.28, 0.55)),          # gakuzuka (centre strut)
              box(c, "t", (0, 0, h * 0.90), (w * 1.12, 0.5, 0.4)),       # shimaki
              box(c, "t", (0, 0, h * 0.965), (w * 1.28, 0.75, 0.3))]    # kasagi (top lintel)
    return join(parts, name)


def make_stairs(c, name, w, steps, rise=0.22, run=0.42, rail=True):
    parts = []
    for i in range(steps):
        parts.append(box(c, "t", (0, i * run + run / 2, (i + 1) * rise / 2), (w, run, (i + 1) * rise)))
    if rail:
        for s in (-1, 1):
            parts.append(box(c, "t", (s * (w / 2 + 0.3), steps * run / 2, steps * rise / 2 + 0.2),
                             (0.6, steps * run, steps * rise + 0.4)))
    return join(parts, name)


def make_temple(c, name, size, face="x+"):
    """Hall on a stone plinth with hipped roof, pillars and front stairs. Front faces `face`."""
    sx, sy, sz = size
    plinth = 1.1
    parts = [box(c, "t", (0, 0, plinth / 2), (sx + 2.4, sy + 2.4, plinth)),
             box(c, "t", (0, 0, plinth + sz / 2), (sx, sy, sz)),
             roof(c, "t", (0, 0, plinth + sz + 0.45), sx + 4.2, sy + 4.2, 0.9, top=0.72),
             roof(c, "t", (0, 0, plinth + sz + 2.2), sx + 2.2, sy + 2.2, 2.6, top=0.12)]
    n = 6
    for i in range(n):  # veranda pillars along the long front side
        y = -sy / 2 + i * sy / (n - 1)
        parts.append(cyl(c, "t", (sx / 2 + 0.75, y, plinth + sz / 2), 0.2, sz, verts=10))
    hall = join(parts, name)
    st = make_stairs(c, name + "_stairs", 4.5, 5, rise=plinth / 5)
    st.rotation_euler = (0, 0, math.radians(90))                # climbs toward -X
    st.location = (sx / 2 + 1.2 + 5 * 0.42, 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    st.select_set(True)
    bpy.context.view_layer.objects.active = st
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    st.parent = hall
    hall.rotation_euler = (0, 0, {"x+": 0, "x-": math.pi, "y-": -math.pi / 2}[face])
    return hall


def make_tree(c, name):
    parts = [cyl(c, "t", (0.3, 0, 1.6), 0.38, 3.4, r2=0.22, verts=10, rot=(0, math.radians(12), 0)),
             cyl(c, "t", (1.5, 0.2, 3.9), 0.2, 3.0, r2=0.08, verts=8, rot=(0, math.radians(55), 0.2)),
             cyl(c, "t", (-0.4, 0.6, 4.2), 0.18, 2.6, r2=0.07, verts=8, rot=(math.radians(-35), math.radians(-20), 0))]
    for _ in range(11):
        p = Vector((random.uniform(-2.6, 3.4), random.uniform(-2.4, 2.4), random.uniform(3.8, 6.4)))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=random.uniform(1.0, 1.8), location=p)
        bpy.context.object.scale.z = 0.6
        apply()
        o = put(bpy.context.object, c, "t")
        parts.append(o)
    return join(parts, name)


def make_banner(c, name):
    parts = [cyl(c, "t", (0, 0, 2.6), 0.05, 5.2, verts=8),
             cyl(c, "t", (0.45, 0, 5.0), 0.035, 1.2, verts=8, rot=(0, math.radians(90), 0)),
             box(c, "t", (0.5, 0, 3.45), (0.85, 0.03, 3.0))]
    return join(parts, name)


def make_paper_lantern(c, name):
    parts = [cyl(c, "t", (0, 0, 0), 0.26, 0.7, verts=14),
             cyl(c, "t", (0, 0, 0.4), 0.16, 0.1, verts=14),
             cyl(c, "t", (0, 0, -0.4), 0.16, 0.1, verts=14),
             cyl(c, "t", (0, 0, -0.65), 0.03, 0.4, verts=6)]
    return join(parts, name)


def make_rock(c, name, seed):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5)
    o = bpy.context.object
    r = random.Random(seed)
    for v in o.data.vertices:
        v.co *= r.uniform(0.7, 1.25)
    o.scale = (r.uniform(0.8, 1.6), r.uniform(0.7, 1.2), r.uniform(0.4, 0.8))
    apply()
    return put(o, c, name)


# ---------- build ----------
def build():
    scn = bpy.context.scene
    env, props, src = coll("COL_Arena_Structures"), coll("COL_Arena_Props"), coll("COL_Prop_Sources")
    src.hide_render = True

    # ground: courtyard slab + surrounding terrain
    cx, cy = L.COURT["x"], L.COURT["y"]
    box(env, "PH_floor_courtyard", (0, 0, -0.1), (cx[1] - cx[0], cy[1] - cy[0], 0.2))
    box(env, "PH_ground_outer", (0, 5, -0.25), (90, 90, 0.2))

    # torii on a low dais, stairs behind it rising to the back temple
    t = L.TORII
    box(env, "PH_torii_dais", (t["pos"][0], t["pos"][1], 0.15), (t["width"] + 5, 4.0, 0.3))
    torii = make_torii(env, "PH_torii_gate", t["width"], t["height"])
    torii.location = (t["pos"][0], t["pos"][1], 0.3)
    s = L.TORII_STAIRS
    st = make_stairs(env, "PH_temple_stairs_main", s["width"], s["steps"])
    st.location = (s["pos"][0], s["pos"][1], 0)
    top = s["steps"] * 0.22
    box(env, "PH_upper_terrace", (s["pos"][0], s["pos"][1] + s["steps"] * 0.42 + 9, top / 2), (30, 18, top))

    tm = make_temple(env, "PH_temple_main", L.TEMPLE_MAIN["size"], "x+")
    tm.location = (*L.TEMPLE_MAIN["pos"], 0)
    tr = make_temple(env, "PH_temple_right", L.TEMPLE_RIGHT["size"], "x-")
    tr.location = (*L.TEMPLE_RIGHT["pos"], 0)
    tb = make_temple(env, "PH_temple_back", (L.TEMPLE_BACK["size"][1], L.TEMPLE_BACK["size"][0], L.TEMPLE_BACK["size"][2]), "y-")
    tb.location = (*L.TEMPLE_BACK["pos"], top)

    # instanced props: one source mesh each, linked duplicates in the scene
    lan = make_lantern(src, "SRC_stone_lantern")
    lan_b = make_lantern(src, "SRC_broken_stone_lantern", broken=True)
    for i, (x, y, broken) in enumerate(L.LANTERNS):
        instance(lan_b if broken else lan, props, f"PH_lantern.{i:02d}", (x, y, 0), random.uniform(-0.3, 0.3))
    tree = make_tree(src, "SRC_cherry_tree")
    for i, (x, y) in enumerate(L.CHERRY_TREES):
        instance(tree, props, f"PH_cherry_tree.{i:02d}", (x, y, 0), random.uniform(0, 6.28), random.uniform(1.1, 1.5))
    ban = make_banner(src, "SRC_banner")
    for i, (x, y) in enumerate(L.BANNERS):
        instance(ban, props, f"PH_banner.{i:02d}", (x, y, 0), random.uniform(-0.4, 0.4))
    pl = make_paper_lantern(src, "SRC_paper_lantern")
    for i, (x, y, z) in enumerate(L.PAPER_LANTERNS):
        instance(pl, props, f"PH_paper_lantern.{i:02d}", (x, y, z))
    rocks = [make_rock(src, f"SRC_rock.{k}", k) for k in range(3)]
    n = 0
    for zx, zy in L.DEBRIS_ZONES:
        for _ in range(7):
            sc = random.uniform(0.3, 1.3)
            instance(random.choice(rocks), props, f"PH_rock.{n:02d}",
                     (zx + random.gauss(0, 1.3), zy + random.gauss(0, 1.3), 0.15 * sc), random.uniform(0, 6.28), sc)
            n += 1
    # pine backdrop
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=2.6, radius2=0, depth=13, location=(0, 0, 6.5))
    apply()
    pine = put(bpy.context.object, src, "SRC_pine")
    for i in range(34):
        a = math.radians(-20 + i * 220 / 33)
        r = random.uniform(40, 48)
        instance(pine, props, f"PH_pine.{i:02d}", (3 + r * math.cos(a), 6 + r * math.sin(a), 0), 0, random.uniform(0.8, 1.6))
    for o in src.objects:
        o.location = (0, -200, 0)  # park sources out of view

    # moon disc (emissive in the lit pass)
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=16, fill_type="NGON", location=(18, 170, 62))
    moon = put(bpy.context.object, env, "PH_blood_moon")
    moon.rotation_euler = (math.radians(70), 0, math.radians(6))

    # duel marks (not rendered): where the fighters stand off
    for nm, x in (("MARK_oni_start", -4.0), ("MARK_ronin_start", 4.0)):
        e = bpy.data.objects.new(nm, None)
        e.location = (x, 0, 0)
        e.empty_display_type = "ARROWS"
        scn.collection.objects.link(e)


def cameras():
    scn = bpy.context.scene
    def cam(name, loc, target, lens=None, ortho=None):
        d = bpy.data.cameras.new(name)
        o = bpy.data.objects.new(name, d)
        scn.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        if ortho:
            d.type, d.ortho_scale = "ORTHO", ortho
        else:
            d.lens = lens
        d.clip_end = 600
        return o
    return {"hero": cam("CAM_hero_wide", (-1.5, -16.5, 0.7), (1.8, 6, 4.6), lens=22),
            "top": cam("CAM_topdown", (0, 4, 80), (0, 4.01, 0), ortho=62)}


def clay_light():
    scn = bpy.context.scene
    w = bpy.data.worlds.new("WORLD_clay")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.57, 0.6, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    scn.world = w
    d = bpy.data.lights.new("LGT_Key_Moon", "SUN")
    d.energy, d.angle = 2.6, math.radians(4)
    o = bpy.data.objects.new("LGT_Key_Moon", d)
    o.rotation_euler = (math.radians(58), 0, math.radians(-150))
    scn.collection.objects.link(o)
    clay = bpy.data.materials.new("MAT_clay")
    clay.use_nodes = True
    b = clay.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1)
    b.inputs["Roughness"].default_value = 0.85
    scn.view_layers[0].material_override = clay


def render(cam, path, res=(1280, 720), samples=24):
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.samples = samples
    scn.cycles.use_denoising = True
    scn.cycles.max_bounces = 4
    scn.view_settings.view_transform = "AgX"
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.fps = 24
    scn.frame_end = 720
    scn.camera = cam
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    reset()
    build()
    cams = cameras()
    clay_light()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "arena_blockout.blend"))
    render(cams["hero"], os.path.join(ROOT, "previews", "stage1a_clay_hero.png"))
    render(cams["top"], os.path.join(ROOT, "previews", "stage1a_clay_topdown.png"), res=(1280, 960))
