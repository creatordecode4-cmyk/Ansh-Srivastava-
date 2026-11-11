#!/usr/bin/env python3
"""Realism fix, step 2: look-around shots as before, then ONE layered master plate for the
laptop reveal + continuous push-in (no crossfades between stills).

  0.00-6.20  vista -> canopy                (identical to seq_render.py)
  6.20-6.43  7-frame whip-pan               (hides the only cut)
  6.43-end   laptop: wide -> slow push-in   (bg / laptop / foreground-grass layers of one image)
  8.10       screen wakes, 8.60 video + audio start

  python3 scripts/fix_render.py --video output/input/screen_video.mp4 --out output/fix/final_fixed_1080p.mp4
  python3 scripts/fix_render.py ... --t0 8 --t1 14 --out output/fix/preview_8-14s.mp4
"""
import argparse
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seq_render as SR  # noqa: E402  (look-around shots are reused unchanged)

FPS = 30
NW, NH = 1376, 768
T_WHIP = 6.2
WHIP_FRAMES = 7
T_LAP = T_WHIP + WHIP_FRAMES / FPS
T_ON, T_VID = SR.T_ON, SR.T_VID          # 8.1 / 8.6, same as before so the audio keeps its place
T_CLOSE = 14.5                            # push-in essentially complete
LID_WIDE, LID_CLOSE = 0.30, 0.53          # lid width as a fraction of frame width
PARALLAX = 0.22                           # how much faster near things grow than far ones
CREEP = 0.05                              # extra slow zoom spread over the whole shot
SCREEN_GAIN = 0.83
SCREEN_TINT = np.float32([0.90, 0.965, 1.0])   # BGR: slightly warm white
ss, ease = SR.ss, SR.ease


class LaptopShot:
    def __init__(self, a):
        self.a = a
        ow, oh = self.ow, self.oh = a.ow, a.oh
        w = os.path.join(a.work)
        P = np.load(os.path.join(w, "fix_prep.npz"))
        K = self.K = int(P["K"])
        self.bg = cv2.imread(os.path.join(w, "layer_bg.png"))
        lap = cv2.imread(os.path.join(w, "layer_laptop.png"), cv2.IMREAD_UNCHANGED)
        self.lap_bgr, self.lap_a = np.ascontiguousarray(lap[..., :3]), np.ascontiguousarray(lap[..., 3])
        self.lap_spill = np.load(os.path.join(w, "layer_laptop_spill.npy")).astype(np.float32)
        fg = cv2.imread(os.path.join(w, "layer_fg.png"), cv2.IMREAD_UNCHANGED)
        self.fg_bgr, self.fg_a = np.ascontiguousarray(fg[..., :3]), np.ascontiguousarray(fg[..., 3])
        self.lap_org, self.fg_org = P["lap_org"].astype(np.float32), P["fg_org"].astype(np.float32)
        self.quad = P["quad"] / K - (K - 1) / (2.0 * K)          # native coords
        self.depth, self.far, self.halo = P["depth"], P["far"], P["halo"]
        self.lap_dep = float(P["lap_dep"])
        self.grass_amp, self.tree_amp, self.mist = P["grass_amp"], P["tree_amp"], P["mist"]
        box = P["lap_box"]
        tlx, trx = self.quad[0, 0], self.quad[1, 0]
        lid_w = (trx - tlx) * 1.085                               # screen + bezel
        cxn = self.quad[:, 0].mean()
        scr_cy = self.quad[:, 1].mean()
        # wide: laptop lid ~30% of the frame, sitting low so it feels close to us
        self.Z0 = ow * LID_WIDE / lid_w
        vh0 = oh / self.Z0
        self.C0 = np.float32([cxn, box[3] - 0.93 * vh0 + vh0 / 2])
        # close: lid ~53%, whole laptop still in frame
        self.Z1 = ow * LID_CLOSE / lid_w
        vh1 = oh / self.Z1
        self.C1 = np.float32([cxn, min(scr_cy + 0.07 * vh1, box[3] - 0.955 * vh1 + vh1 / 2 + 0.0)])
        self.C1[1] = max(self.C1[1], box[1] - 0.06 * vh1 + vh1 / 2)   # keep the lid top inside the frame
        self.Pc = np.float32([ow / 2.0, oh / 2.0])
        ys, xs = np.mgrid[0:oh, 0:ow].astype(np.float32)
        self.xs, self.ys = xs, ys
        vn, un = np.mgrid[0:NH, 0:NW].astype(np.float32)

        rng = np.random.default_rng(5)
        ga = self.grass_amp
        self.g0 = int(np.argmax(ga.max(1) > 0.01))
        gs = slice(self.g0, NH)
        self.gA = ga[gs] * 2.3 * (0.75 + 0.6 * (vn[gs] - self.g0) / max(1.0, NH - self.g0))
        self.gP1 = -un[gs] / 85.0 + 1.6 * SR.smooth_noise(rng, NH - self.g0, NW, 45)
        self.gP2 = -un[gs] / 30.0 + 2.5 * SR.smooth_noise(rng, NH - self.g0, NW, 16)
        self.g_un = un[self.g0:self.g0 + 1]
        self.tr1 = int(NH - np.argmax(self.tree_amp.max(1)[::-1] > 0.01))
        ts = slice(0, self.tr1)
        side = np.where(un[ts] > NW / 2, 1.3, 0.0)
        self.tA = self.tree_amp[ts] * 1.25
        self.tP1 = side + 1.3 * SR.smooth_noise(rng, self.tr1, NW, 110)
        self.tP2 = side * 0.6 + 2.0 * SR.smooth_noise(rng, self.tr1, NW, 40)
        self.tP3 = 1.5 * SR.smooth_noise(rng, self.tr1, NW, 90)

        # light shafts at quarter native res
        r = 4
        ul, vl = un[::r, ::r], vn[::r, ::r]
        sx, sy = NW * 1.05, -NH * 0.10
        self.theta = np.arctan2(vl - sy, ul - sx)
        rad = np.hypot(ul - sx, vl - sy)
        lapl = cv2.GaussianBlur(P["lapN"].astype(np.float32), (0, 0), 6)[::r, ::r]
        self.raymask = (np.clip(1 - rad / (NW * 0.95), 0, 1) ** 1.1 * (0.35 + 0.65 * self.far[::r, ::r])
                        * (1 - 0.6 * ss(0.68, 0.8, vl / NH)) * (1 - 0.7 * lapl)).astype(np.float32)

        # mist strips (native res)
        self.m0 = int(np.argmax(self.mist.max(1) > 0.01))
        self.m1 = int(NH - np.argmax(self.mist.max(1)[::-1] > 0.01))
        nrng = np.random.default_rng(11)

        def strip(cellx, celly):
            g = nrng.uniform(0, 1, (int(NH / celly) + 3, int(2 * NW / cellx))).astype(np.float32)
            g = np.concatenate([g, g[:, :3]], 1)
            big = cv2.resize(g, (int(g.shape[1] * cellx), int(g.shape[0] * celly)), interpolation=cv2.INTER_CUBIC)
            return big[self.m0:self.m1, :int((g.shape[1] - 3) * cellx)]
        self.mn1, self.mn2 = strip(170, 26), strip(90, 16)

        # faint sky reflection for the glass: the sky/blossoms behind the camera stand-in, mirrored and defocused
        bgN = cv2.resize(self.bg, (NW, NH), interpolation=cv2.INTER_AREA)
        self.refl = cv2.GaussianBlur(bgN[40:330, 330:1046][:, ::-1], (0, 0), 7).astype(np.float32)

        # petals (native coordinates)
        pr = np.random.default_rng(77)

        def layer(n, size, vy, vx, sway, idle):
            d = dict(n=n)
            d["size"] = pr.uniform(*size, n)
            d["vy"], d["vx"] = pr.uniform(*vy, n), pr.uniform(*vx, n)
            d["x0"] = pr.uniform(-0.45 * NW, NW * 1.02, n)
            d["swA"] = pr.uniform(*sway, n)
            d["swF"] = pr.uniform(0.25, 0.6, n) * 2 * np.pi
            d["swP"], d["rot0"] = pr.uniform(0, 6.28, n), pr.uniform(0, 6.28, n)
            d["rotS"] = pr.uniform(0.5, 2.2, n) * pr.choice([-1, 1], n)
            d["flF"], d["flP"] = pr.uniform(1.2, 3.2, n), pr.uniform(0, 6.28, n)
            d["col"] = SR.PETAL_COLORS[pr.integers(0, len(SR.PETAL_COLORS), n)] * pr.uniform(0.92, 1.0, (n, 1)).astype(np.float32)
            d["alpha"] = pr.uniform(0.75, 0.95, n)
            d["m"] = d["size"] * 2 + 6
            d["tfall"] = (NH + 2 * d["m"]) / d["vy"]
            d["land"], d["rest"] = np.zeros(n, bool), np.zeros(n)
            d["P"] = d["tfall"] + pr.uniform(*idle, n)
            d["ph"] = pr.uniform(0, 1, n) * d["P"]
            d["dep"] = np.zeros(n)
            return d
        self.pbg = layer(110, (1.5, 3.0), (26, 48), (16, 36), (4, 10), (0, 2))
        self.pmid = layer(80, (3.6, 6.8), (62, 108), (40, 85), (8, 20), (0, 3))
        self.pfg = layer(7, (13, 24), (150, 250), (110, 210), (15, 35), (4, 10))
        self.pbg["dep"][:] = 0.12
        self.pmid["dep"][:] = self.lap_dep - 0.12
        self.pfg["dep"][:] = self.lap_dep + 0.9
        L = self.pmid
        lapn = cv2.dilate(P["lapN"].astype(np.uint8), np.ones((25, 25), np.uint8))
        for i in np.where(pr.uniform(0, 1, L["n"]) < 0.34)[0]:
            for _ in range(30):
                ly = pr.uniform(0.735, 0.97) * NH
                tf = (ly + L["m"][i]) / L["vy"][i]
                lx = L["x0"][i] + L["vx"][i] * tf + L["swA"][i] * np.sin(L["swF"][i] * tf + L["swP"][i])
                if 5 < lx < NW - 5 and not lapn[int(ly), int(lx)]:
                    break
                L["x0"][i] = pr.uniform(-0.45 * NW, NW * 1.02)
            else:
                continue
            L["land"][i], L["tfall"][i], L["rest"][i] = True, tf, pr.uniform(3.0, 5.5)
            L["P"][i] = tf + L["rest"][i] + 0.9 + pr.uniform(0, 2)
            L["dep"][i] = self.depth[int(ly), int(lx)]
            L["size"][i] *= 0.65 + 0.9 * (ly / NH - 0.735) / 0.235
        L["ph"] = pr.uniform(0, 1, L["n"]) * L["P"]

    # ------------------------------------------------------------------ camera
    def cam(self, t):
        x = (t - T_WHIP) / (T_CLOSE - T_WHIP)
        e = ease(x)
        dl = np.log(self.Z1 / self.Z0) * e + CREEP * (t - T_WHIP) / (self.a.total - T_WHIP)   # log-zoom gained so far
        Z = self.Z0 * np.exp(dl)
        C = self.C0 + (self.C1 - self.C0) * e
        fl = 1.3 * self.Z0 / Z                                    # handheld float, constant on screen
        C = C + fl * np.float32([np.sin(2 * np.pi * 0.09 * t) + 0.5 * np.sin(2 * np.pi * 0.21 * t + 1.3),
                                 0.8 * np.sin(2 * np.pi * 0.075 * t + 2.1) + 0.4 * np.sin(2 * np.pi * 0.17 * t + 0.4)])
        return Z, C, dl

    def fwd(self, u, v, dep, t, shx=0.0):
        Z, C, dl = self.cam(t)
        Zd = Z * np.exp(PARALLAX * (dep - self.lap_dep) * dl)
        return self.Pc[0] + shx + (u - C[0]) * Zd, self.Pc[1] + (v - C[1]) * Zd, Zd

    def quad_out(self, t, shx=0.0):
        x, y, _ = self.fwd(self.quad[:, 0], self.quad[:, 1], self.lap_dep, t, shx)
        return np.stack([x, y], 1).astype(np.float32)

    def layer_affine(self, org, Zl, C, shx):
        K = self.K
        s = Zl / K
        return np.float32([[s, 0, self.Pc[0] + shx + ((org[0] - (K - 1) / 2) / K - C[0]) * Zl],
                           [0, s, self.Pc[1] + ((org[1] - (K - 1) / 2) / K - C[1]) * Zl]])

    def petals(self, L, t, shx, res=1.0):
        h, w = int(self.oh * res), int(self.ow * res)
        col = np.zeros((h, w, 3), np.uint8)
        alp = np.zeros((h, w), np.uint8)
        x, y, vx, vy, rot, fl, a, landed = SR.Shot.petal_state(None, L, t)
        X, Y, sc = self.fwd(x, y, L["dep"], t, shx)
        size = L["size"] * sc
        for i in range(L["n"]):
            r = size[i]
            if a[i] <= 0.01 or X[i] < -3 * r or X[i] > self.ow + 3 * r or Y[i] < -3 * r or Y[i] > self.oh + 3 * r:
                continue
            p = SR.PETAL * (r * (0.28 + 0.72 * abs(fl[i])), r)
            c, s_ = np.cos(rot[i]), np.sin(rot[i])
            p = p @ np.float32([[c, s_], [-s_, c]])
            if landed[i]:
                p[:, 1] *= 0.5
            v = np.float32([vx[i], vy[i]]) * sc[i]
            blur = np.linalg.norm(v) / FPS * 0.5
            aa = a[i]
            if blur > 0.3:
                d = v / np.linalg.norm(v)
                st = 1 + blur / (2 * r)
                p = p + np.outer(p @ d, d) * (st - 1)
                aa /= st ** 0.8
            pts = np.round(((p + (X[i], Y[i])) * res) * 16).astype(np.int32)[None]
            cv2.fillPoly(col, pts, tuple(float(cc) for cc in L["col"][i] * (0.86 + 0.14 * fl[i]) * aa), cv2.LINE_AA, 4)
            cv2.fillPoly(alp, pts, float(255 * aa), cv2.LINE_AA, 4)
        return col, alp

    # ------------------------------------------------------------------ screen
    def screen(self, frame, quad, t, fi, e, vid):
        ow, oh = self.ow, self.oh
        qw = float(np.linalg.norm(quad[2] - quad[3]))
        pad = int(qw * 0.25)
        bx0, by0 = int(max(0, np.floor(quad[:, 0].min()) - pad)), int(max(0, np.floor(quad[:, 1].min()) - pad))
        bx1, by1 = int(min(ow, np.ceil(quad[:, 0].max()) + pad)), int(min(oh, np.ceil(quad[:, 1].max()) + pad))
        if bx1 - bx0 < 8 or by1 - by0 < 8:
            return frame
        bw, bh = bx1 - bx0, by1 - by0
        cw = int(np.clip(qw * 1.1, 64, SR.VID_W)) // 2 * 2
        ch = int(cw / 1.6) // 2 * 2                    # 16:10 panel
        vh = int(cw * 9 / 16) // 2 * 2                 # 16:9 video, letterboxed, never stretched
        vi = int(np.clip(round((t - T_VID) * FPS), 0, len(vid) - 1))
        fr = cv2.resize(vid[vi], (cw, vh), interpolation=cv2.INTER_AREA).astype(np.float32)
        content = np.zeros((ch, cw, 3), np.float32)
        o = (ch - vh) // 2
        content[o:o + vh] = fr * SCREEN_GAIN * SCREEN_TINT           # white lands at ~83%, slightly warm
        content = (content + np.float32([8, 8, 9])) * e
        refl = cv2.resize(self.refl, (cw, ch), interpolation=cv2.INTER_AREA)
        content = content * 0.95 + refl * 0.05                       # faint sky reflection in the glass
        content += np.random.default_rng(1000 + fi).normal(0, 1.6, (ch, cw)).astype(np.float32)[..., None]
        q = (quad - (bx0, by0)).astype(np.float32)
        Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]]), q)
        scr = cv2.warpPerspective(content, Hm, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        scr = cv2.GaussianBlur(scr, (0, 0), 0.7)                     # photo softness
        am = np.zeros((bh, bw), np.uint8)
        cv2.fillPoly(am, np.round(q * 16).astype(np.int32)[None], 255, cv2.LINE_AA, 4)
        al = (cv2.GaussianBlur(am, (0, 0), 0.7).astype(np.float32) / 255)[..., None]
        roi = frame[by0:by1, bx0:bx1]
        roi[:] = roi * (1 - al) + scr * al
        bump = np.exp(-((t - (T_ON + 0.3)) / 0.22) ** 2)
        ds = max(1, int(round(qw / 120)))
        sm = cv2.resize(scr * al, (max(2, bw // ds), max(2, bh // ds)), interpolation=cv2.INTER_AREA)
        bloom = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 0.05 * qw / ds), (bw, bh), interpolation=cv2.INTER_LINEAR)
        roi += bloom * (0.13 + 0.10 * bump) * e
        return frame

    # ------------------------------------------------------------------ frame
    def render(self, fi, vid, shx=0.0):
        t = fi / FPS
        ow, oh, K = self.ow, self.oh, self.K
        Z, C, dl = self.cam(t)
        e = float(ss(T_ON, T_VID, t))
        vi = int(np.clip(round((t - T_VID) * FPS), 0, len(vid) - 1))
        small = vid[vi][::8, ::8].astype(np.float32) * SCREEN_GAIN * SCREEN_TINT
        c_all = small.mean((0, 1)) / 255 * e
        c_low = small[small.shape[0] // 2:].mean((0, 1)) / 255 * e
        bump = float(np.exp(-((t - (T_ON + 0.3)) / 0.22) ** 2))

        # ---- background layer: depth parallax + wind, one resample from the 3x master
        px, py = self.xs - (self.Pc[0] + shx), self.ys - self.Pc[1]
        qx, qy = C[0] + px / Z, C[1] + py / Z
        for _ in range(2):
            d = cv2.remap(self.depth, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            inv = np.exp(-PARALLAX * (d - self.lap_dep) * dl) / Z
            qx, qy = (C[0] + px * inv).astype(np.float32), (C[1] + py * inv).astype(np.float32)
        dx = np.zeros((NH, NW), np.float32)
        dy = np.zeros((NH, NW), np.float32)
        gust = 0.62 + 0.38 * np.sin(2 * np.pi * 0.11 * t - self.g_un / 520.0)
        dx[self.g0:] = self.gA * (gust * np.sin(self.gP1 + 2 * np.pi * 0.42 * t) + 0.3 * np.sin(self.gP2 + 2 * np.pi * 1.05 * t) + 0.35 * gust)
        tsl = slice(0, self.tr1)
        dx[tsl] += self.tA * (np.sin(self.tP1 + 2 * np.pi * 0.15 * t) + 0.35 * np.sin(self.tP2 + 2 * np.pi * 0.37 * t))
        dy[tsl] += self.tA * 0.55 * np.sin(self.tP3 + 2 * np.pi * 0.12 * t + 1.0)
        sx_ = qx - cv2.remap(dx, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        sy_ = qy - cv2.remap(dy, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        off = (K - 1) / 2.0
        f = cv2.remap(self.bg, sx_ * K + off, sy_ * K + off, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)

        # ---- light shafts, flicker, mist (evaluated in plate space, sampled through the same camera)
        th = self.theta
        p = (np.sin(th * 41 + 0.11 * t + 0.3) + 0.8 * np.sin(th * 73 - 0.17 * t + 1.9) + 0.6 * np.sin(th * 127 + 0.26 * t + 4.1)) / 2.4
        p = np.clip(0.5 + 0.5 * p, 0, 1) ** 2
        flick = 0.035 * np.sin(2 * np.pi * 0.31 * t) + 0.025 * np.sin(2 * np.pi * 0.83 * t + 1.1)
        m = cv2.remap((((p - 0.30) * (1 + flick) + flick * 0.5) * self.raymask).astype(np.float32), qx / 4, qy / 4,
                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        f *= (1 + 0.11 * m)[..., None]
        f += m[..., None] * (5.0 * np.float32([0.72, 0.9, 1.0]))
        ma = np.zeros((NH, NW), np.float32)
        idx = np.arange(NW)
        mn = (self.mn1[:, (idx + int(-9 * t) % self.mn1.shape[1]) % self.mn1.shape[1]] * 0.6
              + self.mn2[:, (idx + int(-17 * t) % self.mn2.shape[1]) % self.mn2.shape[1]] * 0.4)
        ma[self.m0:self.m1] = self.mist[self.m0:self.m1] * ss(0.42, 0.75, mn) * 0.13
        mo = cv2.remap(ma, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[..., None]
        f += (np.float32([222, 228, 236]) - f) * mo
        # screen light on the lawn next to the laptop
        if e > 0:
            f += cv2.remap(self.halo, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)[..., None] * (c_all * (1 + 0.5 * bump))

        # ---- far petals, hidden behind near things
        col, alp = self.petals(self.pbg, t, shx)
        if alp.any():
            farm = cv2.remap(self.far, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            lapm = cv2.warpAffine(self.lap_a, self.layer_affine(self.lap_org, Z, C, shx), (ow, oh), flags=cv2.INTER_LINEAR)
            farm = farm * (1 - lapm.astype(np.float32) / 255)
            sg = 0.45 * Z / 1.4
            a_ = cv2.GaussianBlur(alp, (0, 0), sg).astype(np.float32) / 255 * farm
            f = f * (1 - a_[..., None]) + cv2.GaussianBlur(col, (0, 0), sg).astype(np.float32) * farm[..., None]

        # ---- laptop layer: rigid, so its screen corners are tracked exactly
        M = self.layer_affine(self.lap_org, Z, C, shx)
        lb = cv2.warpAffine(self.lap_bgr, M, (ow, oh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        la = cv2.warpAffine(self.lap_a, M, (ow, oh), flags=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255
        if e > 0:
            lb += cv2.warpAffine(self.lap_spill, M, (ow, oh), flags=cv2.INTER_LINEAR)[..., None] * (c_low * 1.1)
        f = f * (1 - la) + lb * la
        f = self.screen(f, self.quad_out(t, shx), t, fi, e, vid)

        # ---- foreground grass crossing the front edge of the base (slightly nearer, own gentle sway)
        Zf = Z * np.exp(PARALLAX * 0.12 * dl)
        Mf = self.layer_affine(self.fg_org, Zf, C, shx)
        swx = 1.6 * Zf * (0.6 * np.sin(2 * np.pi * 0.42 * t + 0.7) + 0.4 * np.sin(2 * np.pi * 1.05 * t))
        rows = np.where(cv2.warpAffine(self.fg_a, Mf, (ow, oh), flags=cv2.INTER_LINEAR).any(1))[0]
        if len(rows):
            r0, r1 = rows[0], rows[-1] + 1
            Mf2 = Mf.copy()
            Mf2[1, 2] -= r0
            hgt = r1 - r0
            # shear: tips (top of the layer) move, roots (bottom) stay
            src_h = self.fg_a.shape[0]
            Mf2[0, 1] = -swx / (src_h * Mf[0, 0]) * Mf[0, 0]
            Mf2[0, 2] += swx
            fb = cv2.warpAffine(self.fg_bgr, Mf2, (ow, hgt), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            fa = cv2.warpAffine(self.fg_a, Mf2, (ow, hgt), flags=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255
            f[r0:r1] = f[r0:r1] * (1 - fa) + fb * fa

        # ---- mid + foreground petals
        col, alp = self.petals(self.pmid, t, shx)
        if alp.any():
            sg = 0.75 * Z / 1.4
            a_ = cv2.GaussianBlur(alp, (0, 0), sg).astype(np.float32)[..., None] / 255
            f = f * (1 - a_) + cv2.GaussianBlur(col, (0, 0), sg).astype(np.float32)
        col, alp = self.petals(self.pfg, t, shx, res=0.25)
        if alp.any():
            sg = 0.9 * Z / 1.4
            a_ = cv2.resize(cv2.GaussianBlur(alp, (0, 0), sg), (ow, oh), interpolation=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255 * 0.8
            f = f * (1 - a_) + cv2.resize(cv2.GaussianBlur(col, (0, 0), sg), (ow, oh), interpolation=cv2.INTER_LINEAR).astype(np.float32) * 0.8
        # ---- one layer of fine grain over everything so laptop, screen and plate sit in the same image
        f += np.random.default_rng(50000 + fi).normal(0, 1.2, (oh, ow)).astype(np.float32)[..., None]
        return np.clip(f, 0, 255).astype(np.uint8)


class Film:
    def __init__(self, a):
        self.a = a
        self.old = SR.Sequence(a.seq_args)
        self.vid = self.old.vid
        self.lap = None
        self.means = None

    def laptop(self):
        if self.lap is None:
            self.lap = LaptopShot(self.a)
        return self.lap

    def canopy(self, t, T=(0.0, 0.0)):
        img, pc, pa = self.old.shot("canopy").render(t, 1.0, T, None)
        if pc is not None:
            img = np.clip(img * (1 - pa[..., None]) + pc, 0, 255).astype(np.uint8)
        return img

    def render(self, fi):
        t = fi / FPS
        f_w0 = int(round(T_WHIP * FPS))
        if t < SR.T_BC[0]:
            return self.old.render(fi)                      # 0-6 s: exactly the earlier film
        if fi < f_w0:
            return self.canopy(t)
        if fi >= f_w0 + WHIP_FRAMES:
            return self.laptop().render(fi, self.vid)
        # ---- whip-pan: 7 frames of fast horizontal travel, cut hidden in the blur, colours eased across
        ow = self.a.ow
        if self.means is None:
            a_ = self.canopy(T_WHIP).reshape(-1, 3).mean(0)
            b_ = self.laptop().render(f_w0 + WHIP_FRAMES, self.vid).reshape(-1, 3).mean(0)
            self.means = (a_, b_)
        tau = (fi - f_w0 + 0.5) / WHIP_FRAMES
        if tau < 0.5:
            img = self.canopy(t, T=(-1.1 * ow * (2 * tau) ** 2, 0.0))
        else:
            img = self.laptop().render(fi, self.vid, shx=1.1 * ow * (2 * (1 - tau)) ** 2)
        target = self.means[0] + (self.means[1] - self.means[0]) * tau
        gain = np.clip(target / np.maximum(img.reshape(-1, 3).mean(0), 1), 0.8, 1.25)
        w = 1 - abs(2 * tau - 1)                             # strongest at the cut
        img = np.clip(img * (1 + (gain - 1) * (0.5 + 0.5 * w)), 0, 255).astype(np.uint8)
        L = int(ow * (0.05 + 0.20 * w)) | 1
        return cv2.blur(img, (L, 1), borderType=cv2.BORDER_REFLECT_101)


def work(job):
    a, k, f0, f1 = job
    cv2.setNumThreads(1)
    film = Film(a)
    seg = os.path.join(a.work, f"seg_{a.tag}_{k:02d}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{a.ow}x{a.oh}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-g", str(FPS), "-threads", "2", seg], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        img = film.render(fi)
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
    ap.add_argument("--work", default="output/fix/work")
    ap.add_argument("--seq-work", default="output/seq/work")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--dump", default="")
    a = ap.parse_args()
    a.ow, a.oh = map(int, a.size.split("x"))
    a.tag = os.path.splitext(os.path.basename(a.out))[0]
    a.frames_dir = os.path.join(os.path.dirname(a.out) or ".", "frames")
    os.makedirs(a.frames_dir, exist_ok=True)
    cache = os.path.join(a.seq_work, "screen_video.bgr")
    if not os.path.exists(cache):
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-vf",
                               f"fps={FPS},scale={SR.VID_W}:{SR.VID_H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "bgr24", cache])
    nvid = os.path.getsize(cache) // (SR.VID_W * SR.VID_H * 3)
    a.total = T_VID + nvid / FPS
    a.seq_args = argparse.Namespace(work=a.seq_work, ow=a.ow, oh=a.oh, total=a.total)
    f0 = int(round(a.t0 * FPS))
    f1 = int(round((a.t1 if a.t1 is not None else a.total) * FPS))
    a.dump = {int(round(float(x) * FPS)) for x in a.dump.split(",") if x}
    print(f"total={a.total:.2f}s rendering frames {f0}..{f1} at {a.ow}x{a.oh}", flush=True)
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
