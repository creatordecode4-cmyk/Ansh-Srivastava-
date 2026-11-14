"""Set dressing: red paper lanterns and tattered cloth banners with the flower crest.

References: RED PAPER LANTERN and RED CLOTH BANNER in refs/arena_props.png. The crest (ring
with a five-petal flower) is drawn here as an image so both props share the same emblem.
"""
import math
import os

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import core, mats
from .mats import NT

GEN = os.path.join(core.ASSETS, "gen")
PAPER_RED = (0.9, 0.055, 0.03)


def _crest(draw, cx, cy, R, fg, bg):
    """Ring + five round petals + centre dot (the mon on the sheet)."""
    draw.ellipse((cx - R, cy - R, cx + R, cy + R), fill=fg)
    draw.ellipse((cx - R * 0.86, cy - R * 0.86, cx + R * 0.86, cy + R * 0.86), fill=bg)
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        px, py, pr = cx + math.cos(a) * R * 0.43, cy + math.sin(a) * R * 0.43, R * 0.27
        draw.ellipse((px - pr, py - pr, px + pr, py + pr), fill=fg)
    draw.ellipse((cx - R * 0.15, cy - R * 0.15, cx + R * 0.15, cy + R * 0.15), fill=bg)
    draw.ellipse((cx - R * 0.08, cy - R * 0.08, cx + R * 0.08, cy + R * 0.08), fill=fg)


def lantern_texture():
    path = os.path.join(GEN, "paper_lantern.png")
    if not os.path.exists(path):
        os.makedirs(GEN, exist_ok=True)
        W, H = 1024, 512
        im = Image.new("RGB", (W, H), (235, 32, 22))
        d = ImageDraw.Draw(im)
        for y in range(0, H, 20):       # bamboo ribs under the paper
            d.line([(0, y), (W, y)], fill=(150, 14, 10), width=3)
            d.line([(0, y + 4), (W, y + 4)], fill=(255, 70, 40), width=1)
        for cx in (W * 0.25, W * 0.75):  # crest front and back
            _crest(d, cx, H * 0.5, H * 0.3, (12, 8, 8), (235, 32, 22))
        im = im.filter(ImageFilter.GaussianBlur(0.8))
        im.save(path)
    return path


def banner_texture():
    path = os.path.join(GEN, "banner.png")
    if not os.path.exists(path):
        os.makedirs(GEN, exist_ok=True)
        W, H = 512, 2048
        rs = np.random.RandomState(4)
        base = np.zeros((H, W, 4), np.uint8)
        yy = np.linspace(0, 1, H)[:, None]
        stain = core.fbm2(np.linspace(0, 6, W)[None, :] + 0 * yy, yy * 24 + 0 * np.linspace(0, 1, W)[None, :], 4, 7)
        red = np.clip(150 - 70 * yy ** 1.5 + 40 * (stain - 0.5), 30, 190)       # dirtier toward the hem
        base[..., 0] = red
        base[..., 1] = red * 0.13
        base[..., 2] = red * 0.11
        base[..., 3] = 255
        im = Image.fromarray(base, "RGBA")
        d = ImageDraw.Draw(im)
        _crest(d, W / 2, H * 0.33, W * 0.36, (216, 196, 160, 255), (118, 16, 13, 255))
        a = np.array(im)
        # tattered hem: strips of different length, plus a few tears
        hem = (H * (0.86 + 0.13 * core.fbm2(np.linspace(0, 9, W), np.zeros(W), 3, 11))).astype(int)
        for x in range(W):
            a[hem[x]:, x, 3] = 0
        for _ in range(7):
            x0, y0, ln = rs.randint(20, W - 20), rs.randint(int(H * 0.45), int(H * 0.9)), rs.randint(60, 260)
            a[y0:y0 + ln, max(0, x0 - 2):x0 + rs.randint(2, 7), 3] = 0
        Image.fromarray(a, "RGBA").save(path)
    return path


def _paper_mat():
    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree)
        b = m.node_tree.nodes["Principled BSDF"]
        uv = nt.new("ShaderNodeTexCoord").outputs["UV"]
        tex = nt.image(lantern_texture(), uv, box=False).outputs[0]
        nt.put(b.inputs["Base Color"], tex)
        nt.put(b.inputs["Emission Color"], tex)
        b.inputs["Emission Strength"].default_value = 1.6
        b.inputs["Roughness"].default_value = 0.65
        return m

    return mats.get("MAT_Paper_Lantern", build)


def _cloth_mat():
    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree)
        b = m.node_tree.nodes["Principled BSDF"]
        uv = nt.new("ShaderNodeTexCoord").outputs["UV"]
        tex = nt.image(banner_texture(), uv, box=False)
        nt.put(b.inputs["Base Color"], tex.outputs[0])
        nt.put(b.inputs["Alpha"], tex.outputs[1])
        b.inputs["Roughness"].default_value = 0.85
        b.inputs["Sheen Weight"].default_value = 0.12
        weave = nt.noise(nt.coords("Object", 1.0), 900.0, 2.0, 0.6)
        nt.link(nt.bump(weave, 0.25, 0.002), b.inputs["Normal"])
        return m

    return mats.get("MAT_Cloth_Banner", build)


def paper_lantern(lib, name="PROP_PaperLantern", power=45.0):
    """Master collection: paper body, black caps, hanging loop, tassel and a light. Origin = hang point."""
    master = bpy.data.collections.new(name)
    lib.children.link(master)
    tmp = core.collection("_tmp_build")
    Rm, Hh = 0.21, 0.56
    prof = []
    for i in range(41):
        t = i / 40
        r = Rm * (0.52 + 0.48 * math.sin(math.pi * (0.08 + 0.84 * t)) ** 0.75) + 0.004 * math.cos(t * 28 * 2 * math.pi)
        prof.append((r, -0.12 - Hh * (1 - t)))
    body = core.lathe(name + "_paper", prof, 36, master, cap=False, uv=True)
    core.smooth(body, 80)
    core.set_mat(body, _paper_mat())
    body.visible_shadow = False
    parts = []
    for z0, z1 in ((-0.12, -0.065), (-0.12 - Hh - 0.05, -0.12 - Hh)):
        c = core.lathe("cap", [(0.0, z1), (0.118, z1), (0.125, (z0 + z1) / 2), (0.118, z0), (0.0, z0)], 24, tmp, cap=False)
        parts.append(core.smooth(c, 50))
    parts.append(core.tube("wire", [(0, 0, 0), (0, 0, -0.07)], 0.006, tmp, segs=6))
    parts.append(core.tube("hoop", [(0.1 * math.cos(a), 0, -0.07 + 0.06 * math.sin(a)) for a in np.linspace(0, math.pi, 10)], 0.007, tmp, segs=6))
    black = core.join(parts, name + "_caps")
    core.set_mat(black, mats.black_lacquer())
    core.link(black, master)
    zt = -0.12 - Hh - 0.05
    tas = core.join([core.tube("cord", [(0, 0, zt), (0, 0, zt - 0.12)], 0.007, tmp, segs=6),
                     core.lathe("tas", [(0.0, zt - 0.12), (0.03, zt - 0.12), (0.045, zt - 0.17), (0.04, zt - 0.4), (0.0, zt - 0.4)], 12, tmp, cap=False)], name + "_tassel")
    core.set_mat(tas, mats.emission("MAT_Tassel_Red", (0.35, 0.02, 0.015), 0.0))
    core.link(tas, master)
    ld = bpy.data.lights.new(name + "_light", "POINT")
    ld.color, ld.energy, ld.shadow_soft_size = (1.0, 0.13, 0.05), power, 0.16
    ld.volume_factor = 0.1            # light the wood and floor, not the whole fog bank
    lo = bpy.data.objects.new(name + "_light", ld)
    lo.location = (0, 0, -0.12 - Hh / 2)
    master.objects.link(lo)
    return master


def banner(lib, name="PROP_Banner", height=3.6, cloth=(0.62, 2.35), seed=0):
    """Master collection: pole with crossbar and a hanging cloth (clean quad grid, ready for cloth sim)."""
    master = bpy.data.collections.new(name)
    lib.children.link(master)
    tmp = core.collection("_tmp_build")
    w, h = cloth
    nu, nv = 13, 48
    P = np.zeros((nu, nv, 3))
    for i in range(nu):
        for j in range(nv):
            u, v = i / (nu - 1), j / (nv - 1)        # v = 0 at the hem, 1 at the crossbar
            free = (1 - v) ** 1.3
            P[i, j] = ((u - 0.5) * w, 0.07 * free * math.sin(5.2 * (1 - v) + 1.3 * u + seed) + 0.02 * free * math.sin(9 * u + seed), height - 0.12 - h * (1 - v))
    cl = core.grid_obj(name + "_cloth", P, master, uv=True)
    # flip V so the image top (crest) sits at the crossbar
    core.smooth(cl, 180)
    core.set_mat(cl, _cloth_mat())
    pole = core.tube("pole", [(-w / 2 - 0.1, 0.02, 0), (-w / 2 - 0.1, 0.02, height)], [0.03, 0.022], tmp, segs=8)
    bar = core.tube("bar", [(-w / 2 - 0.22, 0.02, height - 0.1), (w / 2 + 0.12, 0.02, height - 0.1)], 0.018, tmp, segs=8)
    wood = core.join([pole, bar], name + "_pole")
    core.smooth(wood, 60)
    core.set_mat(wood, mats.dark_wood())
    core.link(wood, master)
    return master


def hanging_banner(lib, name="PROP_HangingBanner", cloth=(0.5, 2.5), seed=0):
    """Narrow cloth hung from a beam by a short rod (the banners under the torii). Origin = hang point."""
    master = bpy.data.collections.new(name)
    lib.children.link(master)
    tmp = core.collection("_tmp_build")
    w, h = cloth
    nu, nv = 11, 46
    P = np.zeros((nu, nv, 3))
    for i in range(nu):
        for j in range(nv):
            u, v = i / (nu - 1), j / (nv - 1)
            free = (1 - v) ** 1.3
            P[i, j] = ((u - 0.5) * w, 0.06 * free * math.sin(4.6 * (1 - v) + 1.1 * u + seed) + 0.015 * free * math.sin(8 * u + seed), -0.08 - h * (1 - v))
    cl = core.grid_obj(name + "_cloth", P, master, uv=True)
    core.smooth(cl, 180)
    core.set_mat(cl, _cloth_mat())
    rod = core.tube("rod", [(-w / 2 - 0.05, 0, -0.07), (w / 2 + 0.05, 0, -0.07)], 0.016, tmp, segs=8)
    ties = [core.tube("tie", [(sx * w * 0.35, 0, 0.0), (sx * w * 0.35, 0, -0.07)], 0.006, tmp, segs=5) for sx in (-1, 1)]
    wood = core.join([rod] + ties, name + "_rod")
    core.set_mat(wood, mats.dark_wood())
    core.link(wood, master)
    return master
