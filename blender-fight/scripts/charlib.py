"""Character-building helpers: skeleton, swept tubes, lofts, bone parenting, katana."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
import lib
from lib import MB, TRS

R = math.radians


# ---------------------------------------------------------------- geometry
def _frames(pts, up=None, closed=False):
    n = len(pts)
    tang = []
    for i in range(n):
        a = pts[(i - 1) % n] if closed else pts[max(i - 1, 0)]
        b = pts[(i + 1) % n] if closed else pts[min(i + 1, n - 1)]
        tang.append((b - a).normalized())
    ref = Vector(up) if up else (Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0)))
    nrm = (ref - tang[0] * ref.dot(tang[0])).normalized()
    out = []
    for t in tang:
        nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm.copy(), t.cross(nrm)))
    return out


def tube(mb, pts, radii, segs=10, mat=0, cap=True, up=None, closed=False, tcol=None, smooth=True):
    """Sweep a circle / ellipse along a polyline. radii: number, list of numbers or list of (rx, ry).
    tcol: (bmesh colour layer, strand value) -> stores length fraction in R and the value in G."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    fr = _frames(pts, up, closed)
    rings = []
    for i, (t, nr, bi) in enumerate(fr):
        r = radii if isinstance(radii, (int, float)) else radii[i]
        rx, ry = r if isinstance(r, (tuple, list)) else (r, r)
        rx, ry = max(rx, 2e-4), max(ry, 2e-4)
        rings.append([mb.bm.verts.new(pts[i] + nr * math.cos(6.2832 * k / segs) * rx + bi * math.sin(6.2832 * k / segs) * ry)
                      for k in range(segs)])
    return skin_rings(mb, rings, mat, cap and not closed, closed, tcol, smooth)


def skin_rings(mb, rings, mat=0, cap=True, closed=False, tcol=None, smooth=True, flip=False):
    n, segs = len(rings), len(rings[0])
    faces = []
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            q = (a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k])
            faces.append(mb.bm.faces.new(q[::-1] if flip else q))
    if cap:
        faces.append(mb.bm.faces.new(rings[0] if flip else list(reversed(rings[0]))))
        faces.append(mb.bm.faces.new(list(reversed(rings[-1])) if flip else rings[-1]))
    for f in faces:
        f.material_index, f.smooth = mat, smooth
    if tcol:
        layer, val = tcol
        idx = {v: i / max(n - 1, 1) for i, ring in enumerate(rings) for v in ring}
        for f in faces:
            for lp in f.loops:
                lp[layer] = (idx.get(lp.vert, 0.0), val, 0, 1)
    return faces


def torus(mb, R_, r, loc, rot=(0, 0, 0), major=28, minor=8, mat=0, scale=(1, 1, 1), lump=0.0, seed=0):
    rnd = random.Random(seed)
    M = TRS(loc, rot, scale)
    pts = [M @ Vector((R_ * math.cos(6.2832 * i / major), R_ * math.sin(6.2832 * i / major), 0)) for i in range(major)]
    rad = [r * (1 + rnd.uniform(-lump, lump)) for _ in range(major)]
    return tube(mb, pts, rad, minor, mat, closed=True)


def tbox(mb, size, loc, rot=(0, 0, 0), mat=0, top=(1.0, 1.0), shear=(0.0, 0.0)):
    """Box whose top face is scaled (taper) and shifted (shear) - armour plates."""
    vs = bmesh.ops.create_cube(mb.bm, size=1.0)['verts']
    M = TRS(loc, rot, (1, 1, 1))
    for v in vs:
        up = v.co.z > 0
        x = v.co.x * size[0] * (top[0] if up else 1) + (shear[0] if up else 0)
        y = v.co.y * size[1] * (top[1] if up else 1) + (shear[1] if up else 0)
        v.co = M @ Vector((x, y, v.co.z * size[2]))
    return mb._tag(vs, mat)


def orient(z_dir, y_hint=(0, 0, 1)):
    """Rotation matrix whose +Z points along z_dir and +Y as close to y_hint as possible."""
    z = Vector(z_dir).normalized()
    y = Vector(y_hint)
    y = (y - z * y.dot(z)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_4x4()


# ---------------------------------------------------------------- skeleton
def humanoid_bones(J):
    """J: joint heights / offsets in metres (T-pose, facing -Y, left = +X)."""
    B = {}
    def add(n, h, t, p=None, c=False):
        B[n] = (Vector(h), Vector(t), p, c)
    add('root', (0, 0, 0), (0, 0.25, 0))
    add('hips', (0, 0, J['hip']), (0, 0, J['spine']), 'root')
    add('spine', (0, 0, J['spine']), (0, 0, J['chest']), 'hips', True)
    add('chest', (0, 0, J['chest']), (0, 0, J['neck']), 'spine', True)
    add('neck', (0, 0, J['neck']), (0, 0, J['head']), 'chest', True)
    add('head', (0, 0, J['head']), (0, 0, J['top']), 'neck', True)
    for s, sx in (('L', 1), ('R', -1)):
        z = J['sh_z']
        add('clavicle.' + s, (sx * 0.03, 0, z - 0.02), (sx * J['sh_x'], 0, z), 'chest')
        add('upper_arm.' + s, (sx * J['sh_x'], 0, z), (sx * J['elbow'], 0.02, z), 'clavicle.' + s, True)
        add('forearm.' + s, (sx * J['elbow'], 0.02, z), (sx * J['wrist'], 0, z), 'upper_arm.' + s, True)
        add('hand.' + s, (sx * J['wrist'], 0, z), (sx * J['knuckle'], 0, z), 'forearm.' + s, True)
        add('fingers1.' + s, (sx * J['knuckle'], 0, z), (sx * (J['knuckle'] + J['tip']) / 2, 0, z), 'hand.' + s, True)
        add('fingers2.' + s, (sx * (J['knuckle'] + J['tip']) / 2, 0, z), (sx * J['tip'], 0, z), 'fingers1.' + s, True)
        add('thumb.' + s, (sx * (J['wrist'] + 0.03), -0.03, z - 0.01), (sx * (J['wrist'] + 0.08), -0.075, z - 0.02), 'hand.' + s)
        add('thigh.' + s, (sx * J['hip_x'], 0, J['hip']), (sx * J['hip_x'], -0.02, J['knee']), 'hips')
        add('shin.' + s, (sx * J['hip_x'], -0.02, J['knee']), (sx * J['hip_x'], 0.02, J['ankle']), 'thigh.' + s, True)
        add('foot.' + s, (sx * J['hip_x'], 0.02, J['ankle']), (sx * J['hip_x'], -0.13, 0.02), 'shin.' + s, True)
        add('toe.' + s, (sx * J['hip_x'], -0.13, 0.02), (sx * J['hip_x'], -0.21, 0.02), 'foot.' + s, True)
    return B


def make_armature(name, bones, collection):
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    for bn, (h, t, p, c) in bones.items():
        eb = arm.edit_bones.new(bn)
        eb.head, eb.tail = h, t
        if p:
            eb.parent, eb.use_connect = arm.edit_bones[p], c
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.display_type = 'STICK'
    return ob


def bone_parent(ob, arm, bone):
    """Rigidly attach an object (built in world space) to a bone without moving it."""
    b = arm.data.bones[bone]
    ob.parent, ob.parent_type, ob.parent_bone = arm, 'BONE', bone
    ob.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()


def pose(arm, rotations):
    """rotations: list of (bone, world axis 'X'/'Y'/'Z', degrees), applied parents first."""
    for bone, axis, deg in rotations:
        pb = arm.pose.bones[bone]
        bpy.context.view_layer.update()
        head = pb.matrix.to_translation()
        Rm = Matrix.Translation(head) @ Matrix.Rotation(R(deg), 4, axis) @ Matrix.Translation(-head)
        pb.matrix = Rm @ pb.matrix
    bpy.context.view_layer.update()


class Rig:
    """Armature + one rigid mesh per bone (hard-surface parts) + free separate objects."""

    def __init__(self, name, J, collection):
        self.name, self.col, self.J = name, collection, J
        self.arm = make_armature(name + '_Rig', humanoid_bones(J), collection)
        self.parts = {}
        self.extra = []

    def mb(self, bone, tag=''):
        return self.parts.setdefault((bone, tag), MB())

    def finish(self, mats, bevel=0.004):
        objs = []
        for (bone, tag), mb in self.parts.items():
            if not len(mb.bm.verts):
                continue
            o = mb.obj(f'{self.name}_{bone}{("_" + tag) if tag else ""}', mats, self.col,
                       bevel=0.0 if tag.startswith('soft') else bevel, smooth=True)
            bone_parent(o, self.arm, bone)
            objs.append(o)
        return objs

    def attach(self, ob, bone):
        bone_parent(ob, self.arm, bone)
        self.extra.append(ob)
        return ob


# ---------------------------------------------------------------- katana
def build_katana(name, collection, mats, length=0.72, sori=0.035, tassel=False):
    """Returns (katana, saya). Local frame: origin at the guard, blade along +Z, edge toward +Y,
    handle along -Z. mats = [blade, guard, wrap, cap, saya, cord]."""
    def spine_pt(s):
        return Vector((0, -sori * (s / length) ** 2 * 1.0, s))
    k = MB()
    rings = []
    n = 26
    for i in range(n + 1):
        s = length * i / n
        tip = min(1.0, max(0.0, (s - (length - 0.05)) / 0.05))
        w = (0.031 - 0.008 * i / n) * (1 - tip) ** 0.8 + 0.0005
        t = (0.0068 - 0.002 * i / n) * (1 - tip * 0.7)
        c = spine_pt(s) + Vector((0, -0.006 * tip, 0))
        sec = [(-t / 2, -w / 2), (t / 2, -w / 2), (t * 0.42, w * 0.05), (0, w / 2), (-t * 0.42, w * 0.05)]
        rings.append([k.bm.verts.new(c + Vector((x, y + 0.002, 0))) for x, y in sec])
    skin_rings(k, rings, 0, smooth=False)
    k.cube((0.012, 0.034, 0.028), (0, 0.002, 0.014), mat=1)                      # habaki
    k.cone(0.040, 0.040, 0.006, (0, 0.002, -0.003), segs=28, mat=1, scale=(0.82, 1, 1))  # tsuba
    k.cone(0.021, 0.021, 0.004, (0, 0.002, -0.008), segs=20, mat=3, scale=(0.75, 1, 1))
    tube(k, [(0, 0.002, -0.010), (0, 0.003, -0.13), (0, 0.006, -0.255)],
         [(0.0125, 0.0185), (0.0115, 0.017), (0.0125, 0.0185)], 16, 2)
    k.cone(0.0125, 0.011, 0.014, (0, 0.006, -0.262), segs=16, mat=1, scale=(1, 1.45, 1))
    ko = k.obj(name, mats, collection, smooth=True)
    if tassel:
        # separate object that always hangs straight down, whatever the sword is doing
        t = MB()
        tube(t, [(0, 0, 0), (0.004, 0.002, -0.04), (0.0, 0.0, -0.085)], 0.0035, 6, 5)
        tube(t, [(0, 0, -0.085), (0, 0, -0.105), (0, 0, -0.19)], [0.007, 0.015, 0.021], 10, 5)
        to = t.obj(name + '_Tassel', mats, collection, smooth=True)
        to.parent, to.location = ko, (0, 0.006, -0.27)
        up = bpy.data.objects.get('WORLD_Upright')
        if not up:
            up = bpy.data.objects.new('WORLD_Upright', None)
            collection.objects.link(up)
        con = to.constraints.new('COPY_ROTATION')
        con.target = up
    s = MB()
    pts, rad = [], []
    for i in range(15):
        z = (length + 0.03) * i / 14
        p = spine_pt(z); pts.append((p.x, p.y + 0.002, z + 0.004))
        rad.append((0.0125 - 0.002 * i / 14, 0.024 - 0.004 * i / 14))
    tube(s, pts, rad, 16, 4, up=(1, 0, 0))
    s.cone(0.0135, 0.0135, 0.022, (0, 0.002, 0.014), segs=16, mat=1, scale=(1, 1.85, 1))
    e = Vector(pts[-1])
    s.cone(0.0115, 0.009, 0.03, (e.x, e.y, e.z - 0.008), segs=16, mat=1, scale=(1, 1.75, 1))
    for z in (0.10, 0.125, 0.15):                                                   # sageo cord wraps
        p = spine_pt(z)
        tube(s, [(0.0145 * math.cos(a), p.y + 0.002 + 0.026 * math.sin(a), z) for a in [6.2832 * q / 16 for q in range(16)]],
             0.0032, 6, 5, closed=True)
    so = s.obj(name.replace('Katana', 'Saya'), mats, collection, smooth=True)
    return ko, so
