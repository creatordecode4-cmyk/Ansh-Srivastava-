"""Cinematic grade for the rendered frames (numpy + Pillow, no GPU).

Order (correct first, then the look):
  0. Deband flat areas (hides JPEG blocks before contrast)
  1. Graduated ND on the sky + warm sun glow   (gives the washed-out sky depth)
  2. Filmic tone curve: black point, S-curve, soft highlight shoulder (no crushed blacks)
  3. Split tone: teal-blue shadows, warm golden highlights
  4. Selective colour: greens toward emerald (less neon yellow), turquoise water kept, vibrance
  5. Bloom + red halation on highlights
  6. Detail: luma unsharp mask (perceived sharpness)
  7. Lens: subtle chromatic aberration at the edges, soft vignette
  8. Fine film grain (luma weighted, changes every frame)

Usage:
  python3 cinematic_grade.py <in_dir> <out_dir> [first last]     # f_####.jpg -> f_####.jpg
  python3 cinematic_grade.py --test <in.jpg> <out.jpg>
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)

# ---- look settings (safe ranges from the colour-grading skill) ----
BLACK_IN, WHITE_IN = 0.085, 0.985      # input black / white point
BLACK_OUT, WHITE_OUT = 0.025, 0.975    # never pure 0 / pure 1
S_STRENGTH, S_PIVOT, S_MIX = 2.4, 0.46, 0.62
SKY_ND = 0.34                          # sky darkening at the top edge
SHADOW_TINT = np.array([-0.030, 0.006, 0.034], np.float32)   # teal-blue
HIGH_TINT = np.array([0.034, 0.014, -0.030], np.float32)     # warm golden
VIBRANCE = 0.22
BLOOM, HALATION = 0.13, 0.035
SHARPEN = 0.30
VIGNETTE = 0.20
CA_PX = 1.0
GRAIN = 0.010


def _curve_lut():
    x = np.linspace(0, 1, 4096, dtype=np.float64)
    t = np.clip((x - BLACK_IN) / (WHITE_IN - BLACK_IN), 0, 1)
    a, b = np.tanh(-S_STRENGTH * S_PIVOT), np.tanh(S_STRENGTH * (1 - S_PIVOT))
    s = (np.tanh(S_STRENGTH * (t - S_PIVOT)) - a) / (b - a)
    y = S_MIX * s + (1 - S_MIX) * t
    # soft shoulder: highlights roll off instead of clipping
    y = np.where(y > 0.8, 0.8 + (1 - np.exp(-(y - 0.8) / 0.2 * 1.2)) * 0.2 / (1 - np.exp(-1.2)), y)
    return (BLACK_OUT + (WHITE_OUT - BLACK_OUT) * y).astype(np.float32)


CURVE = _curve_lut()


def _box(a, r, axis):
    """Box filter of radius r along an axis (edge padded), via cumulative sums."""
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float32)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(arr, sigma, down=4):
    """Approximate Gaussian blur (3 box passes) of a float HxW(x3) array on a downscaled copy."""
    h, w = arr.shape[:2]
    a = arr
    if down > 1:
        a = a[: h // down * down, : w // down * down]
        shp = (h // down, down, w // down, down) + a.shape[2:]
        a = a.reshape(shp).mean((1, 3))
    s = sigma / down
    r = max(1, int(round(np.sqrt(12 * s * s / 3 + 1) / 2 - 0.5)))
    for _ in range(3):
        a = _box(_box(a, r, 0), r, 1)
    if down > 1:   # smooth bilinear upscale (no blocks)
        a = a.astype(np.float32)
        chans = [a] if a.ndim == 2 else [a[..., c] for c in range(a.shape[2])]
        up = [np.asarray(Image.fromarray(np.ascontiguousarray(c), "F").resize((w, h), Image.BILINEAR)) for c in chans]
        a = up[0] if a.ndim == 2 else np.stack(up, -1)
    return a.astype(np.float32)


def grade(f, frame_no=0):
    h, w, _ = f.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ny, nx = yy / h, xx / w
    Y = f @ LUMA

    # 0. deband: smooth only flat areas (sky, mist) so JPEG blocks don't show after the contrast boost
    fb = blur(f, 3.0, down=1)
    flat = np.clip(1 - np.abs(Y - fb @ LUMA) / 0.018, 0, 1) ** 2
    f = f + (fb - f) * flat[..., None]
    Y = f @ LUMA

    # 1. graduated ND on bright, non-green pixels near the top (sky only, trees untouched)
    sky = np.clip(1 - ny / 0.56, 0, 1) ** 1.2
    Yb = blur(Y, 40, down=8)                                     # smooth mask: no rings or edges
    sky *= np.clip((Yb - 0.50) / 0.25, 0, 1)
    sky *= 1 - blur(np.clip((Y - 0.93) / 0.05, 0, 1), 3, down=1)   # keep the sun disc bright
    sky *= np.clip(1 - (f[..., 1] - f[..., 2]) * 8, 0, 1)
    f = f * (1 - SKY_ND * sky[..., None])
    f = f + sky[..., None] * np.array([-0.045, 0.0, 0.05], np.float32)
    # warm glow around the sun (brightest spot in the upper half)
    small = Y[: h // 2: 8, ::8]
    sy, sx = np.unravel_index(np.argmax(small), small.shape)
    if small[sy, sx] > 0.93:
        d2 = ((xx - sx * 8) ** 2 + (yy - sy * 8) ** 2) / (0.13 * w) ** 2
        f = f + np.exp(-d2)[..., None] * np.array([0.06, 0.035, 0.0], np.float32)

    # 2. filmic tone curve on luma (keeps hue), then a little per-channel for punch
    Y = np.clip(f @ LUMA, 1e-4, 1)
    Yc = CURVE[np.clip((Y * 4095).astype(np.int32), 0, 4095)]
    f = f * (Yc / Y)[..., None]
    Y = Yc

    # 3. split tone
    ws = (1 - Y) ** 2
    wh = Y ** 2 * np.clip((0.97 - Y) / 0.15, 0, 1)      # pure whites (waterfall, sun) stay neutral
    f = f + ws[..., None] * SHADOW_TINT + wh[..., None] * HIGH_TINT

    # 4. selective colour + vibrance
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    yellow_green = np.clip((g - b) * 4, 0, 1) * np.clip((r - b) * 3, 0, 1) * np.clip((g - r) * 6 + 0.5, 0, 1)
    f[..., 0] -= 0.035 * yellow_green                          # neon lime -> richer green
    f[..., 2] += 0.012 * yellow_green
    turq = np.clip((b - r) * 4, 0, 1) * np.clip((g - r) * 4, 0, 1)
    Y = f @ LUMA
    chroma = f - Y[..., None]
    sat = np.abs(chroma).max(-1)
    k = 1 + VIBRANCE * np.clip(1 - sat / 0.35, 0, 1) + 0.06 * turq
    f = Y[..., None] + chroma * k[..., None]

    # 5. bloom + halation from highlights
    hi = np.clip((Y - 0.84) / 0.14, 0, 1)[..., None] * np.clip(f, 0, 1)
    glow = blur(hi, 60, down=8)
    hal = blur(hi[..., 0], 10, down=2)
    f = 1 - (1 - f) * (1 - BLOOM * glow * np.array([1.0, 0.86, 0.66], np.float32))
    f[..., 0] += HALATION * hal

    # 6. luma sharpening
    Y = f @ LUMA
    d = Y - blur(Y, 1.4, down=1)
    d = np.sign(d) * np.maximum(np.abs(d) - 0.012, 0)          # edges only, flat sky noise untouched
    f = f + (SHARPEN * d)[..., None]

    # 7. lens: chromatic aberration grows toward the edges, vignette
    f = np.clip(f, 0, 1)
    out = Image.fromarray((f * 255 + 0.5).astype(np.uint8))
    rch, gch, bch = out.split()
    s = CA_PX / (w / 2)
    def scale(ch, k):
        nw, nh = round(w * k), round(h * k)
        im = ch.resize((nw, nh), Image.BICUBIC)
        l, t = (nw - w) // 2, (nh - h) // 2
        return im.crop((l, t, l + w, t + h))
    out = Image.merge("RGB", (scale(rch, 1 + s), scale(gch, 1 + s * 0.5), bch))   # all >= 1: no borders
    f = np.asarray(out, np.float32) / 255
    rr = ((nx - 0.5) / 0.62) ** 2 + ((ny - 0.5) / 0.78) ** 2
    f = f * (1 - VIGNETTE * np.clip(rr, 0, 1.6)[..., None] ** 1.5 / 1.6 ** 1.5 * 1.6)

    # 8. film grain (midtone weighted, slightly soft)
    rng = np.random.default_rng(1000 + frame_no)
    n = rng.standard_normal((h // 2, w // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n, "F").resize((w, h), Image.BILINEAR), np.float32)
    Y = f @ LUMA
    f = f + (GRAIN * n * (0.35 + 2.6 * Y * (1 - Y)))[..., None]
    return np.clip(f, 0, 1)


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), np.float32) / 255


def save(f, p):
    Image.fromarray((f * 255 + 0.5).astype(np.uint8)).save(p, quality=97, subsampling=0)


def job(args):
    src, dst, n = args
    if not os.path.exists(dst):
        save(grade(load(src), n), dst)
    return n


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        save(grade(load(sys.argv[2])), sys.argv[3])
        sys.exit()
    src, dst = sys.argv[1], sys.argv[2]
    a, b = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1, 480)
    os.makedirs(dst, exist_ok=True)
    jobs = [(f"{src}/f_{i:04d}.jpg", f"{dst}/f_{i:04d}.jpg", i) for i in range(a, b + 1)]
    with Pool(os.cpu_count()) as p:
        for i, n in enumerate(p.imap_unordered(job, jobs), 1):
            if i % 40 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
