"""STAGE 3 - the 30 second fight: body animation for both fighters, written as code.

All frame numbers are output frames at 24 fps (1..720). Slow motion is authored directly as slow keys.
Returns the list of clash events (frame, world point, strength, time-scale) used for sparks and camera shake.
"""
import math
from mathutils import Vector as V
from anim import fwd, left

R = math.radians
OY = R(90)                 # Oni faces +X
LINE = 3.5                 # y of the duelling line


def pts(c, x, y, yaw, width, stagger, splay=0.12):
    out = {}
    for s, sx in (('L', 1), ('R', -1)):
        p = V((x, y, 0)) + left(yaw) * sx * width / 2 + fwd(yaw) * sx * stagger / 2
        out[s] = (p.x, p.y, yaw + sx * splay)
    return out


def move(c, f0, f1, x, y, yaw, width=0.7, stagger=0.5, first='L', lift=0.07, ease='io'):
    """Two steps into a new stance."""
    P = pts(c, x, y, yaw, width, stagger)
    fm = (f0 + f1) // 2
    second = 'R' if first == 'L' else 'L'
    c.step(first, f0, fm, *P[first], lift=lift, ease=ease)
    c.step(second, fm, f1, *P[second], lift=lift, ease=ease)
    c.pin(f0, 'yaw'); c.key(f1, yaw=yaw)


def slide(c, f0, f1, x, y, yaw, width=0.7, stagger=0.5, ease='o'):
    """Both feet skid along the wet floor (no lift)."""
    P = pts(c, x, y, yaw, width, stagger)
    for s in ('L', 'R'):
        c.pin(f0, 'foot' + s)
        c.ch['foot' + s].key(f1, (*P[s], 0.0), ease)


def oni_guard(o, f, ease='io', crouch=0.15):
    o.key(f, ease, crouch=crouch, chest_pitch=0.12, hip_twist=-0.25, chest_twist=0.12, hip_pitch=0.04, chest_roll=0.0, hip_roll=0.0,
          head_pitch=0.0, head_yaw=0.12, bal=0.0, drawn=1.0, two=1.0, fingers=1.1)
    o.sword(f, 'R', (-0.05, 0.38, 1.22), (0.05, 0.75, 0.6), ease=ease)


def ron_guard(r, f, ease='io', crouch=0.15):
    r.key(f, ease, crouch=crouch, chest_pitch=0.12, hip_twist=0.22, chest_twist=-0.10, hip_pitch=0.04, chest_roll=0.0, hip_roll=0.0,
          head_pitch=0.05, head_yaw=-0.10, bal=0.0, drawn=1.0, fingers=1.1)
    r.sword(f, 'R', (-0.30, 0.34, 1.18), (0.30, 0.8, 0.45), ease=ease)
    r.sword(f, 'L', (0.30, 0.26, 1.30), (-0.25, 0.7, 0.6), ease=ease)


def cross_block(r, f, C, ease='i', sink=0.0):
    """Ronin catches a blow on both blades crossed at world point C."""
    Cs = C - V((0, 0, sink))
    r.sword_through(f, 'R', Cs, r.bd(f, (0.80, 0.10, 0.58)), 0.42, ease=ease)
    r.sword_through(f, 'L', Cs - V((0, 0, 0.03)), r.bd(f, (-0.80, 0.10, 0.58)), 0.42, ease=ease)


def choreograph(o, r):
    EV = []
    RY = R(-90)            # Ronin faces -X (becomes 270 deg after his spin)

    # =========================================================== INTRO 1-270
    o.stand(1, -7.8, 3.0, R(96), width=0.46)
    o.key(1, handL=(0.20, 0.34, 1.34), handR=(-0.38, 0.04, 0.99), fingers=0.75, head_pitch=0.10, drawn=0.0, two=0.0)
    o.key_visibility(1, False)
    fo = o.walk(73, [(-7.8, 3.0), (-3.0, LINE)], step_len=0.66, step_frames=11, width=0.44, first='R', arm_swing='R')
    move(o, fo + 2, fo + 18, -3.0, LINE, OY, 0.75, 0.5, 'L')
    o.key(fo + 18, head_pitch=0.0, head_yaw=0.0, crouch=0.05, handR=(-0.38, 0.04, 0.99))

    r.stand(1, 0.8, 12.4, R(17), width=0.42)
    r.key(1, head_pitch=0.30, drawn=0.0, fingers=0.5)
    r.key_visibility(1, False)
    fr = r.walk(108, [(0.8, 12.4), (2.4, 7.2), (2.8, 3.9)], step_len=0.72, step_frames=9, width=0.40, first='L')
    r.ch['handL'].keys = [k for k in r.ch['handL'].keys if k[0] <= 216]
    r.key(226, handL=(0.17, 0.14, 1.84)); r.pin(226, 'head_pitch')        # fingers to the hat brim ...
    r.key(238, head_pitch=-0.12, handL=(0.17, 0.10, 1.90))                 # ... and the head comes up
    r.key(248, handL=(0.36, 0.04, 0.98), head_pitch=0.0)
    move(r, fr + 2, fr + 16, 2.8, LINE, RY, 0.7, -0.5, 'R')

    # --- both draw
    o.pin(243)
    o.key(250, handR=(0.14, 0.44, 1.33), chest_twist=0.5, chest_pitch=0.16, crouch=0.10, hip_twist=0.10, drawn=0.0)
    o.key(251, 'hold', drawn=1.0); o.key_visibility(251, True)
    o.sword(251, 'R', (0.14, 0.44, 1.33), (0.19, -1.0, -0.64), edge=(0, 0, 1), ease='hold')
    o.sword(257, 'R', (-0.05, 0.68, 1.45), (0.35, -0.75, -0.50), edge=(0, 0, 1), ease='i')
    o.sword(264, 'R', (-0.40, 0.30, 1.62), (-0.15, 0.35, 0.90), ease='o')
    o.key(264, chest_twist=-0.20, two=0.0, fingers=1.1); o.key(270, two=1.0)
    oni_guard(o, 272)

    r.pin(251)
    r.key(258, handR=(-0.27, -0.17, 1.80), handL=(0.27, -0.17, 1.80), chest_pitch=0.04, crouch=0.08, head_pitch=0.0, drawn=0.0)
    r.key(259, 'hold', drawn=1.0, fingers=1.1); r.key_visibility(259, True)
    for s, sx in (('R', -1), ('L', 1)):
        r.sword(259, s, (sx * 0.27, -0.19, 1.80), (-sx * 0.52, -0.03, -0.85), ease='hold')
        r.sword(265, s, (sx * 0.48, 0.05, 2.02), (-sx * 0.25, -0.45, -0.85), ease='i')
        r.sword(271, s, (sx * 0.55, 0.25, 1.45), (sx * 0.35, 0.5, 0.75), ease='o')
    ron_guard(r, 277)

    # =========================================================== F1 dash + slow-motion clash 278-318
    o.pin(278); r.pin(278)
    o.key(286, crouch=0.30, chest_pitch=0.40, hip_twist=-0.35, chest_twist=-0.30)
    o.sword(286, 'R', (-0.38, 0.05, 1.05), (-0.3, -0.85, 0.25))
    r.key(286, crouch=0.30, chest_pitch=0.40)
    r.sword(286, 'R', (-0.50, 0.0, 1.0), (-0.5, -0.75, 0.0)); r.sword(286, 'L', (0.50, 0.0, 1.0), (0.5, -0.75, 0.0))
    o.step('R', 286, 291, -1.9, LINE - 0.3, OY - 0.1, 0.16, 'l'); o.step('L', 291, 298, -0.75, LINE + 0.3, OY + 0.1, 0.16, 'l')
    o.step('R', 298, 303, -1.45, LINE - 0.3, OY - 0.2, 0.06)
    r.step('L', 286, 291, 1.9, LINE - 0.3, RY + 0.1, 0.16, 'l'); r.step('R', 291, 298, 0.75, LINE + 0.3, RY - 0.1, 0.16, 'l')
    r.step('L', 298, 303, 1.45, LINE - 0.3, RY + 0.2, 0.06)
    o.key(293, crouch=0.24, chest_pitch=0.50); r.key(293, crouch=0.24, chest_pitch=0.50)
    o.sword(296, 'R', (-0.40, 0.0, 1.78), (-0.45, -0.35, 0.82)); o.key(296, chest_twist=-0.5)
    r.sword(296, 'R', (-0.55, -0.05, 1.45), (-0.6, -0.5, 0.6)); r.sword(296, 'L', (0.55, -0.05, 1.45), (0.6, -0.5, 0.6))
    Cc = V((0.0, LINE, 1.32))
    o.key(306, 'o', chest_twist=0.45, chest_pitch=0.35, crouch=0.25, bal=0.5)
    r.key(306, 'o', chest_pitch=0.32, crouch=0.25, bal=-0.5)
    o.sword_through(306, 'R', Cc, o.bd(306, (0.45, 0.80, 0.12)), 0.42, ease='o')
    r.sword_through(306, 'R', Cc, r.bd(306, (0.35, 0.75, 0.45)), 0.40, ease='o')
    r.sword_through(306, 'L', Cc - V((0, 0, 0.10)), r.bd(306, (-0.40, 0.75, 0.30)), 0.38, ease='o')
    Cd = Cc + V((0.07, 0, 0.05))                                           # the bind grinds toward the Ronin
    o.key(318, 'l', chest_pitch=0.42, crouch=0.28); r.key(318, 'l', chest_pitch=0.26, crouch=0.30)
    o.sword_through(318, 'R', Cd, o.bd(318, (0.40, 0.82, 0.16)), 0.40, ease='l')
    r.sword_through(318, 'R', Cd, r.bd(318, (0.38, 0.72, 0.48)), 0.38, ease='l')
    r.sword_through(318, 'L', Cd - V((0, 0, 0.10)), r.bd(318, (-0.42, 0.72, 0.32)), 0.36, ease='l')
    EV += [(306, Cc, 1.2, 0.35), (309, Cc, 0.3, 0.35), (312, Cd, 0.3, 0.4), (315, Cd, 0.25, 0.5)]

    # =========================================================== F2 three overhead strikes 319-384
    def overhead(f_up, f_hit, lunge_x, back_x, ron_x, power=1.0, hitstop=2):
        # Oni: rear foot gathers, sword goes up; front foot lunges as the blade falls
        o.pin(f_up - 8)
        o.step('R', f_up - 8, f_up - 1, back_x, LINE - 0.3, OY - 0.15, 0.07)
        o.key(f_up, crouch=0.05, chest_pitch=-0.14 * power, chest_twist=0.0, hip_twist=-0.1, head_pitch=-0.05, bal=-0.3)
        o.sword(f_up, 'R', (0.0, 0.06 - 0.12 * (power - 1), 2.0), (0.0, -0.5 - 0.3 * (power - 1), 0.86))
        o.step('L', f_up + 1, f_hit, lunge_x, LINE + 0.3, OY + 0.1, 0.10, 'i')
        # Ronin: gives ground, then both blades go up
        move(r, f_up - 8, f_up, ron_x, LINE, RY, 0.7, -0.5, 'L', 0.05)
        ron_guard(r, f_up, crouch=0.18)
        C = r.bp(f_hit, (0.0, 0.45, 1.95 - 0.06 * (power - 1)))
        o.key(f_hit, 'i', crouch=0.20, chest_pitch=0.36, bal=0.4, head_pitch=0.08)
        o.sword_through(f_hit, 'R', C, o.bd(f_hit, (0.0, 0.95, 0.30)), 0.50, ease='i')
        r.key(f_hit, 'i', crouch=0.12, chest_pitch=-0.04, head_pitch=-0.15)
        cross_block(r, f_hit, C)
        o.hold(f_hit, f_hit + hitstop); r.hold(f_hit, f_hit + hitstop)
        sink = 0.12 * power
        fs = f_hit + hitstop + 4
        o.key(fs, 'o', crouch=0.24, chest_pitch=0.42)
        o.sword_through(fs, 'R', C - V((0, 0, sink)), o.bd(fs, (0.0, 0.96, 0.24)), 0.50, ease='o')
        r.key(fs, 'o', crouch=0.16 + 0.14 * power, chest_pitch=0.02)
        cross_block(r, fs, C, 'o', sink)
        EV.append((f_hit, C, 0.8 * power, 1.0))
        return C

    o.pin(319); r.pin(319)
    overhead(327, 334, 0.45, -0.45, 1.45)
    overhead(347, 354, 1.00, 0.10, 2.00)
    C3 = overhead(367, 374, 1.55, 0.65, 2.50, power=1.5, hitstop=3)
    o.key(384, 'l', chest_pitch=0.48, crouch=0.27); r.key(384, 'l', crouch=0.44)

    # =========================================================== F3 throw-off, spin, kick, slide 385-456
    o.pin(385); r.pin(385)
    r.key(391, 'i', crouch=0.05, chest_pitch=-0.05)
    P = r.bp(391, (0.35, 0.50, 2.05))
    r.sword_through(391, 'R', P, r.bd(391, (0.85, 0.2, 0.5)), 0.42, ease='i')
    r.sword_through(391, 'L', P - V((0, 0, 0.03)), r.bd(391, (-0.6, 0.3, 0.74)), 0.42, ease='i')
    o.step('L', 386, 392, 0.90, LINE + 0.3, OY + 0.1, 0.06)
    o.key(391, 'i', chest_pitch=-0.20, chest_twist=-0.30, crouch=0.10, bal=-0.4)
    o.sword(391, 'R', (-0.45, 0.15, 1.95), (-0.5, -0.2, 0.85), ease='i')
    # spin: one full turn to the left on quick pivot steps, blades trailing
    cx = 2.3
    r.pin(393, 'yaw'); r.key(409, 'l', yaw=RY + R(360))
    for i, f in enumerate((397, 401, 405, 409)):
        yw = RY + R(90) * (i + 1)
        Pp = pts(r, cx, LINE, yw, 0.55, 0.0)
        s = 'L' if i % 2 == 0 else 'R'
        r.step(s, f - 4, f, *Pp[s], lift=0.05, ease='l')
        other = 'R' if s == 'L' else 'L'
        cur = r.ch['foot' + other].at(f)
        r.ch['foot' + other].key(f, (cur.x, cur.y, yw - (0.12 if other == 'R' else -0.12) , 0.0), 'l')   # pivot in place
    RY += R(360)
    for f in range(393, 410, 2):
        r.key(f, 'l', crouch=0.20, chest_pitch=0.10, chest_twist=0.25, hip_twist=0.0)
        r.sword(f, 'R', (-0.45, 0.35, 1.32), (-0.30, 0.95, 0.04), ease='l')
        r.sword(f, 'L', (0.50, -0.05, 1.30), (0.80, -0.5, 0.0), ease='l')
    o.key(400, crouch=0.16, chest_pitch=0.10, chest_twist=0.0, bal=0.0)
    o.sword(400, 'R', (-0.05, 0.38, 1.25), (0.05, 0.6, 0.78))
    st = r.state(408)
    Csp = st['guard_R'] + (st['tip_R'] - st['guard_R']).normalized() * 0.50
    o.sword_through(408, 'R', Csp, o.bd(408, (0.10, 0.25, 0.95)), 0.36, ease='i')
    o.key(408, 'i', chest_twist=-0.25, crouch=0.20)
    o.hold(408, 410); r.hold(409, 411)
    EV.append((408, Csp, 0.9, 1.0))
    # front kick
    r.pin(411)
    r.key(414, bal=0.9, off=(0.0, 0.10), chest_pitch=-0.10, crouch=0.10, fzR=0.55)
    r.ch['footR'].key(414, (1.95, LINE, RY, 0.0))
    r.sword(414, 'R', (-0.60, 0.05, 1.35), (-0.7, 0.2, 0.6)); r.sword(414, 'L', (0.60, 0.05, 1.35), (0.7, 0.2, 0.6))
    r.key(418, 'i', off=(0.0, 0.28), chest_pitch=-0.28, fzR=1.16, heelR=0.5)
    r.ch['footR'].key(418, (1.18, LINE, RY, 0.0), 'i')
    r.hold(418, 420)
    r.key(424, fzR=0.5, off=(0.0, 0.05), chest_pitch=0.0, heelR=0.0); r.ch['footR'].key(424, (1.9, LINE + 0.2, RY, 0.0))
    Pp = pts(r, 2.15, LINE, RY, 0.7, -0.5)
    r.key(429, fzR=0.0, bal=0.0, off=(0.0, 0.0)); r.ch['footR'].key(429, (*Pp['R'], 0.0))
    ron_guard(r, 436)
    # Oni is driven back and skids
    o.pin(417)
    o.key(419, 'i', chest_pitch=0.55, crouch=0.30, head_pitch=0.30, two=0.0, bal=-0.3)
    o.sword(419, 'R', (-0.60, 0.10, 1.20), (-0.5, 0.3, 0.8), ease='i')
    o.key(419, handL=(0.30, 0.40, 1.10))
    slide(o, 419, 444, -1.95, LINE, OY, 0.75, 0.6)
    o.key(444, 'o', crouch=0.42, chest_pitch=0.38, head_pitch=0.0)
    o.key(448, two=0.0); o.key(454, two=1.0)
    oni_guard(o, 456, crouch=0.18)
    move(r, 440, 456, 0.05, LINE, RY, 0.7, -0.5, 'R', 0.10, 'l')
    ron_guard(r, 456)

    # =========================================================== F4 fast exchange 457-528
    o.pin(457); r.pin(457)
    # A: Oni diagonal cut, Ronin parries with the right blade
    o.step('L', 460, 467, -0.60, LINE + 0.3, OY + 0.1, 0.10, 'i')
    o.key(463, chest_twist=0.35, crouch=0.10, bal=-0.2); o.sword(463, 'R', (0.35, 0.05, 1.80), (0.5, -0.3, 0.8))
    CA = V((-0.42, LINE, 1.36))
    o.key(468, 'i', chest_twist=-0.40, chest_pitch=0.30, crouch=0.24, bal=0.7)
    o.sword_through(468, 'R', CA, o.bd(468, (-0.45, 0.80, -0.15)), 0.50, ease='i')
    r.key(468, 'i', chest_twist=0.25, crouch=0.20)
    r.sword_through(468, 'R', CA, r.bd(468, (0.25, 0.35, 0.90)), 0.35, ease='i')
    r.sword(468, 'L', (0.45, -0.10, 1.30), (0.6, -0.6, 0.5))
    o.hold(468, 469); r.hold(468, 469)
    EV.append((468, CA, 0.7, 1.0))
    o.step('R', 469, 475, -1.45, LINE - 0.3, OY - 0.15, 0.05)
    # B: Ronin's left blade sweeps at the flank, Oni hangs his sword tip-down to stop it
    r.key(474, chest_twist=0.5, bal=0.3); r.sword(474, 'L', (0.60, -0.10, 1.25), (0.7, -0.7, 0.1))
    CB = o.bp(480, (-0.36, 0.45, 1.15))
    r.key(480, 'i', chest_twist=-0.45, crouch=0.24, bal=-0.4)
    r.sword_through(480, 'L', CB, r.bd(480, (-0.75, 0.65, 0.0)), 0.50, ease='i')
    r.sword(480, 'R', (-0.45, 0.20, 1.45), (-0.2, 0.5, 0.85))
    o.key(480, 'i', chest_twist=-0.30, chest_pitch=0.15, crouch=0.22, bal=0.0)
    o.sword_through(480, 'R', CB, o.bd(480, (-0.05, 0.20, -0.97)), 0.36, edge=o.bd(480, (-1, 0, 0)), ease='i')
    o.hold(480, 481); r.hold(480, 481)
    EV.append((480, CB, 0.7, 1.0))
    # C: both go high together and lock
    o.key(486, chest_twist=0.0, crouch=0.10); o.sword(486, 'R', (-0.20, 0.0, 1.95), (-0.2, -0.5, 0.85))
    r.key(486, chest_twist=0.0, crouch=0.10)
    r.sword(486, 'R', (-0.50, 0.0, 1.75), (-0.5, -0.4, 0.75)); r.sword(486, 'L', (0.50, 0.0, 1.75), (0.5, -0.4, 0.75))
    mx = (o.state(492)['P']['hips'].x + r.state(492)['P']['hips'].x) / 2
    CC = V((mx, LINE, 1.66))
    o.key(492, 'i', chest_pitch=0.30, crouch=0.20, bal=0.5); r.key(492, 'i', chest_pitch=0.28, crouch=0.20, bal=-0.5)
    o.sword_through(492, 'R', CC, o.bd(492, (0.15, 0.90, 0.40)), 0.50, ease='i')
    r.sword_through(492, 'R', CC, r.bd(492, (0.50, 0.60, 0.60)), 0.42, ease='i')
    r.sword_through(492, 'L', CC - V((0, 0, 0.05)), r.bd(492, (-0.50, 0.60, 0.60)), 0.42, ease='i')
    o.hold(492, 495); r.hold(492, 495)
    o.hold(495, 500); r.hold(495, 500)
    EV += [(492, CC, 1.1, 1.0), (497, CC, 0.3, 1.0)]
    # shove apart
    move(o, 500, 512, -1.65, LINE, OY, 0.75, 0.5, 'L', 0.09)
    move(r, 500, 512, 1.15, LINE, RY, 0.7, -0.5, 'R', 0.09)
    oni_guard(o, 514); ron_guard(r, 514)
    o.hold(514, 526); r.hold(514, 528)

    # =========================================================== F5 power slash 529-600
    o.pin(527)
    o.key(546, crouch=0.38, hip_twist=-0.60, chest_twist=-0.55, chest_pitch=0.30, bal=-0.7, head_yaw=0.5)
    o.sword(546, 'R', (-0.55, -0.25, 1.00), (-0.5, -0.85, 0.15))
    o.hold(546, 549)
    o.step('L', 549, 555, -0.20, LINE + 0.3, OY + 0.1, 0.12, 'i')
    for f, g, d, tw in ((551, (-0.55, 0.35, 1.25), (-0.75, 0.6, 0.1), -0.2), (553, (-0.10, 0.60, 1.30), (0.0, 1.0, 0.0), 0.2),
                        (556, (0.45, 0.40, 1.35), (0.8, 0.55, 0.05), 0.6), (561, (0.55, 0.15, 1.45), (0.8, -0.3, 0.5), 0.75)):
        o.key(f, 'l', chest_twist=tw, hip_twist=tw * 0.6, crouch=0.30, bal=0.6, head_yaw=0.0)
        o.sword(f, 'R', g, d, edge=o.bd(f, (1, 0, 0)), ease='l' if f < 561 else 'o')
    o.step('R', 556, 563, -1.00, LINE - 0.3, OY - 0.15, 0.05)
    o.hold(561, 568)
    oni_guard(o, 580, crouch=0.18)
    # Ronin springs back out of the arc, lands low and skids
    r.pin(545)
    r.key(550, crouch=0.32, chest_pitch=0.25)
    Pj = pts(r, 2.9, LINE, RY, 0.8, -0.3)
    for s in ('L', 'R'):
        r.pin(550, 'foot' + s); r.ch['foot' + s].key(558, (*Pj[s], 0.42), 'l')
    r.key(554, crouch=-0.28, chest_pitch=0.30)
    r.sword(554, 'R', (-0.45, 0.30, 1.30), (0.6, 0.6, 0.5)); r.sword(554, 'L', (0.45, 0.30, 1.25), (-0.6, 0.6, 0.5))
    r.key(559, 'i', crouch=0.42, chest_pitch=0.45)
    slide(r, 559, 572, 3.40, LINE, RY, 0.8, -0.3)
    r.sword(560, 'R', (-0.60, 0.10, 1.00), (-0.6, 0.3, 0.74)); r.sword(560, 'L', (0.60, 0.10, 1.00), (0.6, 0.3, 0.74))
    r.hold(560, 572)
    ron_guard(r, 584, crouch=0.18)
    # both settle into the final ready stances
    o.pin(588); r.pin(588)
    o.key(600, crouch=0.30, chest_pitch=0.30, hip_twist=0.25, chest_twist=0.30, bal=-0.3, head_yaw=-0.3)
    o.sword(600, 'R', (0.28, 0.18, 1.05), (0.25, -0.92, -0.20), edge=(0, 0, 1))
    r.key(600, crouch=0.30, chest_pitch=0.34, bal=0.3)
    r.sword(600, 'R', (-0.50, 0.0, 0.95), (-0.4, -0.85, -0.1)); r.sword(600, 'L', (0.50, 0.0, 0.95), (0.4, -0.85, -0.1))
    o.hold(600, 612); r.hold(600, 612)

    # =========================================================== F6 final crossing 613-660 (slow motion 621-640)
    yo, yr = LINE - 0.28, LINE + 0.28                                     # they pass shoulder to shoulder
    o.step('R', 613, 617, 0.30, yo - 0.25, OY - 0.1, 0.14, 'l'); o.step('L', 617, 621, 1.10, yo + 0.25, OY + 0.1, 0.14, 'l')
    o.step('R', 621, 640, 1.90, yo - 0.25, OY - 0.1, 0.12, 'l'); o.step('L', 640, 648, 2.75, yo + 0.25, OY + 0.1, 0.12, 'l')
    o.step('R', 648, 654, 2.05, yo - 0.30, OY - 0.25, 0.05)
    r.step('L', 613, 617, 2.60, yr - 0.25, RY + 0.1, 0.14, 'l'); r.step('R', 617, 621, 1.80, yr + 0.25, RY - 0.1, 0.14, 'l')
    r.step('L', 621, 640, 1.00, yr - 0.25, RY + 0.1, 0.12, 'l'); r.step('R', 640, 648, 0.15, yr + 0.25, RY - 0.1, 0.12, 'l')
    r.step('L', 648, 654, 0.85, yr - 0.30, RY + 0.25, 0.05)
    o.key(619, crouch=0.26, chest_pitch=0.45, chest_twist=-0.5); o.sword(619, 'R', (-0.50, -0.10, 1.25), (-0.6, -0.75, 0.1))
    r.key(619, crouch=0.26, chest_pitch=0.45, chest_twist=0.5)
    r.sword(619, 'L', (0.50, -0.10, 1.30), (0.6, -0.75, 0.1)); r.sword(619, 'R', (-0.40, 0.10, 1.40), (-0.3, -0.5, 0.8))
    CX = V((1.45, LINE, 1.30))
    o.key(628, 'l', chest_twist=0.20, crouch=0.28); r.key(628, 'l', chest_twist=-0.20, crouch=0.28)
    o.sword_through(628, 'R', CX, o.bd(628, (0.75, 0.60, 0.05)), 0.50, edge=o.bd(628, (1, 0, 0)), ease='l')
    r.sword_through(628, 'L', CX, r.bd(628, (0.60, 0.75, 0.0)), 0.50, edge=r.bd(628, (1, 0, 0)), ease='l')
    r.sword(628, 'R', (-0.20, 0.50, 1.40), (0.5, 0.8, 0.2), ease='l')
    o.key(640, 'l', chest_twist=0.70, chest_pitch=0.40); o.sword(640, 'R', (0.55, 0.25, 1.20), (0.85, -0.2, -0.3), ease='l')
    r.key(640, 'l', chest_twist=-0.60, chest_pitch=0.40)
    r.sword(640, 'L', (0.55, -0.15, 1.15), (0.6, -0.7, -0.3), ease='l'); r.sword(640, 'R', (-0.30, 0.50, 1.15), (-0.2, 0.9, -0.3), ease='l')
    o.key(654, 'o', crouch=0.32, chest_pitch=0.34, chest_twist=0.55, hip_twist=0.2, head_pitch=0.12, bal=0.4)
    o.sword(654, 'R', (0.50, 0.30, 1.00), (0.8, 0.2, -0.5), ease='o')
    r.key(654, 'o', crouch=0.32, chest_pitch=0.34, chest_twist=-0.45, head_pitch=0.14, bal=-0.4)
    r.sword(654, 'L', (0.52, -0.20, 1.10), (0.6, -0.7, -0.3), ease='o'); r.sword(654, 'R', (-0.35, 0.45, 1.05), (-0.2, 0.9, -0.38), ease='o')
    EV.append((628, CX, 1.4, 0.3))
    # =========================================================== F7 frozen back to back 655-720
    o.hold(654, 720); r.hold(654, 720)
    r.key(676, head_pitch=0.14); r.key(690, head_pitch=0.02)
    return EV
