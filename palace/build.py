"""Assemble the haveli courtyard from the kit, add camera rig + sun + sky, save .blend.
Usage: python3 build.py            -> _work/palace.blend
       PALACE_WIRE=1 python3 build.py -> _work/palace_wire.blend"""
import bpy, bmesh, math, random, os, sys
from math import pi, sin, cos, radians
from mathutils import Vector, Matrix, Euler, noise
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import kit
from kit import M, boxb, lathe, finish, Xf, WIRE

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
K = kit.build_kit()
rng = random.Random(11)
COLS = {}
def coll(name):
    if name not in COLS:
        c = bpy.data.collections.new(name); sc.collection.children.link(c); COLS[name] = c
    return COLS[name]
I4 = Matrix.Identity(4)
def P(name, loc=(0, 0, 0), rz=0.0, s=1.0, mat=None, base=I4, rot=None, col='COL_Arch'):
    obs = []
    for k, (me, mk) in enumerate(K[name]):
        ob = bpy.data.objects.new(me.name.replace('KIT_', ''), me)
        ob.matrix_world = base @ M(loc, rot if rot else (0, 0, rz), s)
        ob['mat'] = mat if (mat and k == 0) else mk
        ob['kit'] = name
        coll(col).objects.link(ob); obs.append(ob)
    return obs
def solid(name, boxes, mat, bevel=.015, col='COL_Arch'):
    bm = bmesh.new()
    for b in boxes: boxb(bm, *b)
    ob = bpy.data.objects.new(name, finish(name, bm, bevel)); ob['mat'] = mat
    coll(col).objects.link(ob); return ob

BAY = 3.1; FY = 15.5; BY = 18.6; ZP = .45; ZT = 6.25; ZR = 10.75
# ------------------------------------------------------------ masses
solid('Plinth', [(-23, 19.2, 15, 23, 0, ZP), (-23, 19.2, -23, -15, 0, ZP), (-23, -15, -15, 15, 0, ZP), (15, 19.2, -15, 15, 0, ZP),
                 (-15.06, 15.06, 14.94, 15, .3, ZP+.02), (-15.06, 15.06, -15, -14.94, .3, ZP+.02),
                 (-15, -14.94, -15.06, 15.06, .3, ZP+.02), (14.94, 15, -15.06, 15.06, .3, ZP+.02)], 'sand2', .02)
solid('Terrace', [(-20.5, 20.5, 15.2, 20.5, 6.0, ZT), (-20.5, 20.5, -20.5, -15.2, 6.0, ZT),
                  (-20.5, -15.2, -15.2, 15.2, 6.0, ZT), (15.2, 18.9, -15.2, 15.2, 6.0, ZT)], 'sand2', .02)
solid('Shell', [(-23, 19.1, 18.35, 23, ZR, ZR+.25), (-23, 19.1, 20.5, 20.8, ZP, ZR), (18.85, 19.1, 18.35, 23, ZT, ZR),
                (-23, 19.1, -23, -18.35, ZR, ZR+.25), (-23, 19.1, -20.8, -20.5, ZP, ZR), (18.85, 19.1, -23, -18.35, ZT, ZR),
                (-23, -18.35, -18.35, 18.35, ZR, ZR+.25), (-20.8, -20.5, -18.35, 18.35, ZP, ZR),
                (18.35, 18.85, 15.5, 18.6, ZP, 6.0), (18.35, 18.85, -18.6, -15.5, ZP, 6.0),
                (-6.2, 6.2, 18.35, 23, 14.0, 14.25), (-6.45, -6.2, 18.35, 23, ZR, 14.0), (6.2, 6.45, 18.35, 23, ZR, 14.0),
                (-6.2, 6.2, 20.5, 20.8, ZR, 14.0)], 'sand', .02)
solid('GroundOut', [(-400, 400, -400, 400, -.3, -.04)], 'dirt', 0, 'COL_Ground')

def wing(angle, kind, matw, jh=(), chh=(), doors='dnpdnpdpndpn'):
    B = Matrix.Rotation(angle, 4, 'Z')
    for i in range(10):
        x = -FY + BAY*i
        P('Pillar', (x, FY, ZP), rz=rng.choice((0, pi/2)), mat=matw, base=B)
        xc = x + BAY/2
        P('Arch', (xc, FY, ZP+4.0), mat=matw, base=B)
        P('Chajja', (xc, FY-.225, 5.98), base=B)
        P('RailingBroken' if rng.random() < .12 else 'Railing', (xc, FY-.1, ZT), base=B)
        P('Bracket', (x, FY-.3, ZP+4.0+.85*.0+0.0), s=(1, .5, .5), base=B, mat=matw)
    if kind == 'open':   # east: double colonnade, open to the sunrise side
        for i in range(11):
            x = -FY + BAY*i
            P('Pillar', (x, BY, ZP), mat=matw, base=B)
            if i < 10:
                P('Arch', (x+BAY/2, BY, ZP+4.0), rz=pi, mat=matw, base=B)
                P('Chajja', (x+BAY/2, BY+.225, 5.98), rz=pi, base=B)
                P('Railing', (x+BAY/2, BY+.15, ZT), base=B)
        P('Bangla', (-7.0, 17.05, ZT), base=B, mat='marble')
        P('Chhatri4', (-11.6, 17.05, ZT), rz=pi/4, s=.8, base=B)
        P('Chhatri4', (-2.4, 17.05, ZT), rz=pi/4, s=.8, base=B)
        P('Chhatri8', (8.0, 17.05, ZT), s=.85, base=B)
        return
    for j in range(12):
        x = -BY + BAY*(j+.5); c = doors[j]
        nm = {'d': 'WallDoor', 'n': 'WallNiche', 'p': 'WallPlain'}[c]
        P(nm, (x, BY, ZP), mat=matw, base=B)
        if c == 'p': pass
        if c == 'd':
            P('DoorAjar' if rng.random() < .25 else 'Door', (x, BY+.08, ZP), base=B)
        isj = j in jh
        P('WallJh' if isj else 'WallWin', (x, BY, ZT), mat=matw, base=B)
        if isj: P('Jharokha', (x, BY-.25, ZT+1.05), base=B)
        else: P('WinJali', (x, BY+.05, ZT+1.0), base=B)
        P('Chajja', (x, BY-.25, ZR-.1), base=B)
        P('Parapet', (x, BY-.2, ZR+.25), mat=matw, base=B)
    for (x, nm, s) in chh:
        P(nm, (x, 20.4, ZR+.25), rz=pi/4 if nm == 'Chhatri4' else 0, s=s, base=B)

wing(0, 'full', 'sand', jh=(2, 9), chh=((-11.5, 'Chhatri4', 1.0), (11.5, 'Chhatri4', 1.0), (-16, 'Chhatri8', .7), (15, 'Chhatri8', .7)))
wing(pi/2, 'full', 'sand2', jh=(2, 5, 6, 9), chh=((-9, 'Chhatri4', .9), (0, 'Bangla', .8), (9, 'Chhatri4', .9)), doors='pdnpdnndpndp')
wing(pi, 'full', 'sand', jh=(3, 8), chh=((-12, 'Chhatri8', .8), (12, 'Chhatri8', .8)), doors='npdnpddpndpn')
wing(-pi/2, 'open', 'marble')
# north central block: third storey + hero pavilion cluster + big jharokha
for j in range(4):
    x = -4.65 + BAY*j
    P('WallTop', (x, BY, ZR), mat='sand'); P('WinJali', (x, BY+.05, ZR+.6), s=(1, 1, .9))
    P('Chajja', (x, BY-.25, 13.9)); P('Parapet', (x, BY-.2, 14.25), mat='sand')
P('Jharokha', (0, BY-.25, ZT+.95), s=1.45)
P('Bangla', (0, 20.3, 14.25), s=1.0); P('Chhatri4', (-4.4, 20.3, 14.25), rz=pi/4, s=.75); P('Chhatri4', (4.4, 20.3, 14.25), rz=pi/4, s=.75)
# south gate block (big pol arch look) reuse: two urns + steps
for sx in (-1, 1):
    for sy in (-1, 1):
        P('Tower', (sx*19.6, sy*19.6, 0), mat='sand' if sy > 0 else 'sand2')
        P('Chhatri8', (sx*19.6, sy*19.6, 12.4), s=1.15)
# steps on every side (centre two bays) + extra
for ang in (0, pi/2, pi, -pi/2):
    B = Matrix.Rotation(ang, 4, 'Z')
    for x in (-1.55, 1.55): P('Steps', (x, 15.0, 0), base=B)
    for x in (-3.1, 3.1): P('StepCheek', (x, 15.0, 0), base=B)
    for sx in (-1, 1): P('Urn', (sx*3.6, 14.55, 0), rz=rng.uniform(0, 6), s=rng.uniform(.8, .95), base=B, col='COL_Props')
P('Steps', (-9.3, 15.0, 0)); P('Steps', (9.3, 15.0, 0), base=Matrix.Rotation(pi/2, 4, 'Z'))
for x in (-10.85, -7.75): P('StepCheek', (x, 15.0, 0))
for x in (10.85, 7.75): P('StepCheek', (x, 15.0, 0), base=Matrix.Rotation(pi/2, 4, 'Z'))

# ------------------------------------------------------------ paving
def pave(x0, x1, y0, y1, z, mat='floor', crack=.12):
    y = y0
    while y < y1-.01:
        d = rng.uniform(.85, 1.35)
        if y1-y-d < .55: d = y1-y
        x = x0 + 0
        while x < x1-.01:
            w = rng.uniform(.85, 1.9)
            if x1-x-w < .6: w = x1-x
            r = rng.random(); v = 3 if r < crack else (2 if r < crack+.1 else (1 if r < .5 else 0))
            P('Slab%d' % v, (x+w/2, y+d/2, z+rng.uniform(-.009, .005)), s=(w-.018, d-.018, 1), mat=mat,
              rot=(rng.uniform(-.006, .006), rng.uniform(-.006, .006), rng.choice((0, pi))), col='COL_Floor')
            x += w
        y += d
pave(-15, 15, -15, 15, 0.0)
for (a, b, c, d) in ((-18.3, 18.3, 15, 18.3), (-18.3, 18.3, -18.3, -15), (-18.3, -15, -15, 15), (15, 18.9, -15, 15)):
    pave(a, b, c, d, ZP+.05, 'floor2', .05)
pave(15.2, 18.9, -15.2, 15.2, ZT+.05, 'floor2', .05)
solid('FloorBase', [(-15.2, 15.2, -15.2, 15.2, -.1, -.03)], 'dirt', 0, 'COL_Floor')
if not WIRE:
    me = bpy.data.meshes.new('Water'); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=14.95); bm.to_mesh(me); bm.free()
    me.materials.append(None)
    ob = bpy.data.objects.new('Water', me); ob.location.z = .004; ob['mat'] = 'water'; coll('COL_FX').objects.link(ob)

# ------------------------------------------------------------ dressing: ivy, moss, debris, props
def wall_pt(side, u, off):  # side 0..3 = N,W,S,E ; u along wing ; off = distance from pillar line into courtyard
    B = Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z'); return B, (u, FY-off)
for side, us in ((0, (-15.5, -12.4, -9.3, -3.1, 6.2)), (1, (-12.4, -6.2, 0, 3.1, 9.3, 12.4)), (2, (-9.3, 3.1, 12.4)), (3, (-12.4, 3.1))):
    B = Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z')
    for u in us:
        P('IvyPillar', (u, FY, ZP+.2), rz=rng.uniform(0, 6), s=(1, 1, rng.uniform(.75, 1.05)), base=B, col='COL_Foliage')
for side, us in ((0, (-13.5, -10.5, -7, -4.5, 8, 12.5)), (1, (-13, -9, -4, 1, 5, 10, 13.5)), (2, (-11, -2, 6, 13)), (3, (-13, -4, 11))):
    B = Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z')
    for u in us:
        P('IvyHang', (u, FY-.32, ZT+.05+rng.uniform(0, .7)), s=(rng.uniform(.8, 1.3), 1, rng.uniform(.8, 1.5)), base=B, col='COL_Foliage')
        if rng.random() < .6:
            P('IvyHang', (u+rng.uniform(-1, 1), FY-.28, 5.7), s=(rng.uniform(.6, 1), 1, rng.uniform(.5, 1.0)), base=B, col='COL_Foliage')
for side, us in ((0, (-16.5, -11, -5.5, 4.5, 14)), (1, (-14, -7.5, 2, 8.5, 15)), (2, (-12, 0.5, 9))):
    B = Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z')
    for u in us:
        P(rng.choice(('IvyWall', 'IvyWall2')), (u, BY-.26, ZP+.05), s=(rng.uniform(.9, 1.4), 1, rng.uniform(.8, 1.15)), base=B, col='COL_Foliage')
        P(rng.choice(('IvyWall', 'IvyWall2')), (u+rng.uniform(-2, 2), BY-.27, ZT), s=(rng.uniform(.8, 1.3), 1, rng.uniform(.5, .85)), base=B, col='COL_Foliage')
        P('IvyHang', (u+rng.uniform(-2, 2), BY-.5, ZR+.3), s=(1.2, 1, rng.uniform(.8, 1.6)), base=B, col='COL_Foliage')
for sx, sy in ((-1, 1), (-1, -1), (1, 1)):
    for k in range(5):
        a = math.atan2(-sy, -sx) + rng.uniform(-1.2, 1.2)
        P('IvyWall', (sx*19.6+2.25*cos(a), sy*19.6+2.25*sin(a), rng.choice((ZT, ZP, 8.5))), rz=a+pi/2, s=(1.1, 1, 1.1), col='COL_Foliage')
# moss + rocks + leaves hugging the plinth base, corners and joints
def edge_pt(inset_lo, inset_hi):
    side = rng.randrange(4); u = rng.uniform(-14.8, 14.8); d = 15 - rng.uniform(inset_lo, inset_hi)
    return Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z') @ Vector((u, d, 0))
for k in range(150):
    p = edge_pt(.0, .9) if k < 110 else Vector((rng.uniform(-14, 14), rng.uniform(-14, 14), 0))
    s = rng.uniform(.25, .9)
    P('Moss%d' % rng.randrange(3), (p.x, p.y, .0), rz=rng.uniform(0, 6), s=(s, s*rng.uniform(.5, 1), rng.uniform(.5, 1.2)), col='COL_Foliage')
for k in range(60):
    side = rng.randrange(4); u = rng.uniform(-18, 18)
    p = Matrix.Rotation((0, pi/2, pi, -pi/2)[side], 4, 'Z') @ Vector((u, rng.choice((15.1, 18.1, 15.6)), ZP+.05))
    s = rng.uniform(.2, .6); P('Moss%d' % rng.randrange(3), tuple(p), rz=rng.uniform(0, 6), s=(s, s, .8), col='COL_Foliage')
for k in range(70):
    p = edge_pt(.05, 1.6) if k < 50 else Vector((rng.uniform(-13, 13), rng.uniform(-13, 13), 0))
    s = rng.uniform(.05, .22)
    P('Rock%d' % rng.randrange(3), (p.x, p.y, 0), rz=rng.uniform(0, 6), s=(s, s*rng.uniform(.7, 1.2), s*rng.uniform(.6, 1)), col='COL_Props')
for k in range(520):
    if k < 330: p = edge_pt(.0, 3.0)
    else:
        a = rng.uniform(0, 6.28); r = rng.uniform(0, 14); p = Vector((r*cos(a), r*sin(a), 0))
    P('Leaf', (p.x, p.y, .012), s=rng.uniform(.8, 1.6), rot=(rng.uniform(-.25, .25), rng.uniform(-.25, .25), rng.uniform(0, 6.28)), col='COL_Props')
# story clusters
P('Pedestal', (2.6, 1.4, 0), col='COL_Props'); P('Pot', (2.6, 1.4, 1.2), s=.7, col='COL_Props')
P('IvyPillar', (2.6, 1.4, 1.3), s=(.9, .9, .28), col='COL_Foliage'); P('Lantern', (3.5, .9, 0), rz=.4, s=1.3, col='COL_Props')
for (x, y, nm, s, rz) in ((-13.2, 13.6, 'Pot', 1.0, 0), (-12.5, 14.1, 'Pot', .75, 1), (-13.7, 12.8, 'PotBroken', .9, 2), (-12.3, 13.2, 'Pot', .55, 3),
                          (12.6, -13.5, 'PotBroken', 1.0, 1), (13.4, -13.0, 'Pot', .8, 0), (-13.6, -6.0, 'Pot', .9, 0), (-13.9, -6.9, 'Pot', .6, 0),
                          (6.5, 14.2, 'PotBroken', .8, 4), (-6.8, -14.1, 'Pot', .85, 2)):
    P(nm, (x, y, 0.0), rz=rz, s=s, col='COL_Props')
P('Stump', (12.3, 5.2, 0), rz=.7, mat='marble', col='COL_Props'); P('Block', (11.2, 6.8, 0), rz=1.1, mat='marble', col='COL_Props')
P('Block', (12.9, 3.6, 0), rz=-.5, s=.8, mat='marble', col='COL_Props'); P('Block', (-10.5, 13.9, 0), rz=.3, s=.9, col='COL_Props')
P('Block', (4.8, -13.8, .0), rz=2.0, s=1.1, col='COL_Props')
for (x, y, rz) in ((-1.9, 14.35, .3), (13.9, -2.0, 1.2), (-14.3, 3.4, 2.0), (2.2, -14.3, .1)):
    P('Lantern', (x, y, .31 if abs(x) < 3 or abs(y) < 3 else 0), rz=rz, s=1.4, col='COL_Props')
for (az, r) in ((204, 8.3), (102, 7.6), (335, 7.4)):   # foreground lamp posts near the orbit path
    x, y = r*cos(radians(az)), r*sin(radians(az))
    P('LampPost', (x, y, 0), col='COL_Props'); P('Lantern', (x, y, 1.7), rz=rng.uniform(0, 1), s=1.05, col='COL_Props')
    P('IvyPillar', (x, y, .1), s=(.5, .5, .35), col='COL_Foliage')

# ------------------------------------------------------------ distant skyline, 3 layers
def skyline(name, r0, r1, n, hmin, hmax, mat, hill=False):
    bm = bmesh.new(); r = random.Random(hash(name) % 999)
    for k in range(n):
        a = 2*pi*k/n + r.uniform(-.05, .05); d = r.uniform(r0, r1); h = r.uniform(hmin, hmax)
        x, y = d*cos(a), d*sin(a)
        if hill:
            w = r.uniform(60, 130)
            lathe(bm, kit.cr([(w, -2), (w*.75, h*.25), (w*.4, h*.7), (w*.12, h*.95), (.5, h)], 2), segs=14, loc=(x, y, 0),
                  mod=lambda aa, zz: 1+.18*sin(3*aa+k)+.08*sin(7*aa))
        else:
            w = r.uniform(4, 8) * (d/60)
            with Xf(bm, M((x, y, 0), (0, 0, a))):
                boxb(bm, -w/2, w/2, -w, w, 0, h)
                for q in range(int(2*w/1.2)):   # kangura-like crenels so the silhouette is not a plain box
                    yy = -w + 2*w*(q+.5)/int(2*w/1.2); boxb(bm, -w/2-.1, -w/2+.3, yy-.3, yy+.3, h, h+.6)
                kit.dome(bm, w*r.uniform(.2, .32), (0, r.uniform(-w*.5, w*.5), h), segs=10)
                if r.random() < .6: boxb(bm, -w*.25, w*.25, w*.3, w*.8, h, h*1.3); kit.dome(bm, w*.18, (0, w*.55, h*1.3), segs=8)
                if r.random() < .5: boxb(bm, -w*.3, w*.3, -w*.9, -w*.4, h, h*1.18)
    ob = bpy.data.objects.new(name, finish(name, bm, 0)); ob['mat'] = mat; coll('COL_BG').objects.link(ob)
skyline('BG_Near', 75, 115, 70, 5, 13, 'bg1'); skyline('BG_Mid', 150, 210, 44, 14, 34, 'bg2'); skyline('BG_Hills', 260, 380, 22, 35, 85, 'bg3', True)

# ------------------------------------------------------------ camera rig (pivot > dolly > shake > camera, target empty)
sc.render.fps = 24; sc.frame_start = 1; sc.frame_end = 240
def empty(name, parent=None):
    e = bpy.data.objects.new(name, None); e.empty_display_size = .5; coll('COL_Cam').objects.link(e)
    if parent: e.parent = parent
    return e
pivot = empty('CAM_Pivot'); dolly = empty('CAM_Dolly', pivot); shake = empty('CAM_Shake', dolly); target = empty('CAM_Target', pivot)
cam_d = bpy.data.cameras.new('CAM_Main'); cam = bpy.data.objects.new('CAM_Main', cam_d); coll('COL_Cam').objects.link(cam)
cam.parent = shake; sc.camera = cam
cam_d.lens = 30; cam_d.sensor_width = 36; cam_d.clip_start = .1; cam_d.clip_end = 3000
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 1.4; cam_d.dof.focus_distance = 14.0
tc = cam.constraints.new('TRACK_TO'); tc.target = target; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
TH0 = radians(-45)
def key(ob, path, frame, val):
    setattr(ob, path, val); ob.keyframe_insert(path, frame=frame)
key(pivot, 'rotation_euler', 1, (0, 0, TH0)); key(pivot, 'rotation_euler', 48, (0, 0, TH0)); key(pivot, 'rotation_euler', 192, (0, 0, TH0+2*pi))
key(pivot, 'rotation_euler', 240, (0, 0, TH0+2*pi))
for f, v in ((1, (0, -13.5, 1.6)), (48, (0, -11.5, 1.6)), (192, (0, -11.5, 1.6)), (240, (0, -17.0, 10.0))): key(dolly, 'location', f, v)
for f, v in ((1, (0, 5.0, 4.6)), (48, (0, 0.0, 3.5)), (192, (0, 0.0, 3.5)), (240, (0, 0.0, 6.3))): key(target, 'location', f, v)
for f, v in ((1, 30), (192, 30), (240, 26)): key(cam_d, 'lens', f, v)
for f, v in ((1, 16.0), (192, 14.0), (240, 22.0)):
    cam_d.dof.focus_distance = v; cam_d.dof.keyframe_insert('focus_distance', frame=f)
for f in range(1, 241):   # handheld-like micro noise: sum of slow sines, baked
    t = f/24
    shake.location = (.012*sin(1.9*t+.3)+.006*sin(4.7*t), .008*sin(2.6*t+1.1)+.004*sin(6.1*t), .010*sin(2.2*t+2.0)+.005*sin(5.3*t+.7))
    shake.keyframe_insert('location', frame=f)

# ------------------------------------------------------------ light: one low sun (15 deg, 4000 K) + cool sky
AZ, EL = radians(30), radians(15)   # sun comes from east-north-east = behind the right (east) wall
S = Vector((cos(EL)*cos(AZ), cos(EL)*sin(AZ), sin(EL)))
sd = bpy.data.lights.new('LGT_Key_Sun', 'SUN'); sun = bpy.data.objects.new('LGT_Key_Sun', sd); coll('COL_Light').objects.link(sun)
sun.rotation_euler = S.to_track_quat('Z', 'Y').to_euler(); sd.energy = 7.0; sd.angle = radians(2.5)
try: sd.use_temperature = True; sd.temperature = 4000
except Exception: sd.color = (1.0, .65, .38)
sc['sun_dir'] = tuple(S)
w = bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear(); N = nt.nodes.new; L = nt.links.new
tcn = N('ShaderNodeTexCoord'); nrm = N('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L(tcn.outputs['Generated'], nrm.inputs[0])
sep = N('ShaderNodeSeparateXYZ'); L(nrm.outputs[0], sep.inputs[0])
ramp = N('ShaderNodeValToRGB'); L(sep.outputs['Z'], ramp.inputs[0])
e = ramp.color_ramp.elements; e[0].position = .0; e[0].color = (.95, .62, .40, 1); e[1].position = .45; e[1].color = (.30, .46, .85, 1)
m = e.new(.12) if hasattr(e, 'new') else None
if m: m.color = (.62, .62, .78, 1)
dot = N('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'; L(nrm.outputs[0], dot.inputs[0]); dot.inputs[1].default_value = S
pw = N('ShaderNodeMath'); pw.operation = 'POWER'; pw.use_clamp = True; L(dot.outputs['Value'], pw.inputs[0]); pw.inputs[1].default_value = 10
bb = N('ShaderNodeBlackbody'); bb.inputs[0].default_value = 3600
sc2 = N('ShaderNodeVectorMath'); sc2.operation = 'SCALE'; L(bb.outputs[0], sc2.inputs[0]); L(pw.outputs[0], sc2.inputs['Scale'])
mul = N('ShaderNodeVectorMath'); mul.operation = 'SCALE'; L(sc2.outputs[0], mul.inputs[0]); mul.inputs['Scale'].default_value = 5.0
add = N('ShaderNodeVectorMath'); add.operation = 'ADD'; L(ramp.outputs[0], add.inputs[0]); L(mul.outputs[0], add.inputs[1])
bg = N('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0; L(add.outputs[0], bg.inputs['Color'])
out = N('ShaderNodeOutputWorld'); L(bg.outputs[0], out.inputs['Surface'])

n_obj = len(bpy.data.objects); tris = 0
for ob in bpy.data.objects:
    if ob.type == 'MESH': tris += len(ob.data.polygons)
print('OBJECTS', n_obj, 'instanced polys', tris, 'unique meshes', len(bpy.data.meshes), 'kit pieces', len(K))
os.makedirs(os.path.join(HERE, '_work'), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, '_work', 'palace_wire.blend' if WIRE else 'palace.blend'))
