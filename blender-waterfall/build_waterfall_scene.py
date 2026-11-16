"""
WATERFALL VALLEY - Blender build script
=======================================
STEP 1 of 8: Plan + Clay match (geometry and camera only, grey clay override).

How to run (Blender 4.2+ / 5.x):
  A) Blender UI: File > New > General, then the Scripting tab > Open > this file > Run Script.
     WARNING: the script deletes every object in the CURRENT scene first. Use a new file.
  B) Command line (renders a clay preview still automatically):
     blender -b -P build_waterfall_scene.py

Coordinates: metres. +Y = camera looking forward (upstream), +X = right, +Z = up.
The layout is matched to the LEFT column of the reference sheet (Final/Clay left panel):
thin waterfall right of centre, layered cliffs left and right, river running to camera,
big smooth boulders in the foreground, pines on the slopes, peak in the centre gap.

All noise is pure Python (no mathutils), so the same geometry can be generated outside
Blender for offline checks. Building takes about 1-2 minutes.
"""

import math
import os
import random

try:
    import bpy
except ImportError:  # dry run outside Blender (offline preview / tests)
    bpy = None

# ---------------------------------------------------------------- CONFIG
MIRROR_X = False          # True = flip the whole layout left/right (waterfall left, sun top-left)
USE_CLAY_OVERRIDE = True  # Step 1: everything renders as matte grey clay
SEED = 7
PREVIEW_PERCENT = 50      # 50% of 1920x1080 for the clay test
PREVIEW_SAMPLES = 32
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "waterfall_project")
SAVE_BLEND = True
RENDER_STILL_IN_BACKGROUND = True   # only when run with blender -b

CAM_LOC = (0.0, -2.0, 1.8)
CAM_PITCH_DEG = 6.0       # tilt up from horizontal
CAM_LENS = 24.0
SUN_AZIMUTH_DEG = 24.0    # degrees to the right of the camera's forward direction
SUN_ELEVATION_DEG = 25.0

COLLECTIONS = ["Terrain", "Water", "Rocks", "Vegetation", "Leaves", "Birds", "Lights", "Camera"]


def mx(x):
    return -x if MIRROR_X else x


def P(x, y):
    return (mx(x), y)


# ---------------------------------------------------------------- MATH / NOISE
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def _hash3(ix, iy, iz, seed):
    h = (ix * 374761393 + iy * 668265263 + iz * 1274126177 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 3266489917) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFF) / 32767.5 - 1.0


def hash1(i, seed):
    return (_hash3(int(i), 17, 31, seed) + 1.0) * 0.5


def vnoise(x, y, z=0.0, seed=0):
    """Smooth 3D value noise, range about -1..1."""
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    uz = fz * fz * fz * (fz * (fz * 6 - 15) + 10)
    h = _hash3
    x00 = lerp(h(ix, iy, iz, seed), h(ix + 1, iy, iz, seed), ux)
    x10 = lerp(h(ix, iy + 1, iz, seed), h(ix + 1, iy + 1, iz, seed), ux)
    x01 = lerp(h(ix, iy, iz + 1, seed), h(ix + 1, iy, iz + 1, seed), ux)
    x11 = lerp(h(ix, iy + 1, iz + 1, seed), h(ix + 1, iy + 1, iz + 1, seed), ux)
    return lerp(lerp(x00, x10, uy), lerp(x01, x11, uy), uz)


def fbm(x, y, z=0.0, octaves=4, seed=0, lac=2.03, gain=0.5):
    s, a, f, norm = 0.0, 1.0, 1.0, 0.0
    for i in range(octaves):
        s += a * vnoise(x * f + i * 17.31, y * f + i * 9.13, z * f + i * 3.7, seed + i)
        norm += a
        a *= gain
        f *= lac
    return s / norm


def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(
        0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
               + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
        for k in range(2))


def icosphere(subdiv):
    t = (1.0 + 5 ** 0.5) / 2.0
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
             (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [tuple(c / math.sqrt(sum(q * q for q in v)) for c in v) for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
             (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
             (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache, new_faces = {}, []

        def mid(a, b):
            key = (a, b) if a < b else (b, a)
            if key not in cache:
                va, vb = verts[a], verts[b]
                m = [(va[k] + vb[k]) / 2 for k in range(3)]
                ln = math.sqrt(sum(q * q for q in m))
                verts.append(tuple(q / ln for q in m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new_faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new_faces
    return verts, faces


def grid_faces(cols, rows):
    """Quad faces for a (cols x rows) vertex grid stored column-major (index = i*rows + j)."""
    return [(i * rows + j, (i + 1) * rows + j, (i + 1) * rows + j + 1, i * rows + j + 1)
            for i in range(cols - 1) for j in range(rows - 1)]


# ---------------------------------------------------------------- RIVER + TERRAIN
RIVER_PTS = [P(40, 92), P(33, 75), P(22, 58), P(11, 40), P(4, 22), P(0, 5), P(0, -25)]
RIVER_HALF_W = [7.0, 7.5, 8.5, 9.5, 10.5, 12.0, 13.0]
POOL_C, POOL_R = P(40, 91), 11.0


def river_info(x, y):
    """Distance to river centreline and the river half-width at the closest point."""
    best_d, best_w = 1e9, RIVER_HALF_W[-1]
    for i in range(len(RIVER_PTS) - 1):
        (ax, ay), (bx, by) = RIVER_PTS[i], RIVER_PTS[i + 1]
        dx, dy = bx - ax, by - ay
        s = clamp(((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy))
        px, py = ax + dx * s, ay + dy * s
        d = math.hypot(x - px, y - py)
        if d < best_d:
            best_d, best_w = d, lerp(RIVER_HALF_W[i], RIVER_HALF_W[i + 1], s)
    return best_d, best_w


def terrain_h(x, y):
    d, rw = river_info(x, y)
    if d < rw:                                    # river channel (water surface is z=0)
        k = d / rw
        h = -0.15 - 0.85 * (1.0 - k * k)
    else:                                         # bank, then steep grassy slopes
        e = d - rw
        h = -0.15 + 1.6 * smoothstep(0.0, 6.0, e) + 0.35 * max(0.0, e - 8.0)
        h = min(h, 22.0)
        h += 2.2 * fbm(x * 0.035, y * 0.035, 0.0, 4, SEED + 1) * smoothstep(0.0, 8.0, e)
    h += 0.25 * fbm(x * 0.35, y * 0.35, 3.1, 3, SEED + 2)
    pd = math.hypot(x - POOL_C[0], y - POOL_C[1])  # plunge pool
    w = smoothstep(POOL_R, POOL_R * 0.55, pd)
    h = lerp(h, -1.7 * (1.0 - (pd / POOL_R) ** 2) - 0.2, w)
    return h


# ---------------------------------------------------------------- CLIFFS
class Cliff:
    """A layered rock wall built as a vertical sheet that follows a plan curve.
    Displacement is horizontal, along the curve normal that faces the camera."""

    def __init__(self, name, ctrl, heights, seed, base_z=-6.0):
        self.name, self.seed, self.base_z = name, seed, base_z
        self.recess = None   # (u_centre, width, depth)
        self.notch = None    # (u_centre, width, z_top)
        pts, hs = [], []
        n = len(ctrl)
        for i in range(n - 1):
            p0, p1, p2, p3 = ctrl[max(i - 1, 0)], ctrl[i], ctrl[i + 1], ctrl[min(i + 2, n - 1)]
            for k in range(40):
                t = k / 40.0
                pts.append(catmull(p0, p1, p2, p3, t))
                hs.append(lerp(heights[i], heights[i + 1], smoothstep(0.0, 1.0, t)))
        pts.append(ctrl[-1])
        hs.append(heights[-1])
        self.pts, self.hs = pts, hs
        self.cum = [0.0]
        for i in range(1, len(pts)):
            self.cum.append(self.cum[-1] + math.dist(pts[i - 1], pts[i]))
        self.length = self.cum[-1]

    def _idx(self, u):
        lo, hi = 0, len(self.cum) - 1
        u = clamp(u, 0.0, self.length)
        while hi - lo > 1:
            m = (lo + hi) // 2
            if self.cum[m] <= u:
                lo = m
            else:
                hi = m
        seg = self.cum[hi] - self.cum[lo]
        return lo, hi, (u - self.cum[lo]) / seg if seg > 0 else 0.0

    def frame(self, u):
        """Position (x, y) and camera-facing normal (nx, ny) at arc length u."""
        lo, hi, t = self._idx(u)
        a, b = self.pts[lo], self.pts[hi]
        px, py = lerp(a[0], b[0], t), lerp(a[1], b[1], t)
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        tx, ty = tx / ln, ty / ln
        nx, ny = ty, -tx
        if nx * (CAM_LOC[0] - px) + ny * (CAM_LOC[1] - py) < 0:
            nx, ny = -nx, -ny
        return px, py, nx, ny, tx, ty

    def top(self, u):
        lo, hi, t = self._idx(u)
        h = lerp(self.hs[lo], self.hs[hi], t) + 4.0 * fbm(u * 0.04, 0.0, 0.0, 3, self.seed + 20)
        if self.notch:
            uc, w, zt = self.notch
            g = math.exp(-((u - uc) / w) ** 2)
            h = lerp(h, min(h, zt), g)
        return h

    def disp(self, u, z):
        s = self.seed
        top = self.top(u)
        zz = z + 0.04 * u + 2.0 * fbm(u * 0.015, 0.5, 0.0, 2, s + 11)
        lt = 3.4                                   # strata layer thickness
        li = math.floor(zz / lt)
        fr = zz / lt - li
        strata = (hash1(li, s) - 0.5) * 1.5 + 0.6 * smoothstep(0.0, 0.18, fr) - 0.6
        big = 6.0 * fbm(u * 0.025, z * 0.03, 0.3, 3, s + 1)
        mid = 1.6 * fbm(u * 0.11, z * 0.16, 1.7, 3, s + 2)
        fine = 0.35 * fbm(u * 0.55, z * 0.55, 2.9, 2, s + 3)
        crev = -2.2 * (1.0 - abs(vnoise(u * 0.16, 0.37, z * 0.012, s + 4))) ** 6
        roll = -6.0 * smoothstep(top - 7.0, top, z) ** 2
        talus = 3.5 * (1.0 - smoothstep(self.base_z, self.base_z + 9.0, z))
        d = big + mid + fine + strata + crev + roll + talus
        if self.recess:
            uc, w, depth = self.recess
            d -= depth * math.exp(-((u - uc) / w) ** 2)
        return d

    u_cut = None

    def mesh(self, du=0.7, dz=0.6):
        length = min(self.length, self.u_cut or self.length)
        cols = int(length / du) + 1
        max_top = max(self.top(i * du) for i in range(cols))
        rows = int((max_top - self.base_z) / dz) + 1
        verts = []
        for i in range(cols):
            u = min(i * du, length)
            px, py, nx, ny, _, _ = self.frame(u)
            tp = self.top(u)
            for j in range(rows):
                z = self.base_z + (tp - self.base_z) * j / (rows - 1)
                d = self.disp(u, z)
                verts.append((px + nx * d, py + ny * d, z))
        faces = grid_faces(cols, rows)
        # make face normals point toward the camera (solidify then grows backwards)
        px, py, nx, ny, tx, ty = self.frame(self.length * 0.5)
        if ty * nx - tx * ny < 0:
            faces = [tuple(reversed(f)) for f in faces]
        return verts, faces

    def u_nearest(self, x, y):
        best, bu = 1e18, 0.0
        for i, p in enumerate(self.pts):
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best:
                best, bu = d, self.cum[i]
        return bu

    def signed_dist(self, x, y):
        """>0 = in front of the cliff base line (camera side)."""
        u = self.u_nearest(x, y)
        px, py, nx, ny, _, _ = self.frame(u)
        return (x - px) * nx + (y - py) * ny, u


WATERFALL_TOP = 27.0


def make_cliffs():
    """One amphitheatre wall: tall left mass -> lower centre face -> waterfall notch -> tall right wall.
    Split in two objects at the waterfall so each stays a manageable mesh."""
    left = Cliff("Cliff_Left_Centre",
                 [P(-64, 18), P(-50, 55), P(-38, 85), P(-18, 108), P(5, 115), P(25, 110), P(44, 100),
                  P(52, 86)],
                 [32.0, 45.0, 52.0, 48.0, 42.0, 29.0, 27.0, 40.0], SEED + 100)
    right = Cliff("Cliff_Right",
                  [P(47, 95), P(52, 86), P(60, 62), P(66, 36), P(70, 10)],
                  [30.0, 52.0, 55.0, 50.0, 42.0], SEED + 200)
    u_wf = left.u_nearest(*P(44, 100))
    left.recess = (u_wf, 7.0, 4.0)
    left.notch = (u_wf, 6.0, WATERFALL_TOP)
    left.u_cut = u_wf + 9.0            # left wall stops just past the falls, right wall takes over
    return left, right, u_wf


def waterfall_mesh(cliff, u_c, z_top, w_top, w_bot, out, seed, z_bot=-0.6, cols=14, dz=0.4):
    """Free-falling curtain: hugs the rock at the lip, never re-enters it, arcs outward."""
    rows = int((z_top - z_bot) / dz) + 1
    grid = [[None] * rows for _ in range(cols + 1)]
    for i in range(cols + 1):
        a = i / cols - 0.5
        d_prev = None
        for j in range(rows):
            z = z_top - (z_top - z_bot) * j / (rows - 1)
            f = (z_top - z) / (z_top - z_bot)
            w = lerp(w_top, w_bot, f ** 0.7)
            u = u_c + a * w
            px, py, nx, ny, _, _ = cliff.frame(u)
            rock = cliff.disp(u, z) + 0.45
            d = rock if d_prev is None else max(d_prev + 0.03, rock)
            d_prev = d
            dd = d + out * math.sqrt(f) + 0.3 * (1.0 - (2 * a) ** 2) \
                + 0.18 * fbm(a * 7.0, z * 0.06, 0.0, 2, seed)
            grid[i][j] = (px + nx * dd, py + ny * dd, z)
    verts = [grid[i][j] for i in range(cols + 1) for j in range(rows)]
    faces = grid_faces(cols + 1, rows)
    px, py, nx, ny, tx, ty = cliff.frame(u_c)
    if ty * nx - tx * ny < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


# ---------------------------------------------------------------- PROPS (mesh data, unit size)
def boulder_mesh(seed, stretch=(1.3, 1.0, 0.75), subdiv=3):
    v, f = icosphere(subdiv)
    out = []
    for (x, y, z) in v:
        r = 1.0 + 0.14 * fbm(x * 1.3, y * 1.3, z * 1.3, 3, seed) + 0.03 * fbm(x * 4, y * 4, z * 4, 2, seed + 5)
        x, y, z = x * r, y * r, z * r
        if z < -0.35:                       # flat-ish bottom so it sits on the ground
            z = -0.35 + (z + 0.35) * 0.3
        out.append((x * stretch[0], y * stretch[1], z * stretch[2]))
    return out, f


def pine_mesh(seed, tiers=7, seg=9):
    """Height 1.0. Trunk + stacked drooping cones (clay blockout; Step 2B adds needle cards)."""
    rnd = random.Random(seed)
    verts, faces = [], []
    tr = 0.018                              # trunk
    base = len(verts)
    for k in range(6):
        a = k / 6 * math.tau
        verts += [(tr * math.cos(a), tr * math.sin(a), -0.05), (tr * math.cos(a), tr * math.sin(a), 0.35)]
    for k in range(6):
        k2 = (k + 1) % 6
        faces.append((base + 2 * k, base + 2 * k2, base + 2 * k2 + 1, base + 2 * k + 1))
    for t in range(tiers):
        f = t / (tiers - 1)
        zb = lerp(0.16, 0.80, f)
        hc = lerp(0.30, 0.22, f)
        r = lerp(0.26, 0.07, f) * rnd.uniform(0.9, 1.1)
        b0 = len(verts)
        for k in range(seg):
            a = k / seg * math.tau + rnd.uniform(-0.15, 0.15)
            rr = r * rnd.uniform(0.8, 1.15)
            verts.append((rr * math.cos(a), rr * math.sin(a), zb - rnd.uniform(0.0, 0.05)))
        verts.append((rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01), zb + hc))  # apex
        verts.append((0.0, 0.0, zb + 0.02))                                          # under-centre
        apex, cen = b0 + seg, b0 + seg + 1
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((b0 + k, b0 + k2, apex))
            faces.append((b0 + k2, b0 + k, cen))
    return verts, faces


def bush_mesh(seed):
    v, f = icosphere(2)
    out = []
    for (x, y, z) in v:
        r = 1.0 + 0.3 * fbm(x * 2.2, y * 2.2, z * 2.2, 3, seed)
        out.append((x * r, y * r, max(z * r * 0.65, -0.15)))
    return out, f


# ---------------------------------------------------------------- MOUNTAINS
PEAKS = [(P(172, 520), 170.0, 90.0), (P(45, 620), 235.0, 110.0), (P(-200, 600), 200.0, 140.0),
         (P(400, 700), 215.0, 160.0), (P(-450, 750), 225.0, 180.0)]


def mountains_mesh(step=15.0):
    xs = [-900 + i * step for i in range(int(1800 / step) + 1)]
    ys = [280 + j * step for j in range(int(720 / step) + 1)]
    verts = []
    for x in xs:
        for y in ys:
            h = -8.0
            for (px, py), H, W in PEAKS:
                r2 = ((x - px) / W) ** 2 + ((y - py) / W) ** 2
                h = max(h, H * math.exp(-(r2 ** 0.8)))
            ridge = (1.0 - abs(vnoise(x * 0.012, y * 0.012, 0.0, SEED + 50))) ** 2
            h += (22.0 * ridge + 12.0 * fbm(x * 0.03, y * 0.03, 0.0, 3, SEED + 51)) * smoothstep(0.0, 60.0, h)
            verts.append((x, y, h))
    return verts, grid_faces(len(xs), len(ys))


# ---------------------------------------------------------------- BUILDER (bpy or dry-run)
class Builder:
    def __init__(self):
        self.records = []        # dry-run: (name, world_verts, faces, collection)
        self.colls = {}
        self.dry = bpy is None

    def reset(self):
        if self.dry:
            return
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(bpy.data.collections):
            bpy.data.collections.remove(c)
        for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                       bpy.data.textures, bpy.data.node_groups, bpy.data.curves):
            for b in list(blocks):
                if b.users == 0:
                    blocks.remove(b)

    def collections(self, names):
        for n in names:
            if self.dry:
                self.colls[n] = n
            else:
                c = bpy.data.collections.new(n)
                bpy.context.scene.collection.children.link(c)
                self.colls[n] = c
        return self.colls

    def mesh(self, name, verts, faces, smooth=True):
        if self.dry:
            return (verts, faces)
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        if smooth:
            try:
                me.shade_smooth()
            except AttributeError:
                me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        return me

    def obj(self, name, mesh, coll, loc=(0, 0, 0), rot_z=0.0, scale=(1, 1, 1)):
        if self.dry:
            verts, faces = mesh
            c, s = math.cos(rot_z), math.sin(rot_z)
            wv = []
            for (x, y, z) in verts:
                x, y, z = x * scale[0], y * scale[1], z * scale[2]
                wv.append((x * c - y * s + loc[0], x * s + y * c + loc[1], z + loc[2]))
            self.records.append((name, wv, faces, coll))
            return None
        o = bpy.data.objects.new(name, mesh)
        self.colls[coll].objects.link(o)
        o.location = loc
        o.rotation_euler = (0.0, 0.0, rot_z)
        o.scale = scale
        return o


# ---------------------------------------------------------------- BUILD STEPS
def build_terrain(B, step=1.0):
    xs = [-90 + i * step for i in range(int(180 / step) + 1)]
    ys = [-30 + j * step for j in range(int(200 / step) + 1)]
    verts = [(x, y, terrain_h(x, y)) for x in xs for y in ys]
    B.obj("Terrain_Valley", B.mesh("Terrain_Valley", verts, grid_faces(len(xs), len(ys))), "Terrain")
    B.obj("Terrain_Mountains", B.mesh("Terrain_Mountains", *mountains_mesh()), "Terrain")


def build_cliffs(B, left, right, u_wf):
    for cl in (left, right):
        o = B.obj(cl.name, B.mesh(cl.name, *cl.mesh()), "Rocks")
        if o is not None:
            m = o.modifiers.new("Solidify", "SOLIDIFY")
            m.thickness = 12.0
            m.offset = -1.0
    B.obj("Waterfall_Main", B.mesh("Waterfall_Main",
          *waterfall_mesh(left, u_wf, WATERFALL_TOP, 10.0, 14.0, 2.5, SEED + 300, cols=24)), "Water")
    B.obj("Waterfall_Strand", B.mesh("Waterfall_Strand",
          *waterfall_mesh(left, u_wf - 7.5, 23.0, 1.0, 1.8, 1.4, SEED + 301, cols=6)), "Water")


def build_water(B):
    verts = [(x, y, 0.0) for x in (-45.0, 55.0) for y in (-30.0, 105.0)]
    B.obj("River_Surface", B.mesh("River_Surface", verts, [(0, 2, 3, 1)], smooth=False), "Water")


def build_rocks(B, rnd):
    hero = [  # (x, y, size, seed) -- big smooth boulders matched to the clay frame
        (-4.0, 21.0, 2.1, 1), (-7.5, 27.0, 2.0, 2), (8.0, 13.0, 1.8, 3), (-11.0, 16.0, 1.3, 4),
        (-14.0, 31.0, 1.6, 5), (5.0, 33.0, 1.0, 6),
        (14.0, 42.0, 3.3, 7), (20.0, 46.0, 2.8, 8), (26.0, 50.0, 3.8, 9), (9.0, 38.0, 2.2, 10),
        (31.0, 55.0, 3.0, 11), (36.0, 60.0, 3.5, 12), (17.0, 52.0, 2.1, 13), (42.0, 68.0, 3.6, 14),
        (25.0, 40.0, 2.0, 15), (3.0, 45.0, 1.8, 16), (34.0, 82.0, 3.0, 17), (48.0, 84.0, 3.2, 18),
    ]
    for i, (x, y, s, sd) in enumerate(hero):
        x = mx(x)
        st = (rnd.uniform(1.1, 1.5), rnd.uniform(0.9, 1.1), rnd.uniform(0.65, 0.85))
        me = B.mesh(f"Boulder_Hero_{i:02d}", *boulder_mesh(SEED + 400 + sd, st))
        B.obj(f"Boulder_Hero_{i:02d}", me, "Rocks", (x, y, terrain_h(x, y) - 0.2 * s),
              rnd.uniform(0, math.tau), (s, s, s))
    variants = [B.mesh(f"Boulder_Var_{k}", *boulder_mesh(SEED + 500 + k, (1.3, 1.0, 0.75 + 0.05 * k)))
                for k in range(6)]
    pebbles = [B.mesh(f"Pebble_Var_{k}", *boulder_mesh(SEED + 600 + k, (1.4, 1.0, 0.6), subdiv=1))
               for k in range(5)]
    n = 0
    for _ in range(400):                      # bank boulders along the river edges
        if n >= 30:
            break
        i = rnd.randrange(len(RIVER_PTS) - 1)
        (ax, ay), (bx, by) = RIVER_PTS[i], RIVER_PTS[i + 1]
        t = rnd.random()
        cx, cy = lerp(ax, bx, t), lerp(ay, by, t)
        if cy < 25:
            continue
        tx, ty = bx - ax, by - ay
        ln = math.hypot(tx, ty)
        nx, ny = -ty / ln, tx / ln
        side = rnd.choice((-1, 1))
        rw = lerp(RIVER_HALF_W[i], RIVER_HALF_W[i + 1], t)
        off = rw + rnd.uniform(-2.5, 3.0)
        x, y = cx + nx * off * side, cy + ny * off * side
        s = rnd.uniform(0.4, 1.5) * (1.2 if cy < 40 else 0.9)
        B.obj(f"Boulder_{n:03d}", rnd.choice(variants), "Rocks",
              (x, y, terrain_h(x, y) - 0.25 * s), rnd.uniform(0, math.tau), (s, s, s))
        n += 1
    for k in range(90):                        # riverbed pebbles / stones breaking the surface
        i = rnd.randrange(len(RIVER_PTS) - 1)
        (ax, ay), (bx, by) = RIVER_PTS[i], RIVER_PTS[i + 1]
        t = rnd.random()
        rw = lerp(RIVER_HALF_W[i], RIVER_HALF_W[i + 1], t)
        tx, ty = bx - ax, by - ay
        ln = math.hypot(tx, ty)
        off = rnd.uniform(-rw, rw)
        x, y = lerp(ax, bx, t) - ty / ln * off, lerp(ay, by, t) + tx / ln * off
        if y < 30:
            continue
        s = rnd.uniform(0.25, 0.7)
        B.obj(f"Pebble_{k:03d}", rnd.choice(pebbles), "Rocks",
              (x, y, max(terrain_h(x, y), -0.55) + 0.05), rnd.uniform(0, math.tau), (s, s, s))


def build_vegetation(B, rnd, left, right):
    pines = [B.mesh(f"Pine_Var_{k}", *pine_mesh(SEED + 700 + k), smooth=False) for k in range(4)]
    bushes = [B.mesh(f"Bush_Var_{k}", *bush_mesh(SEED + 800 + k)) for k in range(4)]

    def free_ground(x, y, margin):
        d, rw = river_info(x, y)
        if d < rw + margin:
            return False
        for cl in (left, right):
            sd, u = cl.signed_dist(x, y)
            if 0 < u < cl.length and sd < 9.0:
                return False
        return True

    def place_pine(name, x, y, z, h):
        B.obj(name, rnd.choice(pines), "Vegetation", (x, y, z - 0.3), rnd.uniform(0, math.tau),
              (h * rnd.uniform(0.9, 1.1), h * rnd.uniform(0.9, 1.1), h))

    n = 0
    for _ in range(3000):                      # conifer cluster on the left slope
        if n >= 20:
            break
        x, y = rnd.uniform(-55, -18), rnd.uniform(50, 88)
        x = mx(x)
        if not free_ground(x, y, 5.0):
            continue
        place_pine(f"Pine_Slope_{n:03d}", x, y, terrain_h(x, y), rnd.uniform(14, 22))
        n += 1
    hx, hy = P(-5, 52)                         # the single tall pine left of centre
    place_pine("Pine_Hero", hx, hy, terrain_h(hx, hy), 22.0)
    n = 0
    u_max = left.u_nearest(*P(20, 112))        # cliff-top trees only on the left / centre wall
    for _ in range(14):
        u = rnd.uniform(4, u_max)
        px, py, nx, ny, _, _ = left.frame(u)
        back = rnd.uniform(-11.0, -8.0) + left.disp(u, left.top(u))
        place_pine(f"Pine_Top_{n:03d}", px + nx * back, py + ny * back, left.top(u) + 0.2,
                   rnd.uniform(9, 15))
        n += 1
    n = 0
    for _ in range(3000):                      # bushes on the banks
        if n >= 45:
            break
        x, y = rnd.uniform(-35, 15), rnd.uniform(8, 75)
        x = mx(x)
        d, rw = river_info(x, y)
        if not (rw + 0.5 < d < rw + 9.0) or not free_ground(x, y, 0.5):
            continue
        s = rnd.uniform(0.5, 1.6)
        B.obj(f"Bush_{n:03d}", rnd.choice(bushes), "Vegetation", (x, y, terrain_h(x, y) - 0.1),
              rnd.uniform(0, math.tau), (s * 1.2, s, s))
        n += 1


# ---------------------------------------------------------------- BLENDER-ONLY SETUP
def sun_direction():
    az, el = math.radians(mx(SUN_AZIMUTH_DEG)), math.radians(SUN_ELEVATION_DEG)
    return (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))


def setup_camera_light_world(B):
    from mathutils import Vector
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("CAM_Main")
    cam_data.lens = CAM_LENS
    cam_data.clip_start = 0.1
    cam_data.clip_end = 3000.0
    cam = bpy.data.objects.new("CAM_Main", cam_data)
    B.colls["Camera"].objects.link(cam)
    cam.location = CAM_LOC
    cam.rotation_euler = (math.radians(90.0 + CAM_PITCH_DEG), 0.0, 0.0)
    scene.camera = cam

    sun_data = bpy.data.lights.new("LGT_Sun_Key", "SUN")
    sun_data.energy = 4.0
    sun_data.angle = math.radians(1.5)
    sun = bpy.data.objects.new("LGT_Sun_Key", sun_data)
    B.colls["Lights"].objects.link(sun)
    s = Vector(sun_direction())
    sun.rotation_euler = (-s).to_track_quat("-Z", "Y").to_euler()
    sun.location = (s * 60.0)

    world = bpy.data.worlds.new("WLD_Clay")
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        bg = nt.nodes.new("ShaderNodeBackground")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) or nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs["Color"].default_value = (0.62, 0.68, 0.76, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world


def make_clay_material():
    mat = bpy.data.materials.new("MAT_Clay")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    return mat


def setup_render():
    scene = bpy.context.scene
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = 1920, 1080
    r.resolution_percentage = PREVIEW_PERCENT
    r.fps = 24
    scene.frame_start, scene.frame_end = 1, 480
    scene.frame_set(1)
    scene.cycles.samples = PREVIEW_SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        pass


def frame_viewport_on_camera():
    try:
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].region_3d.view_perspective = "CAMERA"
                area.spaces[0].shading.type = "SOLID"
    except Exception:
        pass


# ---------------------------------------------------------------- MAIN
def main():
    rnd = random.Random(SEED)
    B = Builder()
    B.reset()
    B.collections(COLLECTIONS)
    left, right, u_wf = make_cliffs()
    build_terrain(B)
    build_cliffs(B, left, right, u_wf)
    build_water(B)
    build_rocks(B, rnd)
    build_vegetation(B, rnd, left, right)
    if B.dry:
        return B
    setup_camera_light_world(B)
    setup_render()
    if USE_CLAY_OVERRIDE:
        bpy.context.view_layer.material_override = make_clay_material()
    frame_viewport_on_camera()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if SAVE_BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTPUT_DIR, "waterfall_valley.blend"))
    if bpy.app.background and RENDER_STILL_IN_BACKGROUND:
        bpy.context.scene.render.filepath = os.path.join(OUTPUT_DIR, "step1_clay.png")
        bpy.ops.render.render(write_still=True)
    print("Waterfall Valley step 1 built:", len(bpy.data.objects), "objects")
    return B


if __name__ == "__main__":
    main()
