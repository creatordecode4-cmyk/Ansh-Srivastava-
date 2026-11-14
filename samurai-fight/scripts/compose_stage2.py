"""Build the Stage 2 review sheets (reference on top, my render below) into previews/."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B, R, O = os.path.join(ROOT, 'build', 'stage2'), os.path.join(ROOT, 'refs'), os.path.join(ROOT, 'previews')
FONT = ImageFont.load_default(size=30)


def label(im, text):
    d = ImageDraw.Draw(im)
    w = d.textlength(text, font=FONT)
    d.rectangle((0, 0, w + 28, 48), fill=(0, 0, 0))
    d.rectangle((0, 0, 6, 48), fill=(200, 30, 30))
    d.text((16, 7), text, font=FONT, fill=(255, 255, 255))
    return im


def to_width(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def vstack(parts, out, gap=8):
    w = max(p.width for p in parts)
    sheet = Image.new('RGB', (w, sum(p.height for p in parts) + gap * (len(parts) - 1)), (12, 12, 14))
    y = 0
    for p in parts:
        sheet.paste(p, (0, y))
        y += p.height + gap
    sheet.save(os.path.join(O, out), quality=90)
    print('wrote', out, sheet.size)


W = 1600
for name, ref in (('Oni', 'oni_sheet.jpg'), ('Ronin', 'ronin_sheet.jpg')):
    sheet = Image.open(os.path.join(R, ref)).convert('RGB')
    top = to_width(sheet.crop((0, 0, 1330, 640)), W)
    views = [Image.open(os.path.join(B, f'{name}_{k}.png')).convert('RGB') for k in ('front', 'side', 'back', 'q34')]
    row = Image.new('RGB', (sum(v.width for v in views), views[0].height))
    x = 0
    for v in views:
        row.paste(v, (x, 0))
        x += v.width
    vstack([label(top, f'YOUR SHEET  {name}'), label(to_width(row, W), 'MY BLENDER MODEL  (T-pose, 400k triangles, real scale)')], f'stage2_{name.lower()}_vs_sheet.jpg')

op = Image.open(os.path.join(R, 'oni_parts.jpg')).convert('RGB').crop((8, 668, 940, 822))
rp = Image.open(os.path.join(R, 'ronin_parts.jpg')).convert('RGB').crop((8, 705, 800, 905))
kat = Image.open(os.path.join(B, 'katanas.png')).convert('RGB')
vstack([label(to_width(op, W), 'YOUR PARTS SHEET  Oni katana'), label(to_width(rp, W), 'YOUR PARTS SHEET  Ronin katanas'),
        label(to_width(kat, W), 'MY KATANAS  (Oni on top, Ronin below)')], 'stage2_katanas.jpg')
label(Image.open(os.path.join(B, 'arena_check.png')).convert('RGB'), 'ARENA SCALE + LIGHT CHECK  (T-pose until Stage 3)').save(os.path.join(O, 'stage2_arena_check.jpg'), quality=90)
print('done')
