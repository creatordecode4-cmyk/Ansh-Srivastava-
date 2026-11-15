"""A fighter's body as a solid that can be asked 'is this point inside me, and which way is out?'.

Everything that must not pass through the body - hands, scabbards, the hat brim, tassels, cloth -
is tested against this. The solid is the watertight skin from sd/envelope.py, moved with the
skeleton by the same weights Blender uses (linear blend skinning), but worked out here in numpy
so that a pose can be tested before anything is keyed.

A question is answered from the nearest skin vertex: on which side of it the point lies (told
by the vertex's outward normal) and how far away. With vertices 9 mm apart that is accurate to a
few millimetres near the surface, which is where it matters.
"""
import numpy as np
from mathutils import Matrix
from scipy.spatial import cKDTree

P = "mixamorig:"
SPACING = 0.006                                   # half the distance between neighbouring skin vertices
ARM_WORDS = ("Arm", "ForeArm", "Hand")            # dominant bone of a vertex that belongs to an arm (the collar bone does not)


class Skin:
    def __init__(self, proxy, pp):
        me = proxy.data
        nv = len(me.vertices)
        co = np.empty(nv * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        no = np.empty(nv * 3, dtype=np.float32)
        me.vertices.foreach_get("normal", no)
        self.P0 = co.reshape(-1, 3).astype(np.float64)
        self.N0 = no.reshape(-1, 3).astype(np.float64)
        self.names = list(pp.names)
        col = {P + n: i for i, n in enumerate(self.names)}
        gname = {g.index: g.name for g in proxy.vertex_groups}
        idx = np.zeros((nv, 4), dtype=np.int32)
        w = np.zeros((nv, 4), dtype=np.float64)
        for v in me.vertices:
            gs = sorted(((g.weight, col[gname[g.group]]) for g in v.groups if gname.get(g.group) in col and g.weight > 0.0), reverse=True)[:4]
            for k, (wt, b) in enumerate(gs):
                idx[v.index, k], w[v.index, k] = b, wt
        tot = w.sum(axis=1, keepdims=True)
        w /= np.maximum(tot, 1e-9)
        self.idx, self.w = idx, w
        top = [self.names[i] for i in idx[:, 0]]
        self.top = np.array(top)
        arm = np.array([any(t.endswith(word) or (word == "Hand" and "Hand" in t) for word in ARM_WORDS) and "Shoulder" not in t for t in top])
        head = np.array([t in ("Head", "Neck") for t in top])
        leg = np.array([("Leg" in t or "Foot" in t or "Toe" in t) for t in top])
        self.region = dict(all=np.ones(nv, dtype=bool), arms=arm, head=head, legs=leg, trunk=~arm & ~head, body=~arm,
                           left_leg=leg & np.array([t.startswith("Left") for t in top]), right_leg=leg & np.array([t.startswith("Right") for t in top]),
                           left_arm=arm & np.array([t.startswith("Left") for t in top]), right_arm=arm & np.array([t.startswith("Right") for t in top]),
                           no_fore=np.array([not ("ForeArm" in t or "Hand" in t) for t in top]), nohead=~head)
        # A region is part of a closed skin and so has an open rim (round the shoulders where the arms
        # were left out, round the neck where the head was). Next to a rim the 'which side' test is
        # meaningless - the vertex's normal points sideways across the hole - so questions answered
        # from a rim vertex are reported as 'clear'. Hands and brims are not judged there anyway.
        self.rim = {}
        for name in ("trunk", "body", "nohead", "no_fore", "left_leg", "right_leg", "left_arm", "right_arm"):
            inc = self.region[name]
            if inc.all():
                continue
            dist, _ = cKDTree(self.P0[~inc]).query(self.P0)
            self.rim[name] = inc & (dist < 0.07)
        self.pp = pp
        # how thick the forearm and the hand are (the fighters wear armour there): distance of their skin from the bone's line
        rad = dict(forearm=[], hand=[])
        for tag in ("Left", "Right"):
            for part, bone, a, b in (("forearm", tag + "ForeArm", tag + "ForeArm", tag + "Hand"), ("hand", tag + "Hand", tag + "Hand", tag + "HandMiddle1")):
                sel = self.top == bone
                if not sel.any():
                    continue
                A, B = np.array(pp.H0[a]), np.array(pp.H0[b])
                ab = B - A
                t = np.clip(((self.P0[sel] - A) @ ab) / float(ab @ ab), 0.0, 1.6)
                rad[part].append(np.percentile(np.linalg.norm(self.P0[sel] - (A + t[:, None] * ab), axis=1), 75))
        fore = float(np.mean(rad["forearm"])) if rad["forearm"] else 0.05
        hand = float(np.mean(rad["hand"])) if rad["hand"] else 0.045
        self.limb_radius = dict(forearm=fore, wrist=0.5 * (fore + hand) * 0.9, hand=hand)

    def frames(self, poses, keep=6):
        """posed[f] for a list of poses (see Frames)."""
        return Frames(self, poses, keep)

    def pose(self, pose, world=None):
        """The skin in a solved pose (armature space, or world if the armature object's matrix is given)."""
        pp = self.pp
        D = pose["D"]
        heads = pp.heads(pose)
        nb = len(self.names)
        R = np.zeros((nb, 3, 3))
        t = np.zeros((nb, 3))
        for i, n in enumerate(self.names):
            d = D.get(n)
            if d is None:                              # end bones: carried by their parent
                p = pp.parent[n]
                d = D.get(p) if p else None
                if d is None:
                    d = Matrix.Identity(3)
            R[i] = np.array(d)
            t[i] = np.array(heads[n]) - R[i] @ np.array(pp.H0[n])
        Pn = np.zeros_like(self.P0)
        Nn = np.zeros_like(self.N0)
        Rv = np.zeros((len(self.P0), 3, 3))
        for k in range(4):
            Rk = R[self.idx[:, k]]
            wk = self.w[:, k][:, None]
            Pn += wk * (np.einsum("vij,vj->vi", Rk, self.P0) + t[self.idx[:, k]])
            Rv += self.w[:, k][:, None, None] * Rk
        Nn = np.einsum("vij,vj->vi", Rv, self.N0)
        if world is not None:
            Rw, tw = np.array(world.to_3x3()), np.array(world.translation)
            Pn = Pn @ Rw.T + tw
            Nn = Nn @ Rw.T
            Rv = np.einsum("ij,vjk->vik", Rw, Rv)
        Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
        return Posed(self, Pn, Nn, Rv)


class Frames:
    """The skin on every frame of a shot: posed[f]. A posed skin with its search trees is some
    tens of megabytes, and a film is hundreds of frames for each fighter, so a frame's skin is
    worked out when it is asked for and only the last few are kept. The passes that use it go
    through the frames in order and ask for one frame many times in a row."""

    def __init__(self, skin, poses, keep=6):
        self.skin, self.poses, self.keep = skin, poses, keep
        self._have = {}

    def __len__(self):
        return len(self.poses)

    def __getitem__(self, f):
        got = self._have.pop(f, None)
        if got is None or got[0] is not self.poses[f]:                # a frame's pose can be replaced after it was last asked for
            got = (self.poses[f], self.skin.pose(self.poses[f]))
        self._have[f] = got                                           # most recently used last
        while len(self._have) > self.keep:
            self._have.pop(next(iter(self._have)))
        return got[1]


class Posed:
    def __init__(self, skin, Pn, Nn, Rv):
        self.skin, self.P, self.N, self.R = skin, Pn, Nn, Rv
        self._trees = {}

    def _tree(self, region):
        if region not in self._trees:
            sel = np.flatnonzero(self.skin.region[region])
            self._trees[region] = (cKDTree(self.P[sel]), sel)
        return self._trees[region]

    def signed(self, pts, region="body"):
        """For each point: distance outside the skin (negative inside), the outward direction there,
        and the skin vertex it was measured from. 'region' picks the part of the body asked."""
        pts = np.atleast_2d(np.asarray(pts, dtype=np.float64))
        tree, sel = self._tree(region)
        r, i = tree.query(pts)
        v = sel[i]
        to = pts - self.P[v]
        plane = np.einsum("ij,ij->i", to, self.N[v])
        # Close to the skin the distance along the vertex normal is the accurate one. Far from it
        # that number only says how far the point is in front of the vertex's tangent plane - a
        # point 15 cm to the side of a shoulder would read as 'touching'. There the straight
        # distance to the vertex is used, with the side still told by the normal.
        far = np.sqrt(np.maximum(r * r - SPACING * SPACING, 0.0))
        d = np.where(plane < 0.0, -1.0, 1.0) * np.maximum(np.abs(plane), far)
        out = np.where((np.abs(plane) >= far)[:, None], self.N[v], to / np.maximum(r, 1e-9)[:, None] * np.where(plane < 0.0, -1.0, 1.0)[:, None])
        rim = self.skin.rim.get(region)
        if rim is not None:
            d = np.where(rim[v], 1.0, d)
        return d, out, v

    def carry(self, v, offset):
        """Where a point that sat at 'offset' from skin vertex v in the rest pose is now."""
        return self.P[v] + self.R[v] @ np.asarray(offset, dtype=np.float64)
