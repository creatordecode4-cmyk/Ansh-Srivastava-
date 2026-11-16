"""Step 7: export output/character.glb (posed, static).
glTF cannot carry Cycles procedural node trees or hair curves, so this builds an export copy:
 - every visible mesh evaluated in the final pose (modifiers applied)
 - scalp hair / brows / lashes converted to thin ribbon strips (subset of strands)
 - simple PBR materials; skin masks and iris/sclera baked into vertex colours (COLOR_0)
"""
import sys, os, math
import numpy as np
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
from common import *

bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "character.blend"))
sc = bpy.context.scene
sc.frame_set(sc.frame_end)
deps = bpy.context.evaluated_depsgraph_get()
exp = bpy.data.collections.new("EXPORT"); sc.collection.children.link(exp)


def pbr(name, col, rough, metal=0.0, alpha=1.0, vcol=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Alpha"].default_value = alpha
    if vcol:
        c = nt.nodes.new("ShaderNodeVertexColor"); c.layer_name = vcol
        nt.links.new(c.outputs["Color"], b.inputs["Base Color"])
    if alpha < 1:
        m.surface_render_method = "BLENDED"
    return m

MATS = {
    "MAT_Skin": pbr("EXP_Skin", (0.5, 0.3, 0.23), 0.5, vcol="Col"),
    "MAT_Eye_Sclera_Iris": pbr("EXP_Eye", (0.8, 0.78, 0.75), 0.3, vcol="Col"),
    "MAT_Eye_Cornea": pbr("EXP_Cornea", (1, 1, 1), 0.0, alpha=0.08),
    "MAT_Eye_Caruncle": pbr("EXP_Caruncle", (0.72, 0.36, 0.33), 0.3),
    "MAT_Eye_Tearline": pbr("EXP_Tear", (0.9, 0.85, 0.85), 0.05, alpha=0.3),
    "MAT_Cotton_Tshirt_Purple": pbr("EXP_Tshirt_Purple", (0.08, 0.013, 0.27), 0.85),
    "MAT_Cotton_Twill_Black": pbr("EXP_Trousers_Black", (0.014, 0.014, 0.015), 0.85),
    "MAT_Sneaker_Leather_White": pbr("EXP_Leather_White", (0.78, 0.77, 0.74), 0.45),
    "MAT_Sneaker_Rubber_Sole": pbr("EXP_Rubber", (0.80, 0.78, 0.73), 0.65),
    "MAT_Sneaker_Laces": pbr("EXP_Laces", (0.80, 0.79, 0.76), 0.85),
    "MAT_Sneaker_Eyelets": pbr("EXP_Eyelets", (0.7, 0.7, 0.68), 0.4),
}
M_HAIR = pbr("EXP_Hair_DarkBrown", (0.035, 0.018, 0.010), 0.45)


def bake_vcols(src_obj, me):
    """skin: masks -> colour; eye: eye_uv -> colour"""
    n = len(me.vertices)
    col = None
    if "masks" in me.attributes:
        mk = np.zeros(n * 4, np.float32); me.attributes["masks"].data.foreach_get("color", mk); mk = mk.reshape(-1, 4)
        base = np.array([0.50, 0.30, 0.225])
        col = base[None, :] * (1 - 0.45 * mk[:, :1]) + np.array([0.58, 0.20, 0.16])[None, :] * 0.45 * mk[:, :1]
        col = col * (1 - 0.8 * mk[:, 3:4]) + np.array([0.48, 0.17, 0.15])[None, :] * 0.8 * mk[:, 3:4]
    elif "eye_uv" in me.attributes:
        uv = np.zeros(n * 3, np.float32); me.attributes["eye_uv"].data.foreach_get("vector", uv); r = uv.reshape(-1, 3)[:, 0]
        col = np.where(r[:, None] < 0.33, [0.005, 0.005, 0.005], np.where(r[:, None] < 0.55, [0.15, 0.11, 0.04], np.where(r[:, None] < 0.97, [0.09, 0.17, 0.07], [0.62, 0.57, 0.53])))
    if col is None:
        return
    a = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    a.data.foreach_set("color", np.hstack([col, np.ones((n, 1))]).astype(np.float32).ravel())


count = 0
for o in list(sc.objects):
    if o.hide_render or o.name.startswith(("SIM_", "SET_", "CAM_", "LGT_")) or o.type not in ("MESH", "CURVE"):
        continue
    e = o.evaluated_get(deps)
    me = bpy.data.meshes.new_from_object(e, preserve_all_data_layers=True, depsgraph=deps)
    me.transform(o.matrix_world)
    src_mats = [s.material.name if s.material else None for s in o.material_slots]
    me.materials.clear()
    for nm in src_mats:
        me.materials.append(MATS.get(nm, pbr("EXP_" + str(nm), (0.5, 0.5, 0.5), 0.5)))
    bake_vcols(o, me)
    no = bpy.data.objects.new(o.name, me); exp.objects.link(no)
    count += 1

# hair curves -> ribbons
HC = Vector((0, -0.05, 1.69))
for name, step, wscale in (("HAIR_Scalp", 7, 3.0), ("HAIR_Eyebrows", 1, 2.0), ("HAIR_Eyelashes", 1, 1.6)):
    o = bpy.data.objects[name]
    e = o.evaluated_get(deps)
    cv = e.data
    npts = len(cv.points)
    pos = np.zeros(npts * 3, np.float32); cv.attributes["position"].data.foreach_get("vector", pos); pos = pos.reshape(-1, 3)
    rad = np.zeros(npts, np.float32); cv.attributes["radius"].data.foreach_get("value", rad)
    offs = np.zeros(len(cv.curves) + 1, np.int64)
    for i, c in enumerate(cv.curves):
        offs[i] = c.first_point_index
    offs[-1] = npts
    M = np.array(o.matrix_world)
    pos = pos @ M[:3, :3].T + M[:3, 3]
    verts, faces = [], []
    for ci in range(0, len(cv.curves), step):
        a, b = offs[ci], offs[ci + 1]
        p = pos[a:b]; r = rad[a:b]
        if len(p) > 10:
            sel = np.linspace(0, len(p) - 1, 10).round().astype(int); p = p[sel]; r = r[sel]
        t = np.gradient(p, axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
        out = p - np.array(HC); out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
        side = np.cross(t, out); side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
        w = np.maximum(r * wscale * step ** 0.5, 0.00004)[:, None]
        base = len(verts)
        for k in range(len(p)):
            verts.append(p[k] - side[k] * w[k]); verts.append(p[k] + side[k] * w[k])
        for k in range(len(p) - 1):
            i0 = base + 2 * k
            faces.append((i0, i0 + 1, i0 + 3, i0 + 2))
    me = bpy.data.meshes.new(name + "_Ribbons")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.materials.append(M_HAIR)
    no = bpy.data.objects.new(name + "_Ribbons", me); exp.objects.link(no)
    print(name, "ribbons", len(faces) // 9)

for o in bpy.data.objects:
    o.select_set(o.name in exp.objects)
path = os.path.join(OUT, "character.glb")
bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=False,
                          export_animations=False, export_skins=False, export_yup=True,
                          export_draco_mesh_compression_enable=False)
print("OK glb", count, "meshes", os.path.getsize(path) / 1e6, "MB")
