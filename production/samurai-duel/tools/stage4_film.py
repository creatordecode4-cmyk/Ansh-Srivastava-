"""Stage 4: the film. Builds the arena with both fighters, runs the cloth, and renders film frames.

    python3 -I tools/stage4_film.py render FIRST LAST [--preset block|look|half|hd|final] [--step K] [--no-cloth] [--reuse-cloth] [--cloth-to FILM_FRAME] [--tag NAME] [--fight]
                                           [--only F,F,...] [--skip-done] [--cache NAME] [--no-trails] [--no-anime] [--no-persistent]
    python3 -I tools/stage4_film.py assemble [--preset look] [--tag NAME[,NAME...]] [--out previews/stage4_intro.mp4] [--from FILM_FRAME] [--to FILM_FRAME] [--finish]
                                             [--size WxH]

--fight builds both fighters' whole parts (sd/film.py fight(): the intro and the fight) with the
fight's effects and camera shake; without it only the intro is built, as it was rendered for the
intro preview. The two keep separate cloth caches (out/cache/stage4 and out/cache/stage4_fight).

Presets (4 CPU cores):
    block   640x360, 6 samples, light arena, no fog            about 10 s per frame: staging and timing
    look    960x540, 8 samples, fog and bloom                   about 35 s per frame: the preview that is shown (sharp: no blur)
    half    960x540, 24 samples, motion blur, depth of field    the finished picture at half size
    hd      1280x720, 16 samples, motion blur, depth of field   the finished picture at 720p
    final   1920x1080, 96 samples, motion blur, depth of field  not for this machine (see README)
--blur and --dof switch motion blur and depth of field on for any preset.

Motion blur follows the time map: the shutter is open for half a film frame, which is half a take
frame at full speed, an eighth in quarter-speed slow motion and nothing while a blow is held. The
camera is placed by a formula per film frame; so that it blurs as well, it is keyed for the frame
before, this frame and the frame after, at the scene times those have. A held frame or an impact
frame is frozen with a shutter of a thousandth of a take frame and the camera keyed in one place;
motion blur and depth of field are never switched off between frames (with persistent data the
camera's blur was lost for every later frame of the job once it had been switched off and on).

Frames go to out/stage4/<preset><tag>/f_####.png (numbered by film frame). Every frame is rendered at
the scene time the film's time map gives it (sd/film.py), with the camera of the shot it belongs to.

assemble --size WxH scales every frame to that size as the film is put together (Lanczos, then a
light sharpening), e.g. --size 1920x1080 for the 720p render (hd) shown at 1080p. With --finish the
scaling comes first, so the grain is laid at the full size; the finished frames then go to
finished_WxH, next to the unscaled ones.
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
               half=dict(size=(960, 540), samples=24, fog=True, detail=True, bloom=True, label=False, blur=True, dof=True),
               hd=dict(size=(1280, 720), samples=16, fog=True, detail=True, bloom=True, label=False, blur=True, dof=True),
               final=dict(size=(1920, 1080), samples=96, fog=True, detail=True, bloom=True, label=False, blur=True, dof=True))


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
    folder = os.path.join(HERE, "out", "cache", ("stage4_fight" if fight else "stage4") + arg("--cache", ""))   # --cache NAME: a cloth cache of its own
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
    from mathutils import Quaternion, Vector
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
    sc.render.use_persistent_data = "--no-persistent" not in sys.argv     # --no-persistent: every frame synced afresh (slower, nothing carried over)
    bpy.data.objects["FOG_Volume"].hide_render = not P["fog"]
    if P["bloom"]:
        rnd.bloom(sc)
    cd = bpy.data.cameras.new("CAM_Film")
    cd.sensor_width, cd.clip_start, cd.clip_end = 36.0, 0.30, 3000.0   # nothing nearer than 30 cm is drawn: a snowflake that drifts past the lens would fill the frame
    cam = bpy.data.objects.new("CAM_Film", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    blur = bool(P.get("blur")) or "--blur" in sys.argv
    dof = bool(P.get("dof")) or "--dof" in sys.argv
    curves = None
    if blur:                                                        # the camera's place over one film frame either side, as animation Cycles can sample
        sc.render.motion_blur_position = "CENTER"
        cam.rotation_mode = "XYZ"
        ad = cam.animation_data_create()
        act = bpy.data.actions.new("CAM_Film_blur")
        slot = act.slots.new(id_type="OBJECT", name="CAM_Film")
        bag = act.layers.new("Layer").strips.new(type="KEYFRAME").channelbag(slot, ensure=True)
        curves = [bag.fcurves.new("location", index=i) for i in range(3)] + [bag.fcurves.new("rotation_euler", index=i) for i in range(3)]
        for fc in curves:
            fc.keyframe_points.add(3)
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        ad.action, ad.action_slot = act, slot

    def orient(pos, look, roll=0.0, near=None):
        """Camera rotation looking from pos at look, turned 'roll' degrees about the line of sight (a
        tilted horizon), as Euler angles close to 'near' so that blur keys never wrap round."""
        q = (Vector(look) - Vector(pos)).to_track_quat("-Z", "Y")
        if roll:
            q = q @ Quaternion((0.0, 0.0, 1.0), math.radians(roll))
        return q.to_euler("XYZ", near) if near is not None else q.to_euler("XYZ")

    def place(sh, g):
        """Where the camera is and looks on film frame g of a shot (held to the shot's own frames)."""
        g = min(max(g, sh["first"]), sh["last"])
        c = sh["cam"](g)
        d_pos, d_look = film.shake(g, c.get("hand", 0.0)) if fight else (Vector(), Vector())
        return c, Vector(c["pos"]) + d_pos, Vector(c["look"]) + d_look
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
    fx = trails = None
    if fight:
        from sd import elemental, fightfx
        fx = fightfx.FightFX(sc, cast, core.collection("FIGHT_FX"), folder if "--no-cloth" not in sys.argv else None)
        if "--no-trails" not in sys.argv:                           # the swords' elemental trails: fire for the Oni, water for the Ronin
            span = (film.DASH, film.J0)
            big_o = [(h - 8, h + 1, 1.5) for h in film.HAMMER] + [(film.F0 + 8, film.SLASH + 6, 2.0), (film.CROSS - 6, film.CROSS + 4, 1.7)]
            big_r = [(film.HIT - 6, film.HIT + 2, 1.4), (film.SPIN - 2, film.KICK, 1.8), (film.CROSS - 6, film.CROSS + 4, 1.7)]
            trails = elemental.Trails(core.collection("FIGHT_FX"), [(cast["oni"], "main", "fire", span, big_o), (cast["ronin"], "R", "water", span, big_r),
                                                                    (cast["ronin"], "L", "water", span, big_r)])
    anime = fight and "--no-anime" not in sys.argv                  # impact frames and speed lines (sd/post.py)
    out = out_dir(preset, tag)
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(11, H // 34))
    ev0 = sc.view_settings.exposure                                 # a shot's camera may open up from this ('ev', in stops)
    if anime:
        from sd import post
    t_all = time.time()
    for ff in (only or range(first, last + 1, step)):
        if skip and os.path.exists(os.path.join(out, f"f_{ff:04d}.png")):
            continue
        t1 = time.time()
        kind = post.impact(ff) if anime else 0                      # an impact frame is a freeze: sharp shapes, no motion blur or depth of field
        st = film.scene_time(ff)
        sc.frame_set(int(math.floor(st)), subframe=st - math.floor(st))
        for who, obs in parts.items():
            hide = ff < film.ENTERS[who]
            for o in obs:
                if o.hide_render != hide and o.name in bpy.data.objects:
                    o.hide_render = hide
        sh = film.shot_at(shots, ff)
        c, pos, look = place(sh, ff)
        sc.view_settings.exposure = ev0 + c.get("ev", 0.0)
        e0 = orient(pos, look, c.get("roll", 0.0))
        rate = film.rate_at(ff)
        if curves is not None:
            # A hold or an impact frame is frozen by a shutter of almost nothing and a camera that stays
            # put, not by switching motion blur off: with persistent data, motion blur switched off for one
            # frame and on again stays broken (the camera's blur is lost) for the rest of the job.
            freeze = rate <= 0.0 or bool(kind)
            sc.render.use_motion_blur = True
            sc.render.motion_blur_shutter = 1e-3 if freeze else 0.5 * rate
            keys = []
            for k in (-1, 0, 1):
                c_k, p_k, l_k = place(sh, ff + (0 if freeze else k))
                keys.append((st + k * max(rate, 1e-3), tuple(p_k), tuple(orient(p_k, l_k, c_k.get("roll", 0.0), e0))))
            for i, fc in enumerate(curves):
                for kp, (t, loc, eul) in zip(fc.keyframe_points, keys):
                    kp.co = (t, (loc + eul)[i])
                    kp.handle_left = kp.handle_right = kp.co
                fc.update()
        cam.location = pos
        cam.rotation_euler = e0
        cd.lens = c["lens"]
        cd.dof.use_dof = dof                                        # never switched off for one frame either (see above)
        if dof:                                                     # focus on what the shot looks at; long lenses are opened up
            cd.dof.focus_distance = (Vector(c.get("focus", look)) - pos).length
            cd.dof.aperture_fstop = 1000.0 if kind else c.get("fstop", 2.0 if c["lens"] >= 70 else 2.8 if c["lens"] >= 45 else 4.0)
        if fx is not None:
            bpy.context.view_layer.update()
            fx.update(ff, cam)
        if trails is not None:
            trails.update(film.take_time(ff))
        g = film.visor_glint(cast, ff) if sh["name"].startswith("S03b") else None
        glint.hide_render = g is None
        if g is not None:
            toward = (cam.location - g[0]).normalized()
            glint.location = g[0] + toward * 0.012
            glint.rotation_euler = cam.rotation_euler
            glint.scale = (g[1], g[1], g[1])
        path = os.path.join(out, f"f_{ff:04d}.png")
        rnd.still(sc, path, cam)
        if anime:
            from bpy_extras.object_utils import world_to_camera_view
            who, k = post.lines(ff)
            if k > 0.0 or kind:                                     # a matte of the fighters keeps the lines off them and draws them in ink
                mpath = os.path.join(out, "mattes", f"m_{ff:04d}.png")
                rnd.mask(sc, mpath, [o for obs in parts.values() for o in obs])
                matte = Image.open(mpath).convert("L")
                im = Image.open(path).convert("RGB")
                if k > 0.0:
                    p = world_to_camera_view(sc, cam, film.joint(cast[who], "Spine2", ff))
                    im = post.speed_lines(im, (p.x * W, (1.0 - p.y) * H), k, seed=ff, matte=matte)
                if kind:
                    im = post.impact_frame(im, kind, matte=matte)
                im.save(path)
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
    """--tag may name several folders, comma separated (e.g. ',_prev' joins out/stage4/look and look_prev):
    each film frame is taken from the first folder that has it."""
    preset, tags = arg("--preset", "look"), arg("--tag", "").split(",")
    lo, hi = arg("--from", 1, cast=int), arg("--to", 10 ** 6, cast=int)
    found = {}
    for tag in tags:
        d = out_dir(preset, tag)
        for f in os.listdir(d):
            if f.startswith("f_") and f.endswith(".png") and lo <= int(f[2:6]) <= hi:
                found.setdefault(int(f[2:6]), os.path.join(d, f))
    nums = sorted(found)
    film_path = os.path.join(HERE, arg("--out", "previews/stage4_intro.mp4"))
    lst = os.path.join(out_dir(preset, tags[0]), "frames.txt")
    size = arg("--size", "")
    size = tuple(int(v) for v in size.lower().split("x")) if size else None
    if "--finish" in sys.argv:                                      # the film look (sd/post.py finish): grade, grain, vignette, wide-screen bars
        import bpy  # noqa: F401  (mathutils for sd.film)
        from PIL import Image, ImageFilter
        from sd import post
        fin = os.path.join(out_dir(preset, tags[0]), "finished" + (f"_{size[0]}x{size[1]}" if size else ""))
        os.makedirs(fin, exist_ok=True)
        for n in nums:
            p = os.path.join(fin, f"f_{n:04d}.png")
            im = Image.open(found[n]).convert("RGB")
            if size and im.size != size:
                im = im.resize(size, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
            post.finish(im, n, keep_label=PRESETS[preset]["label"]).save(p)
            found[n] = p
        size = None                                                 # the finished frames have it already
    with open(lst, "w") as fh:
        for k, n in enumerate(nums):                                # a frame that was not rendered (step > 1) is held
            hold = (nums[k + 1] - n) if k + 1 < len(nums) else 1
            fh.write(f"file '{found[n]}'\nduration {hold / 24.0:.6f}\n")
        fh.write(f"file '{found[nums[-1]]}'\n")
    vf = "fps=24" + (f",scale={size[0]}:{size[1]}:flags=lanczos,unsharp=5:5:0.35" if size else "") + ",format=yuv420p"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf", vf,
                    "-frames:v", str(nums[-1] - nums[0] + 1), "-c:v", "libx264",                # the list's closing entry would add a frame
                    "-crf", "17", "-preset", "slow", "-movflags", "+faststart", film_path], check=True)
    print(f"FILM {film_path} {os.path.getsize(film_path) / 1e6:.1f} MB from {len(nums)} frames ({nums[0]}-{nums[-1]})")


if __name__ == "__main__":
    if "render" in sys.argv:
        render()
    elif "assemble" in sys.argv:
        assemble()
    else:
        print(__doc__)
