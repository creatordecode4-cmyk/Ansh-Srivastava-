"""Quick preview renders: python preview.py <blend> <out_prefix> [clay] [views=front,side,face] [samples]"""
import sys, os, math
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from common import *

blend, out = sys.argv[1], sys.argv[2]
clay = len(sys.argv) > 3 and sys.argv[3] == "clay"
views = (sys.argv[4] if len(sys.argv) > 4 else "front,side,face").split(",")
samples = int(sys.argv[5]) if len(sys.argv) > 5 else 24
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.cycles.adaptive_threshold = 0.02
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.view_transform = "AgX"
sc.render.resolution_percentage = 100
if clay:
    m = bpy.data.materials.new("clay"); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1); b.inputs["Roughness"].default_value = 0.55
    sc.view_layers[0].material_override = m

if "CAM_Preview" not in bpy.data.objects:
    cam = bpy.data.objects.new("CAM_Preview", bpy.data.cameras.new("CAM_Preview"))
    sc.collection.objects.link(cam)
cam = bpy.data.objects["CAM_Preview"]
sc.camera = cam
if not any(o.type == "LIGHT" for o in sc.objects):
    for nm, loc, e, sz in (("k", (-2, -3, 3), 380, 2), ("f", (3, -2, 1.5), 90, 3), ("r", (1, 3, 3), 300, 1.5)):
        l = bpy.data.objects.new("LGT_prev_" + nm, bpy.data.lights.new(nm, "AREA"))
        l.data.energy = e; l.data.size = sz; l.location = loc
        d = Vector((0, 0, 1.2)) - Vector(loc)
        l.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(l)
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.022, 1)

VIEWS = {
    "front": ((0, -6.2, 0.95), (0, 0, 0.88), 50, (600, 1000)),
    "side": ((6.2, 0, 0.95), (0, 0, 0.88), 50, (600, 1000)),
    "back": ((0, 6.2, 0.95), (0, 0, 0.88), 50, (600, 1000)),
    "q34": ((-3.6, -5.0, 1.0), (0, 0, 0.88), 50, (600, 1000)),
    "face": ((0, -1.05, 1.63), (0, 0, 1.6), 85, (560, 640)),
    "eye": ((0.05, -0.36, 1.645), (0.03, -0.13, 1.64), 85, (600, 400)),
    "eyeside": ((0.33, -0.33, 1.645), (0.03, -0.13, 1.64), 85, (600, 400)),
    "mouth": ((0, -0.5, 1.59), (0, 0, 1.59), 85, (500, 400)),
    "face34": ((-0.6, -0.86, 1.64), (0, 0, 1.6), 85, (700, 800)),
    "faceside": ((1.05, -0.05, 1.63), (0, 0, 1.6), 85, (700, 800)),
    "feet": ((-0.9, -1.4, 0.35), (0, -0.05, 0.08), 50, (900, 600)),
    "hands": ((-0.25, -1.9, 0.95), (0, 0, 0.92), 50, (900, 700)),
    "torso": ((-0.5, -2.4, 1.25), (0, 0, 1.15), 85, (800, 900)),
}
for v in views:
    loc, tgt, lens, res = VIEWS[v]
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = f"{out}_{v}.png"
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)
