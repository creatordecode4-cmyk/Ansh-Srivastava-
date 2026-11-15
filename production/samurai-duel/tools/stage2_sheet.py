"""Stage 2 preview for one fighter: turnaround, close-up, exploded parts and the reference panels.

    python3 -I tools/stage2_sheet.py ronin [--samples N] [--quick]
Writes previews/stage2_<who>.jpg and previews/stage2_<who>_parts.jpg
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from sd import core, fighters, render, ronin, studio  # noqa: E402

OUT = os.path.join(core.OUT, "stage2")
PREV = os.path.join(HERE, "previews")


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def label(im, text, size=24):
    d = ImageDraw.Draw(im)
    f = font(size)
    w = d.textlength(text, font=f)
    d.rectangle((0, 0, w + 36, size + 20), fill=(14, 14, 16))
    d.rectangle((0, 0, 6, size + 20), fill=(190, 24, 24))
    d.text((20, 8), text, fill=(235, 232, 226), font=f)
    return im


def exploded(sc, parts, path, samples):
    """Every separate object pulled apart on one line, seen from the front."""
    slots = []                                   # (objects, x offset, label, extra transform)

    def copy(ob, name):
        c = bpy.data.objects.new(name, ob.data)
        for m in ob.modifiers:
            if m.type in ("SUBSURF", "SOLIDIFY"):
                n = c.modifiers.new(m.name, m.type)
                for prop in ("levels", "render_levels", "boundary_smooth", "thickness", "offset"):
                    if hasattr(m, prop):
                        setattr(n, prop, getattr(m, prop))
        sc.collection.objects.link(c)
        c.matrix_world = ob.matrix_world.copy()
        return c

    def shift(ob, dx, dz=0.0, turn=0.0):
        ob.matrix_world = Matrix.Translation((dx, 0, dz)) @ Matrix.Rotation(turn, 4, "Z") @ ob.matrix_world
        return ob

    hat_at = parts["hat"].matrix_world.translation.copy()
    tilt = Matrix.Rotation(math.radians(32), 4, "X")            # tip the crown toward the camera
    x = -2.75
    hat = copy(parts["hat"], "X_hat")
    hat.matrix_world = Matrix.Translation((x, 0, hat_at.z - 0.3)) @ tilt
    slots.append((x, "KASA HAT"))
    x = -2.0
    yaw = parts["hat_spec"]["cut_yaw"]
    n = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    for h, sgn in zip(parts["hat_halves"], (-1, 1)):            # the hidden halves have no evaluated matrix: place them from the hat's
        c = bpy.data.objects.new("X_" + h.name, h.data)
        sc.collection.objects.link(c)
        c.matrix_world = Matrix.Translation((x + sgn * 0.07, 0, hat_at.z - 0.3)) @ tilt @ Matrix.Rotation(math.radians(9) * sgn, 4, "Y")
    slots.append((x, "HAT, PRE-CUT HALVES"))
    x = -1.25
    shift(copy(parts["cape"], "X_cape"), x, 0.0, math.pi)       # turned so its outer face shows
    slots.append((x, "CAPE"))
    x = 0.0
    shift(copy(parts["body"], "X_body"), x)
    slots.append((x, "BODY"))
    x = 1.15
    for o in parts["skirt"]:
        shift(copy(o, "X_" + o.name), x)
    slots.append((x, "HIP CLOTH x2"))
    x = 1.85
    for o in parts["tails"]:
        shift(copy(o, "X_" + o.name), x)
    slots.append((x, "KNOT TAILS x2"))
    stand = Matrix(((0, 0, 1, 0), (-1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 0, 1)))       # point down, flat toward the camera
    for k, (ks, ss) in enumerate(zip(parts["katanas"], parts["sayas"])):
        xk = 2.48 + k * 0.46
        for o, dxo in ((ks, -0.09), (ss, 0.09)):
            c = bpy.data.objects.new("X_" + o.name, o.data)
            sc.collection.objects.link(c)
            c.matrix_world = Matrix.Translation((xk + dxo, 0, 1.42)) @ stand
    slots.append((2.48 + 0.23, "KATANA + SCABBARD x2"))
    for o in parts["root"].children:
        o.hide_render = True
    W, H = 2600, 900
    render.setup(sc, W, H, samples, 0.03)
    sc.view_settings.exposure = -1.0
    cx, span = 0.1, 6.6
    cam = studio.camera(sc, (cx, 0, 0.95), 0, 0, 12.0, ortho=span, name="CAM_Explode")
    keyl = bpy.data.objects.get("LGT_TurnKey")
    if keyl:
        keyl.location = Vector((-3.0, -7.0, 6.0))
        core.look_at(keyl, Vector((0, 0, 1.0)))
        keyl.data.size, keyl.data.energy = 6.0, 9000
    render.still(sc, path, cam)
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    f = font(24)
    for xs, text in slots:
        px = W / 2 + (xs - cx) / span * W
        tw = d.textlength(text, font=f)
        d.text((px - tw / 2, H - 46), text, fill=(238, 236, 230), font=f)
    d.text((24, 18), "CYBER RONIN: every part is its own object", fill=(238, 236, 230), font=font(30))
    im.save(path)
    for o in list(sc.collection.objects):
        if o.name.startswith("X_"):
            bpy.data.objects.remove(o)
    for o in parts["root"].children:
        o.hide_render = o.name.startswith("Ronin_Kasa_Half")
    return im


def main():
    who = sys.argv[1]
    n = int(arg("--samples", 48))
    os.makedirs(PREV, exist_ok=True)
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB", hide_render=True)
    col = core.collection(who.upper())
    t0 = time.time()
    parts = fighters.ronin(lib, col)
    print(f"BUILD {time.time() - t0:.1f}s, tris {core.tri_count()}", flush=True)
    studio.world(sc, strength=0.4)
    studio.floor(sc, 0.0)
    H = ronin.HEIGHT
    S = 620 if "--quick" in sys.argv else 900
    t0 = time.time()
    turn = os.path.join(OUT, f"{who}_s2_turn.png")
    studio.turnaround(sc, turn, (0, 0, H * 0.54), H * 1.14, width=2.0, azimuths=(0, 40, 180, 215), size=(S, S), samples=n, exposure=-1.0)
    close = os.path.join(OUT, f"{who}_s2_close.png")
    studio.turnaround(sc, close, (0, 0.02, 1.66), 0.78, azimuths=(-28, 150), size=(S, S), samples=n, exposure=-1.0)
    print(f"RENDER views {time.time() - t0:.1f}s", flush=True)
    t0 = time.time()
    ex = exploded(sc, parts, os.path.join(OUT, f"{who}_s2_parts.png"), n)
    print(f"RENDER parts {time.time() - t0:.1f}s", flush=True)

    # ---- sheets
    turn_im, close_im = Image.open(turn).convert("RGB"), Image.open(close).convert("RGB")
    ref = Image.open(os.path.join(HERE, "refs", f"{who}_sheet.png")).convert("RGB")
    ref_t = ref.crop((5, 632, 745, 1010))                     # T-pose front + back panels of the user's sheet
    ref_v = ref.crop((5, 5, 1320, 630))                       # front / side / back / three-quarter
    W = turn_im.width
    rv = ref_v.resize((W, round(ref_v.height * W / ref_v.width)), Image.LANCZOS)
    rt_w = W - 2 * S - 12
    rt = ref_t.resize((rt_w, round(ref_t.height * rt_w / ref_t.width)), Image.LANCZOS)
    row3_h = max(S, rt.height)
    sheet = Image.new("RGB", (W, rv.height + 12 + S + 12 + row3_h), (10, 10, 11))
    sheet.paste(label(rv, "YOUR REFERENCE SHEET"), (0, 0))
    y = rv.height + 12
    sheet.paste(label(turn_im, "BLENDER: Cyber Ronin, rest pose (T-pose for rigging)"), (0, y))
    y += S + 12
    sheet.paste(label(close_im, "CLOSE-UP"), (0, y))
    sheet.paste(label(rt, "REFERENCE: T-pose"), (2 * S + 12, y))
    out = os.path.join(PREV, f"stage2_{who}.jpg")
    sheet.save(out, quality=88)
    ex.save(os.path.join(PREV, f"stage2_{who}_parts.jpg"), quality=88)
    print("SHEET", out, sheet.size)


main()
