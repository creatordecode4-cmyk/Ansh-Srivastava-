"""Render every arena prop on a neutral stage and lay them out like the PROPS BREAKDOWN reference.

    python3 tools/props_sheet.py            # renders into out/props/ and writes previews/stage1_props.jpg
    python3 tools/props_sheet.py --sheet    # only rebuild the sheet from existing renders
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "props")

# (builder, label, extra args for prop_test.py, cell width in sheet columns)
PROPS = [
    ("lantern", "STONE LANTERN", ["--size", "520", "720", "--az", "-22", "--el", "6"], 1),
    ("lantern_broken", "BROKEN STONE LANTERN", ["--size", "520", "720", "--az", "-22", "--el", "8"], 1),
    ("torii", "TORII GATE", ["--size", "1040", "720", "--az", "-14", "--el", "4", "--lens", "40"], 2),
    ("paper_lantern", "RED PAPER LANTERN", ["--size", "520", "720", "--az", "-20", "--el", "0", "--dist", "2.3"], 1),
    ("banner", "RED CLOTH BANNER", ["--size", "520", "720", "--az", "-12", "--el", "2"], 1),
    ("stairs", "TEMPLE STAIR SECTION", ["--size", "780", "620", "--az", "-28", "--el", "16"], 1.5),
    ("tiles", "FLOOR TILE SET", ["--size", "780", "620", "--az", "-18", "--el", "52", "--dist", "4.2"], 1.5),
    ("rocks", "BROKEN ROCK DEBRIS", ["--size", "780", "620", "--az", "-20", "--el", "28"], 1.5),
    ("temple", "TEMPLE HALL", ["--size", "1040", "620", "--az", "-30", "--el", "8", "--lens", "40"], 2),
    ("cherry", "CHERRY BLOSSOM TREE", ["--size", "780", "620", "--az", "-20", "--el", "5", "--seed", "3", "--h", "6.5", "--crown", "4.2"], 1.5),
]


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_all():
    for name, _, args, _ in PROPS:
        cmd = [sys.executable, os.path.join(HERE, "tools", "prop_test.py"), name, "--neutral", "--samples", "64"] + args
        print(" ".join(cmd[1:]), flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sheet():
    rows = [PROPS[:5], PROPS[5:]]
    H, pad, head = 520, 14, 46
    row_imgs = []
    for row in rows:
        cells = []
        for name, label, _, _ in row:
            im = Image.open(os.path.join(OUT, f"{name}.png")).convert("RGB")
            w = round(im.width * H / im.height)
            cell = Image.new("RGB", (w, H + head), (38, 40, 44))
            cell.paste(im.resize((w, H), Image.LANCZOS), (0, head))
            d = ImageDraw.Draw(cell)
            f = font(21)
            d.text(((w - d.textlength(label, font=f)) / 2, 11), label, fill=(232, 230, 224), font=f)
            cells.append(cell)
        W = sum(c.width for c in cells) + pad * (len(cells) - 1)
        strip = Image.new("RGB", (W, H + head), (24, 25, 28))
        x = 0
        for c in cells:
            strip.paste(c, (x, 0))
            x += c.width + pad
        row_imgs.append(strip)
    W = max(r.width for r in row_imgs)
    title_h = 64
    out = Image.new("RGB", (W + 2 * pad, title_h + sum(r.height for r in row_imgs) + pad * (len(row_imgs) + 1)), (24, 25, 28))
    d = ImageDraw.Draw(out)
    d.text((pad + 4, 16), "JAPANESE TEMPLE ARENA — PROPS BUILT IN BLENDER (each one a separate object)", fill=(232, 230, 224), font=font(27))
    y = title_h + pad
    for r in row_imgs:
        out.paste(r, (pad + (W - r.width) // 2, y))
        y += r.height + pad
    path = os.path.join(HERE, "previews", "stage1_props.jpg")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path, quality=88)
    print(path, out.size)


if __name__ == "__main__":
    if "--sheet" not in sys.argv:
        render_all()
    sheet()
