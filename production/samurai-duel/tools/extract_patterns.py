"""Lift the painted patterns off the weapon panels of the parts sheets.

    python3 tools/extract_patterns.py          # writes assets/gen/pattern_*.png and a check sheet

Each blade or scabbard in the sheet is a curved strip. For every column the strip's top and
bottom are found (anything that is not the grey panel background), the strip is straightened to
u = along the length, v = edge to spine, and the light design is separated from the dark base.
The masks are small in the sheet (about 25 px wide), so they are upscaled, blurred and
thresholded into clean shapes for a 4096 x 256 texture.
"""
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(HERE, "assets", "gen")

# name: (sheet, box in sheet pixels, flip_v, light rule)
JOBS = {
    "oni_blade": ("oni_parts.png", (300, 700, 912, 772), False, "warm"),
    "oni_saya": ("oni_parts.png", (548, 858, 912, 940), False, "warm"),
    "ronin_blade": ("ronin_parts.png", (252, 740, 790, 802), False, "white"),
    "ronin_saya": ("ronin_parts.png", (270, 930, 760, 990), False, "white"),
}
UP = 8


def strip(sheet, box, rule):
    im = Image.open(os.path.join(HERE, "refs", sheet)).convert("RGB").crop(box)
    im = im.resize((im.width * UP, im.height * UP), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a.mean(axis=2)
    bg = np.median(lum[:UP * 3])                      # top rows of the crop are panel background
    obj = (lum < bg - 0.13) | (lum > bg + 0.16)
    H, W = obj.shape
    top, bot = np.full(W, np.nan), np.full(W, np.nan)
    for x in range(W):
        col = obj[:, x]
        if col.sum() < UP * 6:
            continue
        # longest run of object pixels in this column
        d = np.diff(np.concatenate([[0], col.astype(np.int8), [0]]))
        s, e = np.where(d == 1)[0], np.where(d == -1)[0]
        k = np.argmax(e - s)
        if e[k] - s[k] >= UP * 6:
            top[x], bot[x] = s[k], e[k]
    ok = ~np.isnan(top)
    xs = np.arange(W)
    x0, x1 = xs[ok].min(), xs[ok].max()
    # smooth outline: low-order fit of the centre line and of the width
    cx = xs[ok]
    mid = np.polyval(np.polyfit(cx, (top[ok] + bot[ok]) / 2, 4), xs)
    wid = np.polyval(np.polyfit(cx, (bot[ok] - top[ok]), 3), xs)
    U, V = 4096, 256
    uu = np.linspace(x0, x1, U)
    out = np.zeros((V, U, 3), dtype=np.float32)
    for j in range(V):
        v = (j + 0.5) / V                           # 0 = edge (bottom of the strip in the sheet), 1 = spine
        yy = np.interp(uu, xs, mid) + (0.5 - v) * np.interp(uu, xs, wid)
        xi = np.clip(uu.astype(int), 0, W - 1)
        yi = np.clip(yy.astype(int), 0, H - 1)
        out[V - 1 - j] = a[yi, xi]
    return out, (x0, x1, W, H)


def light_mask(s, rule):
    lum = s.mean(axis=2)
    if rule == "warm":
        m = ((s[..., 0] - s[..., 2]) > 0.07) & (lum > 0.42)
    else:
        m = lum > 0.52
    return m


def main():
    os.makedirs(GEN, exist_ok=True)
    rows = []
    for name, (sheet, box, flip, rule) in JOBS.items():
        s, info = strip(sheet, box, rule)
        m = light_mask(s, rule).astype(np.float32)
        im = Image.fromarray((m * 255).astype(np.uint8))
        im = im.filter(ImageFilter.GaussianBlur(5)).point(lambda p: 255 if p > 118 else 0).filter(ImageFilter.GaussianBlur(1.2))
        im.save(os.path.join(GEN, f"pattern_{name}.png"))
        Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8)).save(os.path.join(GEN, f"strip_{name}.png"))
        print(name, info, "coverage", round(float(m.mean()), 3))
        rows += [Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8)).resize((2048, 128)), im.convert("RGB").resize((2048, 128))]
    sheet = Image.new("RGB", (2048, 132 * len(rows)), (40, 40, 44))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * 132))
    sheet.save(os.path.join(GEN, "pattern_check.png"))


if __name__ == "__main__":
    main()
