"""Render frames of a built animation .blend to PNGs in one process.
python3 scripts/render_frames.py <blend> <out_dir> <start> <end> [step] [--res WxH] [--spp N]"""
import bpy, sys, os, time
blend, out, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
rest = sys.argv[5:]
step = int(rest[0]) if rest and rest[0].isdigit() else 1
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
if '--res' in sys.argv:
    w, h = map(int, sys.argv[sys.argv.index('--res') + 1].split('x'))
    sc.render.resolution_x, sc.render.resolution_y = w, h
if '--spp' in sys.argv:
    sc.cycles.samples = int(sys.argv[sys.argv.index('--spp') + 1])
os.makedirs(out, exist_ok=True)
t0 = time.time()
n = 0
frames = [int(x) for x in sys.argv[sys.argv.index('--list') + 1].split(',')] if '--list' in sys.argv else range(a, b + 1, step)
for f in frames:
    path = os.path.join(out, f'f{f:04d}.png')
    if os.path.exists(path):
        continue                               # resumable
    sc.frame_set(f)
    cams = [m for m in sc.timeline_markers if m.camera and m.frame <= f]
    if cams:                                   # shot cameras are bound to timeline markers
        sc.camera = max(cams, key=lambda m: m.frame).camera
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    n += 1
    if n % 20 == 0:
        print(f'FRAMES {n} done, frame {f}, {(time.time() - t0) / n:.2f}s/frame', flush=True)
print(f'FRAMES rendered {n} frames in {time.time() - t0:.0f}s ({(time.time() - t0) / max(1, n):.2f}s/frame)', flush=True)
