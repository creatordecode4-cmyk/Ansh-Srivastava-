"""Original character 'Surya Warden' (tall gaunt guardian, conical straw hat, sun-disc belt, bronze armour)
built procedurally (numpy SDF -> marching cubes), rigged and given a baked procedural walk around the pedestal.
Usage: python3 character.py   -> _work/palace_char.blend   (needs _work/palace.blend from build.py)"""
import bpy, bmesh, os, sys, math, random, time
import numpy as np
from math import sin, cos, pi, radians, atan2, sqrt
from mathutils import Matrix, Vector, Euler
from skimage import measure
import scipy.sparse as sp
HERE = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
def V(*a): return np.array(a, np.float64)
def nrm(v): return v/np.linalg.norm(v)
def eul(r): return np.array(Euler([radians(x) for x in r], 'XYZ').to_matrix())
SX = np.diag([-1.0, 1.0, 1.0])
def mir_w(w):
    sw = lambda n: n[:-2]+'.R' if n.endswith('.L') else n
    return sw(w) if isinstance(w, str) else {sw(k): v for k, v in w.items()}

# ------------------------------------------------------------------ SDF field
class Field:
    def __init__(s, lo=(-.78, -.46, -.03), hi=(.78, .46, 2.12), h=.005):
        s.lo = np.array(lo, np.float64); s.h = h
        s.n = (np.ceil((np.array(hi)-s.lo)/h).astype(int)+1)
        s.ax = [(s.lo[i]+h*np.arange(s.n[i])).astype(np.float32) for i in range(3)]
        s.f = np.full(s.n, 1.0, np.float32); s.lab = np.zeros(s.n, np.int16); s.prims = []
    def _put(s, bmin, bmax, fn, k, w):
        pad = k+3*s.h
        i0 = np.maximum(0, np.floor((np.array(bmin)-pad-s.lo)/s.h).astype(int))
        i1 = np.minimum(s.n, np.ceil((np.array(bmax)+pad-s.lo)/s.h).astype(int)+1)
        if (i1 <= i0).any(): return
        sl = tuple(slice(a, b) for a, b in zip(i0, i1))
        X = s.ax[0][sl[0]][:, None, None]; Y = s.ax[1][sl[1]][None, :, None]; Z = s.ax[2][sl[2]][None, None, :]
        d = np.minimum(fn(X, Y, Z), 1.0).astype(np.float32); a = s.f[sl]
        s.lab[sl] = np.where(d < a, len(s.prims), s.lab[sl]); s.prims.append(w)
        if k > 0:
            hh = np.clip(.5+.5*(d-a)/k, 0, 1); s.f[sl] = d*(1-hh)+a*hh-k*hh*(1-hh)
        else: s.f[sl] = np.minimum(a, d)
    def ell(s, w, c, r, rot=(0, 0, 0), k=.02, sym=False):
        R = eul(rot) if not isinstance(rot, np.ndarray) else rot
        for side in ((1, -1) if sym else (1,)):
            cc = V(*c)*(V(side, 1, 1)); RR = R if side == 1 else SX@R@SX; ww = w if side == 1 else mir_w(w)
            rr = V(*r); rmin = rr.min()
            def fn(X, Y, Z, cc=cc, RR=RR, rr=rr, rmin=rmin):
                px, py, pz = X-cc[0], Y-cc[1], Z-cc[2]
                l = [RR[0, i]*px+RR[1, i]*py+RR[2, i]*pz for i in range(3)]
                k0 = np.sqrt(sum((l[i]/rr[i])**2 for i in range(3))); k1 = np.sqrt(sum((l[i]/rr[i]**2)**2 for i in range(3)))
                return np.where(k0 < .02, -rmin, k0*(k0-1)/np.maximum(k1, 1e-6))
            s._put(cc-rr.max(), cc+rr.max(), fn, k, ww)
    def cap(s, w, a, b, ra, rb=None, k=.02, sym=False):
        rb = ra if rb is None else rb
        for side in ((1, -1) if sym else (1,)):
            A = V(*a)*V(side, 1, 1); B = V(*b)*V(side, 1, 1); ww = w if side == 1 else mir_w(w); ba = B-A; l2 = max(ba@ba, 1e-12)
            def fn(X, Y, Z, A=A, ba=ba, l2=l2):
                px, py, pz = X-A[0], Y-A[1], Z-A[2]
                t = np.clip((px*ba[0]+py*ba[1]+pz*ba[2])/l2, 0, 1)
                return np.sqrt((px-ba[0]*t)**2+(py-ba[1]*t)**2+(pz-ba[2]*t)**2)-(ra+(rb-ra)*t)
            rm = max(ra, rb); s._put(np.minimum(A, B)-rm, np.maximum(A, B)+rm, fn, k, ww)
    def box(s, w, c, half, rot=(0, 0, 0), rnd=.006, k=0.0, sym=False):
        R = eul(rot) if not isinstance(rot, np.ndarray) else rot
        for side in ((1, -1) if sym else (1,)):
            cc = V(*c)*V(side, 1, 1); RR = R if side == 1 else SX@R@SX; ww = w if side == 1 else mir_w(w); hf = V(*half)-rnd
            def fn(X, Y, Z, cc=cc, RR=RR, hf=hf):
                px, py, pz = X-cc[0], Y-cc[1], Z-cc[2]
                q = [np.abs(RR[0, i]*px+RR[1, i]*py+RR[2, i]*pz)-hf[i] for i in range(3)]
                return np.sqrt(sum(np.maximum(x, 0)**2 for x in q))+np.minimum(np.maximum(np.maximum(q[0], q[1]), q[2]), 0)-rnd
            e = np.linalg.norm(half); s._put(cc-e, cc+e, fn, k, ww)
    def spike(s, w, base, d, bend, length, r0, n=5, k=.004, sym=False, curve=50):
        p = V(*base); d = nrm(V(*d)); bend = nrm(V(*bend))
        for i in range(n):
            a = radians(curve)*i/n; di = nrm(cos(a)*d+sin(a)*bend); q = p+di*length/n
            s.cap(w, p, q, r0*(1-i/n)+.0015, r0*(1-(i+1)/n)+.0015, k=k, sym=sym); p = q
    def mesh(s):
        v, f = measure.marching_cubes(s.f, 0.0, spacing=(s.h,)*3)[:2]
        idx = np.clip(np.rint(v/s.h).astype(int), 0, s.n-1); lab = s.lab[idx[:, 0], idx[:, 1], idx[:, 2]]
        v = v+s.lo
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        if np.einsum('ij,ij->i', a, np.cross(b, c)).sum() < 0: f = f[:, ::-1]
        return v, np.ascontiguousarray(f), lab

# ------------------------------------------------------------------ skeleton (rest pose, facing -Y, left = +X)
S_, E_, W_ = V(.25, 0, 1.72), V(.402, 0, 1.394), V(.512, -.05, 1.088)
H_, K_, A_ = V(.115, 0, 1.12), V(.125, -.01, .58), V(.125, .02, .09)
BALL, TOE = V(.125, -.15, .02), V(.125, -.27, .02)
DF = nrm(W_-E_); NIN = V(-1, 0, 0); NIN = nrm(NIN-DF*(NIN@DF)); WV = nrm(np.cross(DF, NIN)); HANDT = W_+DF*.20
BONES = [  # name, head, tail, parent
    ('hips', (0, 0, 1.12), (0, 0, 1.28), None), ('spine', (0, 0, 1.28), (0, .01, 1.50), 'hips'), ('chest', (0, .01, 1.50), (0, 0, 1.76), 'spine'),
    ('neck', (0, 0, 1.76), (0, -.012, 1.87), 'chest'), ('head', (0, -.012, 1.87), (0, -.012, 2.06), 'neck'),
    ('tabF1', (0, -.135, 1.17), (0, -.14, .93), 'hips'), ('tabF2', (0, -.14, .93), (0, -.14, .69), 'tabF1'), ('tabF3', (0, -.14, .69), (0, -.14, .45), 'tabF2'),
    ('tabB1', (0, .145, 1.17), (0, .15, .93), 'hips'), ('tabB2', (0, .15, .93), (0, .15, .69), 'tabB1'), ('tabB3', (0, .15, .69), (0, .15, .45), 'tabB2')]
for sd, sfx in ((1, '.L'), (-1, '.R')):
    m = lambda p: tuple(V(*p)*V(sd, 1, 1))
    BONES += [('upper_arm'+sfx, m(S_), m(E_), 'chest'), ('forearm'+sfx, m(E_), m(W_), 'upper_arm'+sfx), ('hand'+sfx, m(W_), m(HANDT), 'forearm'+sfx),
              ('thigh'+sfx, m(H_), m(K_), 'hips'), ('shin'+sfx, m(K_), m(A_), 'thigh'+sfx), ('foot'+sfx, m(A_), m(BALL), 'shin'+sfx), ('toe'+sfx, m(BALL), m(TOE), 'foot'+sfx)]
PARENT = {b[0]: b[3] for b in BONES}

# ------------------------------------------------------------------ body sculpt
def build_skin():
    F = Field(); e, c = F.ell, F.cap
    e('hips', (0, .01, 1.13), (.17, .118, .12)); e('spine', (0, -.005, 1.27), (.14, .098, .13), k=.05); e('spine', (0, -.01, 1.40), (.152, .104, .13), k=.05)
    e('chest', (0, 0, 1.55), (.20, .135, .18), k=.05); e('chest', (0, .005, 1.67), (.235, .125, .11), k=.05)
    e('chest', (.10, -.095, 1.635), (.11, .05, .078), rot=(-8, 0, 8), k=.025, sym=True)                    # pecs
    for i, (z, y) in enumerate(((1.50, -.116), (1.435, -.108), (1.37, -.101), (1.305, -.092))):            # abs
        e('spine', (.043, y+.006, z), (.038, .02, .029), k=.016, sym=True)
    e('spine', (.13, -.035, 1.36), (.034, .06, .10), k=.03, sym=True)                                      # obliques
    for i in range(3): e('chest', (.166, -.06+.022*i, 1.50-.045*i), (.03, .035, .019), rot=(0, 0, 25), k=.02, sym=True)   # serratus
    e('chest', (.165, .03, 1.53), (.055, .06, .15), k=.05, sym=True)                                          # lats
    c('chest', (.04, .03, 1.80), (.21, .02, 1.735), .05, .042, k=.03, sym=True)                             # traps
    c('chest', (.03, -.075, 1.735), (.21, -.04, 1.752), .017, .015, k=.014, sym=True)                       # clavicle
    for i in range(10):                                                                                     # spine ridge
        z = 1.22+.06*i; e('hips' if z < 1.28 else 'spine' if z < 1.5 else 'chest', (0, .105+.03*sin((z-1.2)*2.6), z), (.02, .03, .027), k=.012)
    e('chest', (.11, .085, 1.64), (.07, .035, .085), rot=(0, 0, -15), k=.04, sym=True)
    for i in range(4): c('chest', (.05, -.12+.004*i, 1.545-.035*i), (.175, -.04, 1.50-.04*i), .011, .009, k=.012, sym=True)   # ribs                         # shoulder blades
    c('neck', (0, 0, 1.76), (0, -.015, 1.88), .058, .05, k=.03)
    c('neck', (.045, -.03, 1.77), (.03, -.02, 1.87), .016, .014, k=.012, sym=True)                          # neck tendons
    e('head', (0, -.02, 1.945), (.093, .112, .122), k=.03); e('head', (0, -.065, 1.885), (.06, .06, .055), k=.02)
    e('head', (0, -.105, 1.967), (.07, .03, .022), k=.012); e('head', (.055, -.085, 1.925), (.03, .03, .025), k=.012, sym=True)
    # arm
    e('upper_arm.L', (.27, 0, 1.70), (.082, .085, .10), rot=(0, -25, 0), k=.04, sym=True)
    c('upper_arm.L', (.27, 0, 1.68), E_, .06, .048, k=.04, sym=True)
    e('upper_arm.L', (.33, -.028, 1.55), (.044, .045, .10), rot=(0, -25, 0), k=.018, sym=True)
    e('upper_arm.L', (.335, .032, 1.56), (.042, .04, .11), rot=(0, -25, 0), k=.018, sym=True)
    e('forearm.L', E_, (.047, .047, .047), k=.02, sym=True); c('forearm.L', E_, W_, .05, .033, k=.025, sym=True)
    e('forearm.L', E_+.3*(W_-E_)+V(.012, -.005, 0), (.05, .045, .10), rot=(0, -20, 0), k=.018, sym=True)
    RP = np.stack([NIN, WV, DF], 1)
    e('hand.L', W_+DF*.065, (.024, .052, .065), rot=RP, k=.02, sym=True)
    tips = []
    def finger(base, lens, a0, da, r, dirfn):
        p = base; a = a0
        for i, L in enumerate(lens):
            d = dirfn(radians(a)); q = p+d*L; c('hand.L', p, q, r*(1-.12*i), r*(1-.12*(i+1)), k=.008, sym=True); p = q; a += da
        tips.append((p, dirfn(radians(a-da+12))))
    for j, (o, sc) in enumerate(((-.038, 1.0), (-.013, 1.1), (.012, 1.05), (.036, .85))):
        finger(W_+DF*.12+WV*o, (.05*sc, .038*sc, .03*sc), 16+3*j, 25, .0135, lambda a: cos(a)*DF+sin(a)*NIN)
    dth = nrm(DF*.6-WV*.6+NIN*.45)
    finger(W_+DF*.045-WV*.042, (.045, .036), 0, 0, .015, lambda a: dth)
    # leg
    e('hips', (.09, .06, 1.10), (.09, .078, .098), k=.05, sym=True)
    c('thigh.L', H_, K_, .098, .064, k=.04, sym=True); e('thigh.L', (.13, -.05, .88), (.074, .068, .20), k=.03, sym=True)
    e('thigh.L', (.12, .045, .86), (.066, .06, .18), k=.03, sym=True)
    e('shin.L', (.125, -.03, .585), (.05, .05, .055), k=.018, sym=True); c('shin.L', K_, A_, .058, .04, k=.03, sym=True)
    e('shin.L', (.125, .05, .42), (.056, .06, .13), k=.03, sym=True)
    e('foot.L', A_, (.04, .045, .04), k=.02, sym=True); e('foot.L', (.125, -.065, .04), (.05, .10, .04), k=.02, sym=True)
    e('foot.L', (.125, .045, .035), (.04, .045, .035), k=.02, sym=True)
    for i in range(3): e('toe.L', (.093+.032*i, -.185, .022), (.017, .05, .021), k=.01, sym=True)
    return F, tips

def build_rigid(tips):
    out = {}
    PA = {'chest': .55, 'upper_arm.L': .45}
    # --- bronze
    F = Field()
    F.ell('hips', (0, -.128, 1.205), (.062, .02, .062), k=0)                                              # sun-disc buckle
    F.ell('hips', (0, -.146, 1.205), (.03, .012, .03), k=.004)
    for i in range(12):
        a = 2*pi*i/12; d = V(cos(a), 0, sin(a)); L = .105 if i % 2 == 0 else .085
        F.cap('hips', V(0, -.13, 1.205)+d*.05, V(0, -.128, 1.205)+d*L, .013, .003, k=.003)
    for i, (cc, rr, ry) in enumerate((((.268, 0, 1.775), (.118, .112, .05), 24), ((.322, 0, 1.722), (.095, .105, .042), 50), ((.362, 0, 1.655), (.075, .095, .04), 66))):
        F.ell(PA, cc, rr, rot=(0, ry, 0), k=.003, sym=True)                                               # layered pauldron
    for z0 in (1.085, .985, .885):                                                                        # side tassets
        F.box('hips', (.218-(1.085-z0)*.02, .005, z0), (.013, .085-(1.085-z0)*.06, .066), rot=(0, -6, 0), rnd=.009, sym=True)
        for yy in (-.045, .045): F.ell('hips', (.232-(1.085-z0)*.02, yy*(1-(1.085-z0)), z0+.035), (.009, .009, .009), k=.002, sym=True)
    F.ell('shin.L', (.125, -.034, .36), (.05, .034, .17), k=.004, sym=True); F.ell('shin.L', (.125, -.058, .585), (.046, .03, .05), k=.004, sym=True)   # greave + knee cop
    F.ell('shin.L', (.125, -.08, .585), (.014, .012, .014), k=.003, sym=True)
    for t in (.3, .86): p = E_+t*(W_-E_); F.cap('forearm.L', p-DF*.012, p+DF*.012, .061-.014*t, k=.003, sym=True)   # bracer rings
    F.ell('chest', (0, -.012, 1.772), (.125, .105, .03), k=0); F.ell('chest', (0, -.118, 1.74), (.035, .014, .035), k=.004)  # gorget + boss
    out['bronze'] = F.mesh() + (F.prims,)
    # --- leather
    F = Field()
    F.ell('hips', (0, .003, 1.205), (.174, .13, .043), k=0)                                               # belt
    F.cap('forearm.L', E_+.25*(W_-E_), E_+.9*(W_-E_), .057, .044, k=0, sym=True)                          # bracer
    F.ell('hips', (.20, .005, 1.14), (.03, .095, .05), k=.004, sym=True)                                  # tasset hanger
    out['leather'] = F.mesh() + (F.prims,)
    # --- horn / bone
    F = Field()
    for (yy, L, tilt) in ((-.055, .15, -.25), (0, .23, 0), (.058, .17, .3)):                              # pauldron spikes
        F.spike(PA, (.29, yy, 1.805), (.35, tilt, .9), (.9, tilt, -.2), L, .022, sym=True)
    for t, L in ((.32, .15), (.55, .12), (.75, .09)):                                                     # forearm fins
        p = E_+t*(W_-E_)+V(.03, .03, 0); F.spike('forearm.L', p, (.55, .45, .7), (0, .2, 1), L, .017, sym=True, curve=35)
    for (p, d) in tips: F.cap('hand.L', p-d*.006, p+d*.05, .0095, .0015, k=.003, sym=True)                # claws
    for i in range(3): F.cap('toe.L', (.093+.032*i, -.222, .024), (.093+.032*i, -.285, .008), .013, .002, k=.003, sym=True)
    F.ell('head', (0, -.108, 1.915), (.066, .036, .075), k=0)                                             # mask
    F.ell('head', (0, -.14, 1.90), (.016, .02, .05), k=.01); F.ell('head', (0, -.118, 1.975), (.07, .022, .016), k=.006)
    out['horn'] = F.mesh() + (F.prims,)
    # --- cloth wraps
    F = Field()
    F.ell({'neck': .5, 'chest': .5}, (0, .0, 1.815), (.10, .098, .05), k=0); F.ell('chest', (.06, -.07, 1.79), (.06, .04, .045), rot=(0, 0, 20), k=.02)
    for z in (.115, .15, .185, .22): F.cap('shin.L', (.125, .02, z), (.125, .019, z+.02), .043+.02*(z-.1), k=.006, sym=True)
    for t in (.93, .99): p = E_+t*(W_-E_); F.cap('forearm.L', p, p+DF*.014, .04-.006*(t-.9)*10, k=.006, sym=True)
    out['cloth'] = F.mesh() + (F.prims,)
    # --- eyes
    F = Field(lo=(-.1, -.16, 1.9), hi=(.1, -.08, 2.0), h=.0025)
    F.ell('head', (.03, -.134, 1.945), (.013, .008, .006), rot=(0, -12, 0), k=0, sym=True)
    out['eye'] = F.mesh() + (F.prims,)
    return out

# ------------------------------------------------------------------ skin weights
WSEG = {'hips': ((-.09, .02, 1.12), (.09, .02, 1.12), .11), 'spine': ((0, 0, 1.25), (0, 0, 1.43), .11), 'chest': ((-.08, 0, 1.61), (.08, 0, 1.61), .14),
        'neck': ((0, 0, 1.79), (0, -.015, 1.87), .05), 'head': ((0, -.02, 1.92), (0, -.02, 1.98), .09)}
for sd, sfx in ((1, '.L'), (-1, '.R')):
    m = lambda p: tuple(V(*p)*V(sd, 1, 1))
    WSEG.update({'upper_arm'+sfx: (m(S_), m(E_), .05), 'forearm'+sfx: (m(E_), m(W_), .04), 'hand'+sfx: (m(W_), m(HANDT), .03),
                 'thigh'+sfx: (m(H_), m(K_), .07), 'shin'+sfx: (m(K_), m(A_), .045), 'foot'+sfx: (m(A_), m(BALL), .035), 'toe'+sfx: (m(BALL), m(TOE), .02)})
def skin_weights(v, f, lab, prims):
    names = list(WSEG); nb = len(names); ix = {n: i for i, n in enumerate(names)}
    adj = np.eye(nb, dtype=bool)
    for n in names:
        p = PARENT[n]
        if p in ix: adj[ix[n], ix[p]] = adj[ix[p], ix[n]] = True
    D = np.empty((len(v), nb), np.float32)
    for n, (a, b, r) in WSEG.items():
        a = V(*a); b = V(*b); ba = b-a; t = np.clip(((v-a)@ba)/(ba@ba), 0, 1)
        D[:, ix[n]] = np.maximum(np.linalg.norm(v-a-np.outer(t, ba), axis=1)-r, 0)
    prim = np.array([ix[p] for p in prims])[lab]
    Wt = adj[prim]/(D+.015)**4; Wt /= Wt.sum(1, keepdims=True)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); n = len(v)
    A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr(); A = A+A.T
    A = sp.diags(1/np.maximum(A.sum(1).A1, 1))@A
    for _ in range(10): Wt = .5*Wt+.5*(A@Wt)
    Wt[Wt < .02] = 0; Wt /= Wt.sum(1, keepdims=True)
    return names, Wt

# ------------------------------------------------------------------ blender objects
def make_mesh(name, v, f, smooth=True):
    me = bpy.data.meshes.new(name); me.vertices.add(len(v)); me.vertices.foreach_set('co', v.astype(np.float32).ravel())
    me.loops.add(len(f)*3); me.polygons.add(len(f))
    me.polygons.foreach_set('loop_start', np.arange(0, len(f)*3, 3)); me.polygons.foreach_set('loop_total', np.full(len(f), 3))
    me.loops.foreach_set('vertex_index', f.ravel().astype(np.int32)); me.update(calc_edges=True); me.validate()
    me.polygons.foreach_set('use_smooth', np.full(len(me.polygons), smooth)); return me
def add_object(name, me, arm, mat, col):
    ob = bpy.data.objects.new(name, me); col.objects.link(ob); ob['mat'] = 'char'; me.materials.append(mat)
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm; ob.parent = arm; return ob
def set_groups(ob, names, Wt):
    for j, n in enumerate(names):
        col = Wt[:, j]; idx = np.nonzero(col > 0)[0]
        if not len(idx): continue
        vg = ob.vertex_groups.new(name=n)
        full = idx[col[idx] > .999]
        if len(full): vg.add(full.tolist(), 1.0, 'REPLACE')
        for i in idx[col[idx] <= .999]: vg.add([int(i)], float(col[i]), 'REPLACE')
def rigid_groups(ob, lab, prims):
    names = sorted({n for p in prims for n in ([p] if isinstance(p, str) else p)}); ix = {n: i for i, n in enumerate(names)}
    P = np.zeros((len(prims), len(names)), np.float32)
    for i, p in enumerate(prims):
        for n, w in ({p: 1.0} if isinstance(p, str) else p).items(): P[i, ix[n]] = w
    set_groups(ob, names, P[lab])

# ------------------------------------------------------------------ materials (Generated coords -> stable under deformation)
def cmat(name, col, col2, rough, metallic=0.0, bump=.0, bscale=60, emit=None, dims=(1.1, .6, 2.1), patina=None, stripes=0):
    m = bpy.data.materials.new('CHR_'+name); m.use_nodes = True; nt = m.node_tree; N = nt.nodes.new; L = nt.links.new
    b = nt.nodes['Principled BSDF']; tc = N('ShaderNodeTexCoord'); mp = N('ShaderNodeMapping'); mp.inputs['Scale'].default_value = dims; L(tc.outputs['Generated'], mp.inputs['Vector'])
    n1 = N('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 9; n1.inputs['Detail'].default_value = 5; L(mp.outputs[0], n1.inputs['Vector'])
    mx = N('ShaderNodeMixRGB'); mx.inputs[1].default_value = (*col, 1); mx.inputs[2].default_value = (*col2, 1)
    rp = N('ShaderNodeValToRGB'); rp.color_ramp.elements[0].position = .35; rp.color_ramp.elements[1].position = .7; L(n1.outputs['Fac'], rp.inputs[0]); L(rp.outputs[0], mx.inputs[0])
    last = mx.outputs[0]
    if patina:
        n3 = N('ShaderNodeTexNoise'); n3.inputs['Scale'].default_value = 22; n3.inputs['Detail'].default_value = 6; L(mp.outputs[0], n3.inputs['Vector'])
        r3 = N('ShaderNodeValToRGB'); r3.color_ramp.elements[0].position = .52; r3.color_ramp.elements[1].position = .68; L(n3.outputs['Fac'], r3.inputs[0])
        m3 = N('ShaderNodeMixRGB'); L(r3.outputs[0], m3.inputs[0]); L(last, m3.inputs[1]); m3.inputs[2].default_value = (*patina, 1); last = m3.outputs[0]
        inv = N('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1; L(r3.outputs[0], inv.inputs[1]); L(inv.outputs[0], b.inputs['Metallic'])
        rr = N('ShaderNodeMath'); rr.operation = 'MULTIPLY_ADD'; L(r3.outputs[0], rr.inputs[0]); rr.inputs[1].default_value = .4; rr.inputs[2].default_value = rough; L(rr.outputs[0], b.inputs['Roughness'])
    else:
        b.inputs['Metallic'].default_value = metallic
        rr = N('ShaderNodeMath'); rr.operation = 'MULTIPLY_ADD'; L(n1.outputs['Fac'], rr.inputs[0]); rr.inputs[1].default_value = .25; rr.inputs[2].default_value = rough-.12; L(rr.outputs[0], b.inputs['Roughness'])
    L(last, b.inputs['Base Color'])
    if bump:
        n2 = N('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = bscale; n2.inputs['Detail'].default_value = 4; L(mp.outputs[0], n2.inputs['Vector'])
        h = n2.outputs['Fac']
        if stripes:
            wv = N('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = stripes; wv.inputs['Distortion'].default_value = 1.5; wv.bands_direction = 'Z'; L(mp.outputs[0], wv.inputs['Vector'])
            ad = N('ShaderNodeMath'); ad.operation = 'ADD'; L(wv.outputs['Fac'], ad.inputs[0]); L(n2.outputs['Fac'], ad.inputs[1]); h = ad.outputs[0]
        vo = N('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = bscale*.35; L(mp.outputs[0], vo.inputs['Vector'])
        vr = N('ShaderNodeMath'); vr.operation = 'MINIMUM'; L(vo.outputs['Distance'], vr.inputs[0]); vr.inputs[1].default_value = .06
        a2 = N('ShaderNodeMath'); a2.operation = 'MULTIPLY_ADD'; L(vr.outputs[0], a2.inputs[0]); a2.inputs[1].default_value = 6.0; L(h, a2.inputs[2])
        bp = N('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = .004; L(a2.outputs[0], bp.inputs['Height']); L(bp.outputs[0], b.inputs['Normal'])
    if emit: b.inputs['Emission Color'].default_value = (*emit[0], 1); b.inputs['Emission Strength'].default_value = emit[1]
    return m

# ------------------------------------------------------------------ walk (all poses computed in world space, baked per frame)
PC, PR, PHI0 = V(2.6, 1.4), 3.0, radians(110)             # circle around the pedestal, counter-clockwise
STRIDE, TCY, ST = 1.2, 1.15, .62; VEL = STRIDE/TCY; REACH = ST*STRIDE/2; LAT = .10
def path(s):
    ph = PHI0+s/PR; p = Vector((PC[0]+PR*cos(ph), PC[1]+PR*sin(ph), 0)); return p, Vector((-sin(ph), cos(ph), 0)), Vector((-cos(ph), -sin(ph), 0)), ph+pi
def Rz(a): return Matrix.Rotation(a, 3, 'Z')
def Rx(a): return Matrix.Rotation(a, 3, 'X')
def Ry(a): return Matrix.Rotation(a, 3, 'Y')
def sstep(u): u = min(max(u, 0), 1); return u*u*(3-2*u)
def fframe(d, ref):
    y = d.normalized(); x = (ref-y*ref.dot(y)).normalized(); z = x.cross(y); return Matrix((x, y, z)).transposed()
def ankle_at(s_plant, side, pitch, lift=0.0):
    """ankle world position for a foot planted at arc s_plant; pitch>0 toes up (pivot heel), <0 heel up (pivot ball)"""
    p, T, Nl, psi = path(s_plant); base = p+Nl*(LAT*side)
    a, b = 0.0, .09
    if pitch > 0: ca, sa = cos(pitch), sin(pitch); a, b = -.05+(.05*ca-.09*sa), (.05*sa+.09*ca)
    elif pitch < 0: ca, sa = cos(pitch), sin(pitch); a, b = .17+(-.17*ca-.09*sa), (-.17*sa+.09*ca)
    return base+T*a+Vector((0, 0, b+lift)), psi
def foot_state(t, side):
    c = t/TCY+(0 if side == 1 else .5); p = c % 1.0; tc = t-p*TCY; s0 = VEL*tc+REACH
    HS, HO = radians(16), radians(-52)
    if p < ST:
        if p < .12: pit = HS*(1-p/.12)
        elif p < .36: pit = 0
        else: pit = HO*((p-.36)/(ST-.36))**1.5
        pos, psi = ankle_at(s0, side, pit); return pos, psi, pit, (0 if pit < 0 else pit)
    u = (p-ST)/(1-ST); a0, psi0 = ankle_at(s0, side, HO); a1, psi1 = ankle_at(s0+STRIDE, side, HS)
    e = sstep(u); pos = a0.lerp(a1, e)+Vector((0, 0, .075*sin(pi*u**.8))); pit = HO+(HS-HO)*sstep((u-.15)/.85)
    return pos, psi0+(psi1-psi0)*e, pit, pit*sstep(u/.35)
def solve(t, REST):
    """returns {bone: 4x4 world matrix}"""
    P = {}; c = t/TCY
    pb, T, Nl, psi = path(VEL*t); Dh = Rz(psi)
    def put(b, D, head=None):
        if head is None: head = (P[PARENT[b]] @ REST[PARENT[b]].inverted() @ REST[b]).translation
        P[b] = Matrix.Translation(head) @ (D @ REST[b].to_3x3()).to_4x4(); return D
    yaw = radians(-6)*cos(2*pi*c); roll = radians(-3)*cos(2*pi*(c-.31))
    hp = pb+Nl*(.028*cos(2*pi*(c-.31)))+Vector((0, 0, 1.05+.02*cos(4*pi*(c-.31))))
    Dhip = put('hips', Dh @ Rz(yaw) @ Ry(roll) @ Rx(radians(3)), hp)
    Dch = Dh @ Rz(-yaw*.9) @ Ry(-roll*.8) @ Rx(radians(10+1.5*sin(4*pi*c)))
    put('spine', Dh @ Rz(0) @ Rx(radians(6))); put('chest', Dch)
    hy = radians(9)*sin(2*pi*t/5.5+.6)
    put('neck', Dh @ Rz(hy*.5) @ Rx(radians(9))); put('head', Dh @ Rz(hy) @ Rx(radians(11)))
    fwd = {}
    for side, sfx in ((1, '.L'), (-1, '.R')):
        A, psif, pit, tpit = foot_state(t, side)
        H = (P['hips'] @ REST['hips'].inverted() @ REST['thigh'+sfx]).translation
        la = (REST['shin'+sfx].translation-REST['thigh'+sfx].translation).length; lb = (REST['foot'+sfx].translation-REST['shin'+sfx].translation).length
        d = A-H; L = d.length
        if L > (la+lb)*.998: A = H+d*((la+lb)*.998/L); d = A-H; L = d.length
        x = (la*la-lb*lb+L*L)/(2*L); hgt = sqrt(max(la*la-x*x, 0)); dn = d/L
        Tf = Vector((-sin(psif-pi), cos(psif-pi), 0)); pole = (T+Tf).normalized(); pole = (pole-dn*pole.dot(dn)).normalized()
        Kp = H+dn*x+pole*hgt; sideax = Dhip @ Vector((1, 0, 0)); X = Vector((1, 0, 0))
        rH, rK, rA = REST['thigh'+sfx].translation, REST['shin'+sfx].translation, REST['foot'+sfx].translation
        put('thigh'+sfx, fframe(Kp-H, sideax) @ fframe(rK-rH, X).transposed(), H)
        put('shin'+sfx, fframe(A-Kp, sideax) @ fframe(rA-rK, X).transposed(), Kp)
        put('foot'+sfx, Rz(psif) @ Rx(-pit), A); put('toe'+sfx, Rz(psif) @ Rx(-tpit))
        loc = Dhip.transposed() @ (Kp-H); fwd[side] = atan2(-loc.y, -loc.z)
        ca = cos(2*pi*(c-(.5 if side == 1 else 0)))
        Du = Dch @ Rz(yaw*.3) @ Rx(radians(-(15*ca-3))) @ Ry(radians(6)*side)
        put('upper_arm'+sfx, Du); Df = Du @ Rx(radians(-(14+9*(.5+.5*ca)))); put('forearm'+sfx, Df); put('hand'+sfx, Df @ Rx(radians(-6)))
    af = max(0, fwd[1], fwd[-1]); ab = max(0, -fwd[1], -fwd[-1]); sw = radians(2.5)*sin(4*pi*c+.8)
    put('tabF1', Dhip @ Rx(-(.85*af+radians(3)))); put('tabF2', Dhip @ Rx(-(.8*af)+sw)); put('tabF3', Dhip @ Rx(-(.3*af)+2*sw+radians(4)))
    put('tabB1', Dhip @ Rx(.85*ab+radians(5))); put('tabB2', Dhip @ Rx(.8*ab+radians(7)+sw)); put('tabB3', Dhip @ Rx(.35*ab+radians(12)+2*sw))
    return P

# ------------------------------------------------------------------ main
def main():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '_work', 'palace.blend'))
    sc = bpy.context.scene
    col = bpy.data.collections.new('COL_Char'); sc.collection.children.link(col)
    # camera now aims mostly at the character (same dolly/orbit path), focus follows him
    tgt = bpy.data.objects['CAM_Target']; cam = bpy.data.objects['CAM_Main']; rec = {}
    for fr in range(sc.frame_start, sc.frame_end+1):
        sc.frame_set(fr); rec[fr] = (tgt.matrix_world.translation.copy(), cam.matrix_world.translation.copy())
    tgt.parent = None; tgt.animation_data_clear()
    for fr, (tp, cp) in rec.items():
        cpos = path(VEL*(fr-1)/sc.render.fps)[0]; w = .8-.35*sstep((fr-192)/48)
        tgt.location = tp.lerp(cpos+Vector((0, 0, 2.0)), w); tgt.keyframe_insert('location', frame=fr)
        cam.data.dof.focus_distance = (cpos+Vector((0, 0, 1.4))-cp).length; cam.data.dof.keyframe_insert('focus_distance', frame=fr)
    ad = bpy.data.armatures.new('CHR_Rig'); arm = bpy.data.objects.new('CHR_Rig', ad); col.objects.link(arm)
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
    for n, h, t, p in BONES:
        b = ad.edit_bones.new(n); b.head = h; b.tail = t; b.roll = 0
        if p: b.parent = ad.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    REST = {b.name: b.matrix_local.copy() for b in ad.bones}
    M = {'skin': cmat('Skin', (.17, .22, .21), (.08, .105, .11), .5, bump=.6, bscale=70),
         'bronze': cmat('Bronze', (.62, .40, .16), (.36, .22, .09), .36, metallic=1, bump=.25, bscale=40, patina=(.07, .16, .13)),
         'leather': cmat('Leather', (.075, .045, .028), (.035, .022, .015), .62, bump=.5, bscale=90),
         'horn': cmat('Horn', (.70, .63, .48), (.36, .29, .20), .42, bump=.3, bscale=30),
         'cloth': cmat('Cloth', (.34, .035, .028), (.16, .02, .02), .9, bump=.7, bscale=220, stripes=160),
         'straw': cmat('Straw', (.56, .43, .21), (.36, .26, .12), .7, bump=.8, bscale=120, dims=(.9, .9, .3)),
         'eye': cmat('Eye', (1, .5, .1), (1, .4, .05), .3, emit=((1.0, .42, .08), 9.0))}
    F, tips = build_skin(); v, f, lab = F.mesh(); print('skin verts', len(v), 'tris', len(f), round(time.time()-T0, 1), flush=True)
    names, Wt = skin_weights(v, f, lab, F.prims); del F
    ob = add_object('CHR_Body', make_mesh('CHR_Body', v, f), arm, M['skin'], col); set_groups(ob, names, Wt)
    for k, (v, f, lab, prims) in build_rigid(tips).items():
        ob = add_object('CHR_'+k, make_mesh('CHR_'+k, v, f), arm, M[k], col); rigid_groups(ob, lab, prims); print(k, len(v), flush=True)
    # tabard cloth (front/back), tattered hem
    rng = random.Random(4)
    for tag, y0, sgn in (('F', -.137, -1), ('B', .147, 1)):
        bm = bmesh.new(); nx, nz = 8, 22; hem = [rng.uniform(-.09, .05) for _ in range(nx+1)]; grid = []
        for j in range(nz+1):
            row = []
            for i in range(nx+1):
                u = i/nx-.5; w = .2-.03*j/nz; z = 1.19-(1.19-.47-hem[i]*(j/nz)**2)*(j/nz)
                row.append(bm.verts.new((u*w+.004*sin(j*.9+i), y0+sgn*(.012*(1-(2*u)**2)*min(1, j/3)+.004*sin(i*1.7+j*.6)), z)))
            grid.append(row)
        for j in range(nz):
            for i in range(nx): bm.faces.new((grid[j][i], grid[j][i+1], grid[j+1][i+1], grid[j+1][i]))
        me = bpy.data.meshes.new('CHR_Tab'+tag); bm.to_mesh(me); bm.free()
        for p in me.polygons: p.use_smooth = True
        ob = add_object('CHR_Tab'+tag, me, arm, M['cloth'], col)
        sm = ob.modifiers.new('Solid', 'SOLIDIFY'); sm.thickness = .006
        co = np.array([vv.co[:] for vv in me.vertices]); zz = co[:, 2]
        cz = [(1.05, 'tab%s1' % tag), (.81, 'tab%s2' % tag), (.57, 'tab%s3' % tag)]
        Wc = np.stack([np.exp(-((zz-c0)/.13)**2) for c0, _ in cz], 1); Wc[zz > 1.13] = (1, 0, 0); Wc /= Wc.sum(1, keepdims=True)
        hipw = np.clip((zz-1.13)/.05, 0, 1)[:, None]
        set_groups(ob, [n for _, n in cz]+['hips'], np.concatenate([Wc*(1-hipw), hipw], 1))
    # conical woven hat
    bm = bmesh.new(); segs = 72; prof = [(.0, 2.215), (.03, 2.20), (.12, 2.155), (.25, 2.09), (.36, 2.03), (.415, 2.0), (.42, 1.992), (.40, 1.995), (.25, 2.07), (.11, 2.14), (.0, 2.18)]
    rings = []
    for (r, z) in prof:
        ring = []
        for sgi in range(segs):
            a = 2*pi*sgi/segs; rr = r*(1+.012*sin(a*18)+.02*sin(a*3+1)); zz = z+(.006*(sgi % 2) if .02 < r < .41 else 0)-.012*sin(a*2+.5)*(r/.42)
            ring.append(bm.verts.new((rr*cos(a), rr*sin(a), zz)))
        rings.append(ring)
    for a_, b_ in zip(rings[:-1], rings[1:]):
        for i in range(segs): bm.faces.new((a_[i], a_[(i+1) % segs], b_[(i+1) % segs], b_[i]))
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, -.03, 1.95)) @ Matrix.Rotation(radians(9), 4, 'X') @ Matrix.Translation((0, 0, -1.95)), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('CHR_Hat'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = add_object('CHR_Hat', me, arm, M['straw'], col); ob.vertex_groups.new(name='head').add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    # bake walk
    arm.rotation_mode = 'QUATERNION'; prevq = {}
    order = [b[0] for b in BONES]
    for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
    for fr in range(sc.frame_start, sc.frame_end+1):
        P = solve((fr-1)/sc.render.fps, REST)
        for n in order:
            par = PARENT[n]; base = (P[par] @ REST[par].inverted() @ REST[n]) if par else REST[n]
            mb = base.inverted() @ P[n]; pb = arm.pose.bones[n]; q = mb.to_quaternion()
            if n in prevq and prevq[n].dot(q) < 0: q.negate()
            prevq[n] = q.copy(); pb.location = mb.translation; pb.rotation_quaternion = q
            pb.keyframe_insert('location', frame=fr); pb.keyframe_insert('rotation_quaternion', frame=fr)
    sc['char_path'] = (float(PC[0]), float(PC[1]), PR)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, '_work', 'palace_char.blend')); print('SAVED', round(time.time()-T0, 1))
if __name__ == '__main__': main()
