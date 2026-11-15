"""A fighter on set: skeleton, swords and cloth driven by a take.

    a = Actor("oni", lib, col)
    a.place((x, y), facing)                  where the fighter stands when the shot begins
    a.perform(take, swords=..., holds=...)   bake body, hands and swords for the shot
    a.simulate(scene)                        run the cloth over the shot and store it on disk

Frames. A shot's own frames start at 'start' (61 by default). The frames before it are a run-up
nobody sees: the fighter stands in the rest pose, where the cloth hangs as it was draped, then
moves into the first pose of the shot and the cloth settles. The armature object itself is put
where the shot begins, so the run-up happens on the spot.

Swords. A sword is either put somewhere (a track: in its scabbard, relative to the chest or
hips, or in the world) and the hands go to its grip, or it is carried by a hand that moves with
the body. Either way, once a hand has closed on the grip the sword's final place is read back
from that hand, so a sword can never float out of the fist; if the arm could not reach, the
report says by how much the sword missed its mark.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import cache, core, fighters, motion, weapons
from .puppet import EASE, I3, SHAPES, Puppet, Y, ease, mix_shapes, slerp, sword_matrix, ypr

def _ramp(f, a, b):
    """0 before a, 1 after b, smooth between."""
    if b <= a:
        return 1.0 if f >= b else 0.0
    return EASE["inout"](min(1.0, max(0.0, (f - a) / (b - a))))


class Sword:
    """One katana of an actor: its object, where it rests in its scabbard, and its drawing arc."""

    def __init__(self, actor, key, ob, saya, bone, spec):
        self.key, self.ob, self.saya, self.bone, self.spec = key, ob, saya, bone, spec
        self.R = weapons.radius(spec)
        self.flip = Matrix.Rotation(math.pi, 4, "Y") if ob.get("edge", -1.0) > 0 else Matrix.Identity(4)   # mirror-image twin: edge on +Z
        arm = actor.arm
        bone_rest = arm.matrix_world @ arm.data.bones["mixamorig:" + bone].matrix_local
        self.rest = bone_rest.inverted() @ (ob.matrix_world @ self.flip)      # sheathed, in the bone's frame, as a standard sword (edge on -Z)
        self.tassels = [c for c in ob.children]

    def slid(self, d):
        """Standard-frame offset that slides the sword d metres out of the scabbard along their shared arc."""
        c = Matrix.Translation((0, 0, self.R))
        return c @ Matrix.Rotation(-d / self.R, 4, "X") @ c.inverted()


class Actor:
    def __init__(self, who, lib, col, cloth=True, arms_collide=False):
        self.who = who
        self.F = fighters.ronin(lib, col, rigged=True, cloth=cloth, arms_collide=arms_collide) if who == "ronin" else fighters.oni(lib, col, rigged=True)
        self.arm, self.body, self.proxy = self.F["arm"], self.F["body"], self.F["proxy"]
        self.collider = self.F.get("collider", self.proxy)
        with open(os.path.join(core.ASSETS, "gen", f"{who}_rig.json")) as fh:
            self.pp = Puppet(self.arm, json.load(fh)["hands"])
        bpy.context.view_layer.update()
        self.swords = {}
        if who == "oni":
            self.swords["main"] = Sword(self, "main", self.F["katana"], self.F["saya"], "Hips", weapons.ONI)
        else:
            for ks, ss in zip(self.F["katanas"], self.F["sayas"]):
                self.swords[ks["hand"][0]] = Sword(self, ks["hand"][0], ks, ss, "Spine2", weapons.RONIN)
        self.cloth = list(self.F.get("sim", []))
        if who == "oni" and cloth:                                       # his trousers are part of the body mesh: a soft cage moves them
            from . import soft
            with open(os.path.join(core.ASSETS, "gen", f"{who}_rig.json")) as fh:
                J = json.load(fh)["joints"]
            self.cloth.append(soft.hakama(self.arm, self.body, self.proxy, J, col))
        self.start = 61
        self.frames = 0

    # ---- where the shot begins
    def place(self, at=(0.0, 0.0), facing=0.0):
        self.arm.location = (at[0], at[1], 0.0)
        self.arm.rotation_euler = (0.0, 0.0, math.radians(facing))
        bpy.context.view_layer.update()
        return self

    # ---- frames of the body the swords can be tied to
    def _spine(self, c):
        """World matrices of the spine bones for one set of world controls."""
        pp = self.pp
        Dh, Dc = c["hips_D"], c["chest_D"]
        D = dict(Hips=Dh, Spine=slerp(Dh, Dc, 0.3), Spine1=slerp(Dh, Dc, 0.65), Spine2=Dc)
        head = {"Hips": c["hips"].copy()}
        prev = "Hips"
        for b in ("Spine", "Spine1", "Spine2"):
            head[b] = head[prev] + D[prev] @ (pp.H0[b] - pp.H0[prev])
            prev = b
        out = {}
        for b in D:
            m = (D[b] @ pp.R0[b]).to_4x4()
            m.translation = head[b]
            out[b] = m
        for b, name in (("Spine2", "chest"), ("Hips", "hips")):          # 'as if in the rest pose' frames, carried by the body
            m = D[b].to_4x4()
            m.translation = head[b] - D[b] @ pp.H0[b]
            out[name] = m
        return out

    def _sword_world(self, sw, key, sp):
        """Standard-frame world matrix for one track key at the body state sp."""
        space = key.get("space", "world")
        if space == "sheath":
            return sp[sw.bone] @ sw.rest @ sw.slid(key.get("d", 0.0))
        if space in ("chest", "hips"):
            return sp[space] @ key["m"]
        return key["m"]

    def _track(self, sw, keys, f, sp):
        """Standard-frame world matrix of a sword at frame f (keys sorted by frame)."""
        if f <= keys[0]["f"]:
            return self._sword_world(sw, keys[0], sp)
        if f >= keys[-1]["f"]:
            return self._sword_world(sw, keys[-1], sp)
        i = max(k for k in range(len(keys) - 1) if keys[k]["f"] <= f)
        k0, k1 = keys[i], keys[i + 1]
        u = ease(k1.get("ease", "inout"), (f - k0["f"]) / (k1["f"] - k0["f"]))
        W = [self._sword_world(sw, keys[min(len(keys) - 1, max(0, j))], sp) for j in (i - 1, i, i + 1, i + 2)]
        p = [w.translation for w in W]
        if k1.get("line") or k0.get("space") == "sheath" and k1.get("space") == "sheath":
            pos = p[1].lerp(p[2], u)
        else:                                                            # through the keys on a smooth curve
            u2, u3 = u * u, u * u * u
            pos = 0.5 * ((2 * p[1]) + (-p[0] + p[2]) * u + (2 * p[0] - 5 * p[1] + 4 * p[2] - p[3]) * u2 + (-p[0] + 3 * p[1] - 3 * p[2] + p[3]) * u3)
        m = W[1].to_quaternion().slerp(W[2].to_quaternion(), u).to_matrix().to_4x4()
        m.translation = pos
        return m

    def _ungrip(self, tag, wrist, Dhand, along, roll, R, flip=False):
        """The sword that a closed hand holds (standard-frame world matrix): inverse of _grip."""
        station, St = self.pp.ungrip(tag, wrist, Dhand, roll, flip)
        th = -along / R                                                   # the handle follows the sword's arc: back from the fist to the guard
        S = St @ Matrix.Rotation(-th, 3, "X")
        m = S.to_4x4()
        m.translation = station - S @ Vector((0.0, R * math.sin(th), R * (1.0 - math.cos(th))))
        return m

    def _grip(self, tag, W, along, roll, R, flip=False):
        """Wrist position and hand rotation that hold standard-frame sword W with the fist 'along' behind the guard."""
        th = -along / R
        S = W.to_3x3()
        station = W.translation + S @ Vector((0.0, R * math.sin(th), R * (1.0 - math.cos(th))))
        return self.pp.grip(tag, S @ Matrix.Rotation(th, 3, "X"), station, roll=roll, flip=flip)

    def sword_key(self, f, controls, guard, point, edge, space="chest", ease="inout", **more):
        """A track key that puts a sword where it is described in the world for the pose 'controls'
        (guard position, direction of the point, direction of the edge), stored relative to the
        chest or hips so that it travels with the body, or left in the world."""
        W = sword_matrix(guard, point, edge)
        if space in ("chest", "hips"):
            W = self._spine(self.pp.canon(controls))[space].inverted() @ W
        return dict(f=f, space=space, m=W, ease=ease, **more)

    # ---- the performance
    def perform(self, take, swords=None, holds=(), start=61, name=None, report=True):
        """Bake a shot.

        take    body motion as world controls, one per frame (sd/motion.py)
        swords  {sword key: [track keys]}; a key is dict(f=frame in the take, space='sheath'|'chest'|'hips'|'world',
                d=metres drawn (sheath) or m=4x4 matrix, ease=..., line=True for a straight move)
        holds   [dict(sword=key, hand='Right'|'Left', f0, f1 (frames it is fully closed on the grip), blend_in, blend_out,
                along=fist behind the guard (negative: on the scabbard side), roll=degrees round the handle,
                flip=True for thumb toward the pommel, lead=True for the hand the sword follows,
                plan=1.0: the sword's track leads the hand; 0.0: the hand carries the sword)]"""
        pp = self.pp
        n = len(take)
        self.start, self.frames = start, n
        swords = swords or {}
        Tobj = self.arm.matrix_world.copy()
        Rinv = Tobj.to_3x3().inverted()
        tinv = -(Rinv @ Tobj.translation)
        final, sword_m = [], {k: [None] * n for k in self.swords}
        planned = {k: [None] * n for k in self.swords}
        for f in range(n):
            c = dict(take.c[f])
            sp = self._spine(c)
            for key, sw in self.swords.items():
                tr = swords.get(key)
                planned[key][f] = self._track(sw, tr, f, sp) if tr else sp[sw.bone] @ sw.rest
            for h in holds:
                wh = _ramp(f, h["f0"] - h.get("blend_in", 8), h["f0"]) * (1.0 - _ramp(f, h["f1"], h["f1"] + h.get("blend_out", 8)))
                if wh <= 0.0:
                    continue
                tag, s = h["hand"], h["hand"][0]
                sw = self.swords[h["sword"]]
                wp = wh * h.get("plan", 1.0)
                if wp > 0.0:
                    wrist, Dhand = self._grip(tag, planned[h["sword"]][f], h.get("along", 0.058), h.get("roll", 0.0), sw.R, h.get("flip", False))
                    base = c["hand_" + s]
                    if wp < 1.0:                                         # still on the way: between where the body had the hand and the grip
                        bw = self._hand_world(c, tag, sp)
                        wrist = bw[0].lerp(wrist, wp)
                        Dhand = slerp(bw[1], Dhand, wp) if bw[1] is not None else Dhand
                    c["hand_" + s] = dict(pos=wrist, D=Dhand)
                    if h.get("elbow") is not None:
                        c["elbow_" + s] = sp["chest"].to_3x3() @ Vector(h["elbow"])
                elif h.get("bend") is not None:                          # carried: the wrist is set so the blade points where it should
                    c["hand_" + s] = dict(c["hand_" + s], bend=ypr(*[v * wh for v in h["bend"]]))
                c["fingers_" + s] = mix_shapes(c["fingers_" + s], "grip", min(1.0, max(0.0, (wh - 0.55) / 0.45)))
            final.append(c)
        # solve in the armature's own space
        local = [motion.moved(c, Rinv, tinv) for c in final]
        poses = [pp.solve(c) for c in local]
        # swords: read back from the lead hand where one is closed on the grip, else as planned
        miss = {}
        for key, sw in self.swords.items():
            for f in range(n):
                W = planned[key][f]
                for h in holds:
                    if h["sword"] != key or not h.get("lead", True) or not (h["f0"] <= f <= h["f1"]):
                        continue
                    tag = h["hand"]
                    heads = pp.heads(poses[f])
                    wrist = Tobj @ heads[tag + "Hand"]
                    Dhand = Tobj.to_3x3() @ poses[f]["D"][tag + "Hand"]
                    A = self._ungrip(tag, wrist, Dhand, h.get("along", 0.058), h.get("roll", 0.0), sw.R, h.get("flip", False))
                    if h.get("plan", 1.0) > 0.0:
                        miss[key] = max(miss.get(key, 0.0), (A.translation - W.translation).length)
                    W = A
                    break
                sword_m[key][f] = W
        # run-up: rest pose, then into the first pose of the shot
        rest = dict(D={}, hips=pp.H0["Hips"].copy(), short={})
        pre = []
        for fr in range(1, start):
            w = _ramp(fr, start - 50, start - 18)
            if w <= 0.0:
                pre.append(rest)
            else:
                p0 = poses[0]
                pre.append(dict(D={b: slerp(I3, d, w) for b, d in p0["D"].items()}, hips=rest["hips"].lerp(p0["hips"], w), short={}))
        frames = list(range(1, start)) + [start + i for i in range(n)]
        act, slot = pp.write(name or f"{self.who}_shot", frames, pre + poses)
        pp.play(act, slot)
        self.poses, self.sword_m, self.controls = poses, sword_m, final
        for key, sw in self.swords.items():
            ob = sw.ob
            first = Tobj @ pp.bone_matrix(pre[0], sw.bone) @ sw.rest
            mats = [first if sword_m[key][0] is None else sword_m[key][0]] * (start - 1) + sword_m[key]
            _key_object(ob, frames, [m @ sw.flip for m in mats], self.arm)
        if report:
            short_f = max([v for p in poses for k, v in p["short"].items() if "Foot" in k] or [0.0])
            short_h = max([v for p in poses for k, v in p["short"].items() if "Hand" in k] or [0.0])
            print(f"  {self.who}: {n} frames baked from {start}; legs short by {short_f * 1000:.1f} mm, arms short by {short_h * 1000:.1f} mm, "
                  f"swords off their marks by {({k: round(v * 1000, 1) for k, v in miss.items()} or 0)} mm")
        return poses

    def _hand_world(self, c, tag, sp):
        """World wrist position (and hand rotation if given) of a body-driven hand control."""
        pp = self.pp
        h = c["hand_" + tag[0]]
        if "pos" in h:
            return h["pos"], h.get("D")
        sh, ua = tag + "Shoulder", tag + "Arm"
        Dc = c["chest_D"]
        A0 = sp["Spine2"].translation + Dc @ (pp.H0[sh] - pp.H0["Spine2"]) + Dc @ (pp.H0[ua] - pp.H0[sh])
        return A0 + Dc @ h["rel"], h.get("D")

    # ---- cloth
    def simulate(self, sc, folder, end=None, report=40):
        """Run this actor's cloth alone (see simulate() below)."""
        return simulate(sc, [self], folder, end, report)


def simulate(sc, actors, folder, end=None, report=40):
    """Run the cloth of all actors from frame 1 through the shot and store the shot's frames on disk (PC2).
    Afterwards the panels play back from those files and no longer simulate.

    The cloth settings stay as they were built for the whole run. Changing air drag or friction
    part-way (thick air to settle, thin air for the shot) was tried: Blender answers a changed
    setting with a jolt that throws every panel outward."""
    panels = [ob for a in actors for ob in a.cloth]
    if not panels:
        return []
    start = actors[0].start
    end = end or max(a.start + a.frames - 1 for a in actors)
    os.makedirs(folder, exist_ok=True)
    hidden = {a.who: a.body.hide_viewport for a in actors}
    for a in actors:
        a.body.hide_viewport = True                                      # no need to deform a million vertices while the cloth runs
    for ob in panels:
        cache.live(ob)
        cl = ob.modifiers["Cloth"]
        cl.point_cache.frame_start = 1
        cl.point_cache.frame_end = end + 2
    first = start - 1
    rec = {ob.name: [] for ob in panels}
    for f in range(1, end + 2):
        sc.frame_set(f)
        if f >= first:
            dg = bpy.context.evaluated_depsgraph_get()
            for ob in panels:
                me = ob.evaluated_get(dg).data
                co = np.empty(len(me.vertices) * 3, dtype=np.float32)
                me.vertices.foreach_get("co", co)
                rec[ob.name].append(co)
        if report and f % report == 0:
            print(f"    cloth frame {f}/{end + 1}", flush=True)
    files = []
    for ob in panels:
        path = os.path.join(folder, f"{ob.name}.pc2")
        cache.write_pc2(path, np.stack(rec[ob.name]).reshape(len(rec[ob.name]), -1, 3))
        cache.playback(ob, path, first)
        files.append(path)
    for a in actors:
        a.body.hide_viewport = hidden[a.who]
    return files


def _key_object(ob, frames, mats, arm):
    """Free an object from its parent and key its world transform on every frame."""
    ob.parent = None
    ob.rotation_mode = "QUATERNION"
    ad = ob.animation_data or ob.animation_data_create()
    act = bpy.data.actions.new(ob.name + "_shot")
    slot = act.slots.new(id_type="OBJECT", name=ob.name)
    bag = act.layers.new("Layer").strips.new(type="KEYFRAME").channelbag(slot, ensure=True)
    qs, ps = [], []
    for m in mats:
        q = m.to_quaternion()
        if qs and qs[-1].dot(q) < 0.0:
            q.negate()
        qs.append(q)
        ps.append(m.translation.copy())
    ft = [float(f) for f in frames]
    n = len(ft)

    def curve(path, index, values):
        fc = bag.fcurves.new(path, index=index)
        fc.keyframe_points.add(n)
        flat = [0.0] * (2 * n)
        flat[0::2] = ft
        flat[1::2] = values
        fc.keyframe_points.foreach_set("co", flat)
        fc.update()

    for i in range(3):
        curve("location", i, [p[i] for p in ps])
    for i in range(4):
        curve("rotation_quaternion", i, [q[i] for q in qs])
    ad.action = act
    ad.action_slot = slot
    ob.scale = (1, 1, 1)
