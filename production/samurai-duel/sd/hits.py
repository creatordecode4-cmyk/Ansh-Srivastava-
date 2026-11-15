"""What flies when blades meet and feet hit the wet floor: sparks, spray, a flame trail.

None of this is a particle system. The film is rendered frame by frame at times that a time map
decides - slowed down here, skipping there - and a simulated particle system would have to be
stepped through all of it in order. Here every spark and drop is a small projectile with a known
launch: where it is at any time is a formula, so a burst can be drawn for any scene time, in any
order, at any speed.

    burst = Burst(point, time, ...)            # take frame of the hit
    burst.fill(mesh_object, scene_time_in_take_frames)

A burst draws each projectile as a short streak along its path: two crossed quads from where it
is to where it was a moment ago, which reads as a streak from every side.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

FPS = 24.0


class Burst:
    """A spray of projectiles thrown from one point at one moment."""

    def __init__(self, at, frame, toward=(0, 0, 1), count=120, speed=(2.0, 7.0), spread=70.0, life=(0.18, 0.55), gravity=9.81, drag=1.6,
                 width=0.004, streak=0.022, floor=0.004, seed=1):
        r = np.random.default_rng(seed)
        self.at, self.frame = np.array(at, dtype=np.float64), float(frame)
        n = np.array(toward, dtype=np.float64)
        n /= np.linalg.norm(n)
        a = np.cross(n, (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0))
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        th = np.radians(spread) * np.sqrt(r.random(count))             # even over the cone
        ph = r.random(count) * 2 * math.pi
        d = np.cos(th)[:, None] * n + np.sin(th)[:, None] * (np.cos(ph)[:, None] * a + np.sin(ph)[:, None] * b)
        self.v = d * r.uniform(speed[0], speed[1], count)[:, None]
        self.life = r.uniform(life[0], life[1], count)
        self.g, self.drag, self.w, self.streak, self.floor = gravity, drag, width * r.uniform(0.6, 1.3, count), streak, floor

    def _pos(self, age):
        """Positions after 'age' seconds (array per projectile): thrown, slowed by the air, pulled down."""
        k = self.drag
        e = (1.0 - np.exp(-k * age)) / k                               # distance per unit of launch speed
        p = self.at + self.v * e[:, None]
        p[:, 2] -= self.g * (age - e) / k
        return p

    def geometry(self, take_time):
        """(vertices, faces) of the streaks alive at a take time (frames), or ([], [])."""
        age = (take_time - self.frame) / FPS
        if age <= 0.0:
            return [], []
        alive = age < self.life
        if not alive.any():
            return [], []
        ages = np.full(len(self.life), age)
        head = self._pos(ages)
        tail = self._pos(np.maximum(ages - self.streak, 0.0))
        fade = np.clip(1.0 - age / self.life, 0.0, 1.0) ** 0.6          # they thin out as they die
        verts, faces = [], []
        for i in np.flatnonzero(alive & (head[:, 2] > self.floor)):
            h, t = head[i], tail[i]
            d = h - t
            L = np.linalg.norm(d)
            if L < 1e-6:
                continue
            d /= L
            s1 = np.cross(d, (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0))
            s1 /= np.linalg.norm(s1)
            s2 = np.cross(d, s1)
            w = self.w[i] * fade[i]
            for s in (s1, s2):
                k = len(verts)
                verts += [tuple(t - s * w * 0.3), tuple(t + s * w * 0.3), tuple(h + s * w), tuple(h - s * w)]
                faces.append((k, k + 1, k + 2, k + 3))
        return verts, faces


def fill(ob, bursts, take_time):
    """Rebuild a mesh object as all the given bursts at one take time. Returns the number of faces."""
    verts, faces = [], []
    for b in bursts:
        v, f = b.geometry(take_time)
        k = len(verts)
        verts += v
        faces += [tuple(i + k for i in face) for face in f]
    me = ob.data
    me.clear_geometry()
    if verts:
        me.from_pydata(verts, [], faces)
    me.update()
    return len(faces)


def glow(name, color, strength):
    """A material that only gives off light (sparks, embers)."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0, 0, 0, 1)
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def spray_mat(name="MAT_Spray"):
    """Water thrown up from the wet floor: bright against the dark so that it reads, mostly rough white."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.82, 0.86, 0.92, 1)
        b.inputs["Roughness"].default_value = 0.25
        b.inputs["Emission Color"].default_value = (0.75, 0.82, 1.0, 1)
        b.inputs["Emission Strength"].default_value = 0.6
    return m


def holder(name, col, material):
    """An empty mesh object to be filled per frame."""
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    col.objects.link(ob)
    ob.data.materials.append(material)
    ob.visible_shadow = False
    return ob


def sparks(at, frame, toward=(0, 0, 1), seed=1, count=140):
    """Sparks from steel on steel: fast, short-lived, thrown mostly along 'toward'."""
    return Burst(at, frame, toward, count=count, speed=(2.5, 9.0), spread=75.0, life=(0.12, 0.5), gravity=6.0, drag=2.2, width=0.0035, streak=0.020, seed=seed)


def splash(at, frame, toward=(0, 0, 1), seed=1, count=160):
    """Water kicked up from the floor: slower and heavier than sparks, falling back in an arc."""
    return Burst(at, frame, toward, count=count, speed=(1.0, 4.2), spread=55.0, life=(0.3, 0.8), gravity=9.81, drag=0.8, width=0.006, streak=0.030, seed=seed)
