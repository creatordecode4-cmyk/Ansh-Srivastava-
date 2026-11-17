"""Real recordings for the film's sound: Mixkit free sound effects (https://mixkit.co/free-sound-effects/),
used under the Mixkit Sound Effects Free License (free in personal and commercial projects; the sounds are
not to be handed out on their own). So the files are not in this repository: tools/mixkit_fetch.py
downloads them by id into out/sound/mixkit/raw/.

Each role below lists the recordings that can play it; a cue picks one by its index, so repeats differ.
A recording is resampled to 48 kHz and its attack is found (where it first reaches a tenth of its loudest),
so a hit can be laid with its attack exactly on the frame. Loops of many hits (footsteps on stones, tribal
drums) are cut into single hits at their onsets.
"""
import os

import numpy as np
import soundfile as sf
from scipy import signal

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(HERE, "out", "sound", "mixkit", "raw")
SR = 48000

ROLES = dict(
    clash=[2160, 2166, 2762, 2763, 2764, 2765, 2766, 2789],          # blade on blade
    clash_heavy=[2794, 2795, 2797, 2789, 775],
    draw=[2799, 2798, 2760],                                          # steel leaving the scabbard
    swing_heavy=[2792, 1488, 1464, 1462, 1473, 1472],                 # the Oni's big blade
    swing_light=[1506, 1487, 1485, 1478, 607, 1473],                  # the Ronin's quick ones
    steps=[1270, 1269],                                               # loops, cut into single footfalls
    kick=[2163, 2153, 2047, 2198],
    ignite=[1342, 1349],
    fire_burst=[1327, 1348, 1345],
    fire_bed=[1331, 1333],
    splash=[1198, 754],
    wind=[1154, 1172],
    bell=[619, 587],
    impact=[780, 553, 551, 563],                                      # hits loudest at their attack (2896/2897/549 build for seconds: not hits)
    riser=[790, 784, 678],
    drums=[567, 574, 575, 563, 549, 487],                             # cut into single hits
    roll=[577, 569],
    crack=[2945],
    wood=[2182],
    breath=[2240, 2234],
    heart=[490, 498],
    glitch=[1022, 1030, 1035],
    crackle=[1455],
    horn=[3111, 2289, 724],
    choir=[664, 662],
)
TITLES = {  # for the credits sheet
    487: "Cinematic ancient drums heartbeat", 490: "Human single heart beat", 498: "Deep heartbeat impact",
    549: "Deep cinematic subtle drum impact", 551: "Metallic cinematic drum trailer sound", 553: "Blockbuster trailer bass drum",
    563: "Drum deep impact", 567: "Tribal ritual drums", 569: "Atmospheric prelude drum roll", 574: "Tribal drum echoes",
    575: "Tribal deep drum echoes", 577: "Tension and suspense drum roll", 587: "Clock tower or cathedral bell", 607: "Air whoosh and whistle",
    619: "Cinematic church bell hit", 662: "Cinematic tension choir transition", 664: "Cinematic dark choir transition",
    678: "Trailer cinematic suspense swell", 724: "Cinematic trailer apocalypse horn", 754: "Fall on foam splash", 775: "Metal sword impact",
    780: "Cinematic impact echo", 784: "Reverse cinematic impact trailer", 790: "Cinematic trailer riser", 1022: "Cinematic sci fi glitch",
    1030: "Small sci fi glitch", 1035: "Robotic glitch", 1154: "Arctic winds", 1172: "Wind cold interior", 1198: "Sea water splash",
    1269: "Walking on stones loop", 1270: "Footsteps on stones loop", 1327: "Big fire magic swoosh", 1331: "Big fire flame burning",
    1333: "Aggressive fire flame", 1342: "Ignition metal fire", 1345: "Short fire whoosh", 1348: "Fire woosh", 1349: "Fast ignition fire",
    1455: "Static electric crackles", 1462: "Quick swoosh", 1464: "Quick swoosh accent", 1472: "Quick hit swoosh", 1473: "Long hit swoosh",
    1478: "Karate hit whoosh", 1485: "Metal hit woosh", 1487: "Dagger woosh", 1488: "Throw hard wind woosh", 1506: "Sword blade swish",
    2047: "Martial arts fast punch", 2153: "Body punch quick hit", 2160: "Metallic sword strike", 2163: "Martial arts kick",
    2166: "Swift Sword Strike", 2182: "Wood hard hit", 2198: "Strong punches to the body", 2234: "Terrifying Creature Breath",
    2240: "Creepy demon heavy breathing", 2289: "Warfare horn", 2760: "Sword slide in a medieval bar fight",
    2762: "Sword blade attack in medieval battle", 2763: "Sword slashes in battle", 2764: "Fast sword hit in medieval battle",
    2765: "Sword strikes armor", 2766: "Medieval metal sword blade", 2789: "Samurai Sword Impact", 2792: "Fast sword whoosh",
    2794: "Heavy sword hit", 2795: "Heavy sword smashes metal", 2797: "Sword hits heavy metal", 2798: "Fantasy sword slide",
    2799: "Metallic sword scrape", 2945: "Twig breaking", 3111: "Warfare horn trailer hit", 2896: "Movie intro impact",
    2897: "Movie logo presentation impact"}


def ids():
    return sorted({i for v in ROLES.values() for i in v})


def attack_of(x, frac=0.1):
    """Where a sound first reaches 'frac' of its loudest (2 ms envelope), in samples."""
    m = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    env = signal.lfilter([1.0], [1.0, -np.exp(-1.0 / (0.002 * SR))], m) * (1.0 - np.exp(-1.0 / (0.002 * SR)))
    return int(np.argmax(env >= env.max() * frac))


def peak_of(x):
    """Where a sound is loudest (20 ms envelope), in samples."""
    m = (x ** 2).mean(axis=1) if x.ndim == 2 else x ** 2
    env = np.convolve(m, np.ones(int(0.02 * SR)) / int(0.02 * SR), mode="same")
    return int(np.argmax(env))


class Bank:
    def __init__(self, root=ROOT):
        self.root = root
        self.cache, self.cuts = {}, {}

    def available(self, role):
        return all(os.path.exists(os.path.join(self.root, f"{i}.wav")) for i in ROLES[role][:1])

    def get(self, i):
        """The recording, stereo float32 at 48 kHz, peak 1."""
        if i not in self.cache:
            x, sr = sf.read(os.path.join(self.root, f"{i}.wav"), always_2d=True, dtype="float64")
            if x.shape[1] == 1:
                x = np.repeat(x, 2, axis=1)
            x = x[:, :2]
            if sr != SR:
                g = np.gcd(SR, sr)
                x = signal.resample_poly(x, SR // g, sr // g, axis=0)
            x = x - x.mean(axis=0)
            self.cache[i] = (x / (np.abs(x).max() + 1e-12)).astype(np.float32)
        return self.cache[i]

    def pick(self, role, k):
        r = ROLES[role]
        return r[int(k) % len(r)]

    def one(self, role, k, speed=1.0, seconds=None, fade_out=0.05):
        """Variant k of a role, played 'speed' times as fast (below 1: lower and longer), cut to 'seconds'
        after its attack. Returns (stereo sound starting just before the attack, seconds before the attack)."""
        x = self.get(self.pick(role, k))
        if abs(speed - 1.0) > 1e-3:
            x = signal.resample(x, max(2, int(round(len(x) / speed))), axis=0).astype(np.float32)
        a = attack_of(x)
        pre = min(a, int(0.01 * SR))
        x = x[a - pre:]
        if seconds is not None:
            x = x[: pre + int(seconds * SR)]
        f = min(len(x), int(fade_out * SR))
        x = x.copy()
        if f > 0:
            x[len(x) - f:] *= np.linspace(1.0, 0.0, f)[:, None]
        return x, pre / SR

    def hits(self, i, keep_db=14.0, longest=0.6):
        """A loop cut into its single hits: [(stereo hit from 5 ms before its onset, loudness dB)], loudest first.
        Onsets: where the 10 ms energy jumps 6 dB over the quietest of the last 60 ms and is within 30 dB of the top."""
        if i in self.cuts:
            return self.cuts[i]
        x = self.get(i)
        m = x.mean(axis=1)
        hop = int(0.01 * SR)
        e = np.array([np.sqrt(np.mean(m[k:k + hop] ** 2)) for k in range(0, len(m) - hop, hop)]) + 1e-9
        ed = 20 * np.log10(e)
        on = []
        for k in range(6, len(ed)):
            if ed[k] - ed[k - 6:k].min() > 6.0 and ed[k] > ed.max() - 30.0 and (not on or k - on[-1] > 12):
                on.append(k)
        out = []
        for j, k in enumerate(on):
            a = max(0, k * hop - int(0.005 * SR))
            b = min(len(x), (on[j + 1] * hop - int(0.005 * SR)) if j + 1 < len(on) else len(x), a + int(longest * SR))
            h = x[a:b].copy()
            f = min(len(h), int(0.04 * SR))
            h[len(h) - f:] *= np.linspace(1.0, 0.0, f)[:, None]
            lvl = 20 * np.log10(np.sqrt(np.mean(h[: int(0.08 * SR)] ** 2)) + 1e-9)
            out.append((h, lvl))
        top = max(l_ for _, l_ in out)
        out = [(h / (np.abs(h).max() + 1e-12), l_) for h, l_ in out if l_ > top - keep_db]
        out.sort(key=lambda p: -p[1])
        self.cuts[i] = out
        return out

    def bed(self, role, k, n, level=None, xfade=0.4):
        """A recording looped (crossfaded) to n samples, its loudness following 'level' (per sample) if given."""
        x = self.get(self.pick(role, k))
        c = int(xfade * SR)
        out = np.zeros((n, 2), np.float32)
        pos = 0
        ramp = np.linspace(0.0, 1.0, c)[:, None]
        while pos < n:
            seg = x.copy()
            if pos > 0:
                seg[:c] *= ramp
            seg[len(seg) - c:] *= ramp[::-1]
            e = min(n, pos + len(seg))
            out[pos:e] += seg[: e - pos]
            pos += len(seg) - c
        if level is not None:
            out *= np.asarray(level, np.float32)[:n, None]
        return out


def credits(path, used, mix):
    """The recordings used, with ids, titles and where they are from: one section per mix ('film',
    'teaser'), so building one mix rewrites its own list and keeps the other's."""
    sections = {}
    if os.path.exists(path):
        cur = None
        with open(path) as fh:
            for line in fh:
                s = line.strip()
                if s.startswith("[") and s.endswith("]"):
                    cur = s[1:-1]
                    sections[cur] = set()
                elif cur is not None and s[:1].isdigit():
                    sections[cur].add(int(s.split()[0]))
    sections[mix] = set(used)
    with open(path, "w") as fh:
        fh.write("Real recordings in these mixes: Mixkit free sound effects (https://mixkit.co/free-sound-effects/),\n"
                 "used under the Mixkit Sound Effects Free License (https://mixkit.co/license/). Not redistributed here.\n"
                 "One list per mix: [film] the 30 s film, [teaser] the teaser (both shapes).\n")
        for name in sorted(sections):
            fh.write(f"\n[{name}]\n")
            for i in sorted(sections[name]):
                fh.write(f"  {i:5d}  {TITLES.get(i, '')}  https://mixkit.co/free-sound-effects/  (asset id {i})\n")
