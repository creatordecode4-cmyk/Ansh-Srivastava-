"""Camera plan: one camera per shot, baked every frame and bound to timeline markers so Blender cuts automatically."""
import bpy, math
from mathutils import Vector as V
from anim import fwd, left

LINE = 3.5


def bp(st, v):
    h = st['P']['hips']
    return V((h.x, h.y, 0)) + left(st['yaw']) * v[0] + fwd(st['yaw']) * v[1] + V((0, 0, v[2]))


def lerp(a, b, u):
    u = max(0.0, min(1.0, u)); u = u * u * (3 - 2 * u)
    return V(a).lerp(V(b), u)


def shot_list(SO, SR):
    """SO / SR: per-frame solved states of the Oni and the Ronin. Each shot: (name, f0, f1, lens, pos(f), target(f), handheld, fstop)."""
    head = lambda S: (lambda f: S[f]['P']['head'] + V((0, 0, 0.10)))
    chest = lambda S: (lambda f: S[f]['P']['chest'] + V((0, 0, 0.15)))
    mid = lambda f: (SO[f]['P']['hips'] + SR[f]['P']['hips']) / 2
    u = lambda f, a, b: (f - a) / max(1, b - a)
    def orbit(f):
        th = math.radians(-50 + 180 * u(f, 319, 384))
        c = mid(f)
        return V((c.x + 4.3 * math.sin(th), c.y - 4.3 * math.cos(th), 1.5 - 0.4 * u(f, 319, 384)))
    S = [
        ('S01_drone', 1, 72, 24, lambda f: lerp((0, -27, 13), (0, -12.5, 5.0), u(f, 1, 72)), lambda f: lerp((0, 7, 3.5), (0, 8, 4.5), u(f, 1, 72)), 0, 8),
        ('S02_oni_low', 73, 100, 30, lambda f: V((-4.2, 2.4, 0.35)), chest(SO), 0, 4),
        ('S03_oni_side', 101, 136, 35, lambda f: V((SO[f]['P']['hips'].x + 0.5, SO[f]['P']['hips'].y - 3.4, 1.15)),
         lambda f: V((SO[f]['P']['hips'].x + 0.3, SO[f]['P']['hips'].y, 1.2)), 0.003, 4),
        ('S04_oni_mask', 137, 152, 75, lambda f: SO[f]['P']['head'] + fwd(SO[f]['yaw']) * 1.35 + left(SO[f]['yaw']) * 0.45 + V((0, 0, -0.30)),
         lambda f: SO[f]['P']['head'] + V((0, 0, 0.08)), 0.002, 2.8),
        ('S05_oni_hilt', 153, 164, 75, lambda f: bp(SO[f], (0.95, 1.05, 1.32)), lambda f: bp(SO[f], (0.20, 0.36, 1.30)), 0.002, 2.8),
        ('S06_ronin_torii', 165, 186, 85, lambda f: lerp((1.9, 1.2, 0.75), (1.95, 1.8, 0.8), u(f, 165, 186)), chest(SR), 0, 2.8),
        ('S07_ronin_side', 187, 216, 35, lambda f: V((SR[f]['P']['hips'].x - 3.6, SR[f]['P']['hips'].y - 0.5, 1.15)),
         lambda f: V((SR[f]['P']['hips'].x, SR[f]['P']['hips'].y - 0.3, 1.2)), 0.003, 4),
        ('S08_ronin_hat', 217, 240, 85, lambda f: SR[f]['P']['head'] + fwd(SR[f]['yaw']) * 1.35 - left(SR[f]['yaw']) * 0.35 + V((0, 0, -0.22)),
         lambda f: SR[f]['P']['head'] + V((0, 0, 0.16)), 0.002, 2.8),
        ('S09_standoff', 241, 277, 26, lambda f: lerp((0, -3.6, 0.8), (0, -2.9, 0.85), u(f, 241, 277)), lambda f: V((-0.1, LINE, 1.55)), 0, 5.6),
        ('S10_dash', 278, 299, 22, lambda f: V((0, -1.6, 0.45)), lambda f: V((0, LINE, 1.15)), 0.004, 5.6),
        ('S11_clash_slow', 300, 318, 55, lambda f: lerp((0.9, 1.25, 1.38), (0.35, 1.25, 1.34), u(f, 300, 318)), lambda f: V((0.0, LINE, 1.36)), 0, 2.8),
        ('S12_orbit', 319, 384, 32, orbit, lambda f: mid(f) + V((0, 0, 1.45)), 0.003, 4),
        ('S13_spin', 385, 410, 28, lambda f: V((1.4, 0.9, 0.55)), lambda f: mid(f) + V((0, 0, 1.3)), 0.003, 4),
        ('S14_kick', 411, 424, 40, lambda f: V((1.5, 1.2, 1.25)), lambda f: V((1.5, LINE, 1.2)), 0.006, 4),
        ('S15_slide', 425, 456, 26, lambda f: V((-4.6, 2.9, 0.35)), chest(SO), 0.003, 4),
        ('S16a_over_ronin', 457, 470, 40, lambda f: bp(SR[f], (-0.55, -0.95, 1.78)), head(SO), 0.014, 4),
        ('S16b_over_oni', 471, 483, 40, lambda f: bp(SO[f], (0.60, -0.95, 1.88)), head(SR), 0.014, 4),
        ('S16c_side_close', 484, 499, 35, lambda f: V((mid(f).x, 1.3, 1.0)), lambda f: V((mid(f).x, LINE, 1.5)), 0.016, 4),
        ('S16d_high', 500, 528, 30, lambda f: V((-0.2, -0.6, 4.2)), lambda f: V((-0.2, LINE, 1.0)), 0.006, 5.6),
        ('S17_oni_windup', 529, 548, 35, lambda f: lerp(bp(SO[529], (-0.9, 2.6, 0.55)), bp(SO[529], (-0.75, 2.2, 0.6)), u(f, 529, 548)), chest(SO), 0.002, 4),
        ('S18_slash_wide', 549, 575, 26, lambda f: V((1.0, -1.8, 0.7)), lambda f: V((1.2, LINE, 1.2)), 0.004, 5.6),
        ('S19_two_shot', 576, 612, 50, lambda f: lerp((1.5, -6.5, 1.0), (1.5, -5.2, 1.0), u(f, 576, 612)), lambda f: V((1.5, LINE, 1.25)), 0, 4),
        ('S20_crossing', 613, 654, 30, lambda f: lerp((1.45, -1.3, 0.75), (1.45, -1.0, 0.8), u(f, 613, 654)), lambda f: V((1.45, LINE, 1.2)), 0.002, 4),
        ('S21_back_to_back', 655, 684, 35, lambda f: lerp((1.45, -3.4, 0.6), (1.45, -2.9, 0.6), u(f, 655, 684)), lambda f: V((1.45, LINE, 1.35)), 0, 5.6),
        ('S22_ronin_close', 685, 702, 85, lambda f: SR[f]['P']['head'] + fwd(SR[f]['yaw']) * 1.5 + left(SR[f]['yaw']) * 0.4 + V((0, 0, -0.2)),
         lambda f: SR[f]['P']['head'] + V((0, 0, 0.14)), 0, 2.8),
        ('S23_oni_close', 703, 720, 85, lambda f: SO[f]['P']['head'] + fwd(SO[f]['yaw']) * 1.45 - left(SO[f]['yaw']) * 0.45 + V((0, 0, -0.38)),
         lambda f: SO[f]['P']['head'] + V((0, 0, 0.06)), 0, 2.8),
    ]
    return S


def build_cameras(SO, SR, EV, C):
    sc = bpy.context.scene
    for m in list(sc.timeline_markers):
        sc.timeline_markers.remove(m)
    def jitter(f, k):
        return math.sin(f * 1.7 + k * 2.1) * 0.6 + math.sin(f * 0.83 + k * 5.3) * 0.4
    for name, f0, f1, lens, pos, tgt, hand, fstop in shot_list(SO, SR):
        cd = bpy.data.cameras.new('CAM_' + name)
        cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = lens, 36, 0.05, 2000
        cd.dof.use_dof, cd.dof.aperture_fstop = True, fstop
        cam = bpy.data.objects.new('CAM_' + name, cd)
        cam.rotation_mode = 'QUATERNION'
        C.objects.link(cam)
        prev = None
        for f in range(f0, f1 + 1):
            amp = hand + sum(0.045 * s * math.exp(-(f - fe) / 3.5) for fe, _, s, _ in EV if f0 <= fe <= f)
            p = pos(f) + V((jitter(f, 1), jitter(f, 2), jitter(f, 3))) * amp
            t = tgt(f) + V((jitter(f, 4), jitter(f, 5), jitter(f, 6))) * amp * 2.0
            q = (t - p).to_track_quat('-Z', 'Y')
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q.copy()
            cam.location, cam.rotation_quaternion = p, q
            cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_quaternion', frame=f)
            cd.dof.focus_distance = (t - p).length
            cd.dof.keyframe_insert('focus_distance', frame=f)
        mk = sc.timeline_markers.new(name, frame=f0)
        mk.camera = cam
    sc.camera = bpy.data.objects['CAM_S01_drone']
