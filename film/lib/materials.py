"""Material library entry point. Every builder asks for materials by name: materials.get("MAT_Stone_Mossy").

The real PBR versions live in materials_pbr.py. If that module is missing or fails to build a material, a flat
placeholder with the right overall colour is returned so prop builders keep working.
"""
import bpy

# name: (base colour, roughness, metallic, emission colour or None, emission strength)
PLACEHOLDERS = {
    "MAT_Floor_WetStone": ((0.035, 0.035, 0.04), 0.15, 0.0, None, 0.0),
    "MAT_Stone_Mossy": ((0.07, 0.075, 0.07), 0.75, 0.0, None, 0.0),
    "MAT_Stone_Block": ((0.09, 0.09, 0.095), 0.8, 0.0, None, 0.0),
    "MAT_Wood_Red": ((0.33, 0.03, 0.025), 0.55, 0.0, None, 0.0),
    "MAT_Wood_Dark": ((0.045, 0.03, 0.025), 0.6, 0.0, None, 0.0),
    "MAT_Roof_Tile": ((0.03, 0.032, 0.036), 0.5, 0.0, None, 0.0),
    "MAT_Plaster": ((0.42, 0.4, 0.37), 0.85, 0.0, None, 0.0),
    "MAT_Paper_Lantern": ((0.6, 0.04, 0.03), 0.6, 0.0, (1.0, 0.08, 0.04), 6.0),
    "MAT_Lantern_Glow": ((0.8, 0.1, 0.05), 0.5, 0.0, (1.0, 0.12, 0.05), 12.0),
    "MAT_Window_Glow": ((0.5, 0.12, 0.05), 0.6, 0.0, (1.0, 0.2, 0.08), 1.2),
    "MAT_Banner_Red": ((0.3, 0.02, 0.02), 0.85, 0.0, None, 0.0),
    "MAT_Metal_Dark": ((0.03, 0.03, 0.035), 0.45, 1.0, None, 0.0),
    "MAT_Gold": ((0.7, 0.5, 0.2), 0.35, 1.0, None, 0.0),
    "MAT_Rope": ((0.45, 0.36, 0.2), 0.9, 0.0, None, 0.0),
    "MAT_Bark": ((0.05, 0.035, 0.03), 0.85, 0.0, None, 0.0),
    "MAT_Blossom": ((0.9, 0.55, 0.65), 0.6, 0.0, None, 0.0),
    "MAT_Petal": ((0.92, 0.62, 0.7), 0.6, 0.0, None, 0.0),
    "MAT_Snow": ((0.85, 0.87, 0.9), 0.6, 0.0, None, 0.0),
    "MAT_Ground_Dark": ((0.02, 0.022, 0.02), 0.9, 0.0, None, 0.0),
    "MAT_Moon": ((0.8, 0.05, 0.03), 0.9, 0.0, (1.0, 0.07, 0.04), 8.0),
    "MAT_Pine_Dark": ((0.01, 0.018, 0.014), 0.9, 0.0, None, 0.0),
}
NAMES = list(PLACEHOLDERS)


def _placeholder(name):
    color, rough, metal, emit, strength = PLACEHOLDERS.get(name, ((0.5, 0.0, 0.5), 0.5, 0.0, None, 0.0))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    mat["placeholder"] = True
    return mat


def get(name):
    """Return the named material, building it on first use."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    try:
        from . import materials_pbr
        built = materials_pbr.build(name)
        if built is not None:
            return built
    except Exception as exc:  # fall back so one broken material never stops a build
        print(f"[materials] placeholder used for {name}: {exc!r}")
    return _placeholder(name)
