"""Elemental sword trails, drawn in the manner of hand-painted action: a stream of water following
the Ronin's blades, a stream of fire following the Oni's.

When a blade is swung - its point moving fast round the fist, not merely carried along at a run -
a stream follows the path its point has just taken: thick where it leaves the blade, tapering away
behind. It is shaded in flat bands by how squarely it faces the camera (pale in the middle, deeper
toward its sides, an ink line at its edge), so that it reads as a drawn shape in the rendered
scene. Water has flow lines spiralling along it and a thinner stream winding round it; fire has a
ragged, flickering edge. Drops or embers fly from the fastest moments, and each stream lights the
scene a little in its own colour.

This is our own design, after Japanese woodblock prints of waves and fire (the long tradition
behind many anime effects); it does not copy any show's effects.

Like the rest of the fight's effects nothing is simulated: every frame is built from the swords'
places in the take (Actor.sword_m) at that take time, so any film frame can be rendered alone.

    tr = elemental.Trails(collection, [(actor, sword key, 'water' | 'fire', (first, last take frame)), ...])
    tr.update(take_time)
"""
import math

import bpy
import numpy as np
from mathutils import Vector

from . import hits, motion

STYLE = dict(
    water=dict(bands=((0.00, (0.85, 0.95, 1.0)), (0.14, (0.30, 0.74, 1.0)), (0.40, (0.04, 0.32, 0.95)), (0.70, (0.010, 0.08, 0.42)), (0.88, (0.004, 0.014, 0.08))),
               glow=2.2, radius=0.085, light_col=(0.30, 0.60, 1.0), watts=60.0),
    fire=dict(bands=((0.00, (1.0, 0.78, 0.30)), (0.16, (1.0, 0.46, 0.06)), (0.42, (0.95, 0.13, 0.015)), (0.70, (0.40, 0.012, 0.0)), (0.88, (0.06, 0.0, 0.0))),
              glow=3.0, radius=0.09, light_col=(1.0, 0.30, 0.06), watts=150.0),
)
SPAN, STEPS, SIDES = 6.0, 36, 10      # a stream reaches back this many take frames, in this many rings of this many sides
SWING = (4.0, 7.5)                    # speed of the point round the fist (m/s) at which a stream starts to show and is at full size


def trail_mat(kind):
    """u runs along the stream from the blade (0) to its tail (1), v round it."""
    name = "MAT_Stream_" + kind
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    S = STYLE[kind]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    link = nt.links.new

    def op(kind_, a=None, b=None, c=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = kind_
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                link(v, n.inputs[i])
        return n.outputs[0]

    def sock(coll, ident):
        return next(s for s in coll if s.identifier == ident)

    def mix_rgb(fac, a, b):
        n = nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        link(fac, sock(n.inputs, "Factor_Float"))
        for ident, v in (("A_Color", a), ("B_Color", b)):
            if isinstance(v, tuple):
                sock(n.inputs, ident).default_value = (*v, 1.0)
            else:
                link(v, sock(n.inputs, ident))
        return sock(n.outputs, "Result_Color")

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    link(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    facing = lw.outputs["Facing"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    # flat bands by how squarely the surface faces the camera: a drawn shape with an ink edge
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    (p0, c0), (p1, c1) = S["bands"][0], S["bands"][-1]
    els[0].position, els[0].color = p0, (*c0, 1)
    els[1].position, els[1].color = p1, (*c1, 1)
    for p, c in S["bands"][1:-1]:
        e = els.new(p)
        e.color = (*c, 1)
    wob = nt.nodes.new("ShaderNodeTexNoise")                         # the bands' edges wander, as brush strokes do
    wob.inputs["Scale"].default_value = 1.0
    wob.inputs["Detail"].default_value = 2.0
    wxy = nt.nodes.new("ShaderNodeCombineXYZ")
    link(op("MULTIPLY", u, 9.0), wxy.inputs[0])
    link(op("MULTIPLY", v, 3.0), wxy.inputs[1])
    link(wxy.outputs[0], wob.inputs["Vector"])
    link(op("ADD", facing, op("MULTIPLY", op("SUBTRACT", wob.outputs["Fac"], 0.5), 0.14)), ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    alpha = op("MULTIPLY", op("POWER", op("SUBTRACT", 1.0, u), 1.1), 0.95)
    if kind == "water":                                              # flow lines spiralling along the stream, pale, inside the ink edge
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.bands_direction = "X"
        wave.inputs["Scale"].default_value = 1.0
        wave.inputs["Distortion"].default_value = 2.5
        fxy = nt.nodes.new("ShaderNodeCombineXYZ")
        link(op("ADD", op("MULTIPLY", u, 4.5), op("MULTIPLY", v, 0.9)), fxy.inputs[0])
        link(fxy.outputs[0], wave.inputs["Vector"])
        line = op("MULTIPLY", op("GREATER_THAN", wave.outputs["Fac"], 0.86), op("LESS_THAN", facing, 0.62))
        col = mix_rgb(line, col, S["bands"][0][1])
    else:                                                            # fire: the edge is torn into flickering tongues
        tn = nt.nodes.new("ShaderNodeTexNoise")
        tn.inputs["Scale"].default_value = 1.0
        tn.inputs["Detail"].default_value = 4.0
        txy = nt.nodes.new("ShaderNodeCombineXYZ")
        link(op("MULTIPLY", u, 16.0), txy.inputs[0])
        link(op("MULTIPLY", v, 5.0), txy.inputs[1])
        link(txy.outputs[0], tn.inputs["Vector"])
        reach = op("MULTIPLY_ADD", tn.outputs["Fac"], 0.55, 0.52)    # how far toward the edge the flame reaches here
        alpha = op("MULTIPLY", alpha, op("LESS_THAN", facing, reach))
    alpha = op("MULTIPLY", alpha, op("SUBTRACT", 1.0, geo.outputs["Backfacing"]))    # the far side is not drawn
    em = nt.nodes.new("ShaderNodeEmission")
    link(col, em.inputs["Color"])
    gain = op("MULTIPLY", op("POWER", op("SUBTRACT", 1.0, u), 0.5), S["glow"])
    link(gain, em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    link(alpha, mix.inputs["Fac"])
    link(tr.outputs[0], mix.inputs[1])
    link(em.outputs[0], mix.inputs[2])
    link(mix.outputs[0], out.inputs["Surface"])
    return m


class Trails:
    def __init__(self, col, specs, seed=7):
        """specs: [(actor, sword key, 'water' | 'fire', (first take frame, last take frame)[, boosts])];
        boosts [(first, last take frame, k)]: the signature moves, where the stream is k times as thick."""
        self.specs = []
        self.obs, self.lights, self.drops = {}, {}, {}
        for kind in sorted({s[2] for s in specs}):
            ob = hits.holder("FX_Stream_" + kind, col, trail_mat(kind))
            self.obs[kind] = ob
            ld = bpy.data.lights.new("FX_StreamLight_" + kind, "POINT")
            ld.color, ld.shadow_soft_size, ld.energy = STYLE[kind]["light_col"], 0.25, 0.0
            lo = bpy.data.objects.new("FX_StreamLight_" + kind, ld)
            col.objects.link(lo)
            self.lights[kind] = lo
            mat = hits.glow("MAT_Drops_" + kind, (0.70, 0.88, 1.0) if kind == "water" else (1.0, 0.45, 0.08), 10.0 if kind == "water" else 40.0)
            self.drops[kind] = (hits.holder("FX_Drops_" + kind, col, mat), [])
        rng = np.random.default_rng(seed)
        for A, key, kind, (f0, f1), *rest in specs:
            boosts = rest[0] if rest else []
            sw = A.swords[key]
            L = sw.spec["blade"]
            n = len(A.sword_m[key])
            tip = np.array([np.array(A.sword_m[key][f] @ Vector(sw.arc(L))) for f in range(n)])
            grip = np.array([np.array(A.sword_m[key][f] @ Vector(sw.arc(0.0))) for f in range(n)])
            rel = tip - grip                                          # the point round the fist: a swing, not a run
            swing = np.zeros(n)
            swing[1:-1] = np.linalg.norm(rel[2:] - rel[:-2], axis=1) * 0.5 * hits.FPS
            swing[:f0] = swing[f1 + 1:] = 0.0
            w = np.clip((swing - SWING[0]) / (SWING[1] - SWING[0]), 0.0, 1.0)
            w = w * w * (3 - 2 * w)
            w = np.convolve(w, np.ones(3) / 3.0, mode="same")           # no flicker from one frame to the next
            big = np.ones(n)
            for b0, b1, k in boosts:                                  # eased in and out over four frames each side
                for f in range(max(0, b0 - 4), min(n, b1 + 5)):
                    e = min(1.0, (f - (b0 - 4)) / 4.0, ((b1 + 4) - f) / 4.0)
                    big[f] = max(big[f], 1.0 + (k - 1.0) * e * e * (3 - 2 * e))
            self.specs.append((A, key, kind, (f0, f1), w * big))
            last = -99
            for f in range(max(1, f0), min(f1, n - 1)):              # drops and embers from the fastest moments
                if swing[f] < 8.0 or f - last < 2:
                    continue
                last = f
                v = (tip[f + 1] - tip[f - 1]) * 0.5 * hits.FPS
                d = v / max(1e-6, np.linalg.norm(v))
                sp = float(np.linalg.norm(v))
                if kind == "water":
                    b = hits.Burst(tuple(tip[f]), f, toward=tuple(d + np.array((0.0, 0.0, 0.3))), count=int(8 + 1.6 * sp), speed=(0.5, 0.3 * sp),
                                   spread=30.0, life=(0.25, 0.6), gravity=9.81, drag=1.4, width=0.0045, streak=0.02, seed=int(rng.integers(1 << 30)))
                else:
                    b = hits.Burst(tuple(tip[f]), f, toward=tuple(d * 0.6 + np.array((0.0, 0.0, 0.8))), count=int(6 + 1.4 * sp), speed=(0.4, 0.22 * sp),
                                   spread=42.0, life=(0.3, 0.9), gravity=-0.6, drag=2.2, width=0.004, streak=0.012, seed=int(rng.integers(1 << 30)))
                self.drops[kind][1].append(b)

    @staticmethod
    def _blade(A, key, tt):
        n = len(A.sword_m[key])
        tt = min(max(tt, 0.0), n - 1.0)
        i = int(math.floor(tt))
        return motion._mix4(A.sword_m[key][i], A.sword_m[key][min(i + 1, n - 1)], tt - i)

    @staticmethod
    def _weight(w, tt):
        n = len(w)
        if tt <= 0.0 or tt >= n - 1:
            return 0.0
        i = int(math.floor(tt))
        return float(w[i] + (w[i + 1] - w[i]) * (tt - i))

    def update(self, t):
        geo = {k: ([], [], []) for k in self.obs}
        lit = {k: [Vector(), 0.0] for k in self.obs}
        for A, key, kind, (f0, f1), w in self.specs:
            if f0 <= t <= f1 + SPAN:
                self._stream(A, key, kind, w, t, *geo[kind], lit[kind])
        for kind, ob in self.obs.items():
            verts, faces, uvs = geo[kind]
            me = ob.data
            me.clear_geometry()
            if verts:
                me.from_pydata(verts, [], faces)
                layer = me.uv_layers.new(name="UVMap") if not me.uv_layers else me.uv_layers[0]
                layer.data.foreach_set("uv", np.array(uvs, dtype=np.float32).reshape(-1))
                for p in me.polygons:
                    p.use_smooth = True
            me.update()
            c, size = lit[kind]
            Lo = self.lights[kind]
            Lo.data.energy = min(1.0, size) * STYLE[kind]["watts"]
            if size > 0.0:
                Lo.location = c / size
            holder, bursts = self.drops[kind]
            hits.fill(holder, [b for b in bursts if -0.5 < t - b.frame < 24.0], t)

    def _stream(self, A, key, kind, w, t, verts, faces, uvs, lit):
        S = STYLE[kind]
        sw = A.swords[key]
        L = sw.spec["blade"]
        dt = SPAN / STEPS
        path = []
        for k in range(STEPS + 1):
            tt = t - k * dt
            wk = self._weight(w, tt)
            M = self._blade(A, key, tt)
            g, p = M @ Vector(sw.arc(0.0)), M @ Vector(sw.arc(L + 0.03))
            u = k / STEPS
            path.append((p, (p - g).normalized(), S["radius"] * wk * (1.0 - u) ** 0.8, u))
        self._tube(path, verts, faces, uvs)
        if kind == "water":                                          # a thinner stream winding round the main one
            wind = []
            for k, (p, out, r, u) in enumerate(path):
                T = path[max(0, k - 1)][0] - path[min(STEPS, k + 1)][0]
                if T.length < 1e-6 or r < 1e-4:
                    wind.append((p, out, 0.0, u))
                    continue
                T.normalize()
                N = (out - T * out.dot(T)).normalized()
                B = T.cross(N)
                a = 1.3 + k * 0.55 + t * 0.2
                wind.append((p + (N * math.cos(a) + B * math.sin(a)) * (r * 1.45), out, r * 0.32, u))
            self._tube(wind, verts, faces, uvs)
        head = [(p, r) for p, _, r, u in path[:STEPS // 3] if r > 1e-3]
        if head:
            lit[0] += sum((p * r for p, r in head), Vector()) / max(1e-6, sum(r for _, r in head)) * (head[0][1] / S["radius"])
            lit[1] += head[0][1] / S["radius"]

    @staticmethod
    def _tube(path, verts, faces, uvs):
        """A tube through path [(centre, a way square to it, radius, u)]; stretches of zero radius are left open."""
        rings = []
        for k, (p, out, r, u) in enumerate(path):
            if r < 1e-4:
                rings.append(None)
                continue
            T = path[max(0, k - 1)][0] - path[min(len(path) - 1, k + 1)][0]
            if T.length < 1e-6:
                rings.append(None)
                continue
            T.normalize()
            N = out - T * out.dot(T)
            if N.length < 1e-6:
                rings.append(None)
                continue
            N.normalize()
            B = T.cross(N)
            ring = [p + (N * math.cos(2 * math.pi * j / SIDES) * r + B * math.sin(2 * math.pi * j / SIDES) * r * 0.75) for j in range(SIDES)]
            rings.append((ring, u))
        for k in range(len(rings) - 1):
            a, b = rings[k], rings[k + 1]
            if a is None or b is None:
                continue
            for j in range(SIDES):
                j1 = (j + 1) % SIDES
                i = len(verts)
                verts += [tuple(a[0][j]), tuple(a[0][j1]), tuple(b[0][j1]), tuple(b[0][j])]
                faces.append((i, i + 1, i + 2, i + 3))
                v0, v1 = j / SIDES, (j + 1) / SIDES
                uvs += [(a[1], v0), (a[1], v1), (b[1], v1), (b[1], v0)]
