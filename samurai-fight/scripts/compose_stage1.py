"""Build the Stage 1 review sheets (my render next to the reference) into previews/."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B, R, O = os.path.join(ROOT, 'build', 'stage1'), os.path.join(ROOT, 'refs'), os.path.join(ROOT, 'previews')
os.makedirs(O, exist_ok=True)
FONT = ImageFont.load_default(size=30)


def label(im, text):
    d = ImageDraw.Draw(im)
    w = d.textlength(text, font=FONT)
    d.rectangle((0, 0, w + 28, 48), fill=(0, 0, 0))
    d.rectangle((0, 0, 6, 48), fill=(200, 30, 30))
    d.text((16, 7), text, font=FONT, fill=(255, 255, 255))
    return im


def fit(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def stack(parts, out, vertical=True, gap=8):
    w = max(p.width for p in parts) if vertical else sum(p.width for p in parts) + gap * (len(parts) - 1)
    h = sum(p.height for p in parts) + gap * (len(parts) - 1) if vertical else max(p.height for p in parts)
    sheet = Image.new('RGB', (w, h), (12, 12, 14))
    x = y = 0
    for p in parts:
        sheet.paste(p, (x, y))
        if vertical:
            y += p.height + gap
        else:
            x += p.width + gap
    sheet.save(os.path.join(O, out), quality=90)
    print('wrote', out, sheet.size)


def load(name):
    return Image.open(os.path.join(B, name)).convert('RGB')


ref_arena = Image.open(os.path.join(R, 'arena.jpg')).convert('RGB')
ref_bd = Image.open(os.path.join(R, 'arena_breakdown.jpg')).convert('RGB')
ref_top = ref_bd.crop((848, 545, 1492, 932))
ref_clay = ref_bd.crop((8, 545, 836, 932))

stack([label(fit(ref_arena, 1280, 720), 'YOUR REFERENCE  arena.png'), label(load('hero_beauty.png'), 'MY BLENDER RENDER  Stage 1')], 'stage1_hero_vs_reference.jpg')
top = load('top_clay.png')
stack([label(fit(ref_top, top.width, top.height), 'YOUR TOP-DOWN LAYOUT'), label(top, 'MY TOP-DOWN (clay)  35 px = 1 m')], 'stage1_layout_vs_reference.jpg')
clay = load('hero_clay.png')
stack([label(fit(ref_clay, 1280, 720), 'YOUR CLAY RENDER'), label(clay, 'MY CLAY RENDER')], 'stage1_clay_vs_reference.jpg')
label(load('fight_beauty.png'), 'FIGHT-LEVEL CAMERA').save(os.path.join(O, 'stage1_fight_camera.jpg'), quality=90)
label(load('drone_beauty.png'), 'DRONE START (0-3 s)').save(os.path.join(O, 'stage1_drone_start.jpg'), quality=90)
print('done')
