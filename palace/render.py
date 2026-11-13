"""Render stills / frame ranges. python3 render.py MODE FRAMES [W H SAMPLES]
MODE: clay | beauty | wire ; FRAMES: '1,120,240' or '1-240'"""
import bpy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
mode, frames = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 960; H = int(sys.argv[4]) if len(sys.argv) > 4 else 540
SPP = int(sys.argv[5]) if len(sys.argv) > 5 else 24
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '_work', 'palace_wire.blend' if mode == 'wire' else os.environ.get('PAL_BLEND', 'palace.blend')))
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; c = sc.cycles; c.device = 'CPU'; c.samples = SPP
c.use_adaptive_sampling = True; c.adaptive_threshold = .03
c.use_denoising = True; c.denoiser = 'OPENIMAGEDENOISE'
c.max_bounces = 5; c.diffuse_bounces = 3; c.glossy_bounces = 3; c.transmission_bounces = 3; c.volume_bounces = 0; c.transparent_max_bounces = 6
c.caustics_reflective = False; c.caustics_refractive = False; c.sample_clamp_indirect = 6
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.render.threads_mode = 'AUTO'; sc.render.use_persistent_data = True
sc.view_settings.view_transform = 'AgX'; sc.view_settings.exposure = 0.3
for lk in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try: sc.view_settings.look = lk; print('LOOK', lk); break
    except Exception as e: pass
sc.render.image_settings.file_format = 'PNG'
vl = sc.view_layers[0]
if mode == 'clay':
    m = bpy.data.materials.new('MAT_Clay'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (.5, .5, .5, 1); b.inputs['Roughness'].default_value = .75
    vl.material_override = m
    for ob in sc.objects:
        if ob.get('mat') in ('water', 'volume', 'dust'): ob.hide_render = True
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .9
    # neutral grey sky for clay so only form + light is judged
    nt = sc.world.node_tree
    for l in list(nt.links):
        if l.to_node.type == 'BACKGROUND' and l.to_socket.name == 'Color': nt.links.remove(l)
    nt.nodes['Background'].inputs['Color'].default_value = (.55, .6, .7, 1)
    bpy.data.lights['LGT_Key_Sun'].use_temperature = False; bpy.data.lights['LGT_Key_Sun'].color = (1, 1, 1)
elif mode == 'wire':
    m = bpy.data.materials.new('MAT_Wire'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], o.inputs[0])
    cd = nt.nodes.new('ShaderNodeCameraData'); mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 4; mr.inputs['From Max'].default_value = 60; mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = .25
    nt.links.new(cd.outputs['View Distance'], mr.inputs['Value']); nt.links.new(mr.outputs[0], em.inputs['Strength'])
    vl.material_override = m
    for ob in sc.objects:
        if ob.type == 'LIGHT' or ob.name.startswith('BG_') or ob.name == 'GroundOut': ob.hide_render = True
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    c.use_denoising = False; c.max_bounces = 0; sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
    sc.camera.data.dof.use_dof = False
else:
    import mats; mats.apply(sc)
E = os.environ
if E.get('T_HIDE'):
    for ob in sc.objects:
        if ob.get('mat') in E['T_HIDE'].split(','): ob.hide_render = True
if E.get('T_HIDEN'):
    for ob in sc.objects:
        if any(ob.name.startswith(p) for p in E['T_HIDEN'].split(',')): ob.hide_render = True
if E.get('T_BOUNCE'): c.max_bounces = int(E['T_BOUNCE']); c.diffuse_bounces = min(c.diffuse_bounces, int(E['T_BOUNCE']))
if E.get('T_THR'): c.adaptive_threshold = float(E['T_THR'])
fl = []
for part in frames.split(','):
    if '-' in part: a, b = part.split('-'); fl += list(range(int(a), int(b)+1))
    else: fl.append(int(part))
out = os.path.join(HERE, '_work', os.environ.get('PAL_OUT', mode)); os.makedirs(out, exist_ok=True)
import time
for f in fl:
    fp = os.path.join(out, 'f%04d.png' % f)
    if os.path.exists(fp) and os.environ.get('FORCE') != '1': continue
    t = time.time(); sc.frame_set(f); sc.render.filepath = fp; bpy.ops.render.render(write_still=True)
    print('FRAME', f, 'sec', round(time.time()-t, 1), flush=True)
