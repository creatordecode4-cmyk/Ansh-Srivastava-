"""Stage 1 preview sheets.

    python3 tools/stage1_sheet.py [tag]

Writes into previews/:
  stage1_breakdown.jpg   final render + clay render + top-down layout, laid out like the user's
                         ENVIRONMENT BREAKDOWN reference
  stage1_vs_reference.jpg  our passes next to the matching reference panels
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = sys.argv[1] if len(sys.argv) > 1 else "_final"
S1 = os.path.join(HERE, "out", "stage1")
PREV = os.path.join(HERE, "previews")


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def label(im, text, size=30):
    d = ImageDraw.Draw(im)
    f = font(size)
    w = d.textlength(text, font=f)
    d.rectangle((0, 0, w + 44, size + 26), fill=(14, 14, 16))
    d.rectangle((0, 0, 7, size + 26), fill=(190, 24, 24))
    d.text((24, 11), text, fill=(235, 232, 226), font=f)
    return im


def load(name, size):
    return Image.open(os.path.join(S1, f"{name}{TAG}.png")).convert("RGB").resize(size, Image.LANCZOS)


def breakdown():
    W, gap = 1920, 12
    beauty = label(load("beauty", (W, 1080)), "FINAL RENDER", 34)
    hw = (W - gap) // 2
    hh = round(hw * 9 / 16)
    clay = label(load("clay", (hw, hh)), "CLAY RENDER", 26)
    top = label(load("topdown", (hw, hh)), "TOP-DOWN LAYOUT", 26)
    sheet = Image.new("RGB", (W, 1080 + gap + hh), (8, 8, 9))
    sheet.paste(beauty, (0, 0))
    sheet.paste(clay, (0, 1080 + gap))
    sheet.paste(top, (hw + gap, 1080 + gap))
    out = os.path.join(PREV, "stage1_breakdown.jpg")
    sheet.save(out, quality=90)
    return out


def versus():
    ref_beauty = Image.open(os.path.join(HERE, "refs", "arena.png")).convert("RGB")
    bd = Image.open(os.path.join(HERE, "refs", "arena_breakdown.png")).convert("RGB")
    ref_clay = bd.crop((8, 545, 836, 932))
    ref_top = bd.crop((848, 545, 1668, 932))
    cw, gap = 960, 10
    rows = [("beauty", ref_beauty, "REFERENCE: arena.png", "OURS: final render"),
            ("clay", ref_clay, "REFERENCE: clay render", "OURS: clay render"),
            ("topdown", ref_top, "REFERENCE: top-down layout", "OURS: top-down layout")]
    tiles = []
    for name, ref, lr, lo in rows:
        ch = round(cw * 9 / 16)
        r = label(ref.resize((cw, ch), Image.LANCZOS), lr, 22)
        o = label(load(name, (cw, ch)), lo, 22)
        tiles.append((r, o, ch))
    H = sum(t[2] for t in tiles) + gap * (len(tiles) - 1)
    sheet = Image.new("RGB", (cw * 2 + gap, H), (8, 8, 9))
    y = 0
    for r, o, ch in tiles:
        sheet.paste(r, (0, y))
        sheet.paste(o, (cw + gap, y))
        y += ch + gap
    out = os.path.join(PREV, "stage1_vs_reference.jpg")
    sheet.save(out, quality=88)
    return out


if __name__ == "__main__":
    os.makedirs(PREV, exist_ok=True)
    print(breakdown())
    print(versus())
