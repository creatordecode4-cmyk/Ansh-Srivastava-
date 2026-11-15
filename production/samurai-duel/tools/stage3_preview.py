"""Stage 3 preview: the rigged fighters in motion, seen from several sides at once.

    python3 -I tools/stage3_preview.py render <segment> [--size W H] [--samples N] [--frames a b] [--step K] [--proxy]
    python3 -I tools/stage3_preview.py list
    python3 -I tools/stage3_preview.py assemble [segments ...]

Every frame of a segment is rendered from two or three cameras that travel with the fighters and
pasted side by side, so a walk is seen from the side, the front and the back in one picture.
The floor carries a 0.5 m grid: a planted foot stays on its grid square while the body passes
over it. Nothing is blurred: no motion blur, no depth of field.

Frames go to out/stage3/preview/<segment>/, the film to previews/stage3_motion_test.mp4.
"""
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out", "stage3", "preview")
FILM = os.path.join(HERE, "previews", "stage3_motion_test.mp4")
ORDER = ["oni_walk", "ronin_walk", "duo_walk", "ronin_run", "ronin_kick", "ronin_spinkick", "oni_strike", "ronin_draw"]


def arg(flag, default, n=1, cast=float):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


# ----------------------------------------------------------------------------- segments
def _mocap(A, clip_name, lead, show, speed=1.0, widen=0.0, at=(0.0, 0.0), facing=0.0, hold=0, lock=True):
    """A take from a mocap clip: 'lead' cycles run before the part that is shown ('show' cycles)."""
    from sd import mocap, motion
    clip = mocap.Clip(clip_name)
    take = motion.Take.from_clip(A.pp, clip, seconds=clip.T * (lead + show) / speed, speed=speed, widen=widen)
    if lock:
        take.lock_feet(A.pp)
        take.fit_hips(A.pp)
    lead_f = int(round(clip.T * lead / speed * 24))
    take = take.placed(at, facing, frame=lead_f)
    if hold:
        take = take.held(hold)
    return take, lead_f


def seg_oni_walk(lib, new):
    A = new("oni")
    take, lead = _mocap(A, "walk", 1, 2, speed=0.85, widen=0.10)
    n = len(take)
    holds = [dict(sword="main", hand="Left", f0=0, f1=n, along=-0.10, roll=200, flip=True, lead=False, blend_in=0, elbow=(0.9, 0.5, -0.2))]
    return dict(cast=[(A, take, None, holds)], lead=lead, views=[("SIDE", 90, 4), ("FRONT", 18, 4), ("BACK", 205, 6)], height=2.62, look=1.04,
                title="ONI SAMURAI  -  walk  (motion capture + foot lock, hand on the scabbard)")


def seg_ronin_walk(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "walk", 1, 2, widen=0.02)
    return dict(cast=[(A, take, None, ())], lead=lead, views=[("SIDE", 90, 4), ("FRONT", 18, 4), ("BACK", 205, 6)], height=2.5, look=1.0,
                title="CYBER RONIN  -  walk  (cape, waist cloth and tails are simulated)")


def seg_duo_walk(lib, new):
    A, B = new("oni"), new("ronin")
    ta, lead = _mocap(A, "walk", 1, 2.4, speed=0.9, widen=0.10, at=(0.62, 0.0))
    tb, _ = _mocap(B, "walk", 1, 2.4, speed=0.9, widen=0.02, at=(-0.62, 0.0))
    holds = [dict(sword="main", hand="Left", f0=0, f1=len(ta), along=-0.10, roll=200, flip=True, lead=False, blend_in=0, elbow=(0.9, 0.5, -0.2))]
    return dict(cast=[(A, ta, None, holds), (B, tb, None, ())], lead=lead, views=[("FRONT", 12, 5), ("SIDE", 78, 5)], height=2.5, look=1.02, wide=1.9,
                title="SIDE BY SIDE  -  both fighters walking")


def seg_ronin_run(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "run", 2, 3)
    return dict(cast=[(A, take, None, ())], lead=lead, views=[("SIDE", 90, 4), ("FRONT", 25, 5)], height=2.45, look=1.0, wide=2.3,
                title="CYBER RONIN  -  dash  (cloth streaming behind)")


def seg_ronin_kick(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "kick", 0, 1, hold=10)
    return dict(cast=[(A, take, None, ())], lead=0, views=[("SIDE", 100, 4), ("FRONT", 30, 5)], height=2.6, look=1.05, wide=2.6,
                title="CYBER RONIN  -  kick")


def seg_ronin_spinkick(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "spinkick", 1, 1.6)
    return dict(cast=[(A, take, None, ())], lead=lead, views=[("SIDE", 100, 4), ("FRONT", 30, 5)], height=2.9, look=1.2, wide=2.6,
                title="CYBER RONIN  -  spinning kick")


SEGMENTS = {k[4:]: v for k, v in list(globals().items()) if k.startswith("seg_")}


# ----------------------------------------------------------------------------- rendering
def render(segment):
    import bpy
    import numpy as np
    from mathutils import Vector
    from PIL import Image, ImageDraw, ImageFont

    from sd import actor, core, mats, studio
    from sd import render as rnd

    W, H = [int(v) for v in arg("--size", (1280, 720), 2)]
    samples = int(arg("--samples", 32))
    step = int(arg("--step", 1))
    proxy = "--proxy" in sys.argv
    sc = core.reset_scene()
    lib = core.collection("PROPS_LIB", hide_render=True)
    made = []

    def new(who):
        A = actor.Actor(who, lib, core.collection(who.upper() + "_C"), cloth=not proxy)
        made.append(A)
        return A

    t0 = time.time()
    S = SEGMENTS[segment](lib, new)
    leads = S["lead"] if isinstance(S["lead"], tuple) else (S["lead"],) * len(S["cast"])
    for (A, take, swords, holds), lead in zip(S["cast"], leads):
        f0 = take.c[0]["hips"]
        A.place((f0.x, f0.y), 0.0)
        A.perform(take, swords=swords, holds=holds, start=61 - lead + max(leads))
        slide, short = take.slide_report(A.pp, A.poses) if take.locks else (0.0, 0.0)
        print(f"  {A.who}: planted-foot drift {slide * 1000:.2f} mm", flush=True)
    print(f"BUILD + PERFORM {time.time() - t0:.1f}s", flush=True)
    start = 61 + max(leads)                                      # first frame that is shown
    count = min(A.frames - lead for (A, *_), lead in zip(S["cast"], leads))
    t0 = time.time()
    if not proxy:
        actor.simulate(sc, made, os.path.join(HERE, "out", "cache", "stage3_" + segment), end=start + count)
        print(f"CLOTH {time.time() - t0:.1f}s", flush=True)
    else:
        for A in made:
            A.body.hide_render = A.body.hide_viewport = True
            A.proxy.hide_render = False
            core.set_mat(A.proxy, mats.clay())
    studio.world(sc, strength=0.3)
    studio.floor(sc, 0.0, grid=0.5)
    views = S["views"]
    gap, bar = 4, max(34, H // 17)                              # thin gaps between the pictures, a caption strip underneath
    pw = (W - gap * (len(views) - 1)) // len(views)
    ph = H - bar
    rnd.setup(sc, pw, ph, samples, 0.03)
    sc.cycles.adaptive_min_samples = min(samples, 12)
    sc.view_settings.exposure = -0.2
    sc.render.use_persistent_data = True
    lens = 85.0
    half_v, half_h = (18.0, 18.0 * pw / ph) if ph >= pw else (18.0 * ph / pw, 18.0)
    dist = max(S["height"] / 2 * lens / half_v, S.get("wide", 0.0) / 2 * lens / half_h)
    cam = studio.camera(sc, (0, 0, 1), 0, 4, dist, lens, name="CAM_Preview")
    keyl = studio.key(sc, (0, 0, 1), -35, 42, dist * 0.8, power=22.0 * dist * dist, size=S["height"] * 0.7, name="LGT_Key")
    rim = studio.key(sc, (0, 0, 1), 150, 30, dist * 0.8, power=9.0 * dist * dist, size=1.2, name="LGT_Rim")
    # the cameras travel with the fighters: the middle of their hips, smoothed so the picture does not sway with every step
    track = np.array([np.mean([[(A.controls[min(A.frames - 1, f + lead)]["hips"].x), (A.controls[min(A.frames - 1, f + lead)]["hips"].y)]
                               for (A, *_), lead in zip(S["cast"], leads)], axis=0) for f in range(count)])
    k = 13
    pad = np.pad(track, ((k // 2, k // 2), (0, 0)), mode="edge")
    track = np.stack([np.convolve(pad[:, i], np.ones(k) / k, mode="valid") for i in range(2)], axis=1)
    out = os.path.join(OUT + ("_proxy" if proxy else ""), segment)
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(12, H // 40))
    small = ImageFont.truetype("DejaVuSans.ttf", max(11, H // 44))
    a, b = [int(v) for v in arg("--frames", (0, count), 2)]
    t_all = time.time()
    for f in range(a, min(b, count), step):
        t1 = time.time()
        sc.frame_set(start + f)
        tgt = Vector((track[f][0], track[f][1], S["look"]))
        sheet = Image.new("RGB", (W, H), (16, 16, 18))
        for i, (label, az, el) in enumerate(views):
            studio.aim(cam, tgt, az, el, dist)
            for lamp, da, de in ((keyl, -35, 42), (rim, 150, 30)):
                aa, ee = math.radians(az + da), math.radians(de)
                lamp.location = tgt + Vector((math.sin(aa) * math.cos(ee), -math.cos(aa) * math.cos(ee), math.sin(ee))) * dist * 0.8
                core.look_at(lamp, tgt)
            tmp = os.path.join(out, f"_panel{i}.png")
            rnd.still(sc, tmp, cam)
            sheet.paste(Image.open(tmp).convert("RGB"), (i * (pw + gap), 0))
        d = ImageDraw.Draw(sheet)
        for i, (label, az, el) in enumerate(views):
            d.text((i * (pw + gap) + 14, 12), label, font=small, fill=(235, 235, 235))
        d.text((14, ph + (bar - font.size) // 2 - 2), S["title"], font=font, fill=(245, 245, 245))
        tag = f"{f + 1}/{count}"
        d.text((W - 14 - d.textlength(tag, font=small), ph + (bar - small.size) // 2 - 1), tag, font=small, fill=(170, 170, 170))
        sheet.save(os.path.join(out, f"f_{f:04d}.png"))
        print(f"   {segment} frame {f + 1}/{count}: {time.time() - t1:.1f}s", flush=True)
    for i in range(len(views)):
        p = os.path.join(out, f"_panel{i}.png")
        os.path.exists(p) and os.remove(p)
    print(f"RENDER {segment}: {time.time() - t_all:.1f}s -> {out}", flush=True)


def assemble(names):
    from PIL import Image
    names = [n for n in (names or ORDER) if os.path.isdir(os.path.join(OUT, n)) and any(f.startswith("f_") for f in os.listdir(os.path.join(OUT, n)))]
    parts = []
    for n in names:
        d = os.path.join(OUT, n)
        mp4 = os.path.join(d, "segment.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-pattern_type", "glob", "-i", os.path.join(d, "f_*.png"),
                        "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", "24", mp4], check=True)
        parts.append(mp4)
    lst = os.path.join(OUT, "segments.txt")
    with open(lst, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    os.makedirs(os.path.dirname(FILM), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", FILM], check=True)
    print("FILM", FILM, f"{os.path.getsize(FILM) / 1e6:.1f} MB", names)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print("segments:", ", ".join(SEGMENTS))
    elif cmd == "render":
        render(sys.argv[2])
    elif cmd == "assemble":
        assemble([a for a in sys.argv[2:] if not a.startswith("--")])
