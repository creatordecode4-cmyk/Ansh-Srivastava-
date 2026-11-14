"""Keyframing toolkit for the fight choreography (Stage 3b).

Everything is authored in WORLD space with each character's Root left at the origin:
  * feet are world-space plants: a planted foot keeps identical keys, so it cannot slide;
  * the katana is the master object and the hands follow it through the grip targets, so two blades can be
    made to pass through the same world point on a clash frame;
  * hips/spine/head are solved per key from the feet and the swords (reach limits respected).
A character's facing is an angle in degrees: 0 = +X (east), 90 = +Y (north, toward the torii).
Local pose coordinates are (l, f, z) = (to the character's left, forward, up) relative to a ground point.
"""
import bpy, math
from mathutils import Matrix, Vector, Quaternion

SIDES = {'L': 'Left', 'R': 'Right'}
FK_BONES = ('Spine', 'Spine1', 'Spine2', 'Neck', 'Head', 'LeftShoulder', 'RightShoulder')


def Rz(d): return Matrix.Rotation(math.radians(d), 4, 'Z')
def Rx(d): return Matrix.Rotation(math.radians(d), 4, 'X')
def Ry(d): return Matrix.Rotation(math.radians(d), 4, 'Y')


def basis(face):
    a = math.radians(face)
    F = Vector((math.cos(a), math.sin(a), 0.0))
    L = Vector((-math.sin(a), math.cos(a), 0.0))
    return F, L


def sword_matrix(pos, blade, edge):
    Z = Vector(blade).normalized()
    e = Vector(edge)
    e = e - e.dot(Z) * Z
    if e.length < 1e-5:
        e = Vector((0, 0, -1)) - Vector((0, 0, -1)).dot(Z) * Z
    e.normalize()
    Y = -e
    X = Y.cross(Z)
    M = Matrix((X, Y, Z)).transposed().to_4x4()
    M.translation = Vector(pos)
    return M


class Actor:
    def __init__(self, name, swords):
        """swords: {object name: 'RL' | 'R' | 'L'} - which hands belong on that katana."""
        self.n = name
        self.rig = bpy.data.objects[name + '_Rig']
        self.swords = swords
        self.vl = bpy.context.view_layer
        self.sc = bpy.context.scene
        B = self.rig.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in B}
        hips_inv = self.rest['Hips'].inverted()
        self.hipj = {s: hips_inv @ B[SIDES[s] + 'UpLeg'].head_local for s in SIDES}
        self.leg_len = (B['LeftLeg'].head_local - B['LeftUpLeg'].head_local).length + (B['LeftFoot'].head_local - B['LeftLeg'].head_local).length
        self.arm_len = (B['LeftForeArm'].head_local - B['LeftArm'].head_local).length + (B['LeftHand'].head_local - B['LeftForeArm'].head_local).length
        self.ankle_h = {s: B[SIDES[s] + 'Foot'].head_local.z for s in SIDES}
        self.hips_h = B['Hips'].head_local.z
        self.head_h = B['Head'].tail_local.z
        self.feet = {'L': [], 'R': []}
        self._lastq = {}
        self.hip_state = None
        self.st = {'grip': {}, 'curl': {}, 'show': {}}        # sticky states, re-keyed on every body key so they hold
        for k in ('FOOT_L', 'FOOT_R', 'HAND_L', 'HAND_R'):
            self.o(k).rotation_mode = 'QUATERNION'
        for sn in swords:
            bpy.data.objects[sn].rotation_mode = 'QUATERNION'
        for pb in self.rig.pose.bones:
            if 'Fingers' not in pb.name:
                pb.rotation_mode = 'QUATERNION'
        for suf in ('_Body', '_BodyLo'):                      # no mesh deformation while authoring (fast updates)
            for m in bpy.data.objects[name + suf].modifiers:
                m.show_viewport = False

    def o(self, key):
        return bpy.data.objects[f'{self.n}_{key}']

    # ------------------------------------------------------------------ low-level keying
    def _kq(self, owner, tag, frame):
        q = owner.rotation_quaternion.copy()
        last = self._lastq.get(tag)
        if last is not None and last.dot(q) < 0:
            q.negate()
            owner.rotation_quaternion = q
        self._lastq[tag] = q.copy()
        owner.keyframe_insert('rotation_quaternion', frame=frame)

    def _key_obj(self, ob, frame, rot=True):
        ob.keyframe_insert('location', frame=frame)
        if rot:
            self._kq(ob, ob.name, frame)

    def _set_world(self, ob, M):
        """Objects are children of the (identity) root or of nothing: write local = world."""
        ob.matrix_parent_inverse = Matrix.Identity(4)
        loc, rot, _ = M.decompose()
        ob.location = loc
        if ob.rotation_mode == 'QUATERNION':
            ob.rotation_quaternion = rot
        else:
            ob.rotation_euler = rot.to_euler()

    # ------------------------------------------------------------------ feet
    def foot_matrix(self, s, xy, yaw, lift=0.0, pitch=0.0):
        rest = self.rest[SIDES[s] + 'Foot']
        z = self.ankle_h[s] + lift + max(0.0, math.sin(math.radians(pitch))) * 0.13
        return Matrix.Translation((xy[0], xy[1], z)) @ Rz(yaw + 90) @ Rx(pitch) @ rest.to_3x3().to_4x4()

    def plant(self, s, frame, xy, yaw, lift=0.0, pitch=0.0):
        ob = self.o('FOOT_' + s)
        self._set_world(ob, self.foot_matrix(s, xy, yaw, lift, pitch))
        self._key_obj(ob, frame)
        ks = [k for k in self.feet[s] if k[0] != frame]
        ks.append((frame, Vector((xy[0], xy[1])), yaw, lift, pitch))
        self.feet[s] = sorted(ks, key=lambda k: k[0])

    def foot_at(self, s, frame):
        ks = self.feet[s]
        if not ks:
            return None
        if frame <= ks[0][0]:
            return ks[0]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= frame <= b[0]:
                t = (frame - a[0]) / max(1e-6, b[0] - a[0])
                return (frame, a[1].lerp(b[1], t), a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t)
        return ks[-1]

    def step(self, s, f0, f1, xy, yaw, lift=0.10, toe=18.0):
        """Lift the foot at f0 and plant it at xy on f1 (it stays where it was until f0)."""
        cur = self.foot_at(s, f0)
        if cur is None:
            self.plant(s, f1, xy, yaw)
            return
        self.plant(s, f0, cur[1], cur[2], cur[3], cur[4])
        if f1 - f0 >= 2:
            fm = (f0 + f1) // 2
            mid = cur[1].lerp(Vector(xy[:2]), 0.5)
            self.plant(s, fm, mid, cur[2] + (yaw - cur[2]) * 0.5, lift, toe)
        self.plant(s, f1, xy, yaw)

    def hold_feet(self, frame):
        for s in SIDES:
            cur = self.foot_at(s, frame)
            if cur is not None:
                self.plant(s, frame, cur[1], cur[2], cur[3], cur[4])

    # ------------------------------------------------------------------ the pose solver
    def key(self, frame, pos, face, hips=None, sw=None, hands=None, spine=(0, 0, 0), look=None, grip=None, curl=None,
            show=None, elbows=None, lean_to_reach=True):
        """
        pos    ground reference point (x, y); face: facing angle in degrees
        hips   dict(l, f, z, yaw, pitch, roll) - local offsets; z in metres (default 0.93 of rest height)
        sw     {katana name: ('local', tsuba(l,f,z), blade(l,f,z), edge(l,f,z)) | ('world', pos, blade, edge)
                             | ('thru', contact_world, blade_world, edge_world, dist_from_guard)}
        hands  {'L'|'R': (wrist(l,f,z), fingers(l,f,z), palm_normal(l,f,z))} for free hands (grip 0)
        spine  (twist, lean, side) in degrees, spread over the three spine bones
        look   world point the head turns to; grip {'L'|'R': 0..1}; curl {'L'|'R': 0..1}; show {katana: bool}
        """
        self.sc.frame_set(frame)
        F, L = basis(face)
        P = Vector((pos[0], pos[1], 0.0))
        W = lambda v: P + L * v[0] + F * v[1] + Vector((0, 0, v[2]))
        D = lambda v: L * v[0] + F * v[1] + Vector((0, 0, v[2]))
        rig, pbs = self.rig, self.rig.pose.bones
        # ---- swords
        late_sw, late_hand = {}, {}
        for sn, spec in (sw or {}).items():
            ob = bpy.data.objects[sn]
            if spec[0] == 'hip':
                late_sw[sn] = spec
                continue
            if spec[0] == 'local':
                M = sword_matrix(W(spec[1]), D(spec[2]), D(spec[3]))
            elif spec[0] == 'world':
                M = sword_matrix(spec[1], spec[2], spec[3])
            else:
                Z = Vector(spec[2]).normalized()
                M = sword_matrix(Vector(spec[1]) - Z * spec[4], Z, spec[3])
            self._set_world(ob, M)
            self._key_obj(ob, frame)
        self.st['show'].update(show or {})
        self.st['grip'].update(grip or {})
        self.st['curl'].update(curl or {})
        for sn, vis in self.st['show'].items():
            ob = bpy.data.objects[sn]
            ob.hide_render = ob.hide_viewport = not vis
            ob.keyframe_insert('hide_render', frame=frame)
            ob.keyframe_insert('hide_viewport', frame=frame)
            for ch in ob.children:
                if ch.type == 'MESH':
                    ch.hide_render = not vis
                    ch.keyframe_insert('hide_render', frame=frame)
        # ---- grips / free hands / fingers
        for s, v in self.st['grip'].items():
            c = self.o('HAND_' + s).constraints['Grip'] if 'Grip' in self.o('HAND_' + s).constraints else None
            if c:
                c.influence = v
                c.keyframe_insert('influence', frame=frame)
        def hand_matrix(s, wrist, fd, pn):
            fd = fd.normalized()
            pn = (pn - pn.dot(fd) * fd).normalized()
            des = Matrix((fd, pn, fd.cross(pn))).transposed()
            rf = Vector((1, 0, 0)) if s == 'L' else Vector((-1, 0, 0))
            rn = Vector((0, 0, -1))
            rb = Matrix((rf, rn, rf.cross(rn))).transposed()
            M = ((des @ rb.transposed()) @ self.rest[SIDES[s] + 'Hand'].to_3x3()).to_4x4()
            M.translation = wrist
            return M

        for s, spec in (hands or {}).items():
            if spec[0] == 'hip':
                late_hand[s] = spec
                continue
            ob = self.o('HAND_' + s)
            self._set_world(ob, hand_matrix(s, W(spec[0]), D(spec[1]), D(spec[2])))
            self._key_obj(ob, frame)
        for s, v in self.st['curl'].items():
            sign = -1 if s == 'L' else 1
            for k, deg in enumerate((58, 72, 55)):
                fb = pbs[f'{SIDES[s]}HandFingers{k + 1}']
                fb.rotation_euler = (0, 0, sign * math.radians(deg * v))
                fb.keyframe_insert('rotation_euler', frame=frame)
        # ---- feet at this frame (already keyed by plant/step)
        feet = {s: self.foot_at(s, frame) for s in SIDES}
        ank = {s: Vector((feet[s][1].x, feet[s][1].y, self.ankle_h[s] + feet[s][3])) for s in SIDES}
        h = dict(l=0.0, f=0.0, z=self.hips_h * 0.93, yaw=0.0, pitch=0.0, roll=0.0)
        h.update(hips or {})
        hp = W((h['l'], h['f'], h['z']))
        hrot = Rz(face + h['yaw'] + 90) @ Rx(h['pitch']) @ Ry(h['roll'])
        up_axis = Vector((0, 0, 1))
        for outer in range(4):
            # legs: keep both hip joints within reach of their ankles
            for it in range(12):
                HM = Matrix.Translation(hp) @ hrot @ self.rest['Hips'].to_3x3().to_4x4()
                push = Vector((0, 0, 0))
                for s in SIDES:
                    hj = HM @ self.hipj[s]
                    d = ank[s] - hj
                    over = d.length - 0.985 * self.leg_len
                    if over > 0:
                        push += d.normalized() * over
                if push.length < 1e-4:
                    break
                hp = hp + push * 0.7
            for b in FK_BONES:
                pbs[b].matrix_basis = Matrix.Identity(4)
            pbs['Hips'].matrix = Matrix.Translation(hp) @ hrot @ self.rest['Hips'].to_3x3().to_4x4()
            self.vl.update()
            Hd = pbs['Hips'].matrix @ self.rest['Hips'].inverted()        # rest space -> current hips-attached space
            H3 = Hd.to_3x3()
            for sn, spec in late_sw.items():
                self._set_world(bpy.data.objects[sn], sword_matrix(Hd @ Vector(spec[1]), H3 @ Vector(spec[2]), H3 @ Vector(spec[3])))
            for s, spec in late_hand.items():
                self._set_world(self.o('HAND_' + s), hand_matrix(s, Hd @ Vector(spec[1]), H3 @ Vector(spec[2]), H3 @ Vector(spec[3])))
            if late_sw or late_hand:
                self.vl.update()
            Fh = (hrot @ Vector((0, -1, 0))).normalized()
            Lh = (hrot @ Vector((1, 0, 0))).normalized()
            tw, le, si = spine
            for b in ('Spine', 'Spine1', 'Spine2'):
                pb = pbs[b]
                M = pb.matrix.copy()
                head = M.translation.copy()
                # twist: + turns left; lean: + bends forward; side: + bends to the character's right
                R = Matrix.Rotation(math.radians(tw / 3), 4, up_axis) @ Matrix.Rotation(math.radians(le / 3), 4, Lh) \
                    @ Matrix.Rotation(math.radians(si / 3), 4, Fh)
                pb.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ M
                self.vl.update()
            if not lean_to_reach:
                break
            # arms: if a wrist target is out of reach, carry the hips toward it
            shift = Vector((0, 0, 0))
            for s in SIDES:
                sh = pbs[SIDES[s] + 'Arm'].head
                tgt = self.o('HAND_' + s).matrix_world.translation
                d = tgt - sh
                over = d.length - 0.965 * self.arm_len
                if over > 0:
                    shift += d.normalized() * over
            if shift.length < 0.004:
                break
            hp = hp + Vector((shift.x, shift.y, shift.z * 0.6)) * 0.9
        # ---- poles
        chest = pbs['Spine2'].matrix.to_3x3() @ self.rest['Spine2'].to_3x3().inverted()
        Fc, Lc, Uc = (chest @ Vector((0, -1, 0))).normalized(), (chest @ Vector((1, 0, 0))).normalized(), (chest @ Vector((0, 0, 1))).normalized()
        for s in SIDES:
            hj = pbs[SIDES[s] + 'UpLeg'].head
            a = math.radians(feet[s][2])
            Ff = Vector((math.cos(a), math.sin(a), 0))
            kd = (Fh * 0.5 + Ff * 0.7)
            kd.z = 0
            kd.normalize()
            kp = (hj + ank[s]) * 0.5 + kd * 0.9 + Vector((0, 0, 0.10))
            ko = self.o('KNEE_' + s)
            self._set_world(ko, Matrix.Translation(kp))
            ko.keyframe_insert('location', frame=frame)
            sh = pbs[SIDES[s] + 'Arm'].head
            out = Lc if s == 'L' else -Lc
            ep = (elbows or {}).get(s)
            ep = W(ep) if ep is not None else sh - Uc * 0.50 + out * 0.42 - Fc * 0.12
            eo = self.o('ELBOW_' + s)
            self._set_world(eo, Matrix.Translation(ep))
            eo.keyframe_insert('location', frame=frame)
        self.vl.update()
        # ---- head
        if look is not None:
            for b, share in (('Neck', 0.45), ('Head', 1.0)):
                pb = pbs[b]
                M = pb.matrix.copy()
                fwd = ((M.to_3x3() @ self.rest[b].to_3x3().inverted()) @ Vector((0, -1, 0))).normalized()
                d = (Vector(look) - pbs['Head'].head).normalized()
                q = fwd.rotation_difference(d)
                ang = min(q.angle, math.radians(70)) * share
                if ang > 1e-4:
                    head = M.translation.copy()
                    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(ang, 4, q.axis) @ Matrix.Translation(-head) @ M
                    self.vl.update()
        for sn in late_sw:
            self._key_obj(bpy.data.objects[sn], frame)
        for s in late_hand:
            self._key_obj(self.o('HAND_' + s), frame)
        # ---- key the body
        hb = pbs['Hips']
        hb.keyframe_insert('location', frame=frame)
        self._kq(hb, 'Hips', frame)
        for b in FK_BONES:
            self._kq(pbs[b], b, frame)
        self.hip_state = (frame, hp.copy())
        return hp

    # ------------------------------------------------------------------ locomotion
    def travel(self, f0, f1, p0, p1, face, n, lead='R', width=0.12, lift=0.09, bob=0.025, lean=4.0, hipz=0.94,
               pose=None, swing=0.75, end_stance=None, yaw_sway=6.0, ease='both', move_face=None):
        """Walk/run from p0 to p1 in n steps (the body faces `face`; it moves along p0->p1).
        pose(frame, k, pos, swing_side) -> extra kwargs for key(). swing > 1 gives a flight phase (running).
        ease: 'both' | 'in' | 'out' | 'none' - half-step ramps at the eased ends."""
        p0, p1 = Vector(p0[:2]), Vector(p1[:2])
        dvec = p1 - p0
        dist = dvec.length
        Fm = dvec.normalized() if dist > 1e-6 else Vector((1, 0))
        Lm = Vector((-Fm.y, Fm.x))
        T = (f1 - f0) / n
        r = 0.5 / n

        def prog(t):                       # trapezoid speed profile, normalised distance 0..1
            a = r if ease in ('both', 'in') else 0.0
            b = r if ease in ('both', 'out') else 0.0
            total = 1 - a / 2 - b / 2
            if t < a:
                return (t * t / (2 * a)) / total
            if t > 1 - b:
                u = 1 - t
                return 1 - (u * u / (2 * b)) / total
            return (t - a / 2) / total

        side = lead
        prev = 0.0
        for k in range(1, n + 1):
            land = round(f0 + k * T)
            lift_f = max(f0, round(land - min(swing, 1.6) * T))
            sgn = 1 if side == 'L' else -1
            s_k = prog(k / n) * dist
            ahead = min(0.42, 0.5 * (s_k - prev)) if k < n else 0.0
            target = p0 + Fm * (s_k + ahead) + Lm * (sgn * width)
            yaw = face + sgn * 6
            if k == n and end_stance:
                F, L = basis(face)
                target = p1 + L.xy * end_stance[side][0] + F.xy * end_stance[side][1]
                yaw = face + end_stance[side][2]
            self.step(side, lift_f, land, target, yaw, lift=lift)
            prev = s_k
            side = 'L' if side == 'R' else 'R'
        if end_stance:                     # settle the other foot too
            F, L = basis(face)
            tgt = p1 + L.xy * end_stance[side][0] + F.xy * end_stance[side][1]
            self.step(side, round(f1 - 0.15 * T), round(f1 + 0.75 * T), tgt, face + end_stance[side][2], lift=lift * 0.7)
        for k in range(0, 2 * n + 1):      # body keys at every footfall and mid-swing
            fr = round(f0 + k * T / 2)
            pos = p0 + Fm * (prog((fr - f0) / max(1, f1 - f0)) * dist)
            contact = (k % 2 == 0)
            sw_side = lead if ((k // 2) % 2 == 0) else ('L' if lead == 'R' else 'R')
            sgn = 1 if sw_side == 'L' else -1
            hips = dict(z=self.hips_h * hipz - (bob if contact else -bob * 0.6), yaw=(sgn * yaw_sway if contact else 0.0), pitch=lean,
                        roll=(0 if contact else -sgn * 2.0))
            extra = pose(fr, k, pos, sw_side) if pose else {}
            if 'hips' in extra:
                hips.update(extra.pop('hips'))
            sp = extra.pop('spine', (-sgn * yaw_sway * 1.2 if contact else 0.0, lean * 0.5, 0))
            self.key(fr, pos, face, hips=hips, spine=sp, **extra)

    def slide(self, f0, f1, shift, steps=3):
        """Intentional slide: both planted feet glide by `shift` (world xy) between f0 and f1 with an ease-out."""
        for s in SIDES:
            a = self.foot_at(s, f0)
            self.plant(s, f0, a[1], a[2])
            for i in range(1, steps + 1):
                t = i / steps
                e = 1 - (1 - t) ** 2.2
                self.plant(s, round(f0 + (f1 - f0) * t), a[1] + Vector(shift[:2]) * e, a[2])
