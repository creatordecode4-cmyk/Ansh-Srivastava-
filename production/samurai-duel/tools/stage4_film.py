"""Stage 4: the film. Builds the arena with both fighters, runs the cloth, and renders film frames.

    python3 -I tools/stage4_film.py render FIRST LAST [--preset block|look|final] [--step K] [--no-cloth] [--reuse-cloth] [--cloth-to FILM_FRAME] [--tag NAME] [--fight]
                                           [--only F,F,...] [--skip-done]
    python3 -I tools/stage4_film.py assemble [--preset look] [--tag NAME] [--out previews/stage4_intro.mp4] [--from FILM_FRAME] [--to FILM_FRAME]

--fight builds both fighters' whole parts (sd/film.py fight(): the intro and the fight) with the
fight's effects and camera shake; without it only the intro is built, as it was rendered for the
intro preview. The two keep separate cloth caches (out/cache/stage4 and out/cache/stage4_fight).

Presets (4 CPU cores):
    block   640x360, 6 samples, light arena, no fog            about 10 s per frame: staging and timing
    look    960x540, 8 samples, fog and bloom                   about 35 s per frame: the preview that is shown
    final   1920x1080, 96 samples, motion blur, depth of field  not for this machine (see README)

Frames go to out/stage4/<preset><tag>/f_####.png (numbered by film frame). Every frame is rendered at
the scene time the film's time map gives it (sd/film.py), with the camera of the shot it belongs to.
"""
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PRESETS = dict(block=dict(size=(640, 360), samples=6, fog=False, detail=False, bloom=False, label=True),
               look=dict(size=(960, 540), samples=8, fog=True, detail=True, bloom=True, label=True),
               final=dict(size=(1920, 1080), samples=96, fog=True, detail=True, bloom=True, label=False))


def arg(flag, default, n=1, cast=str):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        vals = [cast(v) for v in sys.argv[i + 1:i + 1 + n]]
        return vals[0] if n == 1 else vals
    return default


def out_dir(preset, tag):
    return os.path.join(HERE, "out", "stage4", preset + tag)


def build(preset, cloth=True, last=240, fight=False):
    """Arena, both fighters performing, cloth run and cached. Returns (scene, cast, shots, cloth folder)."""
    import bpy
    from sd import actor, arena, core, film
    P = PRESETS[preset]
    t0 = time.time()
    sc, cams = arena.build(detail=P["detail"], particles=True, verbose=False)
    lib = bpy.data.collections["PROPS_LIB"]
    cast = {who: actor.Actor(who, lib, core.collection(who.upper() + "_C"), cloth=cloth) for who in ("oni", "ronin")}
    if fight:
        parts, notes = film.fight(cast)
    else:
        parts = dict(oni=film.oni_intro(cast["oni"]), ronin=film.ronin_intro(cast["ronin"]))
    for who, A in cast.items():
        take, swords, holds, steer = parts[who]
        h = take.c[0]["hips"]
        A.place((h.x, h.y), 0.0)
        A.perform(take, swords=swords, holds=holds, start=film.LEAD + 1, steer=steer, report=False)
        seen = A.clip_report(film.shown(max(1, film.ENTERS[who]), last))
        print(f"  {who}: {len(take)} take frames; on the frames the film shows: {dict((k, v) for k, v in seen.items() if v > 0.0) or 'nothing overlaps'}", flush=True)
    end = int(math.ceil(film.scene_time(last))) + 1
    print(f"BUILD {time.time() - t0:.1f}s", flush=True)
    t0 = time.time()
    folder = os.path.join(HERE, "out", "cache", "stage4_fight" if fight else "stage4")
    if cloth and "--reuse-cloth" in sys.argv and actor.replay(list(cast.values()), folder):
        cloth = False                                                # played back from the last run's files
        print("cloth played back from", folder, flush=True)
    if cloth:
        actor.simulate(sc, list(cast.values()), folder, end=end)
    else:
        hidden = {A.who: A.body.hide_viewport for A in cast.values()}
        for A in cast.values():
            A.body.hide_viewport = True
        for f in range(1, end + 1):                                  # the falling petals and snow still have to be run through
            sc.frame_set(f)
        for A in cast.values():
            A.body.hide_viewport = hidden[A.who]
    print(f"CLOTH {time.time() - t0:.1f}s (scene frames 1-{end})", flush=True)
    return sc, cast, film.shots(cast), folder


def render():
    import bpy
    from mathutils import Vector
    from PIL import Image, ImageDraw, ImageFont

    from sd import core, film
    from sd import render as rnd
    preset = arg("--preset", "look")
    P = PRESETS[preset]
    tag = arg("--tag", "")
    i = sys.argv.index("render")
    first, last = int(sys.argv[i + 1]), int(sys.argv[i + 2])
    step = arg("--step", 1, cast=int)
    only = [int(v) for v in arg("--only", "").split(",") if v]       # --only 115,116,214: just these film frames, in this order (FIRST LAST still bound the cloth)
    skip = "--skip-done" in sys.argv                                 # leave alone frames that are already on disk (several jobs can then share a range)
    fight = "--fight" in sys.argv
    sc, cast, shots, folder = build(preset, cloth="--no-cloth" not in sys.argv, last=max(last, arg("--cloth-to", last, cast=int)), fight=fight)
    W, H = P["size"]
    rnd.setup(sc, W, H, P["samples"], 0.03)
    sc.cycles.adaptive_min_samples = P["samples"]
    sc.cycles.use_adaptive_sampling = False
    sc.view_settings.exposure = 0.4
    sc.render.use_persistent_data = True
    bpy.data.objects["FOG_Volume"].hide_render = not P["fog"]
    if P["bloom"]:
        rnd.bloom(sc)
    cd = bpy.data.cameras.new("CAM_Film")
    cd.sensor_width, cd.clip_start, cd.clip_end = 36.0, 0.30, 3000.0   # nothing nearer than 30 cm is drawn: a snowflake that drifts past the lens would fill the frame
    cam = bpy.data.objects.new("CAM_Film", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    parts = {who: [A.body] + list(A.cloth) + [o for sw in A.swords.values() for o in (sw.ob, sw.saya)]
             + [t for sw in A.swords.values() for t, _ in list(sw.tassels) + list(sw.saya_tassels)] for who, A in cast.items()}
    for who, A in cast.items():                                     # everything else that belongs to him (hat, straps...) rides on the armature
        parts[who] += [o for o in bpy.data.objects if o.parent in (A.arm, A.body) and o not in parts[who]]
        parts[who] = [o for o in parts[who] if not o.hide_render]   # only what is rendered at all: the collision skin and the cloth cage stay hidden
    # the glint on the visor: a small four-pointed star of light that faces the camera for a few frames as the hat comes up
    verts, faces = [], []
    for w_, h_ in ((0.055, 0.0016), (0.0015, 0.022), (0.005, 0.005)):
        k = len(verts)
        verts += [(-w_, -h_, 0), (w_, -h_, 0), (w_, h_, 0), (-w_, h_, 0)]
        faces.append((k, k + 1, k + 2, k + 3))
    glint = core.mesh_obj("FX_VisorGlint", verts, faces, sc.collection)
    gm = bpy.data.materials.new("MAT_VisorGlint")
    gm.use_nodes = True
    gb = gm.node_tree.nodes["Principled BSDF"]
    gb.inputs["Base Color"].default_value = (0, 0, 0, 1)
    gb.inputs["Emission Color"].default_value = (0.72, 0.88, 1.0, 1)
    gb.inputs["Emission Strength"].default_value = float(arg("--glint", 130.0, cast=float))
    glint.data.materials.append(gm)
    glint.visible_shadow = False
    glint.hide_render = True
    fx = None
    if fight:
        from sd import fightfx
        fx = fightfx.FightFX(sc, cast, core.collection("FIGHT_FX"), folder if "--no-cloth" not in sys.argv else None)
    out = out_dir(preset, tag)
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(11, H // 34))
    t_all = time.time()
    for ff in (only or range(first, last + 1, step)):
        if skip and os.path.exists(os.path.join(out, f"f_{ff:04d}.png")):
            continue
        t1 = time.time()
        st = film.scene_time(ff)
        sc.frame_set(int(math.floor(st)), subframe=st - math.floor(st))
        for who, obs in parts.items():
            hide = ff < film.ENTERS[who]
            for o in obs:
                if o.hide_render != hide and o.name in bpy.data.objects:
                    o.hide_render = hide
        sh = film.shot_at(shots, ff)
        c = sh["cam"](ff)
        d_pos, d_look = film.shake(ff, c.get("hand", 0.0)) if fight else (Vector(), Vector())
        cam.location = Vector(c["pos"]) + d_pos
        core.look_at(cam, Vector(c["look"]) + d_look)
        cd.lens = c["lens"]
        if fx is not None:
            bpy.context.view_layer.update()
            fx.update(ff, cam)
        g = film.visor_glint(cast, ff) if sh["name"].startswith("S03b") else None
        glint.hide_render = g is None
        if g is not None:
            toward = (cam.location - g[0]).normalized()
            glint.location = g[0] + toward * 0.012
            glint.rotation_euler = cam.rotation_euler
            glint.scale = (g[1], g[1], g[1])
        path = os.path.join(out, f"f_{ff:04d}.png")
        rnd.still(sc, path, cam)
        dark = min(1.0, max(0.0, (ff - 708) / 12.0))                   # the last half second goes to black
        if dark > 0.0:
            im = Image.open(path).convert("RGB")
            im = Image.eval(im, lambda v, k=1.0 - dark: int(v * k))
            im.save(path)
        if P["label"]:
            im = Image.open(path).convert("RGB")
            d = ImageDraw.Draw(im)
            txt = f"{sh['name']}   {ff / 24.0:5.2f} s   frame {ff}"
            d.rectangle((0, H - font.size - 10, d.textlength(txt, font=font) + 16, H), fill=(0, 0, 0))
            d.text((8, H - font.size - 6), txt, font=font, fill=(235, 235, 235))
            im.save(path)
        print(f"   film frame {ff} ({sh['name']}): {time.time() - t1:.1f}s", flush=True)
    print(f"RENDER {first}-{last} step {step}: {time.time() - t_all:.1f}s -> {out}", flush=True)


def assemble():
    preset, tag = arg("--preset", "look"), arg("--tag", "")
    d = out_dir(preset, tag)
    lo, hi = arg("--from", 1, cast=int), arg("--to", 10 ** 6, cast=int)
    frames = sorted(f for f in os.listdir(d) if f.startswith("f_") and f.endswith(".png") and lo <= int(f[2:6]) <= hi)
    film_path = os.path.join(HERE, arg("--out", "previews/stage4_intro.mp4"))
    lst = os.path.join(d, "frames.txt")
    nums = [int(f[2:6]) for f in frames]
    with open(lst, "w") as fh:
        for k, f in enumerate(frames):                              # a frame that was not rendered (step > 1) is held
            hold = (nums[k + 1] - nums[k]) if k + 1 < len(nums) else 1
            fh.write(f"file '{os.path.join(d, f)}'\nduration {hold / 24.0:.6f}\n")
        fh.write(f"file '{os.path.join(d, frames[-1])}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf", "fps=24,format=yuv420p", "-c:v", "libx264",
                    "-crf", "17", "-preset", "slow", "-movflags", "+faststart", film_path], check=True)
    print(f"FILM {film_path} {os.path.getsize(film_path) / 1e6:.1f} MB from {len(frames)} frames ({nums[0]}-{nums[-1]})")


if __name__ == "__main__":
    if "render" in sys.argv:
        render()
    elif "assemble" in sys.argv:
        assemble()
    else:
        print(__doc__)
