"""Render frames of the fight.
  python3 scripts/render_fight.py --tag preview --frames 1-720 --step 1 --res 480x270 --spp 8 [--fog] [--petals] [--mblur] [--sheet out.png --cols 6]
Frames go to render_tmp/<tag>/f####.png (existing frames are skipped, so a stopped render can be resumed).
"""
import bpy, os, sys, argparse, time, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ap = argparse.ArgumentParser()
ap.add_argument('--tag', default='preview'); ap.add_argument('--frames', default='1-720'); ap.add_argument('--step', type=int, default=1)
ap.add_argument('--list', default=''); ap.add_argument('--res', default='480x270'); ap.add_argument('--spp', type=int, default=8)
ap.add_argument('--fog', action='store_true'); ap.add_argument('--petals', action='store_true'); ap.add_argument('--mblur', action='store_true')
ap.add_argument('--sheet', default=''); ap.add_argument('--cols', type=int, default=6); ap.add_argument('--out', default='')
ap.add_argument('--force', action='store_true'); ap.add_argument('--fill', type=float, default=1.0)
a = ap.parse_args()
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, f'fight_scene_{a.tag}.blend'))
sc = bpy.context.scene
w, h = map(int, a.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
sc.cycles.samples = a.spp
sc.render.use_motion_blur = a.mblur
if not a.fog:
    bpy.data.objects['Fog_Volume'].hide_render = True
emit = bpy.data.objects['FX_Emitter']
if not a.petals:
    for m in emit.modifiers: m.show_render = False
if a.fill > 0:                      # soft overhead fill so the animation reads in previews
    L = bpy.data.lights.new('PV_Fill', 'AREA'); L.size, L.energy, L.color = 14, 5200 * a.fill, (0.75, 0.82, 1.0)
    lo = bpy.data.objects.new('PV_Fill', L); lo.location = (0, 0.5, 9); sc.collection.objects.link(lo)
    L2 = bpy.data.lights.new('PV_Front', 'SUN'); L2.energy, L2.color = 0.9 * a.fill, (0.8, 0.86, 1.0)
    l2 = bpy.data.objects.new('PV_Front', L2); l2.rotation_euler = (math.radians(62), 0, math.radians(15)); sc.collection.objects.link(l2)
if a.list:
    frames = [int(x) for x in a.list.split(',')]
else:
    f0, f1 = map(int, a.frames.split('-')); frames = list(range(f0, f1 + 1, a.step))
out = os.path.join(ROOT, a.out or f'render_tmp/{a.tag}')
os.makedirs(out, exist_ok=True)
if a.petals:
    for f in range(-800, frames[0]): sc.frame_set(f)
t0 = time.time(); done = 0
for f in frames:
    fp = os.path.join(out, f'f{f:04d}.png')
    if os.path.exists(fp) and not a.force:
        continue
    sc.frame_set(f)
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    done += 1
    if done % 20 == 0:
        print('PROGRESS frame %d, %.1fs/frame' % (f, (time.time() - t0) / done), flush=True)
print('RENDERED %d frames, %.1fs/frame' % (done, (time.time() - t0) / max(done, 1)))
if a.sheet:
    from PIL import Image, ImageDraw
    rows = math.ceil(len(frames) / a.cols)
    S = Image.new('RGB', (a.cols * w, rows * h))
    for i, f in enumerate(frames):
        im = Image.open(os.path.join(out, f'f{f:04d}.png')).convert('RGB')
        ImageDraw.Draw(im).text((4, 3), f'f{f}  {f / 24:.1f}s', fill=(255, 255, 0))
        S.paste(im, ((i % a.cols) * w, (i // a.cols) * h))
    S.save(os.path.join(ROOT, a.sheet))
