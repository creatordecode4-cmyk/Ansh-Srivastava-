"""Procedural animation engine for the fighters.

Each Fighter owns named channels (feet, hips, spine, head, sword grips ...) that are keyed in code,
evaluated every frame with easing, solved into bone transforms (FK spine, IK feet / hands driven by
the control rig) and baked as ordinary keyframes.

Conventions: yaw 0 faces -Y (the models' native front); positive yaw turns left (counter-clockwise from above).
Feet are keyed in WORLD space, so a foot whose keys do not change is perfectly planted.
Sword grips and blade directions are keyed in WORLD space, so two blades can be aimed at one contact point.
Free hands are keyed in the BODY frame (left, forward, up from the point under the hips).
"""
import bpy, math
from mathutils import Vector, Matrix, Quaternion
from charlib import orient

GRIP = 0.11          # distance from the guard down the handle to the centre of the main hand
EASE = {
    'io': lambda u: u * u * (3 - 2 * u),
    'i': lambda u: u * u * u,                      # accelerate into the key (strikes)
    'o': lambda u: 1 - (1 - u) ** 3,               # decelerate (recoveries)
    'l': lambda u: u,
    'hold': lambda u: 0.0 if u < 1 else 1.0,
}


def Rz(a): return Matrix.Rotation(a, 3, 'Z')
def Rx(a): return Matrix.Rotation(a, 3, 'X')
def Ry(a): return Matrix.Rotation(a, 3, 'Y')


def fwd(yaw): return Vector((math.sin(yaw), -math.cos(yaw), 0))
def left(yaw): return Vector((math.cos(yaw), math.sin(yaw), 0))


class Channel:
    def __init__(self, default, kind='lin'):
        self.keys, self.kind, self.default = [], kind, default

    def key(self, f, v, ease='io'):
        if not isinstance(v, (int, float)):
            v = Vector(v)
            if self.kind == 'dir':
                v = v.normalized()
        self.keys = sorted([k for k in self.keys if k[0] != f] + [(f, v, ease)], key=lambda k: k[0])

    def segment(self, f):
        k = self.keys
        if not k:
            return None
        if f <= k[0][0]:
            return k[0], k[0], 0.0
        if f >= k[-1][0]:
            return k[-1], k[-1], 0.0
        for a, b in zip(k, k[1:]):
            if a[0] <= f <= b[0]:
                return a, b, (f - a[0]) / (b[0] - a[0])

    def at(self, f):
        s = self.segment(f)
        if s is None:
            return self.default.copy() if hasattr(self.default, 'copy') else self.default
        a, b, u = s
        if a is b:
            return a[1].copy() if hasattr(a[1], 'copy') else a[1]
        e = EASE[b[2]](u)
        if isinstance(a[1], (int, float)):
            return a[1] + (b[1] - a[1]) * e
        if self.kind == 'dir':
            q = a[1].rotation_difference(b[1])
            return (Quaternion().slerp(q, e) @ a[1]).normalized()
        return a[1].lerp(b[1], e)


class Fighter:
    SCAL = ('yaw', 'bal', 'crouch', 'hip_pitch', 'hip_roll', 'hip_twist', 'chest_pitch', 'chest_roll', 'chest_twist',
            'head_yaw', 'head_pitch', 'heelL', 'heelR', 'drawn', 'fingers', 'two', 'fzL', 'fzR')

    def __init__(self, name, parts, J, two_handed):
        self.name, self.parts, self.arm, self.J, self.two = name, parts, parts['rig'], J, two_handed
        B = self.arm.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in B}
        self.rest3 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.head0 = {b.name: b.head_local.copy() for b in B}
        self.leg = (B['thigh.L'].length + B['shin.L'].length)
        self.armlen = (B['upper_arm.L'].length + B['forearm.L'].length)
        self.ch = {n: Channel(0.0) for n in self.SCAL}
        self.ch['off'] = Channel(Vector((0, 0)))
        self.ch['two'] = Channel(1.0)
        for s, sx in (('L', 1), ('R', -1)):
            self.ch['foot' + s] = Channel(Vector((sx * J['ankle_x'], J.get('ankle_y', 0.03), 0.0, 0.0)))   # x, y, yaw, arc height
            self.ch['hand' + s] = Channel(Vector((sx * 0.36, 0.04, 0.98)))                               # body frame, hanging
            self.ch['grip' + s] = Channel(Vector((sx * 0.3, -0.3, 1.2)))
            self.ch['dir' + s] = Channel(Vector((0, -0.7, 0.7)), 'dir')
            self.ch['edge' + s] = Channel(Vector((0, 0, -1)), 'dir')
        self.krest = {s: parts['krest_' + s] for s in ('L', 'R') if 'krest_' + s in parts}
        self._prev_q = {}

    # ---------------- keying helpers
    def key(self, f, ease='io', **vals):
        for n, v in vals.items():
            self.ch[n].key(f, v, ease)

    def pin(self, f, *names):
        """Key channels at their current value so a new move starts from here instead of drifting in."""
        for n in (names or self.ch.keys()):
            c = self.ch[n]
            if c.keys:
                seg = c.segment(f)
                c.key(f, c.at(f), seg[1][2] if seg[0] is not seg[1] else 'io')

    def hold(self, fa, fb, *names):
        """Freeze: the pose at fa is still there at fb (hit-stop, held stances)."""
        for n in (names or self.ch.keys()):
            c = self.ch[n]
            if c.keys:
                c.key(fa, c.at(fa), c.segment(fa)[1][2] if c.segment(fa)[0] is not c.segment(fa)[1] else 'io')
                c.key(fb, c.at(fa), 'l')

    def stand(self, f, x, y, yaw, width=None, stagger=0.0, splay=0.12, ease='io'):
        """Plant both feet around (x, y). stagger > 0 puts the left foot forward."""
        w = (width if width is not None else 2 * self.J['ankle_x']) / 2
        c = Vector((x, y, 0))
        for s, sx in (('L', 1), ('R', -1)):
            p = c + left(yaw) * sx * w + fwd(yaw) * sx * stagger / 2
            self.ch['foot' + s].key(f, (p.x, p.y, yaw + sx * splay, 0.0), ease)
        self.ch['yaw'].key(f, yaw, ease)

    def step(self, side, f0, f1, x, y, yaw, lift=0.10, ease='io'):
        """Lift one foot at f0 and plant it at (x, y) on f1; it stays put before and after."""
        c = self.ch['foot' + side]
        cur = c.at(f0)
        c.key(f0, (cur.x, cur.y, cur.z, 0.0), 'io' if not c.keys else c.segment(f0)[1][2])
        c.key(f1, (x, y, yaw, lift), ease)

    def foot_rel(self, x, y, yaw, side, lat, ahead=0.0, splay=0.10):
        sx = 1 if side == 'L' else -1
        p = Vector((x, y, 0)) + left(yaw) * sx * lat + fwd(yaw) * ahead
        return p.x, p.y, yaw + sx * splay

    def walk(self, f0, pts, step_len=0.62, step_frames=13, width=0.36, first='R', arm_swing=True):
        """Walk along the polyline pts starting at frame f0. Returns the frame at which both feet are planted."""
        segs, total = [], 0.0
        for a, b in zip(pts, pts[1:]):
            L = (Vector(b) - Vector(a)).length
            segs.append((Vector((*a, 0)), Vector((*b, 0)), total, L)); total += L
        def along(d):
            d = min(max(d, 0.0), total)
            for a, b, s0, L in segs:
                if d <= s0 + L + 1e-6:
                    t = (d - s0) / L
                    dirv = (b - a).normalized()
                    return a.lerp(b, t), math.atan2(dirv.x, -dirv.y)
        n = max(2, math.ceil(total / step_len))
        sl = total / n
        side = first
        p0, y0 = along(0)
        self.stand(f0, p0.x, p0.y, y0, width)
        f = f0
        for i in range(1, n + 2):
            d = min(total, sl * (i - 0.5) if i <= n else total)
            if i == n + 1:
                d = total
            p, yw = along(d if i <= n else total)
            ahead = 0.0
            fx, fy, fyaw = self.foot_rel(p.x, p.y, yw, side, width / 2, ahead, 0.08)
            self.step(side, f, f + step_frames, fx, fy, fyaw, lift=0.085, ease='l')
            self.ch['yaw'].key(f + step_frames, yw, 'l')
            sgn = 1 if side == 'L' else -1
            mid = f + step_frames // 2
            self.key(mid, 'io', crouch=0.035, hip_roll=0.035 * sgn, chest_roll=-0.03 * sgn)
            self.key(f + step_frames, 'io', crouch=0.065, hip_twist=0.10 * sgn, chest_twist=-0.20 * sgn)
            if arm_swing in (True, 'L'):
                self.key(f + step_frames, 'io', handL=(0.36, 0.04 - 0.16 * sgn, 0.99))
            if arm_swing in (True, 'R'):
                self.key(f + step_frames, 'io', handR=(-0.36, 0.04 + 0.16 * sgn, 0.99))
            f += step_frames
            side = 'R' if side == 'L' else 'L'
        self.key(f, 'io', hip_twist=0.0, chest_twist=0.0, hip_roll=0.0, chest_roll=0.0)
        self.key(f + 8, 'io', crouch=0.03)
        return f

    # ---------------- body-frame helpers (left, forward, up measured from the ground point under the hips)
    def bp(self, f, v):
        st = self.state(f)
        yaw, h = st['yaw'], st['P']['hips']
        return Vector((h.x, h.y, 0)) + left(yaw) * v[0] + fwd(yaw) * v[1] + Vector((0, 0, v[2]))

    def bd(self, f, v):
        yaw = self.ch['yaw'].at(f)
        return (left(yaw) * v[0] + fwd(yaw) * v[1] + Vector((0, 0, v[2]))).normalized()

    def sword(self, f, side, grip, direction, edge=(0, 0, -1), ease='io', world=False):
        """Key one sword. grip / direction in the body frame unless world=True."""
        g = Vector(grip) if world else self.bp(f, grip)
        d = Vector(direction).normalized() if world else self.bd(f, direction)
        e = Vector(edge).normalized() if world else self.bd(f, edge)
        self.key(f, ease, **{'grip' + side: g, 'dir' + side: d, 'edge' + side: e})

    def sword_through(self, f, side, point, direction, s=0.45, edge=(0, 0, -1), ease='i'):
        """Aim the blade so that it passes through a WORLD point, s metres up from the guard."""
        d = Vector(direction).normalized()
        self.key(f, ease, **{'grip' + side: Vector(point) - d * (GRIP + s), 'dir' + side: d, 'edge' + side: Vector(edge).normalized()})

    # ---------------- evaluation
    def foot(self, s, f):
        c = self.ch['foot' + s]
        v = c.at(f)
        seg = c.segment(f)
        lift, auto_pitch = 0.0, 0.0
        if seg and seg[0] is not seg[1]:
            a, b, u = seg
            if (Vector(a[1][:2]) - Vector(b[1][:2])).length > 1e-3 and b[1][3] > 0:
                lift = b[1][3] * math.sin(math.pi * u) ** 1.2
                auto_pitch = 0.45 * math.sin(math.pi * min(1.0, u * 2.2)) - 0.28 * math.sin(math.pi * max(0.0, (u - 0.6) / 0.4))
        pitch = self.ch['heel' + s].at(f) + auto_pitch * (1.0 if lift > 0 else 0.0)
        z = self.head0['foot.' + s].z + lift + 0.13 * max(0.0, math.sin(pitch)) + self.ch['fz' + s].at(f)
        return Vector((v.x, v.y, z)), v.z, pitch

    def state(self, f):
        """World-space solve for frame f: returns pose matrices for bones / controls plus useful points."""
        ev = lambda n: self.ch[n].at(f)
        H0 = self.head0
        yaw = ev('yaw')
        F, Lf = fwd(yaw), left(yaw)
        ft = {s: self.foot(s, f) for s in ('L', 'R')}
        bal = 0.5 + 0.35 * ev('bal')
        mid = Vector((ft['R'][0].x, ft['R'][0].y, 0)).lerp(Vector((ft['L'][0].x, ft['L'][0].y, 0)), bal)
        off = ev('off')
        hips_xy = mid + Lf * off.x + F * off.y
        t = f / 24.0
        breath = 0.006 * math.sin(t * 2.4 + hash(self.name) % 7)
        Rh = Rz(yaw + ev('hip_twist')) @ Rx(ev('hip_pitch')) @ Ry(ev('hip_roll'))
        z = H0['hips'].z - ev('crouch') + breath
        # keep both legs within reach
        for s in ('L', 'R'):
            hj = Rh @ (H0['thigh.' + s] - H0['hips'])
            dh = (Vector((hips_xy.x + hj.x, hips_xy.y + hj.y)) - Vector((ft[s][0].x, ft[s][0].y))).length
            Lm = self.leg * 0.992
            if dh < Lm:
                z = min(z, ft[s][0].z + math.sqrt(Lm * Lm - dh * dh) - hj.z)
        hips_p = Vector((hips_xy.x, hips_xy.y, z))
        cp, cr, ct = ev('chest_pitch') + 0.01 * math.sin(t * 2.4), ev('chest_roll'), ev('chest_twist')
        Rs = Rh @ Rz(ct / 2) @ Rx(cp / 2) @ Ry(cr / 2)
        Rc = Rs @ Rz(ct / 2) @ Rx(cp / 2) @ Ry(cr / 2)
        hy, hp = ev('head_yaw'), ev('head_pitch')
        Rn = Rc @ Rz(hy / 2) @ Rx(hp / 2)
        Rhd = Rc @ Rz(hy) @ Rx(hp)
        P = {'hips': hips_p}
        P['spine'] = P['hips'] + Rh @ (H0['spine'] - H0['hips'])
        P['chest'] = P['spine'] + Rs @ (H0['chest'] - H0['spine'])
        P['neck'] = P['chest'] + Rc @ (H0['neck'] - H0['chest'])
        P['head'] = P['neck'] + Rn @ (H0['head'] - H0['neck'])
        Rw = {'hips': Rh, 'spine': Rs, 'chest': Rc, 'neck': Rn, 'head': Rhd}
        M = {n: Matrix.Translation(P[n]) @ (Rw[n] @ self.rest3[n]).to_4x4() for n in Rw}
        out = {'M': M, 'P': P, 'yaw': yaw, 'head_top': P['head'] + Rhd @ Vector((0, 0, 0.18)), 'Rc': Rc, 'feet': ft}
        base = Vector((hips_xy.x, hips_xy.y, 0))
        drawn = ev('drawn')
        for s, sx in (('L', 1), ('R', -1)):
            # feet
            p, fy, pitch = ft[s]
            M['ctl_foot.' + s] = Matrix.Translation(p) @ (Rz(fy - sx * self.J.get('toe_splay', 0.0)) @ Rx(pitch) @ self.rest3['foot.' + s]).to_4x4()
            hipj = hips_p + Rh @ (H0['thigh.' + s] - H0['hips'])
            kyaw = (yaw + ev('hip_twist')) * 0.5 + fy * 0.5
            M['pole_knee.' + s] = Matrix.Translation(hipj.lerp(p, 0.5) + fwd(kyaw) * 1.0) @ self.rest3['pole_knee.' + s].to_4x4()
            # hands
            sh = P['chest'] + Rc @ (H0['upper_arm.' + s] - H0['chest'])
            hv = ev('hand' + s)
            free_p = base + Lf * hv.x + F * hv.y + Vector((0, 0, hv.z))
            free_M = Matrix.Translation(free_p) @ (Rc @ Ry(-sx * 1.35) @ self.rest3['hand.' + s]).to_4x4()
            Hm = free_M
            src = s if s in self.krest else ('R' if self.two else None)
            if drawn > 0 and src:
                K = Matrix.Translation(ev('grip' + src)) @ orient(ev('dir' + src), ev('edge' + src)) @ Matrix.Translation((0, 0, GRIP))
                if src == s:
                    Sm = K @ (self.krest[s].inverted() @ self.rest['hand.' + s])
                    out['K_' + s] = K
                else:                              # second hand of a two-handed grip, lower on the handle
                    Sm = K @ Matrix.Translation((0, 0, -0.125)) @ (self.parts['krest_off'].inverted() @ self.rest['hand.' + s])
                wgt = drawn if src == s else drawn * min(1.0, max(0.0, ev('two')))
                if wgt >= 1:
                    Hm = Sm
                elif wgt > 0:
                    Hm = Matrix.Translation(free_p.lerp(Sm.to_translation(), wgt)) @ free_M.to_quaternion().slerp(Sm.to_quaternion(), wgt).to_matrix().to_4x4()
            d = Hm.to_translation() - sh
            reach = self.armlen * 0.985
            if d.length > reach:
                Hm = Matrix.Translation(sh + d.normalized() * reach - Hm.to_translation()) @ Hm
            M['ctl_hand.' + s] = Hm
            M['pole_elbow.' + s] = Matrix.Translation(sh + Rc @ Vector((sx * 0.40, 0.55, -0.50))) @ self.rest3['pole_elbow.' + s].to_4x4()
            out['sh_' + s] = sh
        for s in self.krest:
            if 'K_' + s in out:
                K = out['K_' + s]
                out['tip_' + s] = K @ Vector((0, 0, 0.72))
                out['guard_' + s] = K.to_translation()
        return out

    # ---------------- baking
    PARENT = {'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}

    def _set(self, name, basis, f, loc=True):
        pb = self.arm.pose.bones[name]
        l, q, _ = basis.decompose()
        prev = self._prev_q.get(name)
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        self._prev_q[name] = q.copy()
        pb.rotation_quaternion = q
        pb.keyframe_insert('rotation_quaternion', frame=f)
        if loc:
            pb.location = l
            pb.keyframe_insert('location', frame=f)

    def bake(self, f0, f1):
        pb = self.arm.pose.bones
        for b in pb:
            b.rotation_mode = 'QUATERNION'
        last_inf = last_fing = None
        for f in range(f0, f1 + 1):
            st = self.state(f)
            M = st['M']
            self._set('hips', self.rest['hips'].inverted() @ M['hips'], f)
            for n, p in self.PARENT.items():
                rel = self.rest[p].inverted() @ self.rest[n]
                self._set(n, rel.inverted() @ M[p].inverted() @ M[n], f, loc=False)
            for s in ('L', 'R'):
                for c in ('ctl_foot.', 'ctl_hand.', 'pole_knee.', 'pole_elbow.'):
                    self._set(c + s, self.rest[c + s].inverted() @ M[c + s], f)
            inf = min(1.0, max(0.0, self.ch['drawn'].at(f)))
            if inf != last_inf:
                pass
            for s in ('L', 'R'):
                if s in self.krest or self.two:
                    v = inf if s in self.krest else inf * min(1.0, max(0.0, self.ch['two'].at(f)))
                    if getattr(self, '_inf_' + s, None) != v:
                        c = pb['hand.' + s].constraints['CopyRot']
                        c.influence = v
                        c.keyframe_insert('influence', frame=f)
                        setattr(self, '_inf_' + s, v)
            if inf != last_inf:
                last_inf = inf
            fg = self.ch['fingers'].at(f)
            if fg != last_fing:
                for s, sx in (('L', 1), ('R', -1)):
                    for bn, k in (('fingers1.', 1.0), ('fingers2.', 1.15)):
                        b = pb[bn + s]
                        ax = (self.rest3[bn + s].inverted() @ Vector((0, 1, 0))).normalized()
                        b.rotation_quaternion = Quaternion(ax, sx * fg * k)
                        b.keyframe_insert('rotation_quaternion', frame=f)
                last_fing = fg
        print(f'  baked {self.name} frames {f0}-{f1}')

    def key_visibility(self, f, drawn):
        for k, o in self.parts.items():
            hide = None
            if k.startswith('hilt'):
                hide = drawn
            elif k.startswith('katana'):
                hide = not drawn
            if hide is not None:
                o.hide_render = o.hide_viewport = hide
                o.keyframe_insert('hide_render', frame=f)
                o.keyframe_insert('hide_viewport', frame=f)
