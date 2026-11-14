"""Clash effects: showers of sparks and a flash of light at every sword contact."""
import bpy, math, random
from mathutils import Vector as V
import lib


def build_sparks(EV, C, per_unit=70):
    me = bpy.data.meshes.new('FX_Spark')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.004)
    for v in bm.verts:
        v.co.z *= 3.0
    bm.to_mesh(me); bm.free()
    m, nt, bsdf, out = lib._new('MAT_Spark')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value, em.inputs[1].default_value = (1.0, 0.50, 0.12, 1), 260.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    rnd = random.Random(5)
    g = V((0, 0, -9.8))
    total = 0
    for fe, P, strength, tscale in EV:
        n = int(per_unit * strength)
        for i in range(n):
            a, el = rnd.uniform(0, 6.283), rnd.uniform(-0.5, 1.35)
            v0 = V((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))) * rnd.uniform(1.6, 7.0) * (0.7 + 0.3 * strength)
            life = int(rnd.uniform(7, 17) / tscale ** 0.6)
            o = bpy.data.objects.new(f'FX_Spark_{fe}_{i}', me)
            o.rotation_mode = 'QUATERNION'
            o.visible_shadow = False
            C.objects.link(o)
            o.scale = (0, 0, 0); o.location = P
            o.keyframe_insert('scale', frame=fe - 1); o.keyframe_insert('location', frame=fe - 1)
            bounced = False
            p, v = V(P), v0.copy()
            dt = tscale / 24.0
            for k in range(life + 1):
                if k:
                    v = v + g * dt
                    v *= (1 - 0.9 * dt)
                    p = p + v * dt
                    if p.z < 0.01 and v.z < 0:
                        p.z = 0.01; v.z *= -0.35; v.x *= 0.6; v.y *= 0.6
                age = k / life
                s = (1.0 - age ** 2) * rnd.uniform(0.8, 1.3)
                o.location = p
                o.rotation_quaternion = v.to_track_quat('Z', 'Y') if v.length > 1e-4 else o.rotation_quaternion
                o.scale = (s, s, s * (1 + min(6.0, v.length * 0.8)))
                o.keyframe_insert('location', frame=fe + k); o.keyframe_insert('scale', frame=fe + k)
                o.keyframe_insert('rotation_quaternion', frame=fe + k)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=fe + life + 1)
            total += 1
        L = bpy.data.lights.new(f'FX_Flash_{fe}', 'POINT')
        L.color, L.shadow_soft_size = (1.0, 0.62, 0.30), 0.15
        lo = bpy.data.objects.new(f'FX_Flash_{fe}', L); lo.location = P + V((0, -0.15, 0.1))
        C.objects.link(lo)
        hold = max(1, int(1 / tscale))
        for f, e in ((fe - 1, 0.0), (fe, 2600.0 * strength), (fe + hold, 1800.0 * strength), (fe + hold + 3, 250.0 * strength), (fe + hold + 7, 0.0)):
            L.energy = e; L.keyframe_insert('energy', frame=f)
    print(f'  sparks: {total} in {len(EV)} clashes')
