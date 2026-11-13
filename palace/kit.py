"""Modular Rajasthani haveli kit: every piece is a procedural bmesh generator.
Used by build.py. Original design, no downloaded assets."""
import bpy, bmesh, math, random, os
from math import pi, sin, cos, radians
from mathutils import Vector, Matrix, Euler, noise

WIRE = os.environ.get("PALACE_WIRE") == "1"

def M(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    if isinstance(scale, (int, float)):
        scale = (scale,) * 3
    return Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(scale))

class Xf:
    """Transform every vertex created inside the with-block."""
    def __init__(s, bm, mat): s.bm, s.mat = bm, mat
    def __enter__(s): s.n = len(s.bm.verts); return s
    def __exit__(s, *a):
        s.bm.verts.ensure_lookup_table()
        bmesh.ops.transform(s.bm, matrix=s.mat, verts=s.bm.verts[s.n:])

def boxb(bm, x0, x1, y0, y1, z0, z1):
    bmesh.ops.create_cube(bm, size=1.0, matrix=M(((x0+x1)/2, (y0+y1)/2, (z0+z1)/2), (0, 0, 0), (x1-x0, y1-y0, z1-z0)))

def box(bm, size, loc=(0, 0, 0), rot=(0, 0, 0)):
    bmesh.ops.create_cube(bm, size=1.0, matrix=M(loc, rot, size))

def cr(pts, sub=4):
    """Catmull-Rom resample of a 2D profile."""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = [Vector(p) for p in P[i-1:i+3]]
        for k in range(sub):
            t = k / sub
            out.append(0.5 * ((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t + (-p0+3*p1-3*p2+p3)*t**3))
    out.append(Vector(pts[-1]))
    return [(max(p.x, 0.004), p.y) for p in out]

def lathe(bm, prof, segs=24, loc=(0, 0, 0), mod=None, phase=0.0, cap=True):
    rings = []
    for (r, z) in prof:
        ring = []
        for i in range(segs):
            a = phase + 2*pi*i/segs
            rr = r * (mod(a, z) if mod else 1.0)
            ring.append(bm.verts.new((loc[0]+rr*cos(a), loc[1]+rr*sin(a), loc[2]+z)))
        rings.append(ring)
    for j in range(len(rings)-1):
        a, b = rings[j], rings[j+1]
        for i in range(segs):
            bm.faces.new((a[i], a[(i+1) % segs], b[(i+1) % segs], b[i]))
    if cap:
        bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

def prism(bm, pts, t, plane='YZ'):
    def mk(p, o):
        if plane == 'YZ': return (o, p[0], p[1])
        if plane == 'XZ': return (p[0], o, p[1])
        return (p[0], p[1], o)
    a = [bm.verts.new(mk(p, -t/2)) for p in pts]
    b = [bm.verts.new(mk(p, t/2)) for p in pts]
    bm.faces.new(a); bm.faces.new(b[::-1])
    n = len(pts)
    for i in range(n):
        bm.faces.new((a[i], b[i], b[(i+1) % n], a[(i+1) % n]))

def finish(name, bm, bevel=0.012, angle=30, smooth=42, weld=0.0):
    if weld > 0:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        es = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > radians(angle)]
        if es:
            bmesh.ops.bevel(bm, geom=es, offset=bevel, offset_type='OFFSET', segments=1,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
    if WIRE:
        bmesh.ops.wireframe(bm, faces=bm.faces[:], thickness=0.012, use_replace=True,
                            use_boundary=True, use_even_offset=False)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    try: me.set_sharp_from_angle(angle=radians(smooth))
    except Exception: pass
    me.materials.append(None)
    return me

# ---------------------------------------------------------------- parts
def pillar(bm, h=4.0, r=0.22, loc=(0, 0, 0), segs=32, flutes=8):
    x, y, z = loc
    boxb(bm, x-1.35*r, x+1.35*r, y-1.35*r, y+1.35*r, z, z+0.07*h)
    boxb(bm, x-1.2*r, x+1.2*r, y-1.2*r, y+1.2*r, z+0.07*h, z+0.092*h)
    P = [(1.1, .09), (1.22, .105), (1.1, .12), (.95, .13), (1.0, .15), (1.2, .175), (1.28, .2), (1.2, .23),
         (1.0, .265), (.86, .285), (.8, .3), (.93, .31), (.93, .33), (.8, .34), (.8, .36), (.7, .78),
         (.82, .79), (.82, .81), (.7, .82), (.68, .84), (.78, .86), (1.05, .89), (1.3, .92), (1.34, .94), (1.15, .955)]
    def mod(a, zz):
        zf = zz / h
        if .355 <= zf <= .785: return 1 - 0.08*(0.5+0.5*cos(flutes*a))
        if .15 < zf < .27 or .855 < zf < .95: return 1 + 0.08*abs(cos(flutes*a/2))
        return 1.0
    lathe(bm, [(r*a, h*b) for a, b in P], segs=segs, loc=loc, mod=mod)
    boxb(bm, x-1.45*r, x+1.45*r, y-1.45*r, y+1.45*r, z+.955*h, z+h)

def wall_opening(bm, W, w, z_bot, z_sill, z_spring, rise, z_top, t, foils=7, amp=0.07, frame=True, n=5):
    """Wall slab (in XZ, thickness t along Y) with a cusped (scalloped) arch opening."""
    N = foils * n
    base = []
    for i in range(N+1):
        th = pi*(1 - i/N); c, s = cos(th), sin(th)
        base.append(Vector(((w/2)*c, z_spring + rise*(0.82*max(s, 0)**0.85 + 0.18*(1-abs(c))**2.2))))
    arch = []
    for i in range(N+1):
        tg = (base[min(i+1, N)] - base[max(i-1, 0)]).normalized()
        arch.append(base[i] + Vector((-tg.y, tg.x)) * (amp*abs(sin(pi*foils*i/N))))
    inner = []
    if z_spring > z_sill + 1e-6:
        nj = max(1, int((z_spring-z_sill)/0.45))
        inner += [Vector((-w/2, z_sill + (z_spring-z_sill)*k/nj)) for k in range(nj)]
        inner += arch
        inner += [Vector((w/2, z_spring - (z_spring-z_sill)*k/nj)) for k in range(1, nj+1)]
    else:
        inner = arch
    C = Vector((0, z_sill)); outer = []
    for p in inner:
        d = p - C
        t1 = (W/2)/abs(d.x) if abs(d.x) > 1e-9 else 1e18
        t2 = (z_top-z_sill)/d.y if d.y > 1e-9 else 1e18
        outer.append(C + d*min(t1, t2))
    for corner in (Vector((-W/2, z_top)), Vector((W/2, z_top))):
        k = min(range(len(outer)), key=lambda i: (outer[i]-corner).length)
        outer[k] = corner
    K = len(inner)
    vf = [(bm.verts.new((p.x, -t/2, p.y)), bm.verts.new((q.x, -t/2, q.y))) for p, q in zip(inner, outer)]
    vb = [(bm.verts.new((p.x, t/2, p.y)), bm.verts.new((q.x, t/2, q.y))) for p, q in zip(inner, outer)]
    for i in range(K-1):
        bm.faces.new((vf[i][0], vf[i+1][0], vf[i+1][1], vf[i][1]))
        bm.faces.new((vb[i][0], vb[i][1], vb[i+1][1], vb[i+1][0]))
        bm.faces.new((vf[i][0], vb[i][0], vb[i+1][0], vf[i+1][0]))
        bm.faces.new((vf[i][1], vf[i+1][1], vb[i+1][1], vb[i][1]))
    bm.faces.new((vf[0][0], vf[0][1], vb[0][1], vb[0][0]))
    bm.faces.new((vf[-1][0], vb[-1][0], vb[-1][1], vf[-1][1]))
    if z_sill > z_bot + 1e-6:
        boxb(bm, -W/2, W/2, -t/2, t/2, z_bot, z_sill)
    apex = z_spring + rise + amp
    if frame and w/2 + 0.2 < W/2 and apex + 0.22 < z_top:
        fx = w/2 + amp + 0.06; fz = apex + 0.1; d = 0.035
        boxb(bm, -fx-0.09, -fx, -t/2-d, -t/2+0.01, z_sill, fz+0.09)
        boxb(bm, fx, fx+0.09, -t/2-d, -t/2+0.01, z_sill, fz+0.09)
        boxb(bm, -fx, fx, -t/2-d, -t/2+0.01, fz, fz+0.09)

def jali(bm, w, h, t=0.03, cell=0.09, bar=0.02):
    """Diagonal lattice clipped to rectangle x[0,w] z[0,h], centred on y=0."""
    step = cell*math.sqrt(2)
    c = -h + step/2
    while c < w:
        x0, z0 = max(c, 0), max(-c, 0); x1, z1 = min(w, c+h), min(h, w-c)
        L = math.hypot(x1-x0, z1-z0)
        if L > 0.03:
            box(bm, (L, t, bar), ((x0+x1)/2, 0, (z0+z1)/2), (0, -pi/4, 0))
        c += step
    c = step/2
    while c < w+h:
        x0, z0 = max(c-h, 0), min(c, h); x1, z1 = min(c, w), max(c-w, 0)
        L = math.hypot(x1-x0, z1-z0)
        if L > 0.03:
            box(bm, (L, t*0.9, bar), ((x0+x1)/2, 0, (z0+z1)/2), (0, pi/4, 0))
        c += step

def grid_solid(bm, fn, nu, nv, thick):
    top = [[bm.verts.new(fn(-1+2*i/nu, -1+2*j/nv)) for j in range(nv+1)] for i in range(nu+1)]
    bot = [[bm.verts.new(Vector(v.co) - Vector((0, 0, thick))) for v in row] for row in top]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((top[i][j], top[i+1][j], top[i+1][j+1], top[i][j+1]))
            bm.faces.new((bot[i][j], bot[i][j+1], bot[i+1][j+1], bot[i+1][j]))
    for i in range(nu):
        bm.faces.new((top[i][0], bot[i][0], bot[i+1][0], top[i+1][0]))
        bm.faces.new((top[i][nv], top[i+1][nv], bot[i+1][nv], bot[i][nv]))
    for j in range(nv):
        bm.faces.new((top[0][j], top[0][j+1], bot[0][j+1], bot[0][j]))
        bm.faces.new((top[nu][j], bot[nu][j], bot[nu][j+1], top[nu][j+1]))

def bangla_roof(bm, a, b, h, thick=0.07, nu=14, nv=8):
    grid_solid(bm, lambda u, v: (a*u, b*v, h*(1-0.5*u*u) - 0.6*h*abs(v)**1.6), nu, nv, thick)

FINIAL = [(.5, 0), (1, .25), (1.1, .6), (.5, .95), (.25, 1.1), (.6, 1.3), (.25, 1.55), (.08, 1.75), (.03, 2.3)]
def finial(bm, s, loc):
    lathe(bm, [(r*s*0.1, z*s*0.1) for r, z in cr(FINIAL, 3)], segs=10, loc=loc)

DOME = [(1.0, 0), (1.0, .12), (1.07, .14), (1.07, .2), (1.0, .22), (1.05, .35), (1.03, .6), (.9, .82), (.7, 1.0),
        (.45, 1.13), (.22, 1.2), (.12, 1.24), (.2, 1.27), (.22, 1.31), (.1, 1.34), (.05, 1.37), (.11, 1.43),
        (.12, 1.5), (.06, 1.56), (.03, 1.6), (.08, 1.66), (.03, 1.74), (.01, 1.92)]
def dome(bm, R, loc, segs=24):
    def mod(a, zz):
        return 1 + 0.02*cos(12*a) if .25*R < zz < 1.15*R else 1.0
    lathe(bm, [(r*R, z*R) for r, z in cr(DOME, 3)], segs=segs, loc=loc, mod=mod)

CHAJJA = [(0, 0.0), (0, 0.13), (-0.95, -0.2), (-0.95, -0.27)]
BRACKET = [(0, 0), (-0.8, 0), (-0.8, -0.1), (-0.6, -0.17), (-0.4, -0.34), (-0.22, -0.58), (-0.1, -0.8), (0, -0.85)]
def chajja(bm, L, brackets=4, s=1.0):
    with Xf(bm, M((0, 0, 0), (0, 0, 0), (1, s, s))):
        prism(bm, CHAJJA, L, 'YZ')
        for k in range(brackets):
            x = -L/2 + L*(k+0.5)/brackets
            with Xf(bm, M((x, 0, -0.03), (0, 0, 0), (1, 0.7, 0.55))):
                prism(bm, BRACKET, 0.1, 'YZ')

def chhatri(bm, n=4, R=1.7, hc=2.0, rc=0.09):
    ph = pi/n
    lathe(bm, [(R+.42, 0), (R+.42, .18), (R+.32, .22), (R+.32, .3)], segs=n, phase=ph)
    W = 2*R*sin(pi/n); dist = R*cos(pi/n); z1 = .3 + hc; H = min(0.28*W + 0.18, 0.9)
    for i in range(n):
        a = ph + 2*pi*i/n
        pillar(bm, h=hc, r=rc, loc=(R*cos(a), R*sin(a), .3), segs=12, flutes=6)
        am = ph + 2*pi*(i+.5)/n
        with Xf(bm, M((dist*cos(am), dist*sin(am), z1), (0, 0, am-pi/2))):
            wall_opening(bm, W, W-2.9*rc, 0, 0, 0, H-0.2, H, 0.14, foils=5, amp=0.035, frame=False, n=4)
    z2 = z1 + H
    lathe(bm, [(R+.14, z2), (R+.14, z2+.14)], segs=n, phase=ph)
    lathe(bm, [(R+.15, z2+.14), (R+.95, z2-.14), (R+.95, z2-.07), (R+.15, z2+.25), (R+.15, z2+.14)], segs=n, phase=ph, cap=False)
    Rd = (R+.14)*cos(pi/n)*0.93
    lathe(bm, [(Rd*1.04, z2+.2), (Rd*1.04, z2+.42)], segs=max(n, 8), phase=ph)
    dome(bm, Rd, (0, 0, z2+.4))

def bangla_pavilion(bm, a=2.5, b=1.3, hc=2.3, rc=0.1):
    boxb(bm, -a-.35, a+.35, -b-.35, b+.35, 0, .2); boxb(bm, -a-.25, a+.25, -b-.25, b+.25, .2, .3)
    xs = (-a, -a/3, a/3, a); z1 = .3 + hc
    for x in xs:
        for y in (-b, b):
            pillar(bm, h=hc, r=rc, loc=(x, y, .3), segs=12, flutes=6)
    for k in range(3):
        for y, rz in ((-b, 0), (b, pi)):
            with Xf(bm, M(((xs[k]+xs[k+1])/2, y, z1), (0, 0, rz))):
                wall_opening(bm, 2*a/3, 2*a/3-0.3, 0, 0, 0, .5, .72, .14, foils=7, amp=.04, frame=False, n=4)
    for x, rz in ((-a, -pi/2), (a, pi/2)):
        with Xf(bm, M((x, 0, z1), (0, 0, rz))):
            wall_opening(bm, 2*b, 2*b-0.3, 0, 0, 0, .5, .72, .14, foils=7, amp=.04, frame=False, n=4)
    z2 = z1 + .72
    boxb(bm, -a-.14, a+.14, -b-.14, b+.14, z2, z2+.16)
    for y, rz, L in ((-b-.14, 0, 2*a+.28), (b+.14, pi, 2*a+.28)):
        with Xf(bm, M((0, y, z2+.05), (0, 0, rz))): chajja(bm, L, 6)
    for x, rz in ((-a-.14, -pi/2), (a+.14, pi/2)):
        with Xf(bm, M((x, 0, z2+.05), (0, 0, rz))): chajja(bm, 2*b+.28, 3)
    with Xf(bm, M((0, 0, z2+.16))):
        bangla_roof(bm, a+.55, b+.5, 1.15, 0.08, 18, 10)
        for x in (-a*.55, 0, a*.55):
            finial(bm, 2.2, (x, 0, 1.15*(1-0.5*(x/(a+.55))**2)-0.05))

def jharokha(bm):
    for x in (-.9, 0, .9):
        with Xf(bm, M((x, 0, 0), (0, 0, 0), (1, 1.25, 1.2))): prism(bm, BRACKET, 0.16, 'YZ')
    boxb(bm, -1.3, 1.3, -1.1, 0, 0, .12); boxb(bm, -1.36, 1.36, -1.16, 0, .12, .19)
    with Xf(bm, M((-1.15, -1.0, .27))): jali(bm, 2.3, .55, .03, .07, .016)
    boxb(bm, -1.2, 1.2, -1.04, -.96, .19, .27); boxb(bm, -1.2, 1.2, -1.05, -.95, .82, .9)
    for sx in (-1, 1):
        with Xf(bm, M((sx*1.2, -1.0, .27), (0, 0, pi/2))): jali(bm, 1.0, .55, .03, .07, .016)
        boxb(bm, sx*1.2-.04, sx*1.2+.04, -1.0, 0, .19, .27); boxb(bm, sx*1.2-.05, sx*1.2+.05, -1.0, 0, .82, .9)
    xs = (-1.15, -.4, .4, 1.15)
    for x in xs: pillar(bm, h=1.72, r=.06, loc=(x, -1.0, .19), segs=10, flutes=5)
    z1 = 1.91
    for k in range(3):
        W = xs[k+1]-xs[k]
        with Xf(bm, M(((xs[k]+xs[k+1])/2, -1.0, z1))):
            wall_opening(bm, W, W-.17, 0, 0, 0, .26, .42, .1, foils=5, amp=.025, frame=False, n=4)
    for sx in (-1, 1):
        with Xf(bm, M((sx*1.15, -.5, z1), (0, 0, sx*pi/2))):
            wall_opening(bm, 1.0, .83, 0, 0, 0, .26, .42, .1, foils=5, amp=.025, frame=False, n=4)
    z2 = z1 + .42
    boxb(bm, -1.25, 1.25, -1.1, 0, z2, z2+.1)
    with Xf(bm, M((0, -1.1, z2+.02), (0, 0, 0), (1, .6, .6))): chajja(bm, 2.5, 5)
    for sx in (-1, 1):
        with Xf(bm, M((sx*1.25, -.55, z2+.02), (0, 0, sx*pi/2), (1, .6, .6))): chajja(bm, 1.1, 2)
    with Xf(bm, M((0, -.5, z2+.1))):
        bangla_roof(bm, 1.5, .8, .62, .06, 12, 8)
        for x in (-.75, 0, .75): finial(bm, 1.3, (x, 0, .62*(1-.5*(x/1.5)**2)-.03))

def deco(bm, W, H, t, frames=()):
    f = -t/2
    boxb(bm, -W/2, W/2, f-.05, f+.01, 0, .22)
    boxb(bm, -W/2, W/2, f-.07, f+.01, H-.3, H); boxb(bm, -W/2, W/2, f-.04, f+.01, H-.62, H-.56)
    n = int(W/0.2)
    for k in range(n):
        x = -W/2 + W*(k+.5)/n
        boxb(bm, x-.05, x+.05, f-.045, f+.01, H-.52, H-.36)
    for (x0, x1, z0, z1) in frames:
        b = .06
        boxb(bm, x0, x1, f-.03, f+.01, z0, z0+b); boxb(bm, x0, x1, f-.03, f+.01, z1-b, z1)
        boxb(bm, x0, x0+b, f-.03, f+.01, z0+b, z1-b); boxb(bm, x1-b, x1, f-.03, f+.01, z0+b, z1-b)

def door(bm, w, h, ajar=0.0):
    for sx in (-1, 1):
        ang = ajar if sx > 0 else 0.0
        with Xf(bm, M((sx*w/2, 0, 0), (0, 0, -sx*ang)) @ M((-sx*w/4, 0, 0))):
            for k in range(4):
                x = -w/4 + (w/2)*(k+.5)/4
                boxb(bm, x-w/16+.004, x+w/16-.004, -.02, .02, 0, h)
            for z in (.25, h*.5, h-.3):
                boxb(bm, -w/4+.01, w/4-.01, -.045, -.02, z-.05, z+.05)

def door_studs(bm, w, h):
    for sx in (-1, 1):
        for z in (.25, h*.5, h-.3):
            for k in range(4):
                x = sx*w/4 - w/4 + (w/2)*(k+.5)/4
                lathe(bm, [(.022, 0), (.004, .03)], segs=6, loc=(0, 0, 0))
                bm.verts.ensure_lookup_table()
                bmesh.ops.transform(bm, matrix=M((x, -.045, z), (pi/2, 0, 0)), verts=bm.verts[-12:])
        with Xf(bm, M((sx*.06, -.05, h*.5-.18), (pi/2, 0, 0))):
            lathe(bm, [(.035, 0), (.045, .012), (.035, .024), (.025, .012), (.035, 0)], segs=10, cap=False)

# ---------------------------------------------------------------- kit registry
KIT = {}
def reg(name, parts):
    KIT[name] = parts

def build_kit(seed=7):
    rng = random.Random(seed)
    # 1 pillar
    bm = bmesh.new(); pillar(bm); reg('Pillar', [(finish('KIT_Pillar', bm, .012), 'sand')])
    # 2 scalloped arcade arch (bay 3.1, sits on pillar tops)
    bm = bmesh.new(); wall_opening(bm, 3.1, 2.56, 0, 0, 0, 1.12, 1.55, .45, foils=9, amp=.085, frame=False, n=5)
    boxb(bm, -1.55, 1.55, -.26, -.2, 1.42, 1.55)
    for sx in (-1, 1):
        lathe(bm, [(.16, 0), (.2, .02), (.12, .05), (.004, .07)], segs=12, loc=(0, 0, 0))
        bm.verts.ensure_lookup_table()
        bmesh.ops.transform(bm, matrix=M((sx*1.1, -.225, 1.15), (pi/2, 0, 0)), verts=bm.verts[-48:])
    reg('Arch', [(finish('KIT_Arch', bm, .012), 'sand')])
    # 3 jharokha
    bm = bmesh.new(); jharokha(bm); reg('Jharokha', [(finish('KIT_Jharokha', bm, .006), 'marble')])
    # 4-6 chhatris
    bm = bmesh.new(); chhatri(bm, 4, 1.7, 2.0); reg('Chhatri4', [(finish('KIT_Chhatri4', bm, .008), 'marble')])
    bm = bmesh.new(); chhatri(bm, 8, 1.75, 2.2, .1); reg('Chhatri8', [(finish('KIT_Chhatri8', bm, .008), 'marble')])
    bm = bmesh.new(); bangla_pavilion(bm); reg('Bangla', [(finish('KIT_Bangla', bm, .008), 'marble')])
    # 7 jali railing (+ broken variant)
    for nm, L in (('Railing', 3.1), ('RailingBroken', 1.7)):
        bm = bmesh.new()
        with Xf(bm, M((-1.55+.09, 0, .12))): jali(bm, L-.18, .68, .035, .085, .02)
        boxb(bm, -1.55, -1.55+L, -.07, .07, 0, .12); boxb(bm, -1.55, -1.55+L, -.09, .09, .8, .9)
        for x in ((-1.55, 1.55) if L > 3 else (-1.55,)):
            boxb(bm, x-.09, x+.09, -.09, .09, 0, 1.0); lathe(bm, cr([(.09, 0), (.12, .06), (.06, .14), (.02, .22)], 3), segs=10, loc=(x, 0, 1.0))
        reg(nm, [(finish('KIT_'+nm, bm, .005), 'marble')])
    # 8 slabs: plain, worn, chipped, cracked
    for v in range(4):
        bm = bmesh.new()
        if v < 3:
            boxb(bm, -.5, .5, -.5, .5, -.12, 0)
            top = [e for e in bm.edges]
            bmesh.ops.subdivide_edges(bm, edges=top, cuts=3, use_grid_fill=True)
            for vv in bm.verts:
                if vv.co.z > -.01:
                    vv.co.z += 0.006*noise.noise(Vector((vv.co.x*3+v*7, vv.co.y*3, v)))*(2 if v == 1 else 1)
            if v == 2:
                for vv in bm.verts:
                    d = (Vector((vv.co.x, vv.co.y)) - Vector((.5, .5))).length
                    if d < .28 and vv.co.z > -.01: vv.co.z -= .05*(1-d/.28)
        else:
            cut = [(-.5, rng.uniform(-.2, .1))] + [(-.5+k/5, rng.uniform(-.25, .25)) for k in range(1, 5)] + [(.5, rng.uniform(-.1, .2))]
            g = .012
            with Xf(bm, M((0, 0, -.06))):
                prism(bm, [(-.5, -.5), (.5, -.5)] + [(x, y-g) for x, y in cut[::-1]], .12, 'XY')
            with Xf(bm, M((0, 0, -.065), (.012, 0, 0))):
                prism(bm, [(x, y+g) for x, y in cut] + [(.5, .5), (-.5, .5)], .12, 'XY')
        reg('Slab%d' % v, [(finish('KIT_Slab%d' % v, bm, .012), 'floor')])
    # 9 steps
    bm = bmesh.new()
    boxb(bm, -1.55, 1.55, -.36, 0, 0, .3); boxb(bm, -1.6, 1.6, -.72, 0, 0, .15)
    reg('Steps', [(finish('KIT_Steps', bm, .015), 'sand2')])
    bm = bmesh.new(); boxb(bm, -.18, .18, -.8, 0, 0, .55); boxb(bm, -.21, .21, -.83, 0, .55, .62)
    reg('StepCheek', [(finish('KIT_StepCheek', bm, .015), 'sand2')])
    # 10-12 ivy (wall climb, hanging, pillar wrap)
    def ivy(kind, name):
        bs = bmesh.new(); bl = bmesh.new()
        def leaf(p, out, s):
            down = Vector((rng.uniform(-.7, .7), 0, -1)); down = (down - out*down.dot(out)).normalized()
            side = out.cross(down).normalized()
            vs = [p, p+down*.45*s+side*.42*s+out*.03, p+down*s-out*.12*s+out*.04, p+down*.45*s-side*.42*s+out*.03]
            bl.faces.new([bl.verts.new(v) for v in vs])
        def seg(a, b, r=.012):
            d = (b-a); 
            if d.length < 1e-5: return
            q = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
            bmesh.ops.create_cone(bs, cap_ends=False, segments=3, radius1=r, radius2=r, depth=d.length,
                                  matrix=Matrix.Translation((a+b)/2) @ q)
        n = {'wall': 9, 'hang': 12, 'pillar': 5}[kind]
        for sidx in range(n):
            if kind == 'wall':
                p = Vector((rng.uniform(-.9, .9), -.03, 0)); L = rng.uniform(2.5, 5.2); up = 1
            elif kind == 'hang':
                p = Vector((rng.uniform(-1.5, 1.5), -.05, 0)); L = rng.uniform(.8, 3.2); up = -1
            else:
                ang = rng.uniform(0, 6.28); zz = 0; L = rng.uniform(2.5, 4.2); up = 1
                p = Vector((.3*cos(ang), .3*sin(ang), 0))
            dirx = rng.uniform(-.25, .25); t = 0
            while t < L:
                if kind == 'pillar':
                    ang += rng.uniform(.1, .32); zz += rng.uniform(.03, .1)
                    rr = .24 + .06*sin(zz*5) + (.06 if zz/4 > .85 else 0)
                    q = Vector((rr*cos(ang), rr*sin(ang), zz)); out = Vector((cos(ang), sin(ang), 0)); t = zz
                else:
                    dirx = max(-.6, min(.6, dirx + rng.uniform(-.25, .25)))
                    q = p + Vector((dirx*.12, rng.uniform(-.015, .015), up*.11)); q.y = min(q.y, -.02)
                    if kind == 'hang': q.y = -.05 - .1*min(t, 1.0) + rng.uniform(-.03, .03)
                    out = Vector((0, -1, 0)); t += .12
                seg(p, q); p = q
                dens = 1.0 if kind != 'wall' else (1.2 - .5*t/L)
                for _ in range(2 if rng.random() < dens*.8 else 1):
                    o = (out + Vector((rng.uniform(-.5, .5), rng.uniform(-.2, .2), rng.uniform(-.2, .4)))).normalized()
                    leaf(p + Vector((rng.uniform(-.1, .1), 0, rng.uniform(-.06, .06))) + out*rng.uniform(.01, .07), o, rng.uniform(.09, .17))
        reg(name, [(finish('KIT_'+name+'_leaf', bl, 0), 'ivy'), (finish('KIT_'+name+'_stem', bs, 0), 'stem')])
    ivy('wall', 'IvyWall'); ivy('wall', 'IvyWall2'); ivy('hang', 'IvyHang'); ivy('pillar', 'IvyPillar')
    # 13 moss patches, 14 rocks
    for v in range(3):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        for vv in bm.verts:
            c = vv.co.copy(); r = 1 + .45*noise.noise(c*1.3 + Vector((v*9, 0, 0)))
            bump = .5 + .5*noise.noise(c*7 + Vector((0, v*5, 0)))
            vv.co = Vector((c.x*r, c.y*r, max(c.z, -.02)*(.07 + .09*bump)))
        reg('Moss%d' % v, [(finish('KIT_Moss%d' % v, bm, 0, smooth=80), 'moss')])
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        for vv in bm.verts:
            c = vv.co.copy()
            vv.co = c*(1 + .35*noise.noise(c*1.1 + Vector((v*4, 3, 1)))) * Vector((1, .8, .6)) + Vector((0, 0, .45))
        reg('Rock%d' % v, [(finish('KIT_Rock%d' % v, bm, 0, smooth=50), 'rock')])
    # 15 debris block + pillar stump
    bm = bmesh.new(); boxb(bm, -.35, .35, -.2, .2, 0, .3)
    for vv in bm.verts:
        if vv.co.x > 0 and vv.co.z > .1: vv.co += Vector((-.12, rng.uniform(-.05, .05), -.1))
    reg('Block', [(finish('KIT_Block', bm, .02), 'sand')])
    bm = bmesh.new(); pillar(bm)
    for v in bm.verts:
        lim = 1.3 + .5*v.co.x + .12*noise.noise(Vector((v.co.x*9, v.co.y*9, 0)))
        if v.co.z > lim: v.co.z = lim
    with Xf(bm, M((1.1, .3, .19), (pi/2, 0, .5))): lathe(bm, [(.17, 0), (.16, .9)], segs=16, mod=lambda a, z: 1-.08*(.5+.5*cos(8*a)))
    reg('Stump', [(finish('KIT_Stump', bm, .008, weld=1e-4), 'sand')])
    # 16 lantern (frame + glass)
    bm = bmesh.new()
    boxb(bm, -.11, .11, -.11, .11, 0, .03)
    for sx in (-1, 1):
        for sy in (-1, 1): boxb(bm, sx*.09-.01, sx*.09+.01, sy*.09-.01, sy*.09+.01, .03, .3)
    boxb(bm, -.11, .11, -.11, .11, .3, .32)
    lathe(bm, [(.16, .32), (.05, .42), (.05, .45), (.02, .47)], segs=4, phase=pi/4)
    lathe(bm, [(.06, .5), (.07, .5), (.07, .51), (.06, .51), (.06, .5)], segs=12, cap=False)
    with Xf(bm, M((0, 0, .5), (pi/2, 0, 0))): pass
    frame = finish('KIT_Lantern_frame', bm, .003)
    bm = bmesh.new(); boxb(bm, -.085, .085, -.085, .085, .035, .295)
    reg('Lantern', [(frame, 'brass'), (finish('KIT_Lantern_glass', bm, 0), 'glow')])
    # 17 pots: intact, broken, urn
    POT = [(.12, 0), (.2, .05), (.3, .2), (.33, .36), (.28, .52), (.16, .62), (.13, .68), (.17, .73), (.18, .75), (.15, .75), (.11, .68)]
    bm = bmesh.new(); lathe(bm, cr(POT, 3), segs=20); reg('Pot', [(finish('KIT_Pot', bm, 0, smooth=60), 'terracotta')])
    bm = bmesh.new(); lathe(bm, cr(POT, 3), segs=20, cap=False)
    kill = [f for f in bm.faces if f.calc_center_median().z > .28 + .14*sin(3*math.atan2(f.calc_center_median().y, f.calc_center_median().x)) ]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    for k in range(6):
        a = rng.uniform(0, 6.28); d = rng.uniform(.4, .8)
        with Xf(bm, M((d*cos(a), d*sin(a), .01), (rng.uniform(-.2, .2), rng.uniform(-.2, .2), a))):
            prism(bm, [(0, 0), (rng.uniform(.08, .16), .02), (.1, rng.uniform(.08, .15)), (.02, .1)], .012, 'XY')
    reg('PotBroken', [(finish('KIT_PotBroken', bm, 0, smooth=60), 'terracotta')])
    URN = [(.28, 0), (.3, .06), (.2, .12), (.18, .2), (.34, .36), (.46, .6), (.44, .82), (.3, .95), (.27, 1.02), (.36, 1.08), (.38, 1.12), (.3, 1.12), (.22, 1.0)]
    bm = bmesh.new(); lathe(bm, cr(URN, 3), segs=24, mod=lambda a, z: 1+.03*abs(cos(6*a)) if .3 < z < .9 else 1)
    reg('Urn', [(finish('KIT_Urn', bm, 0, smooth=60), 'marble')])
    # 18-21 wall modules (ground 5.55 high: door / niche / plain; upper 4.5: window / jharokha door; top 3.25)
    T = .5
    bm = bmesh.new(); wall_opening(bm, 3.1, 1.3, 0, 0, 1.7, .42, 5.55, T, foils=5, amp=.05)
    deco(bm, 3.1, 5.55, T, [(-.9, .9, 2.9, 4.7)])
    with Xf(bm, M((-.4, -T/2-.01, 3.3))): jali(bm, .8, 1.0, .03, .08, .02)
    reg('WallDoor', [(finish('KIT_WallDoor', bm, .012), 'sand')])
    bm = bmesh.new(); wall_opening(bm, 3.1, .8, 0, 1.15, 1.85, .34, 5.55, T, foils=5, amp=.04)
    boxb(bm, -.5, .5, .05, .2, 1.1, 2.5); boxb(bm, -.6, .6, -T/2-.1, -T/2+.02, 1.07, 1.15)
    deco(bm, 3.1, 5.55, T, [(-1.2, 1.2, 2.9, 4.7), (-1.0, 1.0, 3.1, 4.5)])
    reg('WallNiche', [(finish('KIT_WallNiche', bm, .012), 'sand')])
    bm = bmesh.new(); boxb(bm, -1.55, 1.55, -T/2, T/2, 0, 5.55)
    deco(bm, 3.1, 5.55, T, [(-1.2, 1.2, .5, 2.5), (-1.0, 1.0, .7, 2.3), (-1.2, 1.2, 2.9, 4.7)])
    lathe(bm, cr([(.5, 0), (.48, .03), (.3, .05), (.25, .09), (.1, .1), (.004, .12)], 2), segs=16, mod=lambda a, z: 1+.12*abs(cos(4*a)))
    bm.verts.ensure_lookup_table()
    reg('WallPlain', [(finish('KIT_WallPlain', bm, .012), 'sand')])
    bm = bmesh.new(); wall_opening(bm, 3.1, 1.1, 0, 1.0, 2.35, .5, 4.5, T, foils=5, amp=.05)
    deco(bm, 3.1, 4.5, T, []); boxb(bm, -.75, .75, -T/2-.12, -T/2+.02, .92, 1.0)
    reg('WallWin', [(finish('KIT_WallWin', bm, .012), 'sand')])
    bm = bmesh.new(); wall_opening(bm, 3.1, 1.5, 0, 1.05, 2.5, .5, 4.5, T, foils=7, amp=.05, frame=False)
    deco(bm, 3.1, 4.5, T, [])
    reg('WallJh', [(finish('KIT_WallJh', bm, .012), 'sand')])
    bm = bmesh.new(); wall_opening(bm, 3.1, 1.6, 0, .6, 1.5, .6, 3.25, T, foils=7, amp=.05)
    deco(bm, 3.1, 3.25, T, [])
    reg('WallTop', [(finish('KIT_WallTop', bm, .012), 'sand')])
    # 22 window jali fill, 23 door leaves (+ajar) with brass studs
    bm = bmesh.new()
    with Xf(bm, M((-1.0, 0, 0))): jali(bm, 2.0, 2.0, .04, .075, .02)
    reg('WinJali', [(finish('KIT_WinJali', bm, .004), 'marble')])
    for nm, aj in (('Door', 0.0), ('DoorAjar', .5)):
        bm = bmesh.new(); door(bm, 1.5, 2.25, aj); wood = finish('KIT_%s_wood' % nm, bm, .006)
        bm = bmesh.new(); door_studs(bm, 1.5, 2.25)
        reg(nm, [(wood, 'wood'), (finish('KIT_%s_studs' % nm, bm, 0), 'brass')] if aj == 0 else [(wood, 'wood')])
    # 24 chajja, 25 bracket, 26 kangura parapet
    bm = bmesh.new(); chajja(bm, 3.1, 4); reg('Chajja', [(finish('KIT_Chajja', bm, .01), 'sand2')])
    bm = bmesh.new(); prism(bm, BRACKET, .16, 'YZ'); reg('Bracket', [(finish('KIT_Bracket', bm, .012), 'sand')])
    bm = bmesh.new(); boxb(bm, -1.55, 1.55, -.14, .14, 0, .4); boxb(bm, -1.55, 1.55, -.17, .17, .4, .47)
    for k in range(6):
        x = -1.55 + 3.1*(k+.5)/6
        with Xf(bm, M((x, 0, .47))):
            prism(bm, [(-.2, 0), (.2, 0), (.22, .18), (.14, .36), (0, .52), (-.14, .36), (-.22, .18)], .2, 'XZ')
    reg('Parapet', [(finish('KIT_Parapet', bm, .012), 'sand')])
    # 27 corner tower shaft, 28 pedestal (tulsi chaura), 29 dry leaf, 30 lamp post
    bm = bmesh.new()
    lathe(bm, [(2.4, 0), (2.4, .6), (2.2, .75), (2.2, 6.0), (2.32, 6.1), (2.32, 6.35), (2.2, 6.45), (2.2, 10.6),
               (2.32, 10.7), (2.32, 10.95), (2.2, 11.05), (2.2, 11.6), (2.75, 12.1), (2.8, 12.2), (2.8, 12.4)], segs=8, phase=pi/8)
    for i in range(8):
        a = pi/8 + 2*pi*(i+.5)/8; d = 2.2*cos(pi/8)
        for z0 in (7.2,):
            with Xf(bm, M((d*cos(a), d*sin(a), z0), (0, 0, a+pi/2))):
                wall_opening(bm, 1.6, .8, 0, .3, 1.5, .4, 2.8, .12, foils=5, amp=.04)
                boxb(bm, -.5, .5, .0, .05, .3, 2.4)
        with Xf(bm, M((d*cos(a)*1.0, d*sin(a)*1.0, 12.1), (0, 0, a+pi/2), (1, .6, .6))):
            for x in (-.5, .5):
                with Xf(bm, M((x, 0, 0))): prism(bm, BRACKET, .14, 'YZ')
    reg('Tower', [(finish('KIT_Tower', bm, .015), 'sand')])
    bm = bmesh.new()
    lathe(bm, cr([(1.0, 0), (1.0, .15), (.85, .18), (.85, .3), (.62, .36), (.55, .5), (.55, .95), (.7, 1.05), (.74, 1.1), (.74, 1.2), (.5, 1.2)], 2),
          segs=8, phase=pi/8)
    for i in range(8):
        a = 2*pi*i/8; d = .55*cos(pi/8)
        with Xf(bm, M((d*cos(a), d*sin(a), .42), (0, 0, a+pi/2))):
            wall_opening(bm, .4, .22, 0, 0, .22, .1, .5, .04, foils=3, amp=.012, frame=False, n=4)
    reg('Pedestal', [(finish('KIT_Pedestal', bm, .008), 'marble')])
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((0, 0, 0), (.035, .04, .012), (0, .1, 0), (-.035, .04, .012))]
    bm.faces.new(vs); reg('Leaf', [(finish('KIT_Leaf', bm, 0), 'dryleaf')])
    bm = bmesh.new(); pillar(bm, h=1.7, r=.1, segs=16, flutes=8)
    reg('LampPost', [(finish('KIT_LampPost', bm, .006), 'sand2')])
    return KIT
