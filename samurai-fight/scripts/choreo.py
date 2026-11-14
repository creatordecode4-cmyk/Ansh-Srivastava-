"""Blocking pass of the 30 s fight (24 fps, frames 1-720). All coordinates are world metres.
Oni fights facing north (90 deg), Ronin facing south (-90 deg); the duel runs along Y near x = -2.3.
Local specs are (l, f, z) = (to the character's left, forward, up)."""
import bpy, math
from mathutils import Vector
import anim_lib as A

OK, RR, RL = 'Oni_Katana', 'Ronin_Katana_R', 'Ronin_Katana_L'
N, S, E = 90.0, -90.0, 0.0
PA, PB = Vector((-2.6, 0.2)), Vector((-2.0, 10.3))          # standoff marks
C = Vector((-2.3, 5.25))                                     # where they first meet


def loc(tsuba, blade, edge):
    return ('local', tsuba, blade, edge)


def relaxed(s, sw=0.0):
    g = 1 if s == 'L' else -1
    return ((0.33 * g, 0.03 + sw, 0.90), (0.08 * g, 0.12, -1.0), (-1.0 * g, 0.0, 0.0))


def feet(act, f0, f1, pos, face, spec, lift=0.08, plant=False):
    F, L = A.basis(face)
    for s, (l, f, yaw) in spec.items():
        xy = Vector(pos[:2]) + L.xy * l + F.xy * f
        if plant:
            act.plant(s, f1, xy, face + yaw)
        else:
            act.step(s, f0, f1, xy, face + yaw, lift=lift)


def head(p, z=1.72):
    return (p[0], p[1], z)


# ---------------------------------------------------------------- pose libraries (local)
O_GUARD = loc((0.00, 0.44, 1.07), (0, 0.90, 0.43), (0, 0.43, -0.90))
O_JODAN = loc((0.00, 0.08, 1.90), (0, -0.50, 0.87), (0, 0.87, 0.50))
O_WAKI = loc((-0.26, 0.04, 0.96), (-0.25, -0.85, -0.45), (0.2, 0.3, -0.9))
O_KESA_UP = loc((-0.24, 0.02, 1.72), (-0.25, -0.45, 0.86), (0.3, 0.8, 0.5))
O_SHEATH = ('hip', (0.174, -0.248, 1.159), (0.220, 0.823, -0.524), (0, 0, 1))
O_ST = {'R': (-0.17, 0.36, -8), 'L': (0.27, -0.38, 50)}          # right foot leads
O_ST_W = {'R': (-0.20, 0.50, -6), 'L': (0.30, -0.55, 55)}        # deep lunge
R_GUARD = {RR: loc((-0.27, 0.40, 0.99), (0.18, 0.94, 0.28), (0, 0.28, -0.94)), RL: loc((0.27, 0.22, 1.30), (-0.24, 0.82, 0.52), (0, 0.52, -0.82))}
R_RUN = {RR: loc((-0.40, -0.05, 0.98), (-0.35, -0.85, -0.38), (0, 0.3, -0.95)), RL: loc((0.40, -0.05, 0.98), (0.35, -0.85, -0.38), (0, 0.3, -0.95))}
R_SHEATH = {RR: ('hip', (-0.168, 0.233, 1.702), (0.527, 0.086, -0.846), (0, 1, 0)), RL: ('hip', (0.168, 0.233, 1.702), (-0.527, 0.086, -0.846), (0, 1, 0))}
R_ST = {'L': (0.17, 0.34, 8), 'R': (-0.25, -0.36, -48)}          # left foot leads
R_ST_W = {'L': (0.20, 0.48, 6), 'R': (-0.30, -0.52, -55)}


def block_cross(k):
    """Ronin's crossed-blade block through world point k (he faces south)."""
    return {RR: ('thru', k, (0.80, -0.15, 0.58), (0, -0.3, 1), 0.42), RL: ('thru', k, (-0.80, -0.15, 0.58), (0, -0.3, 1), 0.40)}


def build(oni, ron, sc):
    T = {}                                                   # named frames/points other modules (cameras, FX) can read
    # ================================================================ 0-3 s  empty arena (drone); both wait off-stage
    W0 = Vector((-6.5, 0.2))
    oni.plant('L', 1, W0 + Vector((0, 0.13)), E + 8)
    oni.plant('R', 1, W0 + Vector((0, -0.13)), E - 8)
    oni_free = dict(grip={'L': 0, 'R': 0}, curl={'L': 0.3, 'R': 0.3}, show={OK: False})
    lh_on_hilt = ('hip', (0.25, -0.20, 1.25), (-0.25, -0.85, 0.3), (0.0, 0.2, -1.0))
    oni.key(1, W0, E, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=(0, 0.2, 1.6), **oni_free)
    oni.key(72, W0, E, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=(0, 0.2, 1.6))
    feet(ron, 1, 1, PB, S, {'L': (0.14, 0.0, 8), 'R': (-0.14, 0.0, -8)}, plant=True)
    ron_free = dict(grip={'L': 0, 'R': 0}, curl={'L': 0.3, 'R': 0.3}, show={RR: False, RL: False})
    ron.key(1, PB, S, hands={'L': relaxed('L'), 'R': relaxed('R')}, spine=(0, 2, 0), look=(PB.x, PB.y - 3, 1.2), **ron_free)

    # ================================================================ 3-6 s  Oni walks in from the left, hand on the hilt
    def walk_pose(fr, k, pos, side):
        g = 1 if side == 'L' else -1                         # the right arm swings against the legs
        sw = (0.20 * g) if k % 2 == 0 else 0.0
        return dict(hands={'L': lh_on_hilt, 'R': ((-0.34, sw, 0.92), (-0.08, 0.12 + sw, -1.0), (1.0, 0.0, 0.0))}, look=(pos.x + 8, pos.y + 1.5, 1.65))
    oni.travel(73, 150, W0, PA, E, 6, lead='R', pose=walk_pose, lean=3.0, bob=0.022, yaw_sway=5.0,
               end_stance={'R': (-0.14, 0.0, -10), 'L': (0.14, 0.0, 10)})
    T['oni_walk'] = (73, 150, W0.copy(), PA.copy())
    # he stops, then turns to face the gate (pivot on the spot) while the Ronin is revealed
    oni.key(160, PA, E, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=head(PB))
    feet(oni, 166, 176, PA, N, {'L': (0.16, -0.05, 14)}, lift=0.05)
    feet(oni, 178, 188, PA, N, {'R': (-0.16, 0.05, -14)}, lift=0.05)
    oni.key(190, PA, N, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=head(PB), spine=(0, 2, 0))
    oni.key(215, PA, N, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=head(PB), spine=(0, 2, 0))

    # ================================================================ 6-10 s  Ronin under the torii, lifts his hat; both draw
    brim = ((-0.08, 0.27, 1.72), (0.05, -0.35, 0.93), (0.0, -1.0, -0.3))      # right hand under the front of the brim, fingertips on its edge
    ron.key(180, PB, S, hands={'L': relaxed('L'), 'R': relaxed('R')}, spine=(0, 2, 0), look=(PB.x, PB.y - 3, 1.2))
    ron.key(194, PB, S, hands={'L': relaxed('L'), 'R': brim}, spine=(0, 2, 0), look=(PB.x, PB.y - 3, 1.25), curl={'R': 0.6})
    ron.key(208, PB, S, hands={'L': relaxed('L'), 'R': ((-0.08, 0.27, 1.79), (0.05, -0.40, 0.91), (0.0, -1.0, -0.35))}, spine=(0, -3, 0), look=head(PA, 2.6))
    ron.key(215, PB, S, hands={'L': relaxed('L'), 'R': ((-0.08, 0.27, 1.79), (0.05, -0.40, 0.91), (0.0, -1.0, -0.35))}, spine=(0, -3, 0), look=head(PA, 2.6))
    T['hat_lift'] = (194, 208)
    # --- Oni draws (216-240)
    oni.key(216, PA, N, hands={'L': lh_on_hilt, 'R': relaxed('R')}, look=head(PB), spine=(0, 2, 0))
    oni.key(221, PA, N, hands={'L': ('hip', (0.27, -0.06, 1.13), (-0.2, -0.9, -0.2), (-0.9, 0.1, -0.3)), 'R': ('hip', (0.02, -0.40, 1.22), (0.8, -0.2, 0.2), (0.0, 0.3, -1.0))},
            sw={OK: O_SHEATH}, look=head(PB), spine=(12, 6, 0), hips=dict(yaw=6))
    oni.key(223, PA, N, sw={OK: O_SHEATH}, grip={'R': 1}, curl={'R': 1}, show={OK: True}, look=head(PB), spine=(14, 7, 0), hips=dict(yaw=8))
    T['oni_draw'] = 223
    feet(oni, 223, 231, PA, N, {'R': O_ST['R']}, lift=0.06)
    oni.key(227, PA, N, sw={OK: ('hip', (0.086, -0.577, 1.369), (0.220, 0.823, -0.524), (0, 0, 1))}, look=head(PB), spine=(4, 5, 0), hips=dict(yaw=2, z=0.92))
    oni.key(231, PA, N, sw={OK: loc((-0.30, 0.42, 1.30), (0.10, 0.75, 0.65), (0.4, 0.5, -0.75))}, look=head(PB), spine=(-14, 3, 0), hips=dict(yaw=12, z=0.89, pitch=4))
    feet(oni, 231, 238, PA, N, {'L': O_ST['L']}, lift=0.05)
    oni.key(235, PA, N, sw={OK: loc((-0.08, 0.46, 1.16), (0.03, 0.88, 0.47), (0, 0.45, -0.89))}, look=head(PB), spine=(-12, 3, 0), hips=dict(yaw=15, z=0.86, pitch=6),
            hands={'L': ((0.10, 0.30, 1.02), (-0.5, 0.8, 0.2), (0.3, 0.2, -0.9))})
    oni.key(240, PA, N, sw={OK: O_GUARD}, grip={'L': 1}, curl={'L': 1}, look=head(PB), spine=(-10, 3, 0), hips=dict(yaw=16, z=0.85, pitch=6))
    # --- Ronin draws both blades over his shoulders (216-240)
    over = lambda g: ('hip', (0.20 * g, 0.20, 1.80), (0.3 * g, 0.5, 0.8), (-0.2 * g, 0.9, -0.3))
    ron.key(222, PB, S, hands={'L': over(1), 'R': over(-1)}, sw=R_SHEATH, spine=(0, -2, 0), look=head(PA))
    ron.key(224, PB, S, sw=R_SHEATH, grip={'L': 1, 'R': 1}, curl={'L': 1, 'R': 1}, show={RR: True, RL: True}, spine=(0, -2, 0), look=head(PA))
    T['ron_draw'] = 224
    up = lambda g: ('hip', (0.405 * g, 0.194, 2.083), (-0.527 * g, 0.086, -0.846), (0, 1, 0))
    ron.key(228, PB, S, sw={RR: up(-1), RL: up(1)}, spine=(0, 0, 0), look=head(PA))
    feet(ron, 228, 236, PB, S, {'L': R_ST['L']}, lift=0.06)
    ron.key(232, PB, S, sw={RR: loc((-0.42, 0.20, 1.62), (-0.25, 0.45, 0.86), (0.2, 0.8, -0.5)), RL: loc((0.42, 0.20, 1.62), (0.25, 0.45, 0.86), (-0.2, 0.8, -0.5))},
            spine=(0, 4, 0), look=head(PA), hips=dict(z=0.93))
    feet(ron, 232, 239, PB, S, {'R': R_ST['R']}, lift=0.05)
    ron.key(240, PB, S, sw=R_GUARD, spine=(8, 4, 0), look=head(PA), hips=dict(z=0.87, yaw=-16, pitch=6))

    # ================================================================ 10-12 s  both dash, slow-motion clash
    oc, rc = C + Vector((0, -0.92)), C + Vector((0, 0.92))        # where each stands at the clash
    K = Vector((C.x, C.y, 1.40))
    T['clash'] = (270, K.copy())
    orun = lambda fr, k, pos, side: dict(sw={OK: O_WAKI}, look=head(rc), spine=(-8 if side == 'L' else 8, 14, 0))
    oni.travel(241, 262, PA, oc + Vector((0, -0.75)), N, 4, lead='L', pose=orun, lean=16, bob=0.04, hipz=0.90, lift=0.20, swing=1.25, width=0.10, ease='in')
    rrun = lambda fr, k, pos, side: dict(sw=R_RUN, look=head(oc), spine=(-8 if side == 'L' else 8, 16, 0))
    ron.travel(241, 262, PB, rc + Vector((0, 0.75)), S, 4, lead='R', pose=rrun, lean=18, bob=0.04, hipz=0.90, lift=0.20, swing=1.25, width=0.10, ease='in')
    # last stride into the bind, stretched for slow motion (263-270), then the lock (270-288)
    feet(oni, 262, 269, oc, N, {'R': O_ST_W['R']}, lift=0.12)
    feet(oni, 268, 274, oc, N, {'L': O_ST_W['L']}, lift=0.04)
    oni.key(266, oc + Vector((0, -0.35)), N, sw={OK: O_KESA_UP}, look=head(rc), spine=(-22, 6, 0), hips=dict(z=0.88, yaw=-10, pitch=8))
    o_bind = lambda k: {OK: ('thru', k, (-0.35, 0.50, 0.79), (0.1, 0.8, -0.6), 0.50)}
    oni.key(270, oc, N, sw=o_bind(K), look=head(rc), spine=(14, 12, 0), hips=dict(z=0.80, yaw=14, pitch=12))
    feet(ron, 262, 269, rc, S, {'L': R_ST_W['L']}, lift=0.12)
    feet(ron, 268, 274, rc, S, {'R': R_ST_W['R']}, lift=0.04)
    ron.key(266, rc + Vector((0, 0.35)), S, sw={RR: loc((-0.45, 0.10, 1.45), (-0.5, 0.2, 0.84), (0.3, 0.8, -0.4)), RL: loc((0.45, 0.10, 1.45), (0.5, 0.2, 0.84), (-0.3, 0.8, -0.4))},
            look=head(oc), spine=(0, 8, 0), hips=dict(z=0.88, pitch=8))
    r_bind = lambda k: {RR: ('thru', k, (0.45, -0.45, 0.77), (0, -0.8, 0.5), 0.42), RL: ('thru', k, (-0.45, -0.45, 0.77), (0, -0.8, 0.5), 0.38)}
    ron.key(270, rc, S, sw=r_bind(K), look=head(oc), spine=(0, 12, 0), hips=dict(z=0.80, pitch=12))
    K2 = K + Vector((0, 0.16, -0.05))                            # the Oni's weight drives the bind toward the Ronin
    oni.key(288, oc + Vector((0, 0.10)), N, sw=o_bind(K2), look=head(rc), spine=(16, 15, 0), hips=dict(z=0.78, yaw=14, pitch=15))
    ron.key(288, rc + Vector((0, 0.06)), S, sw=r_bind(K2), look=head(oc), spine=(0, 9, 0), hips=dict(z=0.77, pitch=9))

    # ================================================================ 12-15 s  three heavy overhead strikes, crossed-blade parries
    op, rp = oc.copy(), rc.copy()
    # break: the Oni shoves him back
    rp = rp + Vector((0, 0.55))
    ron.slide(289, 297, (0, 0.55))
    ron.key(296, rp, S, sw=R_GUARD, look=head(op), spine=(8, 2, 0), hips=dict(z=0.84, yaw=-14, pitch=2))
    oni.key(294, op, N, sw={OK: loc((0.05, 0.55, 1.20), (0.1, 0.95, 0.30), (0, 0.3, -0.95))}, look=head(rp), spine=(8, 10, 0), hips=dict(z=0.84, yaw=14, pitch=10))
    T['strikes'] = []
    for i, f in enumerate((297, 317, 337)):
        # anticipation: sword all the way up, weight back (8 frames)
        oni.key(f + 7, op + Vector((0, -0.10)), N, sw={OK: O_JODAN}, look=head(rp), spine=(0, -8, 0), hips=dict(z=0.90, yaw=6, pitch=-3))
        # the cut lands in 4 frames with a step in; the Ronin catches it on crossed blades above his head
        op = op + Vector((0, 0.45))
        feet(oni, f + 7, f + 11, op, N, {'R': O_ST_W['R']}, lift=0.10)
        kk = Vector((rp.x, rp.y - 0.40, 1.93 - 0.05 * i))
        T['strikes'].append((f + 11, kk.copy()))
        ron.key(f + 6, rp, S, sw=block_cross(kk + Vector((0, 0, 0.10))), look=head(op, 2.0), spine=(0, -4, 0), hips=dict(z=0.86, pitch=-2))
        oni.key(f + 11, op, N, sw={OK: ('thru', kk, (0.0, 0.97, 0.24), (0, 0.24, -0.97), 0.60)}, look=head(rp), spine=(0, 20, 0), hips=dict(z=0.80, yaw=10, pitch=14))
        ron.key(f + 11, rp, S, sw=block_cross(kk), look=head(op, 2.0), spine=(0, -2, 0), hips=dict(z=0.84, pitch=0))
        # hit-stop (3 frames), then the blow drives him down and back
        oni.key(f + 13, op, N, sw={OK: ('thru', kk, (0.0, 0.97, 0.24), (0, 0.24, -0.97), 0.60)}, look=head(rp), spine=(0, 20, 0), hips=dict(z=0.80, yaw=10, pitch=14))
        ron.key(f + 13, rp, S, sw=block_cross(kk), look=head(op, 2.0), spine=(0, -2, 0), hips=dict(z=0.84, pitch=0))
        back = 0.42
        ron.slide(f + 13, f + 19, (0, back))
        rp = rp + Vector((0, back))
        kd = Vector((rp.x, rp.y - 0.40, 1.74 - 0.05 * i))
        ron.key(f + 18, rp, S, sw=block_cross(kd), look=head(op, 1.9), spine=(0, 4, 0), hips=dict(z=0.74 - 0.03 * i, pitch=4))
        oni.key(f + 18, op + Vector((0, 0.12)), N, sw={OK: ('thru', kd + Vector((0, -0.05, 0)), (0.0, 0.98, 0.18), (0, 0.18, -0.98), 0.60)}, look=head(rp), spine=(0, 22, 0),
                hips=dict(z=0.78, yaw=10, pitch=16))
        feet(oni, f + 14, f + 19, op, N, {'L': O_ST_W['L']}, lift=0.06)
    # after the third blow the Oni leans on him (349-360)
    oni.key(360, op + Vector((0, 0.16)), N, sw={OK: ('thru', kd + Vector((0, -0.03, -0.06)), (0.0, 0.98, 0.16), (0, 0.16, -0.98), 0.58)}, look=head(rp), spine=(0, 24, 0),
            hips=dict(z=0.77, yaw=10, pitch=17))
    ron.key(360, rp, S, sw=block_cross(kd + Vector((0, 0, -0.06))), look=head(op, 1.9), spine=(0, 5, 0), hips=dict(z=0.68, pitch=5))

    # ================================================================ 15-18 s  Ronin throws the blade off, spinning slash, kick; Oni slides back
    # throw-off to the Ronin's right (west)
    ron.key(366, rp, S, sw={RR: loc((-0.55, 0.30, 1.25), (-0.75, 0.45, 0.48), (-0.3, 0.2, -0.9)), RL: loc((-0.15, 0.40, 1.30), (-0.65, 0.60, 0.46), (-0.3, 0.2, -0.9))},
            look=head(op), spine=(-25, 6, 0), hips=dict(z=0.80, yaw=-20, pitch=5))
    oni.key(366, op + Vector((0, 0.10)), N, sw={OK: loc((0.50, 0.40, 1.00), (0.75, 0.55, -0.36), (0.3, -0.2, -0.9))}, look=head(rp), spine=(28, 14, 6), hips=dict(z=0.82, yaw=24, pitch=10))
    # spin to his left (counter-clockwise from above): face goes -90 -> 270, pivot on the left foot
    piv = ron.foot_at('L', 366)[1].copy()
    spin_frames = (367, 371, 375, 379, 383)
    for j, f in enumerate(spin_frames):
        face = S + 90 * j
        Fv, Lv = A.basis(face)
        ron.plant('L', f, piv, face + 8)
        rxy = piv - Lv.xy * 0.42 - Fv.xy * 0.30
        if j > 0:
            ron.step('R', f - 3, f, rxy, face - 40, lift=0.06)
        ctr = piv - Lv.xy * 0.17 - Fv.xy * 0.20
        ext = {RR: loc((-0.75, 0.10, 1.32), (-0.97, 0.20, 0.05), (0.2, 0.97, 0)), RL: loc((0.25, 0.30, 1.15), (0.45, 0.75, 0.45), (0, 0.5, -0.85))}
        ron.key(f, ctr, face, sw=ext, spine=(22, 5, 0), hips=dict(z=0.84, yaw=10, pitch=4), look=(ctr.x + Fv.x * 3, ctr.y + Fv.y * 3, 1.5))
    rp = (piv - A.basis(S + 360)[1].xy * 0.17 - A.basis(S + 360)[0].xy * 0.20).copy()
    SP = S + 360                                              # the Ronin's facing after the full turn (same direction, continuous angle)
    # the slash comes round at chest height; the Oni gets his blade up, edge out, on his left side (381-383)
    ks = Vector((op.x - 0.30, op.y + 0.62, 1.32))
    T['spin_hit'] = (383, ks.copy())
    oni.key(374, op, N, sw={OK: loc((0.35, 0.30, 1.05), (0.50, 0.45, -0.74), (0.6, 0.6, 0.5))}, look=head(rp), spine=(18, 8, 0), hips=dict(z=0.84, yaw=18, pitch=6))
    oni.key(383, op + Vector((0, -0.08)), N, sw={OK: ('thru', ks, (0.10, -0.15, 0.98), (-0.9, 0.4, 0), 0.38)}, look=head(rp), spine=(-10, 2, 0), hips=dict(z=0.84, yaw=4, pitch=0))
    ron.key(383, rp, SP, sw={RR: ('thru', ks, (-0.20, -0.97, 0.10), (0.97, -0.2, 0), 0.50), RL: loc((0.45, 0.05, 1.20), (0.60, 0.30, 0.74), (0, 0.5, -0.85))},
            spine=(-20, 6, 0), hips=dict(z=0.84, yaw=-12, pitch=5), look=head(op))
    # kick: chamber (385-388), drive (389-392), impact 392 on the chest
    Fv, Lv = A.basis(SP)
    arms_wide = {RR: loc((-0.62, -0.05, 1.20), (-0.80, -0.35, 0.48), (0, 0.4, -0.9)), RL: loc((0.62, -0.05, 1.20), (0.80, -0.35, 0.48), (0, 0.4, -0.9))}
    cur = ron.foot_at('R', 384)
    ron.plant('R', 384, cur[1], cur[2])
    ron.plant('R', 388, rp + Fv.xy * 0.30 - Lv.xy * 0.05, SP, lift=0.72, pitch=20)
    ron.key(388, rp, SP, sw=arms_wide, spine=(0, -6, 0), hips=dict(z=0.90, pitch=-6, l=0.06), look=head(op))
    chest = Vector((op.x, op.y + 0.16, 1.28))
    T['kick'] = (392, chest.copy())
    ron.plant('R', 392, Vector((chest.x, chest.y + 0.10)), SP, lift=chest.z - ron.ankle_h['R'], pitch=-55)
    ron.key(392, rp + Fv.xy * 0.10, SP, sw=arms_wide, spine=(0, -14, 0), hips=dict(z=0.94, pitch=-14, l=0.08), look=head(op))
    ron.plant('R', 394, Vector((chest.x, chest.y + 0.10)), SP, lift=chest.z - ron.ankle_h['R'], pitch=-55)
    ron.key(394, rp + Fv.xy * 0.10, SP, sw=arms_wide, spine=(0, -14, 0), hips=dict(z=0.94, pitch=-14, l=0.08), look=head(op))
    ron.plant('R', 398, rp + Fv.xy * 0.35 - Lv.xy * 0.08, SP, lift=0.55, pitch=10)
    feet(ron, 398, 403, rp, SP, {'R': (-0.20, 0.42, -6)}, lift=0.0)
    ron.key(404, rp + Fv.xy * 0.20, SP, sw=R_GUARD, spine=(8, 4, 0), hips=dict(z=0.86, yaw=-10, pitch=5), look=head(op))
    feet(ron, 404, 410, rp + Fv.xy * 0.20, SP, {'L': (0.22, -0.30, 40)}, lift=0.05)
    rp = rp + Fv.xy * 0.20
    R_ST_R = {'R': (-0.20, 0.22, -6), 'L': (0.22, -0.30, 40)}     # after the kick his right foot leads
    ron.key(432, rp, SP, sw=R_GUARD, spine=(8, 4, 0), hips=dict(z=0.86, yaw=-10, pitch=5), look=head(op + Vector((0, -2.6))))
    # Oni: takes it (388 braced, 392 folds), then skids 2.6 m back across the wet stone
    oni.key(388, op + Vector((0, -0.08)), N, sw={OK: ('thru', ks, (0.10, -0.15, 0.98), (-0.9, 0.4, 0), 0.38)}, look=head(rp), spine=(-6, 2, 0), hips=dict(z=0.84, yaw=4))
    oni.key(392, op + Vector((0, -0.12)), N, sw={OK: loc((0.30, 0.35, 1.25), (0.55, 0.30, 0.78), (0.4, 0.6, -0.5))}, look=head(rp), spine=(0, 22, 0), hips=dict(z=0.82, pitch=-8, f=-0.10))
    back = Vector((0, -2.6))
    oni.slide(392, 420, back, steps=5)
    T['slide'] = (392, 420, op.copy(), (op + back).copy())
    oni.key(398, op + back * 0.42, N, sw={OK: loc((-0.45, 0.10, 0.70), (-0.60, -0.65, -0.45), (0, 0.2, -0.98))}, look=head(rp), spine=(-14, 30, 0), hips=dict(z=0.66, pitch=22, f=-0.12), grip={'L': 0},
            hands={'L': ((0.42, 0.42, 0.42), (0.2, 0.9, -0.4), (0, 0.3, -1.0))}, curl={'L': 0.1})
    oni.key(408, op + back * 0.82, N, sw={OK: loc((-0.48, 0.05, 0.62), (-0.55, -0.70, -0.45), (0, 0.2, -0.98))}, look=head(rp), spine=(-14, 34, 0), hips=dict(z=0.60, pitch=24, f=-0.10),
            hands={'L': ((0.38, 0.50, 0.14), (0.1, 1.0, -0.1), (0, 0.1, -1.0))})
    op = op + back
    oni.key(420, op, N, sw={OK: loc((-0.48, 0.05, 0.60), (-0.55, -0.70, -0.45), (0, 0.2, -0.98))}, look=head(rp), spine=(-12, 34, 0), hips=dict(z=0.58, pitch=24, f=-0.06),
            hands={'L': ((0.36, 0.50, 0.10), (0.1, 1.0, -0.05), (0, 0.05, -1.0))})
    oni.key(432, op, N, sw={OK: O_GUARD}, grip={'L': 1}, curl={'L': 1}, look=head(rp), spine=(-10, 6, 0), hips=dict(z=0.84, yaw=16, pitch=6))

    # ================================================================ 18-21 s  fast three-hit exchange
    m = (op + rp) / 2
    o2, r2 = m + Vector((0, -0.86)), m + Vector((0, 0.86))
    oni.travel(433, 445, op, o2, N, 2, lead='R', pose=lambda fr, k, pos, s: dict(sw={OK: O_GUARD}, look=head(r2), spine=(-10, 10, 0)), lean=10, hipz=0.88, lift=0.10, swing=1.1,
               end_stance=O_ST, ease='out')
    ron.travel(433, 445, rp, r2, SP, 2, lead='L', pose=lambda fr, k, pos, s: dict(sw=R_GUARD, look=head(o2), spine=(8, 8, 0)), lean=8, hipz=0.88, lift=0.10, swing=1.1,
               end_stance=R_ST_R, ease='out')
    op, rp = o2, r2
    T['exchange'] = []
    # hit 1 (450): Oni's diagonal cut from his right shoulder; Ronin parries with the right blade
    k1 = Vector((m.x - 0.18, m.y + 0.10, 1.42))
    oni.key(447, op, N, sw={OK: O_KESA_UP}, look=head(rp), spine=(-24, 2, 0), hips=dict(z=0.88, yaw=-8))
    oni.key(450, op, N, sw={OK: ('thru', k1, (0.45, 0.62, 0.64), (0.5, 0.3, -0.8), 0.52)}, look=head(rp), spine=(18, 12, 0), hips=dict(z=0.82, yaw=14, pitch=8))
    ron.key(447, rp, SP, sw=R_GUARD, look=head(op), spine=(8, 4, 0), hips=dict(z=0.86, yaw=-10, pitch=5))
    ron.key(450, rp, SP, sw={RR: ('thru', k1, (0.25, -0.30, 0.92), (-0.6, -0.8, 0), 0.40), RL: loc((0.40, 0.10, 1.10), (0.45, 0.60, 0.66), (0, 0.5, -0.85))}, look=head(op),
            spine=(16, 4, 0), hips=dict(z=0.84, yaw=-4, pitch=3))
    oni.key(452, op, N, sw={OK: ('thru', k1, (0.45, 0.62, 0.64), (0.5, 0.3, -0.8), 0.52)}, look=head(rp), spine=(18, 12, 0), hips=dict(z=0.82, yaw=14, pitch=8))
    ron.key(452, rp, SP, sw={RR: ('thru', k1, (0.25, -0.30, 0.92), (-0.6, -0.8, 0), 0.40), RL: loc((0.40, 0.10, 1.10), (0.45, 0.60, 0.66), (0, 0.5, -0.85))}, look=head(op),
            spine=(16, 4, 0), hips=dict(z=0.84, yaw=-4, pitch=3))
    T['exchange'].append((450, k1.copy()))
    # hit 2 (466): Ronin's left blade whips in low at the flank; the Oni drops his point and stops it
    k2 = Vector((m.x - 0.42, m.y - 0.22, 1.02))
    ron.key(460, rp, SP, sw={RR: loc((-0.35, 0.35, 1.30), (0.2, 0.7, 0.68), (0, 0.6, -0.8)), RL: loc((0.62, -0.10, 1.25), (0.75, -0.55, 0.36), (0.6, 0.8, 0))}, look=head(op),
            spine=(26, 4, 0), hips=dict(z=0.84, yaw=14, pitch=4))
    ron.key(466, rp + Vector((0, -0.12)), SP, sw={RR: loc((-0.40, 0.25, 1.25), (-0.3, 0.6, 0.74), (0, 0.6, -0.8)), RL: ('thru', k2, (-0.50, -0.85, -0.15), (-0.85, 0.5, 0), 0.50)}, look=head(op),
            spine=(-22, 10, 0), hips=dict(z=0.80, yaw=-16, pitch=8))
    oni.key(460, op, N, sw={OK: loc((0.05, 0.40, 1.25), (0.15, 0.80, 0.58), (0, 0.5, -0.85))}, look=head(rp), spine=(4, 6, 0), hips=dict(z=0.84, yaw=10, pitch=5))
    oni.key(466, op, N, sw={OK: ('thru', k2, (0.20, 0.25, -0.95), (-0.9, 0.3, -0.1), 0.42)}, look=head(rp), spine=(-18, 10, -6), hips=dict(z=0.80, yaw=-6, pitch=8))
    oni.key(468, op, N, sw={OK: ('thru', k2, (0.20, 0.25, -0.95), (-0.9, 0.3, -0.1), 0.42)}, look=head(rp), spine=(-18, 10, -6), hips=dict(z=0.80, yaw=-6, pitch=8))
    ron.key(468, rp + Vector((0, -0.12)), SP, sw={RR: loc((-0.40, 0.25, 1.25), (-0.3, 0.6, 0.74), (0, 0.6, -0.8)), RL: ('thru', k2, (-0.50, -0.85, -0.15), (-0.85, 0.5, 0), 0.50)}, look=head(op),
            spine=(-22, 10, 0), hips=dict(z=0.80, yaw=-16, pitch=8))
    T['exchange'].append((466, k2.copy()))
    # hit 3 (482): both swing flat and meet edge to edge at head height
    k3 = Vector((m.x + 0.05, m.y, 1.58))
    oni.key(476, op, N, sw={OK: loc((-0.40, 0.00, 1.45), (-0.70, -0.50, 0.50), (0.6, -0.7, 0.3))}, look=head(rp), spine=(-30, 2, 0), hips=dict(z=0.86, yaw=-14))
    oni.key(482, op, N, sw={OK: ('thru', k3, (0.62, 0.72, 0.30), (0.75, -0.65, 0), 0.50)}, look=head(rp), spine=(24, 10, 0), hips=dict(z=0.82, yaw=16, pitch=8))
    ron.key(476, rp, SP, sw={RR: loc((-0.55, -0.05, 1.45), (-0.80, -0.35, 0.48), (0.5, -0.8, 0.2)), RL: loc((0.35, 0.30, 1.20), (0.2, 0.75, 0.62), (0, 0.6, -0.8))}, look=head(op),
            spine=(-28, 2, 0), hips=dict(z=0.86, yaw=-16))
    ron.key(482, rp, SP, sw={RR: ('thru', k3, (0.62, -0.72, 0.30), (0.75, 0.65, 0), 0.48), RL: loc((0.45, 0.05, 1.15), (0.55, 0.35, 0.76), (0, 0.6, -0.8))}, look=head(op),
            spine=(22, 8, 0), hips=dict(z=0.82, yaw=12, pitch=6))
    T['exchange'].append((482, k3.copy()))
    # lock for a beat, then both spring back (496-504)
    oni.key(494, op, N, sw={OK: ('thru', k3, (0.62, 0.72, 0.30), (0.75, -0.65, 0), 0.50)}, look=head(rp), spine=(24, 12, 0), hips=dict(z=0.80, yaw=16, pitch=10))
    ron.key(494, rp, SP, sw={RR: ('thru', k3, (0.62, -0.72, 0.30), (0.75, 0.65, 0), 0.48), RL: loc((0.45, 0.05, 1.15), (0.55, 0.35, 0.76), (0, 0.6, -0.8))}, look=head(op),
            spine=(22, 10, 0), hips=dict(z=0.80, yaw=12, pitch=8))
    o3, r3 = op + Vector((0, -1.25)), rp + Vector((0, 1.25))
    feet(oni, 496, 503, o3, N, O_ST, lift=0.16)
    feet(ron, 496, 503, r3, SP, R_ST_R, lift=0.16)
    oni.key(499, (op + o3) / 2, N, sw={OK: O_GUARD}, look=head(r3), spine=(-6, 0, 0), hips=dict(z=1.00, pitch=-4))
    ron.key(499, (rp + r3) / 2, SP, sw=R_GUARD, look=head(o3), spine=(6, 0, 0), hips=dict(z=1.00, pitch=-4))
    op, rp = o3, r3
    oni.key(504, op, N, sw={OK: O_GUARD}, look=head(rp), spine=(-10, 8, 0), hips=dict(z=0.78, yaw=16, pitch=8))
    ron.key(504, rp, SP, sw=R_GUARD, look=head(op), spine=(8, 6, 0), hips=dict(z=0.80, yaw=-10, pitch=6))

    # ================================================================ 21-24 s  Oni's power slash (flame trail), the cape is torn
    wind = loc((-0.44, -0.16, 1.46), (-0.72, -0.55, 0.42), (0.6, -0.7, 0.3))
    oni.key(516, op, N, sw={OK: wind}, look=head(rp), spine=(-34, 4, 0), hips=dict(z=0.76, yaw=-22, pitch=4, f=-0.10))
    oni.key(528, op, N, sw={OK: loc((-0.48, -0.20, 1.48), (-0.70, -0.60, 0.40), (0.6, -0.7, 0.3))}, look=head(rp), spine=(-38, 4, 0), hips=dict(z=0.73, yaw=-24, pitch=4, f=-0.14))
    ron.key(520, rp, SP, sw=R_GUARD, look=head(op), spine=(8, 6, 0), hips=dict(z=0.80, yaw=-10, pitch=6))
    T['power'] = (529, 536)
    o4 = op + Vector((0, 1.05))
    feet(oni, 528, 533, o4, N, {'R': O_ST_W['R']}, lift=0.12)
    feet(oni, 532, 537, o4, N, {'L': O_ST_W['L']}, lift=0.05)
    oni.key(531, op + Vector((0, 0.45)), N, sw={OK: loc((-0.25, 0.46, 1.38), (-0.60, 0.78, 0.15), (0.8, 0.6, 0))}, look=head(rp), spine=(-12, 12, 0), hips=dict(z=0.76, yaw=-6, pitch=10))
    oni.key(533, op + Vector((0, 0.80)), N, sw={OK: loc((0.06, 0.56, 1.32), (0.20, 0.97, 0.06), (0.97, -0.2, 0))}, look=head(rp), spine=(14, 16, 0), hips=dict(z=0.74, yaw=12, pitch=14))
    oni.key(536, o4, N, sw={OK: loc((0.42, 0.28, 1.24), (0.90, 0.42, -0.10), (0.42, -0.90, 0))}, look=head(rp), spine=(38, 16, 0), hips=dict(z=0.72, yaw=26, pitch=14))
    oni.key(542, o4, N, sw={OK: loc((0.46, 0.02, 1.16), (0.80, -0.55, -0.22), (-0.5, -0.85, 0))}, look=head(rp + Vector((0, 2.2))), spine=(46, 16, 0), hips=dict(z=0.72, yaw=30, pitch=14))
    oni.key(576, o4, N, sw={OK: loc((0.44, 0.06, 1.14), (0.78, -0.55, -0.28), (-0.5, -0.85, 0))}, look=head(rp + Vector((0, 2.2))), spine=(40, 14, 0), hips=dict(z=0.76, yaw=26, pitch=12))
    op = o4
    # Ronin throws himself back out of the arc; the point still catches the cape
    r4 = rp + Vector((0, 1.9))
    T['cape_tear'] = (533, Vector((rp.x, rp.y + 0.6, 1.35)))
    ron.plant('L', 529, ron.foot_at('L', 529)[1], ron.foot_at('L', 529)[2])
    ron.plant('R', 529, ron.foot_at('R', 529)[1], ron.foot_at('R', 529)[2])
    Fv, Lv = A.basis(SP)
    ron.plant('L', 534, rp + Vector((0, 1.0)) + Lv.xy * 0.20, SP + 20, lift=0.40, pitch=30)
    ron.plant('R', 534, rp + Vector((0, 0.8)) - Lv.xy * 0.20, SP - 10, lift=0.30, pitch=30)
    back_arms = {RR: loc((-0.60, 0.25, 1.50), (-0.55, 0.45, 0.70), (0, 0.6, -0.8)), RL: loc((0.60, 0.25, 1.50), (0.55, 0.45, 0.70), (0, 0.6, -0.8))}
    ron.key(529, rp, SP, sw=R_GUARD, look=head(op), spine=(0, -4, 0), hips=dict(z=0.72, pitch=-4))
    ron.key(534, rp + Vector((0, 0.95)), SP, sw=back_arms, look=head(op), spine=(0, -22, 0), hips=dict(z=1.12, pitch=-20))
    feet(ron, 534, 540, r4, SP, {'R': (-0.24, -0.36, -40), 'L': (0.20, 0.30, 10)}, lift=0.0, plant=True)
    ron.key(540, r4 + Vector((0, -0.10)), SP, sw=R_GUARD, look=head(op), spine=(6, 16, 0), hips=dict(z=0.66, pitch=14, yaw=-10))
    ron.slide(540, 552, (0, 0.45))
    rp = r4 + Vector((0, 0.45))
    ron.key(552, rp, SP, sw=R_GUARD, look=head(op), spine=(8, 12, 0), hips=dict(z=0.70, pitch=10, yaw=-12))
    ron.key(576, rp, SP, sw=R_GUARD, look=head(op), spine=(8, 5, 0), hips=dict(z=0.86, pitch=5, yaw=-12))

    # ================================================================ 24-27 s  final crossing slash, freeze back to back
    # both settle into the draw-cut crouch (577-600)
    o_low = loc((0.30, 0.10, 0.98), (0.35, -0.80, -0.49), (0, 0.3, 0.95))      # blade back along the left hip, as if re-sheathed
    feet(oni, 580, 588, op, N, {'R': O_ST_W['R']}, lift=0.05)
    feet(oni, 588, 596, op, N, {'L': O_ST_W['L']}, lift=0.05)
    oni.key(600, op, N, sw={OK: o_low}, look=head(rp), spine=(26, 18, 0), hips=dict(z=0.70, yaw=22, pitch=14))
    r_low = {RR: loc((-0.42, -0.10, 0.92), (-0.45, -0.80, -0.40), (0, 0.3, -0.95)), RL: loc((0.42, -0.10, 0.92), (0.45, -0.80, -0.40), (0, 0.3, -0.95))}
    feet(ron, 582, 590, rp, SP, {'L': (0.22, 0.46, 6)}, lift=0.05)
    feet(ron, 590, 598, rp, SP, {'R': (-0.28, -0.50, -55)}, lift=0.05)
    ron.key(600, rp, SP, sw=r_low, look=head(op), spine=(0, 18, 0), hips=dict(z=0.70, pitch=14))
    # they pass on each other's right; the cuts happen as they cross (slow motion 610-630)
    mid = (op + rp) / 2
    gap = (rp - op).length
    o_end, r_end = mid + Vector((-0.55, gap * 0.5 + 0.2)), mid + Vector((0.55, -gap * 0.5 - 0.2))
    T['cross'] = (620, Vector((mid.x, mid.y, 1.25)))
    orun2 = lambda fr, k, pos, side: dict(sw={OK: o_low}, look=(pos.x, pos.y + 6, 1.2), spine=(22, 20, 0), hips=dict(yaw=18))
    oni.travel(601, 613, op, mid + Vector((-0.50, -0.9)), N, 3, lead='L', pose=orun2, lean=18, bob=0.03, hipz=0.80, lift=0.16, swing=1.2, width=0.10, ease='in')
    rrun2 = lambda fr, k, pos, side: dict(sw=r_low, look=(pos.x, pos.y - 6, 1.2), spine=(0, 20, 0))
    ron.travel(601, 613, rp, mid + Vector((0.50, 0.9)), SP, 3, lead='R', pose=rrun2, lean=18, bob=0.03, hipz=0.80, lift=0.16, swing=1.2, width=0.10, ease='in')
    # the cuts: Oni rips the blade out and across, Ronin scissors both blades (620), follow through to the freeze (631)
    feet(oni, 613, 622, mid + Vector((-0.52, 0.0)), N, {'R': (-0.18, 0.45, -6)}, lift=0.10)
    oni.key(620, mid + Vector((-0.52, -0.25)), N, sw={OK: loc((-0.20, 0.55, 1.15), (-0.70, 0.70, 0.12), (-0.7, -0.7, 0))}, look=(o_end.x, o_end.y + 4, 1.0), spine=(-30, 20, 0),
            hips=dict(z=0.72, yaw=-20, pitch=16))
    feet(ron, 613, 622, mid + Vector((0.52, 0.0)), SP, {'L': (0.18, 0.45, 6)}, lift=0.10)
    ron.key(620, mid + Vector((0.52, 0.25)), SP, sw={RR: loc((-0.55, 0.40, 1.10), (-0.85, 0.45, 0.25), (-0.4, -0.9, 0)), RL: loc((0.55, 0.40, 1.10), (0.85, 0.45, 0.25), (0.4, -0.9, 0))},
            look=(r_end.x, r_end.y - 4, 1.0), spine=(0, 22, 0), hips=dict(z=0.72, pitch=18))
    fin_o = {'R': (-0.20, 0.62, -6), 'L': (0.26, -0.70, 60)}
    feet(oni, 621, 631, o_end, N, {'L': fin_o['L']}, lift=0.10)
    feet(oni, 624, 633, o_end, N, {'R': fin_o['R']}, lift=0.08)
    o_fin = loc((-0.55, 0.30, 0.95), (-0.80, 0.45, -0.40), (-0.3, -0.5, -0.8))    # zanshin: blade held out low to his right
    oni.key(633, o_end, N, sw={OK: o_fin}, look=(o_end.x, o_end.y + 5, 0.9), spine=(-36, 22, 0), hips=dict(z=0.62, yaw=-18, pitch=18))
    fin_r = {'L': (0.22, 0.60, 6), 'R': (-0.26, -0.70, -60)}
    feet(ron, 621, 631, r_end, SP, {'R': fin_r['R']}, lift=0.10)
    feet(ron, 624, 633, r_end, SP, {'L': fin_r['L']}, lift=0.08)
    r_fin = {RR: loc((-0.70, 0.05, 1.05), (-0.92, -0.10, -0.38), (0, -0.3, -0.95)), RL: loc((0.70, 0.05, 1.05), (0.92, -0.10, -0.38), (0, -0.3, -0.95))}
    ron.key(633, r_end, SP, sw=r_fin, look=(r_end.x, r_end.y - 5, 0.9), spine=(0, 24, 0), hips=dict(z=0.60, pitch=20))
    T['freeze'] = (633, o_end.copy(), r_end.copy())
    # ================================================================ 27-30 s  held poses (hat splits, mask cracks, fade)
    for f in (648, 720):
        oni.key(f, o_end, N, sw={OK: o_fin}, look=(o_end.x, o_end.y + 5, 0.9), spine=(-36, 22, 0), hips=dict(z=0.62, yaw=-18, pitch=18))
        ron.key(f, r_end, SP, sw=r_fin, look=(r_end.x, r_end.y - 5, 0.9), spine=(0, 24, 0), hips=dict(z=0.60, pitch=20))
    return T
