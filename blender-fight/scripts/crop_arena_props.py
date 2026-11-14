"""Crop each prop out of refs/arena_props.png into crops/arena/ (4x upscaled) for image-to-3D."""
import os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOXES = {
    "01_stone_lantern": (15, 128, 152, 447),
    "02_broken_stone_lantern": (305, 128, 448, 447),
    "03_torii_gate": (583, 97, 985, 447),
    "04_red_paper_lantern": (1108, 92, 1238, 400),
    "05_red_banner": (1240, 92, 1381, 447),
    "06_temple_stairs": (1370, 100, 1668, 447),
    "07_floor_tiles": (8, 508, 362, 882),
    "08a_rock_block": (543, 515, 690, 624),
    "08b_rock_slab": (462, 719, 690, 816),
    "08c_rock_boulder": (382, 626, 497, 754),
    "09_temple_wall": (698, 493, 1207, 900),
    "10_cherry_branch": (1212, 500, 1668, 735),
}
src = Image.open(os.path.join(ROOT, "refs", "arena_props.png")).convert("RGB")
out = os.path.join(ROOT, "crops", "arena")
for name, box in BOXES.items():
    c = src.crop(box)
    c = c.resize((c.width * 4, c.height * 4), Image.LANCZOS)
    c.save(os.path.join(out, name + ".png"))
# contact sheet for checking
th = [Image.open(os.path.join(out, n + ".png")) for n in BOXES]
for t in th: t.thumbnail((320, 320))
sheet = Image.new("RGB", (5 * 330, 3 * 330), (40, 40, 40))
for i, t in enumerate(th): sheet.paste(t, ((i % 5) * 330 + 5, (i // 5) * 330 + 5))
sheet.save(os.path.join(ROOT, "previews", "arena_crops_contact.png"))
