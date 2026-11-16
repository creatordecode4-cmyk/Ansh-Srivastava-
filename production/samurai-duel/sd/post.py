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
    if not film.EVENTS:                                              # without the fight built (putting the film together): the same four blows
        out = [film.film_of(f) for f in (film.HIT, film.HAMMER[2], film.KICK, film.CROSS)]
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


ASPECT = 2.1            # the picture inside the black bars, width to height (the frame itself stays 16:9)


def finish(im, ff, label=None, aspect=ASPECT, seed=0, keep_label=True):
    """The film look, laid on a finished frame when the film is put together: a grade (deeper
    blacks that stay open, a little contrast in the middle, cool shadows and warm highlights),
    film grain that changes every frame, a soft vignette, and black bars to a wide screen. An
    impact frame keeps its own colours and only gets the grain and the bars. A preview frame's
    label (light grey on a black box, lower left) is kept on top of the lower bar; frames rendered
    without one should pass keep_label=False. 'label' writes one."""
    raw = im.convert("RGB")
    x = np.asarray(raw, dtype=np.float32) / 255.0
    H, W = x.shape[:2]
    y0 = H - (max(11, H // 34) + 10)                                     # where a preview label's box starts
    box = 0
    if keep_label:
        dark = np.flatnonzero(x[y0].max(axis=1) > 0.02)
        box = int(dark[0]) if len(dark) else W
        box = box if 40 < box < W else 0
        if box:                                                         # the box ends 8 px after its text: the frame may be dark beyond it as well
            rows = x[y0 + 4:H - 3, :box]                                # the text is pure grey on black, one run of letters from x = 8;
            cols = np.flatnonzero(((rows.min(axis=2) > 0.45) & (np.ptp(rows, axis=2) < 0.02)).any(axis=0))
            if len(cols) and cols[0] <= 20:                             # whatever comes after a wide gap is the picture
                gaps = np.flatnonzero(np.diff(cols) > 30)
                box = min(box, int(cols[gaps[0]] if len(gaps) else cols[-1]) + 9)
            else:
                box = 0
    if not impact(ff):
        x = np.interp(x, [0.0, 0.06, 0.25, 0.5, 0.75, 0.94, 1.0], [0.012, 0.05, 0.215, 0.5, 0.79, 0.955, 0.985]).astype(np.float32)
        L = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
        x = L + (x - L) * 1.06                                          # a touch more colour
        x += (1.0 - L) ** 2 * np.array([-0.012, 0.004, 0.018]) + L ** 2 * np.array([0.020, 0.008, -0.012])
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2.0)
        x *= (1.0 - 0.30 * r ** 2.2)[..., None]
    rng = np.random.default_rng(seed * 7919 + ff)
    g = rng.normal(0.0, 1.0, (H, W)).astype(np.float32)
    g = np.asarray(Image.fromarray(np.clip(g * 40 + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.55)), dtype=np.float32) / 40.0 - 3.2
    L = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x += g[..., None] * 0.020 * (0.35 + 0.65 * (1.0 - np.abs(L * 2.0 - 1.0)))   # grain shows most in the middle tones
    bar = max(0, int(round((H - W / aspect) / 2.0)))
    out = Image.fromarray((np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    if bar:
        d = ImageDraw.Draw(out)
        d.rectangle((0, 0, W, bar - 1), fill=(0, 0, 0))
        d.rectangle((0, H - bar, W, H), fill=(0, 0, 0))
        if label:
            from PIL import ImageFont
            font = ImageFont.truetype("DejaVuSans.ttf", max(10, bar // 3))
            d.text((10, H - bar + (bar - font.size) // 2), label, font=font, fill=(150, 150, 150))
    if box:
        out.paste(raw.crop((0, y0, box, H)), (0, y0))
    return out


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
