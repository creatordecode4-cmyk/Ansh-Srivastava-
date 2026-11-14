"""Render a preview still of arena.blend.
  python3 scripts/render_arena.py --cam CAM_Hero --res 1280x720 --spp 64 --out previews/hero.png [--clay] [--nofx] [--frame 1]
"""
import bpy, os, sys, argparse, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ap = argparse.ArgumentParser()
ap.add_argument('--cam', default='CAM_Hero'); ap.add_argument('--res', default='960x540')
ap.add_argument('--spp', type=int, default=32); ap.add_argument('--out', default='previews/test.png')
ap.add_argument('--clay', action='store_true'); ap.add_argument('--nofx', action='store_true')
ap.add_argument('--frame', type=int, default=1); ap.add_argument('--exposure', type=float, default=None)
ap.add_argument('--blend', default='arena.blend')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, a.blend))
sc = bpy.context.scene
sc.camera = bpy.data.objects[a.cam]
w, h = map(int, a.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
sc.cycles.samples = a.spp
sc.render.use_motion_blur = False
if a.exposure is not None:
    sc.view_settings.exposure = a.exposure
emit = bpy.data.objects.get('FX_Emitter')
if a.nofx or a.clay:
    if emit:
        for m in emit.modifiers:
            m.show_render = False
else:
    t = time.time()
    for f in range(-800, a.frame + 1, 1):          # pre-roll the particle simulation
        sc.frame_set(f)
    print('particle pre-roll %.1fs' % (time.time() - t))
sc.frame_set(a.frame)
if a.clay:
    clay = bpy.data.materials.new('MAT_Clay'); clay.use_nodes = True
    b = clay.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.55, 0.55, 0.55, 1); b.inputs['Roughness'].default_value = 0.7
    bpy.context.view_layer.material_override = clay
    for n in ('Fog_Volume', 'Clouds', 'Moon', 'Petals_Ground'):
        o = bpy.data.objects.get(n)
        if o: o.hide_render = True
    for o in bpy.data.objects:
        if o.type == 'LIGHT': o.hide_render = True
    for c in bpy.data.collections:
        for o in c.objects:
            if o.type == 'LIGHT': o.hide_render = True
    L = bpy.data.lights.new('ClaySun', 'SUN'); L.energy, L.angle = 3.0, 0.2
    so = bpy.data.objects.new('ClaySun', L); so.rotation_euler = (0.9, 0.1, -0.6); sc.collection.objects.link(so)
    nt = sc.world.node_tree
    bg = nt.nodes['Background']
    for l in list(bg.inputs[0].links): nt.links.remove(l)
    bg.inputs[0].default_value = (0.75, 0.78, 0.85, 1); bg.inputs[1].default_value = 0.9
    sc.view_settings.exposure = 0.0
sc.render.filepath = os.path.join(ROOT, a.out)
t = time.time(); bpy.ops.render.render(write_still=True)
print('RENDER %s %s %dspp: %.1fs' % (a.cam, a.res, a.spp, time.time() - t))
