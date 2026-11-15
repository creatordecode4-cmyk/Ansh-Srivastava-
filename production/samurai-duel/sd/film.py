"""The film: who does what, when and where (Stage 4).

Film frames run 1..720 at 24 fps. A fighter's take starts on film frame 1 (take frame 0), so
take frame = film frame - 1; in the Blender scene the film starts after LEAD frames in which the
cloth settles (scene frame = film frame + LEAD).

The arena's axes: +Y is north (the torii), +X east; the open floor is centred on the origin.
A facing is given in degrees as everywhere else: 0 looks toward -Y (south), 90 toward +X (east),
180 toward +Y (north); positive turns to the fighter's left.

Each fighter's part is one unbroken take: motion capture where there is a clip for it (walking,
running), poses keyed by hand for everything else (stopping, the draw, sword work), joined on a
frame where the captured feet are planted so that the keyed part can carry on from them.
"""
import math

from mathutils import Vector

from . import mocap, motion
from .puppet import Z, rot

LEAD = 60                                            # scene frames before take frame 0

# Film time against take time. A fighter's take runs on without a break; the film does not show all
# of it at the same rate: a cut may skip a stretch (the middle of a draw, which no arm can make as
# one move) and some beats are shown slowed down.
#        first film frame, last, take frame of the first, take frames per film frame
TIME = [(1, 224, 0.0, 1.0),          # intro up to the hands closing on the grips and the blades starting out
        (225, 240, 232.0, 1.0)]      # the wide standoff picks the draws up 8 frames later, blades already clear


def take_time(film_frame):
    """Take frame (may be fractional) shown on a film frame."""
    for a, b, t0, rate in TIME:
        if a <= film_frame <= b:
            return t0 + (film_frame - a) * rate
    a, b, t0, rate = TIME[-1]
    return t0 + (film_frame - a) * rate


def tf(film_frame):
    """Whole take frame of a film frame (for placing keys)."""
    return int(round(take_time(film_frame)))


def shown(first=1, last=None):
    """Whole take frames that the film shows between two film frames (both ends of every frame's
    blur included when a frame falls between two take frames)."""
    out = set()
    for ff in range(first, (last or TIME[-1][1]) + 1):
        t = take_time(ff)
        out.update((int(math.floor(t)), int(math.ceil(t))))
    return sorted(out)


def scene_time(film_frame):
    """Scene frame (may be fractional) of a film frame: takes start on scene frame LEAD + 1."""
    return LEAD + 1 + take_time(film_frame)


# ----------------------------------------------------------------------------- building blocks
def to_world(pp, pose, at, facing):
    """A pose written for a fighter who stands on the origin facing -Y, as plain controls for one who
    stands on 'at' = (x, y) facing 'facing' degrees."""
    return motion.moved(pp.canon(pose), rot(Z, facing), Vector((at[0], at[1], 0.0)))


def walk(pp, clip_name, frames, heading, speed=1.0, widen=0.0, front="Right"):
    """A walk of frames + 1 frames along 'heading' that ends on the frame where the 'front' foot
    has just come down flat ahead of the body while the other is still on its ball behind - the
    moment a walker can stop from. The last frame's hips are over the origin; move() it."""
    clip = mocap.Clip(clip_name)
    cycle = clip.T / speed * motion.FPS
    take = motion.Take.from_clip(pp, clip, seconds=clip.T * (math.ceil(frames / cycle) + 2) / speed, speed=speed, widen=widen)
    take.lock_feet(pp)
    take.fit_hips(pp)
    rear = "Left" if front == "Right" else "Right"
    ends = [i for i in range(frames, len(take)) if take.locks[front][i] == "flat" and take.locks[rear][i] == "ball"
            and take.locks[front][i - 1] != "flat"]
    if not ends:
        ends = [i for i in range(frames, len(take)) if take.locks[front][i] == "flat" and take.locks[rear][i] in ("ball", "flat")]
    e = ends[0]
    cut = motion.Take(take.c[e - frames:e + 1], clip_name)
    cut.locks = {k: v[e - frames:e + 1] for k, v in take.locks.items()}
    travel = cut.c[-1]["hips"] - cut.c[0]["hips"]
    yaw0 = math.degrees(math.atan2(travel.x, -travel.y))              # the way it actually travels, not the way the hips happen to point
    R = rot(Z, heading - yaw0)
    h = R @ cut.c[-1]["hips"]
    out = motion.Take([motion.moved(c, R, Vector((-h.x, -h.y, 0.0))) for c in cut.c], clip_name)
    out.locks = cut.locks
    return out


def shifted(take, by):
    """The same take moved over the ground by (dx, dy)."""
    out = motion.Take([motion.moved(c, rot(Z, 0.0), Vector((by[0], by[1], 0.0))) for c in take.c], take.name)
    out.locks = take.locks
    return out


def joined(a, b):
    """Take a followed by take b, whose first frame is a's last frame."""
    out = motion.Take(a.c + b.c[1:], a.name + "+" + b.name)
    out.locks = {k: list(a.locks.get(k, [None] * len(a))) + list(b.locks.get(k, [None] * len(b)))[1:] for k in ("Left", "Right")}
    return out


def foot_xy(c, tag):
    p = c["foot_" + tag[0]]["pos"]
    return Vector((p.x, p.y, 0.0))


# ----------------------------------------------------------------------------- the Oni
def oni_intro(A, mark=(-0.5, -1.9), heading=135.0, face=180.0):
    """Film frames 1-240. He walks in from the south-west, left hand on the scabbard, stops on his
    mark and turns to the torii. On the standoff his thumb pushes the guard and the blade shows
    (seen close); the film skips the draw itself - with his short arms and deep chest the right hand
    cannot cross to the left hip without passing through his belt - and finds him in the wide shot
    as the blade sweeps clear to the right and comes to guard with both hands.
    Returns (take, sword tracks, holds, scabbard steering)."""
    pp = A.pp
    sw = A.swords["main"]
    g = sw.spec["grip"]
    STOP = tf(150)                                                   # the walk's last frame
    WIDE = tf(225)                                                   # first take frame of the wide standoff
    FR, FL = dict(pos=(-0.16, -0.26, 0.0), yaw=0), dict(pos=(0.20, 0.24, 0.0), yaw=32)
    near_L = dict(rel=tuple(Vector((0.16, -0.50, 1.20)) - pp.H0["LeftArm"]))    # in front of the belt: the left hand's way from scabbard to grip
    ready = dict(hips=(0.0, -0.02, 1.03), hips_rot=(10, 3, 0), chest_rot=(8, 6, 0), head_rot=(0, 3, 0), foot_R=FR, foot_L=FL)
    breath = dict(ready, hips=(0.0, -0.02, 1.036), chest_rot=(8, 4.5, 0))
    coil = dict(ready, hips=(0.0, 0.0, 1.015), hips_rot=(6, 4, 0), chest_rot=(4, 9, 0), head_rot=(0, 5, 0))       # he sinks as the thumb pushes the guard
    drawn = dict(ready, hips=(0.0, -0.10, 1.00), hips_rot=(24, 5, 0), chest_rot=(24, 12, 0), head_rot=(2, 5, 0))  # left hip pulled back, right arm long
    cut = dict(ready, hips=(0.0, -0.11, 0.99), hips_rot=(14, 5, 0), chest_rot=(-8, 9, 0), head_rot=(0, 5, 0), hand_L=near_L)   # the blade has swept across to the right
    guard = dict(ready, hips=(0.0, -0.05, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0), hand_L=near_L)

    w = walk(pp, "walk", STOP, heading, speed=0.85, widen=0.12, front="Right")
    # he stands where the foot he stops on already is: the right foot only has to turn
    R = rot(Z, face)
    stand_at = foot_xy(w.c[-1], "Right") - R @ Vector(FR["pos"])
    w = shifted(w, (mark[0] - stand_at.x, mark[1] - stand_at.y))
    here = lambda pose: to_world(pp, pose, mark, face)
    k = lambda film, pose, ease="inout": (tf(film) - STOP, here(pose), ease)
    keys = [(0, w.c[-1], "inout"), k(166, ready, "slow_out"), k(192, breath), k(214, ready), k(222, coil), k(224, coil),
            (WIDE - 2 - STOP, here(drawn), "inout"), (WIDE + 4 - STOP, here(cut), "slow_out"), k(237, guard), k(240, guard)]
    steps = [("Left", 2, 13, dict(pos=tuple(here(ready)["foot_L"]["pos"]), yaw=face + FL["yaw"]), 0.05),      # the rear foot is drawn up into the stance
             ("Right", 11, 20, dict(yaw=face + FR["yaw"]), 0.0)]                                                # and he turns on the ball of the front foot
    tail = motion.Take.from_keys(pp, keys, steps, "oni_intro")
    take = joined(w, tail)
    take.fit_hips(pp)
    n = len(take)

    still = dict(hips=tuple(pp.H0["Hips"]))                          # sword places given 'as if he stood in the rest pose' travel with the chest
    k_out = A.sword_key(WIDE, still, (-0.24, -0.44, 1.42), (0.30, -0.95, 0.10), (-0.95, -0.30, 0.0), ease="linear")       # just clear of the scabbard, edge leading to the right
    k_cut = A.sword_key(WIDE + 4, still, (-0.40, -0.52, 1.40), (-0.86, -0.50, 0.06), (-0.50, 0.86, 0.0), ease="slow_out")
    k_guard = A.sword_key(tf(237), still, (-0.04, -0.60, 1.33), (0.02, -0.90, 0.42), (0, -0.42, -0.90))
    track = [dict(f=0, space="sheath", d=0.0), dict(f=tf(219), space="sheath", d=0.0), dict(f=tf(222), space="sheath", d=0.035, ease="snap"),
             dict(f=tf(224), space="sheath", d=0.035), dict(f=WIDE - 5, space="sheath", d=sw.spec["blade"], ease="slow_in"), k_out,
             k_cut, k_guard, dict(k_guard, f=n - 1)]
    holds = [dict(sword="main", on="saya", hand="Left", f0=0, f1=WIDE + 1, along=-0.10, roll=180, flip=True, lead=False, blend_in=0, blend_out=5,
                  elbow=(0.9, 0.5, -0.2)),
             dict(sword="main", hand="Right", f0=WIDE - 4, f1=n, along=0.058, roll=28, blend_in=4),
             dict(sword="main", hand="Left", f0=tf(239), f1=n, along=g - 0.062, roll=-28, lead=False, blend_in=5)]
    steer = dict(main=[(tf(214), 0.0, 0.0), (tf(222), -14.0, 0.0), (WIDE + 2, -14.0, 0.0), (tf(238), 0.0, 0.0)])
    return take, dict(main=track), holds, steer


# ----------------------------------------------------------------------------- the Ronin
PINCH = dict(curl=((30, 42, 26), (36, 46, 28), (58, 70, 46), (64, 76, 50)), spread=0.0, thumb=(42, 12, 14, 10))   # thumb and two fingers on a hat brim


def ronin_intro(A, mark=(0.25, 5.95), face=0.0):
    """Film frames 1-240. He comes out of the fog in front of the torii with his head bowed, stops,
    and lifts the brim of his hat with two fingers until the visor shows. The film skips his hands
    going back to the grips behind his shoulders (a full draw over the shoulder is longer than an
    arm) and finds him in the wide shot with both blades coming down and out to his sides.
    Returns (take, sword tracks, holds, scabbard steering)."""
    pp = A.pp
    STOP = tf(184)                                                   # the walk's last frame
    WIDE = tf(225)
    FR, FL = dict(pos=(-0.11, -0.07, 0.0), yaw=-6), dict(pos=(0.12, 0.06, 0.0), yaw=9)
    WR, WL = dict(pos=(-0.24, -0.20, 0.0), yaw=-12), dict(pos=(0.25, 0.20, 0.0), yaw=30)      # the wide stance he fights from
    up_R = dict(rel=tuple(Vector((-0.36, -0.34, 1.30)) - pp.H0["RightArm"]))     # the right hand on its way up to the brim, clear of the chest
    stand = dict(hips=(0.0, 0.0, 0.985), hips_rot=(0, 0, 0), chest_rot=(0, 3, 0), head_rot=(0, 21, 0), foot_R=FR, foot_L=FL)
    reach = dict(stand, hand_R=up_R)
    lifted = dict(stand, chest_rot=(0, 1, 0), head_rot=(0, -4, 0), hand_R=up_R)
    crouch = dict(stand, hips=(0.0, 0.0, 0.95), chest_rot=(0, 8, 0), head_rot=(0, 2, 0))       # as the hands go back to the grips
    high = dict(hips=(0.0, 0.02, 0.97), hips_rot=(0, 0, 0), chest_rot=(0, -3, 0), head_rot=(0, 2, 0))             # both blades out and up
    wings = dict(hips=(0.0, 0.0, 0.90), hips_rot=(6, 4, 0), chest_rot=(2, 10, 0), head_rot=(0, 2, 0))             # sunk into his stance, blades low and wide
    settle = dict(wings, hips=(0.0, 0.0, 0.915), chest_rot=(2, 8, 0))

    w = walk(pp, "walk", STOP, face, speed=1.0, widen=0.03, front="Right")
    for c in w.c:                                                    # he walks with his head down: the hat hides his face
        c["head_D"] = c["chest_D"] @ rot((1, 0, 0), 19.0)
    R = rot(Z, face)
    stand_at = foot_xy(w.c[-1], "Right") - R @ Vector(FR["pos"])
    w = shifted(w, (mark[0] - stand_at.x, mark[1] - stand_at.y))
    here = lambda pose: to_world(pp, pose, mark, face)
    k = lambda film, pose, ease="inout": (tf(film) - STOP, here(pose), ease)
    keys = [(0, w.c[-1], "inout"), k(196, stand, "slow_out"), k(202, reach), k(215, lifted), k(218, lifted), k(224, crouch),
            (WIDE - 2 - STOP, here(crouch), "inout"), (WIDE - STOP, here(high), "inout"), (WIDE + 7 - STOP, here(wings), "slow_in"), k(238, settle), k(240, settle)]
    steps = [("Left", 2, 12, dict(pos=tuple(here(stand)["foot_L"]["pos"]), yaw=face + FL["yaw"]), 0.05),
             ("Left", WIDE - 7 - STOP, WIDE - 1 - STOP, dict(pos=tuple(here(dict(stand, foot_L=WL))["foot_L"]["pos"]), yaw=face + WL["yaw"]), 0.05),
             ("Right", WIDE - STOP, WIDE + 6 - STOP, dict(pos=tuple(here(dict(stand, foot_R=WR))["foot_R"]["pos"]), yaw=face + WR["yaw"]), 0.04)]
    tail = motion.Take.from_keys(pp, keys, steps, "ronin_intro")
    take = joined(w, tail)
    take.fit_hips(pp)
    n = len(take)

    still = dict(hips=tuple(pp.H0["Hips"]))
    tracks, holds = {}, []
    for key, tag, sg in (("R", "Right", -1.0), ("L", "Left", 1.0)):
        sw = A.swords[key]
        k_high = A.sword_key(WIDE, still, (sg * 0.44, -0.04, 1.87), (sg * 0.50, 0.30, 0.81), (sg * 0.3, -0.9, 0.2), ease="linear")       # just drawn: blade up and out, behind the brim's line
        k_out = A.sword_key(WIDE + 4, still, (sg * 0.56, -0.16, 1.52), (sg * 0.88, 0.15, 0.30), (sg * 0.2, -0.6, -0.75), ease="linear")   # coming down outside the shoulder
        k_low = A.sword_key(WIDE + 7, still, (sg * 0.50, -0.14, 1.16), (sg * 0.82, 0.28, -0.50), (sg * 0.3, -0.5, -0.8), ease="slow_out")  # low and wide, points trailing
        k_set = A.sword_key(tf(238), still, (sg * 0.49, -0.14, 1.19), (sg * 0.84, 0.26, -0.47), (sg * 0.3, -0.5, -0.8))
        tracks[key] = [dict(f=0, space="sheath", d=0.0), dict(f=tf(224), space="sheath", d=0.0), dict(f=WIDE - 3, space="sheath", d=0.42, ease="slow_in"),
                       k_high, k_out, k_low, k_set, dict(k_set, f=n - 1)]
        holds.append(dict(sword=key, hand=tag, f0=WIDE - 4, f1=n, along=0.058, roll=0.0, blend_in=4))
    # the brim is taken at its front right corner, so that the hand does not cover the visor from the front
    holds.append(dict(hat=(-0.225, -0.165, -0.150), hand="Right", f0=tf(204), f1=tf(217), blend_in=8, blend_out=6, fingers=(0.16, 0.10, 1.0), back=(-0.95, -0.3, 0.1),
                      shape=PINCH, elbow=(-0.75, -0.25, -0.6)))
    return take, tracks, holds, None


# ----------------------------------------------------------------------------- cameras
def joint(A, bone, film_frame):
    """World position of one of a fighter's joints on a film frame."""
    f = min(A.frames - 1, max(0, int(round(take_time(film_frame)))))
    return A.arm.matrix_world @ A.pp.heads(A.poses[f])[bone]


def _mix(a, b, u):
    return Vector(a).lerp(Vector(b), u)


def _smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def _along(heading):
    """Unit vector on the ground for a facing in degrees."""
    a = math.radians(heading)
    return Vector((math.sin(a), -math.cos(a), 0.0))


def shots(cast):
    """The film's shots in order: dict(name, first, last film frame, cam(film frame) -> dict(pos, look, lens)).
    A camera is described per film frame, so one that follows a fighter is written from where he is."""
    oni, ronin = cast["oni"], cast["ronin"]
    out = []

    def add(name, first, last, cam, note=""):
        out.append(dict(name=name, first=first, last=last, cam=cam, note=note))

    # 0-3 s: the drone comes in low over the south wall toward the torii and the moon
    def drone(ff):                                                   # high inside the south wall, looking down on the floor; it sinks and tilts up to the torii and the moon
        u = (ff - 1) / 71.0
        v = 1.0 - (1.0 - u) ** 1.5                                   # arrives gently
        return dict(pos=_mix((1.0, -13.8, 13.5), (-0.7, -10.3, 7.3), v), look=_mix((0.0, 1.0, 0.0), (0.0, 9.3, 10.6), _smooth(u)), lens=22.0 + 3.0 * v)
    add("S01 drone push-in", 1, 72, drone)

    # 3-6 s: the Oni walks in from the left; low on the stones, he comes up to the camera
    def low(ff):
        u = (ff - 73) / 35.0
        return dict(pos=_mix((1.25, -2.35, 0.32), (1.05, -2.45, 0.34), u), look=_mix((-3.2, -3.3, 1.35), (-2.6, -3.0, 1.5), u), lens=27.0)
    add("S02a Oni walks in", 73, 108, low)

    def mask(ff):                                                    # close on the mask, travelling with him
        h = joint(oni, "Head", ff)
        d, r = _along(135.0), _along(135.0 - 90.0)                   # the way he walks, and his right
        return dict(pos=h + d * 1.55 + r * 0.95 + Vector((0, 0, -0.16)), look=h + Vector((0, 0, 0.10)), lens=85.0)
    add("S02b the mask", 109, 126, mask)

    def hand(ff):                                                    # close on the hand that holds the sword at his hip
        g = oni.arm.matrix_world @ (oni.saya_local["main"][min(oni.frames - 1, int(round(take_time(ff))))].translation)
        d, l = _along(135.0), _along(135.0 + 90.0)
        return dict(pos=g + d * 0.95 + l * 0.80 + Vector((0, 0, 0.10)), look=g + Vector((0, 0, 0.02)), lens=75.0)
    add("S02c hand on the katana", 127, 144, hand)

    # 6-10 s: over the Oni's shoulder, the Ronin comes out of the fog in front of the torii
    def fog(ff):
        u = (ff - 145) / 35.0
        return dict(pos=_mix((-0.05, -4.6, 1.52), (-0.02, -4.3, 1.50), u), look=(0.2, 7.0, 1.55), lens=70.0)
    add("S03a out of the fog", 145, 180, fog)

    def hat(ff):                                                     # low and close: the brim comes up, the moon behind him
        u = _smooth((ff - 181) / 35.0)
        return dict(pos=_mix((0.02, 4.20, 1.02), (0.02, 4.37, 1.05), u), look=_mix((0.25, 5.95, 1.60), (0.25, 5.95, 1.66), u), lens=50.0)
    add("S03b the hat", 181, 216, hat)

    def thumb(ff):                                                   # insert: the Oni's thumb pushes the guard
        g = oni.arm.matrix_world @ (oni.saya_local["main"][min(oni.frames - 1, int(round(take_time(ff))))].translation)
        return dict(pos=g + Vector((-0.55, 0.95, 0.28)), look=g + Vector((0.02, -0.02, 0.0)), lens=70.0)
    add("S03c the guard", 217, 224, thumb)

    def standoff(ff):                                                # wide, side on from the east: the two of them across the floor, the temple behind; blades come out
        u = _smooth((ff - 225) / 15.0)
        return dict(pos=_mix((7.5, 2.0, 0.50), (7.2, 2.0, 0.52), u), look=(-0.6, 2.05, 1.55), lens=24.0)
    add("S03d standoff", 225, 240, standoff)
    return out


def shot_at(shots_, film_frame):
    for sh in shots_:
        if sh["first"] <= film_frame <= sh["last"]:
            return sh
    return shots_[-1]


# when each fighter is in the film at all: before that he is not rendered (he waits where a camera could see him)
ENTERS = dict(oni=73, ronin=145)


def visor_glint(cast, film_frame, peak=209, width=2.6):
    """The glint on the Ronin's visor as the hat comes up: (where on the visor, how strong from 0 to 1),
    or None when there is none."""
    w = math.exp(-((film_frame - peak) / width) ** 2)
    if w < 0.03:
        return None
    A = cast["ronin"]
    f = min(A.frames - 1, max(0, int(round(take_time(film_frame)))))
    M = A.arm.matrix_world
    D = M.to_3x3() @ A.poses[f]["D"]["Head"]
    return M @ A.pp.heads(A.poses[f])["Head"] + D @ Vector((0.035, -0.118, 0.085)), w
