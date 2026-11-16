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
sys.path.insert(0, HERE)
import lookdev as LD
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--still", default="")
ap.add_argument("--frame", type=int, default=1)
ap.add_argument("--res", type=int, default=640)
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--sun", default="right", choices=["right", "left"],
                help="right = matches colour reference (sun in frame, top-right); left = top-left")
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
    return 7.0 + 4.5 * smooth(55, 0, y)        # widens a little toward the camera

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
    obj = mesh_obj("TER_Ground", verts, faces, "Terrain")
    # --- scatter weight maps for the Geometry Nodes layers
    W = {k: [] for k in ("w_grass", "w_bush", "w_forest", "w_fern", "w_gravel")}
    cam = Vector((-2.0, -26.0))
    for (x, y, h) in verts:
        gx = (ground_h(x + 0.5, y) - h) / 0.5
        gy = (ground_h(x, y + 0.5) - h) / 0.5
        slope = math.sqrt(gx * gx + gy * gy)
        cy = cliff_y(x)
        d_riv = abs(x - river_cx(y)) / river_w(y)
        below_rim = y < cy - 4.0          # keep scatter off the steep strip at the wall
        plateau = y > cy + 3.0
        dist = (Vector((x, y)) - cam).length
        near = 1.0 - smooth(35, 110, dist)
        grass = (below_rim and d_riv > 0.95 and slope < 3.0) * (0.15 + 0.85 * near)
        W["w_grass"].append(grass * (0.6 + 0.4 * smooth(-0.3, 0.3, fbm((x * .08, y * .08, 4), 2))))
        bank = below_rim and 1.0 < d_riv < 1.7 and y < 60 and slope < 1.2
        W["w_bush"].append(1.0 if bank else (0.03 if (below_rim and x < -16 and slope < 2.5) else 0.0))
        W["w_gravel"].append(1.0 - smooth(0.85, 1.25, d_riv) if y < cy else 0.0)
        W["w_fern"].append(near * (1.0 if (below_rim and d_riv > 1.0) else 0.0))
        forest = 0.0
        if plateau and abs(x - FALL_X) > 6 and y < cy + 45:
            forest = 1.0
        elif x < -30 and below_rim and y > 8:
            forest = 0.8
        W["w_forest"].append(forest)
    for k, vals in W.items():
        a = obj.data.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)
    return obj

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
            ledge = 0.15 * (frac ** 3)                      # sharp step at each layer
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
    ys = [y * 0.5 for y in range(-120, 124)]
    nu = 64
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
    for _ in range(200):
        put(random.uniform(-26, 26), random.uniform(-21, 4), random.uniform(0.25, 1.5))
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
    # trunk (material slot 0 = bark, slot 1 = needles)
    trunk = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.22, radius2=0.06, depth=10.0,
                          matrix=__import__("mathutils").Matrix.Translation((0, 0, 5.0)))
    # core cone (keeps the silhouette solid) + drooping branch clumps per tier
    from mathutils import Matrix, Euler
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=1.4, radius2=0.05, depth=8.6,
                          matrix=Matrix.Translation((0, 0, 1.7 + 4.3)))
    for t in range(tiers):
        f = t / (tiers - 1)
        z = 1.6 + f * 8.4
        r = (1 - f) ** 1.1 * 2.6 + 0.3
        n = max(4, int(11 - f * 6))
        for b in range(n):
            a = b / n * 6.283 + rnd.uniform(-0.3, 0.3) + t * 0.7
            rr = r * rnd.uniform(0.55, 0.75)
            mtx = (Matrix.Translation((math.cos(a) * rr, math.sin(a) * rr, z - 0.25 * rr))
                   @ Euler((0, math.radians(rnd.uniform(14, 26)), a)).to_matrix().to_4x4()
                   @ Matrix.Diagonal((r * rnd.uniform(0.5, 0.65), r * 0.28, 0.32 + 0.1 * (1 - f), 1.0)))
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=mtx)
            for v in res["verts"]:
                v.co += Vector((rnd.uniform(-.12, .12), rnd.uniform(-.12, .12), rnd.uniform(-.1, .1)))
    bm.verts.index_update()
    n_trunk = len(trunk["verts"])          # trunk verts were created first
    for f in bm.faces:
        f.material_index = 0 if all(v.index < n_trunk for v in f.verts) else 1
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.shade_smooth()
    return me

def make_bush_mesh(name, seed):
    rnd = random.Random(seed)
    bm = bmesh.new()
    for _ in range(14):
        m = __import__("mathutils").Matrix.Translation((rnd.uniform(-.8, .8), rnd.uniform(-.8, .8), rnd.uniform(.15, .75)))
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rnd.uniform(.25, .5), matrix=m)
    for v in bm.verts:
        v.co *= 1 + 0.4 * noise.noise(v.co * 4.0 + Vector((seed, 0, 0)))
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
    # forest on the left slope + cliff top: Geometry Nodes scatter (see below)
    # right bank sparse trees
    for _ in range(12):
        x = random.uniform(28, 70); y = random.uniform(10, 40)
        if y < cliff_y(x) - 3:
            tree(x, y, random.uniform(8, 14))
    # ---- instance library (hidden) + Geometry Nodes scatter layers
    lib = bpy.data.collections.new("VEG_Library")
    COLS["Vegetation"].children.link(lib)
    lib.hide_render = True; lib.hide_viewport = True
    lib_tree = bpy.data.collections.new("VEG_Lib_Pines"); lib.children.link(lib_tree)
    lib_bush = bpy.data.collections.new("VEG_Lib_Bushes"); lib.children.link(lib_bush)
    lib_grass = bpy.data.collections.new("VEG_Lib_Grass"); lib.children.link(lib_grass)
    lib_fern = bpy.data.collections.new("VEG_Lib_Ferns"); lib.children.link(lib_fern)
    for i, me in enumerate(pines):
        o = bpy.data.objects.new(f"VEG_LibPine_{i}", me); o.scale = (1.15,) * 3; lib_tree.objects.link(o)
    for i, me in enumerate(bushes):
        lib_bush.objects.link(bpy.data.objects.new(f"VEG_LibBush_{i}", me))
    for i in range(4):
        lib_grass.objects.link(bpy.data.objects.new(f"VEG_LibGrass_{i}", LD.make_grass_clump(f"VEG_grass_mesh_{i}", i)))
    for i in range(3):
        lib_fern.objects.link(bpy.data.objects.new(f"VEG_LibFern_{i}", LD.make_fern(f"VEG_fern_mesh_{i}", i)))
    ter = bpy.data.objects["TER_Ground"]
    vc = COLS["Vegetation"]
    LD.gn_scatter("Forest", ter, "w_forest", 0.045, lib_tree, (0.7, 1.45), 11, vc, wind=0.012)
    LD.gn_scatter("Bushes", ter, "w_bush", 0.22, lib_bush, (0.5, 1.4), 21, vc, wind=0.035)
    LD.gn_scatter("Ferns", ter, "w_fern", 0.025, lib_fern, (0.7, 1.5), 41, vc, wind=0.08)
    LD.gn_scatter("Grass", ter, "w_grass", 22.0, lib_grass, (0.7, 1.4), 31, vc, wind=0.10)
    lib_peb = bpy.data.collections.new("RCK_Lib_Pebbles"); lib.children.link(lib_peb)
    for i in range(6):
        lib_peb.objects.link(bpy.data.objects.new(f"RCK_LibPebble_{i}", bpy.data.meshes[f"RCK_mesh_{i}"]))
    LD.gn_scatter("Pebbles", ter, "w_gravel", 3.0, lib_peb, (0.05, 0.28), 51, COLS["Rocks"])
    return trees, shrubs, dict(pines=pines, bushes=bushes,
                               grass=[o.data for o in lib_grass.objects], ferns=[o.data for o in lib_fern.objects])

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
    if args.step >= 2:
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.view_settings.exposure = -0.35

# ---------------------------------------------------------------- step 2
def sun_direction(side):
    """Direction TOWARD the sun. 'right' puts the disc top-right in frame like the
    colour reference; 'left' mirrors it to top-left."""
    yaw = math.radians(19.0 if side == "right" else -58.0)
    el = math.radians(31.0 if side == "right" else 30.0)
    return Vector((math.sin(yaw) * math.cos(el), math.cos(yaw) * math.cos(el), math.sin(el)))

def apply_lookdev(objs, veg_meshes):
    rock = LD.mat_rock("MAT_Rock", cracks=0.25, strata=0.4, base=(0.52, 0.44, 0.35), warm=(0.62, 0.48, 0.32), moss_amt=0.5, disp=0.06)
    cliff = LD.mat_rock("MAT_Cliff", strata=0.8, base=(0.40, 0.33, 0.26), warm=(0.58, 0.36, 0.18),
                        moss_amt=0.35, disp=0.25, scale=3.0)
    ground = LD.mat_ground()
    mount = LD.mat_mountain()
    bark = LD.mat_bark()
    needles = LD.mat_foliage("MAT_Needles", (0.03, 0.09, 0.025), (0.12, 0.24, 0.05), sss=0.2)
    leaves = LD.mat_foliage("MAT_BushLeaves", (0.05, 0.12, 0.02), (0.22, 0.32, 0.05), sss=0.3, bump_scale=9)
    grass = LD.mat_foliage("MAT_Grass", (0.08, 0.18, 0.03), (0.38, 0.45, 0.10), sss=0.3, bump_scale=3)
    fern = LD.mat_foliage("MAT_Fern", (0.06, 0.16, 0.03), (0.20, 0.36, 0.06), sss=0.3, bump_scale=3)
    water = LD.mat_water(); fall = LD.mat_waterfall()

    def put(me, *mats):
        # NB: materials.clear() would reset every face's material_index to 0
        if len(me.materials) == 0:
            for m in mats: me.materials.append(m)
        else:
            for i, m in enumerate(mats): me.materials[i] = m
    put(bpy.data.objects["TER_Ground"].data, ground)
    put(bpy.data.objects["TER_Cliff"].data, cliff)
    for o in COLS["Terrain"].objects:
        if o.name.startswith("TER_Mountain"): put(o.data, mount)
    for me in {o.data for o in COLS["Rocks"].objects}: put(me, rock)
    for me in veg_meshes["pines"]: put(me, bark, needles)
    for me in veg_meshes["bushes"]: put(me, leaves)
    for me in veg_meshes["grass"]: put(me, grass)
    for me in veg_meshes["ferns"]: put(me, fern)
    w = bpy.data.objects["WAT_River"]; put(w.data, water)
    put(bpy.data.objects["WAT_Waterfall"].data, fall)
    LD.bake_foam(w, [o for o in COLS["Rocks"].objects if not o.modifiers], (FALL_X, cliff_y(FALL_X) - 5))

    # lighting
    sdir = sun_direction(args.sun)
    LD.setup_lighting(scene, COLS["Lights"], sdir, 4.5)

    # atmosphere: valley haze (god rays), waterfall mist, distant clouds
    haze = LD.box("ATM_Haze", (0, 120, 60), (220, 170, 75), COLS["Lights"])
    haze.data.materials.append(LD.mat_volume("MAT_Haze", 0.0006, 0.7, (0.92, 0.95, 1.0)))
    haze.visible_shadow = False
    # denser local volume where the sun slants past the left forest -> god rays
    rays = LD.box("ATM_GodRays", (-15, 40, 22), (45, 28, 24), COLS["Lights"])
    rays.data.materials.append(LD.mat_volume("MAT_GodRays", 0.0045, 0.75, (1.0, 0.97, 0.9)))
    rays.visible_shadow = False
    mist = LD.sphere("ATM_Waterfall_Mist", (FALL_X, cliff_y(FALL_X) - 6, 3.0), (11, 7, 7), COLS["Water"])
    mist.data.materials.append(LD.mat_volume("MAT_Mist", 0.35, 0.3, (1, 1, 1), noise_scale=0.6, animate=True))
    cm = LD.mat_cloud()
    for i, (x, z, sx, sz) in enumerate([(-900, 520, 420, 120), (-250, 640, 360, 90),
                                         (420, 560, 500, 130), (1100, 700, 380, 100)]):
        c = LD.plane(f"ATM_Cloud_{i}", (x, 2600, z), (sx, sz), (math.radians(90), 0, 0), COLS["Lights"])
        c.data.materials.append(cm)
        c.visible_shadow = False

    # Cycles volume speed settings
    scene.cycles.volume_step_rate = 4.0
    scene.cycles.volume_max_steps = 96
    scene.cycles.volume_bounces = 0

# ---------------------------------------------------------------- main
build_terrain(); build_cliff(); build_mountains()
build_water(); build_rocks(); _trees, _shrubs, VEG_MESHES = build_vegetation()
build_camera(); build_clay_light()
if args.step == 1:
    clay_override()
else:
    apply_lookdev(None, VEG_MESHES)
render_settings(args.res, args.samples)

bpy.ops.wm.save_as_mainfile(filepath=args.save)
if args.still:
    scene.frame_set(args.frame)
    scene.render.filepath = os.path.abspath(args.still)
    bpy.ops.render.render(write_still=True)
    print("WROTE", scene.render.filepath)
