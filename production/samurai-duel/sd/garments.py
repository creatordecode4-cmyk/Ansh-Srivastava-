"""Cloth that is simulated: the Ronin's cape and waist tails (and the Oni's hakama later).

Each piece starts as a flat panel hanging clear of the body. Its top rows are pinned, and over
the first frames the pins travel to their seats on the body (a 'Tuck' shape key), pulling the
panel in so it drapes and gathers by itself against a collision stand-in of the body. Panels
are wider than their seats, which is what makes the folds.

A panel is a regular grid: column i runs across (u = 0..1), row j runs down from the pinned top
(v = 0) to the hem (v = 1). Ragged hems, slits and holes are cut out of the grid; a per-vertex
'fray' value (0 at a cut edge, 1 a few centimetres in) lets the material fray the edges.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import core
from .mats import _new, get

CELL = 0.0125          # grid spacing in metres


# ----------------------------------------------------------------------------- material
def fabric(name, color=(0.50, 0.51, 0.54), width=1.0, length=1.0, dirt=0.55):
    """Plain-weave cloth: thread relief, grime gathering toward the hem, frayed cut edges."""
    def build(name):
        m, nt, b = _new(name)
        uv = nt.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        sep = nt.new("ShaderNodeSeparateXYZ")
        nt.link(uv.outputs[0], sep.inputs[0])
        v = sep.outputs[1]
        mp = nt.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (width, length, 1.0)             # UV -> metres along the cloth
        nt.link(uv.outputs[0], mp.inputs[0])
        metres = mp.outputs[0]
        warp = nt.new("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
        weft = nt.new("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y")
        for w in (warp, weft):
            nt.link(metres, w.inputs["Vector"])
            w.inputs["Scale"].default_value = 520.0                           # about 1.9 mm thread pitch
            w.inputs["Distortion"].default_value = 0.6
            w.inputs["Detail"].default_value = 1.0
        weave = nt.math("MULTIPLY", warp.outputs[1], weft.outputs[1])            # output 1 is the factor (named Fac or Factor by version)
        blot = nt.noise(metres, 9.0, 4.0, 0.6)
        fray = nt.new("ShaderNodeAttribute", attribute_name="fray").outputs[2]
        grime = nt.math("MULTIPLY", nt.map_range(v, 0.35, 1.0, 0.0, 1.0), nt.map_range(blot, 0.3, 0.75, 0.25, 1.0))
        grime = nt.math("MAXIMUM", grime, nt.map_range(fray, 0.0, 0.5, 0.8, 0.0))
        col = nt.mix(nt.math("MULTIPLY", grime, dirt), (*color, 1), (color[0] * 0.22, color[1] * 0.20, color[2] * 0.18, 1))
        nt.put(b.inputs["Base Color"], col)
        b.inputs["Roughness"].default_value = 0.88
        b.inputs["Sheen Weight"].default_value = 0.35
        b.inputs["Sheen Roughness"].default_value = 0.5
        b.inputs["Subsurface Weight"].default_value = 0.08
        b.inputs["Subsurface Radius"].default_value = (0.004, 0.004, 0.004)
        nt.link(nt.bump(nt.math("ADD", weave, nt.math("MULTIPLY", blot, 0.6)), 0.35, 0.0007), b.inputs["Normal"])
        # worn edges: the cloth is eaten away irregularly over the last 2 cm, down to loose threads
        threads = nt.noise(nt.coords("UV", (width * 900.0, length * 60.0, 1.0)), 1.0, 2.0, 0.5)
        tear = nt.noise(metres, 75.0, 3.0, 0.6)
        body = nt.map_range(fray, 0.0, 0.5, 0.0, 1.0, smooth=False)
        field = nt.math("ADD", body, nt.math("ADD", nt.math("MULTIPLY", nt.math("SUBTRACT", tear, 0.5), 0.9), nt.math("MULTIPLY", nt.math("SUBTRACT", threads, 0.5), 0.5)))
        nt.put(b.inputs["Alpha"], nt.math("GREATER_THAN", field, 0.33))
        return m

    return get(name, build)


# ----------------------------------------------------------------------------- panels
def _ragged_mask(nu, nv, rng, base=None, depth=0.10, notches=5, slits=3, holes=2):
    """How a panel is worn away. Returns (keep, rips):
    keep  boolean (nu-1, nv-1) array of grid cells that remain: a wandering hem with broad torn
          bites out of it and a few moth holes
    rips  (column, first row) of tears running up from the hem. A tear removes no cloth: the
          mesh is split along that line, and the two sides part by themselves when it hangs."""
    keep = np.ones((nu - 1, nv - 1), dtype=bool)
    i = np.arange(nu - 1) + 0.5
    cut = np.zeros(nu - 1) if base is None else np.asarray(base, dtype=float)[:nu - 1].copy()
    ph = rng.uniform(0, 6.28, 3)
    for k, amp in enumerate((0.5, 0.28, 0.16)):                      # wandering hem line
        cut += depth * amp * (0.5 + 0.5 * np.sin(i / (nu - 1) * (2.2 + 3.1 * k) * math.pi + ph[k]))
    for _ in range(notches):                                         # broad bites: gentle sides, no pixel stairs
        c, wdt, dpt = rng.uniform(0.05, 0.95) * (nu - 1), rng.uniform(4.0, 9.0), rng.uniform(0.5, 1.3) * depth
        cut += dpt * np.clip(1.0 - np.abs(i - c) / wdt, 0, 1) ** 1.5
    rows = np.clip(np.round(cut / CELL).astype(int), 0, nv - 6)
    for a in range(nu - 1):
        if rows[a] > 0:
            keep[a, nv - 1 - rows[a]:] = False
    jj, ii = np.meshgrid(np.arange(nv - 1), np.arange(nu - 1))
    for _ in range(holes):                                           # moth-eaten holes in the lower half
        ci, cj = rng.uniform(0.15, 0.85) * (nu - 1), rng.uniform(0.55, 0.85) * (nv - 1)
        ri, rj = rng.uniform(1.5, 3.0), rng.uniform(1.8, 4.5)
        keep &= ((ii - ci) / ri) ** 2 + ((jj - cj) / rj) ** 2 > 1.0
    keep[:, :3] = True                                               # never cut the pinned rows
    # cuts can isolate scraps that would simply fall off: keep only what still hangs from the top
    from scipy import ndimage
    lab, _ = ndimage.label(keep)
    held = np.unique(lab[:, 0])
    keep &= np.isin(lab, held[held > 0])
    rips = []
    cols = rng.permutation(np.arange(2, nu - 2))[:slits]
    for c in cols:
        rips.append((int(c), int((nv - 1) * (1.0 - rng.uniform(0.12, 0.45)))))
    return keep, rips


def panel(name, rest, col, wear=None, mat=None, hold_rows=3):
    """Grid mesh from rest[(nu, nv, 3)]: row 0 is the top. wear = (keep, rips) from _ragged_mask."""
    rest = np.asarray(rest, dtype=np.float64)
    nu, nv = rest.shape[:2]
    ob = core.grid_obj(name, rest, col, uv=True)
    me = ob.data
    keep, rips = wear if wear is not None else (np.ones((nu - 1, nv - 1), dtype=bool), [])
    # distance (in cells) of every vertex from the nearest cut edge, tear or outer side/hem edge: drives fraying
    edge = np.zeros((nu, nv), dtype=bool)
    gone = ~keep
    for da, db in ((0, 0), (1, 0), (0, 1), (1, 1)):
        edge[da:nu - 1 + da, db:nv - 1 + db] |= gone
    edge[0, :] = edge[-1, :] = True
    edge[:, -1] = True
    for c, j0 in rips:
        edge[c, j0 + 1:] = True
    dist = np.where(edge, 0.0, 1e9)
    for _ in range(8):                                               # a few relaxation sweeps are enough for a 10 cm band
        d = dist.copy()
        d[1:, :] = np.minimum(d[1:, :], dist[:-1, :] + 1)
        d[:-1, :] = np.minimum(d[:-1, :], dist[1:, :] + 1)
        d[:, 1:] = np.minimum(d[:, 1:], dist[:, :-1] + 1)
        d[:, :-1] = np.minimum(d[:, :-1], dist[:, 1:] + 1)
        dist = d
    fray = np.clip(dist * CELL / 0.06, 0.0, 1.0)
    fray[:, :hold_rows] = 1.0                                        # the top is tucked away, not torn
    at = me.attributes.new("fray", "FLOAT", "POINT")
    at.data.foreach_set("value", fray.reshape(-1).astype(np.float32))
    if gone.any() or rips:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        dead = [bm.faces[a * (nv - 1) + b_] for a, b_ in zip(*np.nonzero(gone))]
        torn = []
        for c, j0 in rips:                                           # vertex (i, j) of the grid has index i * nv + j
            for j in range(j0, nv - 1):
                e = bm.edges.get((bm.verts[c * nv + j], bm.verts[c * nv + j + 1]))
                if e is not None:
                    torn.append(e)
        if torn:
            bmesh.ops.split_edges(bm, edges=torn)
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(me)
        bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
    ob["grid"] = (nu, nv)
    if mat is not None:
        core.set_mat(ob, mat)
    return ob


def pin(ob, rest_pts, targets, frames=(1, 45)):
    """Pin the vertices that rest at rest_pts and carry them to targets over the given frames
    ('Tuck' shape key). Points whose vertex was cut away are skipped. Returns how many were pinned.
    The move is slow on purpose: yanked in over a few frames, the loose cloth below whips up and
    lands crumpled on whatever ledge it finds."""
    from scipy.spatial import cKDTree
    me = ob.data
    rest_pts, targets = np.asarray(rest_pts, dtype=np.float64).reshape(-1, 3), np.asarray(targets, dtype=np.float64).reshape(-1, 3)
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    dist, idx = cKDTree(co.reshape(-1, 3)).query(rest_pts)
    ok = dist < 1e-4
    if me.shape_keys is None:
        ob.shape_key_add(name="Basis")
    key = ob.shape_key_add(name="Tuck")
    vg = ob.vertex_groups.get("pin") or ob.vertex_groups.new(name="pin")
    vg.add([int(i) for i in idx[ok]], 1.0, "REPLACE")
    for vi, t in zip(idx[ok], targets[ok]):
        key.data[int(vi)].co = t
    key.value = 0.0
    key.keyframe_insert("value", frame=frames[0])
    key.value = 1.0
    key.keyframe_insert("value", frame=frames[1])
    return int(ok.sum())


def cloth(ob, frames=300, bend=0.5, fall_speed=1.0, self_collide=False, quality=10):
    """Cloth settings for a panel on the ~12 mm grid.

    Blender's stock cotton (0.3 kg per vertex, tension 15, bending 0.5, air 1.0) is tuned for a
    grid of about 10 cm. Mass and air drag are per vertex, so on a grid 8 times finer in each
    direction both are divided by 64; the stiffness values already account for spring length and
    stay as they are. Measured on a hip panel: this hangs at its full length and comes to rest.
    What does not work, and why:
      stock mass on the fine grid   64 times too heavy: the cloth does not hang, it falls
      light mass + stiffer springs  (tension 300, bending 0.3 at 3 g) the solver stops converging;
                                    the cloth folds up like an accordion and climbs toward its pins
      light mass + stock air drag   a 3 g vertex sinks at 3 cm/s, gravity loses against every
                                    collision push and the cloth creeps up the body into a wad"""
    mass = 0.3 * (CELL / 0.1) ** 2
    m = ob.modifiers.new("Cloth", "CLOTH")
    s = m.settings
    s.quality = quality
    s.mass = mass
    s.tension_stiffness = 15.0
    s.compression_stiffness = 15.0
    s.shear_stiffness = 5.0
    s.bending_stiffness = bend
    s.tension_damping = s.compression_damping = s.shear_damping = 5.0
    s.bending_damping = 0.5
    s.air_damping = mass * 9.81 / fall_speed          # drag at which a loose vertex falls at fall_speed m/s
    s.vertex_group_mass = "pin"
    s.pin_stiffness = 1.0
    c = m.collision_settings
    c.use_collision = True
    c.collision_quality = 4
    c.distance_min = GAP
    c.friction = 2.0
    c.use_self_collision = self_collide
    c.self_distance_min = 0.003
    c.self_friction = 5.0
    m.point_cache.frame_start, m.point_cache.frame_end = 1, frames
    return m


SKIN = 0.002           # collider's outer skin
GAP = 0.003            # distance the cloth keeps from that skin
SEAT = SKIN + GAP + 0.002      # pinned rows sit this far outside the collider, just clear of both


def collider(ob, friction=2.0):
    """Give ob a collision skin. It must be closed with faces pointing out (see sd/envelope.py):
    cloth is pushed toward the side a face points to."""
    if not any(m.type == "COLLISION" for m in ob.modifiers):
        ob.modifiers.new("Collision", "COLLISION")
    ob.collision.thickness_outer = SKIN
    ob.collision.cloth_friction = friction
    ob.collision.damping = 0.9             # cloth that touches the body should stay there, not bounce
    return ob


def settle(sc, frames=90, report=None):
    """Advance the scene frame by frame so every cloth in it simulates up to 'frames'."""
    sc.frame_start, sc.frame_end = 1, frames
    for f in range(1, frames + 1):
        sc.frame_set(f)
        if report and f % report == 0:
            print(f"    cloth frame {f}/{frames}", flush=True)


def freeze(ob, name, col, thickness=0.0014, subdiv=1):
    """Static copy of a simulated panel as it hangs now, with thickness and a smoothing level for rendering."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = name
    out = bpy.data.objects.new(name, me)
    out.matrix_world = ob.matrix_world.copy()
    col.objects.link(out)
    if subdiv:
        sm = out.modifiers.new("subd", "SUBSURF")
        sm.levels = sm.render_levels = subdiv
        sm.boundary_smooth = "ALL"                    # rounds the grid's stair-steps along torn edges
    if thickness:
        so = out.modifiers.new("solid", "SOLIDIFY")
        so.thickness, so.offset = thickness, 0.0
    return out


# ----------------------------------------------------------------------------- measuring the wearer
class Wearer:
    """Ray-cast helper around the body's collision stand-in."""

    def __init__(self, proxy):
        bpy.context.view_layer.update()
        self.bvh = BVHTree.FromObject(proxy, bpy.context.evaluated_depsgraph_get())

    def back(self, x, z, default=None):
        """y of the back surface at (x, z), looking from behind."""
        hit = self.bvh.ray_cast(Vector((x, 2.0, z)), Vector((0, -1, 0)), 4.0)
        return hit[0].y if hit[0] is not None else default

    def radial(self, phi, z, centre=(0.0, 0.0), default=None):
        """Surface radius around the vertical axis through centre, at azimuth phi (radians; 0 = front,
        pi/2 = the wearer's left) and height z."""
        d = Vector((math.sin(phi), -math.cos(phi), 0.0))
        o = Vector((centre[0], centre[1], z))
        hit = self.bvh.ray_cast(o + d * 1.5, -d, 1.5)
        if hit[0] is None or (hit[0] - o).dot(d) <= 0.0:          # nothing on this side (an opening): the ray went on to the far wall
            return default
        return (hit[0] - o).length


# ----------------------------------------------------------------------------- the Ronin's cloth
def ronin_cape(col, wearer, mat, straps=(), seed=3):
    """Long tattered cape (BACK VIEW of the sheet), seated across the back of the shoulders on
    top of the cowl and falling to the knees. It is kept between the shoulder joints so that it
    hangs clear of the arms in the rest pose.

    straps: (top, bottom) world points of each scabbard's axis. The swords are worn over the
    cape and hold it against the back, so the cloth is pinned to the back along those lines."""
    rng = np.random.default_rng(seed)
    x0, x1 = -0.17, 0.19                                # the seat, between the shoulder joints
    gather = 1.15
    top_w, hem_w = (x1 - x0) * gather, 0.72
    z_top, z_low = 1.645, 0.52
    nu = 52                                             # 8 mm between columns at the seat, 14 mm at the hem
    nv = int(round((z_top - z_low) / CELL)) + 1
    u = np.linspace(0, 1, nu)
    v = np.linspace(0, 1, nv)
    rest = np.zeros((nu, nv, 3))
    xc = (x0 + x1) / 2
    for j in range(nv):
        wdt = top_w + (hem_w - top_w) * v[j] ** 0.85
        rest[:, j, 0] = xc + (u - 0.5) * wdt
        rest[:, j, 1] = 0.32
        rest[:, j, 2] = z_top - v[j] * (z_top - z_low)
    base = (1.0 - u) * 0.26                             # shorter on the wearer's right, as on the sheet
    wear = _ragged_mask(nu, nv, rng, base=base, depth=0.12, notches=5, slits=7, holes=3)
    ob = panel("Ronin_Cape_sim", rest, col, wear, mat=mat)

    def seat_z(x):
        return z_top - 0.04 * (abs(x - 0.01) / 0.18) ** 1.5              # the seat dips toward the shoulders

    src, dst = [], []
    for i in range(nu):
        x = x0 + (x1 - x0) * u[i]
        for j in range(2):
            z = seat_z(x) - j * CELL
            near = [wearer.back(x + ox, z + oz, 0.12) for ox in (-0.015, 0.0, 0.015) for oz in (-0.02, 0.0)]
            src.append(rest[i, j])
            dst.append((x, max(near) + SEAT + 0.002, z))
    dx = (x1 - x0) / (nu - 1)
    done = set()
    for top, bottom in straps:
        top, bottom = Vector(top), Vector(bottom)
        n = max(2, int((top - bottom).length / (CELL * 0.6)))
        for k in range(n + 1):
            p = top.lerp(bottom, k / n)
            i0 = int(round((p.x - x0) / dx))
            j = int(round((seat_z(p.x) - p.z) / CELL))
            if j < 4 or j >= nv or wearer.back(p.x, p.z) is None:        # above the seat, below the hem, or off the body
                continue
            for i in (i0 - 1, i0, i0 + 1):
                x = x0 + i * dx
                near = [wearer.back(x + ox, p.z + oz) for ox in (-0.02, 0.0, 0.02) for oz in (-0.02, 0.0, 0.02)]
                near = [y for y in near if y is not None]
                if 0 <= i < nu and near and (i, j) not in done:      # ride over the bumps around the strap, not into them
                    done.add((i, j))
                    src.append(rest[i, j])
                    dst.append((x, max(near) + SEAT + 0.004, seat_z(x) - j * CELL))
    ob["pinned"] = pin(ob, src, dst)
    cloth(ob)
    return ob


def _belt_panel(name, col, wearer, mat, rng, phi_a, phi_b, z_pin, length, gather, flare, ragged):
    """A panel tucked under the belt along the arc phi_a..phi_b (degrees; 0 = front, +90 = the
    wearer's left), hanging down 'length' metres."""
    pa, pb = math.radians(phi_a), math.radians(phi_b)
    r_mid = wearer.radial((pa + pb) / 2, z_pin, default=0.18)
    arc = abs(pb - pa) * r_mid
    nu = int(round(arc * gather / CELL)) + 1
    nv = int(round(length / CELL)) + 1
    u = np.linspace(0, 1, nu)
    pm = (pa + pb) / 2
    out_dir = np.array([math.sin(pm), -math.cos(pm)])
    tan_dir = np.array([math.cos(pm), math.sin(pm)]) * (1.0 if pb > pa else -1.0)
    rest = np.zeros((nu, nv, 3))
    for j in range(nv):
        w = arc * gather * (1.0 + (flare - 1.0) * j / (nv - 1))
        q = out_dir[None, :] * 0.46 + tan_dir[None, :] * ((u - 0.5) * w)[:, None]
        rest[:, j, 0], rest[:, j, 1], rest[:, j, 2] = q[:, 0], q[:, 1], z_pin - j * CELL
    ob = panel(name, rest, col, _ragged_mask(nu, nv, rng, **ragged), mat=mat)
    src, dst = [], []
    for i in range(nu):
        phi = pa + (pb - pa) * u[i]
        for j in range(2):
            z = z_pin - j * CELL
            r = max(wearer.radial(phi, zz, default=r_mid) for zz in (z, z - 0.02)) + SEAT
            src.append(rest[i, j])
            dst.append((math.sin(phi) * r, -math.cos(phi) * r, z))
    ob["pinned"] = pin(ob, src, dst)
    cloth(ob)
    return ob


def ronin_skirt(col, wearer, mat, seed=21, z_pin=1.205):
    """The ragged hakama cloth round the hips (FRONT VIEW of the sheet): a baggy knee-length
    panel on the wearer's right and a long torn one on the left, both tucked under the belt.
    The pieces do not collide with one another (that makes the solver's dependencies circular),
    so each keeps to its own part of the waist."""
    rng = np.random.default_rng(seed)
    right = _belt_panel("Ronin_SkirtR_sim", col, wearer, mat, rng, -24, -112, z_pin, 0.62, 1.45, 1.2,
                        dict(depth=0.07, notches=3, slits=5, holes=1))
    left = _belt_panel("Ronin_SkirtL_sim", col, wearer, mat, rng, 24, 112, z_pin, 0.88, 1.3, 1.25,
                       dict(depth=0.16, notches=4, slits=6, holes=2))
    return [right, left]


def ronin_tails(col, wearer, mat, seed=11):
    """The long ends of the waist knot (WAIST CLOTH KNOT on the parts sheet): two tapered, ragged
    strips that come off the front of the knot and hang between the legs."""
    rng = np.random.default_rng(seed)
    out = []
    #        side, top width, hem width, length
    specs = [(+1, 0.060, 0.15, 0.90), (-1, 0.055, 0.13, 0.72)]
    z_pin = 1.178
    r_knot = wearer.radial(0.0, 1.205, default=0.19)                  # front face of the knot
    for n, (side, w0, w1, length) in enumerate(specs):
        nu = int(round(w1 / CELL)) + 1
        nv = int(round(length / CELL)) + 1
        u = np.linspace(0, 1, nu)
        rest = np.zeros((nu, nv, 3))
        cx = side * 0.036
        for j in range(nv):
            t = j / (nv - 1)
            wdt = w0 + (w1 - w0) * min(1.0, t / 0.55) ** 0.9
            rest[:, j, 0] = cx * (1.0 + 0.8 * t) + (u - 0.5) * wdt       # the two ends drift apart as they fall
            rest[:, j, 1] = -(r_knot + 0.10)
            rest[:, j, 2] = z_pin - j * CELL
        wear = _ragged_mask(nu, nv, rng, depth=0.07, notches=2, slits=2, holes=0)       # a narrow strip: cut it gently or it falls to threads
        ob = panel(f"Ronin_Tail{n + 1}_sim", rest, col, wear, mat=mat)
        src, dst = [], []
        for i in range(nu):
            x = cx + (u[i] - 0.5) * w0
            phi = math.atan2(x, r_knot)
            for j in range(2):                 # seated on the lower front of the knot, like its tied ends, clear of everything behind
                z = z_pin - j * CELL
                r = max(wearer.radial(phi, zz, default=0.0) for zz in (z + 0.02, z, z - 0.03, z - 0.06)) + SEAT
                r = max(r, r_knot * 0.9)
                src.append(rest[i, j])
                dst.append((x, -math.sqrt(max(1e-6, r * r - x * x)), z))
        ob["pinned"] = pin(ob, src, dst)
        cloth(ob, bend=0.3)
        out.append(ob)
    return out
