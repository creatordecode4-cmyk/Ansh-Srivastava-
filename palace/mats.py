"""Procedural PBR materials + atmosphere for the haveli courtyard (beauty pass)."""
import bpy, bmesh, random, math, os
from mathutils import Vector

def _nt(name):
    m = bpy.data.materials.new('MAT_' + name); m.use_nodes = True
    return m, m.node_tree

class G:
    """Tiny node-graph helper."""
    def __init__(s, nt):
        s.nt = nt; s.N = nt.nodes.new; s.L = nt.links.new
        s.geo = s.N('ShaderNodeNewGeometry'); s.pos = s.geo.outputs['Position']; s.nrm = s.geo.outputs['Normal']
        s.oi = s.N('ShaderNodeObjectInfo')
    def _in(s, sock, v):
        if isinstance(v, bpy.types.NodeSocket): s.L(v, sock)
        else: sock.default_value = v
    def noise(s, scale, detail=4.0, rough=.55, vec=None, dist=0.0):
        n = s.N('ShaderNodeTexNoise'); s.L(vec or s.pos, n.inputs['Vector'])
        n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; n.inputs['Distortion'].default_value = dist
        return n.outputs['Fac']
    def rng(s, v, a, b, c=0.0, d=1.0):
        n = s.N('ShaderNodeMapRange'); n.clamp = True; n.interpolation_type = 'SMOOTHSTEP'
        s._in(n.inputs['Value'], v); n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c; n.inputs['To Max'].default_value = d
        return n.outputs['Result']
    def m(s, op, a, b=0.0):
        n = s.N('ShaderNodeMath'); n.operation = op; n.use_clamp = False
        s._in(n.inputs[0], a); s._in(n.inputs[1], b); return n.outputs[0]
    def mix(s, f, a, b):
        n = s.N('ShaderNodeMix'); n.data_type = 'RGBA'
        s._in(n.inputs[0], f); s._in(n.inputs[6], a if isinstance(a, bpy.types.NodeSocket) else (*a, 1)); s._in(n.inputs[7], b if isinstance(b, bpy.types.NodeSocket) else (*b, 1))
        return n.outputs[2]
    def sepz(s, v):
        n = s.N('ShaderNodeSeparateXYZ'); s.L(v, n.inputs[0]); return n.outputs['Z']

def puddle_mask(g, lo, hi):
    return g.rng(g.noise(.17, 3.0, .5), lo, hi)

def stone(name, col, col2, rough, moss=.3, crack=.6, wet=False, vein=False, edge=.5, dirt=.8):
    mat, nt = _nt(name); g = G(nt); b = nt.nodes['Principled BSDF']
    big = g.noise(.35, 3); fine = g.noise(14, 2, .7); mid = g.noise(2.2, 2)
    c = g.mix(g.rng(big, .3, .7), col, col2)
    c = g.mix(g.rng(mid, .35, .75, 0, .35), c, tuple(x*.6 for x in col))
    if vein:
        w = g.N('ShaderNodeTexWave'); g.L(g.pos, w.inputs['Vector']); w.inputs['Scale'].default_value = .6
        w.inputs['Distortion'].default_value = 9; w.inputs['Detail'].default_value = 4; w.inputs['Detail Scale'].default_value = 1.5
        c = g.mix(g.rng(w.outputs['Fac'], .78, .97, 0, .5), c, (.32, .31, .32))
    hsv = g.N('ShaderNodeHueSaturation'); g.L(c, hsv.inputs['Color'])
    g.L(g.m('ADD', g.m('MULTIPLY', g.oi.outputs['Random'], .3), .85), hsv.inputs['Value']); c = hsv.outputs['Color']
    vo = g.N('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = 1.6
    wp = g.N('ShaderNodeVectorMath'); wp.operation = 'ADD'; g.L(g.pos, wp.inputs[0])
    nz = g.N('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; g.L(g.pos, nz.inputs['Vector']); g.L(nz.outputs['Color'], wp.inputs[1])
    g.L(wp.outputs[0], vo.inputs['Vector'])
    crk = g.m('MULTIPLY', g.rng(vo.outputs['Distance'], .0, .012, 1, 0), g.rng(big, .45, .6, 0, crack))
    c = g.mix(crk, c, (.04, .03, .025))
    ao = g.N('ShaderNodeAmbientOcclusion'); ao.samples = int(os.environ.get('PAL_AO', '1')); ao.inputs['Distance'].default_value = .6
    dmask = g.m('MULTIPLY', g.rng(ao.outputs['AO'], .35, .95, 1, 0), g.rng(mid, .2, .7, .45, 1))   # dirt = inverted AO
    c = g.mix(g.m('MULTIPLY', dmask, dirt*.7), c, (.10, .075, .05))
    if os.environ.get('PAL_BEVEL', '0') == '1':
        bv = g.N('ShaderNodeBevel'); bv.samples = 2; bv.inputs['Radius'].default_value = .03
        dp = g.N('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'; g.L(bv.outputs[0], dp.inputs[0]); g.L(g.nrm, dp.inputs[1])
        em0 = g.rng(dp.outputs['Value'], .9, .995, 1, 0)
    else:   # cheap edge mask: mesh pointiness (convex bevelled edges read > 0.5)
        em0 = g.rng(g.geo.outputs['Pointiness'], .52, .6, 0, 1)
    emask = g.m('MULTIPLY', em0, g.rng(fine, .3, .7, 0, edge))   # edge wear
    c = g.mix(emask, c, tuple(min(x*1.7+.05, .82) for x in col))
    up = g.rng(g.sepz(g.nrm), .1, .9, .25, 1); low = g.rng(g.sepz(g.pos), .3, 7.0, 1, .35)
    mm = g.m('MULTIPLY', g.m('MULTIPLY', up, low), g.m('ADD', g.noise(.8, 3), g.m('MULTIPLY', dmask, .35)))
    mossm = g.rng(mm, .72 - .5*moss, .82 - .4*moss, 0, 1 if moss > 0 else 0)
    c = g.mix(mossm, c, g.mix(fine, (.035, .07, .015), (.1, .14, .03)))
    r = g.m('ADD', rough - .12, g.m('MULTIPLY', fine, .24))
    r = g.m('ADD', r, g.m('MULTIPLY', mossm, .2))
    if wet:
        pm = puddle_mask(g, .48, .66)
        c = g.mix(g.m('MULTIPLY', pm, .25), c, (.05, .042, .034))
        r = g.m('ADD', g.m('MULTIPLY', r, g.m('SUBTRACT', 1.0, pm)), g.m('MULTIPLY', pm, g.m('ADD', .05, g.m('MULTIPLY', fine, .1))))
    g.L(c, b.inputs['Base Color']); g.L(r, b.inputs['Roughness'])
    bp = g.N('ShaderNodeBump'); bp.inputs['Strength'].default_value = .5; bp.inputs['Distance'].default_value = .02
    g.L(fine, bp.inputs['Height'])
    g.L(bp.outputs[0], b.inputs['Normal'])
    return mat

def simple(name, col, rough, metallic=0.0, var=.25, emit=None, bump=0.0):
    mat, nt = _nt(name); g = G(nt); b = nt.nodes['Principled BSDF']
    n = g.noise(6, 4)
    c = g.mix(g.rng(n, .3, .7, 0, var), col, tuple(x*.5 for x in col))
    hsv = g.N('ShaderNodeHueSaturation'); g.L(c, hsv.inputs['Color'])
    g.L(g.m('ADD', g.m('MULTIPLY', g.oi.outputs['Random'], .4), .8), hsv.inputs['Value'])
    g.L(g.m('ADD', g.m('MULTIPLY', g.oi.outputs['Random'], .06), .47), hsv.inputs['Hue'])
    g.L(hsv.outputs['Color'], b.inputs['Base Color'])
    g.L(g.m('ADD', rough-.08, g.m('MULTIPLY', n, .16)), b.inputs['Roughness']); b.inputs['Metallic'].default_value = metallic
    if emit:
        b.inputs['Emission Color'].default_value = (*emit[0], 1); b.inputs['Emission Strength'].default_value = emit[1]
    if bump:
        bp = g.N('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; g.L(g.noise(40, 3), bp.inputs['Height']); g.L(bp.outputs[0], b.inputs['Normal'])
    return mat

def leaf(name):
    mat, nt = _nt(name); g = G(nt); b = nt.nodes['Principled BSDF']
    c = g.mix(g.noise(5, 2), (.06, .20, .03), (.22, .34, .06)); c = g.mix(g.rng(g.noise(1.2, 2), .55, .75, 0, .5), c, (.3, .2, .05))
    g.L(c, b.inputs['Base Color']); b.inputs['Roughness'].default_value = .45
    tr = g.N('ShaderNodeBsdfTranslucent'); g.L(g.mix(.5, c, (.3, .4, .05)), tr.inputs['Color'])
    mx = g.N('ShaderNodeMixShader'); mx.inputs[0].default_value = .35; g.L(b.outputs[0], mx.inputs[1]); g.L(tr.outputs[0], mx.inputs[2])
    g.L(mx.outputs[0], nt.nodes['Material Output'].inputs['Surface']); return mat

def water(name):
    mat, nt = _nt(name); g = G(nt); nt.nodes.remove(nt.nodes['Principled BSDF'])
    gl = g.N('ShaderNodeBsdfGlossy'); gl.inputs['Color'].default_value = (.9, .9, .9, 1)
    g.L(g.m('ADD', .05, g.m('MULTIPLY', g.noise(3, 2), .1)), gl.inputs['Roughness'])      # 0.05 - 0.15
    bp = g.N('ShaderNodeBump'); bp.inputs['Strength'].default_value = .02; g.L(g.noise(25, 2), bp.inputs['Height']); g.L(bp.outputs[0], gl.inputs['Normal'])
    t1 = g.N('ShaderNodeBsdfTransparent'); t1.inputs['Color'].default_value = (.78, .74, .68, 1)
    fr = g.N('ShaderNodeFresnel'); fr.inputs['IOR'].default_value = 1.33
    m1 = g.N('ShaderNodeMixShader'); g.L(g.rng(fr.outputs[0], .02, .5, .12, 1), m1.inputs[0]); g.L(t1.outputs[0], m1.inputs[1]); g.L(gl.outputs[0], m1.inputs[2])
    t0 = g.N('ShaderNodeBsdfTransparent'); m2 = g.N('ShaderNodeMixShader')
    g.L(puddle_mask(g, .59, .65), m2.inputs[0]); g.L(t0.outputs[0], m2.inputs[1]); g.L(m1.outputs[0], m2.inputs[2])
    g.L(m2.outputs[0], nt.nodes['Material Output'].inputs['Surface']); return mat

def volume(name, density, aniso, col=(1, 1, 1)):
    mat, nt = _nt(name); nt.nodes.remove(nt.nodes['Principled BSDF'])
    v = nt.nodes.new('ShaderNodeVolumeScatter'); v.inputs['Density'].default_value = density; v.inputs['Anisotropy'].default_value = aniso
    v.inputs['Color'].default_value = (*col, 1)
    nt.links.new(v.outputs[0], nt.nodes['Material Output'].inputs['Volume']); return mat

def apply(sc):
    M = {
        'sand': stone('Sandstone', (.66, .47, .25), (.52, .34, .17), .8, moss=.22),
        'sand2': stone('SandstoneRed', (.60, .37, .20), (.47, .27, .14), .8, moss=.2),
        'marble': stone('Marble', (.74, .71, .64), (.62, .58, .50), .3, moss=.15, crack=.35, vein=True, edge=.2, dirt=.9),
        'floor': stone('FloorWet', (.40, .33, .25), (.30, .25, .19), .78, moss=.04, crack=.8, wet=True),
        'floor2': stone('FloorDry', (.44, .35, .25), (.32, .25, .18), .8, moss=.15, crack=.6),
        'rock': stone('Rock', (.25, .22, .18), (.16, .14, .12), .85, moss=.6, edge=.2),
        'dirt': simple('Dirt', (.12, .09, .06), .92, bump=.3),
        'wood': simple('Wood', (.13, .07, .035), .6, var=.6, bump=.2),
        'brass': simple('Brass', (.72, .50, .20), .38, metallic=1.0, var=.5),
        'glow': simple('LanternGlass', (.9, .6, .25), .2, emit=((1.0, .5, .15), 3.0)),
        'terracotta': simple('Terracotta', (.42, .17, .09), .75, var=.5, bump=.15),
        'ivy': leaf('Ivy'), 'stem': simple('Stem', (.10, .07, .04), .8),
        'moss': simple('Moss', (.05, .10, .02), .95, var=.6, bump=.5),
        'dryleaf': simple('DryLeaf', (.30, .16, .05), .7, var=.6),
        'bg1': simple('BG1', (.42, .30, .18), .9), 'bg2': simple('BG2', (.38, .29, .20), .9), 'bg3': simple('BG3', (.22, .21, .15), .95),
        'water': water('Puddle'),
    }
    for ob in sc.objects:
        k = ob.get('mat')
        if k in M and ob.type == 'MESH' and ob.material_slots:
            ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = M[k]
    fx = bpy.data.collections.get('COL_FX') or bpy.data.collections.new('COL_FX')
    if fx.name not in [c.name for c in sc.collection.children]: sc.collection.children.link(fx)
    def vbox(name, sx, sy, z0, z1, dens, aniso, col=(1, .74, .46)):
        me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); ob.scale = (sx, sy, z1-z0); ob.location = (0, 0, (z0+z1)/2)
        me.materials.append(volume(name, dens, aniso, col)); ob['mat'] = 'volume'; fx.objects.link(ob)
    sun = bpy.data.lights['LGT_Key_Sun']; sun.energy = 10.0
    if os.environ.get('PAL_NOVOL') == '1': return
    vbox('VOL_Courtyard', 42, 42, -.05, 13, .004, .6)       # light-shaft cube: density 0.02, anisotropy 0.6
    vbox('VOL_HazeNear', 180, 180, -.06, 30, .0003, .5)     # distance haze, 3 nested layers
    vbox('VOL_HazeMid', 480, 480, -.07, 60, .00018, .45)
    vbox('VOL_HazeFar', 1000, 1000, -.08, 110, .0001, .4)
    # dust motes: tiny bright specks, only visible where the sun shafts hit them
    me = bpy.data.meshes.new('Dust'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0); bm.to_mesh(me); bm.free()
    dm, nt = _nt('Dust'); b = nt.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (.9, .85, .75, 1); b.inputs['Roughness'].default_value = .9; b.inputs['Alpha'].default_value = .45
    me.materials.append(dm); r = random.Random(3)
    for i in range(2600):
        ob = bpy.data.objects.new('Dust', me); ob.location = (r.uniform(-14.5, 14.5), r.uniform(-14.5, 14.5), r.uniform(.25, 4.5))
        ob.scale = (r.uniform(.0025, .006),)*3; ob['mat'] = 'dust'; ob.visible_shadow = False; fx.objects.link(ob)
    sun = bpy.data.lights['LGT_Key_Sun']; sun.energy = 10.0
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .6
    sc.world.node_tree.nodes['Vector Math.003'].inputs['Scale'].default_value = 2.0
    e = sc.world.node_tree.nodes['Color Ramp'].color_ramp.elements
    for el, c in zip(sorted(e, key=lambda x: x.position), ((.80, .42, .20), (.42, .40, .52), (.16, .27, .55))): el.color = (*c, 1)
    bpy.data.objects['Water'].location.z = -.0015
