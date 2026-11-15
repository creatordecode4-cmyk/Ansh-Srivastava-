"""Materials for the fighters' weapons, armour fittings and cloth (masters carry the MAT_ prefix).

Blades, scabbards and handle wraps are textured through their own UV maps:
  UVMap   u = along the length, v = around the cross-section
  UVSide  u = along the length, v = edge (0) to spine (1), the same on both faces
Painted designs come from the parts sheets (tools/extract_patterns.py); wrap textures are drawn here.
"""
import math
import os

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import core
from .mats import NT, _new, get

GEN = os.path.join(core.ASSETS, "gen")


def _img(path, colorspace="sRGB"):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def _uv_tex(nt, path, uv_name, colorspace="Non-Color", scale=(1, 1, 1), offset=(0, 0, 0), extension="EXTEND"):
    uv = nt.new("ShaderNodeUVMap")
    uv.uv_map = uv_name
    mp = nt.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Location"].default_value = offset
    nt.link(uv.outputs[0], mp.inputs[0])
    n = nt.new("ShaderNodeTexImage", image=_img(path, colorspace))
    n.extension = extension
    nt.link(mp.outputs[0], n.inputs[0])
    return n.outputs[0], mp.outputs[0]


def pattern_path(name):
    """Design mask lifted from the sheet; built on first use."""
    p = os.path.join(GEN, f"pattern_{name}.png")
    if not os.path.exists(p):
        import importlib.util
        spec = importlib.util.spec_from_file_location("extract_patterns", os.path.join(core.HERE, "tools", "extract_patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    return p


# ----------------------------------------------------------------------------- metals
def metal(name, color, rough=0.25, wear=0.25, grain=0.0):
    """Cast or forged fitting: slightly uneven polish, darker in the recesses."""
    def build(name):
        m, nt, b = _new(name)
        vec = nt.coords("Object", 1.0)
        n = nt.noise(vec, 55.0, 4.0, 0.6)
        geo = nt.new("ShaderNodeNewGeometry")
        cavity = nt.map_range(geo.outputs["Pointiness"], 0.42, 0.5, 0.45, 1.0)       # recesses keep their patina
        col = nt.mix(nt.math("MULTIPLY", wear, nt.math("SUBTRACT", 1.0, cavity)), color, tuple(c * 0.25 for c in color))
        nt.put(b.inputs["Base Color"], col)
        b.inputs["Metallic"].default_value = 1.0
        nt.put(b.inputs["Roughness"], nt.map_range(n, 0.3, 0.7, rough * 0.75, rough * 1.35))
        if grain:
            nt.link(nt.bump(nt.noise(vec, 400.0, 2.0, 0.5), grain, 0.0005), b.inputs["Normal"])
        return m

    return get(name, build)


def gold():
    return metal("MAT_Metal_Gold", (0.83, 0.56, 0.24), rough=0.27, wear=0.6)


def silver():
    return metal("MAT_Metal_Silver", (0.72, 0.73, 0.75), rough=0.22, wear=0.5)


def black_steel():
    return metal("MAT_Metal_BlackSteel", (0.02, 0.02, 0.022), rough=0.32, wear=0.2)


def void():
    """Inside of a scabbard mouth: nothing comes back out."""
    def build(name):
        m, nt, b = _new(name)
        b.inputs["Base Color"].default_value = (0, 0, 0, 1)
        b.inputs["Roughness"].default_value = 1.0
        b.inputs["Specular IOR Level"].default_value = 0.0
        return m

    return get("MAT_Void", build)


# ----------------------------------------------------------------------------- blades
def blade(name, pattern, inlay=(0.80, 0.66, 0.42), edge_v=0.24, tip_u=0.957):
    """Katana blade: mirror-polished cutting edge and point, blackened flats carrying the
    inlaid design from the sheet. The wavy temper line follows the edge."""
    def build(name):
        m, nt, b = _new(name)
        mask, uvv = _uv_tex(nt, pattern_path(pattern), "UVSide")
        sep = nt.new("ShaderNodeSeparateXYZ")
        nt.link(uvv, sep.inputs[0])
        u, v = sep.outputs[0], sep.outputs[1]
        wob = nt.new("ShaderNodeTexNoise", noise_dimensions="1D")     # hamon: an irregular wave along the blade
        nt.link(nt.math("MULTIPLY", u, 46.0), wob.inputs["W"])
        wob.inputs["Scale"].default_value = 1.0
        wob.inputs["Detail"].default_value = 2.0
        line = nt.math("ADD", edge_v, nt.math("MULTIPLY", nt.math("SUBTRACT", wob.outputs[0], 0.5), 0.09))
        polished = nt.math("MAXIMUM", nt.map_range(nt.math("SUBTRACT", v, line), -0.012, 0.012, 1.0, 0.0),
                           nt.map_range(u, tip_u - 0.004, tip_u + 0.004, 0.0, 1.0))
        inl = nt.math("MULTIPLY", mask, nt.math("SUBTRACT", 1.0, polished))
        col = nt.mix(inl, (0.012, 0.012, 0.014, 1), (*inlay, 1))
        col = nt.mix(polished, col, (0.80, 0.81, 0.83, 1))
        nt.put(b.inputs["Base Color"], col)
        b.inputs["Metallic"].default_value = 1.0
        fine = nt.noise(nt.coords("Object", (40.0, 2.0, 400.0)), 30.0, 2.0, 0.5)       # grain running along the blade
        rgh = nt.mix(inl, 0.30, 0.24)
        rgh = nt.mix(polished, rgh, 0.07)
        nt.put(b.inputs["Roughness"], nt.math("ADD", rgh, nt.map_range(fine, 0.3, 0.7, -0.015, 0.03)))
        nt.link(nt.bump(nt.math("ADD", nt.math("MULTIPLY", inl, 0.6), nt.math("MULTIPLY", polished, -0.5)), 0.25, 0.0003), b.inputs["Normal"])
        return m

    return get(name, build)


# ----------------------------------------------------------------------------- handle wrap (tsuka-ito)
def wrap_textures(tag, diamonds=11, skin=(214, 208, 196), cord=(10, 10, 11), W=2048, H=512):
    """Colour + height maps of a cord-wrapped grip: skin-covered core showing through diamond
    openings on the two flat faces (v = 0.25 and 0.75), cords crossing between them."""
    os.makedirs(GEN, exist_ok=True)
    pc, ph_ = os.path.join(GEN, f"wrap_{tag}_col.png"), os.path.join(GEN, f"wrap_{tag}_hgt.png")
    if os.path.exists(pc) and os.path.exists(ph_):
        return pc, ph_
    uu, vv = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
    pitch = 1.0 / diamonds
    du = np.abs(((uu / pitch) % 1.0) - 0.5) * pitch                      # distance to the nearest diamond centre along u
    col = np.zeros((H, W, 3), dtype=np.float32) + np.array(cord, dtype=np.float32) / 255.0
    hgt = np.zeros((H, W), dtype=np.float32) + 0.62
    rng = np.random.default_rng(3)
    nod = Image.fromarray((rng.random((H // 3, W // 3)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    nod = np.asarray(nod).astype(np.float32) / 255.0
    for centre in (0.25, 0.75):
        dv = np.abs(vv - centre)
        d = du / (pitch * 0.33) + dv / 0.125                              # diamond metric: < 1 inside the opening
        inside = d < 1.0
        skin_col = np.array(skin, dtype=np.float32) / 255.0 * (0.82 + 0.3 * nod[..., None])
        col = np.where(inside[..., None], skin_col, col)
        hgt = np.where(inside, 0.12 + 0.16 * nod, hgt)
        ridge = np.clip(1.0 - np.abs(d - 1.12) / 0.16, 0, 1) * (dv < 0.2)      # cord edge standing proud around each opening
        hgt = np.maximum(hgt, 0.62 + 0.3 * ridge)
        knot = np.clip(1.0 - (np.abs(((uu / pitch + 0.5) % 1.0) - 0.5) * pitch) / (pitch * 0.2), 0, 1) * np.clip(1.0 - dv / 0.07, 0, 1)
        hgt = np.maximum(hgt, 0.62 + 0.38 * knot)                           # the twist where the cords cross
    # braid lines in the cord
    braid = 0.5 + 0.5 * np.sin((uu * W / 7.0 + vv * H / 5.0) * 2 * math.pi / 3.0)
    cordmask = (hgt >= 0.6).astype(np.float32)
    hgt = hgt + cordmask * (braid - 0.5) * 0.07
    col = col * (1.0 + cordmask[..., None] * (braid[..., None] - 0.5) * 0.5)
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)).save(pc)
    Image.fromarray((np.clip(hgt, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)).save(ph_)
    return pc, ph_


def grip(name, tag, diamonds=11, skin=(214, 208, 196)):
    def build(name):
        m, nt, b = _new(name)
        pc, ph_ = wrap_textures(tag, diamonds, skin)
        col, _ = _uv_tex(nt, pc, "UVMap", "sRGB", extension="REPEAT")
        hgt, _ = _uv_tex(nt, ph_, "UVMap", "Non-Color", extension="REPEAT")
        nt.put(b.inputs["Base Color"], col)
        nt.put(b.inputs["Roughness"], nt.map_range(hgt, 0.2, 0.7, 0.5, 0.68))
        b.inputs["Sheen Weight"].default_value = 0.25
        nt.link(nt.bump(hgt, 0.9, 0.0016), b.inputs["Normal"])
        return m

    return get(name, build)


# ----------------------------------------------------------------------------- scabbards
def lacquer(name, base=(0.010, 0.010, 0.012), pattern=None, inlay=(0.80, 0.66, 0.42), inlay_metal=1.0, pattern_from=0.56,
            scales=0.0, rough=0.16):
    """Lacquered wood: deep gloss under a clear coat. pattern = sheet design placed on the last
    part of the length (from u = pattern_from); scales > 0 presses a snakeskin relief into it."""
    def build(name):
        m, nt, b = _new(name)
        col, rgh, hgt, metal_ = base, rough, None, 0.0
        if pattern:
            k = 1.0 / (1.0 - pattern_from)
            mask, uvv = _uv_tex(nt, pattern_path(pattern), "UVSide", scale=(k, 1, 1), offset=(-pattern_from * k, 0, 0), extension="CLIP")
            col = nt.mix(mask, (*base, 1), (*inlay, 1))
            metal_ = nt.math("MULTIPLY", mask, inlay_metal)
            rgh = nt.mix(mask, rough, 0.3)
            hgt = nt.math("MULTIPLY", mask, 0.5)
        if scales:
            uv = nt.new("ShaderNodeUVMap")
            uv.uv_map = "UVMap"
            mp = nt.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (scales, scales * 0.11, 1.0)
            mp.inputs["Rotation"].default_value = (0, 0, math.radians(45))
            nt.link(uv.outputs[0], mp.inputs[0])
            cell = nt.voronoi(mp.outputs[0], 1.0, "DISTANCE_TO_EDGE", randomness=0.12)
            relief = nt.map_range(cell, 0.0, 0.16, 0.0, 1.0)
            hgt = relief if hgt is None else nt.math("ADD", hgt, nt.math("MULTIPLY", relief, 0.6))
            rgh = nt.math("ADD", rgh, nt.map_range(relief, 0.0, 1.0, 0.16, 0.0))
        nt.put(b.inputs["Base Color"], col)
        nt.put(b.inputs["Metallic"], metal_)
        nt.put(b.inputs["Roughness"], rgh)
        b.inputs["Coat Weight"].default_value = 0.6
        b.inputs["Coat Roughness"].default_value = 0.06
        if hgt is not None:
            nt.link(nt.bump(hgt, 0.45, 0.0005), b.inputs["Normal"])
        return m

    return get(name, build)


# ----------------------------------------------------------------------------- cords, tassels, cloth
def silk(name, color, rough=0.5, thread=0.0, thread_axis="Z"):
    """Silk cord or tassel thread; thread > 0 adds fine fibres running along one object axis."""
    def build(name):
        m, nt, b = _new(name)
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Sheen Weight"].default_value = 0.3
        b.inputs["Sheen Roughness"].default_value = 0.4
        b.inputs["Sheen Tint"].default_value = (*[min(1.0, c * 1.6 + 0.02) for c in color], 1)      # silk shines in its own colour
        if thread:
            s = {"X": (8.0, 900.0, 900.0), "Y": (900.0, 8.0, 900.0), "Z": (900.0, 900.0, 8.0)}[thread_axis]
            fib = nt.noise(nt.coords("Object", s), 1.0, 2.0, 0.6)
            nt.link(nt.bump(fib, thread, 0.0006), b.inputs["Normal"])
            nt.put(b.inputs["Base Color"], nt.mix(nt.map_range(fib, 0.3, 0.7, 0.0, 1.0), tuple(c * 0.6 for c in color) + (1,), (*color, 1)))
        return m

    return get(name, build)


def red_silk(thread=0.0):
    return silk("MAT_Silk_Red" + ("_Thread" if thread else ""), (0.50, 0.012, 0.010), thread=thread)


def black_cord():
    return silk("MAT_Cord_Black", (0.012, 0.012, 0.013), rough=0.6)
