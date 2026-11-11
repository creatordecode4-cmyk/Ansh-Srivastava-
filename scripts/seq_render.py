#!/usr/bin/env python3
"""Sequence step 2: four stills -> one cinematic move, video playing on the laptop.

  vista -> (tilt up) -> canopy -> (tilt down) -> wide laptop, screen off
        -> screen wakes with a soft glow -> match-zoom glide -> close-up with the video

  python3 scripts/seq_render.py --video output/input/screen_video.mp4 --out output/seq/final_sequence.mp4
  python3 scripts/seq_render.py ... --size 960x540 --t0 7.9 --t1 10.9 --out output/seq/preview.mp4

Every effect is a closed-form function of time, so chunks render in parallel.
"""
import argparse
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

FPS = 30
NW, NH = 1376, 768
VID_W, VID_H = 1280, 720

# ---- timeline (seconds) ------------------------------------------------------
T_AB = (2.8, 3.9)        # vista -> canopy (camera tilts up)
T_BC = (6.0, 7.1)        # canopy -> wide laptop (camera tilts down)
T_ON = 8.1               # screen starts to wake
T_VID = 8.6              # video (and its audio) starts
T_GLIDE = (9.3, 10.8)    # wide -> close-up match zoom
SLIDE = 0.42             # tilt travel, fraction of frame height

SHOTS = {
    "vista": dict(win=(0.0, T_AB[1]), zoom=(1.10, 1.14), pan=((-22, 6), (22, -4)), cy=0.5, push=0.02, fl=1.6,
                  grass=2.3, tree=1.25, sun=(1.05, -0.10), ray=(0.11, 5.0, "shaft"),
                  petals=dict(bg=70, mid=42, fg=5, land=(0.87, 0.98))),
    "canopy": dict(win=(T_AB[0], T_BC[1]), zoom=(1.20, 1.25), pan=((-103, 28), (-88, -20)), cy=0.5, push=0.025, fl=1.6,
                   grass=0, tree=1.7, sun=(900 / NW, 365 / NH), ray=(0.07, 3.0, "star"),
                   petals=dict(bg=40, mid=32, fg=5, land=None, bg_size=(2.5, 5.0))),
    "wide": dict(win=(T_BC[0], T_GLIDE[1]), zoom=(1.004, 1.03), pan=((0, 0), (0, 0)), cy=0.6, push=0.012, fl=1.6,
                 grass=2.3, tree=1.25, sun=(1.05, -0.10), ray=(0.11, 5.0, "shaft"),
                 petals=dict(bg=105, mid=70, fg=8, land=(0.735, 0.97))),
    "closeup": dict(win=(T_GLIDE[0], None), zoom=(1.004, 1.04), pan=((0, 0), (0, 0)), cy=0.5, push=0.008, fl=1.3,
                    grass=1.6, tree=1.5, sun=(1.08, 0.15), ray=(0.08, 4.0, "shaft"),
                    petals=dict(bg=38, mid=7, fg=3, land=None, bg_size=(4.0, 8.0), bg_blur=1.6, speed=1.5,
                                mid_size=(8.0, 14.0))),
}
MIST_ALPHA = 0.13


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def ease(x):
    x = float(np.clip(x, 0, 1))
    return x * x * x * (x * (6 * x - 15) + 10)


def smooth_noise(rng, h, w, cell):
    gh, gw = max(2, int(h / cell) + 3), max(2, int(w / cell) + 3)
    g = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
    return cv2.resize(g, (int(gw * cell), int(gh * cell)), interpolation=cv2.INTER_CUBIC)[:h, :w]


PETAL = np.float32([(0, -1), (.35, -.75), (.62, -.3), (.68, .15), (.55, .6), (.3, .9), (.08, .97), (0, .84),
                    (-.08, .97), (-.3, .9), (-.55, .6), (-.68, .15), (-.62, -.3), (-.35, -.75)])
PETAL_COLORS = np.float32([(203, 186, 246), (214, 198, 252), (226, 214, 255), (238, 234, 252), (196, 176, 238)])


class Shot:
    def __init__(self, name, a):
        self.name, self.a, self.cfg = name, a, SHOTS[name]
        cfg = self.cfg
        ow, oh = self.ow, self.oh = a.ow, a.oh
        S = self.S = oh / NH
        P = np.load(os.path.join(a.work, f"prep_{name}.npz"))
        sw = int(round(NW * S))
        x0 = self.x0 = (sw - ow) // 2
        self.t0 = cfg["win"][0]
        self.t1 = cfg["win"][1] if cfg["win"][1] is not None else a.total

        def up(m, interp=cv2.INTER_LINEAR):
            return np.ascontiguousarray(cv2.resize(m, (sw, oh), interpolation=interp)[:, x0:x0 + ow])

        plate = up(P["plate"], cv2.INTER_LANCZOS4 if S > 1 else cv2.INTER_AREA)
        if S > 1:
            plate = cv2.addWeighted(plate, 1.22, cv2.GaussianBlur(plate, (0, 0), 0.8 * S), -0.22, 0)
        self.plate = plate
        self.depth = up(P["depth"])
        self.lap_soft = up(P["lap_soft"])
        self.far = up(P["far"])
        lap = up(P["lap"].astype(np.float32))
        grass_amp, tree_amp, mist = up(P["grass_amp"]), up(P["tree_amp"]), up(P["mist"])
        self.lap_dep = float(P["lap_dep"])
        self.quad = P["quad"] * S - (x0, 0) if len(P["quad"]) else None

        rng = np.random.default_rng(sum(map(ord, name)))
        ys, xs = np.mgrid[0:oh, 0:ow].astype(np.float32)
        self.xs, self.ys = xs, ys
        un, vn = (xs + x0) / S, ys / S
        self.cx, self.cy = ow / 2.0, oh * cfg["cy"]

        # light the screen throws on keyboard / palm rest / nearby grass
        self.glow = None
        if self.quad is not None:
            q = P["quad"]
            near = ss(0.5, 0.7, self.depth)
            halo = cv2.GaussianBlur(lap, (0, 0), 0.09 * (q[:, 0].max() - q[:, 0].min()) * S) * near * (1 - lap) * (vn > q[:, 1].max() - 40) * 26
            spill = up(P["spill"])
            m = (halo + spill) > 0.3
            r0, r1 = np.where(m.any(1))[0][[0, -1]]
            c0, c1 = np.where(m.any(0))[0][[0, -1]]
            self.glow = (slice(r0, r1 + 1), slice(c0, c1 + 1))
            self.halo = halo[self.glow][..., None]
            self.spill = spill[self.glow][..., None]

        # sway
        self.has_grass = cfg["grass"] > 0 and grass_amp.max() > 0.01
        if self.has_grass:
            self.g0 = int(np.argmax(grass_amp.max(1) > 0.01))
            gs = slice(self.g0, oh)
            boost = 0.75 + 0.6 * (vn[gs] - vn[self.g0, 0]) / max(1.0, NH - vn[self.g0, 0])
            self.gA = grass_amp[gs] * cfg["grass"] * S * boost
            self.gP1 = -un[gs] / 85.0 + 1.6 * smooth_noise(rng, oh - self.g0, ow, 45 * S)
            self.gP2 = -un[gs] / 30.0 + 2.5 * smooth_noise(rng, oh - self.g0, ow, 16 * S)
            self.g_un = un[self.g0:self.g0 + 1]
        self.tr1 = int(oh - np.argmax(tree_amp.max(1)[::-1] > 0.01))
        ts = slice(0, self.tr1)
        side = np.where(un[ts] > NW / 2, 1.3, 0.0)
        self.tA = tree_amp[ts] * cfg["tree"] * S
        self.tP1 = side + 1.3 * smooth_noise(rng, self.tr1, ow, 110 * S)
        self.tP2 = side * 0.6 + 2.0 * smooth_noise(rng, self.tr1, ow, 40 * S)
        self.tP3 = 1.5 * smooth_noise(rng, self.tr1, ow, 90 * S)

        # light rays (quarter res)
        r = 4
        lw, lh = ow // r, oh // r
        ul = cv2.resize(un, (lw, lh), interpolation=cv2.INTER_AREA)
        vl = cv2.resize(vn, (lw, lh), interpolation=cv2.INTER_AREA)
        sx, sy = cfg["sun"][0] * NW, cfg["sun"][1] * NH
        self.theta = np.arctan2(vl - sy, ul - sx)
        rad = np.hypot(ul - sx, vl - sy)
        farl = cv2.resize(self.far, (lw, lh), interpolation=cv2.INTER_AREA)
        lapl = cv2.resize(self.lap_soft, (lw, lh), interpolation=cv2.INTER_AREA)
        if cfg["ray"][2] == "star":
            self.raymask = np.exp(-rad / 200.0) * ss(8, 40, rad) * 1.3
            self.rayf = (11, 17, 29)
        else:
            fall = np.clip(1 - rad / (NW * 0.95), 0, 1) ** 1.1
            self.raymask = fall * (0.35 + 0.65 * farl) * (1 - lapl) * (1 - 0.6 * ss(0.68, 0.8, vl / NH))
            self.rayf = (41, 73, 127)

        # mist
        self.has_mist = mist.max() > 0.01
        if self.has_mist:
            self.m0 = int(np.argmax(mist.max(1) > 0.01))
            self.m1 = int(oh - np.argmax(mist.max(1)[::-1] > 0.01))
            self.mist = mist[self.m0:self.m1]
            nrng = np.random.default_rng(11)

            def strip(cellx, celly):
                g = nrng.uniform(0, 1, (int(NH / celly) + 3, int(2 * NW / cellx))).astype(np.float32)
                g = np.concatenate([g, g[:, :3]], 1)
                big = cv2.resize(g, (int(g.shape[1] * cellx * S), int(g.shape[0] * celly * S)), interpolation=cv2.INTER_CUBIC)
                return big[self.m0:self.m1, :int((g.shape[1] - 3) * cellx * S)]
            self.mn1, self.mn2 = strip(170, 26), strip(90, 16)
            self.mist_col = np.float32([222, 228, 236])

        # petals
        pc = cfg["petals"]
        pr = np.random.default_rng(23 + sum(map(ord, name)))
        sp = pc.get("speed", 1.0)

        def layer(n, size, vy, vx, sway, idle):
            d = dict(n=n)
            d["size"] = pr.uniform(*size, n)
            d["vy"] = pr.uniform(*vy, n) * sp
            d["vx"] = pr.uniform(*vx, n) * sp
            d["x0"] = pr.uniform(-0.45 * NW, NW * 1.02, n)
            d["swA"] = pr.uniform(*sway, n)
            d["swF"] = pr.uniform(0.25, 0.6, n) * 2 * np.pi
            d["swP"] = pr.uniform(0, 6.28, n)
            d["rot0"] = pr.uniform(0, 6.28, n)
            d["rotS"] = pr.uniform(0.5, 2.2, n) * pr.choice([-1, 1], n)
            d["flF"] = pr.uniform(1.2, 3.2, n)
            d["flP"] = pr.uniform(0, 6.28, n)
            d["col"] = PETAL_COLORS[pr.integers(0, len(PETAL_COLORS), n)] * pr.uniform(0.92, 1.0, (n, 1)).astype(np.float32)
            d["alpha"] = pr.uniform(0.75, 0.95, n)
            d["m"] = d["size"] * 2 + 6
            d["tfall"] = (NH + 2 * d["m"]) / d["vy"]
            d["land"] = np.zeros(n, bool)
            d["rest"] = np.zeros(n)
            d["P"] = d["tfall"] + pr.uniform(*idle, n)
            d["ph"] = pr.uniform(0, 1, n) * d["P"]
            d["dep"] = np.zeros(n)
            return d

        self.bg = layer(pc["bg"], pc.get("bg_size", (1.6, 3.2)), (26, 48), (16, 36), (4, 10), (0, 2))
        self.mid = layer(pc["mid"], pc.get("mid_size", (4.2, 8.0)), (62, 108), (40, 85), (8, 20), (0, 3))
        self.fg = layer(pc["fg"], (17, 32), (150, 250), (110, 210), (15, 35), (3, 9))
        self.bg_blur = pc.get("bg_blur", 0.45)
        self.mid["dep"][:] = 0.72
        self.fg["dep"][:] = 1.25
        if pc["land"]:
            L = self.mid
            la, lb = pc["land"]
            depth_n = P["depth"]
            lapn = cv2.dilate(P["lap"].astype(np.uint8), np.ones((25, 25), np.uint8))
            for i in np.where(pr.uniform(0, 1, L["n"]) < 0.32)[0]:
                for _ in range(30):
                    ly = pr.uniform(la, lb) * NH
                    tf = (ly + L["m"][i]) / L["vy"][i]
                    lx = L["x0"][i] + L["vx"][i] * tf + L["swA"][i] * np.sin(L["swF"][i] * tf + L["swP"][i])
                    if 5 < lx < NW - 5 and not lapn[int(ly), int(lx)]:
                        break
                    L["x0"][i] = pr.uniform(-0.45 * NW, NW * 1.02)
                else:
                    continue
                L["land"][i], L["tfall"][i], L["rest"][i] = True, tf, pr.uniform(3.0, 5.5)
                L["P"][i] = tf + L["rest"][i] + 0.9 + pr.uniform(0, 2)
                L["dep"][i] = depth_n[int(ly), int(lx)]
                L["size"][i] *= 0.65 + 0.9 * (ly / NH - la) / (lb - la)
            L["ph"] = pr.uniform(0, 1, L["n"]) * L["P"]

    # ------------------------------------------------------------------ camera
    def cam(self, t):
        cfg = self.cfg
        u = float(np.clip((t - self.t0) / (self.t1 - self.t0), 0, 1))
        z = cfg["zoom"][0] + (cfg["zoom"][1] - cfg["zoom"][0]) * u
        pan = (np.array(cfg["pan"][0]) + (np.array(cfg["pan"][1]) - np.array(cfg["pan"][0])) * (u * u * (3 - 2 * u))) * self.S
        F = cfg["fl"] * self.S * np.array([
            np.sin(2 * np.pi * 0.09 * t) + 0.5 * np.sin(2 * np.pi * 0.21 * t + 1.3),
            0.8 * np.sin(2 * np.pi * 0.075 * t + 2.1) + 0.4 * np.sin(2 * np.pi * 0.17 * t + 0.4)])
        return u, z, pan, F

    def fwd(self, x, y, dep, t, k=1.0, T=(0.0, 0.0)):
        """scene position -> output position for points at depth dep; returns x, y, scale."""
        u, z, pan, F = self.cam(t)
        s = z * (1 + self.cfg["push"] * u * dep)
        kd = 0.4 + 0.9 * dep
        px = self.cx + (x - pan[0] - F[0] * kd - self.cx) * s
        py = self.cy + (y - pan[1] - F[1] * kd - self.cy) * s
        return k * px + T[0], k * py + T[1], s * k

    def quad_out(self, t, k=1.0, T=(0.0, 0.0)):
        x, y, _ = self.fwd(self.quad[:, 0], self.quad[:, 1], self.lap_dep, t, k, T)
        return np.stack([x, y], 1).astype(np.float32)

    # ------------------------------------------------------------------ petals
    def petal_state(self, L, t):
        tau = np.mod(t + L["ph"], L["P"])
        tf = np.minimum(tau, L["tfall"])
        y = -L["m"] + L["vy"] * tf
        x = L["x0"] + L["vx"] * tf + L["swA"] * np.sin(L["swF"] * tf + L["swP"])
        vx = L["vx"] + L["swA"] * L["swF"] * np.cos(L["swF"] * tf + L["swP"])
        landed = L["land"] & (tau >= L["tfall"])
        vis = (tau < L["tfall"]) | landed
        a = L["alpha"] * np.where(landed, 1 - np.clip((tau - L["tfall"] - L["rest"]) / 0.9, 0, 1), 1.0)
        return x, y, np.where(landed, 0, vx), np.where(landed, 0, L["vy"]), L["rot0"] + L["rotS"] * tf, \
            np.cos(L["flF"] * tf + L["flP"]), a * vis, landed

    def draw_petals(self, L, t, shape, res=1.0, scene_space=False, k=1.0, T=(0.0, 0.0)):
        h, w = shape
        col = np.zeros((h, w, 3), np.uint8)
        alp = np.zeros((h, w), np.uint8)
        x, y, vx, vy, rot, fl, a, landed = self.petal_state(L, t)
        S = self.S
        X, Y = x * S - self.x0, y * S
        sc = np.ones_like(X) if scene_space else None
        if not scene_space:
            X, Y, sc = self.fwd(X, Y, L["dep"], t, k, T)
        size = L["size"] * S * sc
        for i in range(L["n"]):
            r = size[i]
            if a[i] <= 0.01 or X[i] < -3 * r or X[i] > self.ow + 3 * r or Y[i] < -3 * r or Y[i] > self.oh + 3 * r:
                continue
            p = PETAL * (r * (0.28 + 0.72 * abs(fl[i])), r)
            c, s_ = np.cos(rot[i]), np.sin(rot[i])
            p = p @ np.float32([[c, s_], [-s_, c]])
            if landed[i]:
                p[:, 1] *= 0.5
            v = np.float32([vx[i], vy[i]]) * S * sc[i]
            blur = np.linalg.norm(v) / FPS * 0.5
            aa = a[i]
            if blur > 0.3:
                d = v / np.linalg.norm(v)
                st = 1 + blur / (2 * r)
                p = p + np.outer(p @ d, d) * (st - 1)
                aa /= st ** 0.8
            shade = 0.86 + 0.14 * fl[i]
            pts = np.round(((p + (X[i], Y[i])) * res) * 16).astype(np.int32)[None]
            cv2.fillPoly(col, pts, tuple(float(cc) for cc in L["col"][i] * shade * aa), cv2.LINE_AA, 4)
            cv2.fillPoly(alp, pts, float(255 * aa), cv2.LINE_AA, 4)
        return col, alp

    # ------------------------------------------------------------------ frame
    def render(self, t, k=1.0, T=(0.0, 0.0), scr=None):
        """Returns (image uint8, petal colour premultiplied float32 | None, petal alpha float32 | None)."""
        S, ow, oh = self.S, self.ow, self.oh
        f = self.plate.astype(np.float32)

        if self.glow is not None and scr is not None and scr["e"] > 0:
            f[self.glow] += self.spill * (scr["low"] * 1.05) + self.halo * (scr["all"] * (1 + 0.5 * scr["bump"]))

        th = self.theta
        f1, f2, f3 = self.rayf
        p = (np.sin(th * f1 + 0.11 * t + 0.3) + 0.8 * np.sin(th * f2 - 0.17 * t + 1.9) + 0.6 * np.sin(th * f3 + 0.26 * t + 4.1)) / 2.4
        p = np.clip(0.5 + 0.5 * p, 0, 1) ** 2
        flick = 0.035 * np.sin(2 * np.pi * 0.31 * t) + 0.025 * np.sin(2 * np.pi * 0.83 * t + 1.1)
        m = cv2.resize(((p - 0.30) * (1 + flick) + flick * 0.5) * self.raymask, (ow, oh), interpolation=cv2.INTER_LINEAR)
        gain, add, _ = self.cfg["ray"]
        f *= (1 + gain * m)[..., None]
        f += m[..., None] * (add * np.float32([0.72, 0.9, 1.0]))

        if self.has_mist:
            def roll(strip, shift):
                wS = strip.shape[1]
                return strip[:, (np.arange(ow) + int(self.x0 - shift) % wS) % wS]
            mn = roll(self.mn1, 9 * S * t) * 0.6 + roll(self.mn2, 17 * S * t) * 0.4
            band = f[self.m0:self.m1]
            band += (self.mist_col - band) * (self.mist * ss(0.42, 0.75, mn) * MIST_ALPHA)[..., None]
        img = np.clip(f, 0, 255).astype(np.uint8)

        # far petals in scene space, hidden behind near objects
        col, alp = self.draw_petals(self.bg, t, (oh, ow), scene_space=True)
        if alp.any():
            sg = self.bg_blur * S
            c = cv2.GaussianBlur(col, (0, 0), sg).astype(np.float32) * self.far[..., None]
            a_ = cv2.GaussianBlur(alp, (0, 0), sg).astype(np.float32) / 255 * self.far
            img = np.clip(img * (1 - a_[..., None]) + c, 0, 255).astype(np.uint8)

        # wind sway + camera (+ transition transform) in one resample
        dx = np.zeros((oh, ow), np.float32)
        dy = np.zeros((oh, ow), np.float32)
        if self.has_grass:
            gust = 0.62 + 0.38 * np.sin(2 * np.pi * 0.11 * t - self.g_un / 520.0)
            dx[self.g0:] = self.gA * (gust * np.sin(self.gP1 + 2 * np.pi * 0.42 * t) + 0.3 * np.sin(self.gP2 + 2 * np.pi * 1.05 * t) + 0.35 * gust)
        tsl = slice(0, self.tr1)
        dx[tsl] += self.tA * (np.sin(self.tP1 + 2 * np.pi * 0.15 * t) + 0.35 * np.sin(self.tP2 + 2 * np.pi * 0.37 * t))
        dy[tsl] += self.tA * 0.55 * np.sin(self.tP3 + 2 * np.pi * 0.12 * t + 1.0)
        u, z, pan, F = self.cam(t)
        ident = k == 1.0 and T[0] == 0 and T[1] == 0
        px = self.xs if ident else (self.xs - np.float32(T[0])) / np.float32(k)
        py = self.ys if ident else (self.ys - np.float32(T[1])) / np.float32(k)
        dep = self.depth if ident else cv2.remap(self.depth, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        inv = 1.0 / (z * (1 + self.cfg["push"] * u * dep))
        kd = 0.4 + 0.9 * dep
        mx = (self.cx + (px - self.cx) * inv + pan[0] + F[0] * kd).astype(np.float32)
        my = (self.cy + (py - self.cy) * inv + pan[1] + F[1] * kd).astype(np.float32)
        sdx = cv2.remap(dx, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        my -= cv2.remap(dy, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mx -= sdx
        img = cv2.remap(img, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)

        # mid + foreground petals as a separate layer (they must pass in front of the screen)
        pc = pa = None
        col, alp = self.draw_petals(self.mid, t, (oh, ow), k=k, T=T)
        if alp.any():
            pc = cv2.GaussianBlur(col, (0, 0), 0.75 * S).astype(np.float32)
            pa = cv2.GaussianBlur(alp, (0, 0), 0.75 * S).astype(np.float32) / 255
        r = 4
        col, alp = self.draw_petals(self.fg, t, (oh // r, ow // r), res=1.0 / r, k=k, T=T)
        if alp.any():
            fc = cv2.resize(cv2.GaussianBlur(col, (0, 0), 0.9 * S), (ow, oh), interpolation=cv2.INTER_LINEAR).astype(np.float32) * 0.8
            fa = cv2.resize(cv2.GaussianBlur(alp, (0, 0), 0.9 * S), (ow, oh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255 * 0.8
            if pc is None:
                pc, pa = fc, fa
            else:
                pc = fc + pc * (1 - fa[..., None])
                pa = fa + pa * (1 - fa)
        return img, pc, pa


class Sequence:
    def __init__(self, a):
        self.a = a
        self.shots = {}
        self.vid = np.memmap(os.path.join(a.work, "screen_video.bgr"), np.uint8, "r").reshape(-1, VID_H, VID_W, 3)

    def shot(self, n):
        if n not in self.shots:
            self.shots[n] = Shot(n, self.a)
        return self.shots[n]

    def screen(self, frame, quad, t, fi, e):
        """Composite the playing video into the output-space quad."""
        ow, oh = self.a.ow, self.a.oh
        qw = float(np.linalg.norm(quad[2] - quad[3]))
        pad = int(qw * 0.22)
        bx0, by0 = int(max(0, np.floor(quad[:, 0].min()) - pad)), int(max(0, np.floor(quad[:, 1].min()) - pad))
        bx1, by1 = int(min(ow, np.ceil(quad[:, 0].max()) + pad)), int(min(oh, np.ceil(quad[:, 1].max()) + pad))
        if bx1 - bx0 < 4 or by1 - by0 < 4:
            return frame
        bw, bh = bx1 - bx0, by1 - by0
        cw = int(np.clip(qw * 1.1, 64, VID_W)) // 2 * 2
        ch = int(cw / 1.6) // 2 * 2          # 16:10 panel
        vh = int(cw * 9 / 16) // 2 * 2       # 16:9 video, letterboxed (never stretched)
        vi = int(np.clip(round((t - T_VID) * FPS), 0, len(self.vid) - 1))
        fr = cv2.resize(self.vid[vi], (cw, vh), interpolation=cv2.INTER_AREA).astype(np.float32)
        content = np.zeros((ch, cw, 3), np.float32)
        o = (ch - vh) // 2
        content[o:o + vh] = fr * 0.93
        cy_, cx_ = np.mgrid[0:ch, 0:cw].astype(np.float32)
        u_, v_ = cx_ / cw, cy_ / ch
        sheen = 0.030 * (1 - v_) ** 1.5 + 0.035 * np.exp(-((u_ - 0.72 + 0.35 * (v_ - 0.5)) / 0.16) ** 2)
        content = (content + np.float32([9, 8, 8])) * e + sheen[..., None] * np.float32([235, 222, 205])
        content += np.random.default_rng(1000 + fi).normal(0, 1.5, (ch, cw)).astype(np.float32)[..., None]
        q = (quad - (bx0, by0)).astype(np.float32)
        Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]]), q)
        scr = cv2.warpPerspective(content, Hm, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        scr = cv2.GaussianBlur(scr, (0, 0), 0.6)                       # match the photo's softness
        am = np.zeros((bh, bw), np.uint8)
        cv2.fillPoly(am, np.round(q * 16).astype(np.int32)[None], 255, cv2.LINE_AA, 4)
        al = (cv2.GaussianBlur(am, (0, 0), 0.7).astype(np.float32) / 255)[..., None]   # 1-2 px feather
        roi = frame[by0:by1, bx0:bx1]
        roi[:] = roi * (1 - al) + scr * al
        bump = np.exp(-((t - (T_ON + 0.3)) / 0.22) ** 2)
        ds = max(1, int(round(qw / 120)))
        sm = cv2.resize(scr * al, (max(2, bw // ds), max(2, bh // ds)), interpolation=cv2.INTER_AREA)
        bloom = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 0.045 * qw / ds), (bw, bh), interpolation=cv2.INTER_LINEAR)
        roi += bloom * (0.10 + 0.10 * bump)
        return frame

    def render(self, fi):
        a = self.a
        t = fi / FPS
        ow, oh = a.ow, a.oh
        e = float(ss(T_ON, T_VID, t))
        vi = int(np.clip(round((t - T_VID) * FPS), 0, len(self.vid) - 1))
        small = self.vid[vi][::8, ::8].astype(np.float32)
        scr = dict(e=e, all=small.mean((0, 1)) / 255 * e, low=small[small.shape[0] // 2:].mean((0, 1)) / 255 * e,
                   bump=float(np.exp(-((t - (T_ON + 0.3)) / 0.22) ** 2)))
        D = SLIDE * oh
        quad = None
        mblur = 0

        def slide(n1, n2, win, sign):
            """n1 leaves, n2 arrives; sign=+1 camera tilts up (picture moves down)."""
            tau = ease((t - win[0]) / (win[1] - win[0]))
            dtau = ease((t + 0.5 / FPS - win[0]) / (win[1] - win[0])) - ease((t - 0.5 / FPS - win[0]) / (win[1] - win[0]))
            T1, T2 = (0.0, sign * tau * D), (0.0, -sign * (1 - tau) * D)
            # the arriving still enters from the top (tilt up) or bottom (tilt down); dissolve row by
            # row across the band where both pictures are valid, so no out-of-frame area ever shows
            yn = np.clip((np.arange(oh, dtype=np.float32) - tau * D) / (oh - D), 0, 1)
            if sign < 0:
                yn = np.clip((np.arange(oh, dtype=np.float32) - (1 - tau) * D) / (oh - D), 0, 1)[::-1]
            w = ss(yn * 0.75, yn * 0.75 + 0.25, tau).astype(np.float32)[:, None]
            return [(n1, 1.0, T1, 1 - w), (n2, 1.0, T2, w)], abs(dtau) * D * 0.7

        if t < T_AB[0]:
            parts = [("vista", 1.0, (0.0, 0.0), 1.0)]
        elif t < T_AB[1]:
            parts, mblur = slide("vista", "canopy", T_AB, +1)
        elif t < T_BC[0]:
            parts = [("canopy", 1.0, (0.0, 0.0), 1.0)]
        elif t < T_BC[1]:
            parts, mblur = slide("canopy", "wide", T_BC, -1)
        elif t < T_GLIDE[0]:
            parts = [("wide", 1.0, (0.0, 0.0), 1.0)]
        elif t < T_GLIDE[1]:
            # match zoom: keep the laptop screen registered between the two stills while dissolving
            s = ease((t - T_GLIDE[0]) / (T_GLIDE[1] - T_GLIDE[0]))
            qW, qD = self.shot("wide").quad_out(t), self.shot("closeup").quad_out(t)
            cW, cD = qW.mean(0), qD.mean(0)
            m = float(((qD - cD) * (qW - cW)).sum() / ((qW - cW) ** 2).sum())
            c = cW + (cD - cW) * s
            kW, kD = m ** s, m ** (s - 1)
            TD = c - kD * cD
            # the close-up only covers part of the frame until the zoom completes: feather its edge
            xs_, ys_ = np.arange(ow, dtype=np.float32)[None], np.arange(oh, dtype=np.float32)[:, None]
            d = np.minimum(np.minimum(xs_ - TD[0], TD[0] + kD * ow - xs_), np.minimum(ys_ - TD[1], TD[1] + kD * oh - ys_))
            fe = 0.30 * oh * kD
            m_ = np.maximum(np.clip(d / fe, 0, 1), float(ss(0.92, 1.0, s)))   # never show beyond the close-up's edge until it nearly fills the frame
            wD = (float(ss(0.15, 0.6, s)) * m_ * m_ * (3 - 2 * m_)).astype(np.float32)
            parts = [("wide", kW, tuple(c - kW * cW), 1 - wD), ("closeup", kD, tuple(TD), wD)]
        else:
            parts = [("closeup", 1.0, (0.0, 0.0), 1.0)]

        frame = None
        pcs = pas = None
        quads = []
        for n, k, T, w in parts:
            sh = self.shot(n)
            img, pc, pa = sh.render(t, k, T, scr)
            w3 = w[..., None] if np.ndim(w) == 2 else w
            frame = img * w3 if frame is None else frame + img * w3
            if pc is not None:
                pcs = pc * w3 if pcs is None else pcs + pc * w3
                pas = pa * w if pas is None else pas + pa * w
            if sh.quad is not None:
                q = sh.quad_out(t, k, T)
                if np.ndim(w) == 2:   # weight of this still where its laptop screen is
                    cq = q.mean(0)
                    wq = float(w[int(np.clip(cq[1], 0, w.shape[0] - 1)), int(np.clip(cq[0], 0, w.shape[1] - 1))])
                else:
                    wq = float(w)
                quads.append((q, wq))
        frame = np.asarray(frame, np.float32)
        tw = sum(w for _, w in quads)
        if tw > 0.003:
            quad = sum(q * (w / tw) for q, w in quads)
            if tw > 0.997:
                frame = self.screen(frame, quad, t, fi, e)
            else:             # laptop still dissolving in: draw the screen only as much as it is visible
                frame = frame * (1 - tw) + self.screen(frame.copy(), quad, t, fi, e) * tw
        if pcs is not None:
            frame = frame * (1 - pas[..., None]) + pcs
        out = np.clip(frame, 0, 255).astype(np.uint8)
        L = int(mblur) | 1
        if L >= 3:
            out = cv2.blur(out, (1, L), borderType=cv2.BORDER_REFLECT_101)
        return out


def work(job):
    a, k, f0, f1 = job
    cv2.setNumThreads(1)
    seq = Sequence(a)
    seg = os.path.join(a.work, f"seg_{a.tag}_{k:02d}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{a.ow}x{a.oh}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-g", str(FPS), "-threads", "2", seg], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        img = seq.render(fi)
        ff.stdin.write(img.tobytes())
        if fi in a.dump:
            cv2.imwrite(os.path.join(a.frames_dir, f"{a.tag}_t{fi / FPS:05.2f}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 93])
    ff.stdin.close()
    assert ff.wait() == 0
    return seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="output/seq/work")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--dump", default="", help="comma separated times (s) to also save as JPG")
    a = ap.parse_args()
    a.ow, a.oh = map(int, a.size.split("x"))
    a.tag = os.path.splitext(os.path.basename(a.out))[0]
    a.frames_dir = os.path.join(os.path.dirname(a.out) or ".", "frames")
    os.makedirs(a.frames_dir, exist_ok=True)
    cache = os.path.join(a.work, "screen_video.bgr")
    if not os.path.exists(cache):
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-vf",
                               f"fps={FPS},scale={VID_W}:{VID_H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "bgr24", cache])
    nvid = os.path.getsize(cache) // (VID_W * VID_H * 3)
    a.total = T_VID + nvid / FPS
    f0 = int(round(a.t0 * FPS))
    f1 = int(round((a.t1 if a.t1 is not None else a.total) * FPS))
    a.dump = {int(round(float(x) * FPS)) for x in a.dump.split(",") if x}
    print(f"video frames={nvid} total={a.total:.2f}s rendering frames {f0}..{f1} at {a.ow}x{a.oh}", flush=True)
    edges = np.linspace(f0, f1, a.jobs + 1).round().astype(int)
    with Pool(a.jobs) as pool:
        segs = pool.map(work, [(a, k, int(edges[k]), int(edges[k + 1])) for k in range(a.jobs)])
    lst = os.path.join(a.work, f"concat_{a.tag}.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{os.path.abspath(s)}'\n" for s in segs)
    ad = f"adelay={int(T_VID * 1000)}:all=1,atrim={f0 / FPS}:{f1 / FPS},asetpts=PTS-STARTPTS"
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", a.video,
                           "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-af", ad, "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", "-shortest", a.out])
    for s in segs:
        os.remove(s)
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
