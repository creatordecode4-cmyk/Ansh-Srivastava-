"""Katanas and scabbards, modelled from KATANA / SCABBARD in refs/oni_parts.png and
TWO KATANAS / SHEATH in refs/ronin_parts.png.

Built by code because an image-to-3D blade comes out bent and lumpy, and these swords are seen
in close-up, drawn, and meeting edge to edge.

Local axes of every sword and scabbard: origin where blade meets guard, +Y toward the point,
cutting edge toward -Z, flats facing +X / -X. Blade, grip and scabbard all follow one circle of
radius R (centre at z = +R), so drawing the sword is a pure rotation about that centre.
"""
import math

import bmesh
import numpy as np
from mathutils import Vector

from . import charmats as cm
from . import core

ONI = dict(
    tag="Oni", blade=0.80, grip=0.285, rise=0.050, width=(0.0335, 0.0245), thick=(0.0074, 0.0050), kissaki=0.050,
    guard="mokko", guard_r=(0.039, 0.046), metal="gold", diamonds=10, skin=(222, 214, 198), pattern="oni_blade", inlay=(0.80, 0.66, 0.42),
)
RONIN = dict(
    tag="Ronin", blade=0.73, grip=0.255, rise=0.040, width=(0.0320, 0.0235), thick=(0.0070, 0.0048), kissaki=0.046,
    guard="disc", guard_r=(0.036, 0.036), metal="silver", diamonds=13, skin=(226, 226, 228), pattern="ronin_blade", inlay=(0.84, 0.85, 0.87),
)


def radius(spec):
    """Circle radius that lifts the point by spec['rise'] over the blade length."""
    return spec["blade"] ** 2 / (2.0 * spec["rise"])


def frame(s, R):
    """Point, tangent and spine-side normal at arc length s (s < 0 runs into the grip)."""
    th = s / R
    return (Vector((0.0, R * math.sin(th), R * (1.0 - math.cos(th)))), Vector((0.0, math.cos(th), math.sin(th))),
            Vector((0.0, -math.sin(th), math.cos(th))))


def _uv_layers(me, U, Vring, Vside, nv):
    """UVMap (u along, v around) and UVSide (u along, v edge-to-spine) for a loft with nv verts per ring."""
    a = me.uv_layers.new(name="UVMap")
    b = me.uv_layers.new(name="UVSide")
    nl = len(me.loops)
    vi = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get("vertex_index", vi)
    i, j = vi // nv, vi % nv
    # the seam quad (j = nv-1 -> 0) must run on to v = 1 instead of jumping back to 0
    ls = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    vr = np.asarray(Vring)[j].astype(np.float64)
    for p in range(len(ls)):
        sl = slice(ls[p], ls[p] + lt[p])
        jj = j[sl]
        if jj.max() == nv - 1 and jj.min() == 0 and lt[p] == 4:
            vr[sl] = np.where(jj == 0, 1.0, vr[sl])
    uvA = np.stack([np.asarray(U)[i], vr], axis=1)
    uvB = np.stack([np.asarray(U)[i], np.asarray(Vside)[j]], axis=1)
    a.data.foreach_set("uv", uvA.reshape(-1))
    b.data.foreach_set("uv", uvB.reshape(-1))


def arc_loft(name, R, stations, col, nv=24, u_range=None, close_ends=True):
    """Oval tube along the sword's circle. stations: (s, half_height, half_thickness).
    Ring vertex j sits at angle 2*pi*(j/nv - 0.25), so the +X flat is at v = 0.25 and -X at 0.75."""
    ns = len(stations)
    P = np.zeros((ns, nv, 3))
    ang = 2 * math.pi * (np.arange(nv) / nv - 0.25)
    for i, (s, a, b) in enumerate(stations):
        p, t, n = frame(s, R)
        for j in range(nv):
            P[i, j] = p + Vector((1, 0, 0)) * (b * math.cos(ang[j])) + n * (a * math.sin(ang[j]))
    ob = core.grid_obj(name, P, col, close_v=True)
    s0, s1 = (stations[0][0], stations[-1][0]) if u_range is None else u_range
    U = [(st[0] - s0) / (s1 - s0) for st in stations]
    _uv_layers(ob.data, U, np.arange(nv) / nv, (np.sin(ang) + 1) / 2, nv)
    if close_ends:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        bm.to_mesh(ob.data)
        bm.free()
    return core.smooth(ob, 40)


# ----------------------------------------------------------------------------- blade
# cross-section: (x as a fraction of thickness, h as a fraction of width); h = +0.5 spine, -0.5 edge
SECTION = [(0.0, 0.5), (0.36, 0.47), (0.50, 0.14), (0.30, -0.22), (0.0, -0.5), (-0.30, -0.22), (-0.50, 0.14), (-0.36, 0.47)]
SHARP = (0, 1, 2, 4, 6, 7)          # spine, its shoulders, the ridge line, the edge: crisp lines down the blade


def blade(name, spec, col):
    R, L, Lk = radius(spec), spec["blade"], spec["kissaki"]
    (w0, w1), (t0, t1) = spec["width"], spec["thick"]
    ss = list(np.linspace(0.0, L - Lk, 72)) + list(L - Lk + Lk * (1 - (1 - np.linspace(0.0, 1.0, 26)[1:]) ** 1.6))
    nv = len(SECTION)
    P = np.zeros((len(ss), nv, 3))
    for i, s in enumerate(ss):
        p, t, n = frame(s, R)
        f = s / L
        w, th = w0 + (w1 - w0) * f, t0 + (t1 - t0) * f
        k = max(0.0, (s - (L - Lk)) / Lk)
        g = k ** 1.75                                    # the edge sweeps up to meet the spine at the point
        th *= 1.0 - 0.93 * k ** 2.2
        for j, (fx, fh) in enumerate(SECTION):
            h = 0.5 * w - (0.5 * w - fh * w) * (1.0 - g)
            P[i, j] = p + Vector((1, 0, 0)) * (fx * th) + n * h
    ob = core.grid_obj(name, P, col, close_v=True)
    _uv_layers(ob.data, [s / L for s in ss], np.arange(nv) / nv, [fh + 0.5 for _, fh in SECTION], nv)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        e.smooth = not (a % nv == b % nv and a % nv in SHARP)
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()
    core.set_mat(ob, cm.blade(f"MAT_Blade_{spec['tag']}", spec["pattern"], spec["inlay"], tip_u=1.0 - Lk / L * 0.86))
    return ob


# ----------------------------------------------------------------------------- fittings
def _prism_y(name, stations, col, bevel=0.0012):
    """Four-sided tapered block along Y: stations = (y, half_x, half_z)."""
    verts, faces = [], []
    for y, hx, hz in stations:
        verts += [(-hx, y, -hz), (hx, y, -hz), (hx, y, hz), (-hx, y, hz)]
    for i in range(len(stations) - 1):
        a, b = i * 4, i * 4 + 4
        faces += [(a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k) for k in range(4)]
    faces += [(3, 2, 1, 0), tuple(len(verts) - 4 + k for k in range(4))]
    ob = core.mesh_obj(name, verts, faces, col)
    if bevel:
        core.bevel_mod(ob, bevel, 2, 30)
    return core.smooth(ob, 40)


def guard(name, spec, col):
    """Tsuba in the XZ plane: four-lobed and heavy for the Oni, a thin round plate for the Ronin."""
    rx, rz = spec["guard_r"]
    mokko = spec["guard"] == "mokko"
    ti, tr = (0.0024, 0.0040) if mokko else (0.0017, 0.0024)
    nphi = 96
    prof = [(0.02, ti), (0.66, ti), (0.76, tr), (0.95, tr), (1.0, tr * 0.45), (1.0, -tr * 0.45), (0.95, -tr), (0.76, -tr), (0.66, -ti), (0.02, -ti)]
    P = np.zeros((nphi, len(prof), 3))
    for i in range(nphi):
        ph = 2 * math.pi * i / nphi
        lobe = 1.0 + (0.085 * math.cos(4 * ph) + 0.02 * math.cos(8 * ph) if mokko else 0.0)
        for k, (f, y) in enumerate(prof):
            P[i, k] = (f * rx * lobe * math.cos(ph), y, f * rz * lobe * math.sin(ph))
    ob = core.grid_obj(name, P, col, close_u=True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bm.to_mesh(ob.data)
    bm.free()
    return core.smooth(ob, 35)


def tassel(lib, name, length=0.16, color_mat=None, band_mat=None, cord=0.35):
    """Hanging tassel: origin at the top of its cord, hanging along -Z (it gets its own swing later)."""
    red = color_mat or cm.red_silk()
    thread = cm.red_silk(thread=0.8) if color_mat is None else color_mat
    lc = length * cord
    parts = []
    c = core.tube(name + "_cord", [(0, 0, 0), (0.002, 0, -lc * 0.5), (0, 0, -lc)], 0.0021, lib, segs=8)
    core.set_mat(core.smooth(c, 60), red)
    parts.append(c)
    head_r = length * 0.085
    head = core.lathe(name + "_head", [(0.0005, 0.0), (head_r * 0.7, -head_r * 0.25), (head_r, -head_r), (head_r * 0.8, -head_r * 1.8), (head_r * 0.55, -head_r * 2.2)],
                      20, lib, cap=False)
    head.location.z = -lc
    core.set_mat(core.smooth(core.apply_transform(head), 60), red)
    parts.append(head)
    zb = -lc - head_r * 2.2
    band = core.lathe(name + "_band", [(head_r * 0.6, 0.0), (head_r * 0.72, -0.001), (head_r * 0.72, -head_r * 0.7), (head_r * 0.6, -head_r * 0.8)], 20, lib, cap=False)
    band.location.z = zb
    core.set_mat(core.smooth(core.apply_transform(band), 40), band_mat or cm.gold())
    parts.append(band)
    zs = zb - head_r * 0.8
    ls = length - (-zs)
    skirt = core.lathe(name + "_skirt", [(head_r * 0.55, 0.0), (head_r * 0.95, -ls * 0.18), (head_r * 1.25, -ls * 0.6), (head_r * 1.45, -ls), (head_r * 0.3, -ls * 0.985)],
                       28, lib, cap=False)
    skirt.location.z = zs
    core.set_mat(core.smooth(core.apply_transform(skirt), 60), thread)
    parts.append(skirt)
    ob = core.join(parts, name)
    ob["length"] = length
    return ob


def katana(lib, name, spec):
    """Returns (sword object, dict of attachment data). Tassels are separate objects named in the dict."""
    R, L, Lg = radius(spec), spec["blade"], spec["grip"]
    (w0, _), (t0, _) = spec["width"], spec["thick"]
    fit = cm.gold() if spec["metal"] == "gold" else cm.silver()
    parts = [blade(name + "_blade", spec, lib)]

    # habaki: the collar that wedges the blade into the scabbard mouth
    hb = _prism_y(name + "_habaki", [(0.0005, t0 / 2 + 0.0026, w0 / 2 + 0.0022), (0.021, t0 / 2 + 0.0024, w0 / 2 + 0.002), (0.027, t0 / 2 + 0.0012, w0 / 2 + 0.0008)], lib, 0.0009)
    core.set_mat(hb, fit)
    parts.append(hb)
    if spec["guard"] == "mokko":          # the Oni's flared, pointed collar in front of the guard
        fl = _prism_y(name + "_flare", [(-0.0005, 0.0125, 0.031), (0.006, 0.0105, 0.027), (0.016, 0.0072, w0 / 2 + 0.006), (0.0235, 0.0066, w0 / 2 + 0.0035)], lib, 0.0012)
        core.set_mat(fl, fit)
        parts.append(fl)
        for sz in (-1, 1):                # two points reaching along the blade, as on the sheet
            tooth = _prism_y(name + "_tooth", [(0.012, 0.0062, 0.0055), (0.034, 0.0048, 0.0036), (0.046, 0.004, 0.0008)], lib, 0.0006)
            tooth.location.z = sz * (w0 / 2 + 0.0015)
            core.set_mat(core.apply_transform(tooth), fit)
            parts.append(tooth)
    g = guard(name + "_guard", spec, lib)
    g.location.y = -0.0042
    core.set_mat(core.apply_transform(g), fit)
    parts.append(g)

    # grip: oval core under the cord wrap, slightly waisted, on the same circle as the blade
    s0, s1 = -0.0085, -Lg
    st = []
    for k in np.linspace(0, 1, 44):
        s = s0 + (s1 - s0) * k
        waist = 1.0 - 0.07 * math.sin(math.pi * k)
        st.append((s, 0.0186 * waist, 0.0136 * waist))
    gr = arc_loft(name + "_grip", R, st, lib, nv=32)
    core.set_mat(gr, cm.grip(f"MAT_Grip_{spec['tag']}", spec["tag"].lower(), spec["diamonds"], spec["skin"]))
    parts.append(gr)
    fuchi = arc_loft(name + "_fuchi", R, [(-0.0075, 0.0196, 0.0146), (-0.0085, 0.0204, 0.0154), (-0.021, 0.0204, 0.0154), (-0.0225, 0.0196, 0.0146)], lib, nv=32)
    core.set_mat(fuchi, fit)
    parts.append(fuchi)
    e = Lg
    kash = arc_loft(name + "_kashira", R, [(-e + 0.016, 0.0196, 0.0146), (-e + 0.0148, 0.0206, 0.0156), (-e + 0.002, 0.0206, 0.0156), (-e - 0.003, 0.0192, 0.0142),
                                         (-e - 0.0065, 0.0150, 0.0108), (-e - 0.0082, 0.0080, 0.0056)], lib, nv=32)
    core.set_mat(kash, fit)
    parts.append(kash)

    info = dict(R=R, blade=L, grip=Lg, grip_centre=frame(-Lg * 0.5, R)[0][:], point=frame(L, R)[0][:], tassels=[])   # tassels: object names
    if spec["metal"] == "gold":           # red cord through the pommel with a heavy tassel
        p, t, n = frame(-Lg - 0.004, R)
        loop = core.tube(name + "_loop", [p + n * 0.012, p + n * 0.024 - t * 0.006, p - t * 0.012, p - n * 0.02 - t * 0.008, p - n * 0.014], 0.0022, lib, segs=8)
        core.set_mat(core.smooth(loop, 60), cm.red_silk())
        parts.append(loop)
        ts = tassel(lib, name + "_tassel", 0.19)
        ts.location = p - n * 0.016 - t * 0.008
        info["tassels"].append(ts.name)
    ob = core.join(parts, name)
    for k, v in info.items():
        ob[k] = ",".join(v) if k == "tassels" else v
    return ob, info


def scabbard(lib, name, spec):
    """Saya on the same circle as its blade (origin at the mouth), so the sword slides straight in."""
    R, L = radius(spec), spec["blade"]
    (w0, w1) = spec["width"]
    oni = spec["metal"] == "gold"
    fit = cm.gold() if oni else cm.silver()
    Ls = L + 0.022
    parts, tassels = [], []
    a0, a1, b0, b1 = w0 / 2 + 0.0075, w1 / 2 + 0.0062, 0.0128, 0.0108
    st = []
    for k in np.linspace(0, 1, 60):
        s = 0.0025 + (Ls - 0.0025) * k
        st.append((s, a0 + (a1 - a0) * k, b0 + (b1 - b0) * k))
    st += [(Ls + 0.006, a1 * 0.86, b1 * 0.86), (Ls + 0.0095, a1 * 0.55, b1 * 0.55)]
    body = arc_loft(name + "_body", R, st, lib, nv=32, u_range=(0.0, Ls))
    if oni:
        lac = cm.lacquer("MAT_Saya_Oni", pattern="oni_saya", inlay=(0.80, 0.66, 0.42), inlay_metal=1.0, pattern_from=0.585, scales=150.0)
    else:
        lac = cm.lacquer("MAT_Saya_Ronin", pattern="ronin_saya", inlay=(0.78, 0.78, 0.80), inlay_metal=0.0, pattern_from=0.42, scales=0.0, rough=0.1)
    core.set_mat(body, lac)
    parts.append(body)
    mouth = arc_loft(name + "_mouth", R, [(0.0, a0 + 0.0002, b0 + 0.0002), (-0.0002, a0 + 0.0016, b0 + 0.0016), (0.017, a0 + 0.0016, b0 + 0.0016), (0.0185, a0 + 0.0002, b0 + 0.0002)],
                     lib, nv=32, close_ends=False)
    core.set_mat(mouth, fit)
    parts.append(mouth)
    hole = arc_loft(name + "_void", R, [(0.0012, a0 * 0.999, b0 * 0.999), (0.0013, a0 * 0.4, b0 * 0.4)], lib, nv=32)
    core.set_mat(hole, cm.void())
    parts.append(hole)
    ke = Ls
    kojiri = arc_loft(name + "_kojiri", R, [(ke - 0.050, a1 + 0.0004, b1 + 0.0004), (ke - 0.0485, a1 + 0.0017, b1 + 0.0017), (ke + 0.004, a1 + 0.0015, b1 + 0.0015),
                                          (ke + 0.009, a1 * 0.9, b1 * 0.9), (ke + 0.0122, a1 * 0.5, b1 * 0.5)], lib, nv=32)
    core.set_mat(kojiri, fit)
    parts.append(kojiri)

    sk = 0.185                                                   # cord knob, a hand's width below the mouth
    p, t, n = frame(sk, R)
    ak = a0 + (a1 - a0) * sk / Ls
    bk = b0 + (b1 - b0) * sk / Ls
    knob = core.box(name + "_kurigata", (0.011, 0.030, 0.014), (bk + 0.0042, p.y, p.z + ak * 0.3), lib, bevel=0.003, segs=3)
    core.set_mat(core.smooth(core.apply_transform(knob), 40), fit if oni else cm.black_steel())
    parts.append(knob)

    def ring(s, r=0.0026, lift=0.0, tilt=0.0):
        """One turn of cord around the scabbard at arc length s (tilt slants it along the length)."""
        pts = []
        aa, bb = a0 + (a1 - a0) * s / Ls + r * 0.9 + lift, b0 + (b1 - b0) * s / Ls + r * 0.9 + lift
        for k in range(25):
            ph = 2 * math.pi * k / 24
            pp, tt, nn = frame(s + tilt * math.sin(ph), R)
            pts.append(pp + Vector((1, 0, 0)) * (bb * math.cos(ph)) + nn * (aa * math.sin(ph)))
        return core.tube(name + "_cord", pts, r, lib, segs=8, cap=False)

    if oni:
        red = cm.red_silk()
        cords = []
        for base in (sk - 0.040, sk + 0.022):                    # two bundles of red cord either side of the knob
            for i in range(5):
                cords.append(ring(base + i * 0.0056, 0.0027, lift=0.0003 * (i % 2)))
        cords.append(ring(sk - 0.006, 0.0027, lift=0.0026, tilt=0.030))       # the crossing turns over the knob
        cords.append(ring(sk - 0.006, 0.0027, lift=0.0030, tilt=-0.030))
        tail = core.tube(name + "_tail", [(bk + 0.008, p.y - 0.004, p.z + ak * 0.1), (bk + 0.011, p.y - 0.002, p.z - ak * 0.6), (bk + 0.006, p.y, p.z - ak - 0.012)], 0.0024, lib, segs=8)
        cords.append(tail)
        for c in cords:
            core.set_mat(core.smooth(c, 60), red)
        parts += cords
        t1 = tassel(lib, name + "_tassel_knob", 0.115)
        t1.location = (bk + 0.006, p.y, p.z - ak - 0.012)
        tassels.append(t1.name)
        pm, tm, nm = frame(0.009, R)                               # cord and tassel hanging from the mouth band
        loop = ring(0.009, 0.0024, lift=0.0018)
        core.set_mat(core.smooth(loop, 60), red)
        parts.append(loop)
        t2 = tassel(lib, name + "_tassel_mouth", 0.17)
        t2.location = pm - nm * (a0 + 0.006)
        tassels.append(t2.name)
    else:
        cords = []
        for tilt in (0.030, -0.030):                               # black cord crossing below the mouth, as on the sheath view
            for s_ in (0.058, 0.098, 0.138):
                cords.append(ring(s_, 0.0022, tilt=tilt))
        for c in cords:
            core.set_mat(core.smooth(c, 60), cm.black_cord())
        parts += cords
        sb = arc_loft(name + "_band", R, [(s_, a0 + (a1 - a0) * s_ / Ls + d, b0 + (b1 - b0) * s_ / Ls + d) for s_, d in ((0.168, 0.0003), (0.1692, 0.002), (0.202, 0.002), (0.2032, 0.0003))],
                      lib, nv=32, close_ends=False)
        core.set_mat(sb, fit)
        parts.append(sb)
    ob = core.join(parts, name)
    ob["R"], ob["length"], ob["tassels"] = R, Ls, ",".join(tassels)
    return ob, dict(R=R, length=Ls, tassels=tassels)


def sheathed_offset(spec, drawn=0.0):
    """Rotation angle (radians, about the X axis through the circle centre) that slides the sword
    'drawn' metres out of its scabbard along the shared arc."""
    return -drawn / radius(spec)
