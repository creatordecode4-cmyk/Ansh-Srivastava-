#!/usr/bin/env python3
"""Step 1+2a: clean the still, find the laptop screen quad, build masks + depth.

Everything is produced at the native resolution of the still; the renderer
upscales to the requested output size.

Usage: python3 scripts/01_prepare.py output/input/scene.png output/work
"""
import sys
import os
import cv2
import numpy as np

src, work = sys.argv[1], sys.argv[2]


def cross2(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]

os.makedirs(work, exist_ok=True)
im = cv2.imread(src)
H, W = im.shape[:2]
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- watermark
# Small 4-point sparkle bottom-right. Found automatically: a low-saturation,
# brighter-than-surroundings blob inside the bottom-right corner.
cx0, cy0 = int(W * 0.82), int(H * 0.73)
corner = im[cy0:, cx0:]
chsv = cv2.cvtColor(corner, cv2.COLOR_BGR2HSV)
cand = ((chsv[..., 1] < 95) & (chsv[..., 2] > 70) & (chsv[..., 2] < 200)).astype(np.uint8)
cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
n, lab, st, cen = cv2.connectedComponentsWithStats(cand)
best = None
for i in range(1, n):
    x, y, w, h, a = st[i]
    if 500 < a < 4000 and 0.6 < w / h < 1.6:
        if best is None or a > st[best][4]:
            best = i
assert best is not None, "watermark not found"
wx, wy = cen[best] + (cx0, cy0)
wr = max(st[best][2], st[best][3]) / 2 + 6
print(f"watermark at ({wx:.0f},{wy:.0f}) r={wr:.0f}")
wm = np.zeros((H, W), np.uint8)
cv2.circle(wm, (int(wx), int(wy)), int(wr), 255, -1)
# Grass is texture, so diffusion inpainting smears. Instead clone a nearby
# grass patch over it (Poisson blend keeps the lighting continuous).
shift = (-int(wr * 2.6), int(wr * 0.3))
M = np.float32([[1, 0, -shift[0]], [0, 1, -shift[1]]])
donor = cv2.warpAffine(im, M, (W, H), borderMode=cv2.BORDER_REFLECT)
clean = cv2.seamlessClone(donor, im, wm, (int(wx), int(wy)), cv2.NORMAL_CLONE)

still = clean.copy()  # deliverable still: watermark removed, nothing else touched

# ---------------------------------------------------------------- frozen petals
# The still has petals frozen in mid-air. Next to animated petals they look
# stuck, so lift the airborne ones out of the animation plate (they are replaced
# by moving ones). Canopy blossoms and petals lying on the grass are untouched.
hsv0 = cv2.cvtColor(clean, cv2.COLOR_BGR2HSV)
pk = (((hsv0[..., 0] >= 150) | (hsv0[..., 0] <= 8)) & (hsv0[..., 1] > 20) & (hsv0[..., 2] > 165)).astype(np.uint8)
pk_loose = ((hsv0[..., 0] >= 145) | (hsv0[..., 0] <= 10)) & (hsv0[..., 1] > 28)
dens = cv2.GaussianBlur(pk.astype(np.float32), (0, 0), 22)
n, lab, st, cen = cv2.connectedComponentsWithStats(pk)
pm = np.zeros((H, W), np.uint8)
cnt_p = 0
for i in range(1, n):
    x, y, w, h, a = st[i]
    cx_, cy_ = cen[i]
    if a < 900 and max(w, h) < 60 and y > 5 and cy_ < 0.69 * H and dens[int(cy_), int(cx_)] < 0.16:
        # skip blobs that are really part of a bigger blossom cluster (pink right next to them)
        y0_, y1_, x0_, x1_ = max(0, y - 6), min(H, y + h + 6), max(0, x - 6), min(W, x + w + 6)
        comp = (lab[y0_:y1_, x0_:x1_] == i).astype(np.uint8)
        ring = (cv2.dilate(comp, np.ones((11, 11), np.uint8)) > 0) & (cv2.dilate(comp, np.ones((3, 3), np.uint8)) == 0)
        if pk_loose[y0_:y1_, x0_:x1_][ring].mean() > 0.10:
            continue
        pm[y0_:y1_, x0_:x1_][comp > 0] = 255
        cnt_p += 1
pm = cv2.dilate(pm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
filled = cv2.inpaint(clean, pm, 3, cv2.INPAINT_TELEA)
# diffusion fill is too smooth: give it back the photo's fine grain/texture,
# borrowed from a nearby (shifted) patch of the same image
hp = clean.astype(np.float32) - cv2.GaussianBlur(clean, (0, 0), 2.5).astype(np.float32)
hp = np.roll(hp, (9, 17), (0, 1))
hp[np.roll(pm, (9, 17), (0, 1)) > 0] = 0
soft = cv2.GaussianBlur(pm, (0, 0), 1.2).astype(np.float32)[..., None] / 255
clean = np.clip(clean * (1 - soft) + (filled.astype(np.float32) + hp * 0.9) * soft, 0, 255).astype(np.uint8)
print("airborne petals lifted from plate:", cnt_p)

# ---------------------------------------------------------------- screen quad
hsv = cv2.cvtColor(clean, cv2.COLOR_BGR2HSV)
green = cv2.inRange(hsv, (45, 150, 150), (75, 255, 255))
n, lab, st, _ = cv2.connectedComponentsWithStats(green)
i = 1 + int(np.argmax(st[1:, 4]))
gm = (lab == i).astype(np.uint8) * 255
cnt = max(cv2.findContours(gm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
ap = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True).reshape(-1, 2).astype(np.float32)
assert len(ap) == 4, ap
# order TL, TR, BR, BL
s, d = ap.sum(1), ap[:, 0] - ap[:, 1]
quad = np.float32([ap[s.argmin()], ap[d.argmax()], ap[s.argmax()], ap[d.argmin()]])
# Sub-pixel refine: fit a line to each side of the contour and intersect.
cpts = cnt.reshape(-1, 2).astype(np.float32)
lines = []
for a, b in zip(quad, np.roll(quad, -1, 0)):
    ab = b - a
    L = np.linalg.norm(ab)
    t = ((cpts - a) @ ab) / L ** 2
    dist = np.abs(cross2(ab, cpts - a)) / L
    sel = cpts[(t > 0.12) & (t < 0.88) & (dist < 3)]
    vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
    lines.append((np.array([x0, y0]), np.array([vx, vy])))


def isect(l1, l2):
    (p, r), (q, s_) = l1, l2
    t = cross2(q - p, s_) / cross2(r, s_)
    return p + t * r


# contour pixels are pixel centres of the outermost green pixels -> grow 0.5px
quad = np.float32([isect(lines[3], lines[0]), isect(lines[0], lines[1]),
                   isect(lines[1], lines[2]), isect(lines[2], lines[3])])
c = quad.mean(0)
quad = quad + (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True) * 0.6
print("quad TL,TR,BR,BL:", quad.round(2).tolist())

# ---------------------------------------------------------------- laptop mask
# Lid: screen quad grown by the bezel. Base: grey/desaturated or green-lit
# region directly below the lid, limited to a trapezoid derived from the quad.
tl, tr, br, bl = quad
sw = np.linalg.norm(tr - tl)
sh = np.linalg.norm(bl - tl)
lid = np.float32([tl + (-0.035 * sw, -0.075 * sh), tr + (0.035 * sw, -0.075 * sh),
                  br + (0.035 * sw, 0.10 * sh), bl + (-0.035 * sw, 0.10 * sh)])
base = np.float32([bl + (-0.035 * sw, 0.08 * sh), br + (0.035 * sw, 0.08 * sh),
                   br + (0.185 * sw, 0.45 * sh), bl + (-0.185 * sw, 0.45 * sh)])
lap = np.zeros((H, W), np.uint8)
cv2.fillConvexPoly(lap, lid.astype(np.int32), 255)
cv2.fillConvexPoly(lap, base.astype(np.int32), 255)
lap_hard = lap.copy()

# ---------------------------------------------------------------- despill
# First blank the screen (quad grown 3px so the antialiased green rim goes too):
# near-black glass = the "screen off" look.
grow = (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True)
qmask = np.zeros((H, W), np.uint8)
cv2.fillConvexPoly(qmask, np.round(quad + grow * 3).astype(np.int32), 255)
qf = cv2.GaussianBlur(qmask, (0, 0), 0.7).astype(np.float32)[..., None] / 255
blank = clean.astype(np.float32) * (1 - qf) + np.float32([14, 12, 11]) * qf
bh = cv2.cvtColor(blank.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
b, g, r = [blank[..., k] for k in range(3)]
hue, sat = bh[..., 0], bh[..., 1]
# Chroma green (H~60, saturated) and its pale reflection on the aluminium
# (H~40-50 but low saturation) separate from grass (H~32-40, high saturation).
neutral = 0.6 * np.maximum(r, b) + 0.4 * np.minimum(r, b)
excess = np.clip(g - neutral, 0, None)
pure = ss(47, 55, hue) * (1 - ss(80, 90, hue)) * ss(15, 40, sat)
pale = ss(34, 40, hue) * (1 - ss(80, 90, hue)) * (1 - ss(105, 128, sat))
chroma_like = np.maximum(pure, pale)
region = cv2.GaussianBlur(cv2.dilate(lap, np.ones((5, 5), np.uint8)), (0, 0), 1.5).astype(np.float32) / 255
spill = cv2.GaussianBlur(excess * chroma_like * region, (0, 0), 0.8)
plate = np.dstack([b, g - spill, r])
# The removed spill shows where screen light lands on the keyboard / palm rest.
# Keep it as a re-lighting map driven by the playing video.
spill_map = np.clip(spill, 0, 80)
plate_off = np.clip(plate, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- depth (MiDaS small, CPU, via cv2.dnn)
net = cv2.dnn.readNet(os.path.join(work, "midas_small.onnx"))
rgb = cv2.cvtColor(plate_off, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
rgb = (rgb - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
blob = cv2.dnn.blobFromImage(cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32))
net.setInput(blob)
dm = net.forward().squeeze()
dm = cv2.resize(dm, (W, H), interpolation=cv2.INTER_CUBIC)
dm = (dm - dm.min()) / (dm.max() - dm.min())  # 1 = near
depth_raw = dm.copy()
# Laptop is a rigid object: give it a smooth planar depth so the screen never warps.
ys = yy[lap_hard > 0]
A = np.c_[ys, np.ones_like(ys)]
coef, *_ = np.linalg.lstsq(A, dm[lap_hard > 0], rcond=None)
lapf = cv2.GaussianBlur(lap_hard, (0, 0), 6).astype(np.float32) / 255
dm = dm * (1 - lapf) + (coef[0] * yy + coef[1]) * lapf
depth = cv2.GaussianBlur(dm, (0, 0), 9)

# ---------------------------------------------------------------- motion masks
lum = cv2.cvtColor(plate_off, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
lap_soft = cv2.GaussianBlur(cv2.dilate(lap_hard, np.ones((9, 9), np.uint8)), (0, 0), 4).astype(np.float32) / 255
ph = cv2.cvtColor(plate_off, cv2.COLOR_BGR2HSV).astype(np.float32)
is_green = ss(22, 30, ph[..., 0]) * (1 - ss(70, 85, ph[..., 0])) * ss(40, 90, ph[..., 1])
# grass: near, green, lower part of frame
grass = ss(0.50, 0.66, depth_raw) * ss(0.66, 0.76, yy / H) * np.maximum(is_green, ss(0.80, 0.9, yy / H))
grass = cv2.GaussianBlur(grass, (0, 0), 3) * (1 - lap_soft)
# tips catch the light, roots sit in shadow -> brightness ~ how far up the blade
lum_n = cv2.GaussianBlur(lum, (0, 0), 1.2)
tip = ss(0.10, 0.55, lum_n)
grass_amp = grass * (0.25 + 0.75 * tip)

# trees: pink blossom + dark branches in the upper part
pink = (ss(140, 150, ph[..., 0]) + (1 - ss(4, 10, ph[..., 0]))) * ss(25, 60, ph[..., 1]) * ss(90, 140, ph[..., 2])
pink = np.clip(pink, 0, 1)
canopy = cv2.GaussianBlur(cv2.dilate(pink, np.ones((15, 15), np.uint8)), (0, 0), 8)
upper = 1 - ss(0.42, 0.56, yy / H)
tree = np.clip(canopy * 1.4, 0, 1) * upper
# trunks/thick limbs barely move, blossom clusters and twigs move more
tree_amp = tree * (0.25 + 0.75 * cv2.GaussianBlur(pink, (0, 0), 4))
tree_amp = cv2.GaussianBlur(tree_amp, (0, 0), 5)

# far mask (sky / mountains / river / far bank) - background petals hide behind near stuff
far = 1 - ss(0.22, 0.40, cv2.GaussianBlur(depth_raw, (0, 0), 2))
far = far * (1 - cv2.GaussianBlur(tree, (0, 0), 2) * 0.9) * (1 - lap_soft)

# mist band over the river
mist = ss(0.50, 0.58, yy / H) * (1 - ss(0.65, 0.72, yy / H)) * (1 - ss(0.45, 0.62, depth_raw)) * (1 - lap_soft)

np.savez_compressed(
    os.path.join(work, "prep.npz"),
    clean=clean, plate_off=plate_off, quad=quad,
    spill_map=spill_map.astype(np.float32), depth=depth.astype(np.float32),
    lap=(lap_hard > 0), lap_soft=lap_soft.astype(np.float32),
    grass_amp=grass_amp.astype(np.float32), tree_amp=tree_amp.astype(np.float32),
    far=far.astype(np.float32), mist=mist.astype(np.float32),
)
cv2.imwrite(os.path.join(work, "clean.png"), still)
cv2.imwrite(os.path.join(work, "plate_no_petals.png"), clean)
cv2.imwrite(os.path.join(work, "clean_1080p.png"),
            cv2.resize(still, (1936, 1080), interpolation=cv2.INTER_LANCZOS4)[:, 8:-8])


def v(a):
    return cv2.cvtColor((np.clip(a, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


dbg = plate_off.copy()
cv2.polylines(dbg, [np.round(quad).astype(np.int32)], True, (0, 0, 255), 1, cv2.LINE_AA)
cv2.polylines(dbg, [lid.astype(np.int32), base.astype(np.int32)], True, (255, 0, 255), 1, cv2.LINE_AA)
row1 = np.hstack([dbg, v(depth), v(spill_map)])
row2 = np.hstack([v(grass_amp), v(tree_amp), v(far * 0.6 + mist * 0.4)])
cv2.imwrite(os.path.join(work, "debug_masks.jpg"), cv2.resize(np.vstack([row1, row2]), None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA))
x0, y0 = int(tl[0] - 90), int(tl[1] - 30)
cv2.imwrite(os.path.join(work, "debug_laptop.png"),
            cv2.resize(np.hstack([dbg, plate_off])[y0:y0 + 320, :][:, list(range(x0, x0 + 460)) + list(range(W + x0, W + x0 + 460))],
                       None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
wx, wy = int(wx), int(wy)
cv2.imwrite(os.path.join(work, "debug_wm.png"),
            cv2.resize(np.hstack([im, clean])[wy - 70:wy + 70, :][:, list(range(wx - 90, wx + 90)) + list(range(W + wx - 90, W + wx + 90))],
                       None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC))
print("ok")
