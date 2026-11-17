"""Sound made in code, version 2: the palette of sd/audio.py rebuilt to sound recorded, not made.

v1 sounded synthetic in the places that carry a fight: every thud was a gliding sine (a 'boop'), the
blades rang a clean chord (a chime, not steel), cloth was noise switched on and off nine times a second,
and the drums were a sine with a little noise. v2 builds them the way the real things make sound:

    thuds       a short burst of noise ringing through the resonance of what was hit (body, ground,
                a drum's shell), never a pure tone
    steel       the modes of a katana held in the hand: bending across its thin and its wide side
                (a free-free beam: 1, 2.76, 5.40, 8.93 ...), along its length and twisted; dozens of
                them, each a close pair that beats slowly. The contact lasts a quarter of a millisecond
                and bounces two to five times (chatter). The hand damps the low modes, a thin blade
                hardly sends them into the air, the highest die fast. Two blades: two sets.
    scrapes     stick-slip: a train of tiny catches drives the blade's modes, so steel sings while it
                slides (the draw, two blades in a bind)
    swings      the rush of air, the whistle a thin edge sheds into it, the push of a big blade
    feet        the body's thud, the heel's tick, the grit crunching under the sole, water; armour
                rattles as separate little plates
    cloth       friction crackle and the air it moves, with an uneven flutter on fast moves
    the place   the courtyard's reverb has the floor bounce, the walls, a slap off the hall, and a
                tail that loses its highs sooner than its lows, as air does
    drums       membranes (Bessel modes) whose pitch settles as the skin relaxes, the stick, the
                wooden shell, the air pushed out; several drummers on one beat
    trailer     the big hit (drummers, a slowed blade slam, a sub drop, air), a brass braam with a
                formant, a reversed cymbal, a low pulse

Everything else (fire, water, the bell, the wind, the drone, the hat, the mask ...) is v1's.
Every function returns float32 at SR: mono, unless its docstring says stereo.
"""
import numpy as np
from scipy import signal

from sd.audio import *  # noqa: F401,F403  (v1's blocks that stay)
from sd.audio import (SR, bp, env_adsr, env_exp, fade, follow_noise, hp, ks, lp, n_of, norm, pink, rng, splash,
                      stereo, sweep, t_of, tanh_sat, white)


# ----------------------------------------------------------------------------- basics
def pad_to(x, n):
    return x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))


def resonator(x, f, decay):
    """x driving a two-pole resonance at f Hz that rings 60 dB down in 'decay' seconds."""
    r = 10.0 ** (-3.0 / (max(decay, 1e-3) * SR))
    w = 2.0 * np.pi * f / SR
    return signal.lfilter([1.0 - r], [1.0, -2.0 * r * np.cos(w), r * r], x)


def mode_bank(freqs, t60s, amps, n, split=0.0, seed=0):
    """Impulse response of a bank of modes: sines from zero, each 60 dB down after its t60. With 'split'
    every mode is a close pair (a real object's twin modes, a hair apart): the pair beats slowly."""
    t = t_of(n)
    r = rng(seed)
    out = np.zeros(n)
    for f, d, a in zip(freqs, t60s, amps):
        if not 20.0 < f < SR * 0.45 or a <= 0.0:
            continue
        m = int(min(n, max(d * 1.2, 0.02) * SR))                    # 72 dB down: nothing left to compute
        tt = t[:m]
        y = np.sin(2.0 * np.pi * f * tt)
        if split > 0.0:
            y = y + r.uniform(0.3, 0.8) * np.sin(2.0 * np.pi * f * (1.0 + split * r.uniform(0.3, 1.0)) * tt)
        out[:m] += a * y * np.exp(-6.9 * tt / d)
    return out


def excite(exc, ir):
    return signal.fftconvolve(exc, ir)[: len(exc)]


def strike(n, power=1.0, seed=0, chatter=3, width=0.00025):
    """What a hard contact puts into an object: a pulse a quarter of a millisecond long (harder: shorter),
    then 'chatter' smaller bounces a few milliseconds apart."""
    r = rng(seed)
    x = np.zeros(n)
    w = max(3, int(width * SR / max(power, 0.5) ** 0.3))
    p = np.hanning(w + 2)[1:-1]
    x[:w] += p
    at, a = 0, 1.0
    for _ in range(chatter):
        at += int(r.uniform(0.0008, 0.006) * SR)
        a *= r.uniform(0.35, 0.65)
        if at + w < n:
            x[at:at + w] += a * p * r.choice((-1.0, 1.0))
    return x


def stick_slip(level, rate, seed=0):
    """Sliding friction: a train of tiny catches, one impulse each, of random size; 'rate' catches per
    second and 'level' (both per sample, or one number) scale it."""
    level = np.asarray(level, float)
    n = len(level)
    rate = np.broadcast_to(np.asarray(rate, float), (n,))
    r = rng(seed)
    rmax = float(rate.max()) + 1.0
    k = np.cumsum(r.exponential(1.0 / rmax, int(rmax * n / SR * 1.3) + 16) * SR).astype(int)
    k = k[k < n]
    k = k[r.random(len(k)) < rate[k] / rmax]
    x = np.zeros(n)
    np.add.at(x, k, r.uniform(0.2, 1.0, len(k)) * r.choice((-1.0, 1.0), len(k)) * level[k])
    return x


def grains(n, count, spread, lo, hi, seed=0):
    """Grit: 'count' tiny bursts, most of them in the first moments of 'spread' seconds."""
    r = rng(seed)
    x = np.zeros(n)
    at = np.minimum((r.exponential(spread / 2.5, count) * SR).astype(int), n - 1)
    np.add.at(x, at, r.uniform(0.2, 1.0, count) * r.choice((-1.0, 1.0), count))
    return bp(x, lo, hi, 2)


def rattle(n, seed=0, count=4, spread=0.06, lo=1800.0, hi=3400.0):
    """Little plates knocking together (lacquered armour scales, a buckle): each a short tick that rings."""
    r = rng(seed)
    out = np.zeros(n)
    m = n_of(0.08)
    for k in range(count):
        at = int(r.uniform(0.004, spread) * SR)
        f0 = r.uniform(lo, hi)
        x = mode_bank([f0, f0 * 1.52, f0 * 2.31, f0 * 3.07], [0.05, 0.04, 0.03, 0.02], [1.0, 0.5, 0.35, 0.2], m)
        c = n_of(0.001)
        x[:c] += hp(white(c, seed + 7 * k), 2500) * 0.6
        e = min(n, at + m)
        if e > at:
            out[at:e] += x[: e - at] * r.uniform(0.3, 1.0)
    return out


# ----------------------------------------------------------------------------- the place
_ER = dict(  # early reflections: (seconds, gain, how dark: low-pass Hz)
    court=[(0.0031, 0.55, 7000.0), (0.027, 0.42, 6000.0), (0.041, 0.38, 5000.0), (0.063, 0.33, 4500.0),
           (0.088, 0.28, 4000.0), (0.134, 0.30, 2800.0), (0.192, 0.16, 2000.0)],     # floor, walls, the hall's slap
    hall=[(0.045, 0.30, 3000.0), (0.11, 0.30, 2500.0), (0.17, 0.25, 2000.0), (0.26, 0.18, 1500.0)],
    near=[(0.0025, 0.50, 8000.0), (0.011, 0.30, 6000.0), (0.019, 0.25, 5000.0)])
_TAIL = dict(court=(2.4, 1.6, 0.55, 0.012), hall=(4.5, 3.4, 1.2, 0.03), near=(0.8, 0.5, 0.25, 0.004))


def impulse(kind="court", seed=3):
    """A stereo reverb impulse for the courtyard ('court'), the big dark space of slow motion ('hall') or
    close by ('near'): early reflections, each darker than the last, then a diffuse tail that builds up
    and dies sooner in the highs than in the lows."""
    seconds, t60_lo, t60_hi, pre = _TAIL[kind]
    n = n_of(seconds)
    t = t_of(n)
    bands = ((20.0, 250.0), (250.0, 1000.0), (1000.0, 3000.0), (3000.0, 8000.0), (8000.0, 20000.0))
    t60 = np.linspace(t60_lo, t60_hi, len(bands))
    out = []
    for ch in range(2):
        r = rng(seed + 31 * ch)
        nz = r.standard_normal(n)
        tail = np.zeros(n)
        for (lo_, hi_), d in zip(bands, t60):
            tail += bp(nz, lo_, min(hi_, SR * 0.45), 2) * np.exp(-6.9 * t / d)
        tail *= np.clip((t - pre) / 0.04, 0.0, 1.0) ** 2
        ir = tail * 0.35
        unit = np.zeros(n_of(0.004))
        unit[0] = 1.0
        for d, g, fc in _ER[kind]:
            i = int(d * (1.0 + r.uniform(-0.08, 0.08)) * SR)
            k = lp(unit, fc, 2)
            if i + len(k) < n:
                ir[i:i + len(k)] += g * r.choice((-1.0, 1.0)) * k / k.max()
        out.append(ir / np.sqrt(np.sum(ir ** 2)))
    return np.stack(out, axis=1)


_IRS = {}


def room(x, kind="court", wet=0.25):
    """Put a sound (mono or stereo) in the courtyard, the hall or close by."""
    if kind not in _IRS:
        _IRS[kind] = impulse(kind)
    ir = _IRS[kind]
    if x.ndim == 1:
        x = stereo(x)
    n = len(x) + len(ir) - 1
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)
    dry = np.zeros_like(y)
    dry[:len(x)] = x
    return ((1.0 - wet) * dry + wet * y * 3.0).astype(np.float32)[:n]


# ----------------------------------------------------------------------------- steel
_BETA = np.r_[4.7300, 7.8532, 10.9956, 14.1372, 17.2788, (np.arange(5, 40) + 0.5) * np.pi]
_BEAM = (_BETA / _BETA[0]) ** 2                                       # a free-free beam's modes: 1, 2.76, 5.40, 8.93, 13.3 ...


def blade(seed=0, size=1.0, hard=1.0, grip=1.0):
    """A katana's modes as it is held, (freqs, t60s, amps). size > 1: a heavier, lower blade; hard: how
    short the contact (higher modes reached); grip: how much the hands (or a bind) damp it."""
    r = rng(seed)
    F, W = [], []
    for f1, w in ((78.0, 0.3), (330.0, 1.0)):                        # bending across the thin side, across the wide side
        f = f1 / size * _BEAM * (1.0 + r.uniform(-0.015, 0.015, len(_BEAM)))
        f = f[f < 17000.0]
        F.append(f)
        W.append(w * r.uniform(0.15, 1.0, len(f)))
    F.append(3640.0 / size * np.arange(1, 5) * (1.0 + r.uniform(-0.01, 0.01, 4)))     # along its length
    W.append(0.35 * r.uniform(0.3, 1.0, 4))
    F.append(1065.0 / size * np.arange(1, 7) * (1.0 + r.uniform(-0.02, 0.02, 6)))     # twisting
    W.append(0.2 * r.uniform(0.2, 1.0, 6))
    F, W = np.concatenate(F), np.concatenate(W)
    rad = (F / 2000.0) ** 2 / (1.0 + (F / 2000.0) ** 2)               # a thin blade hardly sends its low modes into the air
    contact = 1.0 / (1.0 + (F / (7000.0 * hard)) ** 2)
    held = 0.45 + 0.55 * np.clip((F - 600.0) / 1800.0, 0.0, 1.0)      # the hand on the grip damps the lower bending modes most
    T = np.where(F < 600.0, 0.10, 1.1 * held / (1.0 + (F / 7000.0) ** 1.6)) * r.uniform(0.7, 1.3, len(F)) / grip
    return F, T, W * rad * contact


def clang(power=1.0, seed=0, slow=1.0):
    """Blade on blade: the contact's tick and crunch, both blades ringing (their modes, struck with chatter),
    the knock of the arms taking it. 'slow' < 1: slow motion, lower and longer."""
    r = rng(seed)
    s = max(slow, 0.25)
    n = n_of((1.1 + 0.6 * power) / s ** 0.6)
    exc = strike(n, power, seed, chatter=int(r.integers(2, 6)))
    ring = np.zeros(n)
    for b, (size, sign) in enumerate(((r.uniform(0.96, 1.04), 1.0), (r.uniform(1.02, 1.10), -0.85))):
        F, T, W = blade(seed * 7 + b, size, hard=0.9 + 0.3 * power)
        ring += sign * excite(exc, mode_bank(F * s ** 0.5, T * (0.8 + 0.3 * power) / s ** 0.8, W, n, split=0.0025, seed=seed + b))
    click = pad_to(hp(white(n_of(0.003), seed + 5), 2000) * env_exp(n_of(0.003), 0.003, 0.0001), n)
    crunch = pad_to(bp(white(n_of(0.04), seed + 6), 1500, 9000) * env_exp(n_of(0.04), 0.02 * power ** 0.5, 0.0003), n)
    burst = pad_to(lp(white(n_of(0.03), seed + 7), 400) * env_exp(n_of(0.03), 0.02, 0.001), n)
    knock = resonator(burst, 150.0 * s ** 0.5, 0.12 / s ** 0.5)
    out = norm(ring) + 0.45 * norm(click) + 0.25 * power * norm(crunch) + 0.3 * power * norm(knock)
    return norm(out, 0.9).astype(np.float32)


def shing(seconds=1.3, seed=0, rise=True):
    """A blade leaving its scabbard: steel rubbing the wood of the mouth (a hiss that rises) while the
    blade sings from the catches, then rings free as the point leaves."""
    n = n_of(seconds)
    t = t_of(n)
    m = n_of(0.30)
    u = np.clip(t / 0.30, 0.0, 1.0)
    lvl = np.where(t < 0.30, 0.3 + 0.7 * u ** 1.2, 0.0)
    exc = stick_slip(lvl, 900.0 + 6000.0 * u ** 1.3 if rise else 4000.0, seed) * 0.35
    exc[m] += 1.0
    F, T, W = blade(seed + 3, 1.0, hard=1.4)
    ring = excite(exc, mode_bank(F, T * 1.2, W, n, split=0.0025, seed=seed))
    lv = np.concatenate([np.linspace(0.15, 1.0, m) ** 1.4, np.exp(-6.9 * t[: n - m] / 0.05)])
    hiss = follow_noise(lv, np.concatenate([np.linspace(2200.0, 5200.0, m), np.full(n - m, 5200.0)]), width=0.5, seed=seed + 1)
    return norm(fade(norm(ring) * 0.85 + norm(hiss) * 0.3, 0.002, 0.25), 0.8).astype(np.float32)


def guard_click(seed=0):
    """The thumb pushing the guard off the scabbard's mouth: wood, and the collar's steel held tight."""
    n = n_of(0.15)
    exc = strike(n, 0.6, seed, chatter=1, width=0.0004)
    wood = excite(exc, mode_bank([640.0, 1180.0, 1870.0, 2650.0], [0.035, 0.03, 0.022, 0.016], [1.0, 0.6, 0.4, 0.25], n))
    F, T, W = blade(seed + 1, 1.0, hard=1.2)
    steel = excite(exc, mode_bank(F, T * 0.25, W, n))
    tick = pad_to(hp(white(n_of(0.0015), seed + 2), 2500) * np.hanning(n_of(0.0015)), n)
    return norm(norm(wood) * 0.7 + norm(steel) * 0.35 + norm(tick) * 0.4, 0.8).astype(np.float32)


def grind(seconds, seed=0):
    """Two blades in a bind, sliding under pressure: stick-slip through both (damped by the pressure),
    the friction's hiss, a thin squeal where it locks."""
    n = n_of(seconds)
    t = t_of(n)
    lvl = np.clip(t / 0.05, 0.0, 1.0) * np.clip((seconds - t) / 0.12, 0.0, 1.0) * (0.75 + 0.25 * np.sin(2 * np.pi * 7.0 * t))
    exc = stick_slip(lvl, 2500.0 + 1500.0 * np.sin(2 * np.pi * 1.3 * t), seed)
    out = np.zeros(n)
    for b in range(2):
        F, T, W = blade(seed * 3 + b, 1.0 + 0.06 * b, hard=1.3, grip=2.0)
        out += excite(exc, mode_bank(F, T, W, n, seed=seed + b))
    fr = follow_noise(lvl, 4000.0 + 1500.0 * np.sin(2 * np.pi * 1.3 * t), width=0.35, seed=seed + 5)
    sq = np.sin(sweep(3200, 3700, n)) * lvl * (1.0 + 0.3 * np.sin(2 * np.pi * 9.0 * t))
    return norm(norm(out) + 0.35 * norm(fr) + 0.08 * sq, 0.8).astype(np.float32)


def sparks(seconds=0.5, density=120, seed=0):
    """A spray of sparks: tiny dry crackles, most at once, thinning out, and a faint fizz."""
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    c = max(1, int(density * seconds))
    x = np.zeros(n)
    np.add.at(x, (r.random(c) ** 2.2 * (n - 1)).astype(int), r.lognormal(-1.0, 0.6, c) * r.choice((-1.0, 1.0), c))
    fizz = hp(white(n, seed + 1), 5000) * np.exp(-6.9 * t / max(seconds * 0.6, 0.05)) * 0.03
    return norm(bp(x, 2500, 9000, 2) + fizz, 0.6).astype(np.float32)


# ----------------------------------------------------------------------------- moving things
def whoosh(level, centre, seed=0, kind="air"):
    """A swing through the air, loudness and pitch following curves (per sample): the rush, the whistle a
    thin edge sheds (its pitch rises with the speed), and for a big blade the push of air.
    kind: 'air' (light, high), 'deep' (big, low), 'whip' (with a crack at the peak)."""
    width = dict(air=0.55, deep=0.85, whip=0.4)[kind]
    lvl = np.asarray(level, float)
    cen = np.asarray(centre, float)
    out = follow_noise(lvl, cen, width=width, seed=seed, colour="pink" if kind == "deep" else "white")
    out += (0.2 if kind == "deep" else 0.35) * follow_noise(np.clip(lvl, 0, None) ** 1.3, cen * 1.05, width=0.07, seed=seed + 7)
    if kind == "deep":
        out += 0.5 * follow_noise(np.clip(lvl, 0, None) ** 2, np.full(len(lvl), 150.0), width=0.6, seed=seed + 9, colour="pink")
    if kind == "whip":
        k = int(np.argmax(lvl))
        c = hp(white(n_of(0.008), seed + 4), 3000) * env_exp(n_of(0.008), 0.008, 0.0002)
        e = min(len(out), k + len(c))
        out[k:e] += c[: e - k] * 3.0 * float(np.max(lvl))
    return out.astype(np.float32)


def step(surface="stone", weight=1.0, seed=0, wet=0.6, armour=0.0):
    """A footfall on wet stone: heel, then the ball of the foot 70-100 ms later; each a thud of the body
    (noise through its resonance), the sole's tick and the grit crunching under it; water; for the Ronin
    the little plates of his armour."""
    r = rng(seed)
    n = n_of(0.5)
    out = np.zeros(n)
    for k, (at, g) in enumerate(((0.0, 1.0), (r.uniform(0.07, 0.1), 0.5))):
        a = n_of(at)
        m = n - a
        burst = pad_to(lp(white(n_of(0.02), seed + 10 + k), 500) * env_exp(n_of(0.02), 0.012, 0.001), m)
        thud = norm(resonator(burst, r.uniform(85.0, 120.0) / weight ** 0.3, 0.06 * weight)) * weight ** 1.2
        tick = norm(pad_to(hp(white(n_of(0.006), seed + 20 + k), 1200) * env_exp(n_of(0.006), 0.005, 0.0002), m))
        grit = norm(grains(m, int(r.integers(8, 22)), 0.05, 1800.0, 9000.0, seed=seed + 30 + k))
        out[a:] += g * (0.55 * thud + 1.0 * tick / weight ** 0.5 + 0.6 * grit / weight ** 0.5)
    if wet > 0.0:
        out += splash(0.35, seed + 3)[:n] * 0.3 * wet / weight
    if armour > 0.0:
        out += norm(rattle(n, seed + 5, int(r.integers(3, 7)))) * 0.3 * armour
    return norm(out * env_exp(n, 0.45, 0.0005), 0.9).astype(np.float32)


def cloth(level, seed=0):
    """Cloth moving, loudness following 'level' (per sample): the air it pushes, its friction crackle,
    and on fast moves an uneven flutter."""
    lv = np.clip(np.asarray(level, float), 0.0, 1.5)
    n = len(lv)
    swish = follow_noise(lv, 650.0 + 1100.0 * np.clip(lv, 0, 1), width=0.9, seed=seed, colour="pink")
    crackle = bp(stick_slip(lv, 60.0 + 900.0 * np.clip(lv, 0, 1), seed + 1), 900, 6000, 2)
    crackle *= 0.5 * np.sqrt(np.mean(swish ** 2)) / (np.sqrt(np.mean(crackle ** 2)) + 1e-12)
    jit = lp(white(n, seed + 2), 22.0)
    flut = 1.0 + 0.35 * np.clip(lv - 0.6, 0.0, 1.0) * jit / (np.abs(jit).max() + 1e-12)
    return (lp(swish * flut * 0.8 + crackle, 6500) * 0.8).astype(np.float32)


def body_hit(power=1.0, seed=0):
    """A kick landing: the body's deep thud (noise through it, not a tone), the film punch (a fast drop,
    short), the slap of the contact, the cloth snapping tight, the armour's plates."""
    n = n_of(0.7)
    burst = pad_to(lp(white(n_of(0.012), seed), 900) * np.hanning(n_of(0.012)), n)
    thud = norm(resonator(burst, 92.0, 0.16)) + 0.5 * norm(resonator(burst, 205.0, 0.08))
    m = n_of(0.2)
    punch = pad_to(np.sin(sweep(150.0, 52.0, m, 0.4)) * env_exp(m, 0.15, 0.001), n)
    slap = pad_to(bp(white(n_of(0.04), seed + 1), 500, 4500) * env_exp(n_of(0.04), 0.02, 0.0003), n)
    snap = pad_to(bp(white(n_of(0.06), seed + 2), 1500, 7000) * env_exp(n_of(0.06), 0.035, 0.001), n)
    armour = rattle(n, seed + 3, 4, 0.05, 900.0, 2200.0)
    out = 0.9 * norm(thud) + 0.6 * power * punch + 0.9 * norm(slap) + 0.5 * norm(snap) + 0.35 * norm(armour)
    return norm(tanh_sat(out * 1.2, 1.4), 0.9).astype(np.float32)


# ----------------------------------------------------------------------------- instruments
_DRUM = np.array([1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501])    # a membrane's modes (Bessel zeros)
_DRUM_A = np.array([1.0, 0.55, 0.38, 0.28, 0.2, 0.14, 0.1, 0.07])


def taiko(kind="o", vel=1.0, seed=0):
    """Japanese drums. 'o': o-daiko (big, deep), 'nagado': the middle drum, 'shime': small, tight, high,
    'rim': the stick on the wooden rim (kachi). The skin's modes start sharp and settle as it relaxes
    (harder: more), the stick's contact, the shell, and for the big drum the air pushed out."""
    r = rng(seed)
    v = float(np.clip(vel, 0.1, 1.2))
    if kind == "rim":
        n = n_of(0.12)
        exc = strike(n, 1.0, seed, chatter=1, width=0.0003)
        m = excite(exc, mode_bank([r.uniform(1500, 1750), r.uniform(2700, 2950), r.uniform(4000, 4300)], [0.05, 0.035, 0.025], [1.0, 0.5, 0.3], n))
        return norm(norm(m) + 0.3 * norm(pad_to(hp(white(n_of(0.002), seed), 3000), n)), 0.7 * vel).astype(np.float32)
    f0, dur, t60, glide, shell_f, stick_ms, stick_hz = {
        "o": (r.uniform(52.0, 60.0), 1.6, 1.0, 0.12, 190.0, 6.0, 2500.0),
        "nagado": (r.uniform(100.0, 120.0), 1.0, 0.6, 0.10, 260.0, 4.0, 3500.0),
        "shime": (r.uniform(340.0, 390.0), 0.4, 0.17, 0.05, 900.0, 2.0, 5000.0)}[kind]
    n = n_of(dur)
    t = t_of(n)
    skin = np.zeros(n)
    for k, (rr, a) in enumerate(zip(_DRUM, _DRUM_A)):
        f = f0 * rr * (1.0 + glide * v * np.exp(-t / 0.05))
        skin += a * (0.6 + 0.4 * v) ** k * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-6.9 * t / (t60 / (1.0 + 0.8 * k)))
    m = n_of(stick_ms / 1000.0)
    stick = pad_to(lp(white(m, seed + 1), stick_hz) * np.hanning(m), n)
    shell = resonator(stick, shell_f * r.uniform(0.95, 1.05), 0.09) + 0.6 * resonator(stick, shell_f * 1.72, 0.06)
    out = norm(skin) + (0.9 if kind == "shime" else 0.6) * v * norm(stick) + 0.25 * norm(shell)
    if kind == "o":
        out += 0.5 * norm(pad_to(lp(white(n_of(0.06), seed + 2), 160) * env_exp(n_of(0.06), 0.05, 0.002), n))
    return norm(tanh_sat(out, 1.2 + 0.5 * v), 0.95 * vel).astype(np.float32)


def taiko_ens(kind="o", vel=1.0, players=3, seed=0, spread=0.5):
    """Several drummers on one beat (stereo): each drum its own, each player a hair early or late."""
    r = rng(seed)
    parts = []
    for p in range(players):
        x = taiko(kind, vel * r.uniform(0.85, 1.0), seed=seed * 13 + p)
        pan = 0.0 if players == 1 else (p / (players - 1) - 0.5) * 2.0 * spread
        parts.append(stereo(np.pad(x, (n_of(r.uniform(0.0, 0.014)), 0)), pan))
    out = np.zeros((max(len(p_) for p_ in parts), 2), np.float32)
    for p_ in parts:
        out[: len(p_)] += p_
    return (out / players ** 0.5).astype(np.float32)


def koto(freq, seconds=2.2, vel=1.0, seed=0):
    """A koto string plucked near the bridge with an ivory pick, ringing through the instrument's body."""
    s = ks(freq, seconds, damp=0.998, bright=0.6, seed=seed)
    d = max(1, int(SR / freq * 0.12))
    s = s - 0.55 * np.r_[np.zeros(d), s[:-d]]
    n = len(s)
    t = t_of(n)
    pick = pad_to(hp(white(n_of(0.004), seed + 1), 2500) * env_exp(n_of(0.004), 0.004, 0.0001), n)
    body = sum(g * resonator(s, f, dcy) for f, dcy, g in ((190.0, 0.12, 0.5), (330.0, 0.1, 0.4), (560.0, 0.08, 0.3), (930.0, 0.06, 0.2)))
    out = norm(s) + 0.35 * norm(body) + 0.25 * norm(pick)
    return norm(out * np.exp(-6.9 * t / seconds), 0.7 * vel).astype(np.float32)


def flute(freq, seconds, vel=1.0, seed=0, bend=True):
    """A shakuhachi-like bamboo flute: the breath swells in and is never steady, the note starts flat and
    lifts, breath noise sits on its harmonics, a soft chiff, a late vibrato."""
    n = n_of(seconds)
    t = t_of(n)
    e = env_adsr(n, min(0.14, seconds * 0.3), 0.25, 0.8, min(0.35, seconds * 0.4))
    wob = lp(white(n, seed + 1), 4.0)
    b = np.clip(e * (1.0 + 0.12 * wob / (np.abs(wob).max() + 1e-12)), 0.0, 1.3)
    f = freq * np.ones(n)
    if bend:
        f *= 2.0 ** ((-0.7 * np.exp(-t / 0.13)) / 12.0)
    vib = np.clip((t - seconds * 0.45) / (seconds * 0.3), 0, 1) * 0.005 * np.sin(2 * np.pi * 5.0 * t)
    ph = 2 * np.pi * np.cumsum(f * (1 + vib)) / SR
    tone = np.sin(ph) + 0.30 * b * np.sin(2 * ph) + 0.12 * b ** 2 * np.sin(3 * ph) + 0.05 * b ** 2 * np.sin(4 * ph)
    air = sum(follow_noise(b * (0.30 / h), f * h, width=0.035, seed=seed + 10 + h) for h in (1, 2, 3))
    rush = follow_noise(b * 0.25, f * 3.5, width=0.9, seed=seed + 20)
    chiff = bp(white(n, seed + 2), 1500, 6000) * np.exp(-6.9 * t / 0.07) * 0.25
    return norm(tone * b + air + rush + chiff, 0.6 * vel).astype(np.float32)


def cymbal(seconds=2.5, seed=0):
    """A big cymbal (or a gong's wash): a crowd of inharmonic modes and a bright hiss."""
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    F = np.sort(r.uniform(350.0, 15000.0, 120))
    T = np.clip(3.0 / (1.0 + F / 4000.0), 0.4, 2.5) * np.clip(F / 1500.0, 0.3, 1.0) * r.uniform(0.7, 1.3, len(F))
    W = r.uniform(0.2, 1.0, len(F)) * (F / 3000.0) ** 0.5
    wash = hp(white(n, seed + 1), 2500) * np.exp(-6.9 * t / (seconds * 0.8))
    return norm(norm(mode_bank(F, T, W, n, seed=seed)) * 0.6 + norm(wash) * 0.4, 0.8).astype(np.float32)


def reverse_cymbal(seconds=1.0, seed=0):
    """A cymbal played backwards: the swell that sucks toward a hit."""
    x = cymbal(seconds + 0.3, seed)[: n_of(seconds)]
    return norm(fade(x[::-1].copy(), 0.05, 0.004), 0.8).astype(np.float32)


def suck_in(seconds=0.9, seed=0):
    n = n_of(seconds)
    t = t_of(n)
    u = t / seconds
    air = follow_noise(u ** 3, 400.0 + 5000.0 * u ** 2, width=0.8, seed=seed + 1)
    tone = np.sin(sweep(110, 330, n, 2.0)) * u ** 4 * 0.35
    return norm(norm(reverse_cymbal(seconds, seed)) * 0.7 + norm(air) * 0.4 + tone, 0.8).astype(np.float32)


def riser(seconds=1.5, seed=0):
    """Tension rising into a hit: air climbing, a tone climbing, a reversed cymbal arriving with it."""
    n = n_of(seconds)
    t = t_of(n)
    u = t / seconds
    noise = follow_noise(u ** 2.5, 500.0 + 7000.0 * u ** 2, width=0.7, seed=seed)
    tone = np.sin(sweep(80, 640, n, 1.6)) * u ** 3 * 0.4
    rc = reverse_cymbal(min(seconds, 1.6), seed + 1)
    out = norm(noise) + tone
    out[n - len(rc):] += 0.6 * rc
    return norm(out, 0.8).astype(np.float32)


def braam(freq=55.0, seconds=2.2, seed=0):
    """The trailer's low brass hit: stacked, detuned saws through a filter that opens fast and closes
    slowly, a formant for the brass's bite, driven hard."""
    r = rng(seed)
    n = n_of(seconds)
    t = t_of(n)
    v = np.zeros(n)
    for mult, g in ((0.5, 0.7), (1.0, 1.0), (1.5, 0.45), (2.0, 0.6), (3.0, 0.3)):
        for d in (-0.003, 0.0, 0.0035):
            ph = (freq * mult * (1 + d) * t + r.random()) % 1.0
            v += g * (2.0 * ph - 1.0)
    cut = 500.0 + 2600.0 * np.exp(-t / 0.4)
    y = np.zeros(n)
    hop = n_of(0.02)
    zi = None
    for k in range(0, n, hop):
        S = signal.butter(2, float(cut[k]), btype="lowpass", fs=SR, output="sos")
        seg = v[k:k + hop]
        if zi is None:
            zi = np.zeros((S.shape[0], 2))
        y[k:k + len(seg)], zi = signal.sosfilt(S, seg, zi=zi)
    e = env_adsr(n, 0.012, 0.35, 0.7, seconds * 0.5)
    return norm(tanh_sat((y + 1.0 * bp(y, 450, 1400)) * e, 3.0), 0.9).astype(np.float32)


def trailer_hit(seconds=3.0, seed=0, f0=55.0):
    """The trailer's big hit (stereo): four drummers on one beat, a slowed blade slam, a sub that drops,
    a burst of air."""
    n = n_of(seconds)
    t = t_of(n)
    out = np.zeros((n, 2), np.float32)
    drums = taiko_ens("o", 1.0, players=4, seed=seed, spread=0.6)[:n]
    out[: len(drums)] += drums * 0.9
    sub = np.sin(sweep(f0 * 1.25, f0 * 0.6, n, 0.5)) * np.exp(-6.9 * t / (seconds * 0.7)) * np.clip(t / 0.004, 0, 1)
    out += stereo(norm(sub) * 0.5 + 0.45 * norm(bp(np.tanh(4.0 * sub), 180.0, 900.0, 2)), 0.0)   # its harmonics: the boom a phone can play
    slam = clang(1.8, seed=seed + 3, slow=0.5)[:n]
    out[: len(slam)] += stereo(slam * 0.7, 0.0, 0.5)
    crash = hp(cymbal(min(seconds, 2.5), seed + 5), 1500.0)[:n]
    out[: len(crash)] += stereo(norm(crash) * 0.4, 0.0, 0.9)
    out += stereo(norm(lp(pink(n, seed + 4), 3500) * env_exp(n, 0.35, 0.002)) * 0.3, 0.0, 0.8)
    return (out * (0.95 / np.abs(out).max())).astype(np.float32)


def pulse(freq, seconds=0.2, bright=900.0, seed=0):
    """One note of the trailer's low ticking ostinato: two saws a hair apart, a short filtered pluck."""
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    s = (2.0 * ((freq * t + r.random()) % 1.0) - 1.0) + 0.6 * (2.0 * ((freq * 1.004 * t + r.random()) % 1.0) - 1.0)
    return norm(tanh_sat(lp(s, bright, 2) * env_exp(n, seconds * 0.9, 0.003), 1.5), 0.6).astype(np.float32)


def sub_boom(seconds=1.6, f0=58.0, seed=0):
    """A sub drop with its own harmonics (driven hard, so a phone plays the boom's growl) and a knock on top."""
    n = n_of(seconds)
    t = t_of(n)
    s = np.sin(sweep(f0 * 1.8, f0, n, 0.35)) * np.exp(-6.9 * t / (seconds * 0.8)) * np.clip(t / 0.004, 0, 1)
    knock = pad_to(bp(white(n_of(0.03), seed + 1), 300.0, 2500.0) * env_exp(n_of(0.03), 0.025, 0.0005), n)
    return norm(norm(tanh_sat(s, 1.3)) + 0.25 * norm(bp(np.tanh(4.0 * s), 180.0, 900.0, 2)) + 0.2 * norm(knock), 0.95).astype(np.float32)


def bell(f0=55.0, seconds=7.0, seed=0):
    """A great temple bell struck from outside with a wooden beam: the beam's soft thud, the hum and the
    prime (slowly beating pairs), and the bronze's higher partials that carry it across the courtyard."""
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    ratios = [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433, 6.796, 8.215, 9.68, 11.19]
    decays = [8.0, 7.0, 5.0, 4.0, 3.0, 2.2, 2.0, 1.6, 1.0, 0.8, 0.6, 0.45, 0.35, 0.28]
    amps = [0.5, 1.0, 0.6, 0.45, 0.4, 0.3, 0.25, 0.22, 0.18, 0.14, 0.11, 0.08, 0.06, 0.04]
    F = [f0 * x_ for x_ in ratios]
    hum = mode_bank(F, decays, amps, n, split=0.004, seed=seed)
    thud = lp(white(n, seed + 2), 300) * np.exp(-6.9 * t / 0.15) * 0.4
    strike_ = pad_to(bp(white(n_of(0.05), seed + 3), 400.0, 2500.0) * env_exp(n_of(0.05), 0.04, 0.001), n) * 0.25
    return norm(norm(hum) + thud + strike_, 0.9).astype(np.float32)


def drone(freq, seconds, seed=0, dark=900.0):
    """A low bowed drone: detuned saw voices with an octave and a fifth above (a small speaker hears
    those), low-passed, slowly breathing."""
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    out = np.zeros(n)
    for mult, g in ((1.0, 1.0), (2.0, 0.45), (3.0, 0.25)):
        for d in (-0.006, 0.0, 0.0045):
            ph = (freq * mult * (1 + d) * t + r.random()) % 1.0
            out += g * (2.0 * ph - 1.0)
    out += 0.5 * np.sin(2 * np.pi * freq * 0.5 * t)
    out = lp(out, max(dark, 700.0), 2) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.23 * t))
    return norm(out * env_adsr(n, min(1.2, seconds * 0.3), 0.5, 0.9, min(1.5, seconds * 0.35)), 0.5).astype(np.float32)
