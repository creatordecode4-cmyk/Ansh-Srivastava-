"""Build breakdown.png (final | clay | wire) and rig_test.png (rest | pose) with labels, using Pillow."""
import os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
WORK = os.environ["DH_WORK"]; OUT = os.path.join(PROJ, "output"); R = os.path.join(WORK, "renders")


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sheet(paths, labels, out, h=900):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [i.resize((int(i.width * h / i.height), h), Image.LANCZOS) for i in ims]
    W = sum(i.width for i in ims) + 8 * (len(ims) - 1)
    m = Image.new("RGB", (W, h), (12, 12, 13)); x = 0
    d = ImageDraw.Draw(m); f = font(22)
    for im, lb in zip(ims, labels):
        m.paste(im, (x, 0))
        tw = d.textlength(lb, font=f)
        d.rounded_rectangle((x + 16, 16, x + 16 + tw + 24, 54), 8, fill=(30, 30, 36))
        d.text((x + 28, 22), lb, font=f, fill=(235, 235, 240))
        x += im.width + 8
    m.save(out); print("wrote", out)

sheet([os.path.join(OUT, "final_render.png"), os.path.join(R, "clay.png"), os.path.join(R, "wire.png")],
      ["FINAL RENDER", "CLAY RENDER", "WIREFRAME"], os.path.join(OUT, "breakdown.png"))
sheet([os.path.join(R, "rigtest_rest.png"), os.path.join(R, "rigtest_pose.png")],
      ["RIG TEST: REST (A-POSE)", "RIG TEST: FINAL POSE"], os.path.join(OUT, "rig_test.png"))
