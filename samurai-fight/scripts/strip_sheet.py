"""Tile strip frames into one sheet. python3 -I scripts/strip_sheet.py <prefix> <out.jpg> [cols]"""
import sys, glob
from PIL import Image, ImageDraw, ImageFont
prefix, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
fs = sorted(glob.glob(prefix + '_*.png'))
ims = [Image.open(f) for f in fs]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
sh = Image.new('RGB', (w * cols, h * rows), (20, 20, 22))
F = ImageFont.load_default(size=18)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = w * (i % cols), h * (i // cols)
    sh.paste(im, (x, y))
    ImageDraw.Draw(sh).text((x + 6, y + 4), 'f' + f.rsplit('_', 1)[1][:-4], font=F, fill=(255, 230, 0))
sh.save(out, quality=88)
print(sh.size)
