#!/usr/bin/env python3
"""Sequence step 1: prepare the four stills (clean, masks, depth, screen quads).

  python3 scripts/seq_prepare.py output/seq/input output/seq/work [midas_small.onnx]

Expects vista.png, canopy.png, wide.png (laptop, screen off) and closeup.png
(laptop, green screen) in the input folder. Writes prep_<shot>.npz per shot.
"""
import os
import sys

import cv2
import numpy as np

src, work = sys.argv[1], sys.argv[2]
midas = sys.argv[3] if len(sys.argv) > 3 else "output/work/midas_small.onnx"
os.makedirs(work, exist_ok=True)
H, W = 768, 1376
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
net = cv2.dnn.readNet(midas)

# quad of the wide shot's (black) screen, TL,TR,BR,BL. A black screen inside a
# black bezel cannot be keyed, so this was measured once on the matching
# green-screen version of the same still.
WIDE_QUAD = np.float32([[553.09, 435.67], [821.85, 435.67], [828.22, 615.32], [546.77, 615.32]])

SHOTS = {
    #          grass from, canopy until, petals lifted above, mist band,        base poly (side, depth)
    "vista":   dict(grass=0.80, tree=0.56, lift=0.80, mist=(0.50, 0.58, 0.76, 0.84)),
    "canopy":  dict(grass=None, tree=1.01, lift=0.35, mist=None),
    "wide":    dict(grass=0.66, tree=0.56, lift=0.69, mist=(0.50, 0.58, 0.65, 0.72), base=(0.185, 0.45)),
    "closeup": dict(grass=0.62, tree=0.50, lift=None, mist=None, base=(0.22, 0.34), all_green=True),
}


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def cross2(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def remove_watermark(im):
    """Generator sparkle, always at the same spot bottom-right: clone nearby texture over it."""
    cx, cy, r = 1255, 648, 31
    m = np.zeros((H, W), np.uint8)
    cv2.circle(m, (cx, cy), r, 255, -1)
    M = np.float32([[1, 0, int(r * 2.6)], [0, 1, -int(r * 0.3)]])
    donor = cv2.warpAffine(im, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    return cv2.seamlessClone(donor, im, m, (cx, cy), cv2.NORMAL_CLONE)


def lift_petals(clean, ymax):
    """Take petals frozen in mid-air out of the plate (animated ones replace them)."""
    hsv0 = cv2.cvtColor(clean, cv2.COLOR_BGR2HSV)
    pink_h = (hsv0[..., 0] >= 150) | (hsv0[..., 0] <= 8)
    pk = (pink_h & (hsv0[..., 1] > 20) & (hsv0[..., 2] > 165)).astype(np.uint8)
    pk_loose = ((hsv0[..., 0] >= 145) | (hsv0[..., 0] <= 10)) & (hsv0[..., 1] > 28)
    dens = cv2.GaussianBlur(pk.astype(np.float32), (0, 0), 22)
    n, lab, st, cen = cv2.connectedComponentsWithStats(pk)
    pm = np.zeros((H, W), np.uint8)
    cnt = 0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        cx_, cy_ = cen[i]
        if a < 900 and max(w, h) < 60 and y > 5 and cy_ < ymax * H and dens[int(cy_), int(cx_)] < 0.16:
            y0, y1, x0, x1 = max(0, y - 6), min(H, y + h + 6), max(0, x - 6), min(W, x + w + 6)
            comp = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
            ring = (cv2.dilate(comp, np.ones((11, 11), np.uint8)) > 0) & (cv2.dilate(comp, np.ones((3, 3), np.uint8)) == 0)
            if pk_loose[y0:y1, x0:x1][ring].mean() > 0.10:   # part of a bigger blossom cluster
                continue
            pm[y0:y1, x0:x1][comp > 0] = 255
            cnt += 1
    pm = cv2.dilate(pm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    filled = cv2.inpaint(clean, pm, 3, cv2.INPAINT_TELEA)
    hp = clean.astype(np.float32) - cv2.GaussianBlur(clean, (0, 0), 2.5).astype(np.float32)
    hp = np.roll(hp, (9, 17), (0, 1))                       # borrow nearby grain for the fill
    hp[np.roll(pm, (9, 17), (0, 1)) > 0] = 0
    soft = cv2.GaussianBlur(pm, (0, 0), 1.2).astype(np.float32)[..., None] / 255
    out = np.clip(clean * (1 - soft) + (filled.astype(np.float32) + hp * 0.9) * soft, 0, 255).astype(np.uint8)
    return out, cnt


def green_quad(clean):
    hsv = cv2.cvtColor(clean, cv2.COLOR_BGR2HSV)
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
    for a, b in zip(quad, np.roll(quad, -1, 0)):           # sub-pixel: fit each side, intersect
        ab = b - a
        L = np.linalg.norm(ab)
        t = ((cpts - a) @ ab) / L ** 2
        sel = cpts[(t > 0.12) & (t < 0.88) & (np.abs(cross2(ab, cpts - a)) / L < 3)]
        vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))

    def isect(l1, l2):
        (p, r), (q, s_) = l1, l2
        return p + cross2(q - p, s_) / cross2(r, s_) * r

    quad = np.float32([isect(lines[3], lines[0]), isect(lines[0], lines[1]), isect(lines[1], lines[2]), isect(lines[2], lines[3])])
    c = quad.mean(0)
    return quad + (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True) * 0.6


def prepare(name, cfg):
    im = cv2.imread(os.path.join(src, name + ".png"))
    assert im.shape[:2] == (H, W), im.shape
    clean = remove_watermark(im)
    lifted = 0
    if cfg["lift"]:
        clean, lifted = lift_petals(clean, cfg["lift"])

    quad = None
    lap = np.zeros((H, W), np.uint8)
    spill = np.zeros((H, W), np.float32)
    plate = clean
    if "base" in cfg:
        quad = green_quad(clean) if name == "closeup" else WIDE_QUAD
        tl, tr, br, bl = quad
        sw, sh = np.linalg.norm(tr - tl), np.linalg.norm(bl - tl)
        bs, bd = cfg["base"]
        lid = np.float32([tl + (-0.035 * sw, -0.075 * sh), tr + (0.035 * sw, -0.075 * sh),
                          br + (0.035 * sw, 0.10 * sh), bl + (-0.035 * sw, 0.10 * sh)])
        base = np.float32([bl + (-0.035 * sw, 0.06 * sh), br + (0.035 * sw, 0.06 * sh),
                           br + (bs * sw, bd * sh), bl + (-bs * sw, bd * sh)])
        cv2.fillConvexPoly(lap, lid.astype(np.int32), 255)
        cv2.fillConvexPoly(lap, base.astype(np.int32), 255)
        # screen-off glass (quad grown 3px so no antialiased green rim survives)
        c = quad.mean(0)
        grow = (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True)
        qmask = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(qmask, np.round(quad + grow * 3).astype(np.int32), 255)
        qf = cv2.GaussianBlur(qmask, (0, 0), 0.7).astype(np.float32)[..., None] / 255
        blank = clean.astype(np.float32) * (1 - qf) + np.float32([14, 12, 11]) * qf
        # despill: chroma green (saturated H~60) + its pale reflection on aluminium, never the grass
        bh = cv2.cvtColor(blank.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        b, g, r = [blank[..., k] for k in range(3)]
        hue, sat = bh[..., 0], bh[..., 1]
        neutral = 0.6 * np.maximum(r, b) + 0.4 * np.minimum(r, b)
        excess = np.clip(g - neutral, 0, None)
        pure = ss(47, 55, hue) * (1 - ss(80, 90, hue)) * ss(15, 40, sat)
        pale = ss(34, 40, hue) * (1 - ss(80, 90, hue)) * (1 - ss(105, 128, sat))
        region = cv2.GaussianBlur(cv2.dilate(lap, np.ones((5, 5), np.uint8)), (0, 0), 1.5).astype(np.float32) / 255
        chroma = np.maximum(pure, pale)
        bm = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(bm, base.astype(np.int32), 255)
        if cfg.get("all_green"):   # close-up: no grass overlaps the keyboard, so every green there is spill
            chroma = np.maximum(chroma, ss(30, 38, hue) * (1 - ss(80, 90, hue)) * (bm > 0))
        spill = cv2.GaussianBlur(excess * chroma * region, (0, 0), 0.8)
        plate = np.clip(np.dstack([b, g - spill, r]), 0, 255).astype(np.uint8)
        spill = np.clip(spill, 0, 80)
        if spill[bm > 0].mean() < 2:
            # screen was off in the still: no measured reflection, so model one on keys + palm rest
            lum_ = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
            spill = cv2.GaussianBlur(bm.astype(np.float32) / 255 * (6 + 26 * lum_) * (1 - ss(0.0, 1.0, (yy - bl[1]) / (bd * sh))), (0, 0), 1.5)

    # depth (MiDaS small on CPU)
    rgb = cv2.cvtColor(plate, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    rgb = (rgb - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
    net.setInput(cv2.dnn.blobFromImage(cv2.resize(rgb, (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32)))
    dm = cv2.resize(net.forward().squeeze(), (W, H), interpolation=cv2.INTER_CUBIC)
    dm = (dm - dm.min()) / (dm.max() - dm.min())            # 1 = near
    depth_raw = dm.copy()
    lap_dep = 0.0
    if quad is not None:                                     # rigid laptop: one depth, moves as a unit
        lap_dep = float(np.median(dm[lap > 0]))
        lapf = cv2.GaussianBlur(lap, (0, 0), 6).astype(np.float32) / 255
        dm = dm * (1 - lapf) + lap_dep * lapf
    depth = cv2.GaussianBlur(dm, (0, 0), 9)

    lum = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    lap_soft = cv2.GaussianBlur(cv2.dilate(lap, np.ones((9, 9), np.uint8)), (0, 0), 4).astype(np.float32) / 255
    ph = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV).astype(np.float32)
    grass_amp = np.zeros((H, W), np.float32)
    if cfg["grass"]:
        g0 = cfg["grass"]
        is_green = ss(22, 30, ph[..., 0]) * (1 - ss(70, 85, ph[..., 0])) * ss(40, 90, ph[..., 1])
        grass = ss(0.45, 0.62, depth_raw) * ss(g0, g0 + 0.10, yy / H) * np.maximum(is_green, ss(g0 + 0.14, g0 + 0.24, yy / H))
        grass = cv2.GaussianBlur(grass, (0, 0), 3) * (1 - lap_soft)
        tip = ss(0.10, 0.55, cv2.GaussianBlur(lum, (0, 0), 1.2))   # bright = blade tips, dark = roots
        grass_amp = grass * (0.25 + 0.75 * tip)
    pink = np.clip((ss(140, 150, ph[..., 0]) + (1 - ss(4, 10, ph[..., 0]))) * ss(25, 60, ph[..., 1]) * ss(90, 140, ph[..., 2]), 0, 1)
    canopy = cv2.GaussianBlur(cv2.dilate(pink, np.ones((15, 15), np.uint8)), (0, 0), 8)
    tree = np.clip(canopy * 1.4, 0, 1) * (1 - ss(cfg["tree"] - 0.14, cfg["tree"], yy / H)) * (1 - lap_soft)
    tree_amp = cv2.GaussianBlur(tree * (0.25 + 0.75 * cv2.GaussianBlur(pink, (0, 0), 4)), (0, 0), 5)
    far = (1 - ss(0.22, 0.40, cv2.GaussianBlur(depth_raw, (0, 0), 2))) * (1 - cv2.GaussianBlur(tree, (0, 0), 2) * 0.9) * (1 - lap_soft)
    mist = np.zeros((H, W), np.float32)
    if cfg["mist"]:
        a, b_, c_, d_ = cfg["mist"]
        mist = ss(a, b_, yy / H) * (1 - ss(c_, d_, yy / H)) * (1 - ss(0.45, 0.62, depth_raw)) * (1 - lap_soft)

    np.savez_compressed(
        os.path.join(work, f"prep_{name}.npz"), plate=plate, depth=depth.astype(np.float32),
        quad=quad if quad is not None else np.zeros((0, 2), np.float32), lap_dep=lap_dep,
        spill=spill.astype(np.float32), lap=(lap > 0), lap_soft=lap_soft.astype(np.float32),
        grass_amp=grass_amp.astype(np.float32), tree_amp=tree_amp.astype(np.float32),
        far=far.astype(np.float32), mist=mist.astype(np.float32))

    def v(a):
        return cv2.cvtColor((np.clip(a, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    dbg = plate.copy()
    if quad is not None:
        cv2.polylines(dbg, [np.round(quad).astype(np.int32)], True, (0, 0, 255), 1, cv2.LINE_AA)
    sheet = np.vstack([np.hstack([dbg, v(depth), v(spill / 60)]), np.hstack([v(grass_amp), v(tree_amp), v(far * 0.6 + mist * 0.4)])])
    cv2.imwrite(os.path.join(work, f"debug_{name}.jpg"), cv2.resize(sheet, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA))
    cv2.imwrite(os.path.join(work, f"plate_{name}.png"), plate)
    print(f"{name}: petals lifted={lifted} quad={'yes' if quad is not None else 'no'} lap_dep={lap_dep:.2f}")


for name, cfg in SHOTS.items():
    prepare(name, cfg)
