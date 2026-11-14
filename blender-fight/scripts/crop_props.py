"""Crop each prop out of arena_props.png, upscale 3x, and write a contact sheet."""
from PIL import Image
import os
src = Image.open('refs/arena_props.png').convert('RGB')
CROPS = {
    '01_stone_lantern':        (14, 128, 152, 446),
    '02_broken_stone_lantern': (306, 160, 448, 446),
    '03_torii_gate':           (582, 100, 984, 446),
    '04_paper_lantern':        (1118, 92, 1228, 396),
    '05_temple_building':      (694, 494, 1216, 902),
    '06_cherry_branch':        (1214, 498, 1670, 732),
    '07_banner_texture':       (1240, 92, 1386, 446),
    '08_stairs_reference':     (1368, 138, 1670, 446),
    '09_rocks_reference':      (380, 512, 696, 902),
    '10_floor_tiles_texture':  (14, 512, 362, 878),
}
os.makedirs('prop_images', exist_ok=True)
thumbs = []
for name, box in CROPS.items():
    im = src.crop(box)
    im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
    im.save(f'prop_images/{name}.png')
    thumbs.append((name, im))
H = 420
sheet_w = sum(int(t.width * H / t.height) + 10 for _, t in thumbs)
sheet = Image.new('RGB', (sheet_w, H), (30, 30, 34))
x = 0
for _, t in thumbs:
    w = int(t.width * H / t.height)
    sheet.paste(t.resize((w, H)), (x, 0)); x += w + 10
sheet.save('/tmp/claude-0/-home-user-Ansh-Srivastava-/ed2bd320-3ac5-5aaf-8e72-ae54271393e5/scratchpad/crops_sheet.png')
print('ok', sheet.size)
