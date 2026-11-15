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
ORDER = ["oni_walk", "ronin_walk", "duo_walk", "ronin_run", "ronin_kick", "oni_strike", "ronin_blades"]


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
    take, lead = _mocap(A, "walk", 1, 2, speed=0.85, widen=0.12)
    n = len(take)
    holds = [dict(sword="main", hand="Left", f0=0, f1=n, along=-0.10, roll=180, flip=True, lead=False, blend_in=0, elbow=(0.9, 0.5, -0.2))]
    return dict(cast=[(A, take, None, holds)], lead=lead, views=[("SIDE", 90, 4), ("FRONT", 18, 4), ("BACK", 205, 6)], height=2.62, look=1.04,
                title="ONI SAMURAI  -  walk  (motion capture + foot lock, hand on the scabbard)")


def seg_ronin_walk(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "walk", 1, 2, widen=0.03)
    return dict(cast=[(A, take, None, ())], lead=lead, views=[("SIDE", 90, 4), ("FRONT", 18, 4), ("BACK", 205, 6)], height=2.5, look=1.0,
                title="CYBER RONIN  -  walk  (cape, waist cloth and tails are simulated)")


def seg_duo_walk(lib, new):
    A, B = new("oni"), new("ronin")
    ta, lead = _mocap(A, "walk", 1, 2.4, speed=0.9, widen=0.12, at=(0.62, 0.0))
    tb, _ = _mocap(B, "walk", 1, 2.4, speed=0.9, widen=0.03, at=(-0.62, 0.0))
    holds = [dict(sword="main", hand="Left", f0=0, f1=len(ta), along=-0.10, roll=180, flip=True, lead=False, blend_in=0, elbow=(0.9, 0.5, -0.2))]
    return dict(cast=[(A, ta, None, holds), (B, tb, None, ())], lead=lead, views=[("FRONT", 8, 5), ("BACK", 152, 7)], height=2.55, look=1.04, wide=2.5,
                title="SIDE BY SIDE  -  both fighters walking")


def seg_ronin_run(lib, new):
    A = new("ronin")
    take, lead = _mocap(A, "run", 2, 3, widen=0.012)
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


def seg_oni_strike(lib, new):
    """Hand-keyed: guard, sword raised overhead, step in and cut down, back to guard. Both hands on the grip."""
    from sd import motion
    A = new("oni")
    g = 0.285                                                    # length of his grip
    FR, FL = dict(pos=(-0.17, -0.40, 0.0), yaw=0), dict(pos=(0.20, 0.22, 0.0), yaw=35, pitch=10)
    guard = dict(hips=(0.0, -0.05, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0), foot_R=FR, foot_L=FL)
    high = dict(hips=(0.0, 0.0, 1.03), hips_rot=(10, -1, 0), chest_rot=(6, -7, 0), head_rot=(0, 4, 0))
    cut = dict(hips=(0.0, -0.40, 0.93), hips_rot=(4, 10, 0), chest_rot=(0, 23, 0), head_rot=(0, 9, 0))
    sunk = dict(cut, hips=(0.0, -0.43, 0.91), chest_rot=(0, 26, 0))
    rest = dict(cut, hips=(0.0, -0.43, 0.93))
    guard2 = dict(hips=(0.0, -0.49, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0))
    steps = [("Right", 29, 37, dict(pos=(-0.17, -0.84, 0.0)), 0.06),          # the lunge
             ("Left", 31, 38, dict(pitch=26), 0.0),                           # back foot rolls onto its ball as the body goes forward
             ("Left", 38, 45, dict(pos=(0.20, -0.04, 0.0), pitch=18), 0.025),  # and is drawn up behind the cut
             ("Left", 60, 72, dict(pos=(0.20, -0.22, 0.0), pitch=10), 0.04)]
    take = motion.Take.from_keys(A.pp, [(0, guard, "inout"), (10, guard, "inout"), (26, high, "inout"), (31, high, "inout"), (38, cut, "slow_in"),
                                        (45, sunk, "slow_out"), (58, rest, "inout"), (78, guard2, "inout"), (92, guard2, "inout")], steps, "strike")
    take.fit_hips(A.pp)
    still = dict(hips=tuple(A.pp.H0["Hips"]))                    # sword places given 'as if he stood in the rest pose' travel with the chest
    # his arms are short for his trunk: held at the navel the rear fist would be inside the belt knot, so the guard is at chest height
    k_guard = A.sword_key(0, guard, (-0.04, -0.60, 1.33), (0.02, -0.90, 0.42), (0, -0.42, -0.90))
    k_up = A.sword_key(19, still, (0.0, -0.58, 1.80), (0.0, -0.50, 0.87), (0, -0.87, -0.50))         # raised past the face at arm's length, not through the hair
    k_high = A.sword_key(26, still, (0.0, -0.27, 2.10), (0.0, 0.5, 0.87), (0, -0.87, 0.5))            # hands above and in front of the forehead, blade back over the head
    k_mid = A.sword_key(35, still, (0.0, -0.52, 1.95), (0.0, -0.42, 0.91), (0, -0.91, -0.42), ease="slow_in")   # coming down in front of the face
    k_cut = A.sword_key(38, cut, (-0.02, -1.02, 1.12), (0.0, -0.975, -0.22), (0, 0.22, -0.975), ease="slow_in")
    track = [k_guard, dict(k_guard, f=10), k_up, k_high, dict(k_high, f=31), k_mid,
             k_cut, dict(k_cut, f=45, ease="slow_out"), dict(k_cut, f=58), dict(k_guard, f=78), dict(k_guard, f=92)]
    n = len(take)
    holds = [dict(sword="main", hand="Right", f0=0, f1=n, along=0.058, roll=28, blend_in=0),
             dict(sword="main", hand="Left", f0=0, f1=n, along=g - 0.062, roll=-28, lead=False, blend_in=0)]
    return dict(cast=[(A, take, dict(main=track), holds)], lead=0, views=[("SIDE", 90, 3), ("FRONT", 28, 5)], height=3.0, look=1.40, wide=2.7,
                title="ONI SAMURAI  -  overhead cut  (keyed by hand, both hands on the grip)")


def seg_ronin_blades(lib, new):
    """Motion capture for the body, a katana in each hand.

    The captured performer throws his hands over his head; a swordsman under a wide hat cannot,
    and a blade carried wherever such a hand points goes through hat and cape. So the two swords
    are planned and the hands follow them: each wrist keeps the rhythm it was captured with, but
    is held to the space beside the body and below the brim, and the blade points out and back
    from there - clear of head, hat and the kicking legs, which pass in front."""
    from sd import film
    A = new("ronin")
    take, lead = _mocap(A, "spinkick", 1, 1.6)
    n = len(take)
    tracks = {key: [dict(f=f, space="chest", m=M) for f, M in enumerate(mats)] for key, mats in film.blades_beside(A, take).items()}
    holds = [dict(sword=k, hand=h, f0=0, f1=n, blend_in=0) for k, h in (("R", "Right"), ("L", "Left"))]
    return dict(cast=[(A, take, tracks, holds)], lead=lead, views=[("SIDE", 100, 4), ("FRONT", 30, 5)], height=3.0, look=1.2, wide=3.0,
                title="CYBER RONIN  -  spinning kick with both blades drawn")



def seg_s4_oni(lib, new):
    """Stage 4 check: the Oni's part of the intro (walk in, stop, turn, hand to the grip, draw, guard)."""
    from sd import film
    A = new("oni")
    take, swords, holds, steer = film.oni_intro(A)
    return dict(cast=[(A, take, swords, holds)], steer=steer, lead=film.tf(73), views=[("FROM THE EAST", 90, 4), ("FROM THE NORTH", 180, 5)], height=2.9, look=1.15, wide=2.6,
                title="STAGE 4 CHECK  -  Oni: walk in, stop, draw")


def seg_s4_ronin(lib, new):
    """Stage 4 check: the Ronin's part of the intro (out of the fog, stop, lift the hat, both blades out)."""
    from sd import film
    A = new("ronin")
    take, swords, holds, steer = film.ronin_intro(A)
    return dict(cast=[(A, take, swords, holds)], steer=steer, lead=film.tf(145), views=[("FROM THE SOUTH", 0, 4), ("FROM THE SOUTH-WEST", -55, 5)], height=2.9, look=1.2, wide=2.6,
                title="STAGE 4 CHECK  -  Ronin: out of the fog, hat, blades")


def seg_s4_fight(lib, new):
    """Stage 4 check: both fighters' parts from the standoff on, side on."""
    from sd import film
    A, B = new("oni"), new("ronin")
    parts, _ = film.fight(dict(oni=A, ronin=B))
    (ta, sa, ha, steer), (tb, sb, hb, _) = parts["oni"], parts["ronin"]
    lead = film.tf(236)
    return dict(cast=[(A, ta, sa, ha), (B, tb, sb, hb)], steer=steer, lead=lead, views=[("FROM THE EAST", 90, 3), ("FROM ABOVE", 90, 62)], height=3.2, look=1.2, wide=9.5,
                title="STAGE 4 CHECK  -  the fight, take frames from the standoff")


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
    samples = int(arg("--samples", 16))
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
        A.perform(take, swords=swords, holds=holds, start=61 - lead + max(leads), steer=S.get("steer"))
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


PLAYS = dict(oni_walk=2, ronin_walk=2, duo_walk=1, ronin_run=2, ronin_kick=1, ronin_spinkick=1, oni_strike=1, ronin_blades=1)   # times each is shown
SLOW = ("oni_strike", "ronin_blades")                     # these are shown once more at half speed


def assemble(names):
    """Encode the rendered segments into one film. Walk cycles are played twice; the fast moves are
    repeated at half speed (every frame shown twice, marked as slow motion)."""
    from PIL import Image, ImageDraw, ImageFont
    names = [n for n in (names or ORDER) if os.path.isdir(os.path.join(OUT, n)) and any(f.startswith("f_") for f in os.listdir(os.path.join(OUT, n)))]
    lst = os.path.join(OUT, "frames.txt")
    total = 0
    with open(lst, "w") as fh:
        for n in names:
            d = os.path.join(OUT, n)
            frames = sorted(f for f in os.listdir(d) if f.startswith("f_") and f.endswith(".png"))
            seq = [os.path.join(d, f) for f in frames] * PLAYS.get(n, 1)
            if n in SLOW:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
                for f in frames:
                    im = Image.open(os.path.join(d, f)).convert("RGB")
                    dr = ImageDraw.Draw(im)
                    tag = "SLOW MOTION  x0.5"
                    w = dr.textlength(tag, font=font)
                    dr.rectangle((im.width - w - 34, 10, im.width - 10, 44), fill=(150, 20, 20))
                    dr.text((im.width - w - 22, 15), tag, font=font, fill=(255, 255, 255))
                    slow = os.path.join(d, "slow_" + f)
                    im.save(slow)
                    seq += [slow, slow]
            for path in seq:
                fh.write(f"file '{path}'\nduration {1 / 24:.6f}\n")
            total += len(seq)
    film = arg("--out", FILM, 1, str)                        # --out writes somewhere else (a part of the film, for an early look)
    os.makedirs(os.path.dirname(film), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf", "fps=24", "-c:v", "libx264", "-crf", "16",
                    "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", film], check=True)
    print("FILM", film, f"{os.path.getsize(film) / 1e6:.1f} MB, {total} frames, {total / 24:.1f} s", names)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        print("segments:", ", ".join(SEGMENTS))
    elif cmd == "render":
        render(sys.argv[2])
    elif cmd == "assemble":
        skip = sys.argv.index("--out") + 1 if "--out" in sys.argv else -1
        assemble([a for i, a in enumerate(sys.argv[2:], 2) if not a.startswith("--") and i != skip])
