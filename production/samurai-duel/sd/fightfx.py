"""The fight's effects, drawn frame by frame from what film.fight() says happens (film.EVENTS):
sparks and a flash where blades meet, water thrown by feet, fire on the Oni's blade, the tear in
the Ronin's cape, his hat falling in two halves, the crack across the Oni's mask.

Nothing here is simulated or keyed. Everything is a function of the take time (or, for what has
to go on while a blow is held on screen, of the film frame), so any film frame can be rendered on
its own and in any order.

    fx = fightfx.FightFX(scene, cast, collection, cloth_folder)
    ... set the scene to the film frame's scene time ...
    fx.update(film_frame, camera)
"""
import math
import os
import struct

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import film, hits, motion

Z = Vector((0.0, 0.0, 1.0))


def _smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def _fill(ob, verts, faces, uvs=None):
    """Rebuild a mesh object; uvs: one (u, v) per face corner, in face order."""
    me = ob.data
    me.clear_geometry()
    if verts:
        me.from_pydata(verts, [], faces)
        if uvs is not None:
            layer = me.uv_layers.new(name="UVMap") if not me.uv_layers else me.uv_layers[0]
            layer.data.foreach_set("uv", np.array(uvs, dtype=np.float32).reshape(-1))
    me.update()


def read_pc2(path, sample):
    """One sample of a PC2 point cache: (points, 3) positions in the object's own space."""
    with open(path, "rb") as fh:
        _, _, n, _, _, count = struct.unpack("<12siiffi", fh.read(32))
        sample = min(max(sample, 0), count - 1)
        fh.seek(32 + sample * n * 12)
        return np.frombuffer(fh.read(n * 12), dtype="<f4").reshape(n, 3).astype(np.float64)


def flame_mat(name="MAT_Flame"):
    """Fire as light only. v runs from 0 (on the blade, or the newest part of a trail) to 1 (the
    tip of a tongue, the oldest part of a trail): orange-white, through red, to a dark red that
    thins out to nothing. u runs along the blade; the fire is broken into streaks along it."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    link = nt.links.new

    def math(op, a=None, b=None, c=None, name=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                link(v, n.inputs[i])
        if name:
            n.name = name
        return n.outputs[0]

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    link(uv.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, (1.0, 0.50, 0.16, 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 1.0, (0.20, 0.0, 0.0, 1)
    mid = ramp.color_ramp.elements.new(0.30)
    mid.color = (1.0, 0.10, 0.015, 1)
    link(v, ramp.inputs["Fac"])
    young = math("SUBTRACT", 1.0, v)
    strength = math("MULTIPLY_ADD", math("POWER", young, 2.0), 14.0, 1.2, name="gain")
    em = nt.nodes.new("ShaderNodeEmission")
    link(ramp.outputs["Color"], em.inputs["Color"])
    link(strength, em.inputs["Strength"])
    # streaks: noise stretched along the trail
    scale = nt.nodes.new("ShaderNodeCombineXYZ")
    link(math("MULTIPLY", u, 16.0), scale.inputs[0])
    link(math("MULTIPLY", v, 2.2), scale.inputs[1])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 3.0
    link(scale.outputs[0], noise.inputs["Vector"])
    streak = math("MINIMUM", math("MAXIMUM", math("MULTIPLY_ADD", noise.outputs["Fac"], 2.4, -0.62), 0.0), 1.0)
    alpha = math("MULTIPLY", math("MULTIPLY", math("POWER", young, 1.6), math("MULTIPLY_ADD", u, 0.75, 0.25)), streak)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    link(alpha, mix.inputs["Fac"])
    link(tr.outputs[0], mix.inputs[1])
    link(em.outputs[0], mix.inputs[2])
    link(mix.outputs[0], out.inputs["Surface"])
    return m


def crack_mat(name="MAT_Crack"):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.004, 0.003, 0.003, 1)
        b.inputs["Roughness"].default_value = 0.9
        b.inputs["Emission Color"].default_value = (1.0, 0.10, 0.03, 1)
        b.inputs["Emission Strength"].default_value = 0.35
    return m


class FightFX:
    def __init__(self, sc, cast, col, cloth_folder=None):
        self.sc, self.cast, self.col = sc, cast, col
        E = film.EVENTS
        # --- steel on steel: sparks, and a flash that lasts through the frames a blow is held for
        self.sparks = hits.holder("FX_Sparks", col, hits.glow("MAT_Sparks", (1.0, 0.60, 0.20), 55.0))
        self.spark_bursts = [hits.sparks(tuple(ev["at"]), ev["f"] - 0.35, toward=(0.0, 0.0, 1.0), seed=11 + i, count=int(120 * ev.get("power", 1.0)))
                             for i, ev in enumerate(e for e in E if e["kind"] == "clash")]
        verts, faces = [], []
        for w_, h_ in ((0.085, 0.0030), (0.0030, 0.055), (0.011, 0.011)):
            k = len(verts)
            verts += [(-w_, -h_, 0), (w_, -h_, 0), (w_, h_, 0), (-w_, h_, 0)]
            faces.append((k, k + 1, k + 2, k + 3))
        self.flash = bpy.data.objects.new("FX_Flash", bpy.data.meshes.new("FX_Flash"))
        col.objects.link(self.flash)
        self.flash.data.from_pydata(verts, [], faces)
        self.flash.data.materials.append(hits.glow("MAT_Flash", (1.0, 0.86, 0.62), 160.0))
        self.flash.visible_shadow = False
        self.flash.hide_render = True
        self.blows = [(film.film_of(ev["f"]), Vector(ev["at"]), ev.get("power", 1.0)) for ev in E if ev["kind"] == "clash"]
        # --- water: feet that stamp or skid on the wet floor
        self.spray = hits.holder("FX_Spray", col, hits.spray_mat())
        self.water = []
        for i, ev in enumerate(E):
            if ev["kind"] == "splash":
                at = (ev["at"][0], ev["at"][1], 0.012)
                self.water.append(hits.splash(at, ev["f"], toward=Vector(ev.get("toward", (0, 0, 0))) * 0.6 + Z, seed=41 + i, count=int(150 * ev.get("power", 1.0))))
            elif ev["kind"] == "skid":
                A = cast[ev["who"]]
                for f in range(ev["f0"], min(ev["f1"], A.frames - 2)):
                    for s in "LR":
                        p0, p1 = A.controls[f]["foot_" + s]["pos"], A.controls[f + 1]["foot_" + s]["pos"]
                        v = Vector((p1.x - p0.x, p1.y - p0.y, 0.0))
                        speed = v.length * hits.FPS
                        if speed < 0.4:
                            continue
                        self.water.append(hits.Burst((p1.x, p1.y, 0.012), f + 0.5, toward=v.normalized() * 0.8 + Z * 0.7, count=int(8 + 7 * speed), speed=(0.5, 1.0 + 0.6 * speed),
                                                     spread=42.0, life=(0.2, 0.55), drag=1.0, width=0.005, streak=0.028, seed=500 + 7 * f + (0 if s == "L" else 3)))
        # --- fire on the Oni's blade
        self.flame_ev = next((e for e in E if e["kind"] == "flame"), None)
        if self.flame_ev:
            self.flame = hits.holder("FX_Flame", col, flame_mat())
            ld = bpy.data.lights.new("FX_FlameLight", "POINT")
            ld.color, ld.shadow_soft_size, ld.energy = (1.0, 0.22, 0.05), 0.12, 0.0
            self.flame_light = bpy.data.objects.new("FX_FlameLight", ld)
            col.objects.link(self.flame_light)
        # --- the Ronin's cape: the part that the cut takes off, and the scrap that flies
        self.tear_ev = next((e for e in E if e["kind"] == "tear"), None)
        self.tear_mask = self.scrap = None
        cape = cast["ronin"].F.get("cape")
        if self.tear_ev and cape is not None and cloth_folder is not None:
            self._setup_tear(cape, os.path.join(cloth_folder, f"{cape.name}.pc2"))
        # --- his hat: whole until it parts, then two halves that slide off and fall
        self.split_ev = next((e for e in E if e["kind"] == "hat_split"), None)
        F = cast["ronin"].F
        self.hat, self.halves = F.get("hat"), []
        if self.split_ev and self.hat is not None:
            for h in F.get("hat_halves", []):
                mw = h.matrix_world.copy()
                h.parent = None
                h.matrix_world = mw
                c = Vector(np.mean([v.co[:] for v in h.data.vertices], axis=0))      # which side of the cut this half is on, in the hat's own space
                self.halves.append((h, Vector((c.x, c.y, 0.0)).normalized()))
        # --- the Oni's mask: the crack is laid on the mask when it is first needed
        self.crack_ev = next((e for e in E if e["kind"] == "mask_crack"), None)
        self.crack = None

    # ------------------------------------------------------------------ the cape
    def _setup_tear(self, cape, path, seed=5):
        me = cape.data
        if not me.uv_layers or not os.path.exists(path):
            return
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        me.uv_layers[0].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        gone = []
        for p in me.polygons:                                        # the lower corner on his left, cut off on a slant
            u, v = uv[list(p.loop_indices)].mean(axis=0)
            if u > 0.36 and v > 0.58 + 0.34 * (1.0 - u):
                gone.append(p.index)
        if not gone:
            return
        vid = sorted({v for i in gone for v in me.polygons[i].vertices})
        vg = cape.vertex_groups.new(name="torn")
        vg.add(vid, 1.0, "REPLACE")
        mask = cape.modifiers.new("Tear", "MASK")
        mask.vertex_group, mask.invert_vertex_group = "torn", True
        first_dress = next((i for i, m in enumerate(cape.modifiers) if m.type in ("SUBSURF", "SOLIDIFY")), len(cape.modifiers) - 1)
        cape.modifiers.move(len(cape.modifiers) - 1, first_dress)
        mask.show_render = mask.show_viewport = False
        self.tear_mask = mask
        # the scrap, shaped as that part of the cape is on the frame it is cut
        f = self.tear_ev["f"]
        P = read_pc2(path, f + 1)                                    # the cache's first sample is the scene frame before the take's first
        index = {v: k for k, v in enumerate(vid)}
        mw = cape.matrix_world
        W = [mw @ Vector(P[v]) for v in vid]
        c0 = sum(W, Vector()) / len(W)
        scrap = bpy.data.objects.new("Ronin_Cape_Scrap", bpy.data.meshes.new("Ronin_Cape_Scrap"))
        self.col.objects.link(scrap)
        scrap.data.from_pydata([tuple(w - c0) for w in W], [], [tuple(index[v] for v in me.polygons[i].vertices) for i in gone])
        scrap.data.polygons.foreach_set("use_smooth", np.ones(len(scrap.data.polygons), dtype=bool))
        for m in cape.data.materials:
            scrap.data.materials.append(m)
        so = scrap.modifiers.new("solid", "SOLIDIFY")
        so.thickness, so.offset = 0.0014, 0.0
        scrap.hide_render = True
        A = self.cast["oni"]
        sw = A.swords["main"]
        tip = lambda fr: A.sword_m["main"][min(A.frames - 1, fr)] @ Vector(sw.arc(sw.spec["blade"]))
        v0 = (tip(f + 1) - tip(f - 1)) * (hits.FPS / 2.0)            # the blade's point carries it along
        v0 = v0.normalized() * min(v0.length, 3.2) * 0.8 + Z * 0.9
        r = np.random.default_rng(seed)
        axis = Vector(r.normal(size=3)).normalized()
        self.scrap = dict(ob=scrap, c0=c0, v0=v0, axis=axis, f=f)

    def _scrap_at(self, t):
        S = self.scrap
        a = (t - S["f"]) / hits.FPS
        k = 5.5                                                      # cloth: the air stops it almost at once, then it sinks
        e = (1.0 - math.exp(-k * a)) / k
        p = S["c0"] + S["v0"] * e
        p.z -= 9.81 * (a - e) / k
        p.x += 0.07 * math.sin(6.5 * a) * min(1.0, a * 2.0)
        p.y += 0.05 * math.sin(4.7 * a + 1.0) * min(1.0, a * 2.0)
        angle = 5.0 * a + 0.5 * math.sin(6.0 * a)
        if p.z < 0.02:                                               # on the floor: flat, where it came down
            p.z = 0.02
            return Matrix.Translation(p) @ Matrix.Rotation(math.radians(90.0), 4, "X")
        return Matrix.Translation(p) @ Matrix.Rotation(angle, 4, S["axis"])

    # ------------------------------------------------------------------ the hat
    def _half_at(self, W0, d, tau):
        """World matrix of a hat half tau seconds after the cut: a hair's gap, a slide down the side of
        the head, then a fall. d: which way this half goes, in the hat's own space."""
        d = (W0.to_3x3() @ d)
        d = Vector((d.x, d.y, 0.0)).normalized()
        axis = Z.cross(d)
        GAP, SLIDE = 0.22, 0.55
        if tau < GAP:
            off, tilt = d * (0.003 * tau / GAP), 0.0
        elif tau < GAP + SLIDE:
            u = (tau - GAP) / SLIDE
            off, tilt = d * (0.003 + 0.20 * u * u) - Z * (0.11 * u * u), 50.0 * u * u
        else:
            s = tau - GAP - SLIDE
            off = d * (0.203 + 0.727 * s) - Z * (0.11 + 0.40 * s + 4.9 * s * s)
            tilt = min(165.0, 50.0 + 182.0 * s)
            floor = 0.06 - W0.translation.z
            if off.z < floor:                                        # down: it lies where it fell
                s_l = (-0.40 + math.sqrt(0.16 + 19.6 * (-floor - 0.11))) / 9.8
                off = d * (0.203 + 0.727 * s_l) + Z * floor
                tilt = min(165.0, 50.0 + 182.0 * s_l + 60.0 * _smooth((s - s_l) / 0.12))
        return Matrix.Translation(W0.translation + off) @ Matrix.Rotation(math.radians(tilt), 4, axis) @ Matrix.Translation(-W0.translation) @ W0

    # ------------------------------------------------------------------ the mask
    def _build_crack(self, take_frame, seed=3):
        A = self.cast["oni"]
        f = min(A.frames - 1, int(round(take_frame)))
        dg = bpy.context.evaluated_depsgraph_get()
        body = A.body
        bvh = BVHTree.FromObject(body, dg)
        Mw = body.matrix_world
        Mi = Mw.inverted()
        D = A.arm.matrix_world.to_3x3() @ A.poses[f]["D"]["Head"]
        head = A.arm.matrix_world @ A.pp.heads(A.poses[f])["Head"]
        r = np.random.default_rng(seed)

        def on_mask(x, z):
            o = head + D @ Vector((x, -0.6, z))
            hit = bvh.ray_cast(Mi @ o, (Mi.to_3x3() @ (D @ Vector((0.0, 1.0, 0.0)))).normalized(), 1.2)
            if hit[0] is None:
                return None
            return Mw @ hit[0], (Mw.to_3x3() @ hit[1]).normalized()

        def line(a, b, n, wobble):
            pts = []
            for i in range(n + 1):
                u = i / n
                x = a[0] + (b[0] - a[0]) * u + (r.normal() * wobble if 0 < i < n else 0.0)
                z = a[1] + (b[1] - a[1]) * u + (r.normal() * wobble if 0 < i < n else 0.0)
                got = on_mask(x, z)
                if got is not None:
                    pts.append(got)
            return pts

        main = line((0.082, 0.150), (-0.072, -0.012), 16, 0.0065)    # from above his left eye down across the nose to the right cheek
        strokes = [(main, 0.0050)]
        if len(main) > 11:
            for k, to in ((5, (0.040, -0.030)), (10, (-0.085, 0.060))):       # two short branches
                p = main[k][0]
                loc = D.transposed() @ (p - head)
                strokes.append((line((loc.x, loc.z), (loc.x + to[0], loc.z + to[1]), 4, 0.004), 0.0028))
        verts, quads = [], []
        for pts, width in strokes:
            start = len(quads)
            for i, (p, n) in enumerate(pts):
                t = (pts[min(i + 1, len(pts) - 1)][0] - pts[max(i - 1, 0)][0]).normalized()
                side = n.cross(t).normalized()
                w = width * (0.25 + 0.75 * math.sin(math.pi * (i + 0.5) / len(pts)))       # thin at both ends
                verts += [tuple(p + n * 0.0012 + side * w * 0.5), tuple(p + n * 0.0012 - side * w * 0.5)]
                if i:
                    k = len(verts)
                    quads.append((k - 4, k - 3, k - 1, k - 2))
        ob = bpy.data.objects.new("Oni_Mask_Crack", bpy.data.meshes.new("Oni_Mask_Crack"))
        self.col.objects.link(ob)
        ob.data.materials.append(crack_mat())
        ob.visible_shadow = False
        ob.data.from_pydata(verts, [], quads)
        from .fighters import _attach
        _attach(ob, A.arm, "Head")
        self.crack = dict(ob=ob, verts=verts, quads=quads, main=len(main) - 1)

    # ------------------------------------------------------------------ one film frame
    def update(self, ff, cam):
        t = film.take_time(ff)
        hits.fill(self.sparks, [b for b in self.spark_bursts if -0.5 < t - b.frame < 16.0], t)
        hits.fill(self.spray, [b for b in self.water if -0.5 < t - b.frame < 24.0], t)
        # the flash is timed in film frames: it flares while the blow is held
        self.flash.hide_render = True
        for at_ff, at, power in self.blows:
            age = ff - at_ff
            if 0 <= age < 5:
                k = power * (1.0, 0.8, 0.5, 0.26, 0.1)[age]
                self.flash.hide_render = False
                self.flash.location = at + (cam.location - at).normalized() * 0.03
                self.flash.rotation_euler = cam.rotation_euler
                self.flash.scale = (k, k, k)
        if self.flame_ev:
            self._flame(t)
        if self.tear_mask is not None:
            cut = t >= self.tear_ev["f"]
            self.tear_mask.show_render = self.tear_mask.show_viewport = cut
            self.scrap["ob"].hide_render = not cut
            if cut:
                self.scrap["ob"].matrix_world = self._scrap_at(t)
        if self.split_ev and self.halves:
            cut = t >= self.split_ev["f"]
            self.hat.hide_render = cut
            W0 = self.hat.matrix_world.copy()
            for h, d in self.halves:
                h.hide_render = h.hide_viewport = not cut
                h.matrix_world = self._half_at(W0, d, (t - self.split_ev["f"]) / hits.FPS) if cut else W0
        if self.crack_ev:
            grown = (t - self.crack_ev["f"]) / 7.0                   # it runs across the mask in seven frames
            if grown > 0.0 and self.crack is None:
                self._build_crack(t)
            if self.crack is not None:
                C = self.crack
                C["ob"].hide_render = grown <= 0.0
                n = len(C["quads"]) if grown >= 1.0 else max(1, int(math.ceil(C["main"] * grown)))
                me = C["ob"].data
                if len(me.polygons) != n:
                    me.clear_geometry()
                    me.from_pydata(C["verts"], [], C["quads"][:n])
                    me.update()

    def _flame(self, t):
        ev, A = self.flame_ev, self.cast["oni"]
        sw = A.swords["main"]
        env = _smooth((t - ev["f0"]) / 10.0) * (1.0 - _smooth((t - (ev["f1"] - 12.0)) / 12.0))
        if env <= 0.0:
            _fill(self.flame, [], [])
            self.flame_light.data.energy = 0.0
            return
        L = sw.spec["blade"]

        def blade(tt):
            tt = min(max(tt, 0.0), A.frames - 1.0)
            i = int(math.floor(tt))
            return motion._mix4(A.sword_m["main"][i], A.sword_m["main"][min(i + 1, A.frames - 1)], tt - i)

        verts, faces, uvs = [], [], []
        N, dt = 14, 0.16                                             # a trail a little over two take frames long
        rows = [(M @ Vector(sw.arc(0.10)), M @ Vector(sw.arc(L - 0.005))) for M in (blade(t - k * dt) for k in range(N + 1))]
        for k in range(N):
            (a0, b0), (a1, b1) = rows[k], rows[k + 1]
            if (b1 - b0).length < 0.004:                             # the blade is still: no trail
                continue
            i = len(verts)
            verts += [tuple(a0), tuple(b0), tuple(b1), tuple(a1)]
            faces.append((i, i + 1, i + 2, i + 3))
            v0, v1 = 0.12 + 0.88 * k / N, 0.12 + 0.88 * (k + 1) / N
            uvs += [(0.0, v0), (1.0, v0), (1.0, v1), (0.0, v1)]
        M = blade(t)
        for j in range(20):                                          # tongues of flame standing on the blade
            s = 0.08 + j * (L - 0.10) / 19.0
            p = M @ Vector(sw.arc(s))
            along = (M @ Vector(sw.arc(s + 0.02)) - p).normalized()
            h = env * (0.045 + 0.085 * (0.5 + 0.5 * math.sin(t * 2.3 + j * 1.9)) * (0.6 + 0.4 * math.sin(t * 1.13 + j * 0.7)))
            lean = along * (0.012 * math.sin(t * 1.7 + j * 2.3))
            i = len(verts)
            verts += [tuple(p - along * 0.024), tuple(p + along * 0.024), tuple(p + Z * h + lean)]
            faces.append((i, i + 1, i + 2))
            uu = 0.3 + 0.7 * j / 19.0
            uvs += [(uu - 0.03, 0.0), (uu + 0.03, 0.0), (uu, 1.0)]
        _fill(self.flame, verts, faces, uvs)
        self.flame_light.location = M @ Vector(sw.arc(L * 0.55))
        self.flame_light.data.energy = 260.0 * env
        gain = flame_mat().node_tree.nodes.get("gain")
        if gain is not None:
            gain.inputs[1].default_value = 14.0 * (0.4 + 0.6 * env)
