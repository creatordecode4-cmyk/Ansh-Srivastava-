"""Falling petals and snow without any simulation, and static petals on the floor (Blender 5.3 Geometry Nodes).

Falling fields are a closed-form function of ONE number, the modifier input `story_time` (seconds):
    position(i, t) = wrap_in_box( start_i + wind * t + gust(t, start_i) + sway_i(t) - (0, 0, speed_i * t) )
    rotation(i, t) = spin about a random axis by (phase_i + rate_i * t), applied to a random start orientation
Every per-point value comes from a seeded Random Value node with ID = point index, so the same story_time always
gives exactly the same points (also in another process), time can run at any rate, stop, or go backwards, and
slow motion is only a different animation curve on story_time.

    build_petals(bounds, count, seed, name)          -> Object   (instances of a curved petal, MAT_Petal)
    build_snow(bounds, count, seed, name)            -> Object   (instances of a tiny soft flake, MAT_Snow)
    scatter_ground_petals(x_range, y_range, ...)     -> Object   (static instances lying on the floor)
    key_story_time(obj, frame_start, frame_end, fps)             story_time = (frame - frame_start) / fps
    set_story_time(obj, seconds) / get_story_time(obj) / story_time_path(obj)

How story_time is exposed: the object has one Geometry Nodes modifier named "FallField"; its node group has the
float input `story_time`. In Blender 5.3 that input lives at
    obj.modifiers["FallField"].properties.inputs.<identifier>.value
and the identifier / RNA path are also stored on the object as obj["story_time_socket"] / obj["story_time_path"].
Other modifier inputs (not time): `wind` (m/s, vector) and `size_scale`.
"""
import math

import bmesh
import bpy
import numpy as np

from . import common, materials

TAU = 2.0 * math.pi
MOD_NAME = "FallField"


# ------------------------------------------------------------------------------------------------ meshes
def _petal_mesh(name, flat=1.0):
    """One cherry petal, length 1 along +Y, centred on its middle, cupped upwards (+Z), notched tip. 18 triangles."""
    w = 0.37
    rows = [(0.30, 0.55), (0.60, 1.0), (0.85, 0.92)]
    verts, faces = [], []

    def z_of(x, t):
        return flat * (0.50 * (t - 0.47) ** 2 + 0.55 * x * x)

    def add(x, t):
        verts.append((x, t - 0.5, z_of(x, t)))
        return len(verts) - 1

    base = add(0.0, 0.0)
    prev = None
    for (t, k) in rows:
        cur = (add(-w * k, t), add(0.0, t), add(w * k, t))
        if prev is None:
            faces.append((base, cur[1], cur[0]))
            faces.append((base, cur[2], cur[1]))
        else:
            faces.append((prev[0], prev[1], cur[1], cur[0]))
            faces.append((prev[1], prev[2], cur[2], cur[1]))
        prev = cur
    tl, notch, tr = add(-w * 0.45, 1.0), add(0.0, 0.91), add(w * 0.45, 1.0)
    faces.append((prev[0], prev[1], notch, tl))
    faces.append((prev[1], prev[2], tr, notch))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.shade_smooth()
    return me


def _flake_mesh(name, seed):
    """A tiny irregular clump of snow, about 1 across (20 triangles, smooth)."""
    R = common.rng(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
    for v in bm.verts:
        v.co *= R.uniform(0.78, 1.15)
        v.co.z *= 0.8
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    return me


# ------------------------------------------------------------------------------------------------ node writer
class _G:
    def __init__(self, tree):
        self.t = tree
        self.i = 0

    def node(self, idname, **props):
        n = self.t.nodes.new(idname)
        n.location = (220 * (self.i % 12), -180 * (self.i // 12))
        self.i += 1
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        n = self.node("ShaderNodeMath", operation=op)
        for s, v in zip(n.inputs, (a, b, c)):
            self.put(s, v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs["Scale"], scale)
        return n.outputs["Value"] if op in {"DOT_PRODUCT", "LENGTH", "DISTANCE"} else n.outputs["Vector"]

    def comb(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for s, v in zip(n.inputs, (x, y, z)):
            self.put(s, v)
        return n.outputs[0]

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], v)
        return n.outputs

    def rand(self, lo, hi, seed, index, vector=False):
        n = self.node("FunctionNodeRandomValue", data_type="FLOAT_VECTOR" if vector else "FLOAT")
        self.put(n.inputs["Min"], lo)
        self.put(n.inputs["Max"], hi)
        self.put(n.inputs["ID"], index)
        n.inputs["Seed"].default_value = int(seed)
        return n.outputs["Value"]


def _time_item(obj):
    md = obj.modifiers.get(MOD_NAME)
    if md is None or "story_time_socket" not in obj:
        raise ValueError(f"{obj.name} has no story_time input (not built by particles.build_petals / build_snow)")
    return getattr(md.properties.inputs, obj["story_time_socket"])


def story_time_path(obj):
    """RNA path (relative to the object) of the story_time value, for drivers and f-curves."""
    return _time_item(obj).path_from_id("value")


def set_story_time(obj, seconds):
    _time_item(obj).value = float(seconds)
    obj.update_tag()


def get_story_time(obj):
    return _time_item(obj).value


# ------------------------------------------------------------------------------------------------ falling field
def _fall_field(name, mesh, bounds, count, seed, speed, sway, sway_hz, flutter, spin, size, wind, gust, gust_period):
    (x0, y0, z0), (x1, y1, z1) = bounds
    lo = (float(x0), float(y0), float(z0))
    ext = (float(x1 - x0), float(y1 - y0), float(z1 - z0))
    obj = common.mesh_object(name, mesh)
    ng = bpy.data.node_groups.new(name + "_nodes", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    s_time = ng.interface.new_socket("story_time", in_out="INPUT", socket_type="NodeSocketFloat")
    s_time.description = "Seconds of story time; the only time input of this field"
    s_wind = ng.interface.new_socket("wind", in_out="INPUT", socket_type="NodeSocketVector")
    s_wind.default_value = tuple(float(v) for v in wind)
    s_size = ng.interface.new_socket("size_scale", in_out="INPUT", socket_type="NodeSocketFloat")
    s_size.default_value = 1.0
    s_size.min_value = 0.0
    g = _G(ng)
    gi = g.node("NodeGroupInput")
    go = g.node("NodeGroupOutput")
    idx = g.node("GeometryNodeInputIndex").outputs[0]
    t = gi.outputs["story_time"]
    sd = int(seed) * 101

    start = g.rand(lo, tuple(lo[k] + ext[k] for k in range(3)), sd + 0, idx, vector=True)
    spd = g.rand(speed[0], speed[1], sd + 1, idx)
    amp = g.rand(sway[0], sway[1], sd + 2, idx)
    w1 = g.rand(sway_hz[0] * TAU, sway_hz[1] * TAU, sd + 3, idx)
    ph1 = g.rand((0.0, 0.0, 0.0), (TAU, TAU, TAU), sd + 4, idx, vector=True)
    ph2 = g.rand((0.0, 0.0, 0.0), (TAU, TAU, TAU), sd + 5, idx, vector=True)
    # own slow sway: two sine waves per axis with unrelated periods
    a = g.math("MULTIPLY", t, w1)
    s1 = g.vmath("SINE", g.vmath("ADD", ph1, g.vmath("SCALE", (1.0, 0.83, 1.31), scale=a)))
    s2 = g.vmath("SINE", g.vmath("ADD", ph2, g.vmath("SCALE", (2.1, 1.7, 2.6), scale=a)))
    sw = g.vmath("ADD", s1, g.vmath("SCALE", s2, scale=0.22))
    sw = g.vmath("MULTIPLY", g.vmath("SCALE", sw, scale=amp), (1.0, 1.0, float(flutter)))
    # common wind plus a slow gust that travels through the box
    gph = g.vmath("DOT_PRODUCT", start, (0.21, 0.17, 0.05))
    gs = g.math("SINE", g.math("ADD", g.math("MULTIPLY", t, TAU / float(gust_period)), gph))
    drift = g.vmath("ADD", g.vmath("SCALE", gi.outputs["wind"], scale=t), g.vmath("SCALE", tuple(float(v) for v in gust), scale=gs))
    fall = g.comb(0.0, 0.0, g.math("MULTIPLY", g.math("MULTIPLY", spd, t), -1.0))
    raw = g.vmath("ADD", g.vmath("ADD", start, sw), g.vmath("ADD", drift, fall))
    rel = g.sep(g.vmath("SUBTRACT", raw, lo))
    pos = g.comb(*[g.math("ADD", g.math("FLOORED_MODULO", rel[k], ext[k]), lo[k]) for k in range(3)])
    pts = g.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = int(count)
    g.put(pts.inputs["Position"], pos)
    pts.inputs["Radius"].default_value = 0.01
    # tumbling
    axis = g.vmath("NORMALIZE", g.rand((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0), sd + 6, idx, vector=True))
    ang = g.math("ADD", g.rand(0.0, TAU, sd + 7, idx), g.math("MULTIPLY", g.rand(spin[0], spin[1], sd + 8, idx), t))
    r_spin = g.node("FunctionNodeAxisAngleToRotation")
    g.put(r_spin.inputs["Axis"], axis)
    g.put(r_spin.inputs["Angle"], ang)
    r0 = g.node("FunctionNodeEulerToRotation")
    g.put(r0.inputs["Euler"], g.rand((0.0, 0.0, 0.0), (TAU, TAU, TAU), sd + 9, idx, vector=True))
    rot = g.node("FunctionNodeRotateRotation")
    g.put(rot.inputs["Rotation"], r0.outputs[0])
    g.put(rot.inputs["Rotate By"], r_spin.outputs[0])
    scl = g.math("MULTIPLY", g.rand(size[0], size[1], sd + 10, idx), gi.outputs["size_scale"])
    inst = g.node("GeometryNodeInstanceOnPoints")
    g.put(inst.inputs["Points"], pts.outputs[0])
    g.put(inst.inputs["Instance"], gi.outputs["Geometry"])
    g.put(inst.inputs["Rotation"], rot.outputs[0])
    g.put(inst.inputs["Scale"], g.comb(scl, scl, scl))
    g.put(go.inputs["Geometry"], inst.outputs[0])

    md = obj.modifiers.new(MOD_NAME, "NODES")
    md.node_group = ng
    obj["story_time_socket"] = s_time.identifier
    obj["wind_socket"] = s_wind.identifier
    obj["size_scale_socket"] = s_size.identifier
    obj["story_time_path"] = story_time_path(obj)
    obj["count"] = int(count)
    obj["seed"] = int(seed)
    obj["bounds"] = [list(lo), [lo[k] + ext[k] for k in range(3)]]
    set_story_time(obj, 0.0)
    return obj


def build_petals(bounds=((-14.0, -15.0, 0.0), (14.0, 17.0, 11.0)), count=2500, seed=1, name="FX_Petals", *,
                 speed=(0.6, 1.3), sway=(0.10, 0.32), sway_hz=(0.15, 0.40), spin=(1.2, 5.0), size=(0.015, 0.025),
                 wind=(0.45, -0.25, 0.0), gust=(0.30, 0.18, 0.0), gust_period=7.0):
    """Falling cherry petals filling the box `bounds` ((x0, y0, z0), (x1, y1, z1)). `count` points; each falls at
    its own speed (m/s), drifts with the common wind, sways, tumbles and wraps around so the box stays evenly
    filled. Petal length `size` in metres. Driven only by the modifier input story_time (see module docstring)."""
    mesh = _petal_mesh(name + "_shape")
    mesh.materials.append(materials.get("MAT_Petal"))
    return _fall_field(name, mesh, bounds, count, seed, speed, sway, sway_hz, 0.10, spin, size, wind, gust, gust_period)


def build_snow(bounds=((-16.0, -16.0, 0.0), (16.0, 18.0, 12.0)), count=3000, seed=2, name="FX_Snow", *,
               speed=(0.3, 0.7), sway=(0.20, 0.55), sway_hz=(0.10, 0.30), spin=(0.3, 1.5), size=(0.004, 0.008),
               wind=(0.45, -0.25, 0.0), gust=(0.40, 0.25, 0.0), gust_period=7.0):
    """Light snow: tiny soft flakes (diameter `size` in metres), slower and with more sway than the petals.
    Same mechanism and the same story_time input as build_petals."""
    mesh = _flake_mesh(name + "_shape", 7000 + int(seed))
    mesh.materials.append(materials.get("MAT_Snow"))
    return _fall_field(name, mesh, bounds, count, seed, speed, sway, sway_hz, 0.06, spin, size, wind, gust, gust_period)


# ------------------------------------------------------------------------------------------------ ground petals
def scatter_ground_petals(x_range, y_range, count=1500, seed=3, clear_center=None, name="FX_GroundPetals", *,
                          z=0.0, size=(0.015, 0.025), edge_bias=2.2, clump_share=0.35):
    """Static petals lying flat on the floor inside x_range x y_range (metres), 2-4 mm above `z`, random turn,
    a slight tilt, about one in three face down. Denser towards the edges of the rectangle (edge_bias) and partly
    gathered in small drifts (clump_share). clear_center = (x, y, radius) or a radius around (0, 0): no petals
    inside, thinning out to 1.6 x radius. One object: the mesh holds one petal plus one loose vertex per petal
    (attributes `rot`, `scl`), a Geometry Nodes modifier instances the petal on those vertices."""
    R = common.rng(int(seed) * 7919 + 17)
    x0, x1 = float(min(x_range)), float(max(x_range))
    y0, y1 = float(min(y_range)), float(max(y_range))
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    if clear_center is None:
        clear = None
    elif isinstance(clear_center, (int, float)):
        clear = (0.0, 0.0, float(clear_center))
    else:
        clear = tuple(float(v) for v in clear_center)

    def keep(x, y, edge=True):
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        if clear is not None:
            d = math.hypot(x - clear[0], y - clear[1])
            if d < clear[2]:
                return False
            if d < clear[2] * 1.6 and R.random() > (d - clear[2]) / (clear[2] * 0.6):
                return False
        if edge:
            e = max(abs(x - cx) / hx, abs(y - cy) / hy)
            return R.random() < 0.10 + 0.90 * e ** edge_bias
        return True

    def sample():
        for _ in range(10000):
            x, y = R.uniform(x0, x1), R.uniform(y0, y1)
            if keep(x, y):
                return x, y
        return R.uniform(x0, x1), R.uniform(y0, y1)

    pts = []
    n_clump = int(count * clump_share)
    while len(pts) < n_clump:
        mx, my = sample()
        rad = R.uniform(0.15, 0.55)
        for _ in range(R.randint(6, 22)):
            x, y = R.gauss(mx, rad), R.gauss(my, rad * R.uniform(0.5, 1.0))
            if len(pts) < n_clump and keep(x, y, edge=False):
                pts.append((x, y))
    while len(pts) < count:
        pts.append(sample())

    shape = _petal_mesh("_petal_tmp", flat=0.45)
    sv = np.array([v.co[:] for v in shape.vertices], dtype=np.float32)
    sf = [tuple(p.vertices) for p in shape.polygons]
    bpy.data.meshes.remove(shape)
    cup = float(sv[:, 2].max())
    n_s = len(sv)
    co = np.zeros((n_s + count, 3), dtype=np.float32)
    co[:n_s] = sv
    rot = np.zeros((n_s + count, 3), dtype=np.float32)
    scl = np.ones((n_s + count, 3), dtype=np.float32)
    flag = np.zeros(n_s + count, dtype=bool)
    flag[:n_s] = True
    for i, (x, y) in enumerate(pts):
        s = R.uniform(*size)
        down = R.random() < 0.35
        tilt_x, tilt_y = R.uniform(-0.07, 0.07), R.uniform(-0.07, 0.07)
        co[n_s + i] = (x, y, z + R.uniform(0.002, 0.004) + (cup * s if down else 0.0) + 0.5 * s * (abs(tilt_x) + abs(tilt_y)))
        rot[n_s + i] = (tilt_x + (math.pi if down else 0.0), tilt_y, R.uniform(0.0, TAU))
        scl[n_s + i] = (s, s, s)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in co], [], sf)
    me.update()
    me.shade_smooth()
    me.attributes.new("is_shape", "BOOLEAN", "POINT").data.foreach_set("value", flag)
    me.attributes.new("rot", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", rot.ravel())
    me.attributes.new("scl", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", scl.ravel())
    me.materials.append(materials.get("MAT_Petal"))
    obj = common.mesh_object(name, me)

    ng = bpy.data.node_groups.new(name + "_nodes", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    g = _G(ng)
    gi = g.node("NodeGroupInput")
    go = g.node("NodeGroupOutput")

    def attr(aname, dtype):
        n = g.node("GeometryNodeInputNamedAttribute", data_type=dtype)
        n.inputs["Name"].default_value = aname
        return n.outputs["Attribute"]

    sepg = g.node("GeometryNodeSeparateGeometry", domain="POINT")
    g.put(sepg.inputs["Geometry"], gi.outputs["Geometry"])
    g.put(sepg.inputs["Selection"], attr("is_shape", "BOOLEAN"))
    m2p = g.node("GeometryNodeMeshToPoints")
    g.put(m2p.inputs["Mesh"], sepg.outputs["Inverted"])
    e2r = g.node("FunctionNodeEulerToRotation")
    g.put(e2r.inputs["Euler"], attr("rot", "FLOAT_VECTOR"))
    inst = g.node("GeometryNodeInstanceOnPoints")
    g.put(inst.inputs["Points"], m2p.outputs["Points"])
    g.put(inst.inputs["Instance"], sepg.outputs["Selection"])
    g.put(inst.inputs["Rotation"], e2r.outputs[0])
    g.put(inst.inputs["Scale"], attr("scl", "FLOAT_VECTOR"))
    g.put(go.inputs["Geometry"], inst.outputs[0])
    md = obj.modifiers.new("GroundPetals", "NODES")
    md.node_group = ng
    obj["count"] = int(count)
    obj["seed"] = int(seed)
    return obj


# ------------------------------------------------------------------------------------------------ time
def key_story_time(obj, frame_start=1001, frame_end=1720, fps=24):
    """Keyframe story_time linearly: story_time = (frame - frame_start) / fps, linear extrapolation both ways.
    Replaces any earlier story_time animation of the object. Returns the f-curve."""
    from bpy_extras import anim_utils

    item = _time_item(obj)
    path = item.path_from_id("value")
    ad = obj.animation_data
    if ad is not None and ad.action is not None and ad.action_slot is not None:
        bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        if bag is not None:
            for fc in [f for f in bag.fcurves if f.data_path == path]:
                bag.fcurves.remove(fc)
    item.value = 0.0
    item.keyframe_insert("value", frame=frame_start)
    item.value = (frame_end - frame_start) / float(fps)
    item.keyframe_insert("value", frame=frame_end)
    ad = obj.animation_data
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    curve = None
    for fc in bag.fcurves:
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.extrapolation = "LINEAR"
            fc.update()
            curve = fc
    obj["story_time_keyed"] = [int(frame_start), int(frame_end), float(fps)]
    return curve
