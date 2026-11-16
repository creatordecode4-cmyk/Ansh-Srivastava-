"""What the sound is laid to: the fight's events and, for every film frame, where the fighters' feet,
hands, heads and blade points are and where they sit in the picture. Nothing is rendered: both parts
are built and performed as for the film (without cloth), then read back.

    python3 -I tools/sound_events.py [--out out/sound/events.json]

events   the fight's EVENTS (sd/film.py) with film frames: clash (power), kick, splash, skid,
         flame, tear, hat_split, mask_crack
shots    name, first and last film frame of every shot
frames   per film frame: the time map's rate (take frames per film frame), the camera (position,
         look, lens) and per fighter the joints and blade points in the world, plus 'screen'
         (x from -1 left to 1 right, distance from the camera) for the chest
contacts per fighter the film frames on which a foot comes down (heel strike), with the foot and
         how fast the fighter was going
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

JOINTS = ("Hips", "Spine2", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    import bpy  # noqa: F401
    from mathutils import Vector
    from sd import actor, arena, core, film
    t0 = time.time()
    sc, cams = arena.build(detail=False, particles=False, verbose=False)
    lib = bpy.data.collections["PROPS_LIB"]
    cast = {who: actor.Actor(who, lib, core.collection(who.upper() + "_C"), cloth=False) for who in ("oni", "ronin")}
    parts, notes = film.fight(cast)
    for who, A in cast.items():
        take, swords, holds, steer = parts[who]
        h = take.c[0]["hips"]
        A.place((h.x, h.y), 0.0)
        A.perform(take, swords=swords, holds=holds, start=film.LEAD + 1, steer=steer, report=False)
    shots = film.shots(cast)
    print(f"built in {time.time() - t0:.0f} s", flush=True)
    names = list(cast["oni"].pp.heads(cast["oni"].poses[0]).keys())
    joints = [j for j in JOINTS if j in names]
    print("joints:", joints, "| all:", names[:40], flush=True)

    def tip(A, key, t):                                              # a blade's point at a (fractional) take frame
        sw = A.swords[key]
        i = int(math.floor(min(A.frames - 1.0, max(0.0, t))))
        j = min(A.frames - 1, i + 1)
        p = [A.sword_m[key][k] @ Vector(sw.arc(sw.spec["blade"])) for k in (i, j)]
        return p[0].lerp(p[1], min(1.0, max(0.0, t - i)))

    def screen(cam, p):
        pos, look = Vector(cam["pos"]), Vector(cam["look"])
        fwd = (look - pos).normalized()
        right = fwd.cross(Vector((0.0, 0.0, 1.0))).normalized()
        d = p - pos
        z = d.dot(fwd)
        half = 18.0 / cam["lens"]                                     # 36 mm film back, fitted to the width
        return (max(-1.5, min(1.5, d.dot(right) / max(1e-3, z) / half)), d.length, z > 0.0)

    frames = []
    for ff in range(1, 721):
        sh = film.shot_at(shots, ff)
        c = sh["cam"](ff)
        rec = dict(ff=ff, shot=sh["name"], rate=film.rate_at(ff), take=film.take_time(ff),
                   cam=dict(pos=list(c["pos"]), look=list(c["look"]), lens=c["lens"]))
        for who, A in cast.items():
            J = {j: list(film.joint(A, j, ff)) for j in joints}
            T = {k: list(tip(A, k, film.take_time(ff))) for k in A.swords}
            x, dist, front = screen(c, Vector(J.get("Spine2", J["Hips"])))
            rec[who] = dict(joints=J, tips=T, screen=dict(x=x, dist=dist, front=front), seen=ff >= film.ENTERS[who])
        frames.append(rec)

    contacts = {}
    for who, A in cast.items():                                      # heel strikes, on take frames, then onto the film's frames
        out = []
        for side in ("Left", "Right"):                               # a foot that was swinging stops at a low point (flat floor or steps)
            foot = f"{side}Foot" if f"{side}Foot" in names else f"{side}ToeBase"
            P = [A.pp.heads(A.poses[f])[foot].copy() for f in range(A.frames)]
            hips = [A.pp.heads(A.poses[f])["Hips"].xy for f in range(A.frames)]
            sp = [0.0] + [(P[f] - P[f - 1]).length for f in range(1, A.frames)]
            last = -99
            for f in range(4, A.frames - 1):
                low = P[f].z <= min(P[k].z for k in range(max(0, f - 8), min(A.frames, f + 9))) + 0.03
                if sp[f] < 0.010 and max(sp[f - 3:f]) > 0.025 and low and f - last > 6:
                    speed = (hips[min(A.frames - 1, f + 1)] - hips[max(0, f - 1)]).length * 12.0     # metres a second
                    out.append(dict(take=f, foot=side, speed=speed, swing=max(sp[f - 3:f]) * 24.0))
                    last = f
        for c in out:
            c["ff"] = film.film_of(c["take"])
            c["shown"] = abs(film.take_time(c["ff"]) - c["take"]) < 1.01 and c["ff"] >= film.ENTERS[who]
        contacts[who] = sorted([c for c in out if c["shown"]], key=lambda c: c["ff"])

    events = []
    for e in film.EVENTS:
        d = {k: v for k, v in e.items() if k in ("kind", "power", "who", "peak")}
        for k in ("f", "f0", "f1", "peak"):
            if k in e:
                d[k + "_take"] = e[k]
                d[("ff" if k == "f" else k + "_ff")] = film.film_of(e[k])
        if "at" in e:
            d["at"] = list(e["at"])
        events.append(d)
    consts = {k: getattr(film, k) for k in ("DASH", "HIT", "B0", "HAMMER", "C0", "SPIN", "KICK", "D0", "TRADE", "F0", "CHARGE", "SLASH",
                                            "G0", "RUSH", "CROSS", "J0", "END", "SPLIT", "CRACK", "LEAD", "HITSTOP")}
    out = dict(events=events, consts=consts, enters=film.ENTERS,
               shots=[dict(name=s["name"], first=s["first"], last=s["last"]) for s in shots], frames=frames, contacts=contacts,
               swords={who: list(A.swords) for who, A in cast.items()})
    path = os.path.join(HERE, arg("--out", "out/sound/events.json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"EVENTS {path}: {len(events)} events, {sum(len(v) for v in contacts.values())} footfalls, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
