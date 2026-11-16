"""Step 6: renders.  usage: s6_render.py <job> [samples] [scale%]
jobs: final | face | clay | wire | rigtest | turntable
"""
import sys, os, math
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from common import *

job = sys.argv[1]
samples = int(sys.argv[2]) if len(sys.argv) > 2 else 256
pct = int(sys.argv[3]) if len(sys.argv) > 3 else 100
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "character.blend"))
sc = bpy.context.scene
sc.cycles.samples = samples
sc.render.resolution_percentage = pct
sc.render.threads_mode = "AUTO"
PREV = os.path.join(WORK, "renders"); os.makedirs(PREV, exist_ok=True)
F_END = sc.frame_end
sc.frame_set(F_END)


def override(color=(0.55, 0.55, 0.55), wire=False):
    m = bpy.data.materials.new("OVR")
    nt = m.node_tree; nt.nodes.clear(); L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial", (600, 0))
    b = node(nt, "ShaderNodeBsdfPrincipled", (300, 0))
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = 0.55
    if wire:
        w = node(nt, "ShaderNodeWireframe", (0, 200)); w.use_pixel_size = True; w.inputs[0].default_value = 0.6
        e = node(nt, "ShaderNodeEmission", (300, 200)); e.inputs[0].default_value = (0.9, 0.92, 0.95, 1); e.inputs[1].default_value = 1.6
        b.inputs["Base Color"].default_value = (0.05, 0.05, 0.055, 1)
        mx = node(nt, "ShaderNodeMixShader", (450, 0))
        L.new(w.outputs[0], mx.inputs[0]); L.new(b.outputs[0], mx.inputs[1]); L.new(e.outputs[0], mx.inputs[2])
        L.new(mx.outputs[0], out.inputs[0])
    else:
        L.new(b.outputs[0], out.inputs[0])
    return m


def hide(prefixes, val=True):
    for o in bpy.data.objects:
        if o.name.startswith(prefixes):
            o.hide_render = val


def set_material_override(m, keep_set=True):
    """override character materials only (keep floor/backdrop)"""
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVES", "CURVE") and not o.name.startswith(("SET_", "SIM_")):
            for slot in getattr(o, "material_slots", []):
                slot.link = "OBJECT"; slot.material = m
            if o.type == "CURVES" and not o.material_slots:
                pass


def render(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("wrote", path, flush=True)

if job == "final":
    sc.camera = bpy.data.objects["CAM_Hero_85mm"]
    render(os.environ.get("DH_OUTFILE", os.path.join(OUT, "final_render.png")))
elif job == "face":
    sc.camera = bpy.data.objects["CAM_Face_85mm"]
    render(os.environ.get("DH_OUTFILE", os.path.join(OUT, "face_closeup.png")))
elif job in ("clay", "wire"):
    sc.camera = bpy.data.objects["CAM_Hero_85mm"]
    hide(("HAIR_PeachFuzz",))
    m = override(wire=(job == "wire"))
    set_material_override(m)
    for o in bpy.data.objects:  # hair stays visible as grey strands in clay; hidden in wire
        if o.name.startswith("HAIR_") and job == "wire":
            o.hide_render = True
    if job == "wire":
        for o in bpy.data.objects:
            for md in getattr(o, "modifiers", []):
                if md.type == "SUBSURF":
                    md.render_levels = 1
        bpy.data.objects["CAM_Hero_85mm"].data.dof.use_dof = False
    render(os.path.join(PREV, f"{job}.png"))
elif job == "rigtest":
    # rig test: same armature in 2 poses (frame 1 rest A-pose, frame 30 final pose) -- body + hair only
    sc.camera = bpy.data.objects["CAM_Hero_85mm"]
    hide(("GEO_Tshirt", "GEO_Trousers", "GEO_Sneaker", "HAIR_PeachFuzz"))
    m = override((0.6, 0.6, 0.6)); set_material_override(m)
    body = bpy.data.objects["GEO_Body"]
    for md in body.modifiers:
        if md.type == "MASK":
            md.show_render = False
    for f in (-20, F_END):
        sc.frame_set(f)
        render(os.path.join(PREV, f"rigtest_{'rest' if f < 0 else 'pose'}.png"))
elif job == "turntable":
    sc.camera = bpy.data.objects["CAM_Turntable_85mm"]
    hide(("HAIR_PeachFuzz",))
    piv = bpy.data.objects["CAM_Turntable_Pivot"]
    n = int(os.environ.get("TT_FRAMES", "96"))
    start = int(os.environ.get("TT_START", "0"))
    os.makedirs(os.path.join(PREV, "tt"), exist_ok=True)
    for i in range(start, n):
        piv.rotation_euler = (0, 0, 2 * math.pi * i / n)
        sc.render.filepath = os.path.join(PREV, "tt", f"tt_{i:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("tt frame", i, flush=True)
