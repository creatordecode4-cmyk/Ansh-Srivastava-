"""
STEP 2 - materials, Geometry Nodes scattering, lighting and atmosphere.
Imported by build_scene.py. Every material is MAT_*, every light LGT_*.
"""
import bpy, math, random
from mathutils import Vector, kdtree

# ======================================================================
# small node helpers
# ======================================================================
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out

def N(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        if k.startswith("in_"):
            n.inputs[k[3:].replace("_", " ")].default_value = v
        else:
            setattr(n, k, v)
    return n

def L(nt, a, b):
    nt.links.new(a, b)

def ramp(nt, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = interp
    els = r.color_ramp.elements
    while len(els) > 2:
        els.remove(els[-1])
    for i, (pos, col) in enumerate(stops):
        if i < 2:
            e = els[i]; e.position = pos
        else:
            e = els.new(pos)
        e.color = col if len(col) == 4 else (*col, 1.0)
    return r

def mix_rgb(nt, blend, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"; m.blend_type = blend
    L(nt, fac, m.inputs["Factor"]) if not isinstance(fac, float) else None
    if isinstance(fac, float):
        m.inputs["Factor"].default_value = fac
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = val if len(val) == 4 else (*val, 1)
        else:
            L(nt, val, sock)
    return m.outputs[2]

def keyframe_linear(socket_owner, path, f0, v0, f1, v1):
    """Linear keyframes with linear extrapolation -> endless constant motion."""
    socket_owner.default_value = v0
    socket_owner.keyframe_insert("default_value", frame=f0)
    socket_owner.default_value = v1
    socket_owner.keyframe_insert("default_value", frame=f1)

def make_fcurves_linear(id_data):
    ad = id_data.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:                       # Blender 5 layered actions
        curves = []
        for layer in ad.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves.extend(bag.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        fc.extrapolation = "LINEAR"

def set_disp(m, method="BOTH"):
    try:
        m.displacement_method = method
    except Exception:
        m.cycles.displacement_method = method

# ======================================================================
# materials
# ======================================================================
def mat_rock(name, cracks=0.7, strata=1.0, base=(0.42, 0.38, 0.33), warm=(0.55, 0.36, 0.20),
             moss_amt=0.55, disp=0.12, coord="Object", scale=1.0):
    """Layered rock: wave strata + streaks + moss on up-facing + golden lichen."""
    m, nt, out = new_mat(name)
    tc = N(nt, "ShaderNodeTexCoord")
    co = tc.outputs[coord]
    geo = N(nt, "ShaderNodeNewGeometry")
    sep_n = N(nt, "ShaderNodeSeparateXYZ"); L(nt, geo.outputs["Normal"], sep_n.inputs[0])

    # strata bands along Z
    wave = N(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z",
             in_Scale=0.35 / scale, in_Distortion=2.0, in_Detail=4.0, in_Detail_Scale=1.5)
    L(nt, co, wave.inputs["Vector"])
    big = N(nt, "ShaderNodeTexNoise", in_Scale=0.16 / scale, in_Detail=8.0, in_Roughness=0.65)
    L(nt, co, big.inputs["Vector"])
    fine = N(nt, "ShaderNodeTexNoise", in_Scale=2.5 / scale, in_Detail=10.0, in_Roughness=0.65)
    L(nt, co, fine.inputs["Vector"])
    # vertical water-stain streaks
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 1.0, 0.06)
    L(nt, co, mp.inputs["Vector"])
    streak = N(nt, "ShaderNodeTexNoise", in_Scale=0.9 / scale, in_Detail=3.0)
    L(nt, mp.outputs[0], streak.inputs["Vector"])

    # colour regions come from large noise (grey rock <-> warm iron-stained rock)
    base_r = ramp(nt, [(0.32, (0.24, 0.23, 0.22)), (0.45, base), (0.6, warm), (0.72, (0.66, 0.60, 0.52))])
    L(nt, big.outputs["Fac"], base_r.inputs[0])
    # strata are only a subtle light/dark modulation on top
    strata_r = ramp(nt, [(0.0, (0.78, 0.78, 0.78)), (0.6, (1, 1, 1)), (1.0, (0.92, 0.92, 0.92))])
    L(nt, wave.outputs["Fac"], strata_r.inputs[0])
    col = mix_rgb(nt, "MULTIPLY", strata, base_r.outputs[0], strata_r.outputs[0])
    st_r = ramp(nt, [(0.4, (1, 1, 1)), (0.75, (0.55, 0.5, 0.45))])
    L(nt, streak.outputs["Fac"], st_r.inputs[0])
    col = mix_rgb(nt, "MULTIPLY", 0.6 * strata, col, st_r.outputs[0])

    # cracks: voronoi cell edges, darkened
    # vertical fractures: warped, stretched voronoi edges, masked so they're sparse
    warp = N(nt, "ShaderNodeTexNoise", in_Scale=0.5 / scale, in_Detail=4.0)
    L(nt, co, warp.inputs["Vector"])
    wv = N(nt, "ShaderNodeMix"); wv.data_type = "VECTOR"; wv.inputs["Factor"].default_value = 0.35
    L(nt, co, wv.inputs[4]); L(nt, warp.outputs["Color"], wv.inputs[5])
    cm = N(nt, "ShaderNodeMapping"); cm.inputs["Scale"].default_value = (1.0, 1.0, 0.25)
    L(nt, wv.outputs[1], cm.inputs["Vector"])
    crk = N(nt, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE", in_Scale=0.6 / scale)
    L(nt, cm.outputs[0], crk.inputs["Vector"])
    crk_r = ramp(nt, [(0.0, (0, 0, 0)), (0.025, (1, 1, 1))])
    L(nt, crk.outputs["Distance"], crk_r.inputs[0])
    cmask = N(nt, "ShaderNodeTexNoise", in_Scale=0.3 / scale, in_Detail=2.0)
    L(nt, co, cmask.inputs["Vector"])
    cmask_r = ramp(nt, [(0.45, (0, 0, 0)), (0.6, (1, 1, 1))])
    L(nt, cmask.outputs["Fac"], cmask_r.inputs[0])
    inv = N(nt, "ShaderNodeMath", operation="SUBTRACT"); inv.inputs[0].default_value = 1.0
    L(nt, crk_r.outputs[0], inv.inputs[1])                       # 1 on crack
    cr = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, inv.outputs[0], cr.inputs[0]); L(nt, cmask_r.outputs[0], cr.inputs[1])
    cr2 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); cr2.inputs[1].default_value = cracks
    L(nt, cr.outputs[0], cr2.inputs[0])
    col = mix_rgb(nt, "MIX", cr2.outputs[0], col, (0.06, 0.05, 0.05))
    mid = N(nt, "ShaderNodeTexNoise", in_Scale=0.9 / scale, in_Detail=6.0)
    L(nt, co, mid.inputs["Vector"])
    mid_r = ramp(nt, [(0.35, (0.7, 0.7, 0.7)), (0.65, (1.1, 1.05, 1.0))])
    L(nt, mid.outputs["Fac"], mid_r.inputs[0])
    col = mix_rgb(nt, "MULTIPLY", 0.8, col, mid_r.outputs[0])
    # golden lichen patches (voronoi spots masked by noise)
    vor = N(nt, "ShaderNodeTexVoronoi", in_Scale=1.6 / scale)
    L(nt, co, vor.inputs["Vector"])
    lich_r = ramp(nt, [(0.0, (1, 1, 1)), (0.22, (0, 0, 0))])
    L(nt, vor.outputs["Distance"], lich_r.inputs[0])
    lmask_n = N(nt, "ShaderNodeTexNoise", in_Scale=0.25 / scale, in_Detail=2.0)
    L(nt, co, lmask_n.inputs["Vector"])
    lmask_r = ramp(nt, [(0.52, (0, 0, 0)), (0.62, (1, 1, 1))])
    L(nt, lmask_n.outputs["Fac"], lmask_r.inputs[0])
    lich = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, lich_r.outputs[0], lich.inputs[0]); L(nt, lmask_r.outputs[0], lich.inputs[1])
    col = mix_rgb(nt, "MIX", lich.outputs[0], col, (0.62, 0.45, 0.10))

    # moss on up-facing surfaces, broken up by noise
    up = N(nt, "ShaderNodeMapRange", in_From_Min=0.45, in_From_Max=0.85)
    L(nt, sep_n.outputs["Z"], up.inputs["Value"])
    mn = N(nt, "ShaderNodeTexNoise", in_Scale=0.6 / scale, in_Detail=8.0)
    L(nt, co, mn.inputs["Vector"])
    mn_r = ramp(nt, [(0.42, (0, 0, 0)), (0.58, (1, 1, 1))])
    L(nt, mn.outputs["Fac"], mn_r.inputs[0])
    moss = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, up.outputs[0], moss.inputs[0]); L(nt, mn_r.outputs[0], moss.inputs[1])
    moss2 = N(nt, "ShaderNodeMath", operation="MULTIPLY", in_Value=moss_amt)
    moss2.inputs[1].default_value = moss_amt
    L(nt, moss.outputs[0], moss2.inputs[0])
    moss_col = mix_rgb(nt, "MIX", fine.outputs["Fac"], (0.07, 0.14, 0.03), (0.22, 0.30, 0.06))
    col = mix_rgb(nt, "MIX", moss2.outputs[0], col, moss_col)

    bsdf = N(nt, "ShaderNodeBsdfPrincipled")
    L(nt, col, bsdf.inputs["Base Color"])
    rr = N(nt, "ShaderNodeMapRange", in_To_Min=0.62, in_To_Max=0.92)
    L(nt, fine.outputs["Fac"], rr.inputs["Value"])
    L(nt, rr.outputs[0], bsdf.inputs["Roughness"])
    bump = N(nt, "ShaderNodeBump", in_Strength=0.45, in_Distance=0.05)
    L(nt, fine.outputs["Fac"], bump.inputs["Height"])
    L(nt, bump.outputs[0], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs[0], out.inputs["Surface"])

    # true displacement: strata ledges + large noise
    h = N(nt, "ShaderNodeMath", operation="MULTIPLY_ADD")
    L(nt, fine.outputs["Fac"], h.inputs[0]); h.inputs[1].default_value = 0.25
    L(nt, big.outputs["Fac"], h.inputs[2])
    dsp = N(nt, "ShaderNodeDisplacement", in_Scale=disp, in_Midlevel=1.0)
    L(nt, h.outputs[0], dsp.inputs["Height"])
    L(nt, dsp.outputs[0], out.inputs["Displacement"])
    set_disp(m, "BOTH")
    return m

def mat_ground():
    """Meadow grass -> dirt on steep slopes -> wet gravel in the channel."""
    m, nt, out = new_mat("MAT_Ground")
    tc = N(nt, "ShaderNodeTexCoord"); co = tc.outputs["Object"]
    geo = N(nt, "ShaderNodeNewGeometry")
    sn = N(nt, "ShaderNodeSeparateXYZ"); L(nt, geo.outputs["Normal"], sn.inputs[0])
    sp = N(nt, "ShaderNodeSeparateXYZ"); L(nt, geo.outputs["Position"], sp.inputs[0])

    n1 = N(nt, "ShaderNodeTexNoise", in_Scale=0.05, in_Detail=6.0); L(nt, co, n1.inputs["Vector"])
    n2 = N(nt, "ShaderNodeTexNoise", in_Scale=1.2, in_Detail=10.0); L(nt, co, n2.inputs["Vector"])
    grass_r = ramp(nt, [(0.3, (0.10, 0.22, 0.03)), (0.55, (0.26, 0.42, 0.06)), (0.75, (0.48, 0.52, 0.12))])
    L(nt, n1.outputs["Fac"], grass_r.inputs[0])
    dirt = mix_rgb(nt, "MIX", n2.outputs["Fac"], (0.22, 0.17, 0.12), (0.40, 0.33, 0.24))
    gravel = mix_rgb(nt, "MIX", n2.outputs["Fac"], (0.20, 0.17, 0.13), (0.46, 0.39, 0.30))

    steep = N(nt, "ShaderNodeMapRange", in_From_Min=0.8, in_From_Max=0.62)
    L(nt, sn.outputs["Z"], steep.inputs["Value"])
    col = mix_rgb(nt, "MIX", steep.outputs[0], grass_r.outputs[0], dirt)
    wet = N(nt, "ShaderNodeAttribute", attribute_name="w_gravel", attribute_type="GEOMETRY")
    wet = wet.outputs["Fac"].node
    col = mix_rgb(nt, "MIX", wet.outputs["Fac"], col, gravel)
    # fake depth absorption: riverbed under the water turns glacial turquoise
    deep = N(nt, "ShaderNodeMapRange", in_From_Min=-0.4, in_From_Max=-1.4, in_To_Max=0.85)
    L(nt, sp.outputs["Z"], deep.inputs["Value"])
    col = mix_rgb(nt, "MIX", deep.outputs[0], col, (0.02, 0.32, 0.30))

    bsdf = N(nt, "ShaderNodeBsdfPrincipled")
    L(nt, col, bsdf.inputs["Base Color"])
    rough = N(nt, "ShaderNodeMapRange", in_To_Min=0.85, in_To_Max=0.35)
    L(nt, wet.outputs["Fac"], rough.inputs["Value"]); L(nt, rough.outputs[0], bsdf.inputs["Roughness"])
    bump = N(nt, "ShaderNodeBump", in_Strength=0.35, in_Distance=0.1)
    L(nt, n2.outputs["Fac"], bump.inputs["Height"]); L(nt, bump.outputs[0], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs[0], out.inputs["Surface"])
    return m

def mat_foliage(name, dark, light, sss=0.25, bump_scale=18.0):
    """Leaf / needle material with subsurface and per-object colour jitter."""
    m, nt, out = new_mat(name)
    oi = N(nt, "ShaderNodeObjectInfo")
    tc = N(nt, "ShaderNodeTexCoord")
    nz = N(nt, "ShaderNodeTexNoise", in_Scale=bump_scale, in_Detail=4.0)
    L(nt, tc.outputs["Object"], nz.inputs["Vector"])
    add = N(nt, "ShaderNodeMath", operation="MULTIPLY_ADD")
    L(nt, oi.outputs["Random"], add.inputs[0]); add.inputs[1].default_value = 0.6
    L(nt, nz.outputs["Fac"], add.inputs[2])
    add2 = N(nt, "ShaderNodeMath", operation="MULTIPLY", in_Value=0.6)
    add2.inputs[1].default_value = 0.65
    L(nt, add.outputs[0], add2.inputs[0])
    col = mix_rgb(nt, "MIX", add2.outputs[0], dark, light)
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.55)
    L(nt, col, bsdf.inputs["Base Color"])
    bsdf.inputs["Subsurface Weight"].default_value = sss
    bsdf.inputs["Subsurface Radius"].default_value = (0.4, 0.8, 0.2)
    bsdf.inputs["Subsurface Scale"].default_value = 0.02
    bump = N(nt, "ShaderNodeBump", in_Strength=0.6, in_Distance=0.05)
    L(nt, nz.outputs["Fac"], bump.inputs["Height"]); L(nt, bump.outputs[0], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs[0], out.inputs["Surface"])
    return m

def mat_bark():
    m, nt, out = new_mat("MAT_Bark")
    tc = N(nt, "ShaderNodeTexCoord")
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (6, 6, 0.6)
    L(nt, tc.outputs["Object"], mp.inputs["Vector"])
    nz = N(nt, "ShaderNodeTexNoise", in_Scale=4.0, in_Detail=8.0); L(nt, mp.outputs[0], nz.inputs["Vector"])
    col = mix_rgb(nt, "MIX", nz.outputs["Fac"], (0.08, 0.05, 0.03), (0.28, 0.18, 0.11))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.85)
    L(nt, col, bsdf.inputs["Base Color"])
    bump = N(nt, "ShaderNodeBump", in_Strength=0.8); L(nt, nz.outputs["Fac"], bump.inputs["Height"])
    L(nt, bump.outputs[0], bsdf.inputs["Normal"]); L(nt, bsdf.outputs[0], out.inputs["Surface"])
    return m

def mat_water():
    """Glacial river: transmission 1, IOR 1.33, rough 0.05, turquoise, animated
    ripples, white foam from the per-vertex 'foam' attribute (near rocks)."""
    m, nt, out = new_mat("MAT_Water")
    tc = N(nt, "ShaderNodeTexCoord")
    # ripples: 4D noise, flowing toward camera (-Y) + evolving (W)
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 0.45, 1.0)
    L(nt, tc.outputs["Object"], mp.inputs["Vector"])
    rip = N(nt, "ShaderNodeTexNoise", noise_dimensions="4D", in_Scale=1.6, in_Detail=6.0, in_Roughness=0.55)
    L(nt, mp.outputs[0], rip.inputs["Vector"])
    keyframe_linear(rip.inputs["W"], None, 1, 0.0, 480, 8.0)
    keyframe_linear(mp.inputs["Location"], None, 1, (0, 0, 0), 480, (0, 30.0, 0))

    water = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.05, in_IOR=1.33)
    water.inputs["Base Color"].default_value = (0.12, 0.80, 0.72, 1)    # turquoise tint
    water.inputs["Specular IOR Level"].default_value = 0.2
    water.inputs["Transmission Weight"].default_value = 1.0
    bump = N(nt, "ShaderNodeBump", in_Strength=0.5, in_Distance=0.15)
    L(nt, rip.outputs["Fac"], bump.inputs["Height"]); L(nt, bump.outputs[0], water.inputs["Normal"])

    foam_bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.6)
    foam_bsdf.inputs["Base Color"].default_value = (0.9, 0.93, 0.93, 1)
    foam_bsdf.inputs["Subsurface Weight"].default_value = 0.3
    foam_bsdf.inputs["Subsurface Scale"].default_value = 0.05

    attr = N(nt, "ShaderNodeAttribute", attribute_name="foam", attribute_type="GEOMETRY")
    fz = N(nt, "ShaderNodeTexNoise", noise_dimensions="4D", in_Scale=6.0, in_Detail=8.0)
    L(nt, mp.outputs[0], fz.inputs["Vector"])
    keyframe_linear(fz.inputs["W"], None, 1, 0.0, 480, 20.0)
    mul = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, attr.outputs["Fac"], mul.inputs[0]); L(nt, fz.outputs["Fac"], mul.inputs[1])
    fr = ramp(nt, [(0.33, (0, 0, 0)), (0.5, (1, 1, 1))])
    L(nt, mul.outputs[0], fr.inputs[0])
    mix = N(nt, "ShaderNodeMixShader")
    L(nt, fr.outputs[0], mix.inputs[0]); L(nt, water.outputs[0], mix.inputs[1]); L(nt, foam_bsdf.outputs[0], mix.inputs[2])
    L(nt, mix.outputs[0], out.inputs["Surface"])
    make_fcurves_linear(nt)
    return m

def mat_waterfall():
    """Falling sheet: vertical streaks scrolling down, partly transparent."""
    m, nt, out = new_mat("MAT_Waterfall")
    tc = N(nt, "ShaderNodeTexCoord")
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Scale"].default_value = (2.2, 2.2, 0.12)
    L(nt, tc.outputs["Object"], mp.inputs["Vector"])
    keyframe_linear(mp.inputs["Location"], None, 1, (0, 0, 0), 480, (0, 0, 60.0))
    nz = N(nt, "ShaderNodeTexNoise", in_Scale=3.0, in_Detail=8.0, in_Roughness=0.6)
    L(nt, mp.outputs[0], nz.inputs["Vector"])
    a = ramp(nt, [(0.42, (0.0, 0.0, 0.0)), (0.6, (0.95, 0.95, 0.95))])
    L(nt, nz.outputs["Fac"], a.inputs[0])
    gx = N(nt, "ShaderNodeSeparateXYZ"); L(nt, tc.outputs["Generated"], gx.inputs[0])
    edge = N(nt, "ShaderNodeMapRange", in_From_Min=0.0, in_From_Max=0.5)     # 0 at edges -> 1 centre
    pp = N(nt, "ShaderNodeMath", operation="PINGPONG"); pp.inputs[1].default_value = 0.5
    L(nt, gx.outputs["X"], pp.inputs[0]); L(nt, pp.outputs[0], edge.inputs["Value"])
    em = N(nt, "ShaderNodeMath", operation="POWER"); em.inputs[1].default_value = 0.6
    L(nt, edge.outputs[0], em.inputs[0])
    am = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, a.outputs[0], am.inputs[0]); L(nt, em.outputs[0], am.inputs[1])
    a = am.outputs[0].node
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.35, in_IOR=1.33)
    bsdf.inputs["Base Color"].default_value = (0.88, 0.93, 0.95, 1)
    bsdf.inputs["Subsurface Weight"].default_value = 0.5
    bsdf.inputs["Subsurface Scale"].default_value = 0.2
    bsdf.inputs["Emission Color"].default_value = (0.85, 0.9, 0.92, 1)
    bsdf.inputs["Emission Strength"].default_value = 0.05
    L(nt, a.outputs[0], bsdf.inputs["Alpha"])
    L(nt, bsdf.outputs[0], out.inputs["Surface"])
    make_fcurves_linear(nt)
    return m

def mat_mountain():
    """Distant peaks: grey rock, green lower slopes, then aerial-perspective
    haze toward the sky colour by camera distance."""
    m, nt, out = new_mat("MAT_Mountain")
    tc = N(nt, "ShaderNodeTexCoord")
    geo = N(nt, "ShaderNodeNewGeometry")
    sp = N(nt, "ShaderNodeSeparateXYZ"); L(nt, geo.outputs["Position"], sp.inputs[0])
    nz = N(nt, "ShaderNodeTexNoise", in_Scale=0.02, in_Detail=8.0); L(nt, tc.outputs["Object"], nz.inputs["Vector"])
    rock = mix_rgb(nt, "MIX", nz.outputs["Fac"], (0.30, 0.30, 0.31), (0.55, 0.54, 0.52))
    lo = N(nt, "ShaderNodeMapRange", in_From_Min=60.0, in_From_Max=140.0)
    L(nt, sp.outputs["Z"], lo.inputs["Value"])
    col = mix_rgb(nt, "MIX", lo.outputs[0], (0.10, 0.17, 0.06), rock)
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=0.9)
    L(nt, col, bsdf.inputs["Base Color"])
    haze = N(nt, "ShaderNodeEmission", in_Strength=1.0)
    haze.inputs["Color"].default_value = (0.55, 0.68, 0.85, 1)
    cam = N(nt, "ShaderNodeCameraData")
    hz = N(nt, "ShaderNodeMapRange", in_From_Min=200.0, in_From_Max=900.0, in_To_Min=0.25, in_To_Max=0.7)
    L(nt, cam.outputs["View Distance"], hz.inputs["Value"])
    mix = N(nt, "ShaderNodeMixShader")
    L(nt, hz.outputs[0], mix.inputs[0]); L(nt, bsdf.outputs[0], mix.inputs[1]); L(nt, haze.outputs[0], mix.inputs[2])
    L(nt, mix.outputs[0], out.inputs["Surface"])
    return m

def mat_cloud():
    m, nt, out = new_mat("MAT_Cloud")
    tc = N(nt, "ShaderNodeTexCoord")
    nz = N(nt, "ShaderNodeTexNoise", in_Scale=1.5, in_Detail=8.0, in_Roughness=0.6)
    L(nt, tc.outputs["Generated"], nz.inputs["Vector"])
    # soft round falloff so the card edges never show
    grad = N(nt, "ShaderNodeTexGradient", gradient_type="SPHERICAL")
    mp = N(nt, "ShaderNodeMapping"); mp.inputs["Location"].default_value = (-1, -1, 0)
    mp.inputs["Scale"].default_value = (2, 2, 2)
    L(nt, tc.outputs["Generated"], mp.inputs["Vector"]); L(nt, mp.outputs[0], grad.inputs["Vector"])
    mul = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, nz.outputs["Fac"], mul.inputs[0]); L(nt, grad.outputs["Fac"], mul.inputs[1])
    a = ramp(nt, [(0.18, (0, 0, 0)), (0.42, (0.85, 0.85, 0.85))])
    L(nt, mul.outputs[0], a.inputs[0])
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", in_Roughness=1.0)
    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
    bsdf.inputs["Emission Color"].default_value = (0.75, 0.82, 0.95, 1)
    bsdf.inputs["Emission Strength"].default_value = 0.6
    L(nt, a.outputs[0], bsdf.inputs["Alpha"])
    L(nt, bsdf.outputs[0], out.inputs["Surface"])
    return m

def mat_volume(name, density, aniso, color=(1, 1, 1), noise_scale=0.0, animate=False):
    m, nt, out = new_mat(name)
    vol = N(nt, "ShaderNodeVolumePrincipled", in_Anisotropy=aniso)
    vol.inputs["Color"].default_value = (*color, 1)
    if noise_scale:
        tc = N(nt, "ShaderNodeTexCoord")
        nz = N(nt, "ShaderNodeTexNoise", noise_dimensions="4D", in_Scale=noise_scale, in_Detail=3.0)
        L(nt, tc.outputs["Object"], nz.inputs["Vector"])
        if animate:
            keyframe_linear(nz.inputs["W"], None, 1, 0.0, 480, 3.0)
        # density = noise * radial falloff (Generated sphere)
        grad = N(nt, "ShaderNodeTexGradient", gradient_type="SPHERICAL")
        mp = N(nt, "ShaderNodeMapping"); mp.inputs["Location"].default_value = (-1, -1, -1)
        mp.inputs["Scale"].default_value = (2, 2, 2)
        L(nt, tc.outputs["Generated"], mp.inputs["Vector"]); L(nt, mp.outputs[0], grad.inputs["Vector"])
        r = ramp(nt, [(0.4, (0, 0, 0)), (0.75, (1, 1, 1))])
        L(nt, nz.outputs["Fac"], r.inputs[0])
        mul = N(nt, "ShaderNodeMath", operation="MULTIPLY")
        L(nt, r.outputs[0], mul.inputs[0]); L(nt, grad.outputs["Fac"], mul.inputs[1])
        mul2 = N(nt, "ShaderNodeMath", operation="MULTIPLY"); mul2.inputs[1].default_value = density
        L(nt, mul.outputs[0], mul2.inputs[0]); L(nt, mul2.outputs[0], vol.inputs["Density"])
    else:
        vol.inputs["Density"].default_value = density
    L(nt, vol.outputs[0], out.inputs["Volume"])
    make_fcurves_linear(nt)
    return m

# ======================================================================
# Geometry Nodes scatter
# ======================================================================
def gn_scatter(name, source_obj, attr, density, collection, scale_rng, seed, col_target,
               wind=0.0):
    """Scatter instances of `collection` over `source_obj`, density driven by
    a point attribute. Optional wind sway (looping, from Scene Time)."""
    ng = bpy.data.node_groups.new(f"GN_{name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd = ng.nodes; lk = ng.links
    out = nd.new("NodeGroupOutput")
    oi = nd.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = source_obj
    oi.transform_space = "RELATIVE"
    na = nd.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT"; na.inputs["Name"].default_value = attr
    dens = nd.new("ShaderNodeMath"); dens.operation = "MULTIPLY"; dens.inputs[1].default_value = density
    lk.new(na.outputs["Attribute"], dens.inputs[0])
    dist = nd.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = "RANDOM"
    dist.inputs["Seed"].default_value = seed
    lk.new(oi.outputs["Geometry"], dist.inputs["Mesh"]); lk.new(dens.outputs[0], dist.inputs["Density"])

    ci = nd.new("GeometryNodeCollectionInfo"); ci.inputs["Collection"].default_value = collection
    ci.inputs["Separate Children"].default_value = True; ci.inputs["Reset Children"].default_value = True
    n_children = len(collection.objects)
    ridx = nd.new("FunctionNodeRandomValue"); ridx.data_type = "INT"
    ridx.inputs["Min"].default_value = 0; ridx.inputs["Max"].default_value = n_children - 1
    ridx.inputs["Seed"].default_value = seed + 1
    for s in ridx.inputs:
        if s.name == "Min" and s.type == "INT": s.default_value = 0
        if s.name == "Max" and s.type == "INT": s.default_value = n_children - 1
    rrot = nd.new("FunctionNodeRandomValue"); rrot.data_type = "FLOAT_VECTOR"
    rrot.inputs[0].default_value = (0, 0, 0); rrot.inputs[1].default_value = (0, 0, 6.283)
    rrot.inputs["Seed"].default_value = seed + 2
    rsc = nd.new("FunctionNodeRandomValue"); rsc.data_type = "FLOAT"
    for s in rsc.inputs:
        if s.name == "Min" and s.type == "VALUE": s.default_value = scale_rng[0]
        if s.name == "Max" and s.type == "VALUE": s.default_value = scale_rng[1]
    rsc.inputs["Seed"].default_value = seed + 3

    iop = nd.new("GeometryNodeInstanceOnPoints")
    lk.new(dist.outputs["Points"], iop.inputs["Points"])
    lk.new(ci.outputs[0], iop.inputs["Instance"])
    iop.inputs["Pick Instance"].default_value = True
    lk.new(ridx.outputs[2] if ridx.outputs[2].enabled else ridx.outputs["Value"], iop.inputs["Instance Index"])
    lk.new(rrot.outputs[0], iop.inputs["Rotation"])
    fl_out = [o for o in rsc.outputs if o.type == "VALUE" and o.enabled][0]
    lk.new(fl_out, iop.inputs["Scale"])
    last = iop.outputs[0]

    if wind > 0.0:
        # sway = wind * sin(2*pi*t/period + phase(x,y)), period divides 20 s -> loops
        st = nd.new("GeometryNodeInputSceneTime")
        pos = nd.new("GeometryNodeInputPosition")
        sep = nd.new("ShaderNodeSeparateXYZ"); lk.new(pos.outputs[0], sep.inputs[0])
        ph = nd.new("ShaderNodeMath"); ph.operation = "MULTIPLY_ADD"
        lk.new(sep.outputs["X"], ph.inputs[0]); ph.inputs[1].default_value = 0.35
        lk.new(sep.outputs["Y"], ph.inputs[2])
        ph2 = nd.new("ShaderNodeMath"); ph2.operation = "MULTIPLY"; ph2.inputs[1].default_value = 0.25
        lk.new(ph.outputs[0], ph2.inputs[0])
        tt = nd.new("ShaderNodeMath"); tt.operation = "MULTIPLY_ADD"
        lk.new(st.outputs["Seconds"], tt.inputs[0]); tt.inputs[1].default_value = 2 * math.pi / 4.0  # 4 s period
        lk.new(ph2.outputs[0], tt.inputs[2])
        sn = nd.new("ShaderNodeMath"); sn.operation = "SINE"; lk.new(tt.outputs[0], sn.inputs[0])
        tt2 = nd.new("ShaderNodeMath"); tt2.operation = "MULTIPLY_ADD"
        lk.new(st.outputs["Seconds"], tt2.inputs[0]); tt2.inputs[1].default_value = 2 * math.pi / 2.5  # gust
        lk.new(ph.outputs[0], tt2.inputs[2])
        sn2 = nd.new("ShaderNodeMath"); sn2.operation = "SINE"; lk.new(tt2.outputs[0], sn2.inputs[0])
        a1 = nd.new("ShaderNodeMath"); a1.operation = "MULTIPLY"; a1.inputs[1].default_value = wind
        lk.new(sn.outputs[0], a1.inputs[0])
        a2 = nd.new("ShaderNodeMath"); a2.operation = "MULTIPLY"; a2.inputs[1].default_value = wind * 0.5
        lk.new(sn2.outputs[0], a2.inputs[0])
        cmb = nd.new("ShaderNodeCombineXYZ")
        lk.new(a1.outputs[0], cmb.inputs["X"]); lk.new(a2.outputs[0], cmb.inputs["Y"])
        rot = nd.new("GeometryNodeRotateInstances")
        lk.new(last, rot.inputs["Instances"]); lk.new(cmb.outputs[0], rot.inputs["Rotation"])
        rot.inputs["Local Space"].default_value = True
        last = rot.outputs[0]

    lk.new(last, out.inputs[0])
    me = bpy.data.meshes.new(f"VEG_Scatter_{name}")
    obj = bpy.data.objects.new(f"VEG_Scatter_{name}", me)
    col_target.objects.link(obj)
    mod = obj.modifiers.new("Scatter", "NODES"); mod.node_group = ng
    return obj

# ======================================================================
# assets for scattering
# ======================================================================
def make_grass_clump(name, seed, blades=9):
    rnd = random.Random(seed)
    verts, faces = [], []
    for b in range(blades):
        a = rnd.uniform(0, 6.283); r = rnd.uniform(0, 0.12)
        bx, by = math.cos(a) * r, math.sin(a) * r
        h = rnd.uniform(0.25, 0.6); w = rnd.uniform(0.012, 0.025)
        lean = rnd.uniform(0.05, 0.25); la = rnd.uniform(0, 6.283)
        ox, oy = math.cos(la) * lean, math.sin(la) * lean
        tx, ty = -math.sin(la) * w, math.cos(la) * w
        i = len(verts)
        segs = 3
        for s in range(segs):
            t = s / segs
            cx = bx + ox * t * t; cy = by + oy * t * t; z = h * t
            ww = 1 - t * 0.6
            verts += [(cx - tx * ww, cy - ty * ww, z), (cx + tx * ww, cy + ty * ww, z)]
        verts.append((bx + ox, by + oy, h))
        for s in range(segs - 1):
            k = i + s * 2
            faces.append((k, k + 1, k + 3, k + 2))
        k = i + (segs - 1) * 2
        faces.append((k, k + 1, len(verts) - 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update(); me.shade_smooth()
    return me

def make_fern(name, seed):
    """Small leafy ground plant: radial fronds."""
    rnd = random.Random(seed)
    verts, faces = [], []
    for f in range(7):
        a = f / 7 * 6.283 + rnd.uniform(-.2, .2)
        L_ = rnd.uniform(0.35, 0.6)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        i = len(verts)
        for s in range(5):
            t = s / 4
            w = 0.09 * math.sin(math.pi * t) + 0.005
            z = 0.25 * math.sin(math.pi * t * 0.8)
            verts += [(dx * L_ * t - px * w, dy * L_ * t - py * w, z),
                      (dx * L_ * t + px * w, dy * L_ * t + py * w, z)]
        for s in range(4):
            k = i + s * 2
            faces.append((k, k + 1, k + 3, k + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update(); me.shade_smooth()
    return me

# ======================================================================
# water foam attribute
# ======================================================================
def bake_foam(water_obj, rock_objs, fall_xy):
    kd = kdtree.KDTree(len(rock_objs))
    for i, r in enumerate(rock_objs):
        kd.insert(Vector((r.location.x, r.location.y, 0)), i)
    kd.balance()
    me = water_obj.data
    at = me.attributes.new("foam", "FLOAT", "POINT")
    vals = []
    for v in me.vertices:
        p = water_obj.matrix_world @ v.co
        q = Vector((p.x, p.y, 0))
        f = 0.0
        for (co, idx, d) in kd.find_n(q, 4):
            r = rock_objs[idx]
            rad = max(r.scale.x, r.scale.y) * 1.05
            # only rocks that reach the water surface make foam
            if r.location.z + r.scale.z * 0.55 > -0.6:
                f = max(f, 1.0 - max(0.0, d - rad * 0.8) / 0.6)
        # plunge pool churn
        dfall = (Vector((p.x, p.y)) - Vector(fall_xy)).length
        f = max(f, 1.0 - max(0.0, dfall - 3.0) / 9.0)
        vals.append(max(0.0, min(1.0, f)))
    at.data.foreach_set("value", vals)

# ======================================================================
# lighting
# ======================================================================
def setup_lighting(scene, col_lights, sun_dir, sun_strength=4.5):
    """Warm key sun + single-scattering (Nishita) sky aligned to it."""
    for o in list(col_lights.objects):
        bpy.data.objects.remove(o)
    sd = bpy.data.lights.new("LGT_Sun_Key", "SUN")
    sd.energy = sun_strength
    sd.color = (1.0, 0.82, 0.60)              # ~4200 K warm afternoon
    sd.angle = math.radians(0.8)
    sun = bpy.data.objects.new("LGT_Sun_Key", sd)
    col_lights.objects.link(sun)
    sun.rotation_euler = sun_dir.to_track_quat("Z", "Y").to_euler()

    # soft warm bounce from behind the camera: models the cliff faces that the
    # back-lit key leaves in shadow (motivated by sunlit meadow/valley floor)
    fd = bpy.data.lights.new("LGT_Fill_Bounce", "SUN")
    fd.energy = 0.9; fd.color = (1.0, 0.9, 0.78); fd.angle = math.radians(25)
    fd.use_shadow = False
    fill = bpy.data.objects.new("LGT_Fill_Bounce", fd); col_lights.objects.link(fill)
    fdir = Vector((-0.35, -0.9, 0.35)).normalized()
    fill.rotation_euler = fdir.to_track_quat("Z", "Y").to_euler()

    world = scene.world
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "SINGLE_SCATTERING"
    sky.sun_disc = True
    sky.sun_size = math.radians(1.2)
    sky.sun_intensity = 0.25          # the lamp does the lighting; sky gives colour + disc
    sky.sun_elevation = math.asin(sun_dir.z)
    sky.sun_rotation = math.atan2(sun_dir.x, sun_dir.y)
    sky.altitude = 600.0
    sky.aerosol_density = 0.5
    sky.air_density = 1.4             # deeper blue         # a little extra haze
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.35
    hs = nt.nodes.new("ShaderNodeHueSaturation")      # art-directed: richer blue like the reference
    hs.inputs["Saturation"].default_value = 1.9
    nt.links.new(sky.outputs[0], hs.inputs["Color"])
    # saturated sky only where the camera sees it; lighting uses the physical sky
    lp = nt.nodes.new("ShaderNodeLightPath")
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
    nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs["Factor"])
    nt.links.new(sky.outputs[0], mx.inputs[6]); nt.links.new(hs.outputs[0], mx.inputs[7])
    nt.links.new(mx.outputs[2], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return sun, sky

def box(name, loc, size, col):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.location = loc; o.scale = size
    return o

def sphere(name, loc, size, col):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.location = loc; o.scale = size
    return o

def plane(name, loc, size, rot, col):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new()
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.location = loc; o.scale = (*size, 1); o.rotation_euler = rot
    return o
