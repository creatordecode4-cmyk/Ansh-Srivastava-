"""Stage 2: turn the two image-to-3D GLBs into clean, scaled, render-weight character meshes.
python3 -I scripts/prep_characters.py <oni.glb> <ronin.glb> <out.blend> [--tris 400000]

Each GLB is one fused watertight shell (hat, cape, swords and body are a single surface), in a T-pose,
about 1 unit tall, with 1024 px base-colour / normal / roughness-metallic textures.
"""
import bpy, bmesh, sys, time, math
from mathutils import Vector, Matrix

oni_glb, ronin_glb, out = sys.argv[1], sys.argv[2], sys.argv[3]
TRIS = int(sys.argv[sys.argv.index('--tris') + 1]) if '--tris' in sys.argv else 400000
HEIGHT = {'Oni': 1.98, 'Ronin': 2.00}        # bounding-box height in metres (horn tips / hat tip)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def prep(path, name):
    t0 = time.time()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    ob = next(o for o in bpy.data.objects if o not in before and o.type == 'MESH')
    for o in [o for o in bpy.data.objects if o not in before and o is not ob]:
        bpy.data.objects.remove(o)
    me = ob.data
    # bake the object transform, weld the UV-seam vertex splits (UVs live on face corners, so seams survive)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    zs = [v.co.z for v in bm.verts]
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    s = HEIGHT[name] / (max(zs) - min(zs))
    # stand on the ground, centred between the feet (lowest 3 % of the mesh)
    zlo = min(zs)
    foot = [v.co for v in bm.verts if v.co.z < zlo + 0.03 * (max(zs) - zlo)]
    cx = (min(p.x for p in foot) + max(p.x for p in foot)) / 2
    cy = (min(p.y for p in foot) + max(p.y for p in foot)) / 2
    bm.transform(Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -zlo)))
    bm.to_mesh(me)
    n1, f1 = len(bm.verts), len(bm.faces)
    bm.free()
    ob.matrix_world = Matrix.Identity(4)
    if 'custom_normal' in me.attributes:
        me.attributes.remove(me.attributes['custom_normal'])
    me.shade_smooth()
    # render-weight copy: collapse decimation keeps UVs, so the Tripo textures still fit
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    mod = ob.modifiers.new('dec', 'DECIMATE')
    mod.ratio = min(1.0, TRIS / tris)
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.remove(mod)
    old = ob.data
    ob.data = new
    bpy.data.meshes.remove(old)
    new.name = name + '_Body'
    new.shade_smooth()
    ob.name = name + '_Body'
    for m in new.materials:
        m.name = 'MAT_' + name
    for im in bpy.data.images:
        if im.users and not im.name.startswith(('Oni_', 'Ronin_')) and any(k in im.name for k in ('basecolor', 'normal', '_rm')):
            kind = 'basecolor' if 'basecolor' in im.name else ('normal' if 'normal' in im.name else 'rm')
            if (name == 'Oni') == ('demon' in im.name):
                im.name = f'{name}_{kind}'
    coll = bpy.data.collections.new('CHAR_' + name)
    sc.collection.children.link(coll)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    lo = Vector(map(min, *[v.co for v in new.vertices])) if False else None
    co = [v.co for v in new.vertices]
    bb = [min(c[i] for c in co) for i in range(3)], [max(c[i] for c in co) for i in range(3)]
    print(f'PREP {name}: verts {n0}->{n1} welded, faces {f1} -> {len(new.polygons)} tris, scale x{s:.3f}, '
          f'bbox {[round(v, 2) for v in bb[0]]} .. {[round(v, 2) for v in bb[1]]}, {time.time() - t0:.0f}s', flush=True)
    return ob


prep(oni_glb, 'Oni')
prep(ronin_glb, 'Ronin')
bpy.ops.wm.save_as_mainfile(filepath=out)
print('PREP saved', out)
