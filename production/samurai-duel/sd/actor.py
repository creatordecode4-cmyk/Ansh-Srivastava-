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
from mathutils.bvhtree import BVHTree

from . import cache, core, fighters, motion, weapons
from . import clear as clr
from .puppet import EASE, I3, SHAPES, Puppet, Y, ease, mix_shapes, perp, slerp, sword_matrix, ypr
from .skin import Skin

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
        inv = ob.matrix_world.inverted()                                    # tassels hang from the sword: where, in the sword's own space
        self.tassels = [(c, inv @ c.matrix_world.translation) for c in ob.children]
        inv = saya.matrix_world.inverted()
        self.saya_tassels = [(c, inv @ c.matrix_world.translation) for c in saya.children]
        self.rest_world = arm.matrix_world.inverted() @ (saya.matrix_world @ self.flip)   # the scabbard at rest, standard axes, armature space
        self.length = spec["blade"] + 0.02
        self.carry = None                                                   # how the scabbard rides on the body (set by the actor)

    def arc(self, s):
        """Point on the sword's and scabbard's shared arc at distance s from the guard (standard axes)."""
        return tuple(weapons.frame(s, self.R)[0])

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
        # the body as a solid, and what must stay out of it
        self.skin = Skin(self.proxy, self.pp)
        for sw in self.swords.values():
            sw.carry = clr.Scabbard(self.skin, sw.rest_world, sw.arc, sw.length, "hip" if who == "oni" else "back",
                                    gap=0.022 if who == "oni" else 0.017)      # his trousers swing: more room
        self.hat = None
        if self.F.get("hat") is not None:
            spec = self.F["hat_spec"]
            pos = self.arm.matrix_world.inverted() @ self.F["hat"].matrix_world.translation
            self.hat = dict(pos=pos, pts=clr.hat_points(spec["radius"], spec["rise"]), solid=clr.Hat(self.pp, pos, spec))
        self.arm_gap = 0.02 if who == "oni" else 0.03                        # the Ronin's hands must also clear the cloth on his hips
        self.pre, self.poses, self.saya_local, self.report = [], [], {}, {}

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
            return sp["sheath"] @ sw.slid(key.get("d", 0.0))
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
    def perform(self, take, swords=None, holds=(), start=61, name=None, report=True, clear=True, steer=None):
        """Bake a shot.

        take    body motion as world controls, one per frame (sd/motion.py)
        swords  {sword key: [track keys]}; a key is dict(f=frame in the take, space='sheath'|'chest'|'hips'|'world',
                d=metres drawn (sheath) or m=4x4 matrix, ease=..., line=True for a straight move)
        holds   [dict(sword=key, hand='Right'|'Left', f0, f1 (frames it is fully closed on the grip), blend_in, blend_out,
                along=fist behind the guard (negative: on the scabbard side), roll=degrees round the handle,
                flip=True for thumb toward the pommel, lead=True for the hand the sword follows,
                plan=1.0: the sword's track leads the hand; 0.0: the hand carries the sword,
                on='saya': the hand holds the scabbard, and stays on it when the sword is drawn,
                free_blend=True: on its way to and from the grip the hand is kept out of the body like a free hand)]
                A hold without 'sword' puts a hand on the hat: dict(hat=(x, y, z) of the wrist in the hat's
                space, hand=, f0, f1, blend_in, blend_out, fingers=(x, y, z) the way the fingers point and
                back=(x, y, z) the way the back of the hand faces, both in the hat's space, shape=hand shape)
        clear   keep hands, scabbards, hat and tassels out of the body (sd/clear.py). False bakes the
                motion as it comes, which is only useful to measure what the clearing changes.
        steer   {sword key: [(take frame, yaw, pitch)]}: a scabbard worn in the belt turned by the hand
                that holds it (degrees in the pelvis's frame, eased between the keys)"""
        pp, skin = self.pp, self.skin
        n = len(take)
        self.start, self.frames = start, n
        swords = swords or {}
        Tobj = self.arm.matrix_world.copy()
        Tinv = Tobj.inverted()
        Rinv = Tobj.to_3x3().inverted()
        tinv = -(Rinv @ Tobj.translation)
        # 1. the body alone: where trunk and legs are on every frame
        poses = [pp.solve(motion.moved(dict(c), Rinv, tinv)) for c in take.c]
        posed = skin.frames(list(poses))                                # the body before the arms are touched (the list is kept as it is now)
        # 2. scabbards: on the back between two points of the skin, or hanging from the belt and pushed aside by the leg
        saya = {}

        def turned(key, f):
            ks = (steer or {}).get(key)
            if not ks:
                return None
            if f <= ks[0][0]:
                y, p = ks[0][1:]
            elif f >= ks[-1][0]:
                y, p = ks[-1][1:]
            else:
                i = max(j for j in range(len(ks) - 1) if ks[j][0] <= f)
                u = EASE["inout"]((f - ks[i][0]) / (ks[i + 1][0] - ks[i][0]))
                y, p = (ks[i][1] + (ks[i + 1][1] - ks[i][1]) * u, ks[i][2] + (ks[i + 1][2] - ks[i][2]) * u)
            return ypr(y, p, 0.0) if (y or p) else None

        for key, sw in self.swords.items():
            sw.carry.prev = None
            if clear:
                saya[key] = [sw.carry.frame(posed[f], poses[f]["D"]["Hips"], turned(key, f)) for f in range(n)]
            else:
                saya[key] = [pp.bone_matrix(poses[f], sw.bone) @ sw.rest for f in range(n)]
        self.saya_local = saya
        # 3. swords as planned, hands onto the grips
        final = []
        planned = {k: [None] * n for k in self.swords}
        held = [dict(Left=False, Right=False) for _ in range(n)]
        for f in range(n):
            c = dict(take.c[f])
            sp = self._spine(c)
            sheath = {}
            for key, sw in self.swords.items():
                sp["sheath"] = sheath[key] = Tobj @ saya[key][f]
                tr = swords.get(key)
                planned[key][f] = self._track(sw, tr, f, sp) if tr else sp["sheath"]
            for h in holds:
                wh = _ramp(f, h["f0"] - h.get("blend_in", 8), h["f0"]) * (1.0 - _ramp(f, h["f1"], h["f1"] + h.get("blend_out", 8)))
                if wh <= 0.0:
                    continue
                tag, s = h["hand"], h["hand"][0]
                if "hat" in h:                                           # a hand on the hat: placed in the hat's own space, so it rides with the head
                    held[f][tag] = True
                    wrist, Dhand = self._on_hat(tag, poses[f], Tobj, h)
                    bw = self._hand_world(c, tag, sp)
                    c["hand_" + s] = dict(pos=bw[0].lerp(wrist, wh), D=slerp(bw[1], Dhand, wh) if bw[1] is not None else Dhand)
                    if h.get("elbow") is not None:
                        c["elbow_" + s] = sp["chest"].to_3x3() @ Vector(h["elbow"])
                    c["fingers_" + s] = mix_shapes(c["fingers_" + s], h.get("shape", "relaxed"), wh)
                    continue
                sw = self.swords[h["sword"]]
                wp = wh * h.get("plan", 1.0)
                if wp > 0.0:
                    held[f][tag] = held[f][tag] or wp >= 0.999 or not h.get("free_blend")
                    target = sheath[h["sword"]] if h.get("on") == "saya" else planned[h["sword"]][f]
                    wrist, Dhand = self._grip(tag, target, h.get("along", 0.058), h.get("roll", 0.0), sw.R, h.get("flip", False))
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
        local = [motion.moved(c, Rinv, tinv) for c in final]
        poses = [pp.solve(c) for c in local]
        # 4. the hat brim clear of shoulders and sword grips; arms out of body and hat; carried blades off the body
        stats = dict(arm_push=0.0, elbow_turn=0.0, hat_tilt_kept=1.0, blade_left=0.0)
        if clear:
            hat = self.hat["solid"] if self.hat else None
            if self.hat:
                grips = []
                for f in range(n):
                    seg = []
                    for key, sw in self.swords.items():
                        m = Tinv @ planned[key][f]
                        seg.append((np.array(m.translation), np.array(m @ Vector(sw.arc(-sw.spec["grip"] - 0.02))), 0.024))
                    grips.append(seg)
                stats["hat_tilt_kept"] = clr.hat(pp, posed, poses, self.hat["pos"], self.hat["pts"], grips, controls=local)
            free = [dict(Left=not held[f]["Left"], Right=not held[f]["Right"]) for f in range(n)]
            stats["arm_push"], stats["elbow_turn"] = clr.arms(pp, skin, posed, local, poses, free, gap=self.arm_gap, hat=hat)
            carry = {}
            for h in holds:
                if "sword" in h and h.get("plan", 1.0) <= 0.0 and h.get("lead", True):
                    carry[h["hand"]] = h
            if carry:
                carried = [{tag: h["sword"] for tag, h in carry.items() if h["f0"] <= f <= h["f1"]} for f in range(n)]

                def blade_of(pose, tag, key):
                    h, sw = carry[tag], self.swords[key]
                    W = self._ungrip(tag, pp.heads(pose)[tag + "Hand"], pose["D"][tag + "Hand"], h.get("along", 0.058), h.get("roll", 0.0), sw.R, h.get("flip", False))
                    return np.array([W @ Vector(sw.arc(t)) for t in np.linspace(0.04, sw.spec["blade"], 10)])

                stats["blade_left"] = clr.blades(pp, skin, posed, local, poses, carried, blade_of, hat=hat)
            posed = skin.frames(poses)
            # 5. the scabbards once more: moving the arms moved the shoulders they lie on
            for key, sw in self.swords.items():
                sw.carry.prev = None
                saya[key] = [sw.carry.frame(posed[f], poses[f]["D"]["Hips"], turned(key, f)) for f in range(n)]
            for f in range(n):
                sp = self._spine(final[f])
                for key, sw in self.swords.items():
                    sp["sheath"] = Tobj @ saya[key][f]
                    tr = swords.get(key)
                    planned[key][f] = self._track(sw, tr, f, sp) if tr else sp["sheath"]
        # 6. swords: read back from the lead hand where one is closed on the grip, else as planned
        miss = {}
        sword_m = {k: [None] * n for k in self.swords}
        for key, sw in self.swords.items():
            for f in range(n):
                W = planned[key][f]
                for h in holds:
                    if h.get("sword") != key or not h.get("lead", True) or h.get("on") == "saya" or not (h["f0"] <= f <= h["f1"]):
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
        # 7. run-up: rest pose, then into the first pose of the shot
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
        self.pre, self.poses, self.sword_m, self.controls, self.planned = pre, poses, sword_m, final, planned
        self.posed = posed if clear else skin.frames(poses)
        lead_in = start - 1

        def hang(mats, at):                                             # a tassel is a weight on a cord: it hangs, swings and stops at the body
            anchors = [Tinv @ (m @ at) for m in mats]
            sk = skin.frames([poses[0]] * lead_in + poses) if clear else None
            return [Tobj @ m for m in clr.pendulum(anchors, sk)]

        for key, sw in self.swords.items():
            mats = [sword_m[key][0] @ sw.flip] * lead_in + [m @ sw.flip for m in sword_m[key]]
            _key_object(sw.ob, frames, mats, self.arm)
            for tassel, at in sw.tassels:
                _key_object(tassel, frames, hang(mats, at), self.arm)
            mats = [Tobj @ saya[key][0] @ sw.flip] * lead_in + [Tobj @ m @ sw.flip for m in saya[key]]
            _key_object(sw.saya, frames, mats, self.arm)
            for tassel, at in sw.saya_tassels:
                _key_object(tassel, frames, hang(mats, at), self.arm)
        short_f = max([v for p in poses for k, v in p["short"].items() if "Foot" in k] or [0.0])
        short_h = max([v for p in poses for k, v in p["short"].items() if "Hand" in k] or [0.0])
        self.report = dict(stats, legs_short=short_f, arms_short=short_h, sword_miss=dict(miss))
        if report:
            print(f"  {self.who}: {n} frames baked from {start}; legs short by {short_f * 1000:.1f} mm, arms short by {short_h * 1000:.1f} mm, "
                  f"swords off their marks by {({k: round(v * 1000, 1) for k, v in miss.items()} or 0)} mm"
                  + (f"; hands moved out by up to {stats['arm_push'] * 100:.1f} cm, elbows turned up to {stats['elbow_turn']:.0f} deg, "
                     f"hat kept {stats['hat_tilt_kept'] * 100:.0f} % of its tilt at worst" if clear else ""))
        return poses

    def clip_report(self, frames=None):
        """What still passes through what in the baked shot (before cloth): worst overlap in millimetres
        per kind of contact, 0 meaning clear. An overlap is how far one surface is inside the other.
        frames limits the report to some take frames (those a film actually shows).
        arm_in_hat is measured against the hat and the space over it (clear.Hat.above); blade_in_hat
        is the length of blade that has gone through the hat, or how far a blade presses into it."""
        pp, skin, n = self.pp, self.skin, self.frames
        Tinv = self.arm.matrix_world.inverted()
        out = dict(arm_in_body=0.0, arm_in_arm=0.0, scabbard_in_body=0.0, hat_in_body=0.0, strap_in_body=0.0, hat_in_grip=0.0, arm_in_hat=0.0, blade_in_body=0.0, blade_in_arm=0.0, blade_in_hat=0.0)
        hat = self.hat["solid"] if self.hat else None
        frames = [f for f in (range(n) if frames is None else frames) if 0 <= f < n]
        for f in frames:
            posed, pose = self.posed[f], self.poses[f]
            at = hat.at(pose) if hat else None
            for tag in ("Left", "Right"):
                pts = clr.arm_points(pp, skin, pose, tag)
                d, _, _ = posed.signed([p for _, p, _ in pts], "body")
                out["arm_in_body"] = max(out["arm_in_body"], float((np.array([r for _, _, r in pts]) - d).max()))
                chain = clr.arm_chain(pp, skin, pose, tag, upper=True)
                if hat:
                    sd, _ = hat.above(hat.local(at, [p for _, p, _ in chain]))
                    out["arm_in_hat"] = max(out["arm_in_hat"], float((np.array([r for _, _, r in chain]) - sd).max()))
                fore = [q for q in chain if q[0] in ("forearm", "elbow", "upper")]      # one arm through the other (the fists may meet on a grip)
                d, _, _ = posed.signed([p for _, p, _ in fore], "right_arm" if tag == "Left" else "left_arm")
                over = (np.array([r for _, _, r in fore]) - d)[d > -0.09]
                if len(over):
                    out["arm_in_arm"] = max(out["arm_in_arm"], float(over.max()))
            for key, sw in self.swords.items():
                m = self.saya_local[key][f]
                pts = sw.carry.local @ np.array(m.to_3x3()).T + np.array(m.translation)
                d, _, _ = posed.signed(pts[2:], "body")
                out["scabbard_in_body"] = max(out["scabbard_in_body"], float((0.018 - d).max()))
                W = Tinv @ self.sword_m[key][f]
                if (W.translation - m.translation).length > 0.05:        # drawn: the blade against the fighter's own body, arms and hat
                    blade = np.array([W @ Vector(sw.arc(t)) for t in np.linspace(0.05, sw.spec["blade"], 12)])
                    d, _, _ = posed.signed(blade, "body")
                    out["blade_in_body"] = max(out["blade_in_body"], float((0.012 - d).max()))
                    line = clr.dense(blade)
                    for side in ("left_arm", "right_arm"):               # beyond the hands that hold it
                        d, _, _ = posed.signed(line[10:], side)
                        d = d[d > -0.07]                                  # deeper than an arm is thick: the side test has failed, not the blade
                        if len(d):
                            out["blade_in_arm"] = max(out["blade_in_arm"], float((0.004 - d).max()))
                    if hat:
                        L = hat.local(at, line)
                        k = hat.crossing(L)
                        through = float(np.linalg.norm(np.diff(line[k:], axis=0), axis=1).sum()) if k is not None else 0.003 - float(hat.shell(L).min())
                        out["blade_in_hat"] = max(out["blade_in_hat"], through)
            if self.hat:
                P = clr.brim_points(pp, pose, self.hat["pos"], self.hat["pts"])
                d, _, _ = posed.signed(P, "trunk")
                out["hat_in_body"] = max(out["hat_in_body"], float((-d).max()))
                d, _, _ = posed.signed(clr.brim_points(pp, pose, self.hat["pos"], hat.strap_points()), "all")
                out["strap_in_body"] = max(out["strap_in_body"], float((hat.strap_r - d).max()))
                for key, sw in self.swords.items():
                    W = Tinv @ self.planned[key][f]
                    a, b = np.array(W.translation), np.array(W @ Vector(sw.arc(-sw.spec["grip"] - 0.02)))
                    ab = b - a
                    t = np.clip(((P - a) @ ab) / float(ab @ ab), 0.0, 1.0)
                    out["hat_in_grip"] = max(out["hat_in_grip"], float((0.024 - np.linalg.norm(P - (a + t[:, None] * ab), axis=1)).max()))
        # one leg of the trousers inside the other
        L, R = np.flatnonzero(skin.region["left_leg"])[::6], np.flatnonzero(skin.region["right_leg"])[::6]
        legs = 0.0
        for f in frames[::2]:
            posed = self.posed[f]
            for mine, other in ((L, "right_leg"), (R, "left_leg")):
                d, _, _ = posed.signed(posed.P[mine], other)
                d = d[(d < 0.9) & (d > -0.08)]                        # only near the other leg: the side test means nothing for points far away
                if len(d):
                    legs = max(legs, float((-d).max()))
        out["leg_in_leg"] = legs
        return {k: round(max(0.0, v) * 1000, 1) for k, v in out.items()}

    def _on_hat(self, tag, pose, Tobj, h):
        """World wrist position and hand rotation for a hand placed on the hat (see perform)."""
        pp, hat = self.pp, self.hat["solid"]
        hd = pp.hand[tag]
        D, head = pose["D"]["Head"], pp.heads(pose)["Head"]
        R = Tobj.to_3x3() @ D
        wrist = Tobj @ (head + D @ (Vector(h["hat"]) + Vector(hat.off)))
        a = (R @ Vector(h.get("fingers", (0, 0, 1)))).normalized()          # the way the fingers point
        nb = perp(R @ Vector(h.get("back", (0, -1, 0))), a)                  # the way the back of the hand faces
        rest = Matrix((hd["a"], hd["n"].cross(hd["a"]), hd["n"])).transposed()
        now = Matrix((a, nb.cross(a), nb)).transposed()
        return wrist, now @ rest.inverted()

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


def simulate(sc, actors, folder, end=None, report=40, clear=True):
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
    faces = {}
    for f in range(1, end + 2):
        sc.frame_set(f)
        if f >= first:
            dg = bpy.context.evaluated_depsgraph_get()
            for ob in panels:
                me = ob.evaluated_get(dg).data
                co = np.empty(len(me.vertices) * 3, dtype=np.float32)
                me.vertices.foreach_get("co", co)
                rec[ob.name].append(co)
                if ob.name not in faces:
                    faces[ob.name] = [tuple(p.vertices) for p in me.polygons]
        if report and f % report == 0:
            print(f"    cloth frame {f}/{end + 1}", flush=True)
    # trousers that are part of the body: the two legs may press together but not pass through each other
    for a in actors:
        for ob in a.cloth:
            if "Cage" not in ob.name or not a.poses or not clear:
                continue
            rest = np.empty(len(ob.data.vertices) * 3, dtype=np.float32)
            ob.data.vertices.foreach_get("co", rest)
            rest = rest.reshape(-1, 3).astype(np.float64)
            moved = 0
            for i, fr in enumerate(range(first, end + 2)):
                k = fr - a.start
                pose = a.pre[-1] if k < 0 else a.poses[min(a.frames - 1, k)]
                X = rec[ob.name][i].reshape(-1, 3).astype(np.float64)
                moved += clr.part_legs(X, rest, pose, a.pp)
                rec[ob.name][i] = X.astype(np.float32).reshape(-1)
            a.report["trouser_legs_parted"] = moved
            print(f"  {a.who} trousers: {moved} cage points over the shot were through the other leg and were put back on their own side", flush=True)
    # whatever the collision let through is put back: no cloth inside the body, none through a scabbard
    for a in actors:
        mine = [ob for ob in a.cloth if "Cage" not in ob.name]
        if not mine or not a.poses or not clear:
            continue
        before, deepest, left = 0, 0.0, 0
        total = sum(len(rec[ob.name][0]) // 3 for ob in mine) * len(rec[mine[0].name])
        Tinv = a.arm.matrix_world.inverted()
        cut = []                                                        # shot frames on which a drawn blade passes through a cloth panel
        hat, in_hat = (a.hat["solid"] if a.hat else None), 0
        for i, fr in enumerate(range(first, end + 2)):
            k = fr - a.start
            pose = a.pre[-1] if k < 0 else a.poses[min(a.frames - 1, k)]
            posed = a.skin.pose(pose)
            segs, drawn = [], []
            if k >= 0:
                kk = min(a.frames - 1, k)
                for key, sw in a.swords.items():
                    m = a.saya_local[key][kk]
                    pts = sw.carry.local @ np.array(m.to_3x3()).T + np.array(m.translation)
                    segs += [(pts[j], pts[j + 1], 0.019) for j in range(len(pts) - 1)]
                    W = Tinv @ a.sword_m[key][kk]
                    if (W.translation - m.translation).length > 0.05:
                        drawn.append([W @ Vector(sw.arc(t)) for t in np.linspace(0.05, sw.spec["blade"], 12)])
            for ob in mine:
                X = rec[ob.name][i].reshape(-1, 3).astype(np.float64)
                n_bad, deep = clr.depenetrate(X, posed, gap=0.004)
                before += n_bad
                deepest = max(deepest, deep)
                if segs:
                    clr.out_of_capsules(X, segs)
                    clr.depenetrate(X, posed, gap=0.004)
                if hat:                                                  # cloth that came up through the brim goes back under it
                    at = hat.at(pose)
                    sd, g = hat.above(hat.local(at, X))
                    up = sd < 0.002
                    if up.any():
                        in_hat += int(up.sum())
                        X[up] += (g[up] * (0.004 - sd[up])[:, None]) @ at[0].T
                d, _, _ = posed.signed(X, "all")
                left += int((d < -0.001).sum())
                rec[ob.name][i] = X.astype(np.float32).reshape(-1)
                if drawn and k not in cut:                               # a blade is planned, not pushed: this only reports
                    tree = BVHTree.FromPolygons(X.tolist(), faces[ob.name])
                    if any(tree.ray_cast(p, (q - p).normalized(), (q - p).length)[0] is not None for line in drawn for p, q in zip(line[:-1], line[1:])):
                        cut.append(k)
        a.report["cloth"] = dict(points=total, inside_before=before, deepest_mm=round(deepest * 1000, 1), inside_after=left, blade_frames=cut, in_hat=in_hat)
        print(f"  {a.who} cloth: {before} of {total} points were inside the body or too close (deepest {deepest * 1000:.0f} mm); after putting them back: {left}"
              + (f"; {in_hat} points had come up through the hat" if hat else ""), flush=True)
        if any(len(m) for m in a.sword_m.values()):
            print(f"  {a.who} blades through cloth: {len(cut)} frames" + (f" (shot frames {cut})" if cut else ""), flush=True)
    files = []
    for ob in panels:
        path = os.path.join(folder, f"{ob.name}.pc2")
        cache.write_pc2(path, np.stack(rec[ob.name]).reshape(len(rec[ob.name]), -1, 3))
        cache.playback(ob, path, first)
        files.append(path)
    for a in actors:
        a.body.hide_viewport = hidden[a.who]
    return files


def replay(actors, folder):
    """Play the cloth of all actors back from a folder that simulate() filled earlier (same takes).
    Returns False, changing nothing, if a file is missing."""
    panels = [ob for a in actors for ob in a.cloth]
    paths = [os.path.join(folder, f"{ob.name}.pc2") for ob in panels]
    if not panels or not all(os.path.exists(p) for p in paths):
        return False
    for ob, path in zip(panels, paths):
        cache.playback(ob, path, actors[0].start - 1)
    return True


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
