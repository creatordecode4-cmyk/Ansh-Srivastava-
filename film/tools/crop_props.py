"""Crop single props out of arena_props.png, pad to a square on the sheet's grey, upscale for image-to-3D."""
import sys
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
BOXES = {  # name: (left, top, right, bottom) in source pixels
    "P1_stone_lantern": (14, 128, 156, 446),
    "P2_broken_stone_lantern": (306, 150, 452, 446),
    "P3_torii_gate": (584, 103, 982, 446),
    "P4_temple_building": (694, 494, 1200, 900),
    "P5_rock_debris": (380, 520, 700, 900),
    "P6_cherry_branch": (1214, 498, 1664, 734),
    "P7_paper_lantern": (1122, 96, 1222, 396),
    "P8_banner": (1238, 92, 1386, 446),
    "P9_stairs": (1368, 132, 1668, 446),
    "P10_floor_tiles": (10, 508, 364, 880),
}
img = Image.open(SRC).convert("RGB")
tiles = []
for name, box in BOXES.items():
    crop = img.crop(box)
    w, h = crop.size
    side = int(max(w, h) * 1.08)
    bg = crop.getpixel((2, 2))
    sq = Image.new("RGB", (side, side), bg)
    sq.paste(crop, ((side - w) // 2, (side - h) // 2))
    big = sq.resize((1536, 1536), Image.LANCZOS)
    big.save(f"{OUT}/{name}.png")
    tiles.append(sq.resize((384, 384), Image.LANCZOS))
sheet = Image.new("RGB", (384 * 5, 384 * 2), (40, 40, 40))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 5) * 384, (i // 5) * 384))
sheet.save(f"{OUT}/_contact_sheet.png")
print("ok", len(tiles))
