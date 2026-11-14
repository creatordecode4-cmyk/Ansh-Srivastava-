"""Stage 1: build the temple arena from the traced top-down layout and save build/arena.blend.
Run:  python3 samurai-fight/scripts/build_arena.py
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sf_lib import *
import props as P

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'build')
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.name = 'Arena'
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 720
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.unit_settings.system = 'METRIC'

LIB = get_coll('LIB')            # prop sources (instanced, never rendered directly)
ARENA = get_coll('ARENA')
SET = get_coll('SET_Static', ARENA)
DRESS = get_coll('SET_Dressing', ARENA)
FX = get_coll('FX')
LGT = get_coll('LIGHTS')
CAMS = get_coll('CAMERAS')

# ------------------------------------------------------------------ key layout points (metres)
TORII = Vector((-2.2, 14.3, 0.5))
TEMPLE_N = Vector((math.cos(math.radians(-30)), math.sin(math.radians(-30)), 0))   # facade faces the courtyard
TEMPLE_F = px(665, 340)                                                            # facade centre
TEMPLE_D, TEMPLE_W = 11.0, 18.0
TEMPLE = TEMPLE_F - TEMPLE_N * (TEMPLE_D / 2)
TEMPLE_ROT = math.radians(60)
LANTERNS = [(px(935, 318), False), (px(1640, 305), False), (px(788, 700), False), (px(1875, 750), False),
            (px(1640, 935), True), (px(1010, 925), True)]
FLOOR = (-14.6, 14.9, -12.6, 12.6)
FIGHT_C = Vector((0.0, 1.0, 0.0))

# ------------------------------------------------------------------ prop library
c_lan = get_coll('PROP_StoneLantern', LIB)
P.build_stone_lantern(c_lan, False, 1)
c_lanb = get_coll('PROP_StoneLanternBroken', LIB)
P.build_stone_lantern(c_lanb, True, 2, power=800.0)
c_torii = get_coll('PROP_Torii', LIB)
P.build_torii(c_torii)
c_temple = get_coll('PROP_TempleMain', LIB)
P.build_temple(c_temple, TEMPLE_W, TEMPLE_D, tag='A')
c_shrine = get_coll('PROP_ShrineBack', LIB)
P.build_temple(c_shrine, 12.0, 7.5, ph=1.2, wh=3.6, ov=2.2, rH=4.2, bays=5, porch=False, lanterns=2, glow=0.25, door_light=700.0, tag='B')
c_side = get_coll('PROP_HallSide', LIB)
P.build_temple(c_side, 9.0, 6.5, ph=1.0, wh=3.4, ov=2.0, rH=3.6, bays=4, vw=1.4, porch=False, lanterns=2, glow=0.22, door_light=500.0, tag='C')
c_gate = get_coll('PROP_GateHouse', LIB)
P.build_temple(c_gate, 9.0, 5.0, ph=0.5, wh=3.0, ov=1.6, rH=2.8, bays=4, vw=1.0, stairs=False, porch=False, lanterns=0, door_light=0.0, glow=0.12, tag='D')
c_nob = [get_coll(f'PROP_Nobori{k}', LIB) for k in range(3)]
for k, c in enumerate(c_nob):
    P.build_nobori(c, 4.4 + 0.3 * k, seed=k * 2.3)
c_cherry = []
for k, hgt in enumerate((11.0, 7.5, 8.5, 9.0)):
    c = get_coll(f'PROP_Cherry{k}', LIB)
    P.build_cherry(c, seed=21 + k, height=hgt, name=f'Cherry{k}')
    c_cherry.append(c)
c_bough = []
for k in range(2):
    c = get_coll(f'PROP_CherryBough{k}', LIB)
    P.build_cherry(c, seed=51 + k, height=15.0, name=f'Bough{k}', bough=True, r0=0.13)
    c_bough.append(c)
c_pine = []
for k in range(3):
    c = get_coll(f'PROP_Pine{k}', LIB)
    P.build_pine(c, seed=k + 3, height=1.0 * 16, name=f'Pine{k}')
    c_pine.append(c)
rocks = P.make_rock_meshes()

# ------------------------------------------------------------------ ground, floor, water film
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=160)
g = mesh_obj('Ground', bm, SET, [mat_ground()])
g.location = (0, 10, -0.06)
P.build_floor(SET, *FLOOR)
# (puddles are part of the slab shader: mirror-smooth patches with flattened bump)
# stone kerb around the courtyard + south entrance steps
bm = bmesh.new()
for (cx, cy, sx, sy) in ((0.15, FLOOR[2] - 0.35, 30.6, 0.7), (FLOOR[0] - 0.35, 0, 0.7, 25.2), (FLOOR[1] + 0.35, 0, 0.7, 25.2)):
    add_box(bm, (sx, sy, 0.3), (cx, cy, -0.02))
for i in range(3):
    add_box(bm, (10.0, 0.5, 0.16), (-1.4, FLOOR[2] - 0.95 - 0.5 * i, -0.14 - 0.16 * i))
mesh_obj('Floor_Kerb', bm, SET, [mat_stone()], bevel=0.03)

# ------------------------------------------------------------------ torii platform, back stairs, terrace
bm = bmesh.new()
add_box(bm, (12.0, 4.4, 0.5), (TORII.x, 14.8, 0.25))
for i in range(3):
    add_box(bm, (12.0, 0.36 * (3 - i), 0.5 / 3), (TORII.x, 12.6 - 0.36 * (3 - i) / 2, 0.5 / 3 * i + 0.25 / 3))
add_box(bm, (17.0, 26.0, 2.03), (TORII.x, 20.24 + 13.0, 1.015))          # upper terrace
mesh_obj('ToriiPlatform', bm, SET, [mat_stone()], bevel=0.03)
st = P.build_stairs(SET, 9.0, 9, 0.17, 0.36, 'BackStairs')
st.location = (TORII.x, 17.0, 0.5)

instance(c_torii, TORII, 0.0, 1.0, SET, 'I_Torii')
instance(c_temple, TEMPLE, TEMPLE_ROT, 1.0, SET, 'I_TempleMain')
instance(c_shrine, (TORII.x, 33.0, 2.03), 0.0, 1.0, SET, 'I_ShrineBack')
instance(c_side, (14.6, 14.0, 0), math.radians(-60), 1.0, SET, 'I_HallSide')
instance(c_gate, px(620, 960), math.radians(90), 1.0, SET, 'I_GateHouse')
instance(c_side, (-33.5, 4.5, 0), TEMPLE_ROT, 1.15, SET, 'I_Annex')
for k, (p, broken) in enumerate(LANTERNS):
    instance(c_lanb if broken else c_lan, p, 0.7 * k, 1.12, SET, f'I_Lantern{k}', tilt=((0.10, -0.06) if broken else (0, 0)))
for k, p in enumerate(((-12.6, 13.6), (-10.0, 15.3), (5.6, 15.4))):
    instance(c_nob[k], (p[0], p[1], 0), math.radians(-25 + 20 * k), 1.0, DRESS, f'I_Nobori{k}')

# ------------------------------------------------------------------ trees
CHERRIES = [((-27.0, -4.5), 0, 0.3), ((-14.9, 17.4), 1, 1.2), ((-8.6, 19.6), 2, 2.1), ((7.2, 18.6), 3, 0.5),
            ((17.2, 6.8), 1, 3.0), ((-15.6, -11.6), 2, 4.0), ((13.0, -11.8), 3, 5.1), ((-24.0, -14.0), 3, 1.7), ((21.0, -6.0), 0, 2.6)]
for k, ((x, y), idx, rz) in enumerate(CHERRIES):
    instance(c_cherry[idx], (x, y, 0), rz, 1.0, DRESS, f'I_Cherry{k}')
# hero boughs reaching over the south end of the court (frame the low-angle shots like arena.png)
instance(c_cherry[0], (-9.5, -14.2, 0), 1.9, 1.0, DRESS, 'I_CherrySouthL')
instance(c_cherry[0], (10.5, -14.0, 0), 4.4, 0.95, DRESS, 'I_CherrySouthR')
P.build_frame_bough(DRESS, [(-9.5, -14.2, 3.2), (-5.6, -11.6, 3.7), (-2.6, -9.2, 3.5), (-1.8, -6.8, 4.3), (-1.0, -5.0, 5.4)], 5, 'FrameBoughL')
P.build_frame_bough(DRESS, [(10.5, -14.0, 3.5), (7.4, -10.6, 3.9), (4.7, -7.7, 3.4), (3.7, -5.7, 4.3), (3.1, -4.0, 5.7)], 6, 'FrameBoughR')
rnd = random.Random(8)
for k in range(46):
    ang = rnd.uniform(0, 6.283)
    r = rnd.uniform(40, 78)
    p = Vector((-5 + r * math.cos(ang), 10 + r * math.sin(ang), 0))
    if p.y < -25 and abs(p.x) < 25:
        continue
    instance(c_pine[k % 3], p, rnd.uniform(0, 6.28), rnd.uniform(0.8, 1.5), DRESS, f'I_Pine{k}')

# ------------------------------------------------------------------ rubble (zones traced from the layout)
def clear(p):      # keep the fighting area and walkways free
    return (abs(p.x - FIGHT_C.x) < 9.0 and abs(p.y - FIGHT_C.y) < 8.5) or (abs(p.x + 1.4) < 4.0 and p.y < -8)

ZONES = [(px(1020, 330), 3.6, 34), (px(1600, 290), 4.6, 42), (px(800, 700), 4.6, 46), (px(880, 900), 5.2, 60),
         (px(1700, 950), 5.2, 60), (px(1850, 760), 3.2, 26), (px(700, 560), 3.5, 26), (px(1500, 250), 2.5, 16)]
for k, (c, r, n) in enumerate(ZONES):
    P.scatter_rubble(DRESS, rocks, c, r, n, 40 + k, keep_clear=clear)
P.scatter_rubble(DRESS, rocks, (0, 0), 15.5, 70, 77, smax=0.45, keep_clear=lambda p: abs(p.x) < 10.5 and abs(p.y - 1) < 9.5)
# fallen column drum near the south-east rubble, as in the clay render
bm = bmesh.new()
add_cyl(bm, 0.42, 0.40, 2.6, (0, 0, 0), 14, tris=True)
subdivide(bm, 2)
rockify(bm, 0.03, 2.5, 9)
drum = mesh_obj('FallenColumn', bm, DRESS, [mat_stone()], smooth=True, sharp_deg=50)
drum.location, drum.rotation_euler = (9.6, -8.4, 0.42), (math.radians(90), 0, math.radians(62))

# fallen petals + snow flecks lying on the stone
rnd = random.Random(3)
bm = bmesh.new()
for i in range(9000):
    x, y = rnd.uniform(-17, 17), rnd.uniform(-15, 14)
    edge = max(abs(x) / 15.0, abs(y - 1) / 13.0)
    if rnd.random() > 0.10 + edge ** 2.5:
        continue
    s = rnd.uniform(0.011, 0.02)
    R = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-0.2, 0.2), 3, 'X')
    c = Vector((x, y, 0.011))
    bm.faces.new([bm.verts.new(c + R @ Vector((a * s, b2 * s, 0))) for a, b2 in ((-1.0, 0.0), (-0.45, -0.75), (0.6, -0.7), (1.0, 0.0), (0.6, 0.7), (-0.45, 0.75))])
mesh_obj('FallenPetals', bm, DRESS, [mat_blossom()])

# ------------------------------------------------------------------ sky, moon, fog
MOON_DIR = Vector((-0.02, 0.94, 0.33)).normalized()
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
moon = mesh_obj('BloodMoon', bm, FX, [mat_moon()], smooth=True)
moon.location = MOON_DIR * 420
moon.scale = (36, 36, 36)
moon.visible_shadow = False

wld = bpy.data.worlds.new('NightSky')
sc.world = wld
wld.use_nodes = True
nt = NT(wld)
bg = nt.nodes['Background']
co = nt.new('ShaderNodeTexCoord').outputs['Generated']
z = nt.sep(co)[2]
grad = nt.mix(nt.maprange(z, -0.05, 0.6), (0.030, 0.014, 0.024), (0.006, 0.009, 0.022))
stars = nt.ramp(nt.noise(co, 420.0, 2, 0.5), [(0.735, 0.0), (0.78, 1.0)])
nt.link(nt.mix(stars, grad, (0.5, 0.55, 0.7)), bg.inputs[0])
bg.inputs[1].default_value = 1.0


def fog_box(name, lo, hi, density, aniso=0.55, color=(0.8, 0.82, 1.0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    ob = mesh_obj(name, bm, FX, [mat_fog('MAT_' + name, density, aniso, color)])
    lo, hi = Vector(lo), Vector(hi)
    ob.location, ob.scale = (lo + hi) / 2, hi - lo
    ob.display_type = 'WIRE'
    ob.visible_shadow = False
    return ob


fog_box('Fog_Haze', (-70, -45, -1), (70, 95, 34), 0.0045)
fog_box('Fog_GroundMist', (-32, 9, 0), (30, 46, 3.2), 0.022, 0.4)
# night clouds on a card in front of the moon
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
cl = mesh_obj('SkyClouds', bm, FX, [mat_cloud()])
cl.location = MOON_DIR * 400 + Vector((-42, 0, -30))
cl.rotation_euler = (-cl.location).to_track_quat('-Z', 'Y').to_euler()
cl.scale = (520, 260, 1)
cl.visible_shadow = cl.visible_diffuse = cl.visible_volume_scatter = False

# ------------------------------------------------------------------ lights
def sun(name, travel, energy, color, angle_deg):
    l = bpy.data.lights.new(name, 'SUN')
    l.energy, l.color, l.angle = energy, color, math.radians(angle_deg)
    ob = bpy.data.objects.new(name, l)
    ob.rotation_euler = Vector(travel).normalized().to_track_quat('-Z', 'Y').to_euler()
    LGT.objects.link(ob)
    return ob


k = sun('LGT_Key_MoonCold', (0.45, 0.62, -0.64), 1.5, (0.50, 0.66, 1.0), 4.0)      # cold key from camera-left, high
r = sun('LGT_Rim_BloodMoon', -MOON_DIR, 3.0, (1.0, 0.11, 0.06), 2.0)               # red rim from the moon
k.visible_volume_scatter = r.visible_volume_scatter = False                      # suns must not grey out the fog
for nm, loc, col, pw in (('LGT_Mist_L', (-12, 23, 2.4), (0.45, 0.32, 1.0), 6000), ('LGT_Mist_R', (7, 25, 2.4), (0.6, 0.3, 0.9), 4500),
                         ('LGT_Mist_Torii', (-2.2, 19, 1.5), (1.0, 0.2, 0.25), 3500)):
    l = bpy.data.lights.new(nm, 'POINT')
    l.energy, l.color, l.shadow_soft_size = pw, col, 2.5
    ob = bpy.data.objects.new(nm, l)
    ob.location = loc
    ob.visible_diffuse = ob.visible_glossy = ob.visible_transmission = False     # lights the mist only
    LGT.objects.link(ob)

# ------------------------------------------------------------------ falling petals + light snow
# Deterministic Geometry-Nodes particle system: every petal's position is a closed-form function of the
# effects clock (FX_Clock.location.z, seconds), so any frame renders correctly without a simulation cache,
# and slow motion is done later by keyframing that clock instead of letting it follow the frame number.
bm = bmesh.new()
vs = [bm.verts.new(p) for p in ((-0.5, -0.38, 0.06), (0, -0.42, -0.04), (0.5, -0.38, 0.06), (0.55, 0.3, 0.08), (0, 0.5, -0.02), (-0.55, 0.3, 0.08))]
bm.faces.new((vs[0], vs[1], vs[4], vs[5]))
bm.faces.new((vs[1], vs[2], vs[3], vs[4]))
petal = mesh_obj('PetalInstance', bm, LIB, [mat_blossom()], smooth=True)
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
flake = mesh_obj('SnowInstance', bm, LIB, [mat_simple('MAT_Snow', (0.8, 0.84, 0.9), 0.5)], smooth=True)


CLOCK = bpy.data.objects.new('FX_Clock', None)
FX.objects.link(CLOCK)
fc = CLOCK.driver_add('location', 2)        # keyframe this instead (and remove the driver) to slow time down
fc.driver.type = 'SCRIPTED'
fc.driver.expression = 'frame / 24'


def falling_system(name, inst, count, box_min, box_max, fall, drift, sway, size, spin, seed):
    ng = bpy.data.node_groups.new('GN_' + name, 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin, gout = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    W, D, H = (box_max[i] - box_min[i] for i in range(3))

    def rnd(dtype, lo, hi, sd):
        n = N.new('FunctionNodeRandomValue')
        n.data_type = dtype
        n.inputs[0].default_value, n.inputs[1].default_value = lo, hi      # sockets are per-type in Blender 5.x
        n.inputs['Seed'].default_value = sd
        return n.outputs[0]

    def m(op, *args):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate(args):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    oc = N.new('GeometryNodeObjectInfo')          # FX_Clock.location.z is the effects time in seconds
    oc.inputs['Object'].default_value = CLOCK
    st = N.new('ShaderNodeSeparateXYZ')
    L.new(oc.outputs['Location'], st.inputs[0])
    t = st.outputs[2]
    sx = N.new('ShaderNodeSeparateXYZ')
    L.new(rnd('FLOAT_VECTOR', (0, 0, 0), (W, D, H), seed), sx.inputs[0])
    k, ph = rnd('FLOAT', 0.75, 1.3, seed + 1), rnd('FLOAT', 0.0, 6.283, seed + 2)
    zmod = m('FLOORED_MODULO', m('ADD', sx.outputs[2], m('MULTIPLY', m('MULTIPLY', t, fall), k)), H)
    swx = m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', m('MULTIPLY', t, 1.7), k), ph)), sway)
    swy = m('MULTIPLY', m('COSINE', m('ADD', m('MULTIPLY', t, 1.3), m('MULTIPLY', ph, 1.7))), sway)
    x = m('ADD', box_min[0], m('FLOORED_MODULO', m('ADD', m('ADD', sx.outputs[0], m('MULTIPLY', t, drift[0])), swx), W))
    y = m('ADD', box_min[1], m('FLOORED_MODULO', m('ADD', m('ADD', sx.outputs[1], m('MULTIPLY', t, drift[1])), swy), D))
    pos = N.new('ShaderNodeCombineXYZ')
    L.new(x, pos.inputs[0])
    L.new(y, pos.inputs[1])
    L.new(m('SUBTRACT', box_max[2], zmod), pos.inputs[2])
    pts = N.new('GeometryNodePoints')
    pts.inputs['Count'].default_value = count
    L.new(pos.outputs[0], pts.inputs['Position'])
    # shrink to nothing at the wrap (spawn at the top / under the floor) so motion blur never streaks
    fade = m('MULTIPLY', m('MINIMUM', m('MULTIPLY', zmod, 2.5), 1.0), m('MINIMUM', m('MULTIPLY', m('SUBTRACT', H, zmod), 3.3), 1.0))
    scl = m('MULTIPLY', m('MULTIPLY', rnd('FLOAT', 0.55, 1.0, seed + 3), size), fade)
    vm = N.new('ShaderNodeVectorMath')
    vm.operation = 'SCALE'
    L.new(rnd('FLOAT_VECTOR', (-spin,) * 3, (spin,) * 3, seed + 5), vm.inputs[0])
    L.new(t, vm.inputs['Scale'])
    va = N.new('ShaderNodeVectorMath')
    va.operation = 'ADD'
    L.new(rnd('FLOAT_VECTOR', (0, 0, 0), (6.283,) * 3, seed + 4), va.inputs[0])
    L.new(vm.outputs[0], va.inputs[1])
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(va.outputs[0], e2r.inputs[0])
    oi = N.new('GeometryNodeObjectInfo')
    oi.inputs['Object'].default_value = inst
    oi.inputs['As Instance'].default_value = True
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(pts.outputs[0], iop.inputs['Points'])
    L.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    L.new(e2r.outputs[0], iop.inputs['Rotation'])
    L.new(scl, iop.inputs['Scale'])
    L.new(iop.outputs[0], gout.inputs[0])
    me = bpy.data.meshes.new('FX_' + name)
    me.from_pydata([(0, 0, 0)], [], [])
    ob = bpy.data.objects.new('FX_' + name, me)
    FX.objects.link(ob)
    mod = ob.modifiers.new('Falling', 'NODES')
    mod.node_group = ng
    return ob


falling_system('Petals', petal, 9000, (-16, -15, -0.3), (19, 18, 13.0), 1.0, (0.35, -0.12), 0.35, 0.05, 2.5, 11)
falling_system('Snow', flake, 16000, (-17, -16, -0.3), (20, 19, 14.0), 0.8, (0.25, -0.08), 0.15, 0.02, 0.5, 31)

# ------------------------------------------------------------------ cameras
def camera(name, loc, aim, lens=24.0, fstop=2.8, focus=None, ortho=None):
    cd = bpy.data.cameras.new(name)
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.05, 2000
    if ortho:
        cd.type, cd.ortho_scale = 'ORTHO', ortho
    else:
        cd.dof.use_dof = True
        cd.dof.focus_distance = focus or (Vector(aim) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    CAMS.objects.link(ob)
    return ob


camera('CAM_Hero', (2.0, -11.4, 0.5), (-5.0, 12.0, 5.3), 20.0, 4.0, 15.0)
camera('CAM_Wide', (0.5, -33.0, 14.0), (-3.0, 8.0, 2.5), 28.0, 5.6, 40.0)      # drone start position
camera('CAM_Fight', (6.5, -5.5, 1.5), (-0.5, 2.0, 1.4), 35.0, 2.8, 10.0)
top_c = px(975, 592)
camera('CAM_Top', (top_c.x, top_c.y, 120.0), (top_c.x, top_c.y + 0.001, 0.0), ortho=1950 / PXM)
sc.camera = bpy.data.objects['CAM_Hero']

# ------------------------------------------------------------------ render defaults
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'
cy.samples, cy.use_adaptive_sampling, cy.adaptive_threshold = 64, True, 0.03
cy.use_denoising = True
cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces, cy.volume_bounces, cy.transparent_max_bounces = 6, 2, 4, 4, 0, 8
cy.sample_clamp_indirect, cy.sample_clamp_direct = 6.0, 0.0
cy.caustics_reflective = cy.caustics_refractive = False
sc.view_settings.view_transform = 'AgX'
for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try:
        sc.view_settings.look = look
        break
    except TypeError:
        pass
sc.view_settings.exposure = 0.0
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
sc.render.film_transparent = False

clay = bpy.data.materials.new('MAT_Clay')
clay.use_nodes = True
b = next(n for n in clay.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
b.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
b.inputs['Roughness'].default_value = 0.7
clay.use_fake_user = True

exclude_coll('LIB')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'arena.blend'))
tris = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print(f'ARENA BUILT objects={len(bpy.data.objects)} mesh_faces(unique)={tris}')
