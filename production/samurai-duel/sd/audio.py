"""Sound made in code (numpy/scipy): the building blocks, the film's sound effects and its instruments.

Every function returns a float32 array at SR, mono (n,) or stereo (n, 2). Nothing is sampled from a
recording: noise, decaying partials, plucked strings and filters only, so the whole track is ours.

The palette (the film's sound identity): three families and the room.
    metal     the blades: clash by power, the draw, the guard's click, the grind, sparks, the long ring
    elements  fire for the Oni's blade (roar and crackle), water for the Ronin's (swish, splash)
    wood/skin the drums, the plucked strings, footfalls on wet stone, the hat, the mask
    room      a stone courtyard at night: short early reflections and a 1.4 s tail; big hits get a
              longer, darker hall so they hang in slow motion
"""
import math

import numpy as np
from scipy import signal

SR = 48000


# ----------------------------------------------------------------------------- basics
def rng(seed):
    return np.random.default_rng(seed)


def n_of(seconds):
    return max(1, int(round(seconds * SR)))


def t_of(n):
    return np.arange(n, dtype=np.float64) / SR


def white(n, seed=0):
    return rng(seed).standard_normal(n)


def pink(n, seed=0):
    """1/f noise by filtering white noise (Paul Kellet's economy filter)."""
    w = white(n, seed)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1.0, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, w) * 8.0


def brown(n, seed=0):
    x = np.cumsum(white(n, seed))
    x = signal.lfilter([1.0, -1.0], [1.0, -0.995], x)
    return x / (np.abs(x).max() + 1e-9)


def sos(kind, f, order=2):
    f = np.atleast_1d(np.asarray(f, dtype=float))
    f = np.clip(f, 10.0, SR * 0.49)
    return signal.butter(order, f if len(f) > 1 else f[0], btype=kind, fs=SR, output="sos")


def lp(x, f, order=2):
    return signal.sosfilt(sos("lowpass", f, order), x, axis=0)


def hp(x, f, order=2):
    return signal.sosfilt(sos("highpass", f, order), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(sos("bandpass", (lo, hi), order), x, axis=0)


def norm(x, peak=1.0):
    m = np.abs(x).max()
    return x * (peak / m) if m > 0 else x


def env_exp(n, decay, attack=0.002):
    """An attack then an exponential decay (decay = seconds to fall 60 dB)."""
    t = t_of(n)
    a = np.clip(t / max(attack, 1e-5), 0.0, 1.0)
    return a * np.exp(-6.9 * t / max(decay, 1e-4))


def env_adsr(n, a, d, s, r):
    t = t_of(n)
    T = n / SR
    e = np.where(t < a, t / max(a, 1e-5), np.where(t < a + d, 1.0 - (1.0 - s) * (t - a) / max(d, 1e-5), s))
    rel = np.clip((T - t) / max(r, 1e-5), 0.0, 1.0)
    return e * rel


def fade(x, fin=0.003, fout=0.01):
    n = len(x)
    e = np.ones(n)
    a, b = min(n, n_of(fin)), min(n, n_of(fout))
    e[:a] = np.linspace(0.0, 1.0, a)
    e[n - b:] *= np.linspace(1.0, 0.0, b)
    return x * (e[:, None] if x.ndim == 2 else e)


def sweep(f0, f1, n, curve=1.0):
    """Phase of a tone gliding from f0 to f1 Hz over n samples (exponential glide)."""
    u = np.linspace(0.0, 1.0, n) ** curve
    f = f0 * (f1 / f0) ** u
    return 2.0 * np.pi * np.cumsum(f) / SR


def modes(freqs, decays, amps, n, seed=0, jitter=0.0):
    """Struck object: decaying partials (modal synthesis)."""
    t = t_of(n)
    r = rng(seed)
    out = np.zeros(n)
    for f, d, a in zip(freqs, decays, amps):
        f = f * (1.0 + jitter * r.uniform(-1.0, 1.0))
        out += a * np.sin(2.0 * np.pi * f * t + r.uniform(0, 2 * np.pi)) * np.exp(-6.9 * t / d)
    return out


def ks(freq, seconds, damp=0.996, bright=0.6, seed=0):
    """Karplus-Strong plucked string."""
    n = n_of(seconds)
    p = max(2, int(round(SR / freq - 0.5)))                         # the two-point average adds half a sample of delay
    buf = lp(rng(seed).uniform(-1.0, 1.0, p), 1500 + 9000 * bright, 1)
    blocks, before, total = [], 0.0, 0
    while total < n:                                                 # one period at a time: y[k] = damp * (y[k-p] + y[k-p-1]) / 2
        blocks.append(buf)
        total += p
        new = damp * 0.5 * (buf + np.concatenate([[before], buf[:-1]]))
        before, buf = buf[-1], new
    return np.concatenate(blocks)[:n]


def tanh_sat(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def stereo(x, pan=0.0, width=0.0, seed=0):
    """Mono to stereo with equal-power pan (-1 left .. 1 right) and an optional decorrelated width."""
    pan = float(np.clip(pan, -1.0, 1.0))
    a = (pan + 1.0) * math.pi / 4.0
    L, R = x * math.cos(a), x * math.sin(a)
    if width > 0.0:
        d = n_of(0.011)
        side = np.concatenate([np.zeros(d), x[:-d]]) if len(x) > d else x
        L, R = L + width * 0.35 * side, R - width * 0.35 * side
    return np.stack([L, R], axis=1).astype(np.float32)


def pan_track(x, pans):
    """Mono to stereo with a pan that moves (pans: one value per sample, -1..1)."""
    a = (np.clip(pans, -1.0, 1.0) + 1.0) * math.pi / 4.0
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1).astype(np.float32)


def reverse(x):
    return x[::-1].copy()


def resample_speed(x, speed):
    """Play back faster (speed > 1, higher and shorter) or slower (lower and longer)."""
    if abs(speed - 1.0) < 1e-3:
        return x
    n = max(2, int(round(len(x) / speed)))
    return signal.resample(x, n, axis=0)


# ----------------------------------------------------------------------------- the room
def impulse(seconds, decay, seed=0, dark=4000.0, early=True, stereo_=True):
    """A reverb impulse: early reflections off stone, then a diffuse tail that darkens as it dies."""
    n = n_of(seconds)
    t = t_of(n)
    out = []
    for ch in range(2 if stereo_ else 1):
        r = rng(seed + 31 * ch)
        tail = r.standard_normal(n) * np.exp(-6.9 * t / decay)
        lo = lp(tail, dark, 1)
        hi = tail - lo
        mix = lo + hi * np.exp(-6.9 * t / (decay * 0.35))
        if early:
            for k in range(9):
                d = int(r.uniform(0.006, 0.055) * SR)
                mix[d] += r.uniform(0.3, 0.8) * (-1) ** k
        mix[:n_of(0.004)] *= np.linspace(0.0, 1.0, n_of(0.004))
        out.append(mix / np.sqrt(np.sum(mix ** 2)))
    return np.stack(out, axis=1) if stereo_ else out[0]


_IRS = {}


def room(x, kind="court", wet=0.25):
    """Put a sound (stereo) in the courtyard ('court', 1.4 s) or the big dark hall for slow motion ('hall', 3.2 s)."""
    if kind not in _IRS:
        _IRS[kind] = impulse(2.2, 1.4, seed=3, dark=5000.0) if kind == "court" else impulse(4.5, 3.2, seed=7, dark=2200.0)
    ir = _IRS[kind]
    if x.ndim == 1:
        x = stereo(x)
    n = len(x) + len(ir) - 1
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)
    dry = np.zeros_like(y)
    dry[:len(x)] = x
    return ((1.0 - wet) * dry + wet * y * 3.0).astype(np.float32)[:n]


# ----------------------------------------------------------------------------- moving sounds
def follow_noise(level, centre, width=0.6, seed=0, colour="white", hop=256):
    """Noise whose loudness and pitch follow curves given per sample: band-passed around 'centre' Hz
    (a ratio band of +-width octaves), shaped in the frequency domain one short frame at a time."""
    n = len(level)
    x = white(n, seed) if colour == "white" else pink(n, seed)
    f, tt, Z = signal.stft(x, fs=SR, nperseg=hop * 4, noverlap=hop * 3, boundary="even")
    idx = np.clip((tt * SR).astype(int), 0, n - 1)
    c = np.maximum(np.asarray(centre)[idx], 30.0)
    lf = np.log2(np.maximum(f, 1.0))[:, None]
    g = np.exp(-0.5 * ((lf - np.log2(c)[None, :]) / max(width, 0.05)) ** 2)
    _, y = signal.istft(Z * g, fs=SR, nperseg=hop * 4, noverlap=hop * 3, boundary=True)
    y = y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)))
    y = y / (np.std(y) + 1e-9)
    return y * np.asarray(level)


def curve(points, n):
    """A per-sample curve through (seconds, value) points."""
    pts = sorted(points)
    ts = np.array([p[0] for p in pts]) * SR
    vs = np.array([p[1] for p in pts], dtype=float)
    return np.interp(np.arange(n), ts, vs)


# ----------------------------------------------------------------------------- metal
def clang(power=1.0, seed=0, slow=1.0):
    """Blade on blade: a hard click, a cluster of inharmonic partials that ring and beat, a low knock
    from the arms taking the blow. 'slow' < 1 stretches it (slow motion: lower, longer)."""
    r = rng(seed)
    dur = (0.9 + 0.5 * power) / max(slow, 0.25) ** 0.6
    n = n_of(dur)
    base = r.uniform(1750, 2300) * (0.9 if power > 1.3 else 1.0)
    ratios = np.array([1.0, 1.47, 2.09, 2.56, 2.99, 3.71, 4.13])
    freqs = base * ratios * slow ** 0.5
    dec = np.array([0.55, 0.42, 0.33, 0.28, 0.22, 0.16, 0.12]) * (0.8 + 0.4 * power) / max(slow, 0.25) ** 0.8
    amps = np.array([1.0, 0.7, 0.55, 0.45, 0.35, 0.25, 0.2]) * r.uniform(0.8, 1.2, len(ratios))
    ring = modes(freqs, dec, amps, n, seed=seed, jitter=0.01)
    ring += 0.6 * modes(freqs * 1.006, dec, amps * 0.7, n, seed=seed + 1)      # a second blade a hair off: beating
    click = hp(white(n_of(0.006), seed + 2), 2500) * env_exp(n_of(0.006), 0.006, 0.0002)
    knock = np.sin(sweep(260 * slow ** 0.5, 90 * slow ** 0.5, n_of(0.18))) * env_exp(n_of(0.18), 0.16, 0.001)
    out = np.zeros(n)
    out[:len(click)] += click * 1.6
    out[:len(knock)] += knock * 0.9 * power
    out += ring * 0.55
    return norm(out, 0.9).astype(np.float32)


def shing(seconds=1.3, seed=0, rise=True):
    """A blade leaving its scabbard: a scrape that rises, then the blade rings in the air."""
    n = n_of(seconds)
    t = t_of(n)
    scrape_n = n_of(0.32)
    lvl = np.concatenate([np.linspace(0.2, 1.0, scrape_n) ** 1.5, np.exp(-6.9 * t[:n - scrape_n] / 0.08)])
    centre = np.concatenate([np.linspace(2600, 6200, scrape_n) if rise else np.full(scrape_n, 4200.0), np.full(n - scrape_n, 6200.0)])
    scrape = follow_noise(lvl, centre, width=0.35, seed=seed)
    comb = modes([3150, 4720, 6230, 7810, 9120], [0.9, 0.7, 0.55, 0.4, 0.3], [1.0, 0.8, 0.6, 0.4, 0.25], n, seed=seed + 3)
    ring_env = np.clip((t - 0.26) / 0.04, 0.0, 1.0)
    out = scrape * 0.35 + comb * ring_env * 0.5
    return norm(fade(out, 0.004, 0.2), 0.8).astype(np.float32)


def guard_click(seed=0):
    """The thumb pushing the guard off the scabbard's mouth: a small hard 'chk'."""
    n = n_of(0.12)
    m = modes([2850, 4310, 6020], [0.05, 0.04, 0.03], [1.0, 0.6, 0.4], n, seed=seed)
    c = hp(white(n_of(0.004), seed), 3000) * env_exp(n_of(0.004), 0.004, 0.0001)
    m[:len(c)] += c * 2.0
    wood = modes([620, 1180], [0.04, 0.03], [0.6, 0.3], n, seed=seed + 1)
    return norm(m + wood, 0.8).astype(np.float32)


def grind(seconds, seed=0):
    """Blade sliding on blade under pressure: a screeching resonant scrape with a moving pitch."""
    n = n_of(seconds)
    t = t_of(n)
    lvl = np.clip(t / 0.05, 0.0, 1.0) * np.clip((seconds - t) / 0.12, 0.0, 1.0) * (0.75 + 0.25 * np.sin(2 * np.pi * 7.0 * t))
    centre = 3000 + 1400 * np.sin(2 * np.pi * 1.3 * t) + 600 * np.sin(2 * np.pi * 5.1 * t)
    s = follow_noise(lvl, centre, width=0.18, seed=seed)
    squeal = np.sin(sweep(3300, 3900, n)) * lvl * 0.25 * (1 + 0.3 * np.sin(2 * np.pi * 11 * t))
    return norm(s + squeal, 0.8).astype(np.float32)


def sparks(seconds=0.5, density=120, seed=0):
    """A spray of sparks: tiny bright crackles that thin out."""
    n = n_of(seconds)
    r = rng(seed)
    out = np.zeros(n)
    count = int(density * seconds)
    for _ in range(count):
        at = int((r.random() ** 2.2) * (n - n_of(0.01)))
        ln = n_of(r.uniform(0.0015, 0.006))
        c = r.uniform(3500, 10000)
        g = np.sin(2 * np.pi * c * t_of(ln)) * env_exp(ln, ln / SR, 0.0001) * r.uniform(0.2, 1.0)
        out[at:at + ln] += g
    out = hp(out, 2500)
    return norm(out, 0.6).astype(np.float32)


# ----------------------------------------------------------------------------- elements
def fire_roar(level, seed=0):
    """Fire riding on a blade: a low roar and a flutter whose loudness follows 'level' (per sample),
    with crackles that come with it."""
    n = len(level)
    lvl = np.asarray(level)
    roar = follow_noise(lvl, 180 + 900 * np.clip(lvl, 0, 1.5), width=0.9, seed=seed, colour="pink")
    flutter = 0.6 + 0.4 * np.sin(2 * np.pi * (13 + 9 * lvl) * t_of(n) + 1.0)
    crack = sparks(n / SR, density=60, seed=seed + 1)[:n] * 0.7 * np.clip(lvl, 0, 1)
    out = tanh_sat(roar * flutter * 0.6, 1.6) + crack
    return out.astype(np.float32)


def ignite(seed=0):
    """The flame catching along the blade: a soft whoomp, then a rising rush."""
    n = n_of(1.1)
    t = t_of(n)
    whoomp = follow_noise(np.exp(-6.9 * t / 0.35) * np.clip(t / 0.02, 0, 1), 140 + 300 * np.exp(-t / 0.1), width=0.8, seed=seed)
    sub = np.sin(sweep(90, 45, n)) * np.exp(-6.9 * t / 0.5) * 0.8
    rush = follow_noise(np.clip((t - 0.1) / 0.7, 0, 1) ** 2 * np.clip((1.1 - t) / 0.2, 0, 1), 600 + 2400 * np.clip((t - 0.1) / 0.8, 0, 1), width=0.7, seed=seed + 5)
    return norm(whoomp + sub + 0.5 * rush + 0.4 * sparks(1.1, 50, seed + 2)[:n], 0.85).astype(np.float32)


def water_swish(level, seed=0):
    """Water riding on a blade: a wet swish with bubbling, loudness following 'level' (per sample)."""
    n = len(level)
    lvl = np.asarray(level)
    hiss = follow_noise(lvl, 900 + 2600 * np.clip(lvl, 0, 1.5), width=0.55, seed=seed)
    t = t_of(n)
    bubble = np.zeros(n)
    r = rng(seed + 9)
    k = 0
    while k < n:
        k += int(r.exponential(0.018) * SR) + 1
        if k >= n:
            break
        ln = n_of(r.uniform(0.006, 0.02))
        f0 = r.uniform(500, 1800)
        seg = np.sin(sweep(f0, f0 * 1.8, ln)) * env_exp(ln, ln / SR, 0.0005)
        e = min(n, k + ln)
        bubble[k:e] += seg[:e - k] * lvl[k] * r.uniform(0.2, 0.7)
    return (hiss * 0.7 + bubble * 0.9 * (0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t))).astype(np.float32)


def splash(power=1.0, seed=0):
    """A foot or a blow throwing up the water lying on the stones: a wet slap, a spray, drops."""
    n = n_of(0.7)
    t = t_of(n)
    slap = bp(white(n, seed), 400, 3500) * np.exp(-6.9 * t / 0.06) * np.clip(t / 0.002, 0, 1)
    spray = bp(white(n, seed + 1), 2000, 9000) * np.exp(-6.9 * t / (0.25 * power)) * 0.5
    drops = np.zeros(n)
    r = rng(seed + 2)
    for _ in range(int(14 * power)):
        at = int((0.05 + r.random() * 0.5) * SR)
        ln = n_of(r.uniform(0.008, 0.02))
        f0 = r.uniform(900, 2600)
        d = np.sin(sweep(f0, f0 * 1.6, ln)) * env_exp(ln, ln / SR, 0.0003)
        e = min(n, at + ln)
        drops[at:e] += d[:e - at] * r.uniform(0.2, 0.6)
    return norm(slap + spray + drops * 0.7, 0.8).astype(np.float32)


# ----------------------------------------------------------------------------- bodies, cloth, things
def whoosh(level, centre, seed=0, kind="air"):
    """A swing through the air whose loudness and pitch follow curves (per sample).
    kind: 'air' (light, high), 'deep' (big, low), 'whip' (with a crack at the peak)."""
    width = dict(air=0.55, deep=0.85, whip=0.4)[kind]
    s = follow_noise(level, centre, width=width, seed=seed, colour="pink" if kind == "deep" else "white")
    if kind == "whip":
        k = int(np.argmax(level))
        c = hp(white(n_of(0.008), seed + 4), 3000) * env_exp(n_of(0.008), 0.008, 0.0002)
        s[k:k + len(c)] += c * 3.0 * float(np.max(level))
    return s.astype(np.float32)


def step(surface="stone", weight=1.0, seed=0, wet=0.6, armour=0.0):
    """A footfall: heel then toe ~70-90 ms later, a body thud under it, the water on the stone, and
    for the Ronin a small clink of his armoured boot."""
    r = rng(seed)
    n = n_of(0.45)
    t = t_of(n)
    out = np.zeros(n)
    for k, (at, g) in enumerate(((0.0, 1.0), (r.uniform(0.065, 0.095), 0.55))):
        a = n_of(at)
        ln = n - a
        tt = t_of(ln)
        f0 = r.uniform(120, 165) / weight ** 0.35
        thud = np.sin(sweep(f0 * 1.5, f0, ln)) * np.exp(-6.9 * tt / 0.09)
        tick = bp(white(ln, seed + 10 + k), 1200, 5200) * np.exp(-6.9 * tt / 0.022)
        grit = bp(white(ln, seed + 20 + k), 2500, 8000) * np.exp(-6.9 * tt / 0.05) * 0.3
        out[a:] += g * (thud * 0.9 * weight ** 1.5 + (tick * 0.6 + grit) / weight ** 2)     # heavier: more body, less click
    if wet > 0.0:
        out += splash(0.4, seed + 3)[:n] * 0.35 * wet / weight
    if armour > 0.0:
        out += modes([2300, 3420, 5150], [0.08, 0.06, 0.04], [1.0, 0.5, 0.3], n, seed=seed + 5) * 0.25 * armour
    return norm(out * env_exp(n, 0.4, 0.0005), 0.9).astype(np.float32)


def cloth(level, seed=0):
    """Cloth moving: a soft rustle following 'level' (per sample)."""
    n = len(level)
    lvl = np.asarray(level)
    s = follow_noise(lvl, 900 + 1400 * np.clip(lvl, 0, 1), width=1.0, seed=seed, colour="pink")
    flap = 0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 9.0 * t_of(n)))
    return (lp(s * flap, 5000) * 0.8).astype(np.float32)


def tear(seed=0):
    """Cloth torn by a blade: a quick ragged rip, then the flutter of the piece flying off."""
    n = n_of(0.9)
    t = t_of(n)
    r = rng(seed)
    rip_env = np.zeros(n)
    k = 0
    while k < n_of(0.28):
        ln = n_of(r.uniform(0.003, 0.012))
        rip_env[k:k + ln] = r.uniform(0.4, 1.0)
        k += ln + n_of(r.uniform(0.0, 0.006))
    rip = bp(white(n, seed), 900, 7000) * rip_env
    flut = follow_noise(np.clip((t - 0.2) / 0.1, 0, 1) * np.exp(-6.9 * np.maximum(t - 0.3, 0) / 0.6) * (0.6 + 0.4 * np.sin(2 * np.pi * 14 * t)),
                        np.full(n, 1400.0), width=0.9, seed=seed + 1) * 0.4
    return norm(rip + flut, 0.85).astype(np.float32)


def body_hit(power=1.0, seed=0):
    """A kick landing: a deep thump, the snap of the contact, the armour and cloth."""
    n = n_of(0.8)
    t = t_of(n)
    thump = np.sin(sweep(170, 48, n, 0.5)) * np.exp(-6.9 * t / 0.35)
    snap = bp(white(n, seed), 500, 3500) * np.exp(-6.9 * t / 0.03)
    armour = modes([780, 1330, 2150], [0.12, 0.09, 0.07], [1.0, 0.6, 0.4], n, seed=seed + 1) * 0.35
    clothy = bp(white(n, seed + 2), 300, 2500) * np.exp(-6.9 * t / 0.15) * 0.4
    return norm(tanh_sat(thump * 1.2 * power, 1.5) + snap * 0.7 + armour + clothy, 0.9).astype(np.float32)


def skid(seconds, seed=0, wet=1.0):
    """Feet sliding back over wet stone: a gritty scrape with water spray, slowing down."""
    n = n_of(seconds)
    t = t_of(n)
    lvl = np.clip(t / 0.03, 0, 1) * (1.0 - t / seconds) ** 0.7
    scrape = follow_noise(lvl, 1800 + 1200 * (1.0 - t / seconds), width=0.6, seed=seed)
    grit = sparks(seconds, 300, seed + 1)[:n] * 0.25 * lvl
    spray = bp(white(n, seed + 2), 2500, 9000) * lvl * 0.35 * wet
    return norm(scrape + grit + spray, 0.8).astype(np.float32)


def straw_hit(seed=0):
    """Half of a woven bamboo hat landing on stone: a light hollow clack and a small rattle."""
    n = n_of(0.5)
    t = t_of(n)
    m = modes([410, 760, 1180, 1730, 2410], [0.08, 0.07, 0.05, 0.04, 0.03], [1.0, 0.8, 0.6, 0.4, 0.3], n, seed=seed, jitter=0.03)
    rattle = bp(white(n, seed + 1), 1500, 6000) * np.exp(-6.9 * t / 0.12) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 38 * t)))
    return norm(m + rattle * 0.35, 0.8).astype(np.float32)


def straw_creak(seconds=0.6, seed=0):
    n = n_of(seconds)
    t = t_of(n)
    r = rng(seed)
    out = np.zeros(n)
    k = 0
    while k < n:
        k += n_of(r.uniform(0.012, 0.035))
        if k >= n:
            break
        ln = n_of(0.008)
        out[k:k + ln] += bp(white(ln, int(k)), 1200, 4500) * env_exp(ln, 0.008, 0.0005) * r.uniform(0.3, 1.0)
    return norm(out * np.sin(np.pi * t / seconds), 0.6).astype(np.float32)


def crack(seconds=0.35, seed=0):
    """Lacquered mask cracking: a sharp snap, then small fractures running along."""
    n = n_of(seconds + 0.4)
    r = rng(seed)
    out = np.zeros(n)
    snap = bp(white(n_of(0.012), seed), 900, 5000) * env_exp(n_of(0.012), 0.012, 0.0001)
    out[:len(snap)] += snap * 2.0
    out += modes([1150, 1900, 2870, 4410], [0.06, 0.05, 0.04, 0.03], [1.0, 0.8, 0.5, 0.3], n, seed=seed) * 0.6
    for _ in range(26):
        at = int(r.random() ** 0.8 * seconds * SR)
        ln = n_of(r.uniform(0.001, 0.004))
        tick = bp(white(ln, int(at)), 1200, 6000) * env_exp(ln, ln / SR, 0.0001) * r.uniform(0.2, 0.9)
        out[at:at + ln] += tick
    return norm(out, 0.85).astype(np.float32)


def glint(seed=0):
    """The anime glint on the visor: a quick bright shimmer."""
    n = n_of(0.9)
    t = t_of(n)
    tones = modes([5274, 6272, 7902, 10548], [0.5, 0.45, 0.35, 0.25], [1.0, 0.7, 0.5, 0.3], n, seed=seed)
    trem = 0.75 + 0.25 * np.sin(2 * np.pi * 23 * t)
    rise = np.clip(t / 0.03, 0, 1)
    return norm(tones * trem * rise, 0.5).astype(np.float32)


def visor_hum(seconds, seed=0):
    """The Cyber Ronin's visor up close: a faint electric hum with a data flicker."""
    n = n_of(seconds)
    t = t_of(n)
    hum = (np.sin(2 * np.pi * 120 * t) * 0.6 + np.sin(2 * np.pi * 240 * t) * 0.3 + np.sin(2 * np.pi * 360 * t) * 0.15)
    r = rng(seed)
    flick = np.zeros(n)
    for _ in range(int(seconds * 9)):
        at = int(r.random() * (n - n_of(0.03)))
        ln = n_of(r.uniform(0.008, 0.03))
        f = r.choice([1760, 2349, 2637, 3136])
        flick[at:at + ln] += np.sin(2 * np.pi * f * t_of(ln)) * env_adsr(ln, 0.002, 0.004, 0.6, 0.004) * 0.25
    e = env_adsr(n, 0.15, 0.1, 1.0, 0.25)
    return (norm(hum, 0.5) * e + flick * e).astype(np.float32)


def breath(seconds=1.2, seed=0, low=True):
    """A slow breath through a mask: noise through a mouth-like band, in then out."""
    n = n_of(seconds)
    t = t_of(n)
    lvl = np.sin(np.pi * np.clip(t / seconds, 0, 1)) ** 1.5
    centre = np.where(t < seconds * 0.45, 700, 450) if low else np.full(n, 1200.0)
    g = follow_noise(lvl, centre, width=0.7, seed=seed, colour="pink")
    growl = np.sin(2 * np.pi * (58 + 4 * np.sin(2 * np.pi * 3 * t)) * t) * lvl * 0.15 if low else 0.0
    return (g * 0.6 + growl).astype(np.float32)


def bell(f0=55.0, seconds=7.0, seed=0):
    """A great temple bell (struck from outside with a wooden beam): a soft thud, then a deep hum with
    slowly beating partials."""
    n = n_of(seconds)
    ratios = [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166]
    decays = [8.0, 7.0, 5.0, 4.0, 3.0, 2.2, 2.0, 1.6, 1.0]
    amps = [0.5, 1.0, 0.6, 0.45, 0.4, 0.25, 0.2, 0.15, 0.08]
    hum = modes([f0 * r_ for r_ in ratios], decays, amps, n, seed=seed)
    hum += modes([f0 * r_ * 1.004 for r_ in ratios], decays, [a * 0.6 for a in amps], n, seed=seed + 1)
    t = t_of(n)
    thud = lp(white(n, seed + 2), 300) * np.exp(-6.9 * t / 0.15) * 0.8
    return norm(hum + thud, 0.9).astype(np.float32)


def wind(seconds, seed=0, gusts=()):
    """Night wind across the courtyard (stereo): a low moving band, gusts given as (time, strength)."""
    n = n_of(seconds)
    t = t_of(n)
    base = 0.55 + 0.25 * np.sin(2 * np.pi * 0.11 * t + 0.4) + 0.15 * np.sin(2 * np.pi * 0.27 * t + 2.0)
    for at, s in gusts:
        base += s * np.exp(-0.5 * ((t - at) / 0.9) ** 2)
    out = []
    for ch in range(2):
        c = 260 + 420 * base + 60 * np.sin(2 * np.pi * (0.19 + 0.05 * ch) * t + ch)
        out.append(follow_noise(base, c, width=0.9, seed=seed + ch, colour="pink") * 0.5)
    return np.stack(out, axis=1).astype(np.float32)


def chime(seed=0):
    """A small glass wind chime (furin) far off: one high note and its shimmer."""
    r = rng(seed)
    f = r.choice([2637, 2960, 3136, 3520, 3951])
    n = n_of(2.2)
    return norm(modes([f, f * 2.76, f * 5.4], [1.8, 0.9, 0.5], [1.0, 0.3, 0.12], n, seed=seed), 0.5).astype(np.float32)


def sub_boom(seconds=1.6, f0=58.0, seed=0):
    n = n_of(seconds)
    t = t_of(n)
    s = np.sin(sweep(f0 * 1.8, f0, n, 0.35)) * np.exp(-6.9 * t / (seconds * 0.8)) * np.clip(t / 0.004, 0, 1)
    return norm(tanh_sat(s, 1.3), 0.95).astype(np.float32)


def suck_in(seconds=0.9, seed=0):
    """A reversed swell that pulls toward a hit."""
    n = n_of(seconds)
    t = t_of(n)
    swell = follow_noise((t / seconds) ** 3, 400 + 5000 * (t / seconds) ** 2, width=0.8, seed=seed)
    tone = np.sin(sweep(110, 330, n, 2.0)) * (t / seconds) ** 4 * 0.5
    return norm(swell + tone, 0.8).astype(np.float32)


def shock_ring(seed=0):
    """The ring of air thrown out at the crossing: a wide low whoom and a glassy shimmer."""
    n = n_of(2.6)
    t = t_of(n)
    whoom = follow_noise(np.exp(-6.9 * t / 1.1) * np.clip(t / 0.03, 0, 1), 120 + 900 * np.exp(-t / 0.25), width=0.9, seed=seed, colour="pink")
    glass = modes([1567, 2349, 3136, 4186, 6272], [2.0, 1.6, 1.2, 0.9, 0.6], [1.0, 0.7, 0.5, 0.35, 0.2], n, seed=seed + 1) * np.clip(t / 0.08, 0, 1)
    return norm(whoom * 0.9 + glass * 0.35, 0.9).astype(np.float32)


# ----------------------------------------------------------------------------- instruments
def taiko(kind="o", vel=1.0, seed=0):
    """Japanese drums. 'o': o-daiko (big, deep), 'shime': shime-daiko (small, tight, high),
    'rim': a stick on the drum's wooden rim (kachi)."""
    r = rng(seed)
    if kind == "rim":
        n = n_of(0.12)
        m = modes([1650, 2830, 4100], [0.04, 0.03, 0.02], [1.0, 0.5, 0.3], n, seed=seed, jitter=0.02)
        return norm(m, 0.7 * vel).astype(np.float32)
    if kind == "shime":
        n = n_of(0.35)
        t = t_of(n)
        f0 = r.uniform(310, 340)
        body = np.sin(sweep(f0 * 1.15, f0, n, 0.3)) * np.exp(-6.9 * t / 0.16)
        slap = bp(white(n, seed), 1500, 6000) * np.exp(-6.9 * t / 0.02)
        return norm(body + slap * 0.8, 0.8 * vel).astype(np.float32)
    n = n_of(1.6)
    t = t_of(n)
    f0 = r.uniform(58, 64)
    body = np.sin(sweep(f0 * 1.45, f0, n, 0.25)) * np.exp(-6.9 * t / 1.1)
    skin = modes([f0 * 1.59, f0 * 2.14, f0 * 2.30, f0 * 2.65], [0.35, 0.25, 0.2, 0.15], [0.5, 0.35, 0.3, 0.2], n, seed=seed)
    slap = bp(white(n, seed + 1), 180, 900) * np.exp(-6.9 * t / 0.05)
    return norm(tanh_sat(body * 1.1 + skin * 0.6 + slap * 0.7, 1.4), 0.95 * vel).astype(np.float32)


def shamisen(freq, seconds=1.2, vel=1.0, seed=0):
    """A plucked shamisen note: a hard plectrum attack and the buzz (sawari) of the open string."""
    s = ks(freq, seconds, damp=0.9965, bright=0.9, seed=seed)
    n = len(s)
    t = t_of(n)
    pick = hp(white(n_of(0.006), seed + 1), 1800) * env_exp(n_of(0.006), 0.006, 0.0001)
    s[:len(pick)] += pick * 0.8
    buzz = tanh_sat(s * 2.5, 2.0) * 0.25
    return norm((s + buzz) * np.exp(-6.9 * t / seconds), 0.8 * vel).astype(np.float32)


def koto(freq, seconds=2.2, vel=1.0, seed=0):
    s = ks(freq, seconds, damp=0.998, bright=0.55, seed=seed)
    t = t_of(len(s))
    return norm(s * np.exp(-6.9 * t / seconds), 0.7 * vel).astype(np.float32)


def flute(freq, seconds, vel=1.0, seed=0, bend=True):
    """A breathy bamboo flute (in the manner of a shakuhachi): it starts a little flat and slides up,
    breath noise in the tone, a slow vibrato that comes in late."""
    n = n_of(seconds)
    t = t_of(n)
    f = freq * np.ones(n)
    if bend:
        f *= 2 ** ((-0.6 * np.exp(-t / 0.12)) / 12.0)
    vib = np.clip((t - seconds * 0.45) / (seconds * 0.3), 0, 1) * 0.004 * np.sin(2 * np.pi * 5.2 * t)
    ph = 2 * np.pi * np.cumsum(f * (1 + vib)) / SR
    tone = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    e = env_adsr(n, 0.09, 0.2, 0.8, min(0.35, seconds * 0.4))
    breath_ = follow_noise(e, f * 2.0, width=0.5, seed=seed) * 0.18
    chiff = bp(white(n, seed + 1), 1500, 5000) * np.exp(-6.9 * t / 0.06) * 0.2
    return norm((tone * e + breath_ + chiff) * vel, 0.6 * vel).astype(np.float32)


def drone(freq, seconds, seed=0, dark=900.0):
    """A low bowed drone: detuned saw-like voices, low-passed, slowly breathing."""
    n = n_of(seconds)
    t = t_of(n)
    out = np.zeros(n)
    for k, d in enumerate((-0.006, 0.0, 0.0045)):
        ph = 2 * np.pi * freq * (1 + d) * t + k
        out += sum(np.sin(ph * h) / h for h in range(1, 9))
    out += 0.5 * np.sin(2 * np.pi * freq * 0.5 * t)
    out = lp(out, dark, 2) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.23 * t))
    return norm(out * env_adsr(n, min(1.2, seconds * 0.3), 0.5, 0.9, min(1.5, seconds * 0.35)), 0.5).astype(np.float32)


def braam(freq=55.0, seconds=2.2, seed=0):
    """A low brass-like hit: stacked saw voices through a filter that opens fast and closes slowly."""
    n = n_of(seconds)
    t = t_of(n)
    voices = np.zeros(n)
    for mult in (1.0, 2.0, 3.0, 1.5):
        for d in (-0.004, 0.004):
            ph = 2 * np.pi * freq * mult * (1 + d) * t
            voices += sum(np.sin(ph * h) / h for h in range(1, 12)) / mult
    cut = 300 + 2600 * np.exp(-t / 0.35)                            # the filter opens fast and closes slowly, block by block
    y = np.zeros(n)
    hop = n_of(0.02)
    zi = None
    for k in range(0, n, hop):
        S = sos("lowpass", float(cut[k]))
        seg = voices[k:k + hop]
        if zi is None:
            zi = np.zeros((S.shape[0], 2))
        y[k:k + len(seg)], zi = signal.sosfilt(S, seg, zi=zi)
    e = env_adsr(n, 0.01, 0.3, 0.7, seconds * 0.5)
    return norm(tanh_sat(y * e, 1.8), 0.9).astype(np.float32)


def riser(seconds=1.5, seed=0):
    n = n_of(seconds)
    t = t_of(n)
    u = t / seconds
    noise = follow_noise(u ** 2.5, 500 + 7000 * u ** 2, width=0.7, seed=seed)
    tone = np.sin(sweep(80, 640, n, 1.6)) * u ** 3 * 0.4
    return norm(noise + tone, 0.8).astype(np.float32)


def heartbeat(seed=0):
    """lub-dub, felt more than heard."""
    n = n_of(0.6)
    out = np.zeros(n)
    for at, g, f in ((0.0, 1.0, 55.0), (0.17, 0.7, 62.0)):
        a = n_of(at)
        ln = n - a
        tt = t_of(ln)
        out[a:] += g * np.sin(sweep(f * 1.3, f, ln)) * np.exp(-6.9 * tt / 0.18)
    return norm(lp(out, 200), 0.9).astype(np.float32)
