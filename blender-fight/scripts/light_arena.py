"""Stage 1b: mood pass on the blockout arena.

Opens arena_blockout.blend and adds: procedural materials (wet cracked stone floor, mossy
stone, red lacquered wood, roof tile), blood moon, cold moon key + red rim, lantern glow,
volumetric fog, falling cherry petals + light snow (particle systems).
All materials are procedural placeholders; Poly Haven textures / GLB props replace them later.

Run:  python3 scripts/light_arena.py [samples] [frame]
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import layout as L  # noqa: E402

random.seed(11)
RED_GLOW = (1.0, 0.10, 0.04, 1)


# ---------- tiny node helpers ----------
class G:
    """Node-graph builder for one material."""

    def __init__(self, name, volume=False):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.t = self.mat.node_tree
        self.t.nodes.clear()
        self.out = self.t.nodes.new("ShaderNodeOutputMaterial")
        if not volume:
            self.bsdf = self.t.nodes.new("ShaderNodeBsdfPrincipled")
            self.t.links.new(self.bsdf.outputs[0], self.out.inputs["Surface"])
        self.tc = self.t.nodes.new("ShaderNodeTexCoord")
        self.obj = self.tc.outputs["Object"]

    def n(self, kind, ins=None, **props):
        node = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        for k, v in (ins or {}).items():
            sock = node.inputs[k]
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, sock)
            else:
                sock.default_value = v
        return node

    def noise(self, scale, detail=6.0, vec=None, rough=0.6):
        return self.n("ShaderNodeTexNoise", {"Vector": vec or self.obj, "Scale": scale, "Detail": detail,
                                             "Roughness": rough}).outputs["Fac"]

    def ramp(self, fac, stops):
        r = self.n("ShaderNodeValToRGB", {"Fac": fac})
        el = r.color_ramp.elements
        while len(el) < len(stops):
            el.new(0.5)
        for e, (pos, col) in zip(el, stops):
            e.position = pos
            e.color = col if len(col) == 4 else (*col, 1)
        return r.outputs["Color"]

    def mix(self, fac, a, b):
        return self.n("ShaderNodeMix", {0: fac, 6: a, 7: b}, data_type="RGBA").outputs[2]

    def math(self, op, a, b=0.0, clamp=False):
        return self.n("ShaderNodeMath", {0: a, 1: b}, operation=op, use_clamp=clamp).outputs[0]

    def z(self):
        return self.n("ShaderNodeSeparateXYZ", {"Vector": self.obj}).outputs["Z"]

    def step(self, value, edge, soft=0.02):
        """~0 below edge, ~1 above."""
        return self.n("ShaderNodeMapRange", {"Value": value, "From Min": edge - soft, "From Max": edge + soft}).outputs[0]

    def set(self, **ins):
        for k, v in ins.items():
            key = k.replace("_", " ")
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, self.bsdf.inputs[key])
            else:
                self.bsdf.inputs[key].default_value = v

    def bump(self, height, strength=0.5, dist=0.03):
        b = self.n("ShaderNodeBump", {"Height": height, "Strength": strength, "Distance": dist})
        self.t.links.new(b.outputs[0], self.bsdf.inputs["Normal"])

    def snow_mask(self):
        """Light snow settled on up-facing surfaces."""
        nz = self.n("ShaderNodeSeparateXYZ", {"Vector": self.n("ShaderNodeNewGeometry").outputs["Normal"]}).outputs["Z"]
        return self.math("MULTIPLY", self.step(nz, 0.75, 0.1), self.step(self.noise(1.3, 4), 0.56, 0.06), clamp=True)


BLACK, WHITE = (0, 0, 0, 1), (1, 1, 1, 1)


def stone_color(g):
    col = g.ramp(g.noise(2.2, 8), [(0.3, (0.012, 0.012, 0.014)), (0.75, (0.085, 0.085, 0.09))])
    moss = g.step(g.noise(0.9, 5), 0.6, 0.05)
    col = g.mix(g.math("MULTIPLY", moss, 0.6), col, (0.03, 0.05, 0.012, 1))
    return g.mix(g.math("MULTIPLY", g.snow_mask(), 0.85), col, (0.75, 0.78, 0.85, 1))


def mat_stone(name="MAT_stone", glow_z=None):
    g = G(name)
    g.set(Base_Color=stone_color(g), Roughness=0.5)
    g.bump(g.noise(7, 8), 0.7, 0.04)
    if glow_z:  # the lamp chamber of a stone lantern glows red
        z = g.z()
        band = g.math("MULTIPLY", g.step(z, glow_z[0]), g.math("SUBTRACT", 1.0, g.step(z, glow_z[1])), clamp=True)
        g.set(Emission_Color=RED_GLOW, Emission_Strength=g.math("MULTIPLY", band, 2.5))
    return g.mat


def wood_color(g):
    stretch = g.n("ShaderNodeMapping", {"Vector": g.obj, "Scale": (6, 6, 0.6)}).outputs[0]
    return g.ramp(g.noise(3, 6, vec=stretch), [(0.32, (0.012, 0.006, 0.006)), (0.52, (0.16, 0.012, 0.01)),
                                               (0.8, (0.30, 0.02, 0.015))])


def mat_wood(name="MAT_red_wood", stone_below=None):
    g = G(name)
    col = wood_color(g)
    if stone_below is not None:
        col = g.mix(g.step(g.z(), stone_below), stone_color(g), col)
    g.set(Base_Color=col, Roughness=0.32)
    g.bump(g.noise(9, 6), 0.35, 0.02)
    return g.mat


def mat_temple(name, roof_z):
    g = G(name)
    z = g.z()
    tiles = g.n("ShaderNodeTexWave", {"Vector": g.obj, "Scale": 4.0, "Distortion": 0.4}).outputs["Fac"]
    roof = g.ramp(tiles, [(0.0, (0.004, 0.004, 0.005)), (1.0, (0.03, 0.03, 0.034))])
    roof = g.mix(g.math("MULTIPLY", g.snow_mask(), 0.7), roof, (0.75, 0.78, 0.85, 1))
    col = g.mix(g.step(z, 1.12), stone_color(g), wood_color(g))
    col = g.mix(g.step(z, roof_z), col, roof)
    g.set(Base_Color=col, Roughness=0.3)
    g.bump(g.math("ADD", g.math("MULTIPLY", tiles, g.step(z, roof_z)), g.math("MULTIPLY", g.noise(8), 0.3)), 0.6, 0.05)
    return g.mat


def mat_floor():
    """Wet cracked paving: brick-pattern joints + voronoi cracks, puddle roughness map."""
    g = G("MAT_floor_wet_stone")
    warp = g.n("ShaderNodeMix", {0: 0.06, 4: g.obj,
                                 5: g.n("ShaderNodeTexNoise", {"Vector": g.obj, "Scale": 1.4}).outputs["Color"]},
               data_type="VECTOR").outputs[1]
    brick = g.n("ShaderNodeTexBrick", {"Vector": warp, "Scale": 1.0, "Mortar Size": 0.012, "Mortar Smooth": 0.3,
                                       "Brick Width": 1.15, "Row Height": 0.75}, offset=0.5)
    joints = g.math("SUBTRACT", 1.0, brick.outputs["Fac"])                      # 0 in the joints
    vor = g.n("ShaderNodeTexVoronoi", {"Vector": warp, "Scale": 0.85}, feature="DISTANCE_TO_EDGE")
    cracks = g.step(vor.outputs["Distance"], 0.012, 0.012)                       # 0 in the cracks
    height = g.math("MULTIPLY", joints, cracks)
    puddle = g.step(g.noise(0.22, 3), 0.47, 0.12)                                # 1 = standing water
    slab = g.ramp(g.noise(1.6, 8), [(0.3, (0.01, 0.01, 0.012)), (0.8, (0.055, 0.055, 0.06))])
    col = g.mix(height, (0.004, 0.004, 0.005, 1), slab)
    rough = g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, puddle), 0.30), 0.03)
    g.set(Base_Color=col, Roughness=rough, Specular_IOR_Level=0.8)
    relief = g.math("MULTIPLY", g.math("ADD", height, g.math("MULTIPLY", g.noise(5, 6), 0.25)),
                    g.math("SUBTRACT", 1.0, g.math("MULTIPLY", puddle, 0.85)))   # puddles flatten the relief
    g.bump(relief, 0.9, 0.03)
    return g.mat


def mat_simple(name, color, rough=0.6, emit=None, strength=0.0):
    g = G(name)
    g.set(Base_Color=color, Roughness=rough)
    if emit:
        g.set(Emission_Color=emit, Emission_Strength=strength)
    return g.mat


def mat_tree():
    g = G("MAT_cherry_tree")
    blossom = g.ramp(g.noise(3.5, 4), [(0.35, (0.55, 0.16, 0.30)), (0.7, (0.95, 0.62, 0.74))])
    col = g.mix(g.step(g.z(), 3.3, 0.3), (0.02, 0.012, 0.01, 1), blossom)
    g.set(Base_Color=col, Roughness=0.7, Subsurface_Weight=0.2)
    g.bump(g.noise(5, 8), 1.0, 0.25)
    return g.mat


def mat_moon():
    g = G("MAT_blood_moon")
    g.t.nodes.remove(g.bsdf)
    maria = g.ramp(g.noise(0.11, 9, rough=0.7), [(0.35, (0.30, 0.01, 0.01)), (0.7, (1.0, 0.09, 0.04))])
    em = g.n("ShaderNodeEmission", {"Color": maria, "Strength": 3.5})
    g.t.links.new(em.outputs[0], g.out.inputs["Surface"])
    return g.mat


def mat_fog():
    g = G("MAT_fog", volume=True)
    z = g.z()
    low = g.math("SUBTRACT", 1.0, g.step(z, 1.6, 1.6), clamp=True)               # ground mist layer
    wisps = g.step(g.noise(0.09, 5), 0.5, 0.25)
    dens = g.math("ADD", 0.003, g.math("MULTIPLY", g.math("MULTIPLY", low, wisps), 0.07))
    vol = g.n("ShaderNodeVolumePrincipled", {"Color": (0.80, 0.70, 0.86, 1), "Density": dens, "Anisotropy": 0.55})
    g.t.links.new(vol.outputs[0], g.out.inputs["Volume"])
    return g.mat


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------- scene dressing ----------
def materials():
    stone, wood = mat_stone(), mat_wood("MAT_torii", stone_below=0.62)
    lantern = mat_stone("MAT_stone_lantern", glow_z=(1.71, 2.19))
    roofs = {"PH_temple_main": 6.1, "PH_temple_right": 5.1, "PH_temple_back": 5.6}
    table = [("PH_floor_courtyard", mat_floor()),
             ("PH_ground_outer", mat_simple("MAT_ground_dark", (0.008, 0.008, 0.01, 1), 0.35)),
             ("PH_torii_gate", wood), ("SRC_stone_lantern", lantern), ("SRC_broken_stone_lantern", lantern),
             ("SRC_cherry_tree", mat_tree()), ("SRC_banner", mat_simple("MAT_banner_cloth", (0.22, 0.012, 0.012, 1), 0.8)),
             ("SRC_paper_lantern", mat_simple("MAT_paper_lantern", (0.5, 0.02, 0.01, 1), 0.6, RED_GLOW, 2.0)),
             ("SRC_pine", mat_simple("MAT_pine", (0.004, 0.008, 0.006, 1), 0.8)),
             ("PH_blood_moon", mat_moon())]
    done = set()
    for name, mat in table:
        assign(bpy.data.objects[name], mat)
        done.add(bpy.data.objects[name].data.name)
    for name, rz in roofs.items():
        assign(bpy.data.objects[name], mat_temple("MAT_" + name[3:], rz))
        done.add(bpy.data.objects[name].data.name)
    for o in bpy.data.objects:  # everything else (dais, stairs, terrace, rocks) is stone
        if o.type == "MESH" and o.data.name not in done:
            assign(o, stone)
            done.add(o.data.name)


def light(name, kind, loc, target=None, **props):
    d = bpy.data.lights.new(name, kind)
    for k, v in props.items():
        setattr(d, k, v)
    o = bpy.data.objects.new(name, d)
    o.location = loc
    if target is not None:
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


def lighting():
    scn = bpy.context.scene
    old = bpy.data.objects.get("LGT_Key_Moon")
    if old:
        bpy.data.objects.remove(old)
    scn.view_layers[0].material_override = None
    w = bpy.data.worlds.new("WORLD_night")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.010, 0.014, 0.040, 1)   # replaced by a night HDRI later
    bg.inputs[1].default_value = 1.2
    scn.world = w
    # cold moonlight key (front-left, high) and red rim from the blood moon behind the torii
    light("LGT_Key_Moon_Cold", "SUN", (-20, -25, 40), (0, 0, 0), energy=1.3, color=(0.55, 0.70, 1.0),
          angle=math.radians(3))
    rim = light("LGT_Rim_BloodMoon", "SUN", (8, 80, 30), (0, 0, 0), energy=0.9, color=(1.0, 0.10, 0.06),
                angle=math.radians(5))
    rim.visible_volume_scatter = False   # keep the red rim off the fog so the sky stays dark
    moon = bpy.data.objects["PH_blood_moon"]   # face the disc toward the arena so it reads as a circle
    moon.rotation_euler = (Vector((0, -10, 2)) - moon.location).to_track_quat("Z", "Y").to_euler()
    # practicals: stone lanterns, paper lanterns, glow from inside the temples
    for i, (x, y, _) in enumerate(L.LANTERNS):
        v = Vector((-x, -y, 0)).normalized() * 0.55
        light(f"LGT_Lantern.{i:02d}", "POINT", (x + v.x, y + v.y, 1.95), energy=28, color=RED_GLOW[:3],
              shadow_soft_size=0.25)
    for i, (x, y, z) in enumerate(L.PAPER_LANTERNS):
        light(f"LGT_Paper.{i:02d}", "POINT", (x + (0.6 if x < 0 else -0.6), y, z), energy=18,
              color=(1.0, 0.16, 0.06), shadow_soft_size=0.3)
    light("LGT_Temple_Main_Glow", "AREA", (-11.0, 5.0, 3.6), (-4, 5, 0), energy=70, color=(1.0, 0.13, 0.05),
          size=12, shape="RECTANGLE", size_y=2.5)
    light("LGT_Temple_Back_Glow", "AREA", (3.0, 24.5, 4.5), (3, 14, 1), energy=110, color=(1.0, 0.13, 0.05),
          size=12, shape="RECTANGLE", size_y=3)


def fog():
    bpy.ops.mesh.primitive_cube_add(location=(0, 15, 14))
    o = bpy.context.object
    o.scale = (48, 48, 14.02)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.name = "FX_fog_volume"
    assign(o, mat_fog())
    o.visible_shadow = False


def quad(name, size, bend=0.0):
    m = bpy.data.meshes.new(name)
    s = size / 2
    m.from_pydata([(-s, -s * 0.7, 0), (s, -s * 0.7, bend), (s, s * 0.7, bend), (-s, s * 0.7, 0)], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new(name, m)
    return o


def particles(preview_frame):
    scn = bpy.context.scene
    fx = bpy.data.collections.new("COL_FX")
    scn.collection.children.link(fx)
    src = bpy.data.collections["COL_Prop_Sources"]
    petal = quad("SRC_petal", 0.09, bend=0.02)
    assign(petal, mat_simple("MAT_petal", (0.95, 0.55, 0.68, 1), 0.5, (0.95, 0.45, 0.6, 1), 0.3))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.02, location=(0, -200, 0))
    flake = bpy.context.object
    flake.name = "SRC_snowflake"
    for u in list(flake.users_collection):
        u.objects.unlink(flake)
    assign(flake, mat_simple("MAT_snow", (0.9, 0.92, 1, 1), 0.4, (0.8, 0.85, 1, 1), 0.8))
    for o in (petal, flake):
        src.objects.link(o)
    petal.location = (0, -200, 0)

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 4, 13))
    em = bpy.context.object
    em.name = "FX_sky_emitter"
    em.scale = (30, 40, 1)
    em.show_instancer_for_render = False   # hide the plane itself but keep its particles renderable
    em.show_instancer_for_viewport = False
    for u in list(em.users_collection):
        u.objects.unlink(em)
    fx.objects.link(em)
    for name, inst, count, grav, size, brown in (("FX_petals", petal, 8000, 0.035, 1.0, 1.6),
                                                 ("FX_snow", flake, 9000, 0.05, 1.0, 0.9)):
        mod = em.modifiers.new(name, "PARTICLE_SYSTEM")
        ps = mod.particle_system.settings
        ps.name = name
        ps.count = count
        ps.frame_start, ps.frame_end = -260, 760          # pre-rolled so the air is already full at frame 1
        ps.lifetime = 240
        ps.emit_from = "FACE"
        ps.distribution = "RAND"
        ps.normal_factor = 0.0
        ps.object_align_factor = (0.25, -0.1, -0.35)       # gentle wind drift
        ps.effector_weights.gravity = grav
        ps.brownian_factor = brown
        ps.drag_factor = 0.12
        ps.render_type = "OBJECT"
        ps.instance_object = inst
        ps.particle_size = size
        ps.size_random = 0.5
        ps.use_rotations = True
        ps.rotation_factor_random = 1.0
        ps.phase_factor_random = 2.0
        ps.use_dynamic_rotation = True
        ps.angular_velocity_mode = "RAND"
        ps.angular_velocity_factor = 1.5
        mod.particle_system.seed = count

    # fallen petals resting on the wet floor (one static mesh)
    verts, faces = [], []
    for i in range(900):
        x, y = random.uniform(-12, 12), random.uniform(-15, 15)
        if random.random() < 0.6:  # cluster under the trees
            tx, ty = random.choice(L.CHERRY_TREES)
            x, y = tx + random.gauss(0, 3.5), ty + random.gauss(0, 3.5)
        if not (-12 < x < 12 and -15 < y < 15):
            continue
        a, s = random.uniform(0, 6.28), random.uniform(0.018, 0.03)
        n = len(verts)
        for dx, dy in ((-1, -0.7), (1, -0.7), (1, 0.7), (-1, 0.7)):
            verts.append((x + s * (dx * math.cos(a) - dy * math.sin(a)), y + s * (dx * math.sin(a) + dy * math.cos(a)), 0.004))
        faces.append((n, n + 1, n + 2, n + 3))
    m = bpy.data.meshes.new("FX_fallen_petals")
    m.from_pydata(verts, [], faces)
    fallen = bpy.data.objects.new("FX_fallen_petals", m)
    fx.objects.link(fallen)
    assign(fallen, bpy.data.materials["MAT_petal"])

    scn.frame_start, scn.frame_end = 1, 720
    for f in range(-260, preview_frame + 1):  # step the simulation up to the preview frame
        scn.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for psys in em.evaluated_get(dg).particle_systems:
        alive = [p for p in psys.particles if p.alive_state == "ALIVE"]
        zs = [p.location.z for p in alive] or [0]
        print(f"PARTICLES {psys.name}: alive={len(alive)} z=[{min(zs):.1f}, {max(zs):.1f}]")


def render(path, samples, res=(1280, 720)):
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    c = scn.cycles
    c.samples, c.use_denoising, c.use_adaptive_sampling = samples, True, True
    c.max_bounces, c.volume_bounces, c.volume_max_steps = 5, 0, 96
    try:
        c.volume_step_rate = 4.0
    except AttributeError:
        pass
    scn.view_settings.view_transform = "AgX"
    try:
        scn.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scn.view_settings.exposure = 0.0
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.resolution_percentage = 100
    scn.render.use_motion_blur = False
    cam = bpy.data.objects["CAM_hero_wide"]
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 17.0
    cam.data.dof.aperture_fstop = 2.8
    scn.camera = cam
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a.isdigit()]
    samples = int(args[0]) if args else 64
    frame = int(args[1]) if len(args) > 1 else 40
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "arena_blockout.blend"))
    materials()
    lighting()
    fog()
    particles(frame)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "arena_lit.blend"))
    render(os.path.join(ROOT, "previews", "stage1b_mood_hero.png"), samples)
