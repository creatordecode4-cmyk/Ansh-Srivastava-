"""The teaser: about ten seconds of the film's strongest moments, cut hard, then a title card. It
shows the build-up and the blows but nothing of the ending (the hat falling, the mask cracking).

    python3 -I tools/teaser.py [--preset look] [--tag _v3] [--out previews/stage4_teaser_v3]

Writes <out>_vertical.mp4 (1080x1920, for phones: Reels, Shorts) and <out>_wide.mp4 (1920x1080).
Every film frame gets the film look (sd/post.py finish) and is cut to the wide picture (2.1:1)
inside the black bars, which also leaves out a preview frame's label. Of each impact frame pair
only one frame is used, held for two frames, and the three flashes are kept at least 0.7 s apart.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# ("shot", first, last[, "fadein"]) film frames at film speed; ("hold", frame, n); ("black", n);
# ("text", words, n) a line of words on black; ("title", n) the title card
EDIT = [
    ("black", 6),
    ("shot", 57, 72, "fadein"),     # the red moon over the torii
    ("shot", 109, 126),             # the Oni's mask
    ("shot", 164, 175),             # the Ronin comes down the steps, past the Oni
    ("shot", 129, 138),             # a hand on the katana
    ("shot", 204, 216),             # the hat comes up: the glint on the visor
    ("text", "ONE MOON.   TWO BLADES.", 20),
    ("shot", 243, 251),             # the Oni runs
    ("shot", 253, 261),             # the Ronin runs
    ("shot", 268, 274),             # the clash
    ("hold", 276, 2),               # its red impact frame
    ("shot", 277, 288),
    ("shot", 346, 349),             # the third cut
    ("hold", 350, 2),               # its ink impact frame
    ("shot", 451, 456),             # water
    ("shot", 529, 537),             # fire: the great cut
    ("shot", 597, 603),             # the crossing
    ("hold", 604, 2),
    ("hold", 605, 2),
    ("shot", 606, 620),             # the ring, and the blades part
    ("black", 6),
    ("title", 56),
    ("black", 6),
]

TITLE_JP, TITLE_EN, TAG = "鬼 対 浪人", "ONI  ×  RONIN", "COMING SOON"
FONTS = dict(jp="IPAGothic", en="Inter Display:style=SemiBold", light="Inter Display:style=Light")


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def frames_used():
    out = []
    for e in EDIT:
        if e[0] == "shot":
            out += range(e[1], e[2] + 1)
        elif e[0] == "hold":
            out.append(e[1])
    return sorted(set(out))


def font(key, size):
    from PIL import ImageFont
    path = subprocess.run(["fc-match", "-f", "%{file}", FONTS[key]], capture_output=True, text=True, check=True).stdout
    return ImageFont.truetype(path, size)


def smooth(i, a, b):
    u = min(1.0, max(0.0, (i - a) / max(1, b - a)))
    return u * u * (3.0 - 2.0 * u)


def tracked(d, cx, y, text, f, spacing, fill):
    """Text centred on cx with extra space between the letters."""
    widths = [d.textlength(ch, font=f) for ch in text]
    x = cx - (sum(widths) + spacing * (len(text) - 1)) / 2.0
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill)
        x += w + spacing


def grain(im, seed, amount=0.018):
    import numpy as np
    from PIL import Image
    x = np.asarray(im, dtype=np.float32) / 255.0
    g = np.random.default_rng(seed).normal(0.0, 1.0, x.shape[:2]).astype(np.float32)
    x = x + g[..., None] * amount
    return Image.fromarray((np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))


def text_card(i, n, W, H, words):
    from PIL import Image, ImageDraw
    unit = min(W, H)
    im = Image.new("RGB", (W, H), (0, 0, 0))
    k = smooth(i, 0, 4) * (1.0 - smooth(i, n - 5, n - 1))
    f = font("light", int(unit * 0.045))
    v = int(225 * k)
    tracked(ImageDraw.Draw(im), W / 2.0, H / 2.0 - f.size * 0.6, words, f, f.size * 0.30, (v, v, v))
    return grain(im, 900 + i)


def title_card(i, n, W, H):
    """鬼 対 浪人 grows in over a red glow, then ONI × RONIN, a red line drawn out, COMING SOON."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    unit = min(W, H)
    end = 1.0 - smooth(i, n - 10, n - 1)
    cy = H / 2.0 - unit * 0.06
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W / 2 - unit * 0.42, cy - unit * 0.13, W / 2 + unit * 0.42, cy + unit * 0.13), fill=255)
    glow = np.asarray(glow.filter(ImageFilter.GaussianBlur(unit * 0.09)), dtype=np.float32) / 255.0
    rgb = glow[..., None] * np.array([0.55, 0.03, 0.02]) * 0.55 * smooth(i, 0, 18) * end
    im = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    # the Japanese title on its own layer, scaled down from a little larger as it fades in
    fj = font("jp", int(unit * 0.17))
    box = fj.getbbox(TITLE_JP)
    layer = Image.new("L", (box[2] - box[0] + 40, box[3] - box[1] + 40), 0)
    ImageDraw.Draw(layer).text((20 - box[0], 20 - box[1]), TITLE_JP, font=fj, fill=255)
    s = 1.0 + 0.07 * (1.0 - smooth(i, 0, 26))
    layer = layer.resize((int(layer.width * s), int(layer.height * s)), resample=Image.LANCZOS)
    a = smooth(i, 0, 12) * end
    white = Image.new("RGB", layer.size, (244, 240, 236))
    im.paste(white, (int(W / 2 - layer.width / 2), int(cy - layer.height / 2)), layer.point(lambda v: int(v * a)))
    d = ImageDraw.Draw(im)
    fe = font("en", int(unit * 0.048))
    v = int(225 * smooth(i, 10, 22) * end)
    y_en = cy + unit * 0.125
    tracked(d, W / 2.0, y_en, TITLE_EN, fe, fe.size * 0.32, (v, v, v))
    w = unit * 0.30 * smooth(i, 16, 32)
    if w > 1:
        r = int(200 * end)
        y_l = y_en + fe.size * 1.75
        d.rectangle((W / 2 - w / 2, y_l, W / 2 + w / 2, y_l + max(2, unit // 400)), fill=(r, int(r * 0.08), int(r * 0.06)))
    fc = font("light", int(unit * 0.030))
    v = int(190 * smooth(i, 26, 38) * end)
    tracked(d, W / 2.0, y_en + fe.size * 2.35, TAG, fc, fc.size * 0.55, (v, v, v))
    return grain(im, 700 + i)


def main():
    import bpy  # noqa: F401  (mathutils for sd.film)
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    from sd import post
    src = os.path.join(HERE, "out", "stage4", arg("--preset", "look") + arg("--tag", "_v3"))
    out = os.path.join(HERE, arg("--out", "previews/stage4_teaser_v3"))
    need = frames_used()
    missing = [f for f in need if not os.path.exists(os.path.join(src, f"f_{f:04d}.png"))]
    if missing:
        sys.exit(f"missing film frames in {src}: {missing}")
    pictures = {}
    for f in need:                                                      # the film look, then the picture inside the bars
        im = post.finish(Image.open(os.path.join(src, f"f_{f:04d}.png")), f)
        W0, H0 = im.size
        bar = max(0, int(round((H0 - W0 / post.ASPECT) / 2.0)))
        pictures[f] = im.crop((0, bar, W0, H0 - bar))
    seq = []                                                            # (kind, payload, index in its element, length)
    for e in EDIT:
        if e[0] == "shot":
            n = e[2] - e[1] + 1
            seq += [("pic", (f, "fadein" in e[3:] and f - e[1] < 10, f - e[1]), k, n) for k, f in enumerate(range(e[1], e[2] + 1))]
        elif e[0] == "hold":
            seq += [("pic", (e[1], False, 0), k, e[2]) for k in range(e[2])]
        elif e[0] == "black":
            seq += [("black", None, k, e[1]) for k in range(e[1])]
        elif e[0] == "text":
            seq += [("text", e[1], k, e[2]) for k in range(e[2])]
        elif e[0] == "title":
            seq += [("title", None, k, e[1]) for k in range(e[1])]
    shot_span = (min(j for j, s in enumerate(seq) if s[0] == "pic"), max(j for j, s in enumerate(seq) if s[0] == "pic"))
    cap_en, cap_tag = font("en", 40), font("light", 30)
    for shape, (W, H) in (("vertical", (1080, 1920)), ("wide", (1920, 1080))):
        tmp = tempfile.mkdtemp(dir=os.path.dirname(out))
        pw = W
        ph = int(round(pw / post.ASPECT))
        top = (H - ph) // 2
        for j, (kind, p, k, n) in enumerate(seq):
            if kind == "pic":
                f, fade, idx = p
                pic = pictures[f].resize((pw, ph), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
                if fade:
                    pic = Image.fromarray((np.asarray(pic, dtype=np.float32) * smooth(idx, 0, 9) + 0.5).astype(np.uint8))
                frame = Image.new("RGB", (W, H), (0, 0, 0))
                frame.paste(pic, (0, top))
            elif kind == "text":
                frame = text_card(k, n, W, H, p)
            elif kind == "title":
                frame = title_card(k, n, W, H)
            else:
                frame = Image.new("RGB", (W, H), (0, 0, 0))
            if shape == "vertical" and shot_span[0] <= j <= shot_span[1] and kind != "text":
                ck = smooth(j - shot_span[0], 0, 9)                     # captions over the black above and below the picture,
                d = ImageDraw.Draw(frame)                               # faded in with the first shot
                tracked(d, W / 2.0, top - 150, TITLE_EN, cap_en, cap_en.size * 0.32, tuple(int(c * ck) for c in (215, 210, 205)))
                d.rectangle((W / 2 - 60, top - 78, W / 2 + 60, top - 76), fill=tuple(int(c * ck) for c in (170, 14, 10)))
                tracked(d, W / 2.0, top + ph + 90, TAG, cap_tag, cap_tag.size * 0.55, tuple(int(c * ck) for c in (165, 160, 155)))
            frame.save(os.path.join(tmp, f"t_{j:05d}.png"))
        path = f"{out}_{shape}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(tmp, "t_%05d.png"), "-vf", "format=yuv420p",
                        "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-movflags", "+faststart", path], check=True)
        shutil.rmtree(tmp)
        print(f"TEASER {path} {os.path.getsize(path) / 1e6:.1f} MB, {len(seq)} frames ({len(seq) / 24.0:.1f} s), {W}x{H}")


if __name__ == "__main__":
    if "--frames" in sys.argv:                                          # the film frames the teaser uses, comma separated
        print(",".join(str(f) for f in frames_used()))
    else:
        main()
