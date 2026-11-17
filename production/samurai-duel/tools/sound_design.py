"""The film's sound (v2): effects laid to the picture from the film's own code (out/sound/events.json,
made by tools/sound_events.py), a score with a trailer's grammar on Japanese drums, mixed and
mastered; the same sounds re-cut for the teaser. Everything is synthesized (sd/audio2.py, built to
sound recorded: steel from a blade's modes, thuds through real resonances, stick-slip scrapes,
drummers on membranes, the courtyard's reflections): no recordings, nothing borrowed.
v1 (sd/audio.py) is in the history.

    python3 -I tools/sound_design.py film   [--video previews/stage4_film_v3.mp4] [--out previews/stage4_film_v3_sound.mp4]
    python3 -I tools/sound_design.py teaser [--src previews/stage4_teaser_v3] [--tag _sound_v2]

film writes the mastered track (out/sound/film_master.wav), its stems, the cue sheet and the music map
(out/sound/), and the video with the track. teaser does the same for both teaser shapes
(<src>_<shape><tag>.mp4, --tag default _sound_v2).

Sync: film frame f is on screen from (f - 1) / 24 s. A hit's loudest moment is put on the frame the
blow lands; a swing follows its blade (the whoosh is as loud as the point is fast, slowed with the
picture); feet sound on the frames they come down; sounds sit left or right as their fighter does in
the shot, and nearer sounds are louder.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from sd import audio2 as A  # noqa: E402
from sd import samples as SM  # noqa: E402

SR, FPS = A.SR, 24
SPF = SR // FPS                                                     # samples per film frame (2000)
OUT = os.path.join(HERE, "out", "sound")
STEMS = ("amb", "foley", "sfx", "elem", "music")
NOTE = dict(A1=55.0, E2=82.41, A2=110.0, B2=123.47, C3=130.81, E3=164.81, F3=174.61, A3=220.0, B3=246.94, C4=261.63,
            E4=329.63, F4=349.23, A4=440.0, B4=493.88, C5=523.25, E5=659.26, F5=698.46, A5=880.0)


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def T(ff):
    return (ff - 1) / FPS


def db(x):
    return 10.0 ** (x / 20.0)


# ----------------------------------------------------------------------------- the picture, as data
class Film:
    def __init__(self, path):
        with open(path) as fh:
            D = json.load(fh)
        self.D, self.F = D, D["frames"]
        self.ev = D["events"]
        self.n = len(self.F)

    def fr(self, ff):
        return self.F[min(self.n, max(1, ff)) - 1]

    def rate(self, ff):
        return self.fr(ff)["rate"]

    def screen(self, ff, p):
        """x in the picture (-1 left .. 1 right), distance, in front of the camera: for a world point."""
        c = self.fr(ff)["cam"]
        pos, look = np.array(c["pos"]), np.array(c["look"])
        fwd = look - pos
        fwd /= np.linalg.norm(fwd)
        right = np.cross(fwd, [0.0, 0.0, 1.0])
        right /= np.linalg.norm(right)
        d = np.array(p) - pos
        z = float(d @ fwd)
        return float(np.clip((d @ right) / max(z, 1e-3) / (18.0 / c["lens"]), -1.5, 1.5)), float(np.linalg.norm(d)), z > 0.0

    def pan(self, ff, who=None, p=None):
        if p is None:
            s = self.fr(ff)[who]["screen"]
            x, front = s["x"], s["front"]
        else:
            x, _, front = self.screen(ff, p)
        return float(np.clip(x * 0.7, -0.75, 0.75)) if front else 0.0

    def near(self, ff, who=None, p=None):
        """dB for how close a fighter (or a point) is to the camera, and whether he is in the picture."""
        if p is None:
            s = self.fr(ff)[who]["screen"]
            x, dist, front = s["x"], s["dist"], s["front"]
        else:
            x, dist, front = self.screen(ff, p)
        g = float(np.clip(20.0 * math.log10(2.5 / max(dist, 1.0)), -10.0, 4.0))
        if not front or abs(x) > 1.15:
            g -= 6.0
        return g

    def tips(self, who, key):
        return np.array([f[who]["tips"][key] for f in self.F])

    def joint(self, who, j):
        return np.array([f[who]["joints"][j] for f in self.F])


def per_sample(vals, n):
    """Values given per film frame (frame f at its centre) to one per sample."""
    vals = np.asarray(vals, dtype=float)
    centres = (np.arange(len(vals)) + 0.5) * SPF
    return np.interp(np.arange(n), centres, vals)


def take_speed(film, P):
    """Speed (m/s, in the take's own time) of a point given per film frame; 0 while a blow is held."""
    rate = np.array([f["rate"] for f in film.F])
    take = np.array([f["take"] for f in film.F])
    dt = np.r_[1.0, np.diff(take)]                                  # take frames between this film frame and the last
    d = np.r_[0.0, np.linalg.norm(np.diff(P, axis=0), axis=1)] * FPS
    v = np.where((dt > 1e-3) & (dt < 2.0), d / np.maximum(dt, 1e-3), 0.0)   # held: still; a jump in the time map: not a move
    v[0] = v[1]
    cuts = {s["first"] for s in film.D["shots"]}
    return np.clip(v, 0.0, 60.0), rate, cuts


# ----------------------------------------------------------------------------- the mix
class Mix:
    def __init__(self, seconds):
        self.n = A.n_of(seconds)
        self.stems = {k: np.zeros((self.n, 2), np.float32) for k in STEMS}
        self.cues = []

    def add(self, stem, t, x, gain_db=0.0, pan=0.0, name="", kind="", width=0.0, room=None, wet=0.2, log=True, ff=None):
        if x.ndim == 1:
            x = A.stereo(x, pan, width)
        if room:
            x = A.room(x, room, wet)
        i = int(round(t * SR))
        if i < 0:
            x, i = x[-i:], 0
        e = min(self.n, i + len(x))
        if e > i:
            self.stems[stem][i:e] += x[:e - i] * db(gain_db)
        if log:
            self.cues.append(dict(t=t, ff=ff if ff is not None else int(round(t * FPS)) + 1, stem=stem, name=name, kind=kind, db=gain_db, pan=pan))

    def layer(self, stem, x, gain_db=0.0, name="", kind=""):
        n = min(self.n, len(x))
        if x.ndim == 1:
            x = A.stereo(x)
        self.stems[stem][:n] += x[:n] * db(gain_db)
        self.cues.append(dict(t=0.0, ff=1, stem=stem, name=name, kind=kind, db=gain_db, pan=0.0, layer=True))

    def duck(self, stems, t0, t1, by_db, ramp=0.012):
        g = np.ones(self.n, np.float32)
        a, b, r = int(t0 * SR), int(t1 * SR), int(ramp * SR)
        lo = db(by_db)
        g[max(0, a - r):a] = np.linspace(1.0, lo, len(g[max(0, a - r):a]))
        g[a:b] = lo
        g[b:b + r] = np.linspace(lo, 1.0, len(g[b:b + r]))
        for s in stems:
            self.stems[s] *= g[:, None]


# ----------------------------------------------------------------------------- real recordings
BANK = SM.Bank()
USED = set()                                                        # recordings that went into the mix (for the credits)
REAL = "--synth" not in sys.argv and all(os.path.exists(os.path.join(SM.ROOT, f"{i}.wav")) for i in SM.ids())


def rec(role, k, speed=1.0, seconds=None, mono=True):
    """A real recording for a role, variant k: (sound, seconds before its attack). Mono for a point
    source (Mix.add pans it), stereo for a bed or a hit that fills the screen."""
    x, pre = BANK.one(role, k, speed=speed, seconds=seconds)
    USED.add(BANK.pick(role, k))
    return (x.mean(axis=1).astype(np.float32) if mono else x), pre


def rec_into(role, k, at_peak, seconds_before, after=0.4, mono=False):
    """A recording that builds to its loudest moment (a riser, a roll), cut to start 'seconds_before' its
    peak and end 'after' past it; returns (sound, seconds from its start to the peak)."""
    i = BANK.pick(role, k)
    USED.add(i)
    x = BANK.get(i)
    pk = SM.peak_of(x)
    a = max(0, pk - int(seconds_before * SR))
    y = x[a:pk + int(after * SR)].copy()
    f = min(len(y), int(0.08 * SR))
    y[:f] *= np.linspace(0.0, 1.0, f)[:, None]
    g = min(len(y), int(0.1 * SR))
    y[len(y) - g:] *= np.linspace(1.0, 0.0, g)[:, None]
    return (y.mean(axis=1).astype(np.float32) if mono else y), (pk - a) / SR


_DRUMS = {}


def drum_hits(kind):
    """Single drum hits cut from the tribal drum recordings: low ones play the o-daiko, middle ones the nagado."""
    if not _DRUMS:
        lo, mid = [], []
        for i in (567, 575, 574):
            for h, _ in BANK.hits(i, keep_db=12.0, longest=1.2):
                m = h.mean(axis=1)
                X = np.abs(np.fft.rfft(m)) ** 2
                c = float((np.fft.rfftfreq(len(m), 1 / SR) * X).sum() / X.sum())
                (lo if c < 115.0 else mid if c < 400.0 else []).append(m.astype(np.float32))
            USED.add(i)
        _DRUMS["o"], _DRUMS["nagado"] = lo, mid
    return _DRUMS[kind]


def ens(kind="o", vel=1.0, players=1, seed=0, spread=0.5):
    """Drummers on one beat (stereo): real drum hits (a different one for each player, each a hair early or
    late) with the synthesized membrane under them for the long body; shime and rim stay synthesized."""
    synth = A.taiko_ens(kind, vel, players, seed=seed, spread=spread) if players > 1 else A.stereo(A.taiko(kind, vel, seed=seed))
    if not REAL or kind not in ("o", "nagado"):
        return synth
    hs = drum_hits(kind)
    r = np.random.default_rng(seed)
    parts = []
    for p in range(players):
        h = hs[int(r.integers(len(hs)))] * float(np.clip(vel, 0.1, 1.2))
        pan = 0.0 if players == 1 else (p / (players - 1) - 0.5) * 2.0 * spread
        parts.append(A.stereo(np.pad(h, (int(r.uniform(0.0, 0.012) * SR), 0)), pan))
    out = np.zeros((max(max(len(q) for q in parts), len(synth)), 2), np.float32)
    for q in parts:
        out[: len(q)] += q / players ** 0.5
    out[: len(synth)] += synth * db(-6.0)
    return out


def heart(k=0):
    """A heartbeat: recorded, or the modelled lub-dub."""
    if not REAL:
        return A.heartbeat(seed=k)
    x, pre = rec("heart", 0, seconds=0.9)                           # the single beat (490); 498 is a cinematic boom
    return x[int(pre * SR):]


def fade_both(x, fin, fout):
    y = x.copy()
    a, b = min(len(y), int(fin * SR)), min(len(y), int(fout * SR))
    y[:a] *= (np.linspace(0.0, 1.0, a)[:, None] if y.ndim == 2 else np.linspace(0.0, 1.0, a))
    y[len(y) - b:] *= (np.linspace(1.0, 0.0, b)[:, None] if y.ndim == 2 else np.linspace(1.0, 0.0, b))
    return y


def big_hit(seconds=3.0, seed=0, k=0):
    """The trailer's big hit: a real cinematic impact on top, the synthesized one (drums, slam, sub, crash) under it."""
    synth = A.trailer_hit(seconds, seed=seed)
    if not REAL:
        return synth
    x, pre = rec("impact", k, seconds=seconds, mono=False)
    x = A.hp(x[int(pre * SR):], 35.0)                                # (under 35 Hz it only takes headroom)
    out = np.zeros((max(len(x), len(synth)), 2), np.float32)
    out[: len(x)] += 0.6 * x / (np.abs(x).max() + 1e-9)             # the recorded impact gives the weight ...
    out[: len(synth)] += synth                                       # ... the modelled crash and slam carry it on a phone
    return (out * (0.95 / np.abs(out).max())).astype(np.float32)


def brass(freq=55.0, seconds=2.0, seed=0, k=0):
    """A war horn (real) over the synthesized braam."""
    synth = A.stereo(A.braam(freq, seconds, seed=seed))
    if not REAL:
        return synth
    x, pre = rec("horn", k, seconds=seconds + 0.5, mono=False)
    x = x[int(pre * SR):]
    out = np.zeros((max(len(x), len(synth)), 2), np.float32)
    out[: len(x)] += x
    out[: len(synth)] += synth * db(-6.0)
    return (out * (0.95 / np.abs(out).max())).astype(np.float32)


# ----------------------------------------------------------------------------- the effects
def lay_effects(film, mix):
    E = film.ev
    by = lambda k: [e for e in E if e["kind"] == k]                  # noqa: E731
    seen = lambda who, ff: ff >= film.D["enters"][who]               # noqa: E731

    # --- footfalls: heel and toe on wet stone; the Oni heavier, the Ronin's armoured boot with a clink
    for who in ("oni", "ronin"):
        for k, c in enumerate(film.D["contacts"][who]):
            ff = c["ff"]
            if not seen(who, ff):
                continue
            rate = film.rate(ff)
            run = min(1.0, c["speed"] / 6.0)
            s = A.step(weight=1.45 if who == "oni" else 1.0, seed=k * 7 + (0 if who == "oni" else 1000), wet=0.7,
                       armour=0.0 if who == "oni" else 1.0)
            if 0.0 < rate < 1.0:                                     # slow motion: lower and longer
                s = A.resample_speed(s, rate ** 0.45)
            g = -11.0 + 6.0 * run + min(0.0, film.near(ff, who)) + np.random.default_rng(k).uniform(-1.5, 1.5)
            if c["speed"] < 0.3:                                       # a foot set down in a stance: a scuff, not a step
                s = A.lp(s, 2500).astype(np.float32)
                g -= 7.0
            if REAL:                                                   # a real footfall on stone; the synthesized one under it keeps the body, the plates, the water
                hs = BANK.hits(1270)
                USED.add(1270)
                h = hs[(k * 7 + (0 if who == "oni" else 3)) % len(hs)][0].mean(axis=1)
                sp = (0.86 if who == "oni" else 1.04) * (rate ** 0.45 if 0.0 < rate < 1.0 else 1.0)
                h = A.resample_speed(h, sp)
                if c["speed"] < 0.3:
                    h = A.lp(h, 2500)
                mix.add("foley", T(ff) - 0.005, h.astype(np.float32), g + 1.0, film.pan(ff, who), f"step {who} {c['foot']} (recorded)", "foley", room="court", wet=0.12, ff=ff)
                g -= 7.0
            mix.add("foley", T(ff) - 0.004, s, g, film.pan(ff, who), f"step {who} {c['foot']}" + (" (body, plates, water)" if REAL else ""), "foley", room="court", wet=0.12, ff=ff, log=not REAL)

    # --- swings: each blade's point, as fast as it moves; the Oni's deep, the Ronin's light and quick
    for who, keys in film.D["swords"].items():
        for key in keys:
            v, rate, cuts = take_speed(film, film.tips(who, key))
            I = np.clip((v - 4.0) / 16.0, 0.0, 1.0)
            I[: film.D["enters"][who]] = 0.0
            P = 0.45 + 0.55 * np.sqrt(np.clip(rate, 0.0, 1.0))
            near = np.array([film.near(ff, who) for ff in range(1, film.n + 1)])
            pans = np.array([film.pan(ff, who) for ff in range(1, film.n + 1)])
            lvl = per_sample(I ** 1.6 * np.minimum(1.0, db(near)), mix.n)          # never louder than full: the hits stay on top
            if who == "oni":
                cen = per_sample((180.0 + 1300.0 * I) * P, mix.n)
                w = A.whoosh(lvl, cen, seed=sum(map(ord, key)) % 97, kind="deep")
            else:
                cen = per_sample((420.0 + 2900.0 * I) * P, mix.n)
                w = A.whoosh(lvl, cen, seed=31 + sum(map(ord, key)) % 97, kind="air")
            w = (np.tanh(1.6 * w) / 1.6).astype(np.float32)                # noise has tall peaks: round them off
            g = (-15.0 if who == "oni" else -17.0) - (5.0 if REAL else 0.0)   # the Ronin swings two blades at once
            if REAL:                                                     # a recorded swing on each peak of the point's speed, its loudest moment on that frame
                peaks = [f for f in range(1, film.n - 1) if I[f] > 0.45 and I[f] >= I[f - 1] and I[f] > I[f + 1]]
                kept = []
                for f in sorted(peaks, key=lambda f: -I[f]):
                    if all(abs(f - q) >= 6 for q in kept):
                        kept.append(f)
                for j, f in enumerate(sorted(kept)):
                    sp = (0.85 if who == "oni" else 1.0) * (rate[f] ** 0.5 if 0.0 < rate[f] < 1.0 else 1.0)
                    x, _ = rec("swing_heavy" if who == "oni" else "swing_light", j + sum(map(ord, key)), speed=sp)
                    mix.add("sfx", T(f + 1) - SM.peak_of(x) / SR, x, (-14.0 if who == "oni" else -16.0) + 6.0 * (I[f] - 1.0) + min(0.0, near[f]),
                            pans[f], f"swing {who} {key} (recorded)", "motion", ff=f + 1)
            mix.stems["sfx"] += A.pan_track(w, per_sample(pans, mix.n)) * db(g)
            mix.cues.append(dict(t=0.0, ff=1, stem="sfx", name=f"swing {who} {key} (follows the blade's point)", kind="motion", db=g, pan=0.0, layer=True))

    # --- fire on the Oni's blade, water on the Ronin's: with the trails, louder where they are big
    C = film.D["consts"]
    big_o = [(h - 8, h + 1, 1.5) for h in C["HAMMER"]] + [(C["F0"] + 8, C["SLASH"] + 6, 2.0), (C["CROSS"] - 6, C["CROSS"] + 4, 1.7)]
    big_r = [(C["HIT"] - 6, C["HIT"] + 2, 1.4), (C["SPIN"] - 2, C["KICK"], 1.8), (C["CROSS"] - 6, C["CROSS"] + 4, 1.7)]
    take = np.array([f["take"] for f in film.F])
    span = (take >= C["DASH"]) & (take <= C["J0"])
    flame = next((e for e in E if e["kind"] == "flame"), None)
    for who, keys, big, kind in (("oni", ["main"], big_o, "fire"), ("ronin", film.D["swords"]["ronin"], big_r, "water")):
        I = np.zeros(film.n)
        for key in keys:
            v, rate, _ = take_speed(film, film.tips(who, key))
            I = np.maximum(I, np.clip((v - 3.0) / 14.0, 0.0, 1.4))
        w = np.ones(film.n)
        for a, b, k in big:
            w = np.where((take >= a) & (take <= b), np.maximum(w, k), w)
        lvl = np.where(span, (0.06 + 0.4 * np.minimum(I, 1.0)) * w / 2.0, 0.0)
        if kind == "fire" and flame:                                   # once the fire wakes the blade burns on
            lit = (take >= flame["f0_take"]) & (take <= flame["f1_take"])
            lvl = np.where(lit, np.maximum(lvl, 0.4 + 0.45 * np.minimum(I, 1.0)), lvl)
        near = np.array([film.near(ff, who) for ff in range(1, film.n + 1)])
        pans = np.array([film.pan(ff, who) for ff in range(1, film.n + 1)])
        s_lvl = per_sample(np.minimum(1.0, lvl * np.minimum(1.0, db(near))), mix.n)
        x = A.fire_roar(s_lvl, seed=5) if kind == "fire" else A.water_swish(s_lvl, seed=6)
        if kind == "fire" and REAL:                                    # a real flame, as loud as the trail; the modelled roar under it
            fb = BANK.bed("fire_bed", 0, mix.n, level=np.minimum(1.0, s_lvl * 1.6)).mean(axis=1)
            USED.add(BANK.pick("fire_bed", 0))
            mix.stems["elem"] += A.pan_track(fb.astype(np.float32), per_sample(pans, mix.n)) * db(-14.0)
            x = x * db(-6.0)
        mix.stems["elem"] += A.pan_track(x, per_sample(pans, mix.n)) * db(-15.0 if kind == "fire" else -14.0)
        mix.cues.append(dict(t=T(241), ff=241, stem="elem", name=f"{kind} on the {who}'s blade (follows the trail)", kind="aesthetic", db=-15.0 if kind == "fire" else -14.0, pan=0.0, layer=True))

    # --- cloth on both, with the body's and the hands' speed
    for who in ("oni", "ronin"):
        vh, rate, _ = take_speed(film, film.joint(who, "Hips"))
        va = np.maximum(take_speed(film, film.joint(who, "LeftHand"))[0], take_speed(film, film.joint(who, "RightHand"))[0])
        lv = np.clip(0.08 + vh / 7.0 + va / 16.0, 0.0, 1.3) * np.sqrt(np.clip(rate, 0.0, 1.0) + 0.15)
        lv[: film.D["enters"][who]] = 0.0
        near = np.array([film.near(ff, who) for ff in range(1, film.n + 1)])
        pans = np.array([film.pan(ff, who) for ff in range(1, film.n + 1)])
        x = A.cloth(per_sample(lv * db(near), mix.n), seed=11 if who == "oni" else 12)
        mix.stems["foley"] += A.pan_track(x, per_sample(pans, mix.n)) * db(-25.0)
        mix.cues.append(dict(t=0.0, ff=1, stem="foley", name=f"cloth {who} (follows body and hands)", kind="foley", db=-25.0, pan=0.0, layer=True))

    # --- the rush of air on the runs (the speed lines) and the crossing
    vO = take_speed(film, film.joint("oni", "Hips"))[0]
    vR = take_speed(film, film.joint("ronin", "Hips"))[0]
    rate = np.array([f["rate"] for f in film.F])
    run = np.clip((np.maximum(vO, vR) - 3.0) / 5.0, 0.0, 1.0) * (0.4 + 0.6 * np.sqrt(rate))
    run[:240] = 0.0
    lvl = per_sample(run, mix.n)
    x = A.whoosh(lvl, 250.0 + 900.0 * lvl, seed=21, kind="deep")
    mix.stems["sfx"] += A.stereo(x, 0.0, 0.6) * db(-17.0)
    mix.cues.append(dict(t=T(241), ff=241, stem="sfx", name="rush of air on the runs", kind="motion", db=-17.0, pan=0.0, layer=True))

    # --- the blows
    clashes = by("clash")
    for k, e in enumerate(clashes):
        ff, pw = e["ff"], e.get("power", 1.0)
        rate = film.rate(ff)
        slow = rate if 0.0 < rate < 1.0 else 1.0
        p = film.pan(ff, p=e["at"])
        nd = film.near(ff, p=e["at"])
        big = pw >= 1.5 or slow < 1.0
        if slow < 1.0:                                                 # slow motion: a pull toward it, then everything opens out
            mix.add("sfx", T(ff) - 0.85, A.suck_in(0.85, seed=k), -12.0, p, "suck-in", "aesthetic", ff=ff)
        g_hit = -4.0 + 2.0 * (pw - 1.0) + 0.4 * nd
        if REAL:                                                       # the recorded clash on the frame; the modelled blades ring under it
            role = "clash_heavy" if pw >= 1.5 else "clash"
            x, pre = rec(role, k, speed=slow ** 0.5 if slow < 1.0 else 1.0)
            mix.add("sfx", T(ff) - pre, x, g_hit - 2.0, p, f"clash power {pw:.1f}" + (" slow" if slow < 1 else "") + f" (recorded {BANK.pick(role, k)})",
                    "diegetic", room="hall" if big else "court", wet=0.25 if big else 0.15, ff=ff)
            c, pre = rec("crackle", k, seconds=0.5)
            mix.add("sfx", T(ff) + 0.01 - pre, c, -21.0, p, "sparks crackle (recorded)", "diegetic", width=0.5, ff=ff)
        mix.add("sfx", T(ff) - 0.003, A.clang(pw, seed=40 + k, slow=slow), g_hit - (8.0 if REAL else 0.0), p,
                f"clash power {pw:.1f}" + (" slow" if slow < 1 else "") + (" (modelled ring)" if REAL else ""), "diegetic", room="hall" if big else "court",
                wet=0.3 if big else 0.18, ff=ff, log=not REAL)
        mix.add("sfx", T(ff) + 0.01, A.sparks(0.6 / max(slow, 0.25) ** 0.5, 160, seed=50 + k), -15.0 - (5.0 if REAL else 0.0), p, "sparks", "diegetic", width=0.5, ff=ff)
        if big:
            mix.add("sfx", T(ff), A.sub_boom(2.2 if slow < 1 else 1.4, 52.0, seed=k), -8.0, 0.0, "sub boom", "aesthetic", ff=ff)
    for k, e in enumerate(by("splash")):
        g = -13.0 + film.near(e["ff"], p=e["at"]) * 0.5
        if REAL:
            x, pre = rec("splash", k, seconds=0.9)
            mix.add("foley", T(e["ff"]) - pre, x, g, film.pan(e["ff"], p=e["at"]), "splash (recorded)", "foley", room="court", wet=0.15, ff=e["ff"])
        mix.add("foley", T(e["ff"]), A.splash(e.get("power", 1.0), seed=60 + k), g - (6.0 if REAL else 0.0),
                film.pan(e["ff"], p=e["at"]), "splash", "foley", room="court", wet=0.15, ff=e["ff"], log=not REAL)
    for k, e in enumerate(by("skid")):
        dur = max(0.2, (e["f1_ff"] - e["f0_ff"] + 1) / FPS)
        mix.add("foley", T(e["f0_ff"]), A.skid(dur, seed=70 + k), -12.0 + film.near(e["f0_ff"], e["who"]) * 0.5,
                film.pan(e["f0_ff"], e["who"]), f"skid {e['who']}", "foley", ff=e["f0_ff"])
    spin = C["SPIN"]                                                   # the spin: a fly-by that turns with him, left to right
    f0, f1 = next(i + 1 for i, f in enumerate(film.F) if f["take"] >= spin), next(i + 1 for i, f in enumerate(film.F) if f["take"] >= C["KICK"]) - 2
    n = A.n_of(T(f1) - T(f0))
    u = np.linspace(0.0, 1.0, n)
    lv = np.sin(np.pi * u) ** 1.2
    fly = A.whoosh(lv, 500.0 + 1700.0 * np.sin(np.pi * u) ** 2 * (1.15 - 0.3 * u), seed=88, kind="air")
    mix.stems["sfx"][int(T(f0) * SR):int(T(f0) * SR) + n] += A.pan_track(np.tanh(1.5 * fly) / 1.5, -0.6 + 1.2 * u)[: mix.n - int(T(f0) * SR)] * db(-11.0)
    mix.cues.append(dict(t=T(f0), ff=f0, stem="sfx", name="spin: doppler fly-by, panned left to right", kind="motion", db=-11.0, pan=0.0))
    for k, e in enumerate(by("kick")):
        ff = e["ff"]
        p = film.pan(ff, p=e["at"])
        if REAL:
            x, pre = rec("kick", k)
            mix.add("sfx", T(ff) - pre, x, -3.0, p, "kick lands (recorded)", "diegetic", room="court", wet=0.15, ff=ff)
        mix.add("sfx", T(ff) - 0.003, A.body_hit(e.get("power", 1.0), seed=80 + k), -3.0 - (6.0 if REAL else 0.0), p, "kick lands", "diegetic", room="court", wet=0.15, ff=ff, log=not REAL)
        mix.add("sfx", T(ff), A.sub_boom(1.4, 50.0, seed=81), -7.0, 0.0, "sub boom", "aesthetic", ff=ff)
    if flame:
        if REAL:
            x, pre = rec("ignite", 0)
            mix.add("elem", T(flame["f0_ff"]) - pre, x, -8.0, film.pan(flame["f0_ff"], "oni"), "the fire wakes (recorded)", "aesthetic", ff=flame["f0_ff"])
        mix.add("elem", T(flame["f0_ff"]) - 0.02, A.ignite(seed=90), -8.0 - (6.0 if REAL else 0.0), film.pan(flame["f0_ff"], "oni"), "the fire wakes", "aesthetic", ff=flame["f0_ff"], log=not REAL)
    if flame:                                                          # the great cut: the fire bursts along the blade as it passes
        ff = flame["peak_ff"]
        n = A.n_of(0.45)
        lash = A.whoosh(A.curve([(0, 0), (0.12, 1.0), (0.45, 0)], n), A.curve([(0, 900), (0.12, 2600), (0.45, 700)], n), seed=89, kind="whip")
        mix.add("sfx", T(ff) - 0.12, (np.tanh(1.5 * lash) / 1.5).astype(np.float32), -10.0, film.pan(ff, "oni"), "great cut: the lash", "motion", ff=ff)
        if REAL:
            x, _ = rec("fire_burst", 0)
            mix.add("elem", T(ff) - SM.peak_of(x) / SR, x, -6.0, film.pan(ff, "oni"), "great cut: the fire bursts (recorded)", "aesthetic", room="court", wet=0.2, ff=ff)
        mix.add("elem", T(ff) - 0.03, A.ignite(seed=87), -7.0 - (6.0 if REAL else 0.0), film.pan(ff, "oni"), "great cut: the fire bursts", "aesthetic", room="court", wet=0.2, ff=ff, log=not REAL)
        mix.add("sfx", T(ff), A.sub_boom(1.2, 50.0, seed=86), -9.0, 0.0, "sub boom", "aesthetic", ff=ff)
    for e in by("tear"):
        mix.add("foley", T(e["ff"]), A.tear(seed=91), -9.0, film.pan(e["ff"], "ronin"), "cape torn", "foley", ff=e["ff"])
    for e in by("hat_split"):                                          # the cut shows, the halves part and slide, fall, land
        ff = e["ff"]
        mix.add("sfx", T(ff), A.glint(seed=92)[: A.n_of(0.5)] * 0.6, -16.0, film.pan(ff, "ronin"), "hat: the cut line", "diegetic", ff=ff)
        mix.add("foley", T(ff + 5), A.straw_creak(0.55, seed=93), -17.0, film.pan(ff + 5, "ronin"), "hat halves slide", "foley", ff=ff + 5)
        fall = A.whoosh(A.curve([(0, 0), (0.4, 0.6), (0.53, 0.0)], A.n_of(0.53)), np.full(A.n_of(0.53), 700.0), seed=94, kind="air")
        mix.add("foley", T(ff + 18), fall, -22.0, film.pan(ff + 18, "ronin"), "hat halves fall", "motion", ff=ff + 18)
        land = ff + 31                                                 # 0.22 s gap + 0.55 s slide + 0.53 s fall (sd/fightfx.py)
        for j, (f, g, pn) in enumerate(((land, -15.0, -0.35), (land + 2, -17.0, 0.3))):
            if REAL:
                x, pre = rec("wood", 0, speed=1.25 if j == 0 else 1.1)
                mix.add("foley", T(f) - pre, x, g, pn, "hat half lands (recorded wood)", "foley", room="court", wet=0.2, ff=f)
            mix.add("foley", T(f), A.straw_hit(seed=95 + j), g - (6.0 if REAL else 0.0), pn, "hat half lands", "foley", room="court", wet=0.2, ff=f, log=not REAL)
    for e in by("mask_crack"):
        ff = e["ff"]
        if REAL:
            x, pre = rec("crack", 0)
            mix.add("sfx", T(ff) - pre, x, -3.0, film.pan(ff, "oni"), "mask cracks (recorded)", "diegetic", room="court", wet=0.15, ff=ff)
        mix.add("sfx", T(ff) - 0.003, A.crack(7 / FPS, seed=97), -2.0 - (5.0 if REAL else 0.0), film.pan(ff, "oni"), "mask cracks", "diegetic", room="court", wet=0.15, ff=ff, log=not REAL)

    # --- moments laid by hand to the picture
    if REAL:
        x, pre = rec("breath", 0, seconds=1.4)
        mix.add("foley", T(110) - pre, x, -12.0, film.pan(110, "oni"), "Oni breathes behind the mask (recorded)", "diegetic", room="near", wet=0.2, ff=110)
    mix.add("foley", T(110), A.norm(A.breath(1.3, seed=98), 0.7), -11.0 - (8.0 if REAL else 0.0), film.pan(110, "oni"), "Oni breathes behind the mask", "diegetic", ff=110, log=not REAL)
    mix.add("foley", T(131), A.norm(A.lp(A.straw_creak(0.45, seed=99), 2500), 0.6), -16.0, 0.1, "hand tightens on the grip", "foley", ff=131)
    mix.add("foley", T(188), A.straw_creak(0.6, seed=100), -19.0, film.pan(188, "ronin"), "hat brim lifted", "foley", ff=188)
    mix.add("sfx", T(208) - 0.03, A.glint(seed=101), -12.0, film.pan(208, "ronin"), "glint on the visor", "aesthetic", ff=208)
    mix.add("sfx", T(220) - 0.002, A.guard_click(seed=102), -8.0, 0.1, "guard pushed off the scabbard", "diegetic", room="court", wet=0.25, ff=220)
    for k, (ff, who) in enumerate(((222, "oni"), (223, "ronin"), (224, "ronin"))):
        if REAL:
            x, pre = rec("draw", k, seconds=1.1)
            mix.add("sfx", T(ff) - pre, x, -6.0 - 1.5 * k, film.pan(225, who), f"blade drawn ({who}, recorded)", "diegetic", room="court", wet=0.25, ff=ff)
        mix.add("sfx", T(ff), A.shing(1.4, seed=103 + k), -5.0 - 1.5 * k - (6.0 if REAL else 0.0), film.pan(225, who), f"blade drawn ({who})" + (" ring" if REAL else ""),
                "diegetic", room="court", wet=0.3, ff=ff, log=not REAL)
    mix.add("sfx", T(564), A.visor_hum(T(591) - T(564), seed=106), -21.0, film.pan(570, "ronin"), "visor hum", "aesthetic", ff=564)
    if REAL:
        x, pre = rec("glitch", 0)
        mix.add("sfx", T(564) - pre, x, -20.0, film.pan(570, "ronin"), "visor flickers on (recorded glitch)", "aesthetic", ff=564)
        x, pre = rec("breath", 1, seconds=1.0)
        mix.add("foley", T(585) - pre, x, -14.0, film.pan(587, "oni"), "Oni breathes, eyes in the mask (recorded)", "diegetic", room="near", wet=0.2, ff=585)
    mix.add("foley", T(585), A.norm(A.breath(0.9, seed=107), 0.7), -13.0 - (8.0 if REAL else 0.0), film.pan(587, "oni"), "Oni breathes, eyes in the mask", "diegetic", ff=585, log=not REAL)


def lay_ambience(film, mix):
    """The courtyard at night: wind with gusts on the openings and the stillness, a far wind chime, the
    great bell at the start."""
    w = A.wind(mix.n / SR + 0.1, seed=200, gusts=[(0.6, 0.7), (6.2, 0.5), (9.5, 0.15), (26.2, 0.3), (28.2, 0.3)])[: mix.n]
    if REAL:                                                           # a recorded cold wind over the courtyard, the modelled gusts under it
        w = BANK.bed("wind", 0, mix.n) * 0.6 + w * db(-8.0)
        USED.add(BANK.pick("wind", 0))
    shot_db = np.zeros(film.n)
    for i, f in enumerate(film.F):
        lens = f["cam"]["lens"]
        shot_db[i] = -2.0 if lens <= 24 else -6.0 if lens <= 45 else -10.0           # wide shots carry more of the place
        if 241 <= f["ff"] <= 623:
            shot_db[i] -= 5.0                                                        # the fight covers it anyway
    mix.stems["amb"] += w * per_sample(db(shot_db), mix.n)[:, None] * db(-15.0)
    mix.cues.append(dict(t=0.0, ff=1, stem="amb", name="night wind over the courtyard (gusts 0.6, 6.2, 9.5, 26.2, 28.2 s)", kind="ambience", db=-15.0, pan=0.0, layer=True))
    if REAL:
        x, pre = rec("bell", 0, speed=0.8, mono=False)
        mix.add("amb", 0.04 - pre, x, -14.0, 0.0, "temple bell (recorded bell, a fifth lower)", "diegetic", room="hall", wet=0.3)
    mix.add("amb", 0.04, A.bell(55.0, 7.5, seed=201), -9.0 - (6.0 if REAL else 0.0), -0.15, "temple bell", "diegetic", room="hall", wet=0.35, log=not REAL)
    for k, (t, p) in enumerate(((1.7, -0.6), (3.7, 0.5), (7.3, -0.4), (26.7, 0.55))):
        mix.add("amb", t, A.chime(seed=210 + k), -29.0, p, "wind chime, far off", "ambience", room="court", wet=0.5)


# ----------------------------------------------------------------------------- the score
def lay_score(film, mix):
    """Japanese palette in A (hirajoshi: A B C E F): temple drone, flute, plucked strings, drums.
    The music follows the story and stops where the picture needs silence."""
    m = lambda t, x, g, p=0.0, name="", room="court", wet=0.25: mix.add("music", t, x, g, p, name, "music", room=room, wet=wet)  # noqa: E731
    notes = []

    # M1 night (0-3 s): the bell's drone, a flute alone
    m(0.3, A.drone(55.0, 9.0, seed=300), -17.0, 0.0, "drone A1 (night)")
    for t, nm, d in ((1.0, "A4", 0.85), (1.95, "C5", 0.5), (2.5, "B4", 1.2)):
        m(t, A.flute(NOTE[nm], d, seed=int(t * 10)), -19.0, -0.2, f"flute {nm}", wet=0.35)
    # M2 the Oni (3-5.3 s): a low drum under each of his steps, a pluck and a swell on the mask
    for k, c in enumerate(film.D["contacts"]["oni"]):
        if 73 <= c["ff"] <= 108:
            m(T(c["ff"]), ens("o", 0.6, 1, seed=310 + k), -23.0, 0.0, "taiko under the Oni's step")
    m(T(109), A.shamisen(NOTE["A2"], 1.6, seed=320), -17.0, 0.0, "shamisen A2 (the mask)")
    m(T(109) - 0.6, A.reverse(A.room(A.taiko("o", 0.8, seed=321), "hall", 0.6)[:, 0][: A.n_of(0.6)]), -16.0, 0.0, "reversed drum into the mask")
    # M3 the grip (5.3-6 s): a koto trembling on one note
    for k in range(9):
        m(T(127) + k * 0.075, A.koto(NOTE["E4"], 0.5, 0.4 + 0.07 * k, seed=330 + k), -22.0, 0.25, "koto tremolo E4")
    # M4 the Ronin (6-7.5 s): the flute answers; a quiet electric pulse for the cyber ronin
    for t, nm, d in ((6.3, "E5", 0.6), (6.95, "F5", 0.45), (7.45, "E5", 0.9)):
        m(t, A.flute(NOTE[nm], d, seed=int(t * 10)), -18.0, 0.25, f"flute {nm}", wet=0.35)
    for k in range(int((9.0 - 6.04) / 0.4167)):
        t = 6.04 + k * 0.4167
        m(t, A.pulse(NOTE["E2"], 0.18, 900.0, seed=600 + k), -27.0 + 2.0 * k / 7.0, 0.0, "cyber pulse E2")
    # M5 the hat (7.5-9 s): a drum roll that grows, a run up the koto into the glint
    if REAL:
        x, to_pk = rec_into("roll", 1, 8.95, 1.35)
        m(8.95 - to_pk, x, -16.0, 0.1, "drum roll into the glint (recorded)")
    t = 7.6
    while t < 8.95:
        u = (t - 7.6) / 1.35
        m(t, A.taiko("shime", 0.35 + 0.6 * u, seed=int(t * 100)), -20.0 + 6.0 * u, 0.1, "shime roll")
        t += 0.16 - 0.1 * u
    for k, nm in enumerate(("A4", "B4", "C5", "E5", "F5", "A5")):
        m(T(208) - 0.3 + k * 0.05, A.koto(NOTE[nm], 1.4, 0.7, seed=340 + k), -18.0, 0.3, f"koto run {nm}")
    # M6 the guard (9.04-9.33 s): nothing but the wind; M7 the draw: one great drum and a low brass hit
    m(T(225), ens("o", 1.0, 3, seed=350), -14.0, 0.0, "o-daiko x3 (the draw)", "hall", 0.3)
    m(T(225), A.braam(55.0, 1.6, seed=351), -20.0, 0.0, "braam A1")
    for t in (9.85,):
        m(t, heart(0), -19.0, 0.0, "heartbeat")

    # the fight's drums: an elastic grid that always lands on the blows
    def drums(f0, f1, accents, lo=10, sub=4, vel=1.0, riff=True, seed=0):
        """Drums (and the shamisen riff) from film frame f0 to f1: o-daiko on the beats and accents,
        shime on the subdivisions; between two marks the beat stretches to fit."""
        marks = sorted(set([f0] + [a for a in accents if f0 <= a <= f1] + [f1]))
        riff_notes = ["A3", "C4", "E4", "F4", "E4", "C4", "B3", "C4"]
        r = np.random.default_rng(seed)
        k = 0
        for a, b in zip(marks[:-1], marks[1:]):
            beats = max(1, round((b - a) / lo))
            step = (T(b) - T(a)) / (beats * sub)
            for i in range(beats * sub):
                t = T(a) + i * step
                on_beat = i % sub == 0
                if on_beat:
                    acc = i == 0 and a in accents
                    m(t, ens("o", (1.0 if acc else 0.7) * vel, 3 if acc else 1, seed=seed + k), -14.0 if acc else -18.0, 0.0, "o-daiko" + (" x3 (blow)" if acc else ""), "hall" if acc else "court", 0.25)
                else:
                    m(t, A.taiko("shime", r.uniform(0.5, 0.8) * vel, seed=seed + 500 + k), -24.0, r.uniform(-0.3, 0.3), "shime")
                if riff and i % 2 == 0:
                    nm = riff_notes[(k // 2) % len(riff_notes)]
                    m(t, A.pulse(NOTE[nm] / 4.0, step * 1.8, 700.0, seed=seed + 900 + k), -22.0, 0.0, f"pulse {nm} two octaves down")
                if i % sub == 2:
                    m(t, ens("nagado", r.uniform(0.55, 0.75) * vel, 1, seed=seed + 700 + k), -20.0, 0.0, "nagado")
                k += 1

    m(T(241), ens("o", 1.0, 3, seed=360), -9.0, 0.0, "o-daiko x3 (they run)", "hall", 0.25)
    drums(241, 262, [], seed=1000)
    m(T(263), A.drone(55.0, 1.6, seed=361, dark=500.0), -12.0, 0.0, "drone under the slow strides")
    m(T(275), big_hit(2.6, seed=362, k=0), -9.0, 0.0, "trailer hit (first clash)", "hall", 0.3)
    m(T(275), brass(55.0, 2.4, seed=363, k=2), -13.0, 0.0, "war horn and braam (first clash)")
    m(T(284), heart(1), -19.0, 0.0, "heartbeat")
    H = [film.D["events"][i]["ff"] for i, e in enumerate(film.D["events"]) if e["kind"] == "clash"]
    hammer = [f for f in H if 289 <= f <= 360]
    drums(289, 359, hammer, seed=2000)
    if hammer:
        m(T(hammer[-1]), A.braam(55.0, 1.8, seed=365), -11.0, 0.0, "braam (third cut)")
    kick = [e["ff"] for e in film.D["events"] if e["kind"] == "kick"]
    drums(360, 431, [372] + kick, seed=3000)
    trade = [f for f in H if 433 <= f <= 503]
    drums(433, 503, trade, seed=4000)
    # the fire: everything gathers, then the great cut
    m(T(504), A.riser(T(542) - T(504), seed=366), -13.0 - (5.0 if REAL else 0.0), 0.0, "riser into the great cut")
    if REAL:
        x, to_pk = rec_into("riser", 0, T(542), T(542) - T(504))
        m(T(542) - to_pk, x, -12.0, 0.0, "riser into the great cut (recorded)")
        x, to_pk = rec_into("roll", 0, T(541), T(541) - T(505))
        m(T(541) - to_pk, x, -14.0, 0.0, "drum roll building (recorded)")
    t = T(505)
    while t < T(541):
        u = (t - T(505)) / (T(541) - T(505))
        m(t, A.taiko("shime", 0.4 + 0.6 * u, seed=int(t * 100)), -20.0 + 7.0 * u, 0.0, "shime roll")
        t += 0.17 - 0.12 * u
    m(T(518), ens("o", 0.9, 2, seed=367), -11.0, 0.0, "o-daiko (he comes in)")
    m(T(542), big_hit(2.2, seed=368, k=1), -9.0, 0.0, "trailer hit (great cut)", "hall", 0.25)
    m(T(542), brass(55.0, 1.0, seed=369, k=1), -13.0, 0.0, "war horn and braam (great cut)")
    # the stare (22.6-24.6 s): the drone and a heart; the flute, low
    m(T(548), A.drone(55.0, T(601) - T(548), seed=370, dark=600.0), -18.0, 0.0, "drone (the stare)")
    for t in (23.55, 24.25):
        m(t, heart(int(t * 10)), -19.0, 0.0, "heartbeat")
    if REAL:
        x, pre = rec("choir", 0, seconds=2.8, mono=False)
        m(T(552) - pre, fade_both(x, 0.6, 0.8), -24.0, 0.0, "a dark choir under the stare (recorded)", "hall", 0.3)
    for t, nm, d in ((22.95, "A4", 0.5), (23.5, "F4", 0.45), (24.0, "E4", 0.8)):
        m(t, A.flute(NOTE[nm], d, seed=int(t * 10)), -21.0, -0.2, f"flute {nm}", wet=0.4)
    # the launch and the crossing: a riser, three frames of silence, the biggest hit
    m(T(588) - 0.25, A.riser(T(601) - T(588) + 0.25, seed=371), -12.0 - (5.0 if REAL else 0.0), 0.0, "riser (they launch)")
    if REAL:
        x, to_pk = rec_into("riser", 0, T(601), T(601) - T(588) + 0.25, after=0.05)
        m(T(601) - to_pk, x, -11.0, 0.0, "riser (they launch, recorded)")
    m(T(604), big_hit(3.0, seed=372, k=2), -8.0, 0.0, "trailer hit (the crossing)", "hall", 0.35)
    m(T(604), brass(55.0, 1.6, seed=373, k=0), -12.0, 0.0, "war horn and braam (the crossing)")
    m(T(604), A.drone(55.0, 1.8, seed=374, dark=1400.0), -17.0, 0.0, "drone chord (they pass)")
    m(T(606), A.koto(NOTE["A4"], 2.4, 0.8, seed=375), -21.0, 0.3, "koto A4 (they pass)", "hall", 0.4)
    # the end: a note for the hat, the crack heard first and the drum after it, the bell, then nothing
    m(T(657), A.koto(NOTE["A4"], 2.2, 0.8, seed=376), -22.0, 0.3, "koto A4 (the hat parts)", "hall", 0.4)
    m(T(666), A.koto(NOTE["E4"], 2.2, 0.6, seed=377), -24.0, 0.3, "koto E4")
    m(T(650), A.drone(55.0, T(700) - T(650), seed=378, dark=500.0), -20.0, 0.0, "drone (the end)")
    m(T(696), ens("o", 1.0, 2, seed=379), -14.0, 0.0, "o-daiko (after the crack)", "hall", 0.45)
    if REAL:
        x, pre = rec("bell", 0, speed=0.8, mono=False)
        mix.add("amb", T(694) - pre, x, -14.0, 0.0, "temple bell (the end, recorded)", "diegetic", room="hall", wet=0.35)
    mix.add("amb", T(694), A.bell(55.0, 6.0, seed=380), -10.0 - (6.0 if REAL else 0.0), 0.0, "temple bell (the end)", "diegetic", room="hall", wet=0.4, log=not REAL)
    return notes


# ----------------------------------------------------------------------------- master
def compress(x, thresh_db=-20.0, ratio=2.0, attack=0.03, release=0.25):
    """A gentle glue compressor (slow attack keeps each hit's first punch)."""
    lvl = np.sqrt(np.convolve(np.mean(x ** 2, axis=1), np.ones(A.n_of(0.01)) / A.n_of(0.01), mode="same") + 1e-12)
    ldb = 20 * np.log10(lvl)
    over = np.maximum(ldb - thresh_db, 0.0)
    target = -over * (1.0 - 1.0 / ratio)
    g = np.zeros_like(target)
    a, r = math.exp(-1.0 / (attack * SR)), math.exp(-1.0 / (release * SR))
    cur = 0.0
    for i, v in enumerate(target):
        cur = a * cur + (1 - a) * v if v < cur else r * cur + (1 - r) * v
        g[i] = cur
    return (x * db(g)[:, None]).astype(np.float32), float(-g.min())


def true_peak(x):
    from scipy import signal
    return float(np.abs(signal.resample_poly(x, 4, 1, axis=0)).max())


def limit(x, ceiling_db=-2.0, release=0.08, look=0.002):
    """A true-peak limiter: the peak is found at 4x the sample rate, the gain is lowered just before it
    (look-ahead) and comes back slowly. Returns the signal, the most gain taken and where."""
    from scipy import signal
    from scipy.ndimage import minimum_filter1d
    c = db(ceiling_db)
    pk = np.abs(signal.resample_poly(x, 4, 1, axis=0)).reshape(-1, 4, 2).max(axis=(1, 2))[: len(x)]
    need = np.minimum(1.0, c / np.maximum(pk, 1e-9))
    need = minimum_filter1d(need, size=2 * A.n_of(look) + 1)
    g = np.empty_like(need)
    r = math.exp(-1.0 / (release * SR))
    cur = 1.0
    for i, v in enumerate(need):
        cur = v if v < cur else r * cur + (1 - r) * v
        g[i] = cur
    y = (x * g[:, None]).astype(np.float32)
    k = int(np.argmin(g))
    return y, float(-20 * np.log10(g.min())), k / SR


def low_shelf(x, g_db, fc=90.0):
    """The band under fc changed by g_db (a 4th-order Linkwitz-Riley split, so the two halves sum flat)."""
    from scipy import signal
    lo, hi = x, x
    for _ in range(2):
        lo = signal.sosfilt(signal.butter(2, fc, "lowpass", fs=SR, output="sos"), lo, axis=0)
        hi = signal.sosfilt(signal.butter(2, fc, "highpass", fs=SR, output="sos"), hi, axis=0)
    return (lo * db(g_db) + hi).astype(np.float32)


def master(mix_sum, target=-14.0, ceiling=-2.0):
    import pyloudnorm as pyln
    from scipy import signal
    meter = pyln.Meter(SR)
    mix_sum = signal.sosfilt(signal.butter(2, 28.0, btype="highpass", fs=SR, output="sos"), mix_sum, axis=0)   # below 28 Hz: nothing plays it, it only eats headroom
    mix_sum = low_shelf(mix_sum, -3.0, 90.0)       # phone first: a phone's speaker plays almost nothing under ~300 Hz, so the
                                                   # hits must not spend the loudness on sub-bass (measured: v1's title lost 8 dB on a phone)
    L0 = meter.integrated_loudness(mix_sum.astype(np.float64))
    x, comp_db = compress(mix_sum * db(-18.0 - L0), thresh_db=-16.0)       # compress from a known level
    L = meter.integrated_loudness(x.astype(np.float64))
    x = x * db(target - L)
    worst = []
    for _ in range(3):
        x, gr, where = limit(x, ceiling)
        worst.append((gr, where))
        if true_peak(x) <= db(ceiling) * 1.001:
            break
        ceiling -= 0.2
    L2 = meter.integrated_loudness(x.astype(np.float64))
    return x, dict(lufs_before=L, lufs=L2, comp_db=comp_db, limiter_db=worst[0][0], limiter_at=worst[0][1], true_peak_db=20 * np.log10(true_peak(x)))


def write_wav(path, x):
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, x, SR, subtype="PCM_24")


def mux(video, wav, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-map", "0:a", "-af", "loudnorm=print_format=summary", "-f", "null", "-"],
                       capture_output=True, text=True)
    lines = [ln.strip() for ln in r.stderr.splitlines() if ln.strip().startswith(("Input Integrated", "Input True Peak", "Input LRA"))]
    return lines


def write_sheets(mix, path_cues, path_music, title):
    rows = sorted(mix.cues, key=lambda c: (c.get("layer", False) is False, c["t"]))
    with open(path_cues, "w") as fh:
        fh.write(f"{title}: cue sheet (time in s, film frame, stem, level in dB before the master, pan -1 left .. 1 right)\n")
        fh.write("Layers (run along the picture):\n")
        for c in rows:
            if c.get("layer"):
                fh.write(f"  {c['stem']:6s} {c['db']:+6.1f} dB  {c['name']}\n")
        fh.write("\nCues:\n")
        for c in rows:
            if not c.get("layer") and c["stem"] != "music":
                fh.write(f"  {c['t']:6.2f} s  f{c['ff']:4d}  {c['stem']:6s} {c['kind']:10s} {c['db']:+6.1f} dB  pan {c['pan']:+.2f}  {c['name']}\n")
    with open(path_music, "w") as fh:
        fh.write(f"{title}: music map (A hirajoshi: A B C E F; taiko ensemble, trailer hits, drums on a grid that lands on the blows)\n")
        for c in rows:
            if c["stem"] == "music":
                fh.write(f"  {c['t']:6.2f} s  f{c['ff']:4d}  {c['db']:+6.1f} dB  {c['name']}\n")


def film_main():
    film = Film(os.path.join(OUT, "events.json"))
    mix = Mix(30.0)
    lay_ambience(film, mix)
    lay_effects(film, mix)
    lay_score(film, mix)
    # the music steps aside for the effects (sidechain): fast down on a hit, back up over 0.3 s
    key = np.abs(mix.stems["sfx"]).max(axis=1) + 0.6 * np.abs(mix.stems["foley"]).max(axis=1)
    env = np.zeros_like(key)
    a, r = math.exp(-1.0 / (0.004 * SR)), math.exp(-1.0 / (0.30 * SR))
    cur = 0.0
    for i, v in enumerate(key[::8]):                                   # (at an eighth of the rate: plenty for an envelope)
        cur = a * cur + (1 - a) * v if v > cur else r ** 8 * cur + (1 - r ** 8) * v
        env[i * 8:(i + 1) * 8] = cur
    ldb = 20 * np.log10(env + 1e-6)
    duck = -np.clip(0.5 * (ldb + 30.0), 0.0, 9.0)
    mix.stems["music"] *= db(duck)[:, None].astype(np.float32)
    # the impact frames: two frames where everything but the blow drops away
    for f in (275, 350, 396, 604):
        mix.duck(("amb", "elem", "music", "foley"), T(f), T(f + 2), -9.0)
    # silence where the picture holds its breath: the guard, three frames before the crossing, back to back; the black at the end below
    mix.duck(("music", "elem"), T(217), T(222), -14.0, ramp=0.05)
    mix.duck(STEMS, T(601), T(604) - 0.005, -20.0, ramp=0.015)            # the world goes quiet, then the blow
    mix.duck(("music", "elem"), T(626), T(650), -14.0, ramp=0.35)
    mix.duck(("sfx",), T(626), T(650), -8.0, ramp=0.5)                     # the blades' ring dies away
    mix.duck(("music",), T(552), T(590), -5.0, ramp=0.3)
    end = np.ones(mix.n, np.float32)
    a, b = int(T(704) * SR), int(T(720) * SR + SPF)
    end[a:b] = np.linspace(1.0, 0.0, b - a) ** 1.6
    end[b:] = 0.0
    total = sum(mix.stems.values()) * end[:, None]
    master_x, rep = master(total, ceiling=-2.5)                          # AAC adds about 1 dB to the sharpest peaks
    for k, s in mix.stems.items():
        write_wav(os.path.join(OUT, "stems", f"film_{k}.wav"), s * end[:, None])
    wav = os.path.join(OUT, "film_master.wav")
    write_wav(wav, master_x)
    write_sheets(mix, os.path.join(OUT, "cue_sheet_v2.txt"), os.path.join(OUT, "music_map_v2.txt"), "Oni vs Ronin, the film (30 s)")
    print("MASTER", {k: round(v, 2) for k, v in rep.items()})
    if USED:
        SM.credits(os.path.join(HERE, "SOUND_CREDITS.txt"), USED)
    video = os.path.join(HERE, arg("--video", "previews/stage4_film_v3.mp4"))
    out = os.path.join(HERE, arg("--out", "previews/stage4_film_v3_sound.mp4"))
    print("MP4", out, mux(video, wav, out))
    n_cues = sum(1 for c in mix.cues if not c.get("layer"))
    print(f"cues {n_cues}, layers {sum(1 for c in mix.cues if c.get('layer'))}")
    return mix


def teaser_main():
    """The teaser's sound: each shot keeps the film's own effects for the frames it shows (a short tail
    over the cut), the held impact frames get their blow, and a score of its own carries the cut:
    a bell and a drone under the stills, a riser into the words, drums through the action and a big
    drum on the impact frames, six frames of silence, the title hit, the ring-out."""
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import teaser as TZ
    film = Film(os.path.join(OUT, "events.json"))
    fm = Mix(30.0)
    lay_ambience(film, fm)
    lay_effects(film, fm)
    for f in (275, 350, 396, 604):
        fm.duck(("amb", "elem", "foley"), T(f), T(f + 2), -9.0)
    segs, j = [], 0
    for e in TZ.EDIT:                                                  # (kind, first teaser frame, frames, what)
        n = e[2] - e[1] + 1 if e[0] == "shot" else e[2] if e[0] in ("hold", "text") else e[1]
        segs.append((e[0], j, n, e[1:]))
        j += n
    mix = Mix(j / FPS)
    # shots and held frames that follow each other in the film (gaps of a frame or two) make one run of the
    # film's sound, so a blow lands on its impact frame and nothing is heard twice
    chains = []
    for kind, j0, n, what in segs:
        if kind not in ("shot", "hold"):
            chains.append(None)
            continue
        f0, f1 = (what[0], what[1]) if kind == "shot" else (what[0], what[0])
        c = chains[-1] if chains else None
        if c is not None and 0 < f0 - c["last"] <= 2:
            c["frames"] += n
            c["last"] = f1
        else:
            chains.append(dict(j0=j0, film=f0, frames=n, last=f1))
    tail, fin = A.n_of(0.06), A.n_of(0.008)
    for c in (c for c in chains if c):
        a = int(T(c["film"]) * SR)
        ln = c["frames"] * SPF + tail
        for stem, g in (("foley", 0.0), ("sfx", 0.0), ("elem", 0.0), ("amb", -4.0)):
            x = fm.stems[stem][a:a + ln].copy()
            if len(x) == 0:
                continue
            x[:fin] *= np.linspace(0.0, 1.0, min(fin, len(x)))[:, None]
            fo = min(len(x), tail)
            x[len(x) - fo:] *= np.linspace(1.0, 0.0, fo)[:, None]
            mix.add(stem, c["j0"] / FPS, x, g, name=f"film's sound from frame {c['film']} for {c['frames']} frames ({stem})", kind="from the film",
                    log=stem == "sfx", ff=c["film"])
    first = {k: j0 for k, j0, n, w in segs[::-1]}
    m = lambda t, x, g, p=0.0, name="", room="court", wet=0.25: mix.add("music", t, x, g, p, name, "music", room=room, wet=wet)  # noqa: E731
    shots = [(j0, n, w) for k, j0, n, w in segs if k == "shot"]
    text = next((j0, n) for k, j0, n, w in segs if k == "text")
    title = next((j0, n) for k, j0, n, w in segs if k == "title")
    holds = [j0 for k, j0, n, w in segs if k == "hold"]
    act0 = next(j0 for j0, n, w in shots if w[0] >= 241)
    act1 = max(j0 + n for j0, n, w in shots)
    # stills: the bell and a drone; each cut lands on two drummers and a sub; the shakuhachi alone
    if REAL:
        x, pre = rec("bell", 0, speed=0.8, mono=False)
        mix.add("amb", shots[0][0] / FPS - pre, x, -16.0, 0.0, "temple bell (recorded)", "diegetic", room="hall", wet=0.3)
    mix.add("amb", shots[0][0] / FPS, A.bell(55.0, 6.0, seed=401), -11.0 - (6.0 if REAL else 0.0), 0.0, "temple bell", "diegetic", room="hall", wet=0.35, log=not REAL)
    m(shots[0][0] / FPS, ens("o", 0.9, 3, seed=400), -13.0, 0.0, "o-daiko x3 (the opening)", "hall", 0.3)
    m(shots[0][0] / FPS, A.drone(55.0, text[0] / FPS - shots[0][0] / FPS + 0.5, seed=402), -19.0, 0.0, "drone A1")
    for k, (j0, n, w) in enumerate(shots):
        if j0 < text[0] and k > 0:
            m(j0 / FPS, A.sub_boom(0.9, 55.0, seed=410 + k), -17.0, 0.0, "sub on the cut")
            m(j0 / FPS, ens("o", 0.55, 2, seed=420 + k), -19.0, 0.0, "two o-daiko on the cut", "hall", 0.25)
    for t, nm, d in ((0.55, "A4", 0.7), (1.35, "C5", 0.45), (1.85, "B4", 1.0)):
        m(t, A.flute(NOTE[nm], d, seed=int(t * 10)), -17.0, -0.2, f"shakuhachi {nm}", "hall", 0.35)
    # into the words: a riser with a reversed cymbal, then the trailer's big hit and a braam
    rs = shots[3][0] / FPS
    m(rs, A.riser(text[0] / FPS - rs, seed=430), -14.0 - (5.0 if REAL else 0.0), 0.0, "riser into the words")
    if REAL:
        x, to_pk = rec_into("riser", 0, text[0] / FPS, text[0] / FPS - rs, after=0.05)
        m(text[0] / FPS - to_pk, x, -13.0, 0.0, "riser into the words (recorded)")
    m(text[0] / FPS, big_hit(2.6, seed=431, k=1), -6.0, 0.0, "trailer hit (ONE MOON. TWO BLADES.)", "hall", 0.3)
    m(text[0] / FPS, brass(55.0, 1.2, seed=432, k=1), -14.0, 0.0, "war horn and braam A1")
    m(text[0] / FPS, A.braam(110.0, 1.0, seed=435), -16.0, 0.0, "braam A2")
    m(text[0] / FPS, A.clang(1.4, seed=434, slow=0.7), -10.0, 0.0, "a blade's ring (TWO BLADES)", "hall", 0.3)
    m(act0 / FPS - 0.45, A.suck_in(0.45, seed=433), -12.0, 0.0, "pull into the action")
    # the action: a taiko ensemble at 144 a minute (o-daiko DON, nagado DOKO, shime running, kachi on the rim),
    # a low pulse in A that drops to F in the second bar, a trailer hit on the held impact frames
    step16 = 60.0 / 144.0 / 4.0
    groove = dict(o=(0, 6, 8, 14), nagado=(2, 3, 10, 11), rim=(4, 12))
    r = np.random.default_rng(440)
    k = 0
    t = act0 / FPS
    while t < act1 / FPS - 0.05:
        s16 = k % 16
        if s16 in groove["o"]:
            m(t, ens("o", 0.8 if s16 in (0, 8) else 0.65, 2, seed=450 + k), -15.0 if s16 in (0, 8) else -17.0, 0.0, "o-daiko x2", "court", 0.2)
        if s16 in groove["nagado"]:
            m(t, ens("nagado", r.uniform(0.6, 0.8), 1, seed=460 + k), -19.0, 0.0, "nagado")
        if s16 in groove["rim"]:
            m(t, A.taiko("rim", 0.8, seed=465 + k), -24.0, 0.3, "kachi (rim)")
        m(t, A.taiko("shime", (0.75 if s16 % 4 == 0 else 0.45) * r.uniform(0.9, 1.0), seed=470 + k), -26.0 if s16 % 4 else -23.0, -0.3 + 0.15 * (s16 % 2), "shime")
        if s16 % 2 == 0:
            note = NOTE["A1"] if (k // 16) % 2 == 0 or s16 < 8 else NOTE["F3"] / 4.0
            m(t, A.pulse(note, step16 * 1.8, 700.0, seed=480 + k), -23.0, 0.0, "pulse " + ("A1" if note == NOTE["A1"] else "F1"))
        k += 1
        t += step16
    for jj, j0 in enumerate(holds[::2] if len(holds) > 3 else holds):
        m(j0 / FPS, big_hit(1.6, seed=490 + j0, k=3 + jj), -12.0, 0.0, "trailer hit (impact frame)", "hall", 0.25)
    m(holds[-2] / FPS, brass(55.0, 1.4, seed=491, k=2), -12.0, 0.0, "war horn and braam (the crossing)")
    # silence, then the title: the biggest hit, the brass, the bell, the shakuhachi's last note, the ring-out
    m(title[0] / FPS, big_hit(3.2, seed=492, k=2), -5.0, 0.0, "trailer hit (title)", "hall", 0.35)
    m(title[0] / FPS, brass(55.0, 2.0, seed=493, k=0), -11.0, 0.0, "war horn and braam (title)")
    m(title[0] / FPS, A.braam(110.0, 1.6, seed=499), -13.0, 0.0, "braam an octave up (the brass a phone plays)")
    m(title[0] / FPS, A.clang(1.8, seed=498, slow=0.6), -8.0, 0.0, "a blade's ring (title)", "hall", 0.35)
    if REAL:
        x, pre = rec("bell", 0, speed=0.8, mono=False)
        mix.add("amb", title[0] / FPS + 0.05 - pre, x, -13.0, 0.0, "temple bell (title, recorded)", "diegetic", room="hall", wet=0.35)
    mix.add("amb", title[0] / FPS + 0.05, A.bell(55.0, 4.0, seed=495), -9.0 - (6.0 if REAL else 0.0), 0.0, "temple bell (title)", "diegetic", room="hall", wet=0.4, log=not REAL)
    m(title[0] / FPS + 0.55, A.flute(NOTE["A4"], 1.5, seed=496), -19.0, -0.15, "shakuhachi A4 (title)", "hall", 0.4)
    m(title[0] / FPS + 0.6, A.koto(NOTE["A4"], 1.8, 0.7, seed=497), -19.0, 0.3, "koto A4 (title)", "hall", 0.4)
    # the music steps aside for the blows; the black before the title is silent; the end fades
    key = np.abs(mix.stems["sfx"]).max(axis=1)
    cur, a_, r_ = 0.0, math.exp(-1.0 / (0.004 * SR / 8)), math.exp(-1.0 / (0.3 * SR / 8))
    env = np.zeros_like(key)
    for i, v in enumerate(key[::8]):
        cur = a_ * cur + (1 - a_) * v if v > cur else r_ * cur + (1 - r_) * v
        env[i * 8:(i + 1) * 8] = cur
    mix.stems["music"] *= db(-np.clip(0.5 * (20 * np.log10(env + 1e-6) + 30.0), 0.0, 8.0))[:, None].astype(np.float32)
    blk = next(j0 for k_, j0, n, w in segs if k_ == "black" and j0 > act0)
    mix.duck(STEMS, blk / FPS + 0.03, title[0] / FPS - 0.008, -26.0, ramp=0.02)   # the black before the title: silence
    end = np.ones(mix.n, np.float32)
    a = int((title[0] + title[1] - 12) / FPS * SR)
    end[a:] = np.linspace(1.0, 0.0, mix.n - a) ** 1.4
    total = sum(mix.stems.values()) * end[:, None]
    x, rep = master(total)
    wav = os.path.join(OUT, "teaser_master.wav")
    write_wav(wav, x)
    for k_, s_ in mix.stems.items():
        write_wav(os.path.join(OUT, "stems", f"teaser_{k_}.wav"), s_ * end[:, None])
    write_sheets(mix, os.path.join(OUT, "teaser_cue_sheet_v2.txt"), os.path.join(OUT, "teaser_music_map_v2.txt"), "Oni vs Ronin, the teaser (10.4 s)")
    print("MASTER", {k_: round(v, 2) for k_, v in rep.items()})
    if USED:
        SM.credits(os.path.join(HERE, "SOUND_CREDITS.txt"), USED)
    src = arg("--src", "previews/stage4_teaser_v3")
    for shape in ("vertical", "wide"):
        video = os.path.join(HERE, f"{src}_{shape}.mp4")
        print("MP4", shape, mux(video, wav, os.path.join(HERE, f"{src}_{shape}{arg('--tag', '_sound_v2')}.mp4")))


if __name__ == "__main__":
    if "film" in sys.argv:
        film_main()
    elif "teaser" in sys.argv:
        teaser_main()
    else:
        print(__doc__)
