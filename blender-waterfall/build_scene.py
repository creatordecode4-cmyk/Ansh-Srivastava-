"""
Waterfall valley - procedural Blender scene (bpy 5.x).

STEP 1: geometry + clay override (this file, --step 1)
Later steps add materials, lighting, animation and render settings.

Run headless:
    python build_scene.py --step 1 --still renders/step1_clay.png
or inside Blender:  blender -b -P build_scene.py -- --step 1
Units: metres. Axes: +X right, +Y into the valley (camera looks +Y), +Z up.
"""
import bpy, bmesh, math, random, sys, os, argparse
from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--still", default="")
ap.add_argument("--frame", type=int, default=1)
ap.add_argument("--res", type=int, default=640)
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--save", default=os.path.join(HERE, "waterfall_valley.blend"))
args = ap.parse_args(argv)

random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- collections
COLS = {}
for name in ["Terrain", "Water", "Rocks", "Vegetation", "Birds", "Lights", "Camera"]:
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    COLS[name] = c

def link(obj, col):
    COLS[col].objects.link(obj)
    return obj

def mesh_obj(name, verts, faces, col, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.shade_smooth()
    return link(bpy.data.objects.new(name, me), col)

def fbm(p, octaves=4, lac=2.0, gain=0.5):
    a, f, s = 1.0, 1.0, 0.0
    for _ in range(octaves):
        s += a * noise.noise(Vector(p) * f)
        a *= gain; f *= lac
    return s

def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)

# ---------------------------------------------------------------- layout
CLIFF_TOP = 47.0           # height of the back cliff rim
FALL_X = 9.0               # waterfall x position (center-right, as in clay A)

def cliff_y(x):
    """Back cliff line: amphitheatre; right wall swings toward the camera."""
    y = 64.0 + 0.004 * (x - FALL_X) ** 2
    if x > FALL_X + 6:
        y -= 1.1 * (x - FALL_X - 6) ** 1.15
    return y

def cliff_h(x):
    """Cliff rim height: tall left wall, low saddle in the centre (distant
    peaks show through), tall right wall that the waterfall pours from."""
    h = 47.0
    h -= 19.0 * math.exp(-((x + 8.0) / 11.0) ** 2)          # centre saddle
    h -= 6.0 * math.exp(-((x - FALL_X) / 3.0) ** 2)          # waterfall notch
    return h + 3.0 * fbm((x * 0.04, 0.0, 1.0), 2)

def river_cx(y):
    """River centreline: from the plunge pool (FALL_X, ~58) toward camera."""
    t = smooth(58, -40, y)
    return FALL_X * (1 - t) + (-2.0) * t + 3.0 * math.sin(y * 0.06)

def river_w(y):
    return 7.0 + 9.0 * smooth(55, 0, y)        # widens toward the camera

def ground_h(x, y):
    # base meadow/riverbank level
    h = 0.6 + 0.6 * fbm((x * 0.04, y * 0.04, 0.3), 3)
    # river channel
    d = abs(x - river_cx(y))
    w = river_w(y)
    h -= 1.9 * (1 - smooth(w * 0.55, w * 1.05, d))
    # left grassy slope rising to the left cliffs
    h += max(0.0, -x - 14) ** 1.35 * 0.32 * smooth(-30, 10, y)
    # right bank slope
    h += max(0.0, x - 26) ** 1.25 * 0.28 * smooth(-10, 30, y)
    # plateau behind the cliff rim
    cy = cliff_y(x)
    h = max(h, cliff_h(x) * smooth(cy - 1.0, cy + 2.0, y) + 2.5 * fbm((x * 0.05, y * 0.05, 2.0), 3))
    return h

# ---------------------------------------------------------------- terrain
def build_terrain():
    x0, x1, y0, y1, step = -130.0, 130.0, -60.0, 150.0, 0.9
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    verts, faces = [], []
    for j in range(ny):
        y = y0 + j * step
        for i in range(nx):
            x = x0 + i * step
            verts.append((x, y, ground_h(x, y)))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    return mesh_obj("TER_Ground", verts, faces, "Terrain")

def build_cliff():
    """Vertical layered cliff wall following cliff_y(), with strata ledges."""
    xs = [x * 0.6 for x in range(int(-110 / 0.6), int(120 / 0.6))]
    NZ = 130
    ts = [k / (NZ - 1) for k in range(NZ)]
    verts, faces = [], []
    for x in xs:
        cy = cliff_y(x)
        # outward normal of the curve (toward camera)
        dydx = 2 * 0.0045 * (x - FALL_X)
        nrm = Vector((dydx, -1.0, 0.0)).normalized()
        top = cliff_h(x) + 1.5
        for t in ts:
            z = -2.5 + t * (top + 2.5)
            # strata: horizontal bands with ledges and overhang variation
            band = (z / 3.2) + 0.4 * fbm((x * 0.03, 0, z * 0.02), 2)
            frac = band - math.floor(band)
            ledge = 0.35 * (frac ** 3)                      # sharp step at each layer
            bulge = 4.5 * fbm((x * 0.06, z * 0.01, 5.0), 4)  # vertical rounded columns
            bulge += 1.5 * fbm((x * 0.02, z * 0.02, 3.0), 2)
            detail = 0.35 * fbm((x * 0.25, z * 0.25, 9.0), 3)
            # notch where the waterfall cuts the rim
            notch = -3.0 * math.exp(-((x - FALL_X) / 4.0) ** 2) * smooth(top - 14, top, z)
            off = ledge + bulge + detail + notch
            # cliff leans back slightly near the top
            lean = -0.06 * z
            p = Vector((x, cy, z)) + nrm * (off - lean)
            verts.append(p[:])
    nz = NZ
    for i in range(len(xs) - 1):
        for k in range(nz - 1):
            a = i * nz + k
            faces.append((a, a + nz, a + nz + 1, a + 1))
    return mesh_obj("TER_Cliff", verts, faces, "Terrain")

def build_mountains():
    """Distant peaks behind the cliff (seen through the gap on the left)."""
    objs = []
    peaks = [(-60, 520, 260, 200), (-5, 600, 330, 230), (70, 560, 240, 180),
             (150, 500, 200, 170), (-150, 480, 210, 180)]
    for idx, (px, py, ph, pr) in enumerate(peaks):
        verts, faces = [], []
        n = 48
        for j in range(n + 1):
            for i in range(n + 1):
                u, v = i / n * 2 - 1, j / n * 2 - 1
                x, y = px + u * pr * 1.6, py + v * pr
                r = math.sqrt(u * u + v * v)
                ridge = 1 - abs(fbm((x * 0.012, y * 0.012, idx), 4))
                h = ph * max(0.0, 1 - r) ** 1.4 * (0.75 + 0.35 * ridge)
                verts.append((x, y, h))
        for j in range(n):
            for i in range(n):
                a = j * (n + 1) + i
                faces.append((a, a + 1, a + n + 2, a + n + 1))
        objs.append(mesh_obj(f"TER_Mountain_{idx}", verts, faces, "Terrain"))
    return objs

# ---------------------------------------------------------------- water
def build_water():
    # river surface: plane following the channel
    verts, faces = [], []
    ys = [y * 1.0 for y in range(-60, 61)]
    nu = 24
    for y in ys:
        w = river_w(y) * 1.15
        for i in range(nu + 1):
            u = i / nu * 2 - 1
            verts.append((river_cx(y) + u * w, y, -0.35))
    for j in range(len(ys) - 1):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    river = mesh_obj("WAT_River", verts, faces, "Water")

    # waterfall: a ribbon from the rim notch down to the pool, with a slight arc
    verts, faces = [], []
    nz, nu = 60, 12
    top_y = cliff_y(FALL_X) - 3.0
    for k in range(nz + 1):
        t = k / nz
        ztop = cliff_h(FALL_X) - 0.5
        z = ztop - t * (ztop + 0.3)
        y = top_y - 1.6 * math.sin(t * math.pi * 0.5) - 0.8 * t   # slight outward arc
        w = 3.2 + 2.6 * t                                           # spreads as it falls
        for i in range(nu + 1):
            u = i / nu * 2 - 1
            x = FALL_X + u * w + 0.5 * math.sin(z * 0.3)
            yy = y - 0.6 * (1 - u * u)                               # rounded front
            verts.append((x, yy, z))
    for k in range(nz):
        for i in range(nu):
            a = k * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    fall = mesh_obj("WAT_Waterfall", verts, faces, "Water")
    return river, fall

# ---------------------------------------------------------------- rocks
def make_rock_mesh(name, seed, sub=3):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in bm.verts:
        p = v.co
        d = 0.28 * fbm(p * 0.9 + off, 3) + 0.06 * fbm(p * 3 + off, 2)
        v.co = p * (1 + d)
        v.co.z *= 0.62                       # river boulders are flattish
        if v.co.z < -0.25:                   # flat-ish bottom
            v.co.z = -0.25 + (v.co.z + 0.25) * 0.2
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.shade_smooth()
    return me

def build_rocks():
    meshes = [make_rock_mesh(f"RCK_mesh_{i}", i) for i in range(8)]
    placed = []

    def put(x, y, s, rz=None, sink=0.08):
        me = random.choice(meshes)
        o = link(bpy.data.objects.new(f"RCK_{len(placed):03d}", me), "Rocks")
        z = ground_h(x, y)
        o.location = (x, y, max(z, -1.2) - sink * s)
        o.rotation_euler = (random.uniform(-.15, .15), random.uniform(-.15, .15),
                            rz if rz is not None else random.uniform(0, 6.28))
        o.scale = (s * random.uniform(0.9, 1.4), s * random.uniform(0.8, 1.2), s)
        placed.append(o)

    # hero boulders (clay A: big pale rocks lower-right and centre)
    put(9.0, -4.0, 2.6); put(-5.5, 2.0, 2.6); put(-11.0, 6.0, 2.0)
    put(2.5, 6.0, 1.5); put(14.0, 10.0, 1.8); put(-17.0, 0.0, 2.2); put(20.0, 14.0, 1.6)
    # dense riverbed stones across the foreground and up to the pool
    for _ in range(260):
        y = random.uniform(-12, 58)
        cx = river_cx(y)
        w = river_w(y)
        x = cx + random.gauss(0, w * 0.75)
        far = smooth(-30, 58, y)
        s = random.uniform(0.25, 1.1) * (1.2 - 0.5 * far)
        put(x, y, s)
    # dry gravel bank + scattered boulders in the foreground
    for _ in range(110):
        put(random.uniform(-24, 26), random.uniform(-20, 2), random.uniform(0.2, 1.3))
    # pool rim boulders under the waterfall
    for _ in range(40):
        a = random.uniform(math.pi * 1.05, math.pi * 1.95)
        r = random.uniform(6, 12)
        put(FALL_X + math.cos(a) * r * 1.4, 58 + math.sin(a) * r * 0.6 + 4, random.uniform(0.6, 1.6))
    # talus at the cliff base
    for _ in range(70):
        x = random.uniform(-60, 70)
        put(x, cliff_y(x) - random.uniform(1, 6), random.uniform(0.5, 1.8))
    return placed

# ---------------------------------------------------------------- vegetation
def make_pine_mesh(name, seed, tiers=11):
    rnd = random.Random(seed)
    bm = bmesh.new()
    # trunk
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.22, radius2=0.06, depth=10.0,
                          matrix=__import__("mathutils").Matrix.Translation((0, 0, 5.0)))
    # stacked drooping branch tiers
    for t in range(tiers):
        f = t / (tiers - 1)
        z = 1.8 + f * 8.0
        r = (1 - f) * 2.4 + 0.35
        depth = 1.9 - f * 0.7
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=r, radius2=0.02, depth=depth,
                                    matrix=__import__("mathutils").Matrix.Translation((0, 0, z + depth / 2)))
        for v in res["verts"]:
            if v.co.z < z + 0.05:            # jagged branch tips
                k = 1 + 0.35 * rnd.uniform(-1, 1)
                v.co.x *= k; v.co.y *= k
                v.co.z -= 0.35 * rnd.random()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    return me

def make_bush_mesh(name, seed):
    rnd = random.Random(seed)
    bm = bmesh.new()
    for _ in range(6):
        m = __import__("mathutils").Matrix.Translation((rnd.uniform(-.7, .7), rnd.uniform(-.7, .7), rnd.uniform(.3, .8)))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rnd.uniform(.5, .9), matrix=m)
    for v in bm.verts:
        v.co *= 1 + 0.25 * noise.noise(v.co * 2.5 + Vector((seed, 0, 0)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.shade_smooth()
    return me

def build_vegetation():
    pines = [make_pine_mesh(f"VEG_pine_mesh_{i}", i) for i in range(4)]
    bushes = [make_bush_mesh(f"VEG_bush_mesh_{i}", i) for i in range(4)]
    trees, shrubs = [], []

    def tree(x, y, h):
        o = link(bpy.data.objects.new(f"VEG_Pine_{len(trees):03d}", random.choice(pines)), "Vegetation")
        o.location = (x, y, ground_h(x, y) - 0.2)
        s = h / 10.5
        o.scale = (s * random.uniform(.85, 1.1), s * random.uniform(.85, 1.1), s)
        o.rotation_euler.z = random.uniform(0, 6.28)
        trees.append(o)

    def bush(x, y, s):
        o = link(bpy.data.objects.new(f"VEG_Bush_{len(shrubs):03d}", random.choice(bushes)), "Vegetation")
        o.location = (x, y, ground_h(x, y) - 0.15)
        o.scale = (s, s, s * random.uniform(.7, 1.0))
        o.rotation_euler.z = random.uniform(0, 6.28)
        shrubs.append(o)

    # hero pine mid-left (clay A ~x=0.43 of frame)
    tree(-10.0, 24.0, 19.0)
    tree(-14.0, 30.0, 14.0)
    # left forested slope + left cliff top
    for _ in range(140):
        x = random.uniform(-95, -30); y = random.uniform(10, 75)
        if y < cliff_y(x) - 2:
            tree(x, y, random.uniform(8, 18))
    # cliff-top forest along the rim (dense dark band in clay A)
    for _ in range(260):
        x = random.uniform(-100, 110)
        y = cliff_y(x) + random.uniform(2, 40)
        if abs(x - FALL_X) > 5:
            tree(x, y, random.uniform(7, 15))
    # right bank sparse trees
    for _ in range(12):
        x = random.uniform(28, 70); y = random.uniform(10, 40)
        if y < cliff_y(x) - 3:
            tree(x, y, random.uniform(8, 14))
    # bushes on banks and slopes
    for _ in range(220):
        side = random.choice([-1, 1])
        y = random.uniform(-35, 60)
        x = river_cx(y) + side * (river_w(y) * random.uniform(1.0, 3.2))
        bush(x, y, random.uniform(.5, 1.4))
    for _ in range(120):
        bush(random.uniform(-70, -15), random.uniform(-30, 60), random.uniform(.6, 1.6))
    return trees, shrubs

# ---------------------------------------------------------------- camera / light
def build_camera():
    cam_data = bpy.data.cameras.new("CAM_Main")
    cam_data.lens = 24.0
    cam_data.sensor_width = 36.0
    cam = link(bpy.data.objects.new("CAM_Main", cam_data), "Camera")
    cam.location = (-2.0, -26.0, ground_h(-2.0, -26.0) + 2.3)
    tgt = link(bpy.data.objects.new("CAM_Target", None), "Camera")
    tgt.location = (-12.0, 60.0, 11.0)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    scene.camera = cam
    return cam, tgt

def build_clay_light():
    sun_d = bpy.data.lights.new("LGT_Sun_Key", "SUN")
    sun_d.energy = 4.5
    sun_d.angle = math.radians(1.5)
    sun = link(bpy.data.objects.new("LGT_Sun_Key", sun_d), "Lights")
    # sun high, upper-left, slightly back-lit (as in colour ref)
    sun.rotation_euler = (math.radians(40), math.radians(0), math.radians(-150))
    world = bpy.data.worlds.new("WLD_Sky")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.8, 0.85, 0.9, 1)
    bg.inputs["Strength"].default_value = 0.6

def clay_override():
    m = bpy.data.materials.new("MAT_Clay")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
    b.inputs["Roughness"].default_value = 0.8
    bpy.context.view_layer.material_override = m
    return m

def render_settings(res_x, samples):
    r = scene.render
    r.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.max_bounces = 5
    r.resolution_x = res_x
    r.resolution_y = int(res_x * 9 / 16)
    r.resolution_percentage = 100
    r.fps = 24
    scene.frame_start, scene.frame_end = 1, 480
    scene.view_settings.view_transform = "AgX"

# ---------------------------------------------------------------- main
build_terrain(); build_cliff(); build_mountains()
build_water(); build_rocks(); build_vegetation()
build_camera(); build_clay_light()
if args.step == 1:
    clay_override()
render_settings(args.res, args.samples)

bpy.ops.wm.save_as_mainfile(filepath=args.save)
if args.still:
    scene.frame_set(args.frame)
    scene.render.filepath = os.path.abspath(args.still)
    bpy.ops.render.render(write_still=True)
    print("WROTE", scene.render.filepath)
