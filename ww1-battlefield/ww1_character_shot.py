#!/usr/bin/env python3
"""
Shot 2: a character walks out of no-man's-land toward the trench.

    python3 ww1_character_shot.py --char /path/to/character.glb --still 1 60 120
    python3 ww1_character_shot.py --char /path/to/character.glb

The battlefield is rebuilt from ww1_scene.py. The character file is a STATIC
mesh (no rig, no animation), so this script does the whole job itself:

  * decimates the mesh once and caches it (out/char_cache.blend)
  * assigns skin weights from the mesh's own proportions (procedural rig)
  * drives a walk cycle with two-bone leg IK so the feet stay planted on the
    terrain (no sliding), plus pelvis/spine/arm motion
  * deforms the mesh per frame with linear-blend skinning (numpy)

The joint positions below were measured for this particular model (a figure
standing in a relaxed A-pose, facing -Y, a weapon in the hand on the -X side).
Resumable like shot 1: finished frames are skipped.
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ww1_scene as W  # noqa: E402

OUT_DIR = W.OUT_DIR
FRAME_DIR = os.path.join(OUT_DIR, "frames_walk")
CACHE = os.path.join(OUT_DIR, "char_cache.blend")
BLEND_PATH = os.path.join(OUT_DIR, "ww1_character_shot.blend")
FPS, N_FRAMES = W.FPS, W.N_FRAMES

# ----------------------------------------------------------------------------
# character measurements (model units; the mesh is ~0.98 tall)
# ----------------------------------------------------------------------------
CX, CY = 0.046, 0.065                 # body midline
SCALE = 2.0 / 0.98                    # -> a 2.0 m tall brute
J = {                                 # joint pivots
    'hips': (CX, 0.065, 0.52), 'spine': (CX, 0.065, 0.58), 'chest': (CX, 0.07, 0.70),
    'neck': (CX, 0.06, 0.875),
    'shoulderN': (-0.115, 0.075, 0.83), 'elbowN': (-0.160, 0.085, 0.635),
    'shoulderP': (0.210, 0.075, 0.83), 'elbowP': (0.250, 0.080, 0.635),
    'hipN': (-0.045, 0.070, 0.50), 'kneeN': (-0.075, 0.065, 0.27), 'ankleN': (-0.088, 0.070, 0.07),
    'hipP': (0.135, 0.070, 0.50), 'kneeP': (0.165, 0.060, 0.27), 'ankleP': (0.180, 0.060, 0.07),
}
BONES = ['hips', 'spine', 'chest', 'head', 'uaN', 'faN', 'uaP', 'faP',
         'thN', 'shN', 'ftN', 'thP', 'shP', 'ftP']
BI = {b: i for i, b in enumerate(BONES)}

# gait (model units / seconds)
CYCLE_T = 1.16                        # one full cycle (two steps): heavy, unhurried
CYCLE_LEN = 0.50                      # distance per cycle
STANCE = 0.62                         # duty factor
SPEED = CYCLE_LEN / CYCLE_T           # model units per second
HIP_DROP = 0.040
BALL = (0.125, -0.055)                # ball of the foot relative to the ankle (forward, up)

PATH_START = Vector((1.15, 12.75))    # world metres
PATH_DIR = Vector((-0.12, -1.0)).normalized()


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def fs(a, b, x):                      # scalar smoothstep
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------
# skin weights from proportions
# ----------------------------------------------------------------------------
def compute_weights(co):
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    n = len(co)
    w = np.zeros((n, len(BONES)))

    # torso chain, partition of unity along height
    t_spine = sstep(0.52, 0.60, z)
    t_chest = sstep(0.64, 0.72, z)
    t_head = sstep(0.855, 0.895, z) * (np.abs(x - CX) < 0.085)
    w[:, BI['hips']] = 1 - t_spine
    w[:, BI['spine']] = t_spine * (1 - t_chest)
    w[:, BI['chest']] = t_chest * (1 - t_head)
    w[:, BI['head']] = t_chest * t_head

    # legs take over from the hips going down; the hanging cloth blends across the midline
    leg = sstep(0.54, 0.42, z)
    shin = sstep(0.30, 0.24, z)
    foot = np.maximum(sstep(0.085, 0.050, z), sstep(0.02, -0.03, y) * (z < 0.105))
    sideN = np.where(z > 0.30, sstep(CX + 0.035, CX - 0.035, x), (x < CX).astype(float))
    hips_keep = w[:, BI['hips']] * (1 - leg)
    legw = w[:, BI['hips']] * leg
    w[:, BI['hips']] = hips_keep
    for s, f in (('N', sideN), ('P', 1 - sideN)):
        w[:, BI['th' + s]] = legw * f * (1 - shin)
        w[:, BI['sh' + s]] = legw * f * shin * (1 - foot)
        w[:, BI['ft' + s]] = legw * f * shin * foot

    # arms: hard geometric gates where the arm hangs free of the body
    armN = ((z < 0.70) & (z >= 0.50) & (x < -0.088)) | ((z < 0.50) & (z >= 0.455) & (x < -0.113)) \
        | ((z < 0.455) & (z > 0.20) & (x < -0.125)) | ((z < 0.455) & (z > 0.20) & (y < -0.045) & (x < -0.10))
    armP = ((z < 0.70) & (z >= 0.64) & (x > 0.158)) | ((z < 0.64) & (z >= 0.56) & (x > 0.18)) \
        | ((z < 0.56) & (z > 0.36) & (x > 0.205))
    fore = sstep(0.67, 0.60, z)
    for s, gate in (('N', armN), ('P', armP)):
        w[gate] = 0.0
        w[gate, BI['ua' + s]] = (1 - fore)[gate]
        w[gate, BI['fa' + s]] = fore[gate]
    # shoulders: soft blend chest -> upper arm
    dx = np.abs(x - CX)
    up = sstep(0.125, 0.185, dx) * sstep(0.93, 0.86, z) * (z >= 0.70)
    cont = ((x < -0.088) | (x > 0.158)) * sstep(0.76, 0.70, z) * (z >= 0.70)
    up = np.maximum(up, cont)
    for s, side in (('N', x < CX), ('P', x >= CX)):
        m = side & (z >= 0.70)
        k = up * m
        w *= (1 - k)[:, None]
        w[:, BI['ua' + s]] += k
    w /= w.sum(axis=1, keepdims=True)
    return w


# ----------------------------------------------------------------------------
# kinematics
# ----------------------------------------------------------------------------
def T(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def R(axis, a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    if axis == 'x':
        m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    elif axis == 'y':
        m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    else:
        m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def about(p, *rots):
    m = T(p)
    for r in rots:
        m = m @ r
    return m @ T([-c for c in p])


def leg_dims(s):
    h, k, a = (np.array(J[n + s]) for n in ('hip', 'knee', 'ankle'))
    fu = lambda p: np.array((-p[1], p[2]))          # sagittal plane: forward = -Y, up = Z
    l1, l2 = np.linalg.norm(fu(k) - fu(h)), np.linalg.norm(fu(a) - fu(k))
    th1 = math.atan2(fu(k)[0] - fu(h)[0], -(fu(k)[1] - fu(h)[1]))
    th2 = math.atan2(fu(a)[0] - fu(k)[0], -(fu(a)[1] - fu(k)[1]))
    return l1, l2, th1, th2


def rot2(v, d):
    """Rotate a (forward, up) vector by d, angle measured from 'down' toward 'forward'."""
    return np.array((v[0] * math.cos(d) - v[1] * math.sin(d), v[0] * math.sin(d) + v[1] * math.cos(d)))


def foot_track(phase):
    """Ankle position relative to the hip joint's ground point (forward, up above ground) and
    absolute foot pitch delta, for one leg at gait phase 0..1 (0 = heel strike)."""
    S = STANCE * CYCLE_LEN
    ball = np.array(BALL)
    ankle_h = 0.07

    def stance(ph):
        f = S / 2 - S * ph / STANCE
        p = math.radians(34) * fs(0.40, STANCE, ph) ** 1.4                 # heel lift before toe-off
        strike = math.radians(11) * (1 - fs(0.0, 0.09, ph))                # toes up at heel strike
        flat = np.array((f, ankle_h))
        a = flat + ball - rot2(ball, -p)
        return a, -p + strike

    if phase < STANCE:
        return stance(phase)
    s = (phase - STANCE) / (1 - STANCE)
    a0, d0 = stance(STANCE - 1e-6)
    a1, d1 = stance(0.0)
    e = s * s * (3 - 2 * s)
    a = a0 + (a1 - a0) * (0.25 * s + 0.75 * e)
    a[1] += 0.062 * math.sin(math.pi * s ** 0.75)                          # foot clearance
    d = d0 + (d1 - d0) * fs(0.15, 0.95, s)
    return a, d


def pose(t, ground):
    """Bone matrices (model space) at time t. `ground(dist, lateral)` -> terrain height in
    model units relative to the terrain under the root."""
    ph = (t / CYCLE_T) % 1.0                     # phase of leg N; leg P is half a cycle later
    c1 = math.cos(2 * math.pi * ph)
    mats = {}

    bob = 0.011 * math.cos(4 * math.pi * (ph - 0.3))
    sway = -0.013 * math.cos(2 * math.pi * (ph - 0.3))
    yaw = math.radians(4.0) * c1
    roll = math.radians(2.2) * math.cos(2 * math.pi * (ph - 0.3))
    hips = T((sway, 0.0, -HIP_DROP + bob)) @ about(J['hips'], R('z', yaw), R('y', roll), R('x', math.radians(2.0)))
    mats['hips'] = hips
    mats['spine'] = hips @ about(J['spine'], R('x', math.radians(3.5 + 1.0 * math.cos(4 * math.pi * ph))),
                                 R('z', -yaw * 1.3), R('y', -roll * 1.2))
    mats['chest'] = mats['spine'] @ about(J['chest'], R('x', math.radians(3.0)), R('z', -yaw * 1.6))
    mats['head'] = mats['chest'] @ about(J['neck'], R('x', math.radians(-4.0)), R('z', yaw * 1.4),
                                         R('y', roll * 0.8))

    # arms: free arm (P) swings against leg P; the weapon arm (N) barely moves, it is carrying weight
    swP = math.radians(19) * c1
    mats['uaP'] = mats['chest'] @ about(J['shoulderP'], R('x', -swP), R('y', math.radians(-3)))
    mats['faP'] = mats['uaP'] @ about(J['elbowP'], R('x', -math.radians(15 + 11 * math.cos(2 * math.pi * (ph - 0.07)))))
    swN = math.radians(6.5) * math.cos(2 * math.pi * (ph - 0.5 - 0.06))
    mats['uaN'] = mats['chest'] @ about(J['shoulderN'], R('x', -swN), R('y', math.radians(5)))
    mats['faN'] = mats['uaN'] @ about(J['elbowN'], R('x', -math.radians(7 + 4 * math.cos(2 * math.pi * (ph - 0.62)))))

    # legs: two-bone IK in the sagittal plane, feet locked to the terrain during stance
    dist = SPEED * t
    for s, php in (('N', ph), ('P', (ph + 0.5) % 1.0)):
        l1, l2, r1, r2 = leg_dims(s)
        a, dfoot = foot_track(php)
        lat = J['ankle' + s][0] - CX
        # terrain under this foot: fixed at the plant point during stance, blended in swing
        mid_prev = dist - (php - 0.3) * CYCLE_LEN
        if php < STANCE:
            g = ground(mid_prev, lat)
        else:
            sw = (php - STANCE) / (1 - STANCE)
            g = ground(mid_prev, lat) + (ground(mid_prev + CYCLE_LEN, lat) - ground(mid_prev, lat)) * fs(0, 1, sw)
        hip = np.array(J['hip' + s])
        hip_now = (hips @ np.append(hip, 1.0))[:3]
        tgt = np.array((a[0] - (-(hip_now[1] - hip[1])), a[1] + g - hip_now[2]))   # ankle rel. hip joint
        d = min(np.linalg.norm(tgt), (l1 + l2) * 0.998)
        d = max(d, abs(l1 - l2) + 1e-3)
        base = math.atan2(tgt[0], -tgt[1])
        th1 = base + math.acos(np.clip((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1))
        knee_in = math.acos(np.clip((l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2), -1, 1))
        th2 = th1 - (math.pi - knee_in)
        # the hips matrix already carries pelvis yaw/roll; counter the small pelvis pitch
        mats['th' + s] = hips @ about(J['hip' + s], R('x', -(th1 - r1) - math.radians(2.0)))
        mats['sh' + s] = mats['th' + s] @ about(J['knee' + s], R('x', -((th2 - r2) - (th1 - r1))))
        mats['ft' + s] = mats['sh' + s] @ about(J['ankle' + s], R('x', -(dfoot - (th2 - r2))),
                                                R('z', -yaw))
    return np.stack([mats[b] for b in BONES])


# ----------------------------------------------------------------------------
# character loading
# ----------------------------------------------------------------------------
def make_cache(glb, faces=90000):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    ob = [o for o in bpy.data.objects if o.type == 'MESH'][0]
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(ob.data.polygons) > faces:
        m = ob.modifiers.new('dec', 'DECIMATE')
        m.ratio = faces / len(ob.data.polygons)
        bpy.ops.object.modifier_apply(modifier='dec')
    me = ob.data
    for name in ('custom_normal', 'sharp_face', 'sharp_edge'):
        if name in me.attributes:
            me.attributes.remove(me.attributes[name])
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    ob.name = "Character"
    bpy.ops.file.pack_all()
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=CACHE)
    print(f"[walk] cached character: {len(me.polygons)} faces", flush=True)


def load_character():
    with bpy.data.libraries.load(CACHE) as (src, dst):
        dst.objects = [n for n in src.objects if n == "Character"]
    ob = dst.objects[0]
    bpy.context.scene.collection.objects.link(ob)
    # the model's own material is glossier than anything standing in a dust storm
    for mat in ob.data.materials:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                for name in ('Coat Weight', 'Sheen Weight'):
                    if name in node.inputs:
                        node.inputs[name].default_value = 0.0
    return ob


class Walker:
    def __init__(self, ob):
        self.ob = ob
        n = len(ob.data.vertices)
        co = np.empty(n * 3)
        ob.data.vertices.foreach_get('co', co)
        self.rest = np.c_[co.reshape(-1, 3), np.ones(n)]
        self.w = compute_weights(self.rest[:, :3])
        self.yaw = math.atan2(PATH_DIR.x, -PATH_DIR.y)        # model faces -Y

    def root_xy(self, dist_model, lateral_model=0.0):
        p = PATH_START + PATH_DIR * (dist_model * SCALE)
        side = Vector((-PATH_DIR.y, PATH_DIR.x)) * (lateral_model * SCALE)   # model +X = walker's left
        return p + side

    def ground_under_root(self, dist_model):
        vals = [W.ground_z(*self.root_xy(dist_model + o)) for o in (-0.25, -0.12, 0.0, 0.12, 0.25)]
        return sum(vals) / len(vals)

    def set_frame(self, frame):
        t = (frame - 1) / FPS
        dist = SPEED * t
        g_root = self.ground_under_root(dist)

        def ground(d, lat):
            return (W.ground_z(*self.root_xy(d, lat)) - g_root) / SCALE

        mats = pose(t, ground)
        out = np.zeros((len(self.rest), 3))
        for b in range(len(BONES)):
            out += self.w[:, b:b + 1] * (self.rest @ mats[b].T)[:, :3]
        self.ob.data.vertices.foreach_set('co', out.ravel())
        self.ob.data.update()
        p = self.root_xy(dist)
        world = T((p.x, p.y, g_root - 0.035)) @ R('z', self.yaw) @ np.diag((SCALE, SCALE, SCALE, 1.0)) \
            @ T((-CX, -CY, 0.0))
        self.ob.matrix_world = Matrix(world.tolist())
        return Vector((p.x, p.y, g_root))


# ----------------------------------------------------------------------------
# camera for this shot: 50 mm from the trench, tracking the walker
# ----------------------------------------------------------------------------
def setup_camera(walker):
    sc = bpy.context.scene
    old = sc.camera
    cam = bpy.data.cameras.new("CamWalk")
    cam.lens, cam.sensor_width = 50.0, 36.0
    cam.clip_start, cam.clip_end = 0.05, 4000
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = 4.0
    ob = W.link(bpy.data.objects.new("CamWalk", cam))
    sc.camera = ob
    if old:
        bpy.data.objects.remove(old)
    return ob


def camera_frame(cam, frame, walker_pos):
    t = (frame - 1) / (N_FRAMES - 1)
    tt = frame / FPS
    pos = Vector((-2.65 + 0.30 * t, 0.35, 1.10))
    pos.x += 0.004 * math.sin(tt * 5.3 + 0.4)
    pos.y += 0.003 * math.sin(tt * 4.1 + 1.7)
    pos.z += 0.005 * math.sin(tt * 6.7 + 0.9) + 0.004 * math.sin(tt * 2.3)
    # aim a little to the walker's screen-left so he sits on the right third, walking into frame
    to = Vector((walker_pos.x, walker_pos.y)) - Vector((pos.x, pos.y))
    bearing = math.atan2(to.x, to.y) - math.radians(6.0 - 1.5 * t)
    pitch = math.radians(-0.6 - 0.5 * t)
    d = Vector((math.sin(bearing) * math.cos(pitch), math.cos(bearing) * math.cos(pitch), math.sin(pitch)))
    rot = d.to_track_quat('-Z', 'Y').to_euler()
    rot.x += math.radians(0.09 * math.sin(tt * 7.1 + 0.3) + 0.05 * math.sin(tt * 13.0 + 1.1))
    rot.y += math.radians(0.06 * math.sin(tt * 3.7 + 2.0))
    rot.z += math.radians(0.10 * math.sin(tt * 5.9 + 1.3) + 0.04 * math.sin(tt * 11.3))
    cam.location, cam.rotation_euler = pos, rot
    cam.data.dof.focus_distance = to.length
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)
    cam.data.dof.keyframe_insert("focus_distance", frame=frame)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default=os.path.join(HERE, "assets", "character.glb"))
    ap.add_argument("--still", type=int, nargs='*')
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    os.makedirs(FRAME_DIR, exist_ok=True)
    if not os.path.exists(CACHE):
        make_cache(args.char)
    W.build_scene(args.samples)
    ob = load_character()
    walker = Walker(ob)
    cam = setup_camera(walker)
    sc = bpy.context.scene

    def prepare(frame):
        sc.frame_set(frame)
        p = walker.set_frame(frame)
        camera_frame(cam, frame, p)
        bpy.context.view_layer.update()

    for f in range(1, N_FRAMES + 1):            # bake the camera keys so the .blend is animated
        camera_frame(cam, f, walker.set_frame(f))
    prepare(1)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    if args.no_render:
        return

    def render(frame, path):
        prepare(frame)
        tmp = path[:-4] + ".part.png"
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, path)

    if args.still is not None:
        os.makedirs(os.path.join(OUT_DIR, "test"), exist_ok=True)
        for f in (args.still or [60]):
            t0 = time.time()
            p = os.path.join(OUT_DIR, "test", f"walk_{f:04d}.png")
            render(f, p)
            print(f"[walk] still {f} -> {p} ({time.time() - t0:.1f}s)", flush=True)
        return

    for f in range(1, N_FRAMES + 1):
        p = os.path.join(FRAME_DIR, f"frame_{f:04d}.png")
        if os.path.exists(p):
            continue
        t0 = time.time()
        render(f, p)
        print(f"[walk] frame {f}/{N_FRAMES} ({time.time() - t0:.1f}s)", flush=True)
    print("[walk] render complete", flush=True)


if __name__ == "__main__":
    main()
