"""Touches drawn on a rendered frame, in the manner of hand-drawn action: impact frames on the
heaviest blows and speed lines on the charges. Both use a matte of the fighters (render.mask):
white where a fighter is.

impact(ff)    which impact frame a film frame is (0 for none). The heaviest blows - the first clash,
              the third overhead cut, the kick, the crossing - are each marked by two frames as the
              blow lands: an ink frame (the fighters as black shapes picked out by their brightest
              edges, on pale paper, with what blazed - sparks, flash, fire - in red) and a red frame
              (the same shapes on red).
lines(ff)     who the speed lines close in on and how strong they are on a film frame (0..1).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import film


def _heaviest():
    out = []
    for e in film.EVENTS:
        if e["kind"] == "kick" or (e["kind"] == "clash" and (e["f"] in (film.HIT, film.CROSS) or e.get("power", 1.0) >= 1.5)):
            out.append(film.film_of(e["f"]))
    return sorted(set(out))


def impact(ff):
    for a in _heaviest():
        if ff == a:
            return 1
        if ff == a + 1:
            return 2
    return 0


def _soft(matte, radius=0.8):
    m = matte.filter(ImageFilter.GaussianBlur(radius)) if radius > 0 else matte
    return np.asarray(m, dtype=np.float32) / 255.0


def impact_frame(im, kind, matte):
    """The rendered frame as an impact frame (see the module's notes)."""
    g = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    lo, hi = np.percentile(g, 2), np.percentile(g, 99.5)
    g = np.clip((g - lo) / max(1e-3, hi - lo), 0.0, 1.0)
    fig = _soft(matte)
    lit = np.clip((g - 0.62) * 3.5, 0.0, 1.0)                           # a fighter's brightest edges stay pale
    hot = np.clip((g - 0.82) * 6.0, 0.0, 1.0) * (1.0 - fig)              # sparks, flash and fire round them
    if kind == 1:
        ground = np.array([0.96, 0.93, 0.88])
        shade = np.clip(1.0 - (1.0 - g) * 0.25, 0.0, 1.0)                # the paper keeps a faint trace of the scene
        rgb = shade[..., None] * ground[None, None, :]
        rgb = rgb * (1.0 - hot[..., None]) + hot[..., None] * np.array([0.82, 0.05, 0.03])
        figure = lit[..., None] * np.array([0.85, 0.82, 0.78])
    else:
        k = 0.55 + 0.45 * np.clip((g - 0.15) * 2.0, 0.0, 1.0)
        rgb = k[..., None] * np.array([0.92, 0.06, 0.04])
        rgb = rgb * (1.0 - hot[..., None]) + hot[..., None] * np.array([1.0, 0.75, 0.55])
        figure = lit[..., None] * np.array([0.30, 0.02, 0.02])
    rgb = rgb * (1.0 - fig[..., None]) + figure * fig[..., None]
    return Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))


# speed lines: (first film frame, last film frame, who they close in on)
RUNS = [(241, 251, "oni"), (252, 262, "ronin"), (529, 537, "oni")]


def lines(ff):
    for a, b, who in RUNS:
        if a <= ff <= b:
            u = (ff - a) / max(1, b - a)
            return who, math.sin(math.pi * min(1.0, 0.15 + u)) ** 0.5
    return None, 0.0


def speed_lines(im, centre, strength, seed, matte=None, clear=0.30):
    """Thin streaks from the edges of the frame toward 'centre' (pixels), stopping short of it and
    kept off the fighters (matte)."""
    W, H = im.size
    rng = np.random.default_rng(seed)
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    R = math.hypot(W, H)
    for _ in range(int(90 * strength)):
        a = rng.uniform(0.0, 2.0 * math.pi)
        r0 = rng.uniform(clear, clear * 1.7) * min(W, H)
        p0 = (centre[0] + math.cos(a) * r0, centre[1] + math.sin(a) * r0)
        p1 = (centre[0] + math.cos(a) * R, centre[1] + math.sin(a) * R)
        d.line([p0, p1], fill=int(255 * rng.uniform(0.35, 0.85)), width=1 if rng.random() < 0.8 else 2)
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255.0 * 0.40 * strength
    if matte is not None:
        m *= 1.0 - _soft(matte, 2.0)
    out = np.asarray(im.convert("RGB"), dtype=np.float32) * (1.0 - m[..., None]) + np.array([236.0, 240.0, 250.0]) * m[..., None]
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8))
