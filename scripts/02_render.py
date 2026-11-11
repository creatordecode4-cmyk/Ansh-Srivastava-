#!/usr/bin/env python3
"""Step 2-4: animate the still and play the video on the laptop screen.

  python3 scripts/02_render.py --video output/input/screen_video.mp4 \
      --out output/final_1080p.mp4                 # 1920x1080
  python3 scripts/02_render.py ... --size 1080x1920 --out output/final_vertical.mp4
  python3 scripts/02_render.py ... --size 960x540 --t0 0.5 --t1 3.5 --out output/preview.mp4

Every effect is a closed-form function of time, so frames can be rendered in
parallel chunks and in any order.
"""
import argparse
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

FPS = 30
INTRO = 1.5          # seconds before the video starts
DARK = 1.0           # screen stays off this long, then fades up until INTRO
NATIVE_W, NATIVE_H = 1376, 768
VID_W, VID_H = 768, 432  # cached screen-video resolution

# ---- look controls (all subtle on purpose) ---------------------------------
PUSH_FAR, PUSH_NEAR = 0.030, 0.050   # push-in over the whole clip (far / near layers)
FLOAT_PX = 1.6                        # handheld float amplitude, native px
GRASS_PX = 2.3                        # grass tip sway, native px
TREE_PX = 1.25                        # blossom sway, native px
N_BG, N_MID, N_FG = 105, 70, 9       # petals per depth layer
RAY_GAIN, RAY_ADD = 0.11, 5.0
MIST_ALPHA = 0.13


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def smooth_noise(rng, h, w, cell):
    """Smooth random field in [-1,1], feature size ~cell px."""
    gh, gw = max(2, int(h / cell) + 3), max(2, int(w / cell) + 3)
    g = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
    big = cv2.resize(g, (int(gw * cell), int(gh * cell)), interpolation=cv2.INTER_CUBIC)
    return big[:h, :w]


PETAL = np.float32([(0, -1), (.35, -.75), (.62, -.3), (.68, .15), (.55, .6), (.3, .9), (.08, .97), (0, .84),
                    (-.08, .97), (-.3, .9), (-.55, .6), (-.68, .15), (-.62, -.3), (-.35, -.75)])
PETAL_COLORS = np.float32([(203, 186, 246), (214, 198, 252), (226, 214, 255), (238, 234, 252), (196, 176, 238)])  # BGR


class Scene:
    def __init__(self, a):
        self.a = a
        self.ow, self.oh = a.ow, a.oh
        S = self.S = self.oh / NATIVE_H
        P = np.load(os.path.join(a.work, "prep.npz"))
        sw = int(round(NATIVE_W * S))
        self.quad_n = P["quad"]
        cxn = self.quad_n[:, 0].mean()
        x0 = self.x0 = int(np.clip(round(cxn * S - self.ow / 2), 0, sw - self.ow))
        ow, oh = self.ow, self.oh

        def up(m, interp=cv2.INTER_LINEAR):
            return np.ascontiguousarray(cv2.resize(m, (sw, oh), interpolation=interp)[:, x0:x0 + ow])

        plate = up(P["plate_off"], cv2.INTER_LANCZOS4 if S > 1 else cv2.INTER_AREA)
        if S > 1:  # mild unsharp to recover what the upscale softened
            bl = cv2.GaussianBlur(plate, (0, 0), 0.8 * S)
            plate = cv2.addWeighted(plate, 1.22, bl, -0.22, 0)
        self.plate = plate
        self.depth = up(P["depth"])
        self.spill = up(P["spill_map"])
        self.lap_soft = up(P["lap_soft"])
        lap = up(P["lap"].astype(np.float32))
        self.far = up(P["far"])
        grass_amp, tree_amp, mist = up(P["grass_amp"]), up(P["tree_amp"]), up(P["mist"])

        rng = np.random.default_rng(7)
        ys, xs = np.mgrid[0:oh, 0:ow].astype(np.float32)
        self.xs, self.ys = xs, ys
        un, vn = (xs + x0) / S, ys / S  # native coordinates of every output pixel

        # ---------------- screen ----------------
        self.quad = self.quad_n * S - (x0, 0)
        q = self.quad
        pad = int(70 * S)
        bx0, by0 = int(max(0, q[:, 0].min() - pad)), int(max(0, q[:, 1].min() - pad))
        bx1, by1 = int(min(ow, q[:, 0].max() + pad)), int(min(oh, q[:, 1].max() + pad * 2.2))
        self.bb = (bx0, by0, bx1, by1)
        bw, bh = bx1 - bx0, by1 - by0
        self.cw = int(np.linalg.norm(q[2] - q[3]) * 1.1) // 2 * 2
        self.ch = int(self.cw / 1.6) // 2 * 2          # 16:10 panel
        self.vh = int(self.cw * 9 / 16) // 2 * 2       # 16:9 video, letterboxed
        self.Hm = cv2.getPerspectiveTransform(
            np.float32([[0, 0], [self.cw, 0], [self.cw, self.ch], [0, self.ch]]), (q - (bx0, by0)).astype(np.float32))
        k = 8
        am = np.zeros((bh * k, bw * k), np.uint8)
        cv2.fillConvexPoly(am, np.round((q - (bx0, by0)) * k).astype(np.int32), 255)
        am = cv2.resize(am, (bw, bh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        self.salpha = cv2.GaussianBlur(am, (0, 0), 0.55 * max(1.0, S / 1.4))[..., None]  # ~1-2 px feather
        # glass reflection: faint sky-coloured sheen, stronger toward the top + one soft diagonal band
        cy_, cx_ = np.mgrid[0:self.ch, 0:self.cw].astype(np.float32)
        u_, v_ = cx_ / self.cw, cy_ / self.ch
        sheen = 0.030 * (1 - v_) ** 1.5 + 0.035 * np.exp(-((u_ - 0.72 + 0.35 * (v_ - 0.5)) / 0.16) ** 2)
        self.sheen = sheen[..., None] * np.float32([235, 222, 205])
        # light the screen throws: keyboard/palm rest (measured spill map) + grass right around the laptop
        near = ss(0.5, 0.7, self.depth)
        halo = cv2.GaussianBlur(lap, (0, 0), 34 * S) * near * (1 - lap) * (vn > self.quad_n[:, 1].max() - 40)
        self.halo = (halo * 26)[by0:by1, bx0:bx1, None]
        self.spill_bb = self.spill[by0:by1, bx0:bx1, None]
        self.vid = np.memmap(os.path.join(a.work, "screen_video.bgr"), np.uint8, "r").reshape(-1, VID_H, VID_W, 3)

        # ---------------- sway ----------------
        self.g0 = int(np.argmax(grass_amp.max(1) > 0.01))
        gs = slice(self.g0, oh)
        depth_boost = 0.75 + 0.6 * (vn[gs] - vn[self.g0, 0]) / max(1.0, NATIVE_H - vn[self.g0, 0])
        self.gA = grass_amp[gs] * GRASS_PX * S * depth_boost
        self.gP1 = -un[gs] / 85.0 + 1.6 * smooth_noise(rng, oh - self.g0, ow, 45 * S)
        self.gP2 = -un[gs] / 30.0 + 2.5 * smooth_noise(rng, oh - self.g0, ow, 16 * S)
        self.g_un = un[self.g0:self.g0 + 1]
        self.t1 = int(oh - np.argmax(tree_amp.max(1)[::-1] > 0.01))
        ts = slice(0, self.t1)
        side = np.where(un[ts] > NATIVE_W / 2, 1.3, 0.0)  # left and right tree out of phase
        self.tA = tree_amp[ts] * TREE_PX * S
        self.tP1 = side + 1.3 * smooth_noise(rng, self.t1, ow, 110 * S)
        self.tP2 = side * 0.6 + 2.0 * smooth_noise(rng, self.t1, ow, 40 * S)
        self.tP3 = 1.5 * smooth_noise(rng, self.t1, ow, 90 * S)

        # ---------------- light rays (quarter res) ----------------
        r = 4
        lw, lh = ow // r, oh // r
        ul = cv2.resize(un, (lw, lh), interpolation=cv2.INTER_AREA)
        vl = cv2.resize(vn, (lw, lh), interpolation=cv2.INTER_AREA)
        sx, sy = NATIVE_W * 1.05, -NATIVE_H * 0.10
        self.theta = np.arctan2(vl - sy, ul - sx)
        rad = np.hypot(ul - sx, vl - sy)
        fall = np.clip(1 - rad / (NATIVE_W * 0.95), 0, 1) ** 1.1
        farl = cv2.resize(self.far, (lw, lh), interpolation=cv2.INTER_AREA)
        lapl = cv2.resize(self.lap_soft, (lw, lh), interpolation=cv2.INTER_AREA)
        self.raymask = fall * (0.35 + 0.65 * farl) * (1 - lapl) * (1 - 0.6 * ss(0.68, 0.8, vl / NATIVE_H))
        self.lsize = (lw, lh)

        # ---------------- mist ----------------
        self.m0 = int(np.argmax(mist.max(1) > 0.01))
        self.m1 = int(oh - np.argmax(mist.max(1)[::-1] > 0.01))
        mh = self.m1 - self.m0
        self.mist = mist[self.m0:self.m1]
        tw = int(NATIVE_W * S * 2)
        nrng = np.random.default_rng(11)
        # wide, tileable-in-x noise strips (built at fixed native size so every chunk/crop agrees)
        def strip(cellx, celly):
            g = nrng.uniform(0, 1, (int(NATIVE_H / celly) + 3, int(2 * NATIVE_W / cellx))).astype(np.float32)
            g = np.concatenate([g, g[:, :3]], 1)
            big = cv2.resize(g, (int(g.shape[1] * cellx * S), int(g.shape[0] * celly * S)), interpolation=cv2.INTER_CUBIC)
            return big[self.m0:self.m1, :int((g.shape[1] - 3) * cellx * S)]
        self.mn1, self.mn2 = strip(170, 26), strip(90, 16)
        self.mist_col = np.float32([222, 228, 236])

        # ---------------- camera ----------------
        self.cx, self.cy = ow / 2.0, oh * 0.60

        # ---------------- petals (defined in native coords so every output size matches) ----------------
        pr = np.random.default_rng(23)

        def layer(n, size, vy, vx, sway, idle):
            d = dict(n=n)
            d["size"] = pr.uniform(*size, n)
            d["vy"] = pr.uniform(*vy, n)
            d["vx"] = pr.uniform(*vx, n)
            d["x0"] = pr.uniform(-0.45 * NATIVE_W, NATIVE_W * 1.02, n)
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
            d["tfall"] = (NATIVE_H + 2 * d["m"]) / d["vy"]
            d["land"] = np.zeros(n, bool)
            d["rest"] = np.zeros(n)
            d["P"] = d["tfall"] + pr.uniform(*idle, n)
            d["ph"] = pr.uniform(0, 1, n) * d["P"]
            d["dep"] = np.zeros(n)
            return d

        self.bg = layer(N_BG, (1.6, 3.2), (26, 48), (16, 36), (4, 10), (0, 2))
        self.mid = layer(N_MID, (4.2, 8.0), (62, 108), (40, 85), (8, 20), (0, 3))
        self.fg = layer(N_FG, (17, 32), (150, 250), (110, 210), (15, 35), (3, 9))
        self.mid["dep"][:] = 0.72
        self.fg["dep"][:] = 1.25
        # some mid petals land on the grass, rest a while, then fade
        L = self.mid
        depth_n = P["depth"]
        lapn = cv2.dilate(P["lap"].astype(np.uint8), np.ones((25, 25), np.uint8))
        for i in np.where(pr.uniform(0, 1, L["n"]) < 0.32)[0]:
            for _ in range(30):
                ly = pr.uniform(0.735, 0.97) * NATIVE_H
                tf = (ly + L["m"][i]) / L["vy"][i]
                lx = L["x0"][i] + L["vx"][i] * tf + L["swA"][i] * np.sin(L["swF"][i] * tf + L["swP"][i])
                if 5 < lx < NATIVE_W - 5 and not lapn[int(ly), int(lx)]:
                    break
                L["x0"][i] = pr.uniform(-0.45 * NATIVE_W, NATIVE_W * 1.02)
            else:
                continue
            L["land"][i], L["tfall"][i], L["rest"][i] = True, tf, pr.uniform(3.0, 5.5)
            L["P"][i] = tf + L["rest"][i] + 0.9 + pr.uniform(0, 2)
            L["dep"][i] = depth_n[int(ly), int(lx)]
            L["size"][i] *= 0.65 + 0.9 * (ly / NATIVE_H - 0.735) / 0.235  # nearer ground = bigger
        self.mid["ph"] = pr.uniform(0, 1, L["n"]) * L["P"]

    # ------------------------------------------------------------------ camera
    def cam(self, t):
        u = t / self.a.total
        F = FLOAT_PX * self.S * np.array([
            np.sin(2 * np.pi * 0.09 * t) + 0.5 * np.sin(2 * np.pi * 0.21 * t + 1.3),
            0.8 * np.sin(2 * np.pi * 0.075 * t + 2.1) + 0.4 * np.sin(2 * np.pi * 0.17 * t + 0.4)])
        return u, F

    def cam_fwd(self, x, y, dep, t):
        """scene position -> output position for a point at depth dep (1 = near)."""
        u, F = self.cam(t)
        s = 1.004 + u * (PUSH_FAR + (PUSH_NEAR - PUSH_FAR) * dep)
        k = 0.4 + 0.9 * dep
        return self.cx + (x - F[0] * k - self.cx) * s, self.cy + (y - F[1] * k - self.cy) * s, s

    # ------------------------------------------------------------------ petals
    def petal_state(self, L, t):
        tau = np.mod(t + L["ph"], L["P"])
        tf = np.minimum(tau, L["tfall"])            # frozen after landing
        y = -L["m"] + L["vy"] * tf
        x = L["x0"] + L["vx"] * tf + L["swA"] * np.sin(L["swF"] * tf + L["swP"])
        vx = L["vx"] + L["swA"] * L["swF"] * np.cos(L["swF"] * tf + L["swP"])
        landed = L["land"] & (tau >= L["tfall"])
        vis = (tau < L["tfall"]) | landed
        a = L["alpha"] * np.where(landed, 1 - np.clip((tau - L["tfall"] - L["rest"]) / 0.9, 0, 1), 1.0)
        rot = L["rot0"] + L["rotS"] * tf
        fl = np.cos(L["flF"] * tf + L["flP"])
        return x, y, np.where(landed, 0, vx), np.where(landed, 0, L["vy"]), rot, fl, a * vis, landed

    def draw_petals(self, L, t, shape, res=1.0, scene_space=False):
        """Returns premultiplied colour (float32) and alpha (float32) canvases."""
        h, w = shape
        col = np.zeros((h, w, 3), np.uint8)
        alp = np.zeros((h, w), np.uint8)
        x, y, vx, vy, rot, fl, a, landed = self.petal_state(L, t)
        S = self.S
        X, Y = x * S - self.x0, y * S
        if scene_space:
            sc = np.ones_like(X)
        else:
            X, Y, sc = self.cam_fwd(X, Y, L["dep"], t)
        size = L["size"] * S * sc
        for i in range(L["n"]):
            if a[i] <= 0.01:
                continue
            r = size[i]
            if X[i] < -3 * r or X[i] > self.ow + 3 * r or Y[i] < -3 * r or Y[i] > self.oh + 3 * r:
                continue
            p = PETAL * (r * (0.28 + 0.72 * abs(fl[i])), r)          # tumble: petal turns edge-on
            c, s_ = np.cos(rot[i]), np.sin(rot[i])
            p = p @ np.float32([[c, s_], [-s_, c]])
            if landed[i]:
                p[:, 1] *= 0.5                                       # lying on the ground, seen at a low angle
            v = np.float32([vx[i], vy[i]]) * S * sc[i]
            blur = np.linalg.norm(v) / FPS * 0.5                      # 180 degree shutter
            aa = a[i]
            if blur > 0.3:
                d = v / np.linalg.norm(v)
                st = 1 + blur / (2 * r)
                p = p + np.outer(p @ d, d) * (st - 1)
                aa /= st ** 0.8
            shade = 0.86 + 0.14 * fl[i]                              # catches the sun as it turns
            pts = np.round(((p + (X[i], Y[i])) * res) * 16).astype(np.int32)[None]
            cv2.fillPoly(col, pts, tuple(float(cc) for cc in L["col"][i] * shade * aa), cv2.LINE_AA, 4)
            cv2.fillPoly(alp, pts, float(255 * aa), cv2.LINE_AA, 4)
        return col, alp

    @staticmethod
    def over(img, col, alp, sigma, mask=None, size=None):
        if not alp.any():
            return img
        if size is not None:
            col = cv2.resize(col, size, interpolation=cv2.INTER_LINEAR)
            alp = cv2.resize(alp, size, interpolation=cv2.INTER_LINEAR)
        ys_, xs_ = np.where(alp > 0)
        pad = int(sigma * 3) + 2
        y0, y1 = max(0, ys_.min() - pad), min(alp.shape[0], ys_.max() + pad + 1)
        x0, x1 = max(0, xs_.min() - pad), min(alp.shape[1], xs_.max() + pad + 1)
        c = cv2.GaussianBlur(col[y0:y1, x0:x1], (0, 0), sigma).astype(np.float32)
        a = cv2.GaussianBlur(alp[y0:y1, x0:x1], (0, 0), sigma).astype(np.float32) / 255
        if mask is not None:
            m = mask[y0:y1, x0:x1]
            c, a = c * m[..., None], a * m
        roi = img[y0:y1, x0:x1].astype(np.float32)
        img[y0:y1, x0:x1] = np.clip(roi * (1 - a[..., None]) + c, 0, 255).astype(np.uint8)
        return img

    # ------------------------------------------------------------------ frame
    def render(self, fi):
        t = fi / FPS
        S, ow, oh = self.S, self.ow, self.oh
        img = self.plate.copy()

        # --- 1. laptop screen
        bx0, by0, bx1, by1 = self.bb
        e = float(ss(DARK, INTRO, t))
        vi = int(np.clip(round((t - INTRO) * FPS), 0, len(self.vid) - 1))
        fr = cv2.resize(self.vid[vi], (self.cw, self.vh), interpolation=cv2.INTER_AREA).astype(np.float32)
        content = np.zeros((self.ch, self.cw, 3), np.float32)
        o = (self.ch - self.vh) // 2
        content[o:o + self.vh] = fr * 0.93
        content = (content + np.float32([9, 8, 8])) * e + self.sheen   # backlit black + glass sheen
        frng = np.random.default_rng(1000 + fi)
        content += frng.normal(0, 1.5, content.shape[:2]).astype(np.float32)[..., None]
        scr = cv2.warpPerspective(content, self.Hm, (bx1 - bx0, by1 - by0), flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REPLICATE)
        scr = cv2.GaussianBlur(scr, (0, 0), 0.42 * S)                   # match the photo's softness
        roi = img[by0:by1, bx0:bx1].astype(np.float32)
        a = self.salpha
        roi = roi * (1 - a) + scr * a
        lit = scr * a
        sm = cv2.resize(lit, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        bump = np.exp(-((t - (DARK + 0.3)) / 0.22) ** 2)               # soft glow pulse as it wakes up
        bloom = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 3.2 * S), (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_LINEAR)
        roi += bloom * (0.10 + 0.10 * bump)
        avg_all = fr.mean((0, 1)) / 255 * e
        avg_low = fr[self.vh // 2:].mean((0, 1)) / 255 * e
        roi += self.spill_bb * (avg_low * 1.05) + self.halo * (avg_all * (1 + 0.5 * bump))
        img[by0:by1, bx0:bx1] = np.clip(roi, 0, 255).astype(np.uint8)

        # --- 2. sun shafts + gentle flicker
        th = self.theta
        p = (np.sin(th * 41 + 0.11 * t + 0.3) + 0.8 * np.sin(th * 73 - 0.17 * t + 1.9)
             + 0.6 * np.sin(th * 127 + 0.26 * t + 4.1)) / 2.4
        p = np.clip(0.5 + 0.5 * p, 0, 1) ** 2
        flick = 0.035 * np.sin(2 * np.pi * 0.31 * t) + 0.025 * np.sin(2 * np.pi * 0.83 * t + 1.1)
        m = cv2.resize(((p - 0.30) * (1 + flick) + flick * 0.5) * self.raymask, (ow, oh), interpolation=cv2.INTER_LINEAR)
        f = img.astype(np.float32)
        f *= (1 + RAY_GAIN * m)[..., None]
        f += m[..., None] * (RAY_ADD * np.float32([0.72, 0.9, 1.0]))

        # --- 3. mist drifting over the river
        def roll(strip, shift):
            wS = strip.shape[1]
            s0 = int(self.x0 - shift) % wS
            idx = (np.arange(ow) + s0) % wS
            return strip[:, idx]
        mn = roll(self.mn1, 9 * S * t) * 0.6 + roll(self.mn2, 17 * S * t) * 0.4
        ma = (self.mist * ss(0.42, 0.75, mn) * MIST_ALPHA)[..., None]
        band = f[self.m0:self.m1]
        band += (self.mist_col - band) * ma
        img = np.clip(f, 0, 255).astype(np.uint8)

        # --- 4. far petals (scene space, hidden behind near objects)
        col, alp = self.draw_petals(self.bg, t, (oh, ow), scene_space=True)
        img = self.over(img, col, alp, 0.6 * S, mask=self.far)

        # --- 5. wind sway + camera in ONE resample
        dx = np.zeros((oh, ow), np.float32)
        dy = np.zeros((oh, ow), np.float32)
        gust = 0.62 + 0.38 * np.sin(2 * np.pi * 0.11 * t - self.g_un / 520.0)
        w1 = 2 * np.pi * 0.42 * t
        dx[self.g0:] = self.gA * (gust * np.sin(self.gP1 + w1) + 0.3 * np.sin(self.gP2 + 2 * np.pi * 1.05 * t) + 0.35 * gust)
        w2 = 2 * np.pi * 0.15 * t
        tsl = slice(0, self.t1)
        dx[tsl] += self.tA * (np.sin(self.tP1 + w2) + 0.35 * np.sin(self.tP2 + 2 * np.pi * 0.37 * t))
        dy[tsl] += self.tA * 0.55 * np.sin(self.tP3 + 2 * np.pi * 0.12 * t + 1.0)
        u, F = self.cam(t)
        inv = 1.0 / (1.004 + u * (PUSH_FAR + (PUSH_NEAR - PUSH_FAR) * self.depth))
        k = 0.4 + 0.9 * self.depth
        mx = (self.cx + (self.xs - self.cx) * inv + F[0] * k).astype(np.float32)
        my = (self.cy + (self.ys - self.cy) * inv + F[1] * k).astype(np.float32)
        sdx = cv2.remap(dx, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        my -= cv2.remap(dy, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mx -= sdx
        img = cv2.remap(img, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        # --- 6. mid + foreground petals (output space)
        col, alp = self.draw_petals(self.mid, t, (oh, ow))
        img = self.over(img, col, alp, 0.75 * S)
        r = 4
        col, alp = self.draw_petals(self.fg, t, (oh // r, ow // r), res=1.0 / r)
        if alp.any():
            col = cv2.GaussianBlur(col, (0, 0), 0.9 * S)
            alp = cv2.GaussianBlur(alp, (0, 0), 0.9 * S)
            img = self.over(img, col, (alp * 0.8).astype(np.uint8), 1.0, size=(ow, oh))
        return img


def encode_cmd(a, path):
    return ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{a.ow}x{a.oh}",
            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-g", str(FPS), "-threads", "2", path]


def work(job):
    a, k, f0, f1 = job
    cv2.setNumThreads(1)
    sc = Scene(a)
    seg = os.path.join(a.work, f"seg_{a.tag}_{k:02d}.mp4")
    ff = subprocess.Popen(encode_cmd(a, seg), stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        img = sc.render(fi)
        ff.stdin.write(img.tobytes())
        if fi in a.dump:
            cv2.imwrite(os.path.join(a.frames_dir, f"{a.tag}_f{fi:04d}.png"), img)
    ff.stdin.close()
    assert ff.wait() == 0
    return seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="output/work")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--dump", default="", help="comma separated times (s) to also save as PNG")
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
    a.total = INTRO + nvid / FPS
    f0 = int(round(a.t0 * FPS))
    f1 = int(round((a.t1 if a.t1 is not None else a.total) * FPS))
    a.dump = {int(round(float(x) * FPS)) for x in a.dump.split(",") if x}
    print(f"video frames={nvid} total={a.total:.2f}s rendering frames {f0}..{f1} at {a.ow}x{a.oh}", flush=True)

    edges = np.linspace(f0, f1, a.jobs + 1).round().astype(int)
    jobs = [(a, k, int(edges[k]), int(edges[k + 1])) for k in range(a.jobs)]
    with Pool(a.jobs) as pool:
        segs = pool.map(work, jobs)
    lst = os.path.join(a.work, f"concat_{a.tag}.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{os.path.abspath(s)}'\n" for s in segs)
    # original audio, delayed by the intro (trimmed to the rendered window)
    ad = f"adelay={int(INTRO * 1000)}:all=1,atrim={f0 / FPS}:{f1 / FPS},asetpts=PTS-STARTPTS"
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", a.video,
                           "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-af", ad, "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", "-shortest", a.out])
    for s in segs:
        os.remove(s)
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
