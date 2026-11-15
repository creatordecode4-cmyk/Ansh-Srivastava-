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
def _timeline(stretches):
    """TIME rows from [(film frames, take frames per film frame, take frame to jump to or None to carry on)]."""
    out, ff, t = [], 1, 0.0
    for count, rate, jump in stretches:
        t = t if jump is None else float(jump)
        out.append((ff, ff + count - 1, t, rate))
        t += count * rate
        ff += count
    return out


HITSTOP = 3                                          # film frames a big clash is held for

# Take frames on which the fight turns (the beats are written from these, and so is the time map)
DASH, HIT = 248, 273                                 # both start to run; the blades meet
B0, HAMMER = 277, (293, 313, 334)                    # the Oni's three cuts land
C0, SPIN, KICK = 342, 354, 378                       # the Ronin slips out; his spin starts; his heel lands
D0, TRADE = 412, (423, 441, 459)                     # the exchange: three meetings of blades
F0, CHARGE, SLASH = 478, 492, 514                    # the Oni winds up; he comes in; his blade passes the Ronin
G0, RUSH, CROSS = 544, 556, 566                      # they set themselves; both run; the blades meet as they pass
J0, END = 595, 667                                   # both stand frozen, back to back; the last frame of the film
SPLIT, CRACK = J0 + 9, J0 + 44                       # the Ronin's hat parts; the crack runs across the Oni's mask

TIME = _timeline([
    (224, 1.0, 0),            # intro up to the hands closing on the grips and the blades starting out
    (16, 1.0, 232),           # the wide standoff picks the draws up 8 frames later, blades already clear
    (22, 1.0, DASH),          # 10 s: both dash
    (26, 0.25, HIT - 3),      # the last strides and the clash at a quarter speed
    (16, 1.0, B0),            # 12 s: the Oni's three cuts; each is held for a moment where it lands
    (HITSTOP, 0.0, HAMMER[0]), (19, 1.0, HAMMER[0] + 1),
    (HITSTOP, 0.0, HAMMER[1]), (20, 1.0, HAMMER[1] + 1),
    (HITSTOP, 0.0, HAMMER[2]), (8, 1.0, HAMMER[2] + 1),
    (35, 1.0, C0 + 1),        # 15 s: the Ronin's counter
    (HITSTOP, 0.0, KICK), (34, 1.0, KICK + 1),
    (10, 1.0, D0 + 1),        # 18 s: the exchange
    (HITSTOP, 0.0, TRADE[0]), (17, 1.0, TRADE[0] + 1),
    (HITSTOP, 0.0, TRADE[1]), (17, 1.0, TRADE[1] + 1),
    (HITSTOP, 0.0, TRADE[2]), (19, 1.0, TRADE[2] + 1),
    (33, 1.0, F0 + 1),        # 21 s: the Oni's great cut...
    (12, 0.5, SLASH - 2),     # ...seen at half speed as it passes
    (27, 1.0, SLASH + 4),
    (19, 1.0, G0 + 1),        # 24 s: they set themselves and run
    (28, 0.25, CROSS - 2),    # the crossing at a quarter speed
    (25, 1.0, CROSS + 5),     # they run out the cut and stop, back to back
    (72, 1.0, J0 + 1),        # 27 s: the hat, the mask, black
])
assert TIME[-1][1] == 720 and abs(TIME[-1][2] + 71 - END) < 1e-6


def take_time(film_frame):
    """Take frame (may be fractional) shown on a film frame."""
    for a, b, t0, rate in TIME:
        if a <= film_frame <= b:
            return t0 + (film_frame - a) * rate
    a, b, t0, rate = TIME[-1]
    return t0 + (film_frame - a) * rate


def rate_at(film_frame):
    """Take frames per film frame on a film frame: 1 at full speed, less in slow motion, 0 while a blow is held."""
    for a, b, t0, rate in TIME:
        if a <= film_frame <= b:
            return rate
    return TIME[-1][3]


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


def run_to(pp, frames, heading, speed=1.0, widen=0.012, front="Right"):
    """A run of frames + 1 frames along 'heading' that ends on the frame where the 'front' foot
    strikes the ground ahead of the body - the stride a runner can strike or stop from.
    The last frame's hips are over the origin; move it with shifted()."""
    clip = mocap.Clip("run")
    cycle = clip.T / speed * motion.FPS
    take = motion.Take.from_clip(pp, clip, seconds=clip.T * (math.ceil(frames / cycle) + 2) / speed, speed=speed, widen=widen)
    take.lock_feet(pp)
    take.fit_hips(pp)
    ends = [i for i in range(frames, len(take)) if take.locks[front][i] is not None and take.locks[front][i - 1] is None]
    e = ends[0]
    cut = motion.Take(take.c[e - frames:e + 1], "run")
    cut.locks = {k: v[e - frames:e + 1] for k, v in take.locks.items()}
    travel = cut.c[-1]["hips"] - cut.c[0]["hips"]
    R = rot(Z, heading - math.degrees(math.atan2(travel.x, -travel.y)))
    h = R @ cut.c[-1]["hips"]
    out = motion.Take([motion.moved(c, R, Vector((-h.x, -h.y, 0.0))) for c in cut.c], "run")
    out.locks = cut.locks
    return out


def launched(pp, pose, take, frames=7):
    """'take' entered from a standing pose: over the first frames the controls go from the pose to
    the take's own, which carries the body from rest up to the take's speed; feet that are still
    down while that happens are then held where they are (lock_feet)."""
    c = [motion.mix(pose, t, (lambda u: u * u * (3 - 2 * u))((i + 1) / (frames + 1))) for i, t in enumerate(take.c[:frames])] + take.c[frames:]
    out = motion.Take(c, take.name)
    out.lock_feet(pp)
    out.fit_hips(pp)
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


# ----------------------------------------------------------------------------- the fight
EVENTS = []                                          # what happens when (filled by fight()): sparks, spray, camera shake and the tests read it


def blade_key(f, point, direction, along, edge, ease="inout", sw=None, **more):
    """A sword track key in the world that puts the blade's point 'along' metres from the guard on
    'point', the blade lying along 'direction' with its edge toward 'edge'. This is how blades are
    made to meet: both swords get a key on the same point on the same frame. With the sword given,
    its curve is allowed for (the blade itself is on the point, not its chord)."""
    from .puppet import sword_matrix
    d = Vector(direction).normalized()
    m = sword_matrix(Vector(point) - d * along, d, edge)
    if sw is not None:
        m.translation += Vector(point) - m @ Vector(sw.arc(along))
    return dict(f=f, space="world", m=m, ease=ease, **more)


def window(part, a, b):
    """A part (take, sword tracks, holds, steering) cut down to take frames a..b, to bake one beat alone."""
    take, tracks, holds, steer = part
    cut = motion.Take(take.c[a:b + 1], take.name)
    cut.locks = {k: v[a:b + 1] for k, v in take.locks.items()}
    tr = {key: [dict(k, f=k["f"] - a) for k in keys] for key, keys in tracks.items()}
    hd = [dict(h, f0=h["f0"] - a, f1=h["f1"] - a) for h in holds]
    st = {key: [(f - a, y, p) for f, y, p in ks] for key, ks in steer.items()} if steer else None
    return cut, tr, hd, st


def _blend(Ma, Mb, t):
    """Between two sword places (4x4)."""
    return motion._mix4(Ma, Mb, t)


class Part:
    """One fighter's part while the fight is put together: the take so far, his sword tracks and holds."""

    def __init__(self, A, take, tracks, holds, steer):
        self.A, self.pp, self.take, self.tracks, self.holds, self.steer = A, A.pp, take, tracks, holds, steer

    def __len__(self):
        return len(self.take)

    @property
    def last(self):
        return self.take.c[-1]

    def add(self, seg):
        """Carry on with a take whose first frame is the part's last."""
        self.take = joined(self.take, seg)

    def keyed(self, keys, steps=(), name="keyed"):
        """Carry on with poses set by hand, from the part's last frame: keys = [(take frame, controls, ease)],
        steps as for Take.from_keys, in take frames."""
        f0 = len(self.take) - 1
        seg = motion.Take.from_keys(self.pp, [(0, self.last, "inout")] + [(f - f0, c, e) for f, c, e in keys],
                                    [(tag, a - f0, b - f0, to, lift) for tag, a, b, to, lift in steps], name)
        seg.fit_hips(self.pp)
        self.add(seg)

    def frame(self, f, space="chest"):
        """The chest (or hips) frame on a take frame: takes a place given 'as if he stood in the rest pose' into the world."""
        return self.A._spine(self.take.c[min(f, len(self.take) - 1)])[space]

    def sword(self, key, f):
        """Where the track as it stands puts a sword on a take frame (world, standard axes); not for a sheathed sword."""
        return self.A._track(self.A.swords[key], sorted(self.tracks[key], key=lambda k: k["f"]), f, self.A._spine(self.take.c[min(f, len(self.take) - 1)]))

    def on_blade(self, key, f, along):
        """World position of the point of a blade 'along' metres from its guard, as the track stands."""
        return self.sword(key, f) @ Vector(self.A.swords[key].arc(along))

    def at(self, key, f, M, ease="inout", space="chest", **more):
        """A track key that puts a sword on a place given in the chest's (or hips') frame."""
        self.tracks[key].append(dict(f=f, space=space, m=M, ease=ease, **more))

    def result(self):
        for key in self.tracks:
            self.tracks[key].sort(key=lambda k: k["f"])
        for h in self.holds:
            h["f1"] = min(h["f1"], len(self.take))
        return self.take, self.tracks, self.holds, self.steer


def _oni_stations(A):
    """Places for the Oni's sword in his chest's frame. guard, up, high, mid and cut are the overhead cut
    of the Stage 3 test, which was measured clear of his body; his arms are short for his deep chest,
    so two hands on the grip only work in front of the breastbone and above."""
    still = dict(hips=tuple(A.pp.H0["Hips"]))
    cut = dict(hips=(0.0, -0.40, 0.93), hips_rot=(4, 10, 0), chest_rot=(0, 23, 0))
    guard = dict(hips=(0.0, -0.05, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0))
    K = lambda pose, g, p, e: A.sword_key(0, pose, g, p, e)["m"]
    return dict(guard=K(guard, (-0.04, -0.60, 1.33), (0.02, -0.90, 0.42), (0, -0.42, -0.90)),
                up=K(still, (0.0, -0.58, 1.80), (0.0, -0.50, 0.87), (0, -0.87, -0.50)),          # raised past the face at arm's length
                high=K(still, (0.0, -0.27, 2.10), (0.0, 0.5, 0.87), (0, -0.87, 0.5)),            # hands above the forehead, blade back over the head
                mid=K(still, (0.0, -0.52, 1.95), (0.0, -0.42, 0.91), (0, -0.91, -0.42)),         # coming down in front of the face
                cut=K(cut, (-0.02, -1.02, 1.12), (0.0, -0.975, -0.22), (0, 0.22, -0.975)),       # the cut home: arms long, blade level
                carry=K(still, (-0.45, -0.22, 1.38), (-0.32, 0.20, 0.93), (0.3, -0.9, 0.3)),     # in the right hand beside the shoulder, point up and out
                aside=K(cut, (-0.05, -1.00, 1.10), (-0.62, -0.72, -0.32), (0.0, 0.3, -0.95)),    # the cut knocked down and away to his right
                side=A.sword_key(0, still, (-0.47, -0.26, 1.20), (-0.50, -0.74, -0.44), (0.2, 0.4, -0.9), space="hips")["m"],   # right hand only, low at his side (hips' frame)
                # the great one-handed cut, level, from behind his right shoulder round to his left (the edge leads all the way)
                wind=K(still, (-0.50, 0.05, 1.50), (-0.35, 0.90, 0.25), (-0.9, -0.35, 0.0)),
                sweep1=K(still, (-0.55, -0.33, 1.45), (-0.80, -0.60, 0.0), (0.6, -0.8, 0.0)),
                sweep2=K(still, (-0.38, -0.46, 1.45), (-0.20, -0.98, 0.0), (0.98, -0.2, 0.0)),
                sweep3=K(still, (-0.20, -0.47, 1.45), (0.35, -0.94, 0.0), (0.94, 0.35, 0.0)),
                sweep4=K(still, (-0.05, -0.42, 1.42), (0.93, -0.30, -0.20), (0.30, 0.93, 0.0)),
                # the passing cut, one-handed, from in front of his left breast out to his right (the edge leads)
                pass1=K(still, (-0.04, -0.40, 1.42), (0.92, -0.25, 0.10), (-0.25, -0.92, 0.0)),
                pass2=K(still, (-0.46, -0.36, 1.44), (-0.70, -0.71, 0.05), (-0.71, 0.70, 0.0)),
                pass2b=K(still, (-0.52, -0.26, 1.50), (-0.72, -0.35, 0.60), (-0.35, 0.72, 0.0)),      # just after the blades meet: up and over the other's arm
                pass3=K(still, (-0.60, -0.08, 1.50), (-0.80, 0.45, 0.40), (0.45, 0.80, 0.0)),
                held=K(still, (-0.58, -0.10, 1.38), (-0.80, 0.26, -0.54), (0.3, 0.9, -0.1)))             # the cut finished and held: arm long, point low and out to his right


def _ronin_stations(A):
    """Places for the Ronin's two swords in his chest's frame, per sword key."""
    still = dict(hips=tuple(A.pp.H0["Hips"]))
    K = lambda g, p, e: A.sword_key(0, still, g, p, e)["m"]
    both = lambda f: {key: f(sg) for key, sg in (("R", -1.0), ("L", 1.0))}
    return dict(open=both(lambda sg: K((sg * 0.36, -0.30, 1.48), (sg * 0.10, -0.45, 0.88), (sg * -0.2, -0.85, -0.45))),      # both raised, points up and a little apart
                ready=both(lambda sg: K((sg * 0.30, -0.30, 1.32), (sg * -0.12, -0.78, 0.60), (0.0, -0.6, -0.8))),          # in front of him, points at the other's face
                wings=both(lambda sg: K((sg * 0.49, -0.14, 1.19), (sg * 0.84, 0.26, -0.47), (sg * 0.3, -0.5, -0.8))),      # low and wide, points trailing
                high=both(lambda sg: K((sg * 0.44, -0.04, 1.87), (sg * 0.50, 0.30, 0.81), (sg * 0.3, -0.9, 0.2))),          # raised to cut: blade up and out, behind the brim's line
                back=both(lambda sg: K((sg * 0.50, -0.02, 1.22), (sg * 0.62, 0.70, -0.35), (sg * 0.3, -0.6, -0.7))),       # drawn back at the hip for a cut from the side
                sweep=both(lambda sg: K((sg * 0.50, -0.18, 1.28), (sg * 0.88, -0.46, -0.05), (0.0, -0.3, -0.95))),         # half way round such a cut: blade out to the side and forward
                across=both(lambda sg: K((sg * 0.04, -0.45, 1.36), (sg * -0.90, -0.30, 0.10), (sg * 0.3, -0.9, 0.0))))     # the sword hand in front of the other breast, to cut outward as he passes


# The Ronin's fighting stance, for a fighter on the origin facing -Y: left foot ahead, weight between the feet.
RONIN_STANCE = dict(
    front=dict(pos=(0.12, -0.66, 0.0)),
    up=dict(hips=(0.0, -0.44, 0.92), hips_rot=(-8, 2, 0), chest_rot=(-3, 2, 0), head_rot=(0, -4, 0)),
    ready=dict(hips=(0.0, -0.40, 0.90), hips_rot=(-8, 4, 0), chest_rot=(-3, 6, 0), head_rot=(0, -2, 0)),
    brace=dict(hips=(0.0, -0.42, 0.84), hips_rot=(-8, 6, 0), chest_rot=(-3, 8, 0), head_rot=(0, -6, 0)),       # sunk under a blow, looking up at it
    sink=dict(hips=(0.0, -0.40, 0.80), hips_rot=(-8, 7, 0), chest_rot=(-3, 10, 0), head_rot=(0, -7, 0)),
    low=dict(hips=(0.0, -0.38, 0.63), hips_rot=(-8, 10, 0), chest_rot=(-3, 12, 0), head_rot=(0, -13, 0)),      # driven down
    low2=dict(hips=(0.0, -0.38, 0.615), hips_rot=(-8, 10, 0), chest_rot=(-3, 13, 0), head_rot=(0, -13, 0)))


def _fit_run(pp, pose, to_xy, frames, front, speed=0.85, widen=0.012, ease_in=7):
    """A run of frames + 1 frames from a standing pose to the spot 'to_xy', ending on the stride where the
    'front' foot strikes the ground. The clip's strides are made longer or shorter to cover exactly the
    distance (every position is stretched along the way he runs, so a planted foot stays planted)."""
    p0 = Vector((pose["hips"].x, pose["hips"].y, 0.0))
    v = Vector((to_xy[0], to_xy[1], 0.0)) - p0
    d = v.normalized()
    run = run_to(pp, frames, math.degrees(math.atan2(d.x, -d.y)), speed, widen, front)
    travel = run.c[-1]["hips"] - run.c[0]["hips"]
    k = v.length / math.hypot(travel.x, travel.y)
    end = Vector((to_xy[0], to_xy[1], 0.0))

    def fit(p):
        return Vector((p.x, p.y, 0.0)) + d * (Vector((p.x, p.y, 0.0)).dot(d) * (k - 1.0)) + end + Vector((0.0, 0.0, p.z))

    for c in run.c:
        c["hips"] = fit(c["hips"])
        for s in "LR":
            c["foot_" + s] = dict(c["foot_" + s], pos=fit(c["foot_" + s]["pos"]))
    out = launched(pp, pose, run, ease_in)
    return out, k


def _dash(O, R):
    """10-12 s. Both run in; the Oni's cut comes down with both hands and is caught on the Ronin's crossed
    blades on take frame HIT. The Oni leads: his sword is placed from his own body, and the Ronin's two
    blades are laid on the point of his blade that they stop.
    Each brakes over two steps: the last running stride lands under the body, the other foot swings
    through and lands ahead as the cut arrives, so that he stops with his weight between his feet."""
    T0 = DASH
    PLANT = HIT - 6                                                  # the last running stride
    MEET = Vector((-0.05, 2.05, 0.0))                                # where the blades meet, on the ground plan
    ALONG = 0.50                                                     # ...on the Oni's blade, from his guard
    # --- the Oni: sword up beside the right shoulder as he runs, then both hands bring it down
    A, pp, K = O.A, O.pp, O.K
    g = A.swords["main"].spec["grip"]
    face = 176.5                                                     # north, closing a little on the Ronin's line
    FRONT = dict(pos=(-0.13, -0.86, 0.0))                            # the right foot, which comes through and lands ahead
    lunge = dict(hips=(0.0, -0.64, 0.92), hips_rot=(10, 12, 0), chest_rot=(4, 22, 0), head_rot=(0, 8, 0))
    press = dict(hips=(0.0, -0.70, 0.89), hips_rot=(10, 14, 0), chest_rot=(4, 26, 0), head_rot=(0, 9, 0))
    stop = _blend(K["mid"], K["cut"], 0.22)                          # the cut as far as it gets
    p = rot(Z, face) @ (A._spine(pp.canon(lunge))["chest"] @ stop @ Vector(A.swords["main"].arc(ALONG)))
    at = (MEET.x - p.x, MEET.y - p.y)                                # where his last stride must land for the blade to arrive on the spot
    run, k = _fit_run(pp, O.last, at, PLANT - T0, "Left")
    O.add(run)
    O.note["oni stride"] = k
    O.spot, O.face = at, face
    here = lambda pose: to_world(pp, pose, at, face)
    O.keyed([(HIT, here(lunge), "slow_out"), (HIT + 4, here(press), "slow_out")],
            [("Right", PLANT, HIT - 1, dict(pos=tuple(here(dict(lunge, foot_R=FRONT))["foot_R"]["pos"]), yaw=face, pitch=0), 0.05),
             ("Left", HIT - 3, HIT + 1, dict(pitch=22), 0.0)], "oni_clash")
    O.at("main", T0 + 8, K["carry"])
    O.at("main", HIT - 10, K["carry"])
    O.at("main", HIT - 4, K["high"], ease="slow_out")
    O.at("main", HIT, stop, ease="slow_in")
    O.at("main", HIT + 4, _blend(K["mid"], K["cut"], 0.27), ease="slow_out")
    for h in O.holds:                                                # the left hand lets go of the grip for the run and comes back for the cut
        if h["hand"] == "Left" and h.get("on") != "saya" and h["f1"] >= T0:
            h["f1"], h["blend_out"], h["free_blend"] = T0, 6, True
    O.holds.append(dict(sword="main", hand="Left", f0=HIT - 5, f1=FOREVER, along=g - 0.062, roll=-28, lead=False, blend_in=6, free_blend=True))
    # --- the Ronin: blades trailing low behind him, then up and crossed under the cut
    A, pp = R.A, R.pp
    face = -2.5                                                      # south, closing a little on the Oni's line
    S = R.S
    P = O.on_blade("main", HIT, ALONG)
    q = rot(Z, face) @ (A._spine(pp.canon(S["brace"]))["chest"] @ Vector((0.0, -0.72, 1.5)))     # the crossing, 0.72 m in front of his breastbone
    at = (P.x - q.x, P.y - q.y)
    run, k = _fit_run(pp, R.last, at, PLANT - T0, "Right", speed=0.88)
    R.add(run)
    R.note["ronin stride"] = k
    R.spot, R.face = at, face
    here = lambda pose: to_world(pp, pose, at, face)
    R.keyed([(HIT, here(S["brace"]), "slow_out"), (HIT + 4, here(S["sink"]), "slow_out")],
            [("Left", PLANT, HIT - 1, dict(pos=tuple(here(dict(S["brace"], foot_L=S["front"]))["foot_L"]["pos"]), yaw=face, pitch=0), 0.05),
             ("Right", HIT - 3, HIT + 1, dict(pitch=22), 0.0)], "ronin_clash")
    still = dict(hips=tuple(pp.H0["Hips"]))
    for key, sg in (("R", -1.0), ("L", 1.0)):
        k_trail = A.sword_key(T0 + 8, still, (sg * 0.46, 0.02, 1.12), (sg * 0.55, 0.72, -0.42), (sg * 0.3, -0.5, -0.8))     # low and behind as he runs
        R.tracks[key] += [k_trail, dict(k_trail, f=HIT - 7), dict(f=HIT - 3, space="chest", m=R.K["open"][key], ease="inout")]
        for f in range(HIT, HIT + 5):                                # on the Oni's blade for as long as it bears down
            _cross(R, O, key, sg, f, ALONG, FIST, ease="slow_in" if f == HIT else "linear")
    EVENTS.append(dict(kind="clash", f=HIT, at=O.on_blade("main", HIT, ALONG), power=1.0, blades=(("oni", "main", ALONG), ("ronin", "R", None), ("ronin", "L", None))))
    for P_, tag in ((O, "Right"), (R, "Left")):                      # the feet they stop on throw water
        EVENTS.append(dict(kind="splash", f=HIT - 1, at=foot_xy(P_.take.c[HIT], tag), power=1.0, toward=(0.0, 1.0 if P_ is O else -1.0, 0.0)))
    return HIT + 4


FIST = (0.27, -0.36, 1.50)                           # where the Ronin holds each sword for the cross, in his chest's frame (x to its own side)


def _local(P, p):
    """A world position seen from where a fighter stands (his spot and facing): x to his left, -y ahead."""
    return rot(Z, -P.face) @ (Vector((p[0], p[1], 0.0)) - Vector((P.spot[0], P.spot[1], 0.0)))


def _cross(R, O, key, sg, f, along, fist, ease="linear", at=None):
    """Lay one of the Ronin's blades on the Oni's blade (the point 'along' metres from the Oni's guard)
    on a take frame, held from a fist placed in the Ronin's own chest frame. at: the take frame whose
    point of the Oni's blade is meant (to have the cross waiting there before the cut arrives)."""
    P = O.on_blade("main", f if at is None else at, along)
    G = R.frame(f) @ Vector((sg * fist[0], fist[1], fist[2] + 0.03 * sg))     # the left a little higher: the blades cross, they do not collide
    R.tracks[key].append(blade_key(f, P, P - G, (P - G).length, (sg * -0.2, -0.4, 0.9), ease=ease, sw=R.A.swords[key]))


def _hammer(O, R):
    """12-15 s. Three overhead cuts, each heavier than the last. The Ronin stops them on his crossed
    blades: the first where he stands, the second drives him back skidding, the third drives him down."""
    assert len(O) - 1 == B0 == len(R) - 1
    H = HAMMER
    END = C0
    ALONG = 0.50
    # --- the Oni
    A, pp, K = O.A, O.pp, O.K
    at, face = O.spot, O.face
    here = lambda pose: to_world(pp, pose, at, face)
    fr, fl = _local(O, foot_xy(O.last, "Right")), _local(O, foot_xy(O.last, "Left"))
    O.note["oni feet at the clash (his own frame: front, rear, hips)"] = [tuple(round(v, 2) for v in q[:2]) for q in (fr, fl, _local(O, O.last["hips"]))]
    LUNGE = 0.30
    high = lambda y, lean=-8: dict(hips=(0.0, y + 0.40, 1.03), hips_rot=(10, -1, 0), chest_rot=(6, lean, 0), head_rot=(0, 4, 0))
    cut = lambda y: dict(hips=(0.0, y + 0.22, 0.91), hips_rot=(10, 12, 0), chest_rot=(4, 23, 0), head_rot=(0, 8, 0))
    press = lambda y, dz=0.0, lean=26: dict(hips=(0.0, y + 0.16, 0.89 + dz), hips_rot=(10, 14, 0), chest_rot=(4, lean, 0), head_rot=(0, 9, 0))
    y1, y2, y3 = fr.y, fr.y - LUNGE, fr.y - 2 * LUNGE                # where his front foot stands for each cut
    foot = lambda p, **more: dict(pos=tuple(here(dict(hips=(0, 0, 1), foot_R=dict(pos=(p[0], p[1], 0.0))))["foot_R"]["pos"]), **more)
    keys = [(B0 + 10, here(high(y1)), "inout"), (B0 + 12, here(high(y1)), "inout"), (H[0], here(cut(y1)), "slow_in"), (H[0] + 3, here(press(y1)), "slow_out"),
            (B0 + 29, here(high(y1)), "inout"), (B0 + 31, here(high(y1)), "inout"), (H[1], here(cut(y2)), "slow_in"), (H[1] + 6, here(press(y2 - 0.10)), "slow_out"),
            (B0 + 48, here(high(y2, -12)), "inout"), (B0 + 51, here(high(y2, -13)), "inout"), (H[2], here(cut(y3)), "slow_in"),
            (H[2] + 5, here(press(y3 - 0.04, -0.03, 31)), "slow_out"), (END, here(press(y3 - 0.05, -0.035, 32)), "inout")]
    steps = [("Right", B0 + 30, H[1], foot((fr.x, y2), yaw=face), 0.07),                        # the lunge lands with the cut
             ("Left", H[1] - 4, H[1] + 3, foot((fl.x, fl.y - LUNGE), pitch=22), 0.03),              # and the rear foot follows at once
             ("Right", B0 + 51, H[2], foot((fr.x, y3), yaw=face), 0.08),
             ("Left", H[2] - 4, H[2] + 3, foot((fl.x, fl.y - 2 * LUNGE), pitch=22), 0.03)]
    O.keyed(keys, steps, "oni_hammer")
    stop = lambda t: _blend(K["mid"], K["cut"], t)
    for f, M, e in ((B0 + 10, K["high"], "inout"), (B0 + 12, K["high"], "inout"), (H[0], stop(0.30), "slow_in"), (H[0] + 3, stop(0.36), "slow_out"),
                    (B0 + 29, K["high"], "inout"), (B0 + 31, K["high"], "inout"), (H[1], stop(0.30), "slow_in"), (H[1] + 6, stop(0.38), "slow_out"),
                    (B0 + 48, K["high"], "inout"), (B0 + 51, K["high"], "inout"), (H[2], stop(0.42), "slow_in"), (H[2] + 5, stop(0.78), "slow_out"),
                    (END, stop(0.82), "inout")):
        O.at("main", f, M, ease=e)
    # --- the Ronin
    A, pp, S = R.A, R.pp, R.S
    face = R.face
    fl, fr = _local(R, foot_xy(R.last, "Left")), _local(R, foot_xy(R.last, "Right"))          # his stance, from where he stands: left foot ahead
    R.note["ronin feet at the clash (front, rear, hips)"] = [tuple(round(v, 2) for v in q[:2]) for q in (fl, fr, _local(R, R.last["hips"]))]

    def spot(f, pose):                                               # where he must stand for the Oni's blade to come down 0.72 m in front of his breastbone
        P = O.on_blade("main", f, ALONG)
        q = rot(Z, face) @ (A._spine(pp.canon(pose))["chest"] @ Vector((0.0, -0.72, 1.5)))
        return (P.x - q.x, P.y - q.y)

    s1, s2, s2b, s3 = spot(H[0], S["brace"]), spot(H[1], S["brace"]), spot(H[1] + 6, S["sink"]), spot(H[2], S["brace"])
    R.note["ronin gives ground"] = [round((Vector(b) - Vector(a)).length, 2) for a, b in ((R.spot, s1), (s1, s2), (s2, s2b), (s2b, s3))]
    on = lambda sp, name: to_world(pp, S[name], sp, face)
    foot = lambda sp, p, **more: dict(pos=tuple(to_world(pp, dict(hips=(0, 0, 1), foot_R=dict(pos=(p.x, p.y, 0.0))), sp, face)["foot_R"]["pos"]), **more)
    keys = [(B0 + 6, on(R.spot, "up"), "inout"), (B0 + 12, on(s1, "ready"), "inout"), (H[0], on(s1, "brace"), "snap"), (H[0] + 3, on(s1, "sink"), "slow_out"),
            (H[0] + 13, on(s2, "ready"), "inout"), (H[1], on(s2, "brace"), "snap"), (H[1] + 6, on(s2b, "sink"), "slow_out"),
            (H[1] + 16, on(s3, "ready"), "inout"), (H[2], on(s3, "brace"), "snap"), (H[2] + 5, on(s3, "low"), "slow_out"), (END, on(s3, "low2"), "inout")]
    steps = [("Right", H[0] + 4, H[0] + 10, foot(s2, fr, pitch=22), 0.04),                     # back a step while the sword is over the Oni's head
             ("Left", H[0] + 9, H[0] + 15, foot(s2, fl, yaw=face), 0.04),
             ("Right", H[1], H[1] + 7, foot(s2b, fr, pitch=0, slide=True), 0.0),               # the second cut shoves him back over the wet stone
             ("Left", H[1], H[1] + 7, foot(s2b, fl, yaw=face, slide=True), 0.0),
             ("Right", H[1] + 9, H[1] + 15, foot(s3, fr, pitch=0), 0.04),
             ("Left", H[1] + 14, H[1] + 20, foot(s3, fl, yaw=face), 0.04)]
    R.keyed(keys, steps, "ronin_hammer")
    for key, sg in (("R", -1.0), ("L", 1.0)):
        for f in range(B0 + 1, B0 + 4):                              # he heaves the Oni's blade up off him
            _cross(R, O, key, sg, f, ALONG, FIST)
        R.tracks[key].append(dict(f=B0 + 10, space="chest", m=R.K["ready"][key], ease="inout"))
        for i, (h, n) in enumerate(zip(H, (3, 6, 8))):
            R.tracks[key].append(dict(f=h - 4, space="chest", m=R.K["open"][key], ease="inout"))
            _cross(R, O, key, sg, h - 1, ALONG, FIST2, ease="slow_out", at=h)       # the cross is there before the cut lands
            for f in range(h, h + n + 1):
                _cross(R, O, key, sg, f, ALONG, FIST2)
            if i < 2:
                R.tracks[key].append(dict(f=h + n + 6, space="chest", m=R.K["ready"][key], ease="inout"))
    for i, h in enumerate(H):
        EVENTS.append(dict(kind="clash", f=h, at=O.on_blade("main", h, ALONG), power=(1.0, 1.2, 1.5)[i], blades=(("oni", "main", ALONG), ("ronin", "R", None), ("ronin", "L", None))))
    EVENTS.append(dict(kind="skid", who="ronin", f0=H[1], f1=H[1] + 7))
    EVENTS.append(dict(kind="splash", f=H[1], at=foot_xy(O.take.c[H[1]], "Right"), power=1.0, toward=(0.0, 1.0, 0.0)))
    EVENTS.append(dict(kind="splash", f=H[2], at=foot_xy(O.take.c[H[2]], "Right"), power=1.3, toward=(0.0, 1.0, 0.0)))
    return END


FIST2 = (0.25, -0.40, 1.57)                          # ...and for a block he has time to set: higher and nearer the crossing


def blades_beside(A, take):
    """A place for each of the Ronin's swords on every frame of a take, in his chest's frame, for
    motion in which the hands fly about (a captured spinning kick): each wrist keeps the rhythm it
    was captured with but is held to the space beside the body and below the brim, and the blade
    points out and back from there - clear of head, hat and the kicking legs. Returns {key: [4x4]}."""
    import numpy as np

    from . import clear as clr
    from .puppet import perp, sword_matrix
    pp = A.pp
    out = {}
    for key, tag, sgn in (("R", "Right", -1.0), ("L", "Left", 1.0)):
        sh = pp.H0[tag + "Arm"]                                      # the shoulder, in the chest's own (rest pose) coordinates
        reach = (pp.arm_[tag]["L1"] + pp.arm_[tag]["L2"]) * 0.90
        W = []
        for c in take.c:
            sp = A._spine(c)
            w = sp["chest"].inverted() @ A._hand_world(c, tag, sp)[0]                  # the captured wrist, seen from the chest
            w = Vector((sgn * max(sgn * w.x, 0.34), min(w.y, 0.15), min(w.z, sh.z + 0.02)))   # beside the body, no higher than the shoulder
            v = w - sh
            w = sh + v.normalized() * min(v.length, reach)
            near = 0.32 ** 2 - (w.y - sh.y) ** 2 - (w.z - sh.z) ** 2                   # ...and not folded up against his own shoulder plate
            if near > 0.0:
                w.x = sgn * max(sgn * w.x, sgn * sh.x + math.sqrt(near))
            W.append(w)
        W = clr._smooth(np.array(W), 7)
        mats = []
        for f in range(len(take.c)):
            w = Vector(W[f])
            arm = (w - sh).normalized()
            t = min(1.0, max(0.0, (w.z - (sh.z - 0.45)) / 0.40))
            lift = t * t * (3.0 - 2.0 * t)                           # 0 with the hand low, 1 with it at shoulder height
            point = Vector((sgn * 0.80, 0.35, -0.45 + 0.60 * lift)).normalized()
            if point.angle(arm) < math.radians(40.0):                # a blade in line with the forearm would break the wrist
                point = (arm * math.cos(math.radians(40.0)) + perp(point, arm) * math.sin(math.radians(40.0))).normalized()
            M = sword_matrix(w, point, arm)                          # knuckles, and so the edge, face the way the forearm runs
            M.translation = w + (w - A._grip(tag, M, 0.058, 0.0, A.swords[key].R)[0])   # so that the wrist comes to w
            mats.append(M)
        out[key] = mats
    return out


def _counter(O, R):
    """15-18 s. The Ronin slips out from under the third cut: he steps in past the Oni's blade turning
    side on, his right blade sweeping across the Oni's chest (the Oni rocks back out of its way),
    spins on and his heel comes down into the Oni's belly. The Oni is thrown back and skids across
    the wet floor. The spin and the kick are a captured move; where the kick lands places it."""
    assert len(O) - 1 == C0 == len(R) - 1 and KICK == SPIN + 24      # the heel lands on the clip's 24th frame
    STOP = KICK + 18                                                 # the Oni comes to rest
    END = D0
    SLIDE = 2.6
    DRIFT = 0.35                                                     # how far the Ronin's jump carries him toward the Oni
    # --- the Oni, up to the kick
    A, pp, K = O.A, O.pp, O.K
    g = A.swords["main"].spec["grip"]
    at, face = O.spot, O.face
    here = lambda pose: to_world(pp, pose, at, face)
    fr, fl = _local(O, foot_xy(O.last, "Right")), _local(O, foot_xy(O.last, "Left"))
    y = fr.y
    aside = dict(hips=(0.0, y + 0.30, 0.93), hips_rot=(4, 8, 0), chest_rot=(-8, 14, 0), head_rot=(4, 6, 0))
    out_L = dict(rel=(0.36, -0.10, -0.28))                           # the free arm thrown out for balance
    recoil = dict(hips=(0.0, y + 0.54, 0.96), hips_rot=(6, -4, 0), chest_rot=(2, -16, 0), head_rot=(4, -8, 0), hand_L=out_L)     # rocked back from the blade, weight on the rear foot
    back = dict(hips=(0.0, y + 0.60, 0.95), hips_rot=(6, -6, 0), chest_rot=(2, -22, 0), head_rot=(2, -8, 0), hand_L=out_L)       # further still as the second blade comes round
    brace = dict(hips=(0.0, y + 0.54, 0.97), hips_rot=(6, -3, 0), chest_rot=(2, -11, 0), head_rot=(0, 0, 0), hand_L=out_L)       # still leaning away when the heel comes down
    struck = dict(hips=(0.0, y + 0.62, 0.95), hips_rot=(4, -4, 0), chest_rot=(2, 16, 0), head_rot=(0, 14, 0))      # folded over the heel
    skid = dict(hips=(0.0, y + 0.52, 0.74), hips_rot=(8, 12, 0), chest_rot=(6, 30, 0), head_rot=(0, -8, 0))       # low, leaning into the slide
    rest = dict(hips=(0.0, y + 0.50, 0.72), hips_rot=(8, 13, 0), chest_rot=(6, 33, 0), head_rot=(0, -14, 0))
    guard = dict(hips=(0.0, y + 0.40, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0))
    slid = lambda f: SLIDE * (1.0 - (1.0 - min(1.0, max(0.0, (f - KICK) / (STOP - KICK)))) ** 2)     # how far he has skidded on a take frame
    off = lambda pose, d: dict(pose, hips=(pose["hips"][0], pose["hips"][1] + d, pose["hips"][2]))
    keys = [(C0 + 6, here(aside), "inout"), (SPIN + 1, here(recoil), "slow_out"), (SPIN + 9, here(back), "inout"), (SPIN + 15, here(back), "inout"), (KICK - 1, here(brace), "inout"),
            (KICK + 2, here(off(struck, slid(KICK + 2))), "snap")]
    for f in range(KICK + 4, STOP, 2):                               # the body rides the skid: the same curve as the feet
        u = (f - KICK - 2) / (STOP - KICK - 2)
        pose = motion.mix(pp.canon(struck), pp.canon(skid), min(1.0, u * 2.2))
        keys.append((f, to_world(pp, dict(pose, hips=pose["hips"] + Vector((0.0, slid(f), 0.0))), at, face), "linear"))
    keys += [(STOP, here(off(rest, SLIDE)), "linear"), (STOP + 6, here(off(rest, SLIDE)), "inout"), (END, here(off(guard, SLIDE)), "inout")]
    foot = lambda p, **more: dict(pos=tuple(here(dict(hips=(0, 0, 1), foot_R=dict(pos=(p[0], p[1], 0.0))))["foot_R"]["pos"]), **more)
    steps = [("Left", C0 + 5, C0 + 11, foot((fl.x + 0.04, fl.y + 0.24), yaw=face + 40, pitch=0), 0.03),          # a step back to lean away on
             ("Right", KICK, STOP, foot((fr.x - 0.04, fr.y + SLIDE), yaw=face - 8, slide=True), 0.0),
             ("Left", KICK, STOP, foot((fl.x + 0.10, fl.y + SLIDE + 0.36), yaw=face + 40, pitch=0, slide=True), 0.0),
             ("Left", STOP + 8, STOP + 15, foot((fl.x + 0.06, fl.y + SLIDE - 0.04), yaw=face + 38, pitch=0), 0.04)]      # and the rear foot is brought up as he rises
    O.keyed(keys, steps, "oni_thrown")
    O.at("main", C0 + 6, K["aside"], ease="slow_out")
    O.at("main", SPIN + 2, K["side"], space="hips")
    O.at("main", STOP + 6, K["side"], space="hips")
    O.at("main", END, K["guard"])
    for h in O.holds:                                                # the left hand comes off the grip as the blade is knocked away, and returns at the end
        if h["hand"] == "Left" and h.get("on") != "saya" and h["f1"] >= C0:
            h["f1"], h["blend_out"], h["free_blend"] = C0 + 5, 6, True
    O.holds.append(dict(sword="main", hand="Left", f0=END - 2, f1=FOREVER, along=g - 0.062, roll=-28, lead=False, blend_in=9, free_blend=True))
    # --- the Ronin: out from under the blade, the spin, the kick
    A, pp, S = R.A, R.pp, R.S
    face_r = R.face
    clip = mocap.Clip("spinkick")
    spin = motion.Take.from_clip(pp, clip, seconds=clip.T, speed=1.0, widen=0.012)
    spin.lock_feet(pp)
    spin.fit_hips(pp)
    spin = spin.placed((0.0, 0.0), face_r + 90.0)                    # he starts it side on, right shoulder to the Oni
    toward = rot(Z, face_r) @ Vector((0.0, -1.0, 0.0))
    for i, c in enumerate(spin.c):                                   # the jump carries him in: he starts the spin out of the reach of his own blades
        d = toward * (DRIFT * _smooth((i - 12) / 12.0))
        c["hips"] = c["hips"] + d
        for s_ in "LR":
            c["foot_" + s_] = dict(c["foot_" + s_], pos=c["foot_" + s_]["pos"] + d)
    for i, k in ((25, 0.86), (26, 0.76), (27, 0.86)):                # the heel has landed: the leg is pulled back rather than dropped through him
        c = spin.c[i]
        v = c["foot_R"]["pos"] - c["hips"]
        c["foot_R"] = dict(c["foot_R"], pos=Vector((c["hips"].x + v.x * k, c["hips"].y + v.y * k, c["foot_R"]["pos"].z)))
    ball = spin.c[24]["foot_R"]["pos"] + Vector((0.0, 0.0, pp.ball_h))
    target = O.frame(KICK) @ Vector((0.0, -0.25, 1.28))              # the Oni's belly, above the knot of his belt
    away = Vector((ball.x - spin.c[24]["hips"].x, ball.y - spin.c[24]["hips"].y, 0.0)).normalized()
    t = target - away * 0.10 - ball                                  # the sole and toes reach a hand's breadth beyond the ball of the foot
    spin = shifted(spin, (t.x, t.y))
    R.note["kick: heel height against the belt knot"] = (round(ball.z, 2), round(target.z, 2))
    start = spin.c[0]
    rise = to_world(pp, dict(hips=(0.0, -0.40, 0.80), hips_rot=(30, 6, 0), chest_rot=(48, 8, 0), head_rot=(30, -4, 0)), R.spot, face_r)
    rise["hips"] = R.last["hips"].lerp(start["hips"], 0.45) + Vector((0.0, 0.0, 0.06))
    fa = lambda c, s_: motion.foot_angles(c["foot_" + s_]["D"])[0]
    steps = [("Right", C0 + 2, C0 + 8, dict(pos=(start["foot_R"]["pos"].x, start["foot_R"]["pos"].y, 0.0), yaw=fa(start, "R"), pitch=0), 0.06),      # in past the Oni's blade
             ("Left", C0 + 7, SPIN, dict(pos=(start["foot_L"]["pos"].x, start["foot_L"]["pos"].y, 0.0), yaw=fa(start, "L"), pitch=0), 0.04)]
    R.keyed([(C0 + 6, rise, "inout"), (SPIN, start, "inout")], steps, "ronin_slip")
    R.add(spin)
    after = len(R) - 1                                               # the spin's last frame: side on again
    land = spin.c[-1]
    ffr, ffl = foot_xy(land, "Right"), foot_xy(land, "Left")
    RF, LF = Vector((-0.13, -0.30, 0.0)), Vector((0.17, 0.24, 0.0))  # he lands right foot toward the Oni: that foot stays, the left is set behind
    mark = tuple((ffr - rot(Z, face_r) @ RF).to_2d())
    wide = to_world(pp, dict(hips=(0.0, 0.0, 0.86), hips_rot=(10, 4, 0), chest_rot=(4, 8, 0), head_rot=(0, 2, 0)), mark, face_r)
    wide2 = to_world(pp, dict(hips=(0.0, 0.0, 0.88), hips_rot=(10, 4, 0), chest_rot=(4, 6, 0), head_rot=(0, 2, 0)), mark, face_r)
    R.keyed([(after + 11, wide, "slow_out"), (END, wide2, "inout")],
            [("Right", after, after + 3, dict(pos=tuple(ffr), yaw=face_r - 8, pitch=0), 0.0),
             ("Left", after, after + 3, dict(pos=tuple(ffl), pitch=0), 0.0),
             ("Left", after + 3, after + 10, dict(pos=tuple(to_world(pp, dict(hips=(0, 0, 1), foot_L=dict(pos=tuple(LF))), mark, face_r)["foot_L"]["pos"]), yaw=face_r + 34), 0.05)],
            "ronin_lands")
    plan = blades_beside(A, motion.Take(R.take.c[SPIN:after + 1]))
    for key, sg in (("R", -1.0), ("L", 1.0)):
        for f in range(C0 + 1, C0 + 3):                              # the cross tips the Oni's blade off to the side as he goes
            _cross(R, O, key, sg, f, 0.50, FIST2)
        R.tracks[key].append(dict(f=C0 + 7, space="chest", m=R.K["open"][key], ease="inout"))
        for i, M in enumerate(plan[key]):
            R.tracks[key].append(dict(f=SPIN + i, space="chest", m=M, ease="inout" if i == 0 else "linear"))
        R.tracks[key].append(dict(f=after + 10, space="chest", m=R.K["wings"][key], ease="inout"))
        R.tracks[key].append(dict(f=END, space="chest", m=R.K["wings"][key], ease="inout"))
    R.spot = mark
    O.spot = tuple(Vector(O.spot) + (rot(Z, O.face) @ Vector((0.0, SLIDE, 0.0))).to_2d())
    EVENTS.append(dict(kind="kick", f=KICK, at=target, power=1.4))
    EVENTS.append(dict(kind="skid", who="oni", f0=KICK, f1=STOP))
    return END


def _lay(R, O, key, f, along, fist, edge, ease="linear", at=None):
    """Lay one of the Ronin's blades on the point of the Oni's blade 'along' metres from its guard, on a take
    frame, held from a fist placed in the Ronin's chest frame (at: the take frame whose point is meant)."""
    P = O.on_blade("main", f if at is None else at, along)
    G = R.frame(f) @ Vector(fist)
    R.tracks[key].append(blade_key(f, P, P - G, (P - G).length, edge, ease=ease, sw=R.A.swords[key]))
    return (P - G).length


def _spot(R, O, f, pose, where, along):
    """Where the Ronin must stand, in a pose, for the point of the Oni's blade to be at 'where' in his chest's frame."""
    P = O.on_blade("main", f, along)
    q = rot(Z, R.face) @ (R.A._spine(R.pp.canon(pose))["chest"] @ Vector(where))
    return (P.x - q.x, P.y - q.y)


def _trade(O, R):
    """18-21 s. Three fast meetings of blades. The Ronin comes in with a cut from above that stops on the
    Oni's raised guard; the Oni answers with a short chop, caught under the Ronin's left blade; the
    Ronin's cut from low on his right is beaten down. They shove each other off and spring apart."""
    assert len(O) - 1 == D0 == len(R) - 1
    E, END = TRADE, F0
    ALONG = (0.42, 0.50, 0.45)                                       # where on the Oni's blade each meeting is
    # --- the Oni
    A, pp, K = O.A, O.pp, O.K
    at, face = O.spot, O.face
    here = lambda pose: to_world(pp, pose, at, face)
    fr, fl = _local(O, foot_xy(O.last, "Right")), _local(O, foot_xy(O.last, "Left"))
    y0 = fr.y
    y1, y2 = y0 - 0.40, y0 - 0.70                                    # his front foot: a step in to meet the Ronin, a shorter one with his own cut
    guard = lambda y, dz=0.0: dict(hips=(0.0, y + 0.35, 1.00 + dz), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0))
    parry = lambda y, dz=0.0: dict(hips=(0.0, y + 0.30, 0.97 + dz), hips_rot=(8, 3, 0), chest_rot=(3, 5, 0), head_rot=(0, 4, 0))
    high = lambda y: dict(hips=(0.0, y + 0.40, 1.03), hips_rot=(10, -1, 0), chest_rot=(6, -8, 0), head_rot=(0, 4, 0))
    cut = lambda y, lean=23, dz=0.0: dict(hips=(0.0, y + 0.22, 0.91 + dz), hips_rot=(10, 12, 0), chest_rot=(4, lean, 0), head_rot=(0, 8, 0))
    foot = lambda p, **more: dict(pos=tuple(here(dict(hips=(0, 0, 1), foot_R=dict(pos=(p[0], p[1], 0.0))))["foot_R"]["pos"]), **more)
    keys = [(D0 + 6, here(guard(y0 - 0.20, 0.02)), "inout"), (E[0] - 1, here(parry(y1)), "inout"), (E[0] + 2, here(parry(y1, -0.03)), "slow_out"),
            (E[1] - 7, here(high(y1)), "inout"), (E[1] - 5, here(high(y1)), "inout"), (E[1], here(cut(y2)), "slow_in"), (E[1] + 3, here(cut(y2, 26, -0.02)), "slow_out"),
            (E[2] - 5, here(guard(y2 + 0.02, -0.01)), "inout"), (E[2], here(cut(y2, 25, -0.01)), "slow_in"), (E[2] + 4, here(cut(y2, 28, -0.03)), "slow_out"),
            (E[2] + 7, here(cut(y2 - 0.08, 20, 0.0)), "inout"), (E[2] + 14, here(guard(y2 + 0.36, 0.01)), "inout"), (END, here(guard(y2 + 0.55)), "inout")]
    steps = [("Right", D0 + 3, D0 + 9, foot((fr.x, y1), yaw=face), 0.05),
             ("Left", D0 + 7, D0 + 12, foot((fl.x, fl.y - 0.40), pitch=0), 0.03),
             ("Right", E[1] - 6, E[1], foot((fr.x, y2), yaw=face), 0.06),
             ("Left", E[1] - 4, E[1] + 3, foot((fl.x, fl.y - 0.70), pitch=20), 0.03),
             ("Left", E[2] + 8, E[2] + 13, foot((fl.x, fl.y - 0.70 + 0.55), pitch=0), 0.05),             # sprung back off the shove
             ("Right", E[2] + 12, E[2] + 17, foot((fr.x, y2 + 0.55), yaw=face), 0.05)]
    O.keyed(keys, steps, "oni_trade")
    stop = lambda t: _blend(K["mid"], K["cut"], t)
    raised = lambda t: _blend(K["guard"], K["up"], t)
    for f, M, e in ((D0 + 6, K["guard"], "inout"), (E[0] - 2, raised(0.32), "inout"), (E[0] + 2, raised(0.24), "slow_out"),
                    (E[1] - 7, K["high"], "inout"), (E[1] - 5, K["high"], "inout"), (E[1], stop(0.30), "slow_in"), (E[1] + 3, stop(0.36), "slow_out"),
                    (E[2] - 5, K["mid"], "inout"), (E[2], stop(0.72), "slow_in"), (E[2] + 4, stop(0.80), "slow_out"), (E[2] + 7, stop(0.66), "inout"),
                    (END - 3, K["guard"], "inout"), (END, K["guard"], "inout")):
        O.at("main", f, M, ease=e)
    # --- the Ronin
    A, pp = R.A, R.pp
    face_r = R.face
    lunge = dict(hips=(0.0, -0.40, 0.88), hips_rot=(14, 8, 0), chest_rot=(22, 12, 0), head_rot=(6, -3, 0))        # right side leading
    roof = dict(hips=(0.0, -0.04, 0.87), hips_rot=(-6, 4, 0), chest_rot=(-14, 6, 0), head_rot=(0, -7, 0))         # left side leading, under the chop
    low = dict(hips=(0.0, -0.34, 0.80), hips_rot=(12, 8, 0), chest_rot=(20, 14, 0), head_rot=(4, 0, 0))
    wide = dict(hips=(0.0, 0.0, 0.88), hips_rot=(10, 4, 0), chest_rot=(4, 6, 0), head_rot=(0, 2, 0))
    FEET = dict(lunge=((-0.14, -0.74), (0.15, 0.02)), roof=((-0.15, -0.30), (0.16, 0.26)), low=((-0.14, -0.68), (0.16, 0.04)), wide=((-0.13, -0.30), (0.17, 0.24)))
    WHERE = ((-0.05, -0.85, 1.80), (0.0, -0.72, 1.89), (-0.05, -0.78, 1.50))
    FISTS = ((-0.30, -0.40, 1.70), (0.30, -0.36, 1.66), (-0.36, -0.32, 1.36))
    sp = [_spot(R, O, E[0], lunge, WHERE[0], ALONG[0]), _spot(R, O, E[1], roof, WHERE[1], ALONG[1]), _spot(R, O, E[2], low, WHERE[2], ALONG[2])]
    back = tuple((Vector(sp[2]) + (rot(Z, face_r) @ Vector((0.0, 0.7, 0.0))).to_2d()))             # where he lands when they spring apart
    on = lambda spot, pose, dz=0.0: to_world(pp, dict(pose, hips=(pose["hips"][0], pose["hips"][1], pose["hips"][2] + dz)), spot, face_r)
    ft = lambda spot, name, i, **more: dict(pos=tuple(to_world(pp, dict(hips=(0, 0, 1), foot_R=dict(pos=(*FEET[name][i], 0.0))), spot, face_r)["foot_R"]["pos"]), **more)
    half = on(sp[0], dict(lunge, hips=(0.0, 0.20, 0.86), chest_rot=(10, 14, 0)))
    half["hips"] = R.last["hips"].lerp(on(sp[0], lunge)["hips"], 0.5) + Vector((0.0, 0.0, 0.01))
    keys = [(D0 + 5, half, "slow_in"), (E[0], on(sp[0], lunge), "slow_out"), (E[0] + 2, on(sp[0], lunge, -0.03), "slow_out"),
            (E[1] - 6, on(sp[1], roof, 0.04), "inout"), (E[1], on(sp[1], roof), "snap"), (E[1] + 3, on(sp[1], roof, -0.05), "slow_out"),
            (E[2] - 6, on(sp[1], roof, 0.02), "inout"), (E[2], on(sp[2], low), "slow_in"), (E[2] + 4, on(sp[2], low, -0.02), "slow_out"),
            (E[2] + 7, on(sp[2], low, 0.03), "inout"), (E[2] + 12, on(tuple((Vector(sp[2]) + Vector(back)) * 0.5), wide, 0.03), "inout"), (E[2] + 16, on(back, wide, -0.05), "slow_out"),
            (END, on(back, wide), "inout")]
    steps = [("Left", D0 + 1, D0 + 6, ft(sp[0], "lunge", 1, yaw=face_r + 30, pitch=0), 0.06),              # two fast steps in
             ("Right", D0 + 5, E[0], ft(sp[0], "lunge", 0, yaw=face_r - 4), 0.07),
             ("Right", E[0] + 4, E[0] + 9, ft(sp[1], "roof", 0, yaw=face_r - 20), 0.04),                  # back from the Oni's answer
             ("Left", E[0] + 8, E[0] + 13, ft(sp[1], "roof", 1, yaw=face_r + 30), 0.04),
             ("Right", E[1] + 6, E[1] + 12, ft(sp[2], "low", 0, yaw=face_r - 4), 0.05),                   # in again with the low cut
             ("Left", E[1] + 10, E[1] + 15, ft(sp[2], "low", 1, yaw=face_r + 30), 0.03),
             ("Left", E[2] + 8, E[2] + 13, ft(back, "wide", 1, yaw=face_r + 34), 0.06),                    # sprung apart
             ("Right", E[2] + 9, E[2] + 15, ft(back, "wide", 0, yaw=face_r - 8), 0.07)]
    R.keyed(keys, steps, "ronin_trade")
    RK = R.K
    edge = (0.0, 0.0, -1.0)
    tr = R.tracks
    tr["R"] += [dict(f=D0 + 6, space="chest", m=RK["high"]["R"], ease="inout")]
    R.note["trade: blade used from the fist (m)"] = []
    for f in range(E[0], E[0] + 3):
        R.note["trade: blade used from the fist (m)"].append(round(_lay(R, O, "R", f, ALONG[0], FISTS[0], edge, ease="slow_in" if f == E[0] else "linear"), 2))
    tr["R"] += [dict(f=E[0] + 9, space="chest", m=RK["back"]["R"], ease="inout"), dict(f=E[2] - 6, space="chest", m=RK["back"]["R"], ease="inout"),
                dict(f=E[2] - 3, space="chest", m=RK["sweep"]["R"], ease="linear")]                           # round the outside, not through himself
    for f in range(E[2], E[2] + 8):
        R.note["trade: blade used from the fist (m)"].append(round(_lay(R, O, "R", f, ALONG[2], FISTS[2], (0.2, 0.0, -1.0), ease="slow_in" if f == E[2] else "linear"), 2))
    tr["R"] += [dict(f=E[2] + 10, space="chest", m=RK["ready"]["R"], ease="inout"),                    # the blade goes with him when he springs back
                dict(f=END - 4, space="chest", m=RK["wings"]["R"], ease="inout"), dict(f=END, space="chest", m=RK["wings"]["R"], ease="inout")]
    tr["L"] += [dict(f=E[0], space="chest", m=RK["back"]["L"], ease="inout"), dict(f=E[1] - 6, space="chest", m=RK["open"]["L"], ease="inout")]
    _lay(R, O, "L", E[1] - 1, ALONG[1], FISTS[1], edge, ease="slow_out", at=E[1])
    for f in range(E[1], E[1] + 4):
        R.note["trade: blade used from the fist (m)"].append(round(_lay(R, O, "L", f, ALONG[1], FISTS[1], edge), 2))
    tr["L"] += [dict(f=E[1] + 10, space="chest", m=RK["ready"]["L"], ease="inout"), dict(f=E[2] + 6, space="chest", m=RK["ready"]["L"], ease="inout"),
                dict(f=END - 4, space="chest", m=RK["wings"]["L"], ease="inout"), dict(f=END, space="chest", m=RK["wings"]["L"], ease="inout")]
    for i, (e, key) in enumerate(zip(E, "RLR")):
        EVENTS.append(dict(kind="clash", f=e, at=O.on_blade("main", e, ALONG[i]), power=1.0, blades=(("oni", "main", ALONG[i]), ("ronin", key, None))))
    R.spot = back
    return END


def _power(O, R):
    """21-24 s. The Oni coils, his blade back behind his right shoulder (it takes fire), comes in at a
    run and cuts level with one hand, right to left. The Ronin throws himself back out of it; the
    point passes a hand's breadth from his chest, through the cape that swings forward as he lands."""
    assert len(O) - 1 == F0 == len(R) - 1
    END = G0
    PLANT = SLASH - 5                                                # the Oni's last running stride
    # --- the Ronin: watches, sinks, leaps back, lands in a skid
    A, pp = R.A, R.pp
    face_r = R.face
    fR, fL = _local(R, foot_xy(R.last, "Right")), _local(R, foot_xy(R.last, "Left"))
    P = lambda y, z, hr, cr, hd: dict(hips=(0.0, y, z), hips_rot=hr, chest_rot=cr, head_rot=hd)
    watch = P(0.02, 0.90, (10, 2, 0), (4, 4, 0), (0, 0, 0))
    crouch = P(0.06, 0.77, (8, 10, 0), (4, 16, 0), (0, -6, 0))
    air = P(0.74, 1.00, (6, -4, 0), (2, -12, 0), (0, 4, 0))
    land = P(1.34, 0.74, (8, 12, 0), (4, 20, 0), (0, -8, 0))
    FAR = 2.30                                                       # how far back he ends: the leap, then a long skid
    skid = P(FAR, 0.79, (8, 10, 0), (4, 16, 0), (0, -6, 0))
    stand = P(FAR, 0.89, (10, 4, 0), (4, 6, 0), (0, 2, 0))
    on = lambda pose: to_world(pp, pose, R.spot, face_r)
    ft = lambda x, y, **more: dict(pos=tuple(to_world(pp, dict(hips=(0, 0, 1), foot_R=dict(pos=(x, y, 0.0))), R.spot, face_r)["foot_R"]["pos"]), **more)
    R.keyed([(F0 + 12, on(watch), "inout"), (SLASH - 10, on(watch), "inout"), (SLASH - 5, on(crouch), "inout"), (SLASH, on(air), "inout"), (SLASH + 5, on(land), "inout"),
             (SLASH + 16, on(skid), "slow_out"), (END - 6, on(stand), "inout"), (END, on(stand), "inout")],
            [("Left", SLASH - 4, SLASH + 4, ft(fL.x + 0.02, fL.y + 1.36, yaw=face_r + 34, pitch=0), 0.16),
             ("Right", SLASH - 3, SLASH + 5, ft(fR.x - 0.02, fR.y + 1.32, yaw=face_r - 8, pitch=0), 0.14),
             ("Left", SLASH + 5, SLASH + 16, ft(fL.x + 0.02, fL.y + FAR + 0.04, yaw=face_r + 34, slide=True), 0.0),
             ("Right", SLASH + 5, SLASH + 16, ft(fR.x - 0.02, fR.y + FAR, yaw=face_r - 8, slide=True), 0.0)], "ronin_leap")
    for key in "RL":
        for f, name in ((F0 + 12, "ready"), (SLASH - 10, "ready"), (SLASH - 5, "back"), (SLASH, "wings"), (END, "wings")):
            R.tracks[key].append(dict(f=f, space="chest", m=R.K[name][key], ease="inout"))
    R.spot = tuple(Vector(R.spot) + (rot(Z, face_r) @ Vector((0.0, FAR, 0.0))).to_2d())
    # --- the Oni
    A, pp, K = O.A, O.pp, O.K
    g = A.swords["main"].spec["grip"]
    face = O.face
    fr, fl = _local(O, foot_xy(O.last, "Right")), _local(O, foot_xy(O.last, "Left"))
    y = fr.y
    here = lambda pose: to_world(pp, pose, O.spot, face)
    coil = dict(hips=(0.0, y + 0.42, 0.94), hips_rot=(-28, 4, 0), chest_rot=(-50, 6, 0), head_rot=(-4, 2, 0),       # wound up to his right, eyes on the Ronin,
                hand_L=dict(rel=(0.28, -0.12, -0.34)))                                                                # the empty hand held out before him
    coil2 = dict(coil, hips=(0.0, y + 0.44, 0.92), chest_rot=(-54, 7, 0))
    O.keyed([(F0 + 12, here(coil), "inout"), (CHARGE, here(coil2), "inout")], [], "oni_coil")
    # where he must stand for the point of his blade to pass in front of the Ronin's chest
    out_L = dict(rel=(0.30, 0.12, -0.34))                            # the free arm out behind him against the swing
    hit = dict(hips=(0.0, 0.20, 0.92), hips_rot=(4, 8, 0), chest_rot=(6, 6, 0), head_rot=(0, 6, 0), hand_L=out_L)    # the cut half way: square to the Ronin
    thru = dict(hips=(0.0, 0.12, 0.90), hips_rot=(30, 9, 0), chest_rot=(56, 8, 0), head_rot=(20, 6, 0), hand_L=out_L)  # the cut home: turned right round to his left
    T = R.frame(SLASH) @ Vector((0.0, -0.30, 1.38))
    tip = rot(Z, face) @ (A._spine(pp.canon(hit))["chest"] @ K["sweep2"] @ Vector(A.swords["main"].arc(0.78)))
    spot = (T.x - tip.x, T.y - tip.y)                                # his front foot stands on (fr.x, 0) of this frame
    O.note["power: point of the blade against the Ronin's chest height"] = (round(tip.z, 2), round(T.z, 2))
    there = lambda pose: to_world(pp, pose, spot, face)
    run_end = there(dict(hips=(0.0, 0.62, 0.95)))["hips"]
    run, k = _fit_run(pp, O.last, (run_end.x, run_end.y), PLANT - CHARGE, "Left", speed=0.9)
    O.add(run)
    O.note["power: stride"] = k
    foot = lambda p, **more: dict(pos=tuple(there(dict(hips=(0, 0, 1), foot_R=dict(pos=(p[0], p[1], 0.0))))["foot_R"]["pos"]), **more)
    guard = dict(hips=(0.0, 0.35, 1.00), hips_rot=(8, 4, 0), chest_rot=(3, 9, 0), head_rot=(0, 6, 0))
    O.keyed([(SLASH - 2, there(dict(hit, hips=(0.0, 0.30, 0.92), hips_rot=(-14, 8, 0), chest_rot=(-26, 10, 0))), "slow_out"), (SLASH, there(hit), "linear"),
             (SLASH + 5, there(thru), "slow_out"), (SLASH + 14, there(dict(thru, hips=(0.0, 0.14, 0.88))), "inout"), (END - 4, there(guard), "inout"), (END, there(guard), "inout")],
            [("Right", PLANT, SLASH - 2, foot((fr.x, 0.0), yaw=face, pitch=0), 0.05),
             ("Left", SLASH - 2, SLASH + 2, dict(pitch=22), 0.0),
             ("Left", SLASH + 16, SLASH + 23, foot((fl.x, 0.60), yaw=face + 38, pitch=0), 0.04)], "oni_great_cut")
    O.spot = spot
    for f, name, e in ((F0 + 12, "wind", "inout"), (SLASH - 4, "wind", "inout"), (SLASH - 2, "sweep1", "slow_in"), (SLASH, "sweep2", "linear"), (SLASH + 2, "sweep3", "linear"),
                       (SLASH + 5, "sweep4", "slow_out"), (SLASH + 14, "sweep4", "inout"), (END - 4, "guard", "inout"), (END, "guard", "inout")):
        O.at("main", f, K[name], ease=e)
    for h in O.holds:                                                # one hand for this cut; the left comes back to the grip afterwards
        if h["hand"] == "Left" and h.get("on") != "saya" and h["f1"] >= F0:
            h["f1"], h["blend_out"], h["free_blend"] = F0 + 3, 7, True
    O.holds.append(dict(sword="main", hand="Left", f0=END - 5, f1=FOREVER, along=g - 0.062, roll=-28, lead=False, blend_in=10, free_blend=True))
    EVENTS.append(dict(kind="flame", f0=F0 + 8, f1=SLASH + 16, peak=SLASH))
    EVENTS.append(dict(kind="tear", f=SLASH + 1))
    EVENTS.append(dict(kind="splash", f=SLASH - 2, at=foot_xy(O.take.c[SLASH], "Right"), power=1.3, toward=(0.0, 1.0, 0.0)))
    EVENTS.append(dict(kind="splash", f=SLASH + 5, at=foot_xy(R.take.c[SLASH + 5], "Right"), power=1.0, toward=(0.0, 1.0, 0.0)))
    EVENTS.append(dict(kind="skid", who="ronin", f0=SLASH + 5, f1=SLASH + 16))
    return END


def _crossing(O, R):
    """24-27 s. They set themselves, run at each other and cut as they pass, each with the other on his
    right: the blades meet between them. They run out the cut and stop two strides on, back to back.
    Seen from the side they pass through one line; in depth there is a sword's length between them."""
    assert len(O) - 1 == G0 == len(R) - 1
    PLANT = CROSS + 9                                                # the last running stride of each
    HOLD = PLANT + 8                                                 # both are still
    SIDE, LANE = 0.65, 0.88                                          # each steps this far to his left first; and ends this far left of the line between them
    APART = 1.26                                                     # how far short of each other they are when the blades meet
    ALONG = 0.50
    po, pr = O.last["hips"], R.last["hips"]
    mid = Vector(((po.x + pr.x) * 0.5, (po.y + pr.y) * 0.5, 0.0))
    north = Vector((pr.x - po.x, pr.y - po.y, 0.0)).normalized()     # from the Oni to the Ronin
    west = Vector((-north.y, north.x, 0.0))                          # the Oni's left
    ends = dict(oni=mid + west * LANE + north * 1.0, ronin=mid - west * LANE - north * 1.0)        # where each plants his last stride: a metre past the middle
    cast = ((O, "oni", "Left", west), (R, "ronin", "Right", -west))
    faces = {}
    for P, who, front, left in cast:                                 # a step to the side, eyes on each other
        pp = P.pp
        to = ends[who]
        stand = (P.last["hips"].x + left.x * SIDE, P.last["hips"].y + left.y * SIDE)
        d = Vector((to.x - stand[0], to.y - stand[1], 0.0)).normalized()
        faces[who] = math.degrees(math.atan2(d.x, -d.y))
        if who == "oni":
            set_ = dict(hips=(0.0, 0.0, 0.93), hips_rot=(-10, 8, 0), chest_rot=(-16, 12, 0), head_rot=(0, 4, 0), hand_L=dict(rel=(0.26, -0.04, -0.38)))
        else:
            set_ = dict(hips=(0.0, 0.0, 0.84), hips_rot=(8, 8, 0), chest_rot=(12, 12, 0), head_rot=(0, 4, 0))
        sl = lambda tag, P=P, left=left: tuple(foot_xy(P.last, tag) + left * SIDE)
        P.keyed([(G0 + 11, to_world(pp, set_, stand, P.face), "inout")],
                [("Left", G0 + 1, G0 + 7, dict(pos=sl("Left")), 0.05), ("Right", G0 + 5, G0 + 11, dict(pos=sl("Right")), 0.05)], who + "_set")
    # when they start to run decides how far apart they are when the blades are due to meet: take the start that fits best
    best = None
    for rush in range(G0 + 11, CROSS - 4):
        runs = {who: _fit_run(P.pp, P.last, (ends[who].x, ends[who].y), PLANT - rush, front, speed=0.9) for P, who, front, left in cast}
        a_, b_ = runs["oni"][0].c[CROSS - rush]["hips"], runs["ronin"][0].c[CROSS - rush]["hips"]
        apart = Vector((b_.x - a_.x, b_.y - a_.y, 0.0)).dot(north)
        if best is None or abs(apart - APART) < best[0]:
            best = (abs(apart - APART), rush, runs)
    rush, runs = best[1], best[2]
    O.note["crossing: they start to run on take frame"] = rush
    for P, who, front, left in cast:
        pp = P.pp
        to, face = ends[who], faces[who]
        if rush > len(P) - 1:
            P.keyed([(rush, dict(P.last), "inout")], [], who + "_wait")
        P.add(runs[who][0])
        P.note[f"crossing: {who} stride"] = runs[who][1]
        here = lambda pose, to=to, face=face, pp=pp: to_world(pp, pose, (to.x, to.y), face)
        if who == "oni":
            stop = dict(hips=(0.0, -0.62, 0.84), hips_rot=(-12, 13, 0), chest_rot=(-24, 20, 0), head_rot=(-6, 12, 0), hand_L=dict(rel=(0.26, 0.10, -0.38)))
            P.keyed([(PLANT + 6, here(stop), "slow_out"), (HOLD, here(dict(stop, hips=(0.0, -0.64, 0.83))), "inout"), (J0, here(dict(stop, hips=(0.0, -0.64, 0.83))), "inout")],
                    [("Right", PLANT, PLANT + 5, dict(pos=tuple(here(dict(stop, foot_R=dict(pos=(-0.13, -0.90, 0.0))))["foot_R"]["pos"]), yaw=face, pitch=0), 0.05),
                     ("Left", PLANT + 3, PLANT + 7, dict(pitch=24), 0.0)], "oni_stops")
        else:
            stop = dict(hips=(0.0, -0.52, 0.76), hips_rot=(10, 14, 0), chest_rot=(20, 23, 0), head_rot=(6, 15, 0))       # low over the front knee, head bowed under the hat
            P.keyed([(PLANT + 6, here(stop), "slow_out"), (HOLD, here(dict(stop, hips=(0.0, -0.54, 0.75))), "inout"), (J0, here(dict(stop, hips=(0.0, -0.54, 0.75))), "inout")],
                    [("Left", PLANT, PLANT + 5, dict(pos=tuple(here(dict(stop, foot_L=dict(pos=(0.12, -0.84, 0.0))))["foot_L"]["pos"]), yaw=face, pitch=0), 0.05),
                     ("Right", PLANT + 3, PLANT + 7, dict(pitch=24), 0.0)], "ronin_stops")
        P.spot, P.face = (to.x, to.y), face
    # swords: the Oni's leads, the Ronin's right blade is laid on it at the crossing
    K, RK = O.K, R.K
    for f, name, e in ((G0 + 9, "pass1", "inout"), (CROSS - 3, "pass1", "inout"), (CROSS, "pass2", "slow_in"), (CROSS + 1, "pass2b", "linear"), (CROSS + 4, "pass3", "slow_out"),
                       (PLANT + 2, "pass3", "inout"), (HOLD, "held", "inout"), (J0, "held", "inout")):
        O.at("main", f, K[name], ease=e)
    for h in O.holds:
        if h["hand"] == "Left" and h.get("on") != "saya" and h["f1"] >= G0:
            h["f1"], h["blend_out"], h["free_blend"] = G0 + 2, 6, True
    tr = R.tracks
    tr["R"] += [dict(f=G0 + 4, space="chest", m=RK["sweep"]["R"], ease="inout"),                       # round the front, not through himself
                dict(f=G0 + 9, space="chest", m=RK["across"]["R"], ease="inout"), dict(f=CROSS - 3, space="chest", m=RK["across"]["R"], ease="inout")]
    used = _lay(R, O, "R", CROSS, ALONG, (-0.46, -0.34, 1.40), (0.7, 0.7, 0.0), ease="slow_in")
    tr["R"] += [dict(f=CROSS + 3, space="chest", m=RK["back"]["R"], ease="slow_out"), dict(f=J0, space="chest", m=RK["back"]["R"], ease="inout")]
    tr["L"] += [dict(f=G0 + 8, space="chest", m=RK["back"]["L"], ease="inout"), dict(f=PLANT, space="chest", m=RK["back"]["L"], ease="inout"),
                dict(f=HOLD, space="chest", m=RK["wings"]["L"], ease="inout"), dict(f=J0, space="chest", m=RK["wings"]["L"], ease="inout")]
    a, b = O.take.c[CROSS]["hips"], R.take.c[CROSS]["hips"]
    sep = Vector((b.x - a.x, b.y - a.y, 0.0))
    R.note["crossing: apart along the run, apart in depth, blade used from the fist"] = (round(sep.dot(north), 2), round(abs(sep.dot(west)), 2), round(used, 2))
    EVENTS.append(dict(kind="clash", f=CROSS, at=O.on_blade("main", CROSS, ALONG), power=1.6, blades=(("oni", "main", ALONG), ("ronin", "R", None))))
    for P_, tag in ((O, "Right"), (R, "Left")):
        EVENTS.append(dict(kind="splash", f=PLANT + 5, at=foot_xy(P_.take.c[PLANT + 6], tag), power=1.2, toward=tuple(north if P_ is O else -north)))
    return J0


def _aftermath(O, R):
    """27-30 s. Neither moves. The Ronin's hat parts down the middle and the halves fall; a crack runs
    across the Oni's mask. Only their breathing shows."""
    assert len(O) - 1 == J0 == len(R) - 1
    for P in (O, R):
        base = P.last
        keys = []
        for i, f in enumerate(range(J0 + 12, END + 1, 12)):
            c = dict(base)
            c["hips"] = base["hips"] + Vector((0.0, 0.0, 0.006 if i % 2 == 0 else 0.0))
            c["chest_D"] = base["chest_D"] @ rot((1, 0, 0), -1.2 if i % 2 == 0 else 0.0)
            keys.append((f, c, "inout"))
        if keys[-1][0] != END:
            keys.append((END, dict(base), "inout"))
        P.keyed(keys, [], "still")
        for key in P.tracks:
            last = max(P.tracks[key], key=lambda k: k["f"])
            P.tracks[key].append(dict(last, f=END))
    EVENTS.append(dict(kind="hat_split", f=SPLIT))
    EVENTS.append(dict(kind="mask_crack", f=CRACK))
    return END


FOREVER = 10 ** 6                                    # a hold that lasts until something ends it

BEATS = [_dash, _hammer, _counter, _trade, _power, _crossing, _aftermath]


def fight(cast, beats=None):
    """Both fighters' whole parts: the intro, then the fight beat by beat.
    Returns {who: (take, sword tracks, holds, scabbard steering)}; EVENTS says what happens when."""
    EVENTS.clear()
    O = Part(cast["oni"], *oni_intro(cast["oni"]))
    R = Part(cast["ronin"], *ronin_intro(cast["ronin"]))
    O.K, R.K = _oni_stations(cast["oni"]), _ronin_stations(cast["ronin"])
    R.S = RONIN_STANCE
    O.note, R.note = {}, {}
    for P in (O, R):
        for h in P.holds:                                            # hands that were on the grips at the end of the intro stay there
            if "sword" in h and h.get("on") != "saya" and h["f1"] >= len(P.take):
                h["f1"] = FOREVER
    for beat in (BEATS if beats is None else BEATS[:beats]):
        beat(O, R)
    return dict(oni=O.result(), ronin=R.result()), dict(O.note, **R.note)


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

    def facing(A, ff):                                               # the way a fighter's chest faces on a film frame, in degrees
        f = min(A.frames - 1, max(0, int(round(take_time(ff)))))
        d = (A.arm.matrix_world.to_3x3() @ A.poses[f]["D"]["Spine2"]) @ Vector((0.0, -1.0, 0.0))
        return math.degrees(math.atan2(d.x, -d.y))

    oni_face, ronin_face = (lambda ff: facing(oni, ff)), (lambda ff: facing(ronin, ff))

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

    # ------------------------------------------------------------------ the fight
    hips = lambda A, ff: joint(A, "Hips", ff)
    head = lambda A, ff: joint(A, "Head", ff)
    both = lambda ff: (hips(oni, ff) + hips(ronin, ff)) * 0.5
    flat = lambda v, z: Vector((v.x, v.y, z))

    def polar(centre, azimuth, radius, height):                      # azimuth as for the studio cameras: 0 = from the south, 90 = from the east
        a = math.radians(azimuth)
        return Vector((centre.x + math.sin(a) * radius, centre.y - math.cos(a) * radius, height))

    # 10 s: the dash. Each is followed low and from the side for a few strides, then the clash side on, slowed down
    def dash_oni(ff):
        h = hips(oni, ff)
        return dict(pos=flat(h, 0.0) + Vector((3.1, 1.5, 0.55)), look=flat(h, 1.15) + Vector((0, 0.4, 0)), lens=32.0, hand=0.012)
    add("S04a the Oni runs", 241, 251, dash_oni)

    def dash_ronin(ff):
        h = hips(ronin, ff)
        return dict(pos=flat(h, 0.0) + Vector((-2.9, -1.6, 0.60)), look=flat(h, 1.10) + Vector((0, -0.4, 0)), lens=32.0, hand=0.012)
    add("S04b the Ronin runs", 252, 262, dash_ronin)

    def clash(ff):
        u = _smooth((ff - 263) / 25.0)
        return dict(pos=_mix((3.7, 1.70, 0.95), (3.1, 1.80, 1.12), u), look=(-0.05, 1.88, 1.40), lens=30.0)
    add("S04c the clash", 263, 288, clash)

    # 12 s: the three cuts, the camera circling from the east round behind the Oni's shoulder
    def orbit(ff):
        u = (ff - 289) / 71.0
        c = both(ff)
        return dict(pos=polar(c, 90.0 - 68.0 * _smooth(u), 4.3 - 0.6 * u, 1.55 - 0.40 * u), look=flat(c, 1.30), lens=32.0, hand=0.006)
    add("S05 three cuts", 289, 360, orbit)

    # 15 s: the slip, the spin and the kick from the south-west; then low behind the Oni as he is thrown back toward the lens
    def spin(ff):
        u = (ff - 361) / 37.0
        c = both(ff)
        return dict(pos=polar(c, -62.0 - 14.0 * u, 4.0, 1.25), look=flat(c, 1.25), lens=35.0, hand=0.008)
    add("S06a spin and kick", 361, 398, spin)

    def thrown(ff):
        end = hips(oni, 432)
        return dict(pos=Vector((end.x + 1.5, end.y - 2.7, 0.34)), look=flat(both(ff), 0.95), lens=28.0)
    add("S06b thrown back", 399, 432, thrown)

    # 18 s: the exchange, hand-held, a new angle for every blow
    def trade_a(ff):
        o = hips(oni, ff)
        return dict(pos=flat(o, 0.0) + Vector((1.5, -1.7, 1.50)), look=flat(both(ff), 1.40), lens=38.0, hand=0.022)
    add("S07a first blow", 433, 445, trade_a)

    def trade_b(ff):
        c = both(ff)
        return dict(pos=flat(c, 0.0) + Vector((-3.6, 0.4, 0.85)), look=flat(c, 1.38), lens=32.0, hand=0.022)
    add("S07b second blow", 446, 465, trade_b)

    def trade_c(ff):
        r = hips(ronin, ff)
        return dict(pos=flat(r, 0.0) + Vector((1.3, 1.9, 1.55)), look=flat(both(ff), 1.20), lens=38.0, hand=0.022)
    add("S07c third blow", 466, 485, trade_c)

    def trade_d(ff):
        c = both(ff)
        return dict(pos=Vector((5.4, c.y, 1.0)), look=flat(c, 1.15), lens=30.0, hand=0.012)
    add("S07d apart", 486, 504, trade_d)

    # 21 s: the Oni winds up, seen low from in front; the cut from the side; then over the Ronin's shoulder
    def wind(ff):
        u = _smooth((ff - 505) / 23.0)
        o = hips(oni, ff)
        return dict(pos=flat(o, 0.0) + _mix((1.5, 2.6, 0.50), (1.2, 2.1, 0.58), u), look=flat(o, 1.35), lens=40.0)
    add("S08a the Oni winds up", 505, 528, wind)

    def great(ff):
        c = both(ff)
        o = hips(oni, ff)
        return dict(pos=Vector((5.2, c.y, 1.05)), look=flat(_mix(o, c, 0.6), 1.15), lens=28.0, hand=0.008)
    add("S08b the great cut", 529, 549, great)

    def torn(ff):
        r = hips(ronin, ff)
        return dict(pos=flat(r, 0.0) + Vector((-1.5, 1.9, 1.60)), look=flat(_mix(r, hips(oni, ff), 0.5), 1.15), lens=35.0, hand=0.006)
    add("S08c the cape", 550, 576, torn)

    # 24 s: the last pass, side on and wide; at the crossing nearer and slowed down; then both still, back to back
    def last_a(ff):
        c = both(ff)
        return dict(pos=Vector((4.9, c.y, 0.80)), look=flat(c, 1.20), lens=30.0)
    add("S09a they set themselves", 577, 595, last_a)

    def last_b(ff):
        c = both(604)
        u = _smooth((ff - 596) / 27.0)
        return dict(pos=_mix((5.2, c.y, 0.95), (4.7, c.y, 1.0), u), look=flat(c, 1.20), lens=35.0)
    add("S09b the crossing", 596, 623, last_b)

    def last_c(ff):
        c = both(648)
        u = _smooth((ff - 624) / 24.0)
        return dict(pos=_mix((4.5, c.y, 0.62), (4.75, c.y, 0.60), u), look=flat(c, 1.20), lens=28.0)
    add("S09c back to back", 624, 648, last_c)

    # 27 s: the Ronin's hat, seen from in front of him with the moon behind; the Oni's mask; black
    def hat_falls(ff):
        h = head(ronin, 660)
        f_ = _along(ronin_face(660))
        u = _smooth((ff - 649) / 35.0)
        return dict(pos=h + f_ * (1.75 - 0.15 * u) + Vector((-f_.y, f_.x, 0.0)) * 0.45 + Vector((0, 0, -0.22)), look=h + Vector((0, 0, 0.04)), lens=58.0)
    add("S10a the hat", 649, 684, hat_falls)

    def mask_cracks(ff):
        h = head(oni, 700)
        f_ = _along(oni_face(700))
        u = _smooth((ff - 685) / 35.0)
        return dict(pos=h + f_ * (1.25 - 0.12 * u) + Vector((-f_.y, f_.x, 0.0)) * -0.38 + Vector((0, 0, -0.05)), look=h + Vector((0, 0, 0.02)), lens=80.0)
    add("S10b the mask", 685, 720, mask_cracks)
    return out


def shot_at(shots_, film_frame):
    for sh in shots_:
        if sh["first"] <= film_frame <= sh["last"]:
            return sh
    return shots_[-1]


# when each fighter is in the film at all: before that he is not rendered (he waits where a camera could see him)
ENTERS = dict(oni=73, ronin=145)


def film_of(take_frame):
    """The first film frame that shows a take frame."""
    for a, b, t0, rate in TIME:
        if rate > 0.0 and t0 <= take_frame <= t0 + (b - a) * rate + 1e-6:
            return a + int(math.ceil((take_frame - t0) / rate - 1e-6))
        if rate == 0.0 and abs(t0 - take_frame) < 1e-6:
            return a
    return TIME[-1][1]


def _wobble(t, seed):
    return (math.sin(t * 1.7 + seed * 12.9) + 0.6 * math.sin(t * 3.1 + seed * 7.3) + 0.35 * math.sin(t * 5.3 + seed * 3.7)) / 1.95


def shake(film_frame, hand=0.0):
    """How far the camera and the point it looks at are off their marks on a film frame (two vectors,
    metres): the drift of a hand-held camera, and a jolt from every blow that has just landed. It
    runs in film frames, so the jolt goes on through the frames a blow is held for."""
    t = film_frame / 24.0
    pos = Vector((_wobble(t * 5.0, 1), _wobble(t * 5.0, 2), _wobble(t * 5.0, 3))) * hand
    look = Vector((_wobble(t * 6.3, 4), _wobble(t * 6.3, 5), _wobble(t * 6.3, 6))) * hand * 1.6
    for ev in EVENTS:
        if ev["kind"] not in ("clash", "kick"):
            continue
        age = film_frame - film_of(ev["f"])
        if 0 <= age < 12:
            k = 0.030 * ev.get("power", 1.0) * math.exp(-age / 2.6)
            pos += Vector((_wobble(film_frame * 2.3, 7), _wobble(film_frame * 2.9, 8), _wobble(film_frame * 3.7, 9))) * k
            look += Vector((_wobble(film_frame * 3.1, 10), _wobble(film_frame * 2.7, 11), _wobble(film_frame * 4.1, 12))) * k * 1.5
    return pos, look


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
