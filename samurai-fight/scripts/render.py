"""Render stills from a built .blend.
python3 render.py <blend> <out.png> [--cam CAM_Hero] [--res 1280x720] [--spp 48] [--frame 1]
                   [--clay] [--no-fog] [--no-fx] [--exposure 1.2] [--no-dof]
"""
import bpy, sys, time, argparse

ap = argparse.ArgumentParser()
ap.add_argument('blend')
ap.add_argument('out')
ap.add_argument('--cam', default='CAM_Hero')
ap.add_argument('--res', default='1280x720')
ap.add_argument('--spp', type=int, default=48)
ap.add_argument('--frame', type=int, default=1)
ap.add_argument('--clay', action='store_true')
ap.add_argument('--no-fog', action='store_true')
ap.add_argument('--no-fx', action='store_true')
ap.add_argument('--no-dof', action='store_true')
ap.add_argument('--exposure', type=float, default=None)
a = ap.parse_args()

bpy.ops.wm.open_mainfile(filepath=a.blend)
sc = bpy.context.scene
sc.camera = bpy.data.objects[a.cam]
w, h = map(int, a.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
sc.cycles.samples = a.spp
if a.exposure is not None:
    sc.view_settings.exposure = a.exposure
if a.no_dof and sc.camera.data.type == 'PERSP':
    sc.camera.data.dof.use_dof = False
for ob in bpy.data.objects:
    if a.no_fog and ob.name.startswith('Fog_'):
        ob.hide_render = True
    if a.no_fx and ob.name.startswith('FX_'):
        ob.hide_render = True
if a.clay:
    bpy.context.view_layer.material_override = bpy.data.materials['MAT_Clay']
    for ob in bpy.data.objects:
        if ob.name.startswith(('Fog_', 'BloodMoon', 'Floor_WaterFilm')):
            ob.hide_render = True
    sc.world.node_tree.nodes['Background'].inputs[1].default_value = 6.0
    sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.25, 0.27, 0.32, 1)
    for l in bpy.data.lights:
        if l.type != 'SUN':
            l.energy *= 0.0
        else:
            l.color = (1, 1, 1)
            l.energy = 2.5 if 'Key' in l.name else 0.6
    sc.view_settings.exposure = -0.3
sc.frame_set(a.frame)
sc.render.filepath = a.out
t = time.time()
bpy.ops.render.render(write_still=True)
print(f'RENDERED {a.out} {w}x{h} {a.spp}spp in {time.time() - t:.1f}s')
