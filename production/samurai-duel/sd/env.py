"""Sky, blood moon, key/rim lights and volumetric fog.

Mood target (refs/arena.png): night, blood-red moon behind the torii, red lantern pools on a
wet floor, cold moonlight as key, red rim from the moon side, mist hugging the ground.
"""
import math

import bpy
from mathutils import Vector

from . import core, layout, mats
from . import polyhaven as ph
from .mats import NT


def moon_dir():
    az, el = layout.MOON["azimuth"], layout.MOON["elevation"]
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


def world(sc, hdri="kloppenheim_07_puresky", strength=0.2, rotation=math.radians(53.3)):
    """Night HDRI for ambient light and clouds, warmed toward red around the moon."""
    w = bpy.data.worlds.new("WORLD_Night")
    w.use_nodes = True
    sc.world = w
    nt = NT(w.node_tree, clear=True)
    out = nt.new("ShaderNodeOutputWorld")
    tc = nt.new("ShaderNodeTexCoord")
    mp = nt.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, rotation)
    nt.link(tc.outputs["Generated"], mp.inputs[0])
    env = nt.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ph.hdri(hdri, "4k"), check_existing=True)
    nt.link(mp.outputs[0], env.inputs[0])
    # angular distance to the moon -> blood-red tint on the surrounding clouds
    dot = nt.new("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    nt.link(tc.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = moon_dir()
    near = nt.map_range(dot.outputs["Value"], 0.945, 0.999, 0.0, 1.0)
    cool = nt.mix(1.0, env.outputs[0], (0.50, 0.56, 0.88, 1), "MULTIPLY")     # grey-violet night, not saturated blue
    warm = nt.mix(1.0, env.outputs[0], (1.0, 0.14, 0.09, 1), "MULTIPLY")
    col = nt.mix(nt.math("POWER", near, 2.2), cool, nt.mix(1.0, warm, (1.45, 1.45, 1.45, 1), "MULTIPLY"))
    bg = nt.new("ShaderNodeBackground")
    nt.link(col, bg.inputs[0])
    bg.inputs[1].default_value = strength
    nt.link(bg.outputs[0], out.inputs["Surface"])
    return w


def moon(col, distance=900.0, strength=1.3):
    """Blood moon: a far emissive sphere with dark maria, so it parallaxes like the real thing."""
    d = moon_dir()
    radius = distance * math.tan(layout.MOON["angular_diameter"] / 2)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=d * distance)
    ob = bpy.context.object
    ob.name = "Moon"
    core.link(ob, col)
    core.smooth(ob, 180)

    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree, clear=True)
        out = nt.new("ShaderNodeOutputMaterial")
        vec = nt.coords("Object", 1.0 / radius)
        # dark seas with sharp, ragged shores over brighter highlands
        maria = nt.noise(vec, 1.55, 9.0, 0.56, distortion=0.18)
        v = nt.map_range(maria, 0.40, 0.50, 0.30, 1.0)
        v = nt.math("MULTIPLY", v, nt.map_range(nt.noise(vec, 6.5, 6.0, 0.7), 0.3, 0.72, 0.78, 1.1))
        # impact craters at three sizes: darker floor, bright rim, only in some cells
        for scale, depth, share in ((3.4, 0.5, 0.42), (8.5, 0.42, 0.42), (21.0, 0.3, 0.45)):
            dist = nt.voronoi(vec, scale, "F1")
            bowl = nt.ramp(dist, [(0.0, 1.0 - depth), (0.15, 1.0 - 0.55 * depth), (0.22, 1.0 + 0.7 * depth), (0.32, 1.0), (1.0, 1.0)])
            pick = nt.math("GREATER_THAN", nt.voronoi(vec, scale, "F1", out=1), share)
            v = nt.math("MULTIPLY", v, nt.mix(pick, 1.0, bowl))
        lw = nt.new("ShaderNodeLayerWeight")           # gentle limb darkening
        lw.inputs["Blend"].default_value = 0.35
        v = nt.math("MULTIPLY", v, nt.map_range(lw.outputs["Facing"], 0.0, 1.0, 1.0, 0.45))
        colr = nt.ramp(v, [(0.0, (0.07, 0.001, 0.002)), (0.45, (0.50, 0.012, 0.010)), (1.0, (1.0, 0.07, 0.036))])
        em = nt.new("ShaderNodeEmission")
        nt.link(colr, em.inputs[0])
        em.inputs[1].default_value = strength
        nt.link(em.outputs[0], out.inputs["Surface"])
        return m

    core.set_mat(ob, mats.get("MAT_Moon", build))
    ob.visible_shadow = False
    ob.visible_diffuse = False       # lighting comes from the rim lamp, the disc is for camera and reflections
    ob.visible_volume_scatter = False
    return ob


def lights(col, key=1.3, rim=0.28, fill=1.25):
    out = {}
    # cold moonlight key from the east-north-east, raking across the courtyard
    kd = bpy.data.lights.new("LGT_Key_Moonlight", "SUN")
    kd.color, kd.energy, kd.angle = (0.5, 0.68, 1.0), key, math.radians(2.5)
    kd.volume_factor = 2.5           # the mist is lit by the cold moonlight, so it reads grey-violet against the red glow
    ko = bpy.data.objects.new("LGT_Key_Moonlight", kd)
    az, el = math.radians(78), math.radians(38)
    src = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    ko.rotation_euler = (-src).to_track_quat("-Z", "Y").to_euler()
    col.objects.link(ko)
    out["key"] = ko
    # red rim from the blood moon itself
    rd = bpy.data.lights.new("LGT_Rim_BloodMoon", "SUN")
    rd.color, rd.energy, rd.angle = (1.0, 0.1, 0.05), rim, layout.MOON["angular_diameter"]
    rd.specular_factor = 0.25        # the moon mesh already gives the reflection on the wet floor
    rd.volume_factor = 0.06          # keep the whole frame from turning red: fog near the lanterns does that job
    ro = bpy.data.objects.new("LGT_Rim_BloodMoon", rd)
    ro.rotation_euler = (-moon_dir()).to_track_quat("-Z", "Y").to_euler()
    col.objects.link(ro)
    out["rim"] = ro
    # soft sky fill from behind the camera so front faces (torii, lanterns) are not pure silhouettes
    fd = bpy.data.lights.new("LGT_Fill_Sky", "SUN")
    fd.color, fd.energy, fd.angle = (0.78, 0.84, 1.0), fill, math.radians(40)     # near-neutral: blue light would turn red lacquer black
    fd.specular_factor, fd.volume_factor = 0.15, 0.18
    fo = bpy.data.objects.new("LGT_Fill_Sky", fd)
    az, el = math.radians(200), math.radians(34)
    src = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    fo.rotation_euler = (-src).to_track_quat("-Z", "Y").to_euler()
    col.objects.link(fo)
    out["fill"] = fo
    return out


def fog(col, haze=0.002, mist=0.2, mist_height=1.15):
    """One volume: thin haze everywhere + ground mist that thickens toward the torii and temple."""
    ob = core.box("FOG_Volume", (110, 120, 30), (0, 8, 14.5), col)

    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree, clear=True)
        out = nt.new("ShaderNodeOutputMaterial")
        pos = nt.world_pos()
        sep = nt.new("ShaderNodeSeparateXYZ")
        nt.link(pos, sep.inputs[0])
        z = sep.outputs[2]
        fall = nt.math("POWER", 2.718, nt.math("MULTIPLY", nt.math("MAXIMUM", z, 0.0), -1.0 / mist_height))
        puff = nt.map_range(nt.noise(pos, 0.14, 3.0, 0.55, distortion=0.8), 0.38, 0.7, 0.04, 1.0)
        north = nt.map_range(sep.outputs[1], -6.0, 9.0, 0.35, 1.0)
        dens = nt.math("ADD", haze, nt.math("MULTIPLY", nt.math("MULTIPLY", fall, puff), nt.math("MULTIPLY", north, mist)))
        vs = nt.new("ShaderNodeVolumeScatter")
        vs.inputs["Color"].default_value = (0.82, 0.86, 1.0, 1)
        vs.inputs["Anisotropy"].default_value = 0.25
        nt.link(dens, vs.inputs["Density"])
        nt.link(vs.outputs[0], out.inputs["Volume"])
        return m

    core.set_mat(ob, mats.get("MAT_Fog", build))
    ob.display_type = "WIRE"
    return ob
