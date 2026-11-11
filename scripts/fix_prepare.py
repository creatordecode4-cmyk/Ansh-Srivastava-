#!/usr/bin/env python3
"""Realism fix, step 1: build ONE layered master plate from the wide green-screen still.

  python3 scripts/upscale_esrgan.py output/work/plate_no_petals.png output/fix/work/master_x4.png
  python3 scripts/fix_prepare.py output/work/plate_no_petals.png output/fix/work/master_x4.png output/fix/work

Layers (all from the same image, at 3x the still's resolution):
  bg      everything except the laptop (laptop painted out, contact shadow added)
  laptop  rigid cut-out: despilled, aluminium warmed, golden rim light on the lid edges
  fg      grass blades that overlap the front edge of the base
plus native-resolution depth and motion masks.
"""
import os
import sys

import cv2
import numpy as np

native_path, x4_path, work = sys.argv[1], sys.argv[2], sys.argv[3]
midas = sys.argv[4] if len(sys.argv) > 4 else "output/work/midas_small.onnx"
K = 3
nat = cv2.imread(native_path)
H, W = nat.shape[:2]
big = cv2.resize(cv2.imread(x4_path), (W * K, H * K), interpolation=cv2.INTER_AREA)
BH, BW = big.shape[:2]


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def cross2(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def green_quad(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (45, 150, 150), (75, 255, 255))
    n, lab, st, _ = cv2.connectedComponentsWithStats(green)
    gm = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8) * 255
    cnt = max(cv2.findContours(gm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
    ap = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True).reshape(-1, 2).astype(np.float32)
    assert len(ap) == 4, ap
    s, d = ap.sum(1), ap[:, 0] - ap[:, 1]
    quad = np.float32([ap[s.argmin()], ap[d.argmax()], ap[s.argmax()], ap[d.argmin()]])
    cpts = cnt.reshape(-1, 2).astype(np.float32)
    lines = []
    for a, b in zip(quad, np.roll(quad, -1, 0)):
        ab = b - a
        L = np.linalg.norm(ab)
        t = ((cpts - a) @ ab) / L ** 2
        sel = cpts[(t > 0.12) & (t < 0.88) & (np.abs(cross2(ab, cpts - a)) / L < 3 * K)]
        vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))

    def isect(l1, l2):
        (p, r), (q, s_) = l1, l2
        return p + cross2(q - p, s_) / cross2(r, s_) * r
    quad = np.float32([isect(lines[3], lines[0]), isect(lines[0], lines[1]), isect(lines[1], lines[2]), isect(lines[2], lines[3])])
    c = quad.mean(0)
    return quad + (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True) * 0.6, gm


quad, gm = green_quad(big)                      # 3x coordinates, TL,TR,BR,BL
tl, tr, br, bl = quad
sw, sh = np.linalg.norm(tr - tl), np.linalg.norm(bl - tl)
c = quad.mean(0)
grow = (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True)
yy, xx = np.mgrid[0:BH, 0:BW].astype(np.float32)

# ---------------------------------------------------------------- despill + blank screen
lid_poly = np.float32([tl + (-0.045 * sw, -0.09 * sh), tr + (0.045 * sw, -0.09 * sh), br + (0.045 * sw, 0.10 * sh), bl + (-0.045 * sw, 0.10 * sh)])
base_poly = np.float32([bl + (-0.05 * sw, 0.06 * sh), br + (0.05 * sw, 0.06 * sh), br + (0.20 * sw, 0.47 * sh), bl + (-0.20 * sw, 0.47 * sh)])
lidm = np.zeros((BH, BW), np.uint8)
basem = np.zeros((BH, BW), np.uint8)
cv2.fillConvexPoly(lidm, lid_poly.astype(np.int32), 255)
cv2.fillConvexPoly(basem, base_poly.astype(np.int32), 255)
qmask = np.zeros((BH, BW), np.uint8)
cv2.fillConvexPoly(qmask, np.round(quad + grow * 3 * K).astype(np.int32), 255)
qf = cv2.GaussianBlur(qmask, (0, 0), 0.7 * K).astype(np.float32)[..., None] / 255
blank = big.astype(np.float32) * (1 - qf) + np.float32([14, 12, 11]) * qf
bh_ = cv2.cvtColor(blank.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
b, g, r = [blank[..., k] for k in range(3)]
hue, sat = bh_[..., 0], bh_[..., 1]
neutral = 0.6 * np.maximum(r, b) + 0.4 * np.minimum(r, b)
excess = np.clip(g - neutral, 0, None)
pure = ss(47, 55, hue) * (1 - ss(80, 90, hue)) * ss(15, 40, sat)
pale = ss(34, 40, hue) * (1 - ss(80, 90, hue)) * (1 - ss(105, 128, sat))
region = cv2.GaussianBlur(cv2.dilate(lidm | basem, np.ones((3 * K, 3 * K), np.uint8)), (0, 0), 1.5 * K).astype(np.float32) / 255
spill = cv2.GaussianBlur(excess * np.maximum(pure, pale) * region, (0, 0), 0.8 * K)
plate = np.clip(np.dstack([b, g - spill, r]), 0, 255).astype(np.uint8)
spill = np.clip(spill, 0, 80)

# ---------------------------------------------------------------- laptop matte
ph = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
# lid: the dark bezel/glass blob around the screen, plus its thin aluminium rim
dark = ((ph[..., 2] < 70) & (lidm > 0)).astype(np.uint8)
dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((2 * K + 1, 2 * K + 1), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(dark)
lid = (lab == lab[int(c[1]), int(c[0])]).astype(np.uint8)
lid = cv2.morphologyEx(lid, cv2.MORPH_OPEN, np.ones((3 * K, 3 * K), np.uint8))
lid = cv2.dilate(lid, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(1.6 * K) + 1,) * 2))
# base: grey metal and dark keys inside the base trapezoid; saturated green = grass in front, not laptop
metal = (ph[..., 1] < 78) | (ph[..., 2] < 60)
base = (metal & (basem > 0)).astype(np.uint8)
base = cv2.morphologyEx(base, cv2.MORPH_OPEN, np.ones((K + 1, K + 1), np.uint8))
base = cv2.morphologyEx(base, cv2.MORPH_CLOSE, np.ones((2 * K + 1, 2 * K + 1), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(base)
base = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.uint8)
hard = ((lid | base) > 0).astype(np.uint8)
matte = cv2.GaussianBlur(hard.astype(np.float32), (0, 0), 0.35 * K)
lidf = cv2.GaussianBlur(lid.astype(np.float32), (0, 0), 0.35 * K)

# ---------------------------------------------------------------- background layer (laptop painted out)
holeN = cv2.resize(cv2.dilate(hard, np.ones((3 * K, 3 * K), np.uint8)), (W, H), interpolation=cv2.INTER_AREA)
holeN = cv2.dilate((holeN > 0).astype(np.uint8) * 255, np.ones((5, 5), np.uint8))
fillN = cv2.inpaint(cv2.resize(plate, (W, H), interpolation=cv2.INTER_AREA), holeN, 6, cv2.INPAINT_TELEA)
fill = cv2.resize(fillN, (BW, BH), interpolation=cv2.INTER_CUBIC)
hole = cv2.GaussianBlur(cv2.dilate(hard, np.ones((2 * int(2.5 * K) + 1,) * 2, np.uint8)).astype(np.float32), (0, 0), 0.8 * K)[..., None]
bg = plate.astype(np.float32) * (1 - hole) + fill.astype(np.float32) * hole
# contact shadow: tight occlusion right under the base + a softer one falling toward the camera (sun is behind)
bf = base.astype(np.float32)


def shifted(m, dx, dy, sig):
    M = np.float32([[1, 0, dx * K], [0, 1, dy * K]])
    return cv2.GaussianBlur(cv2.warpAffine(m, M, (BW, BH)), (0, 0), sig * K)


ground = ss(bl[1] + 0.02 * sh, bl[1] + 0.10 * sh, yy)
shadow = np.clip(0.55 * shifted(bf, -1.5, 3.0, 2.2) + 0.45 * shifted(bf, -6, 9, 9), 0, 1) * ground
bg *= (1 - 0.62 * shadow)[..., None]
bg = np.clip(bg, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- laptop layer: warm metal + golden rim
lap = plate.astype(np.float32)
alum = (ss(60, 110, ph[..., 2].astype(np.float32)) * (1 - ss(70, 110, ph[..., 1].astype(np.float32))))[..., None]
lap = lap * (1 - alum * 0.85) + lap * np.float32([0.90, 0.985, 1.06]) * (alum * 0.85)
# rim: thin band just inside the silhouette, lit from the back-right like the trees
soft = cv2.GaussianBlur(hard.astype(np.float32), (0, 0), 2.0 * K)
gx = cv2.Sobel(soft, cv2.CV_32F, 1, 0, ksize=5)
gy = cv2.Sobel(soft, cv2.CV_32F, 0, 1, ksize=5)
nrm = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
nx, ny = -gx / nrm, -gy / nrm                                   # outward normal
facing = np.clip(0.30 + 0.75 * (0.75 * nx - 0.66 * ny), 0, 1)   # light from upper right
inner = cv2.erode(hard, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(1.3 * K) + 1,) * 2))
band = cv2.GaussianBlur((hard - inner).astype(np.float32), (0, 0), 0.5 * K)
rim = band * facing * (0.35 + 0.65 * ss(bl[1] + 0.2 * sh, bl[1] - 0.1 * sh, yy))   # mostly the lid
wide_glow = cv2.GaussianBlur(rim, (0, 0), 2.5 * K) * 0.5
lap += (rim * 0.9 + wide_glow)[..., None] * np.float32([95, 170, 240])
lap = np.clip(lap, 0, 255).astype(np.uint8)

ys_, xs_ = np.where(matte > 0.004)
pad = 4 * K
y0, y1, x0, x1 = max(0, ys_.min() - pad), min(BH, ys_.max() + pad), max(0, xs_.min() - pad), min(BW, xs_.max() + pad)
cv2.imwrite(os.path.join(work, "layer_laptop.png"), np.dstack([lap[y0:y1, x0:x1], (matte[y0:y1, x0:x1] * 255).astype(np.uint8)]))
np.save(os.path.join(work, "layer_laptop_spill.npy"), (spill * matte)[y0:y1, x0:x1].astype(np.float16))
lap_org = (x0, y0)

# ---------------------------------------------------------------- foreground grass over the base's front edge
# blades are taken from the strip of lawn right in front of the laptop, mirrored so the copy never
# sits directly above its source, and lifted until their tips cross the front edge of the base
front = float(np.percentile(np.where(base.any(1))[0], 100))      # bottom row of the base (3x)
cxL = float(c[0])
sx0, sx1 = int(cxL - 0.80 * sw), int(cxL + 0.80 * sw)
strip_h = int(BH - front - 2 * K)
lift = int(front + 6 * K - (BH - strip_h))                       # how far the strip is moved up (negative = up)
src = bg[BH - strip_h:BH, sx0:sx1][:, ::-1].astype(np.float32)
sh_ = cv2.cvtColor(src.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
blade = ss(95, 150, sh_[..., 2]) * ss(22, 30, sh_[..., 0]) * (1 - ss(60, 75, sh_[..., 0])) * ss(60, 110, sh_[..., 1])
blade = cv2.GaussianBlur(blade, (0, 0), 0.4 * K)
rows = np.arange(strip_h, dtype=np.float32)[:, None]
blade *= ss(0, 0.25 * strip_h, rows) ** 0 * (1 - ss(0.70 * strip_h, 0.98 * strip_h, rows))   # roots fade into the lawn
edge = np.arange(sx1 - sx0, dtype=np.float32)[None]
blade *= ss(0, 0.12 * (sx1 - sx0), edge) * (1 - ss(0.88 * (sx1 - sx0), sx1 - sx0, edge))
# decontaminate: where the matte is soft, use the neighbouring blade colour, not the dark gap behind it
solid = (blade > 0.55)[..., None]
spread = cv2.dilate((src * solid).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * K + 1, 2 * K + 1))).astype(np.float32)
src = np.where(solid, src, np.where(spread.sum(2, keepdims=True) > 0, spread, src))
fg = np.dstack([np.clip(src * 1.04, 0, 255).astype(np.uint8), (blade * 255).astype(np.uint8)])
fg_org = (sx0, int(BH - strip_h + lift - 22 * K))
cv2.imwrite(os.path.join(work, "layer_fg.png"), fg)
cv2.imwrite(os.path.join(work, "layer_bg.png"), bg)

# ---------------------------------------------------------------- native-res depth + motion masks
bgN = cv2.resize(bg, (W, H), interpolation=cv2.INTER_AREA)
net = cv2.dnn.readNet(midas)
rgb = cv2.cvtColor(bgN, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
rgb = (rgb - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
net.setInput(cv2.dnn.blobFromImage(cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32)))
dm = cv2.resize(net.forward().squeeze(), (W, H), interpolation=cv2.INTER_CUBIC)
dm = (dm - dm.min()) / (dm.max() - dm.min())
depth_raw = dm
depth = cv2.GaussianBlur(dm, (0, 0), 9)
matteN = cv2.resize(matte, (W, H), interpolation=cv2.INTER_AREA)
baseN = cv2.resize(base.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
ringN = (cv2.dilate((baseN > 0.5).astype(np.uint8), np.ones((21, 21), np.uint8)) > 0) & (matteN < 0.05)
ynN, xnN = np.mgrid[0:H, 0:W].astype(np.float32)
ringN &= ynN > (front / K - 25)
lap_dep = float(np.median(depth[ringN]))                         # the ground the laptop stands on

lap_soft = cv2.GaussianBlur(cv2.dilate((matteN > 0.05).astype(np.uint8) * 255, np.ones((9, 9), np.uint8)), (0, 0), 4).astype(np.float32) / 255
lum = cv2.cvtColor(bgN, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
pN = cv2.cvtColor(bgN, cv2.COLOR_BGR2HSV).astype(np.float32)
is_green = ss(22, 30, pN[..., 0]) * (1 - ss(70, 85, pN[..., 0])) * ss(40, 90, pN[..., 1])
grass = ss(0.45, 0.62, depth_raw) * ss(0.66, 0.76, ynN / H) * np.maximum(is_green, ss(0.80, 0.9, ynN / H))
grass = cv2.GaussianBlur(grass, (0, 0), 3) * (1 - 0.85 * lap_soft)   # blades right at the laptop barely move
grass_amp = grass * (0.25 + 0.75 * ss(0.10, 0.55, cv2.GaussianBlur(lum, (0, 0), 1.2)))
pink = np.clip((ss(140, 150, pN[..., 0]) + (1 - ss(4, 10, pN[..., 0]))) * ss(25, 60, pN[..., 1]) * ss(90, 140, pN[..., 2]), 0, 1)
canopy = cv2.GaussianBlur(cv2.dilate(pink, np.ones((15, 15), np.uint8)), (0, 0), 8)
tree = np.clip(canopy * 1.4, 0, 1) * (1 - ss(0.42, 0.56, ynN / H))
tree_amp = cv2.GaussianBlur(tree * (0.25 + 0.75 * cv2.GaussianBlur(pink, (0, 0), 4)), (0, 0), 5)
far = (1 - ss(0.22, 0.40, cv2.GaussianBlur(depth_raw, (0, 0), 2))) * (1 - cv2.GaussianBlur(tree, (0, 0), 2) * 0.9)
mist = ss(0.50, 0.58, ynN / H) * (1 - ss(0.65, 0.72, ynN / H)) * (1 - ss(0.45, 0.62, depth_raw))
# screen light on the lawn around the laptop
near = ss(0.5, 0.7, depth)
halo = cv2.GaussianBlur((matteN > 0.5).astype(np.float32), (0, 0), 30) * near * (1 - matteN) * (ynN > quad[:, 1].max() / K - 40) * 30

np.savez_compressed(os.path.join(work, "fix_prep.npz"), quad=quad, lap_org=lap_org, fg_org=fg_org, K=K, lap_dep=lap_dep,
                    depth=depth.astype(np.float32), grass_amp=grass_amp.astype(np.float32), tree_amp=tree_amp.astype(np.float32),
                    far=far.astype(np.float32), mist=mist.astype(np.float32), halo=halo.astype(np.float32),
                    lapN=(matteN > 0.3), lid_w=float(np.ptp(np.where(lid.any(0))[0])) / K,
                    lap_box=np.float32([xs_.min(), ys_.min(), xs_.max(), ys_.max()]) / K)

# debug: flat composite of the layers
comp = bg.astype(np.float32)
a = matte[..., None]
comp = comp * (1 - a) + lap * a
fy, fx = fg_org[1], fg_org[0]
fa = fg[..., 3:].astype(np.float32) / 255
comp[fy:fy + fg.shape[0], fx:fx + fg.shape[1]] = comp[fy:fy + fg.shape[0], fx:fx + fg.shape[1]] * (1 - fa) + fg[..., :3] * fa
X0, Y0 = int(c[0] - 1.0 * sw), int(tl[1] - 0.25 * sh)
crop = lambda im: im[Y0:Y0 + int(1.95 * sh), X0:X0 + int(2.0 * sw)]
cv2.imwrite(os.path.join(work, "debug_layers.jpg"), np.hstack([crop(big), crop(bg), crop(np.clip(comp, 0, 255).astype(np.uint8))]))
cv2.imwrite(os.path.join(work, "debug_comp.jpg"), crop(np.clip(comp, 0, 255).astype(np.uint8)))
print(f"quad(native)={np.round(quad / K, 1).tolist()} lap_dep={lap_dep:.2f} lid_w={np.ptp(np.where(lid.any(0))[0]) / K:.0f}px box={(np.float32([xs_.min(), ys_.min(), xs_.max(), ys_.max()]) / K).round(0).tolist()}")
