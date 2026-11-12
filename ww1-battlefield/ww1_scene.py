#!/usr/bin/env python3
"""
WW1 ruined-city battlefield -- fully procedural Blender scene (headless bpy).

    pip install bpy
    python3 ww1_scene.py --still 60        # build + save .blend + one test frame
    python3 ww1_scene.py                   # build + save .blend + render all frames
    python3 ww1_scene.py --no-render       # build + save .blend only

Environment only: no figures, no gore. No downloaded assets -- every mesh is
generated from code. Rendering is resumable: frames that already exist on disk
are skipped, so the script can simply be started again after an interruption.

Layout (metres, Z up):
    trench runs along X at y = 0, no-man's-land is +Y, the city starts at y ~ 72,
    the central street runs along +Y at x = 0, the low sun sits behind the city.
"""
import argparse
import math
import os
import random
import sys
import time

import bpy
from mathutils import Euler, Matrix, Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
FRAME_DIR = os.path.join(OUT_DIR, "frames")
BLEND_PATH = os.path.join(OUT_DIR, "ww1_scene.blend")

FPS, N_FRAMES = 24, 120
RES_X, RES_Y = 768, 328
SEED = 1917

TRENCH_HALF_W = 1.5          # 3 m wide
TRENCH_DEPTH = 1.5
TRENCH_X = (-40.0, 40.0)     # dressed (planked / sandbagged) stretch
FOG_DENSITY = 0.0075

rng = random.Random(SEED)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(scale))


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


_UNIT_CUBE = [Vector(v) for v in ((-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
                                  (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5))]
_CUBE_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
_ELL_CACHE = {}


def _ellipsoid_template(e, nu, nv):
    key = (e, nu, nv)
    if key in _ELL_CACHE:
        return _ELL_CACHE[key]

    def sp(v):
        return math.copysign(abs(v) ** e, v)

    verts, faces = [Vector((0, 0, -1))], []
    for j in range(1, nv):
        phi = -math.pi / 2 + math.pi * j / nv
        for i in range(nu):
            th = 2 * math.pi * i / nu
            verts.append(Vector((sp(math.cos(phi)) * sp(math.cos(th)),
                                 sp(math.cos(phi)) * sp(math.sin(th)), sp(math.sin(phi)))))
    verts.append(Vector((0, 0, 1)))
    top = len(verts) - 1
    for i in range(nu):
        faces.append((0, 1 + (i + 1) % nu, 1 + i))
        faces.append((top, top - nu + i, top - nu + (i + 1) % nu))
    for j in range(nv - 2):
        a, b = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            k = (i + 1) % nu
            faces.append((a + i, a + k, b + k, b + i))
    _ELL_CACHE[key] = (verts, faces)
    return _ELL_CACHE[key]


class Builder:
    """Accumulates many primitives into ONE mesh (fast to build, fast to render)."""

    def __init__(self):
        self.v, self.f, self.c = [], [], []

    def _add(self, verts, faces, col):
        o = len(self.v)
        self.v.extend(verts)
        self.f.extend(tuple(o + i for i in f) for f in faces)
        if isinstance(col, (int, float)):
            col = (col, col, col)
        self.c.extend([col] * len(verts))

    def box_m(self, mat, col=1.0):
        self._add([mat @ v for v in _UNIT_CUBE], _CUBE_FACES, col)

    def box(self, loc, size, rot=(0, 0, 0), col=1.0):
        self.box_m(M(loc, rot, size), col)

    def ellipsoid(self, mat, col=1.0, e=1.0, nu=10, nv=6, jitter=0.0):
        tv, tf = _ellipsoid_template(e, nu, nv)
        if jitter:
            tv = [v * (1 + rng.uniform(-jitter, jitter)) for v in tv]
        self._add([mat @ v for v in tv], tf, col)

    def cyl(self, p0, p1, r0, r1=None, segs=8, col=1.0, mat=None, cap=True):
        r1 = r0 if r1 is None else r1
        p0, p1 = Vector(p0), Vector(p1)
        q = (p1 - p0).to_track_quat('Z', 'Y')
        ring = [(math.cos(2 * math.pi * i / segs), math.sin(2 * math.pi * i / segs)) for i in range(segs)]
        vs = [p0 + q @ Vector((c * r0, s * r0, 0)) for c, s in ring] + \
             [p1 + q @ Vector((c * r1, s * r1, 0)) for c, s in ring]
        if mat is not None:
            vs = [mat @ v for v in vs]
        fs = [(i, (i + 1) % segs, segs + (i + 1) % segs, segs + i) for i in range(segs)]
        if cap:
            fs.append(tuple(range(segs - 1, -1, -1)))
            fs.append(tuple(range(segs, 2 * segs)))
        self._add(vs, fs, col)

    def prism(self, profile, y0, y1, mat=None, col=1.0):
        """Extrude an (x, z) polygon along Y."""
        n = len(profile)
        vs = [Vector((x, y0, z)) for x, z in profile] + [Vector((x, y1, z)) for x, z in profile]
        if mat is not None:
            vs = [mat @ v for v in vs]
        fs = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        fs.append(tuple(range(n)))
        fs.append(tuple(range(2 * n - 1, n - 1, -1)))
        self._add(vs, fs, col)

    def lathe(self, profile, mat, segs=16, col=1.0):
        """Surface of revolution from (radius, z) pairs."""
        vs, fs = [], []
        for r, z in profile:
            for i in range(segs):
                a = 2 * math.pi * i / segs
                vs.append(mat @ Vector((r * math.cos(a), r * math.sin(a), z)))
        for j in range(len(profile) - 1):
            for i in range(segs):
                k = (i + 1) % segs
                fs.append((j * segs + i, j * segs + k, (j + 1) * segs + k, (j + 1) * segs + i))
        self._add(vs, fs, col)

    def build(self, name, material, smooth=False, matrix=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.v], [], self.f)
        attr = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
        flat = []
        for c in self.c:
            flat.extend((c[0], c[1], c[2], 1.0))
        attr.data.foreach_set("color", flat)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.materials.append(material)
        me.update()
        ob = link(bpy.data.objects.new(name, me))
        if matrix is not None:
            ob.matrix_world = matrix
        return ob


# --------------------------------------------------------------------------- #
# shader helpers
# --------------------------------------------------------------------------- #
def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    return mat, nt


class NT:
    """Tiny expression helper around a node tree."""

    def __init__(self, nt):
        self.nt = nt

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def _set(self, sock, val):
        if val is None:
            return
        if hasattr(val, "is_output") or hasattr(val, "links"):
            self.nt.links.new(val, sock)
        else:
            sock.default_value = val

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        self._set(n.inputs[2], c)
        return n.outputs[0]

    def vmath(self, op, a, b=None, out=0):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        return n.outputs[out]

    def mix(self, fac, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        self._set(n.inputs[0], fac)
        self._set(n.inputs[6], a if not isinstance(a, tuple) else (*a, 1.0)[:4])
        self._set(n.inputs[7], b if not isinstance(b, tuple) else (*b, 1.0)[:4])
        return n.outputs[2]

    def smooth(self, val, lo, hi, to0=0.0, to1=1.0):
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self._set(n.inputs[0], val)
        for i, v in enumerate((lo, hi, to0, to1), start=1):
            n.inputs[i].default_value = v
        return n.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55):
        n = self.node('ShaderNodeTexNoise')
        self._set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        return n.outputs[0]

    def bump(self, height, strength=0.5, distance=0.1):
        n = self.node('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = distance
        self._set(n.inputs['Height'], height)
        return n.outputs[0]

    def principled(self, color, rough, metallic=0.0, normal=None):
        p = self.node('ShaderNodeBsdfPrincipled')
        self._set(p.inputs['Base Color'], color if not isinstance(color, tuple) else (*color, 1.0))
        self._set(p.inputs['Roughness'], rough)
        self._set(p.inputs['Metallic'], metallic)
        if normal is not None:
            self._set(p.inputs['Normal'], normal)
        out = self.node('ShaderNodeOutputMaterial')
        self.nt.links.new(p.outputs[0], out.inputs['Surface'])
        return p

    def objco(self):
        return self.node('ShaderNodeTexCoord').outputs['Object']


def mat_generic(name, base, rough=0.85, metallic=0.0, nscale=3.0, bump=0.4, bump_dist=0.03,
                var=0.5, tint=None, tint_scale=0.6):
    """Vertex colour 'Col' x base colour x noise variation, with noise bump."""
    mat, nt = new_material(name)
    t = NT(nt)
    co = t.objco()
    col = t.node('ShaderNodeAttribute', attribute_name='Col').outputs['Color']
    n = t.noise(co, nscale, 6.0)
    c = t.mix(1.0, col, (*base, 1.0), 'MULTIPLY')
    shade = t.math('ADD', t.math('MULTIPLY', n, var), 1.0 - var * 0.5)
    c = t.mix(1.0, c, t.node('ShaderNodeCombineColor').outputs[0], 'MULTIPLY') if False else \
        t.vmath('SCALE', c, None)
    # VectorMath SCALE uses the 'Scale' socket (index 3)
    nt.links.new(shade, c.node.inputs[3])
    if tint is not None:
        m = t.smooth(t.noise(co, tint_scale, 5.0), 0.45, 0.7)
        c = t.mix(m, c, (*tint, 1.0))
    t.principled(c, rough, metallic, t.bump(n, bump, bump_dist))
    return mat


def mat_mud():
    mat, nt = new_material("Mud")
    t = NT(nt)
    co = t.objco()
    big = t.noise(co, 0.06, 4.0)
    mid = t.noise(co, 0.45, 5.0)
    fine = t.noise(co, 2.6, 8.0, 0.65)
    wet = t.smooth(t.math('ADD', big, t.math('MULTIPLY', mid, 0.35)), 0.70, 0.78)
    col = t.mix(fine, (0.050, 0.036, 0.024, 1), (0.125, 0.092, 0.058, 1))
    col = t.mix(t.smooth(mid, 0.35, 0.75), col, (0.085, 0.070, 0.052, 1))
    col = t.mix(wet, col, (0.022, 0.017, 0.013, 1))
    rough = t.math('ADD', t.smooth(wet, 0.0, 1.0, 0.82, 0.05), t.math('MULTIPLY', fine, 0.08))
    h = t.math('ADD', t.math('MULTIPLY', fine, 0.6), t.math('MULTIPLY', mid, 0.9))
    h = t.math('MULTIPLY', h, t.smooth(wet, 0.0, 1.0, 1.0, 0.05))
    t.principled(col, rough, 0.0, t.bump(h, 0.75, 0.12))
    return mat


def mat_water():
    mat, nt = new_material("PuddleWater")
    t = NT(nt)
    n = t.noise(t.objco(), 1.2, 3.0)
    t.principled((0.018, 0.014, 0.010), 0.02, 0.0, t.bump(n, 0.03, 0.02))
    return mat


def mat_building():
    """Object colour drives plaster/brick tone; alpha of object colour = brick amount."""
    mat, nt = new_material("RuinWall")
    t = NT(nt)
    co = t.objco()
    info = t.node('ShaderNodeObjectInfo')
    sep = t.node('ShaderNodeSeparateXYZ')
    nt.links.new(co, sep.inputs[0])
    comb = t.node('ShaderNodeCombineXYZ')            # (x + y, z) -> brick UV on vertical walls
    nt.links.new(t.math('ADD', sep.outputs[0], sep.outputs[1]), comb.inputs[0])
    nt.links.new(sep.outputs[2], comb.inputs[1])
    brick = t.node('ShaderNodeTexBrick')
    nt.links.new(comb.outputs[0], brick.inputs['Vector'])
    brick.inputs['Color1'].default_value = (0.75, 0.75, 0.75, 1)
    brick.inputs['Color2'].default_value = (1.0, 1.0, 1.0, 1)
    brick.inputs['Mortar'].default_value = (1.5, 1.45, 1.35, 1)
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.012
    brick.inputs['Brick Width'].default_value = 0.42
    brick.inputs['Row Height'].default_value = 0.14
    c = t.mix(info.outputs['Alpha'], info.outputs['Color'],
              t.mix(1.0, info.outputs['Color'], brick.outputs['Color'], 'MULTIPLY'))
    # blotchy plaster / grime
    grime = t.smooth(t.noise(co, 0.22, 6.0, 0.65), 0.38, 0.72)
    c = t.mix(t.math('MULTIPLY', grime, 0.62), c, (0.035, 0.030, 0.027, 1))
    # vertical soot streaks
    scomb = t.node('ShaderNodeCombineXYZ')
    nt.links.new(t.math('MULTIPLY', t.math('ADD', sep.outputs[0], sep.outputs[1]), 1.4), scomb.inputs[0])
    nt.links.new(t.math('MULTIPLY', sep.outputs[2], 0.12), scomb.inputs[1])
    streak = t.smooth(t.noise(scomb.outputs[0], 1.0, 4.0), 0.5, 0.75)
    c = t.mix(t.math('MULTIPLY', streak, 0.5), c, (0.02, 0.018, 0.016, 1))
    # splash-back dirt near the ground
    low = t.smooth(sep.outputs[2], 0.0, 3.0, 0.55, 0.0)
    c = t.mix(low, c, (0.05, 0.04, 0.03, 1))
    h = t.math('ADD', t.math('MULTIPLY', brick.outputs['Fac'], -0.6), t.noise(co, 1.5, 6.0))
    t.principled(c, 0.92, 0.0, t.bump(h, 0.35, 0.05))
    return mat


def mat_flat(name, color, rough=0.9, metallic=0.0):
    mat, nt = new_material(name)
    NT(nt).principled(color, rough, metallic)
    return mat


def mat_smoke(name, H, r0, r1, lean, density):
    """Volume: noise x soft radial edge x height fade, in the plume's local space."""
    mat, nt = new_material(name)
    t = NT(nt)
    co = t.objco()
    sep = t.node('ShaderNodeSeparateXYZ')
    nt.links.new(co, sep.inputs[0])
    x, y, z = sep.outputs
    zn = t.math('DIVIDE', z, H, clamp=True)
    cx = t.math('MULTIPLY', t.math('POWER', zn, 1.6), lean * H)
    R = t.math('ADD', t.math('MULTIPLY', t.math('POWER', zn, 0.7), r1 - r0), r0)
    dx = t.math('SUBTRACT', x, cx)
    rn = t.math('DIVIDE', t.math('SQRT', t.math('ADD', t.math('MULTIPLY', dx, dx),
                                                 t.math('MULTIPLY', y, y))), R)
    stretch = t.node('ShaderNodeCombineXYZ')
    nt.links.new(dx, stretch.inputs[0])
    nt.links.new(y, stretch.inputs[1])
    nt.links.new(t.math('MULTIPLY', z, 0.55), stretch.inputs[2])
    billow = t.noise(stretch.outputs[0], 0.07, 3.0)
    detail = t.noise(stretch.outputs[0], 0.11, 3.0, 0.5)
    rn = t.math('ADD', rn, t.math('MULTIPLY', t.math('SUBTRACT', billow, 0.5), 0.9))
    edge = t.smooth(rn, 0.15, 0.95, 1.0, 0.0)                       # soft edges
    body = t.smooth(detail, 0.22, 0.62)
    top = t.smooth(zn, 0.62, 1.0, 1.0, 0.0)
    base = t.smooth(zn, 0.0, 0.5, 2.6, 1.0)
    d = t.math('MULTIPLY', t.math('MULTIPLY', edge, body), t.math('MULTIPLY', top, base))
    d = t.math('MULTIPLY', d, density)
    vol = t.node('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.030, 0.026, 0.023, 1)
    vol.inputs['Anisotropy'].default_value = 0.3
    nt.links.new(d, vol.inputs['Density'])
    out = t.node('ShaderNodeOutputMaterial')
    nt.links.new(vol.outputs[0], out.inputs['Volume'])
    return mat


# --------------------------------------------------------------------------- #
# 1. ground: mud, noise bumps, craters
# --------------------------------------------------------------------------- #
CRATERS = []          # (x, y, radius, depth)
SUN_AZ, SUN_EL = math.radians(9.0), math.radians(8.0)     # azimuth measured from +Y toward +X
SUN_DIR = Vector((math.sin(SUN_AZ) * math.cos(SUN_EL), math.cos(SUN_AZ) * math.cos(SUN_EL),
                  math.sin(SUN_EL)))


def make_craters():
    def ok(x, y, r):
        if abs(y) - r * 1.7 < 4.2:                 # keep the trench line intact
            return False
        return all((x - cx) ** 2 + (y - cy) ** 2 > (0.75 * (r + cr)) ** 2 for cx, cy, cr, _ in CRATERS)

    tries = 0
    while len(CRATERS) < 40 and tries < 4000:      # no-man's-land
        tries += 1
        x, y, r = rng.uniform(-62, 62), rng.uniform(7, 69), rng.uniform(1.4, 5.2)
        if ok(x, y, r):
            CRATERS.append((x, y, r, r * rng.uniform(0.28, 0.42)))
    while len(CRATERS) < 48 and tries < 8000:      # behind the trench and in the street
        tries += 1
        if rng.random() < 0.6:
            x, y, r = rng.uniform(-50, 50), rng.uniform(-23, -8), rng.uniform(1.5, 4.0)
        else:
            x, y, r = rng.uniform(-5, 5), rng.uniform(76, 93), rng.uniform(1.2, 2.4)
        if ok(x, y, r):
            CRATERS.append((x, y, r, r * rng.uniform(0.25, 0.38)))


def ground_z(x, y):
    """Analytic terrain height -- used for the mesh AND for placing props."""
    if abs(y) <= TRENCH_HALF_W + 1e-6:
        return -TRENCH_DEPTH
    edge = min(1.0, max(0.0, (abs(y) - 1.6) / 3.0))        # flatten next to the trench
    city = 0.3 if y > 71 else 1.0
    border = min(1.0, max(0.0, (80 - abs(x)) / 8.0)) * min(1.0, max(0.0, (95 - y) / 8.0)) \
        * min(1.0, max(0.0, (y + 25) / 6.0))
    z = 0.22 * noise.noise(Vector((x * 0.07, y * 0.07, 3.1))) \
        + 0.07 * noise.noise(Vector((x * 0.45, y * 0.45, 7.7))) \
        + 0.02 * noise.noise(Vector((x * 1.7, y * 1.7, 1.3)))
    z *= edge * city * border
    for cx, cy, r, d in CRATERS:
        dx, dy = x - cx, y - cy
        if abs(dx) > 2.2 * r or abs(dy) > 2.2 * r:
            continue
        q = math.sqrt(dx * dx + dy * dy) / r
        if q < 1.0:
            z -= d * (1.0 - q * q)
        z += 0.30 * d * math.exp(-((q - 1.0) / 0.32) ** 2)   # raised rim
    return z


def build_ground(mud):
    step = 0.6
    xs = [-80 + i * step for i in range(int(160 / step) + 1)]
    ys = [-25 + i * step for i in range(int(120 / step) + 1)]
    special = [-1.56, -TRENCH_HALF_W, TRENCH_HALF_W, 1.56]   # crisp vertical trench walls
    ys = sorted([y for y in ys if all(abs(y - s) > 0.25 for s in special)] + special)
    nx, ny = len(xs), len(ys)
    verts = [(x, y, ground_z(x, y)) for y in ys for x in xs]
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(ny - 1) for i in range(nx - 1)]
    me = bpy.data.meshes.new("Ground")
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.materials.append(mud)
    link(bpy.data.objects.new("Ground", me))

    # far apron so the mud runs to the horizon
    me2 = bpy.data.meshes.new("GroundFar")
    s = 2500
    me2.from_pydata([(-s, -s, -0.1), (s, -s, -0.1), (s, s, -0.1), (-s, s, -0.1)], [], [(0, 1, 2, 3)])
    me2.materials.append(mud)
    link(bpy.data.objects.new("GroundFar", me2))

    # standing water in the bigger craters
    water = Builder()
    for cx, cy, r, d in CRATERS:
        if r < 2.0:
            continue
        zc = ground_z(cx, cy) + d * 0.38
        pr = r * 0.62
        segs = 20
        o = len(water.v)
        water.v.extend(Vector((cx + pr * math.cos(2 * math.pi * i / segs),
                               cy + pr * math.sin(2 * math.pi * i / segs), zc)) for i in range(segs))
        water.f.append(tuple(range(o, o + segs)))
        water.c.extend([(1, 1, 1)] * segs)
    water.build("CraterWater", mat_water())


# --------------------------------------------------------------------------- #
# 2 + 3. trench, sandbags, props
# --------------------------------------------------------------------------- #
def sandbag(b, x, y, z, yaw=0.0, tilt=0.0, roll=0.0, scale=1.0):
    tone = rng.uniform(0.62, 1.12)
    col = (tone, tone * rng.uniform(0.92, 1.0), tone * rng.uniform(0.8, 0.95))
    b.ellipsoid(M((x, y, z), (roll, tilt, yaw),
                  (0.32 * scale * rng.uniform(0.93, 1.07), 0.18 * scale, 0.112 * scale)),
                col, e=0.62, nu=10, nv=6)


def build_trench(mats):
    wood, bags, crate_b, metal = Builder(), Builder(), Builder(), Builder()
    x0, x1 = TRENCH_X

    # plank revetment on both walls
    for side in (-1, 1):
        ywall = side * (TRENCH_HALF_W + 0.03)
        for row in range(6):
            zc = -TRENCH_DEPTH + 0.125 + row * 0.25
            x = x0
            while x < x1:
                L = rng.uniform(2.4, 4.2)
                tone = rng.uniform(0.55, 1.15)
                wood.box((x + L / 2, ywall + rng.uniform(-0.012, 0.012), zc + rng.uniform(-0.01, 0.01)),
                         (L - 0.03, 0.05, 0.235), (rng.uniform(-0.03, 0.03), 0, rng.uniform(-0.004, 0.004)),
                         (tone, tone * 0.93, tone * 0.85))
                x += L
        x = x0
        while x <= x1:                                   # uprights
            tone = rng.uniform(0.5, 0.9)
            wood.box((x, side * (TRENCH_HALF_W - 0.05), -TRENCH_DEPTH / 2 + 0.08),
                     (0.11, 0.11, TRENCH_DEPTH + 0.2), (side * rng.uniform(-0.03, 0.02), rng.uniform(-0.02, 0.02), 0),
                     (tone, tone * 0.92, tone * 0.84))
            x += 2.0

    # duckboards
    zf = -TRENCH_DEPTH
    for ry in (-0.42, 0.42):
        wood.box(((x0 + x1) / 2, ry, zf + 0.045), (x1 - x0, 0.09, 0.09), col=0.6)
    x = x0 + 0.1
    while x < x1:
        if rng.random() > 0.05:
            tone = rng.uniform(0.6, 1.2)
            wood.box((x, rng.uniform(-0.03, 0.03), zf + 0.105), (0.13, 1.15 + rng.uniform(-0.08, 0.08), 0.028),
                     (0, rng.uniform(-0.03, 0.03), rng.uniform(-0.05, 0.05)), (tone, tone * 0.94, tone * 0.86))
        x += 0.2

    # ladder against the front wall
    for lx in (3.8, 4.25):
        wood.cyl((lx, 0.75, zf), (lx, 1.42, 0.45), 0.035, segs=6, col=0.8)
    for k in range(6):
        f = (k + 0.6) / 6.5
        wood.cyl((3.8, 0.75 + 0.67 * f, zf + 1.95 * f), (4.25, 0.75 + 0.67 * f, zf + 1.95 * f), 0.022, segs=6, col=0.9)

    # sandbag parapet (front, 4 layers) and lower parados (rear, 2 layers)
    def wall(rows_per_layer, z_base):
        for layer, rows in enumerate(rows_per_layer):
            z = z_base + 0.105 + layer * 0.2
            for ry in rows:
                x = x0 + (0.31 if layer % 2 else 0.0) + rng.uniform(0, 0.1)
                while x < x1:
                    top = layer == len(rows_per_layer) - 1
                    if not (top and rng.random() < 0.1):
                        sandbag(bags, x, ry + rng.uniform(-0.035, 0.035), z + rng.uniform(-0.012, 0.012),
                                rng.uniform(-0.09, 0.09), rng.uniform(-0.04, 0.04), rng.uniform(-0.06, 0.06))
                    x += 0.61 + rng.uniform(-0.02, 0.03)

    wall([(1.86, 2.2, 2.54, 2.88), (1.98, 2.32, 2.66), (2.08, 2.42, 2.72), (2.22, 2.54)], 0.0)
    wall([(-1.86, -2.2, -2.54), (-2.0, -2.34)], 0.0)

    # loose sandbags lying around
    for _ in range(46):
        x = rng.uniform(-22, 22)
        y = rng.choice((rng.uniform(3.2, 6.5), rng.uniform(-5.5, -2.9), rng.uniform(3.2, 4.2)))
        sandbag(bags, x, y, ground_z(x, y) + 0.09, rng.uniform(0, 3.14), rng.uniform(-0.25, 0.25),
                rng.uniform(-0.2, 0.2))
    for _ in range(14):                                   # a few fallen onto the duckboards
        sandbag(bags, rng.uniform(-18, 18), rng.uniform(-1.2, 1.2), zf + 0.23, rng.uniform(0, 3.14),
                rng.uniform(-0.2, 0.2))

    # ammo crates
    def crate(x, y, z, yaw=0.0, s=(0.85, 0.45, 0.36)):
        tone = rng.uniform(0.75, 1.15)
        m = M((x, y, z + s[2] / 2), (0, 0, yaw))
        crate_b.box_m(m @ M(scale=s), (tone, tone * 0.95, tone * 0.8))
        for sx in (-0.3, 0.3):                            # battens
            crate_b.box_m(m @ M((sx * s[0], 0, 0), scale=(0.06, s[1] + 0.03, s[2] + 0.03)), tone * 0.55)
        crate_b.box_m(m @ M((0, 0, s[2] / 2), scale=(s[0] + 0.02, s[1] + 0.02, 0.025)), tone * 0.8)

    for (cx, cy, n) in ((1.4, -1.0, 3), (2.35, -1.02, 2), (3.3, -0.98, 3), (6.2, -1.0, 1), (-9.5, 0.95, 2)):
        for k in range(n):
            crate(cx + rng.uniform(-0.04, 0.04), cy + rng.uniform(-0.03, 0.03), zf + 0.02 + k * 0.385,
                  rng.uniform(-0.08, 0.08))
    crate(4.6, -2.95, 0.02, 0.3)                          # on the rear lip
    crate(4.5, -2.9, 0.405, 0.1)
    crate(5.6, -3.05, 0.02, -0.2)
    crate(0.4, 3.9, ground_z(0.4, 3.9) - 0.03, 0.5)       # one thrown out in front

    # Brodie helmet resting on the parapet
    prof = [(0.0, 0.125), (0.05, 0.122), (0.095, 0.105), (0.13, 0.07), (0.148, 0.03), (0.152, 0.008),
            (0.19, 0.0), (0.2, -0.006), (0.19, -0.012), (0.146, -0.005), (0.14, 0.03)]
    metal.lathe(prof[::-1], M((-0.45, 2.36, 0.845), (0.2, -0.16, 0.5)), segs=22, col=(1, 1, 1))

    wood.build("TrenchWood", mats['wood'])
    bags.build("Sandbags", mats['burlap'], smooth=True)
    crate_b.build("AmmoCrates", mats['crate'])
    metal.build("Helmet", mats['helmet'], smooth=True)


# --------------------------------------------------------------------------- #
# 4. no-man's-land: wire, trees, rubble
# --------------------------------------------------------------------------- #
def build_wire(mats):
    posts = Builder()
    cu = bpy.data.curves.new("BarbedWire", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.014
    cu.bevel_resolution = 0
    cu.materials.append(mats['wire'])

    def spline(pts):
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for p, co in zip(sp.points, pts):
            p.co = (co[0], co[1], co[2], 1.0)

    for line_y in (10.5, 16.5):
        segments = [(-46.0, -5.5), (6.0, 46.0)]           # gap where the tank drove through
        for sx0, sx1 in segments:
            tops = []
            x = sx0
            while x <= sx1:
                y = line_y + rng.uniform(-0.35, 0.35)
                z = ground_z(x, y)
                lean = (rng.uniform(-0.16, 0.16), rng.uniform(-0.16, 0.16))
                top = Vector((x + lean[0], y + lean[1], z + rng.uniform(1.0, 1.3)))
                posts.cyl((x, y, z - 0.3), top, 0.04, 0.03, segs=6, col=rng.uniform(0.5, 1.0))
                tops.append(top)
                x += rng.uniform(2.2, 2.9)
            # straight strands with sag
            for h in (0.0, -0.4, -0.8):
                pts = []
                for a, b in zip(tops, tops[1:]):
                    for k in range(5):
                        f = k / 5
                        p = a.lerp(b, f)
                        pts.append((p.x, p.y, p.z + h - 0.12 * math.sin(math.pi * f)))
                pts.append((tops[-1].x, tops[-1].y, tops[-1].z + h))
                spline(pts)
            # concertina coil
            pts = []
            n = int((sx1 - sx0) / 0.55 * 14)
            ph = rng.uniform(0, 6.28)
            for i in range(n + 1):
                x = sx0 + (sx1 - sx0) * i / n
                a = 2 * math.pi * i / 14 + ph
                rr = 0.42 + 0.08 * math.sin(i * 0.031 + ph) + rng.uniform(-0.015, 0.015)
                yc = line_y + 0.55 + 0.25 * math.sin(x * 0.21 + ph)
                pts.append((x, yc + rr * math.cos(a), ground_z(x, yc) + 0.46 + rr * math.sin(a)))
            spline(pts)
    posts.build("WirePosts", mats['wood'])
    link(bpy.data.objects.new("BarbedWire", cu))


def build_trees(mats):
    b = Builder()
    spots = [(-13.5, 9.0), (9.5, 13.5), (-7.5, 23.0), (15.5, 26.0), (-22.0, 31.0), (10.0, 45.0),
             (-12.5, 50.0), (23.0, 57.0)]
    for tx, ty in spots:
        p = Vector((tx, ty, ground_z(tx, ty) - 0.3))
        d = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 1)).normalized()
        nseg = rng.randint(5, 8)
        r = rng.uniform(0.2, 0.3)
        b.cyl(p, p + Vector((0, 0, 0.5)), r * 1.5, r, segs=9, cap=False)     # root flare
        p = p + Vector((0, 0, 0.45))
        for s in range(nseg):
            L = rng.uniform(0.8, 1.4)
            d = (d + Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 0))).normalized()
            r1 = r * rng.uniform(0.8, 0.92)
            q = p + d * L
            b.cyl(p, q, r, r1, segs=9, cap=(s == nseg - 1), col=rng.uniform(0.6, 1.2))
            if s >= 1 and rng.random() < 0.7:                                 # broken branch
                bd = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.1, 0.9))).normalized()
                bp, br = p.lerp(q, rng.random()), r1 * rng.uniform(0.35, 0.6)
                for _ in range(rng.randint(1, 3)):
                    bl = rng.uniform(0.4, 1.1)
                    bq = bp + bd * bl
                    b.cyl(bp, bq, br, br * 0.7, segs=6, col=rng.uniform(0.6, 1.2))
                    bp, br = bq, br * 0.7
                    bd = (bd + Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4),
                                       rng.uniform(-0.3, 0.3)))).normalized()
            p, r = q, r1
        for _ in range(3):                                                    # splintered top
            sd = (d + Vector((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), 0))).normalized()
            b.cyl(p, p + sd * rng.uniform(0.25, 0.7), r * 0.5, 0.01, segs=5)
    b.build("DeadTrees", mats['char'])


BRICK_TONES = [(0.17, 0.085, 0.06), (0.13, 0.07, 0.055), (0.19, 0.18, 0.17), (0.12, 0.115, 0.11),
               (0.24, 0.20, 0.15), (0.08, 0.07, 0.065)]


def rubble_pile(b, cx, cy, radius, height, zfn=ground_z, n=None):
    z0 = zfn(cx, cy)
    for _ in range(rng.randint(2, 4)):                                         # mound
        ox, oy = rng.uniform(-0.4, 0.4) * radius, rng.uniform(-0.4, 0.4) * radius
        t = rng.choice(BRICK_TONES)
        b.ellipsoid(M((cx + ox, cy + oy, z0), (0, 0, rng.uniform(0, 3.14)),
                      (radius * rng.uniform(0.5, 0.9), radius * rng.uniform(0.4, 0.8), height * rng.uniform(0.5, 1))),
                    tuple(c * 0.8 for c in t), e=1.0, nu=10, nv=6, jitter=0.16)
    for _ in range(n if n is not None else int(14 + radius * 7)):              # blocks, bricks, beams
        a, q = rng.uniform(0, 6.283), abs(rng.gauss(0, 0.55))
        x, y = cx + math.cos(a) * q * radius, cy + math.sin(a) * q * radius
        z = zfn(x, y) + height * max(0.0, 1 - q) * rng.uniform(0.4, 1.0)
        kind = rng.random()
        if kind < 0.12:
            size, t = (rng.uniform(1.2, 2.8), 0.16, 0.18), (0.1, 0.07, 0.05)   # charred beam
        elif kind < 0.5:
            size, t = (rng.uniform(0.4, 1.3), rng.uniform(0.3, 0.9), rng.uniform(0.2, 0.6)), rng.choice(BRICK_TONES)
        else:
            size, t = (0.24, 0.115, 0.07), rng.choice(BRICK_TONES[:2])
            size = tuple(v * rng.uniform(1, 2.2) for v in size)
        s = rng.uniform(0.7, 1.25)
        b.box((x, y, z + size[2] * 0.3), size, (rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), rng.uniform(0, 3.14)),
              tuple(c * s for c in t))


def build_nomansland_rubble(mats):
    b = Builder()
    for cx, cy, r, h in ((-9.0, 28.0, 2.6, 0.9), (8.0, 52.0, 3.0, 1.1), (-4.5, 62.0, 2.4, 0.9),
                         (20.0, 38.0, 2.8, 1.0), (-19.0, 44.0, 3.2, 1.2), (5.5, 21.0, 1.8, 0.6),
                         (-27.0, 60.0, 3.5, 1.3), (30.0, 64.0, 3.5, 1.4), (-2.0, 8.2, 1.3, 0.4),
                         (13.0, 66.0, 3.0, 1.2), (-14.0, 67.0, 3.2, 1.3)):
        rubble_pile(b, cx, cy, r, h)
    b.build("FieldRubble", mats['rubble'])


# --------------------------------------------------------------------------- #
# 5. Mark IV-style rhomboid tank
# --------------------------------------------------------------------------- #
def build_tank(name, mats, world):
    b = Builder()
    prof = [(-3.95, 0.55), (-3.3, 0.06), (-2.6, 0.0), (2.0, 0.0), (2.9, 0.35), (4.0, 1.75), (3.7, 2.3),
            (2.7, 2.48), (-2.4, 2.22), (-3.6, 1.75), (-3.98, 1.2)]
    hull = [(-3.5, 0.55), (2.3, 0.45), (3.35, 1.7), (2.5, 2.2), (-2.5, 2.0), (-3.5, 1.3)]
    b.prism(hull, -1.3, 1.3, col=0.95)
    for side in (-1, 1):
        ya, yb = sorted((side * 1.3, side * 1.82))
        b.prism([(x * 0.985, 0.03 + z * 0.975) for x, z in prof], ya, yb, col=0.9)        # track frame
        yc = side * 1.56
        n = len(prof)
        for i in range(n):                                                               # track plates
            (ax, az), (bx, bz) = prof[i], prof[(i + 1) % n]
            L = math.hypot(bx - ax, bz - az)
            ang = math.atan2(bz - az, bx - ax)
            k = max(1, int(L / 0.19))
            for j in range(k):
                f = (j + 0.5) / k
                b.box((ax + (bx - ax) * f, yc, az + (bz - az) * f), (L / k * 0.86, 0.56, 0.07), (0, -ang, 0),
                      rng.uniform(0.45, 0.75))
        # sponson with a 6-pounder
        sy = side * 2.2
        b.box((0.15, sy, 1.12), (2.2, 0.78, 1.05), col=1.0)
        b.box((1.35, sy - side * 0.12, 1.12), (0.9, 0.62, 1.05), (0, 0, side * 0.5), col=0.95)
        b.box((-1.05, sy - side * 0.12, 1.12), (0.7, 0.62, 1.05), (0, 0, -side * 0.5), col=0.9)
        b.cyl((1.5, sy, 1.2), (1.75, sy + side * 0.05, 1.2), 0.2, 0.17, segs=10, col=0.8)  # mantlet
        b.cyl((1.7, sy + side * 0.04, 1.2), (3.2, sy + side * 0.2, 1.14), 0.065, 0.055, segs=8, col=0.6)
        b.cyl((-0.5, sy + side * 0.38, 1.3), (-0.5, sy + side * 0.75, 1.27), 0.03, segs=6, col=0.6)  # MG
        b.box((0.2, side * 0.95, 2.52), (5.4, 0.07, 0.1), (0, 0.045, 0), col=0.7)          # unditching rail
    b.box((1.75, 0, 2.42), (1.25, 1.5, 0.5), col=1.0)                                     # driver's cab
    b.box((2.42, 0, 2.42), (0.08, 1.1, 0.2), col=0.3)                                     # vision slit
    b.box((-1.9, 0, 2.2), (1.0, 1.2, 0.3), col=0.9)                                       # rear hatch box
    b.cyl((-0.4, 0.5, 2.1), (-0.4, 0.5, 2.75), 0.06, segs=6, col=0.5)                     # exhaust
    b.box((-3.75, 0, 1.0), (0.5, 1.6, 0.7), col=0.8)                                      # fuel tank
    return b.build(name, mats['tank'], matrix=world)


# --------------------------------------------------------------------------- #
# 6. ruined city
# --------------------------------------------------------------------------- #
WALL_TONES = [((0.30, 0.13, 0.09), 1.0), ((0.25, 0.10, 0.075), 1.0), ((0.34, 0.17, 0.11), 1.0),
              ((0.45, 0.38, 0.27), 0.15), ((0.33, 0.31, 0.28), 0.25), ((0.50, 0.45, 0.38), 0.1),
              ((0.17, 0.15, 0.14), 0.6), ((0.38, 0.30, 0.20), 0.3), ((0.28, 0.26, 0.21), 0.5)]


def ruin_profile(h, heavy):
    k = rng.randint(6, 10)
    ts = sorted(rng.random() for _ in range(k))
    lo = 0.5 if heavy else 0.86
    vs = [h * rng.uniform(lo, 1.0) for _ in ts]
    t0 = rng.random()
    if heavy:
        for i, t in enumerate(ts):
            dist = min(abs(t - t0), 1 - abs(t - t0))
            if dist < 0.2:
                vs[i] *= rng.uniform(0.12, 0.5)
    ph = rng.uniform(0, 6.28)

    def H(t):
        t %= 1.0
        for i in range(k):
            a, b = ts[i], ts[(i + 1) % k]
            if i == k - 1:
                b += 1.0
                tt = t if t >= a else t + 1.0
            else:
                tt = t
            if a <= tt <= b:
                f = (tt - a) / max(b - a, 1e-6)
                v = vs[i] + (vs[(i + 1) % k] - vs[i]) * f
                break
        else:
            v = vs[-1] + (vs[0] - vs[-1]) * ((t + 1 - ts[-1]) / max(ts[0] + 1 - ts[-1], 1e-6))
        return max(0.7, v + 0.45 * math.sin(t * 190 + ph) * math.sin(t * 61 + ph * 2))

    return H, min(vs), t0


def build_building(idx, cx, cy, w, d, h, wall_mat, cores, roofs, rubble, heavy=None, tone=None):
    heavy = (rng.random() < 0.68) if heavy is None else heavy
    H, hmin, t0 = ruin_profile(h, heavy)
    corners = [Vector((-w / 2, -d / 2)), Vector((w / 2, -d / 2)), Vector((w / 2, d / 2)), Vector((-w / 2, d / 2))]
    perim = 2 * (w + d)
    fh = rng.uniform(3.0, 3.6)
    zs = [0.0]
    f = 0
    while zs[-1] < h + 1.5:
        zs.extend((f * fh + 1.1, f * fh + 2.55, (f + 1) * fh))
        f += 1
    vid, verts, faces = {}, [], []

    def vert(p):
        key = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        if key not in vid:
            vid[key] = len(verts)
            verts.append(key)
        return vid[key]

    cum = 0.0
    for k in range(4):
        a, bcn = corners[k], corners[(k + 1) % 4]
        L = (bcn - a).length
        u_dir = (bcn - a) / L
        bays = max(1, int((L - 1.4) / 2.6))
        m = (L - bays * 2.6) / 2
        us = [0.0, m]
        for bay in range(bays):
            s = m + bay * 2.6
            us.extend((s + 0.8, s + 1.8, s + 2.6))
        us.append(L)
        hs = [H((cum + u) / perim) for u in us]
        for i in range(len(us) - 1):
            win_col = 1 <= i < len(us) - 2 and (i - 1) % 3 == 1
            for j in range(len(zs) - 1):
                if win_col and j % 3 == 1 and rng.random() > 0.07:
                    continue                                              # window hole
                z0a, z0b = min(zs[j], hs[i]), min(zs[j], hs[i + 1])
                z1a, z1b = min(zs[j + 1], hs[i]), min(zs[j + 1], hs[i + 1])
                if z1a <= z0a + 1e-4 and z1b <= z0b + 1e-4:
                    continue
                pa, pb = a + u_dir * us[i], a + u_dir * us[i + 1]
                ids = []
                for p in ((pa.x, pa.y, z0a), (pb.x, pb.y, z0b), (pb.x, pb.y, z1b), (pa.x, pa.y, z1a)):
                    v = vert(p)
                    if v not in ids:
                        ids.append(v)
                if len(ids) >= 3:
                    faces.append(tuple(ids))
        cum += L

    me = bpy.data.meshes.new(f"Ruin{idx:03d}")
    me.from_pydata(verts, [], faces)
    me.materials.append(wall_mat)
    ob = link(bpy.data.objects.new(f"Ruin{idx:03d}", me))
    yaw = rng.uniform(-0.05, 0.05)
    ob.location, ob.rotation_euler = (cx, cy, -0.3), (0, 0, yaw)
    col, brick = tone if tone else rng.choice(WALL_TONES)
    s = rng.uniform(0.75, 1.15)
    ob.color = (col[0] * s, col[1] * s, col[2] * s, brick)
    sol = ob.modifiers.new("Thickness", 'SOLIDIFY')
    sol.thickness, sol.offset = 0.42, -1.0

    world = M((cx, cy, -0.3), (0, 0, yaw))
    # dark gutted interior -> the lower windows read as black holes
    ch = hmin * 0.93
    cores.box_m(world @ M((0, 0, ch / 2), scale=(w - 0.9, d - 0.9, ch)), 1.0)
    # what is left of a pitched roof on the lightly damaged houses
    if not heavy and rng.random() < 0.8:
        rh = rng.uniform(2.0, 3.6)
        if w >= d:
            roofs.prism([(-w / 2 - 0.3, 0), (w / 2 + 0.3, 0), (w / 2 - 0.5, rh * 0.15), (0.0, rh), (-w / 2 + 0.5, rh * 0.15)],
                        -d / 2 * 0.72, d / 2 * 0.72, world @ M((0, 0, hmin * 0.97), (0, 0, math.pi / 2),
                                                               (d / w, w / d, 1)), rng.uniform(0.6, 1.0))
        else:
            roofs.prism([(-w / 2 - 0.3, 0), (w / 2 + 0.3, 0), (0.0, rh)], -d / 2 * 0.72, d / 2 * 0.72,
                        world @ M((0, 0, hmin * 0.97)), rng.uniform(0.6, 1.0))
    if rng.random() < 0.45:                                                # chimney stack
        cxo, cyo = rng.uniform(-0.3, 0.3) * w, rng.uniform(-0.3, 0.3) * d
        roofs.box_m(world @ M((cxo, cyo, (hmin + 2.2) / 2), scale=(0.9, 0.7, hmin + 2.2)), rng.uniform(0.9, 1.5))

    # rubble at the base, heaviest under the collapsed corner
    flat = lambda x, y: -0.05
    tt = t0 * perim
    acc = 0.0
    hot = corners[0]
    for k in range(4):
        L = (corners[(k + 1) % 4] - corners[k]).length
        if tt <= acc + L:
            hot = corners[k].lerp(corners[(k + 1) % 4], (tt - acc) / L)
            break
        acc += L
    hw = world @ Vector((hot.x * 1.12, hot.y * 1.12, 0))
    if heavy:
        rubble_pile(rubble, hw.x, hw.y, rng.uniform(3.0, 5.0), rng.uniform(1.2, 2.6), flat, n=22)
    for _ in range(4):
        k = rng.randrange(4)
        p = corners[k].lerp(corners[(k + 1) % 4], rng.random()) * 1.12
        pw = world @ Vector((p.x, p.y, 0))
        rubble_pile(rubble, pw.x, pw.y, rng.uniform(1.2, 2.4), rng.uniform(0.3, 0.9), flat, n=7)


def build_city(mats):
    wall = mats['wall']
    cores, roofs, rubble = Builder(), Builder(), Builder()
    count = 0
    street_half = 7.0
    for side in (-1, 1):
        x_inner = street_half
        for row in range(3):
            y = 72 + rng.uniform(0, 4)
            row_depth = 0.0
            while y < 254:
                dy, dx = rng.uniform(9, 15), rng.uniform(9, 14)
                hh = rng.uniform(8, 14) + row * 1.5 + (y - 72) / 180 * 9
                if rng.random() < 0.09:                                   # a lot flattened completely
                    rubble_pile(rubble, side * (x_inner + dx / 2), y + dy / 2, 5.5, 2.4, lambda a, b_: -0.05, n=40)
                else:
                    build_building(count, side * (x_inner + dx / 2 + rng.uniform(0, 1.2)), y + dy / 2, dx, dy, hh,
                                   wall, cores, roofs, rubble)
                    count += 1
                row_depth = max(row_depth, dx)
                y += dy + rng.uniform(0.3, 2.2)
            x_inner += row_depth + rng.uniform(4, 6)
    # the far end of the street: taller blocks and a broken church tower as the focal point
    for x in (-44, -31, -18, 19, 32, 45):
        build_building(count, x + rng.uniform(-1, 1), 266 + rng.uniform(-3, 3), 12, 12, rng.uniform(17, 26),
                       wall, cores, roofs, rubble)
        count += 1
    build_building(count, -5.5, 268, 11, 13, 20, wall, cores, roofs, rubble, heavy=False,
                   tone=((0.33, 0.31, 0.28), 0.25))
    build_building(count + 1, 4.5, 263, 7.5, 7.5, 44, wall, cores, roofs, rubble, heavy=True,
                   tone=((0.30, 0.28, 0.25), 0.3))
    count += 2

    # cobbled street with debris down the middle
    st = Builder()
    st.box((0, 170, 0.0), (2 * street_half, 200, 0.12), col=1.0)
    st.build("Street", mats['street'])
    for _ in range(26):
        rubble_pile(rubble, rng.uniform(-6.5, 6.5), rng.uniform(72, 250), rng.uniform(0.8, 2.2), rng.uniform(0.2, 0.7),
                    lambda a, b_: 0.05, n=8)
    cores.build("RuinInteriors", mats['black'])
    roofs.build("RuinRoofs", mats['roof'])
    rubble.build("CityRubble", mats['rubble'])
    return count


# --------------------------------------------------------------------------- #
# 7. atmosphere
# --------------------------------------------------------------------------- #
def build_atmosphere():
    sc = bpy.context.scene
    # sun: low, warm, behind the city -> backlight
    sun = bpy.data.lights.new("Sun", 'SUN')
    sun.energy, sun.angle, sun.color = 34.0, math.radians(2.5), (1.0, 0.60, 0.32)
    so = link(bpy.data.objects.new("Sun", sun))
    so.rotation_euler = SUN_DIR.to_track_quat('Z', 'Y').to_euler()

    # sky: dusty brown-orange gradient with a soft glow around the sun
    world = bpy.data.worlds.new("DustSky")
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    nt.nodes.clear()
    t = NT(nt)
    d = t.vmath('NORMALIZE', t.node('ShaderNodeTexCoord').outputs['Generated'])
    sep = t.node('ShaderNodeSeparateXYZ')
    nt.links.new(d, sep.inputs[0])
    up = t.math('POWER', t.math('MAXIMUM', sep.outputs[2], 0.0), 0.42)
    sky = t.mix(up, (1.00, 0.50, 0.22, 1), (0.21, 0.155, 0.12, 1))
    cloud = t.smooth(t.noise(t.vmath('MULTIPLY', d, (1.0, 1.0, 5.0)), 2.2, 5.0, 0.6), 0.42, 0.72)
    sky = t.mix(t.math('MULTIPLY', cloud, 0.45), sky, (0.16, 0.115, 0.09, 1))
    sky = t.mix(t.smooth(sep.outputs[2], -0.08, 0.0, 1.0, 0.0), sky, (0.07, 0.05, 0.035, 1))
    cosang = t.math('MAXIMUM', t.vmath('DOT_PRODUCT', d, tuple(SUN_DIR), out=1), 0.0)
    glow = t.math('ADD', t.math('MULTIPLY', t.math('POWER', cosang, 900.0), 160.0),
                  t.math('ADD', t.math('MULTIPLY', t.math('POWER', cosang, 40.0), 5.0),
                         t.math('MULTIPLY', t.math('POWER', cosang, 5.0), 0.9)))
    sky = t.mix(1.0, sky, t.vmath('SCALE', (1.0, 0.58, 0.28), None).node.outputs[0], 'ADD')
    nt.links.new(glow, sky.node.inputs[7].links[0].from_node.inputs[3])
    bg = t.node('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 1.15
    nt.links.new(sky, bg.inputs['Color'])
    nt.links.new(bg.outputs[0], t.node('ShaderNodeOutputWorld').inputs['Surface'])
    sc.world = world

    # one big homogeneous fog volume over the whole battlefield
    fb = Builder()
    fb.box((0, 180, 14), (900, 800, 36))
    fmat, fnt = new_material("Fog")
    ft = NT(fnt)
    vol = ft.node('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.80, 0.70, 0.60, 1)
    vol.inputs['Density'].default_value = FOG_DENSITY
    vol.inputs['Anisotropy'].default_value = 0.55
    fnt.links.new(vol.outputs[0], ft.node('ShaderNodeOutputMaterial').inputs['Volume'])
    fog = fb.build("Fog", fmat)
    fog.display_type = 'WIRE'

    # five tall smoke plumes rising from the city
    plumes = [(-36, 128, 74, 3.0, 15, -0.42, 0.26), (27, 152, 92, 3.5, 18, -0.36, 0.23),
              (-17, 208, 104, 4.0, 21, -0.33, 0.22), (52, 214, 86, 3.5, 17, -0.40, 0.23),
              (16, 104, 62, 2.4, 12, -0.45, 0.28)]
    for i, (px, py, H, r0, r1, lean, dens) in enumerate(plumes):
        segs, levels = 14, 14
        verts, faces = [], []
        for j in range(levels + 1):
            zn = j / levels
            cxo, R = lean * H * zn ** 1.6, (r0 + (r1 - r0) * zn ** 0.7) * 1.6
            for k in range(segs):
                a = 2 * math.pi * k / segs
                verts.append((cxo + R * math.cos(a), R * math.sin(a), zn * H))
        for j in range(levels):
            for k in range(segs):
                n = (k + 1) % segs
                faces.append((j * segs + k, j * segs + n, (j + 1) * segs + n, (j + 1) * segs + k))
        faces.append(tuple(range(segs - 1, -1, -1)))
        faces.append(tuple(range(levels * segs, (levels + 1) * segs)))
        me = bpy.data.meshes.new(f"Smoke{i}")
        me.from_pydata(verts, [], faces)
        me.materials.append(mat_smoke(f"Smoke{i}", H, r0, r1, lean, dens))
        ob = link(bpy.data.objects.new(f"Smoke{i}", me))
        ob.location = (px, py, 1.0)
        ob.display_type = 'WIRE'


# --------------------------------------------------------------------------- #
# camera: slow dolly along the trench + pan to the street + light handheld shake
# --------------------------------------------------------------------------- #
def cam_pose(frame):
    t = (frame - 1) / (N_FRAMES - 1)
    s = t * t * (3 - 2 * t)                                   # ease in / out
    x = -5.2 + 3.9 * (0.35 * t + 0.65 * s)                    # dolly forward along the trench (+X)
    pos = Vector((x, 0.35, 1.10))
    heading = math.radians(57.0 + (0.8 - 57.0) * s)           # angle from +Y toward +X
    pitch = math.radians(-5.5 + (2.6 + 5.5) * s)
    d = Vector((math.sin(heading) * math.cos(pitch), math.cos(heading) * math.cos(pitch), math.sin(pitch)))
    rot = d.to_track_quat('-Z', 'Y').to_euler()
    # very light handheld shake: sums of sines, evaluated per frame (no F-curve editing)
    tt = frame / FPS
    pos.x += 0.004 * math.sin(tt * 5.3 + 0.4)
    pos.y += 0.003 * math.sin(tt * 4.1 + 1.7)
    pos.z += 0.006 * math.sin(tt * 6.7 + 0.9) + 0.004 * math.sin(tt * 2.3)
    rot.x += math.radians(0.10 * math.sin(tt * 7.1 + 0.3) + 0.06 * math.sin(tt * 13.0 + 1.1))
    rot.y += math.radians(0.07 * math.sin(tt * 3.7 + 2.0))
    rot.z += math.radians(0.11 * math.sin(tt * 5.9 + 1.3) + 0.05 * math.sin(tt * 11.3))
    return pos, rot


def build_camera():
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("Cam")
    cam.lens, cam.sensor_width = 28.0, 36.0
    cam.clip_start, cam.clip_end = 0.05, 4000
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = 6.0
    cam.dof.focus_distance = 14.0
    ob = link(bpy.data.objects.new("Cam", cam))
    sc.camera = ob
    for f in range(1, N_FRAMES + 1):
        ob.location, ob.rotation_euler = cam_pose(f)
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    return ob


# --------------------------------------------------------------------------- #
# scene assembly + render
# --------------------------------------------------------------------------- #
def setup_render(samples):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 1
    sc.cycles.sample_clamp_indirect = 3.0
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES_X, RES_Y, 100
    sc.render.fps, sc.frame_start, sc.frame_end = FPS, 1, N_FRAMES
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.threads_mode = 'AUTO'
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = 0.0


def build_scene(samples):
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_render(samples)
    mats = {
        'mud': mat_mud(),
        'wood': mat_generic("Wood", (0.19, 0.13, 0.08), 0.85, nscale=7.0, bump=0.5, tint=(0.05, 0.04, 0.03)),
        'crate': mat_generic("CrateWood", (0.23, 0.19, 0.10), 0.8, nscale=9.0, bump=0.3),
        'burlap': mat_generic("Burlap", (0.34, 0.28, 0.19), 0.95, nscale=45.0, bump=0.35, bump_dist=0.01,
                              var=0.3, tint=(0.09, 0.07, 0.05), tint_scale=1.2),
        'helmet': mat_generic("HelmetSteel", (0.10, 0.11, 0.07), 0.5, 0.7, nscale=30.0, bump=0.15, var=0.3),
        'wire': mat_flat("RustyWire", (0.07, 0.045, 0.03), 0.6, 0.8),
        'char': mat_generic("CharredWood", (0.022, 0.019, 0.017), 0.9, nscale=9.0, bump=0.9, bump_dist=0.05),
        'rubble': mat_generic("Rubble", (1.0, 1.0, 1.0), 0.93, nscale=4.0, bump=0.6, bump_dist=0.04, var=0.7),
        'tank': mat_generic("TankSteel", (0.115, 0.115, 0.085), 0.58, 0.65, nscale=5.0, bump=0.25,
                            tint=(0.17, 0.075, 0.035), tint_scale=1.1),
        'wall': mat_building(),
        'black': mat_flat("Soot", (0.006, 0.005, 0.005), 1.0),
        'roof': mat_generic("Slate", (0.075, 0.07, 0.075), 0.8, nscale=3.0, bump=0.4),
        'street': mat_generic("Cobbles", (0.10, 0.09, 0.08), 0.75, nscale=6.0, bump=0.8, bump_dist=0.05),
    }
    make_craters()
    build_ground(mats['mud'])
    build_trench(mats)
    build_wire(mats)
    build_trees(mats)
    build_nomansland_rubble(mats)
    # tank 1: abandoned in the central corridor, nose down over a crater lip
    build_tank("Tank_Corridor", mats, M((0.4, 33.0, ground_z(0.4, 33.0) + 0.02), (0.05, 0.07, math.radians(-118))))
    # tank 2: far away on the left, half lost in the haze
    build_tank("Tank_Far", mats, M((-23.0, 61.0, ground_z(-23.0, 61.0) - 0.05), (-0.06, -0.10, math.radians(160))))
    n_buildings = build_city(mats)
    build_atmosphere()
    build_camera()
    print(f"[ww1] scene built in {time.time() - t0:.1f}s | craters={len(CRATERS)} buildings={n_buildings} "
          f"objects={len(bpy.data.objects)}", flush=True)
    assert len(CRATERS) >= 30 and n_buildings >= 60
    return n_buildings


def render_frame(frame, path):
    sc = bpy.context.scene
    sc.frame_set(frame)
    tmp = path[:-4] + ".part.png"
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    os.replace(tmp, path)                      # atomic: a killed render never leaves a half frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=int, nargs='*', help="render only these frame numbers into out/test/")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=N_FRAMES)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)

    os.makedirs(FRAME_DIR, exist_ok=True)
    build_scene(args.samples)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"[ww1] saved {BLEND_PATH}", flush=True)
    if args.no_render:
        return

    if args.still is not None:
        os.makedirs(os.path.join(OUT_DIR, "test"), exist_ok=True)
        for f in (args.still or [60]):
            t0 = time.time()
            p = os.path.join(OUT_DIR, "test", f"still_{f:04d}.png")
            render_frame(f, p)
            print(f"[ww1] still {f} -> {p} ({time.time() - t0:.1f}s)", flush=True)
        return

    for f in range(args.start, args.end + 1):
        p = os.path.join(FRAME_DIR, f"frame_{f:04d}.png")
        if os.path.exists(p):
            continue                           # resumable: skip finished frames
        t0 = time.time()
        render_frame(f, p)
        print(f"[ww1] frame {f}/{N_FRAMES} ({time.time() - t0:.1f}s)", flush=True)
    print("[ww1] render complete", flush=True)


if __name__ == "__main__":
    main()
