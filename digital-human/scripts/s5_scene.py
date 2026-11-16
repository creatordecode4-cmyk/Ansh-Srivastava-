"""Step 5: studio scene -- dark cyclorama, subtle floor reflection, key/fill/rim lights, 85 mm cameras,
Cycles + AgX.  Reads work/posed.blend -> output/character.blend
"""
import sys, os, math
import bpy, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from common import *

bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "posed.blend"))
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith(("CAM_Preview", "LGT_prev")):
        bpy.data.objects.remove(o)
C_SET = coll("SET"); C_LGT = coll("LIGHTS"); C_CAM = coll("CAMERAS")

# ---------------------------------------------------------------- cyclorama (floor curving into the back wall)
bm = bmesh.new()
W, D, R, Hh = 8.0, 6.0, 1.2, 5.0
prof = [(y, 0.0) for y in [-D, -2.0, 0.0, 1.0]]
for k in range(1, 13):
    a = math.radians(90 * k / 12)
    prof.append((1.0 + R * math.sin(a), R * (1 - math.cos(a))))
prof.append((1.0 + R, Hh))
nx = 2
rows = []
for y, z in prof:
    rows.append([bm.verts.new((x, y + 1.5, z)) for x in (-W / 2, W / 2)])
for i in range(len(rows) - 1):
    bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
me = bpy.data.meshes.new("SET_Cyclorama"); bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = True
cyc = bpy.data.objects.new("SET_Cyclorama", me); C_SET.objects.link(cyc)
sub = cyc.modifiers.new("Subdivision", "SUBSURF"); sub.levels = 2; sub.render_levels = 3

m = bpy.data.materials.new("MAT_Set_Floor")
nt = m.node_tree; nt.nodes.clear(); L = nt.links
out = node(nt, "ShaderNodeOutputMaterial", (800, 0))
b = node(nt, "ShaderNodeBsdfPrincipled", (500, 0)); L.new(b.outputs[0], out.inputs[0])
geo = node(nt, "ShaderNodeNewGeometry", (-700, 0))
nz = node(nt, "ShaderNodeTexNoise", (-500, 200), Scale=3.0, Detail=6.0)
L.new(geo.outputs["Position"], nz.inputs["Vector"])
mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-250, 200)
mr.inputs[3].default_value = 0.26; mr.inputs[4].default_value = 0.42
L.new(nz.outputs["Fac"], mr.inputs[0]); L.new(mr.outputs[0], b.inputs["Roughness"])
b.inputs["Base Color"].default_value = (0.011, 0.011, 0.012, 1)
b.inputs["Specular IOR Level"].default_value = 0.45
fn = node(nt, "ShaderNodeTexNoise", (-500, -200), Scale=400.0, Detail=3.0)
L.new(geo.outputs["Position"], fn.inputs["Vector"])
bp = node(nt, "ShaderNodeBump", (200, -200), Strength=0.04, Distance=0.001)
L.new(fn.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs[0], b.inputs["Normal"])
cyc.data.materials.append(m)

# ---------------------------------------------------------------- lights (area softboxes, colour temperature via blackbody)
def area(name, loc, target, size, energy, kelvin, shape="RECTANGLE", size_y=None, spread=180):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = energy; ld.shape = shape
    ld.size = size; ld.size_y = size_y or size
    ld.spread = math.radians(spread)
    ld.use_nodes = True
    lnt = ld.node_tree
    bb = lnt.nodes.new("ShaderNodeBlackbody"); bb.inputs[0].default_value = kelvin
    lnt.links.new(bb.outputs[0], lnt.nodes["Emission"].inputs["Color"])
    o = bpy.data.objects.new(name, ld); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    C_LGT.objects.link(o)
    return o

area("LGT_Key_Softbox", (-2.1, -2.6, 2.55), (0, 0, 1.25), 1.3, 230, 5200, size_y=1.0)
area("LGT_Fill_Bounce", (2.8, -2.2, 1.3), (0, 0, 1.0), 2.4, 45, 6200)
area("LGT_Rim_Left", (-1.8, 2.0, 1.9), (0, 0, 1.2), 0.35, 150, 4800, size_y=1.8, spread=90)
area("LGT_Rim_Right", (1.9, 1.8, 2.0), (0, 0, 1.25), 0.35, 175, 6500, size_y=1.8, spread=90)
area("LGT_Hair_Top", (0.3, 0.8, 3.4), (0, 0, 1.7), 0.6, 22, 5600)
glow = area("LGT_Backdrop_Glow", (0.0, 1.2, 0.25), (0, 3.2, 1.2), 1.5, 30, 4200, size_y=0.4)
glow.visible_glossy = False; glow.visible_camera = False

if sc.world is None:
    sc.world = bpy.data.worlds.new("WORLD_Studio")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.004, 0.0045, 1)
sc.world.name = "WORLD_Studio"

# ---------------------------------------------------------------- cameras (85 mm)
def cam(name, loc, target, lens, focus_obj_loc, fstop):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop
    o = bpy.data.objects.new(name, cd); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cd.dof.focus_distance = (Vector(focus_obj_loc) - Vector(loc)).length
    C_CAM.objects.link(o)
    return o

head = Vector((0.0, -0.13, 1.66))
cam("CAM_Hero_85mm", (-1.05, -5.0, 1.05), (0.0, 0.0, 0.92), 85, head, 2.0)
fc = cam("CAM_Face_85mm", (-0.24, -1.02, 1.69), (0.0, -0.10, 1.665), 85, (0.0, -0.15, 1.66), 4.0)
bpy.context.view_layer.update()
eyeL = bpy.data.objects["GEO_Eye_L"]; eyeR = bpy.data.objects["GEO_Eye_R"]
def _ctr(o):
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    return sum(vs, Vector()) / len(vs)
foc = bpy.data.objects.new("CAM_Face_Focus", None); C_CAM.objects.link(foc)
foc.location = (_ctr(eyeL) + _ctr(eyeR)) / 2 + Vector((0, -0.012, 0))
fc.data.dof.focus_object = foc
ec = foc.location
fc.location = ec + Vector((-0.27, -0.98, 0.03))
fc.rotation_euler = (ec + Vector((0.0, 0.02, -0.03)) - fc.location).to_track_quat("-Z", "Y").to_euler()
hero = bpy.data.objects["CAM_Hero_85mm"]
hfoc = bpy.data.objects.new("CAM_Hero_Focus", None); C_CAM.objects.link(hfoc); hfoc.location = ec
hero.data.dof.focus_object = hfoc
# turntable: camera on an orbiting rig
piv = bpy.data.objects.new("CAM_Turntable_Pivot", None); piv.location = (0, 0, 0); C_CAM.objects.link(piv)
tt = cam("CAM_Turntable_85mm", (0, -5.3, 1.05), (0, 0, 0.92), 85, (0, -0.1, 1.4), 2.8)
tt.parent = piv
tt.location = (0, -5.3, 1.05)
sc.camera = bpy.data.objects["CAM_Hero_85mm"]

# ---------------------------------------------------------------- render settings
sc.render.engine = "CYCLES"
cy = sc.cycles
cy.device = "CPU"; cy.samples = 256; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.01
cy.use_denoising = True; cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 10; cy.diffuse_bounces = 4; cy.glossy_bounces = 4; cy.transmission_bounces = 8
cy.transparent_max_bounces = 16; cy.volume_bounces = 0
cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8.0; cy.blur_glossy = 0.5
sc.render.film_transparent = False
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = -0.45
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"

# tidy outliner names / collections
for o in bpy.data.objects:
    if o.type == "CURVE" and o.name.startswith("GEO_"):
        pass
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "character.blend"), compress=True)
print("OK scene")
