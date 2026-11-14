"""Crop single assets out of the reference sheets for image-to-3D upload.
Sheet labels / neighbouring panels inside the crop are painted out with the local background
grey, then the crop is upscaled 4x (Lanczos + light unsharp) and padded to a square so the
image-to-3D tool sees one centred object on a plain background."""
import sys, os
from PIL import Image, ImageDraw, ImageFilter

def crop_up(src, box, out, patches=(), scale=4, pad=1.08):
    sheet = Image.open(src).convert('RGB')
    d = ImageDraw.Draw(sheet)
    for (l, t, r, b), sample_xy in patches:      # paint out labels with nearby background colour
        d.rectangle((l, t, r, b), fill=sheet.getpixel(sample_xy))
    im = sheet.crop(box)
    bg = im.getpixel((2, im.height // 2))
    im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2.0, percent=60, threshold=2))
    side = int(max(im.size) * pad)
    canvas = Image.new('RGB', (side, side), bg)
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    canvas.save(out)
    return canvas.size

STAGE1 = [  # (sheet, crop box (l,t,r,b), output, [(label rect, bg sample point)])
    ('arena_props.png', (16, 126, 152, 448), 'A01_stone_lantern_FRONT.png', []),
    ('arena_props.png', (161, 126, 299, 448), 'A01_stone_lantern_SIDE.png', []),
    ('arena_props.png', (694, 478, 1214, 900), 'A02_temple_FRONT.png',
        [((815, 468, 990, 490), (800, 478)), ((1185, 750, 1214, 900), (1200, 740))]),
    ('arena_props.png', (584, 90, 984, 446), 'A03_torii_FRONT.png', [((735, 78, 835, 100), (720, 88))]),
    ('arena_props.png', (998, 90, 1098, 446), 'A03_torii_SIDE.png', [((998, 78, 1098, 99), (1094, 110))]),
]

if __name__ == '__main__':
    refs, outdir = sys.argv[1], sys.argv[2]
    for sheet, box, name, patches in STAGE1:
        print(name, crop_up(os.path.join(refs, sheet), box, os.path.join(outdir, name), patches))
