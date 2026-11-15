"""Neutral photo-studio set for checking props and characters against the reference sheets.

Soft HDRI light for reflections, a plain backdrop the camera sees, and a key light that can be
turned around the subject. Nothing here is used in the film scene.
"""
import math

import bpy
from mathutils import Vector

from . import core
from . import polyhaven as ph
from .mats import NT


def world(sc, hdri="studio_small_08", strength=0.9, backdrop=(0.21, 0.215, 0.225), rotation=0.0):
    """HDRI lights and reflects; the camera sees a flat backdrop colour like the sheet panels."""
    w = bpy.data.worlds.new("WORLD_Studio")
    w.use_nodes = True
    sc.world = w
    nt = NT(w.node_tree, clear=True)
    out = nt.new("ShaderNodeOutputWorld")
    tc = nt.new("ShaderNodeTexCoord")
    mp = nt.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, rotation)
    nt.link(tc.outputs["Generated"], mp.inputs[0])
    env = nt.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ph.hdri(hdri, "2k"), check_existing=True)
    nt.link(mp.outputs[0], env.inputs[0])
    lit = nt.new("ShaderNodeBackground")
    nt.link(env.outputs[0], lit.inputs[0])
    lit.inputs[1].default_value = strength
    flat = nt.new("ShaderNodeBackground")
    flat.inputs[0].default_value = (*backdrop, 1)
    lp = nt.new("ShaderNodeLightPath")
    mix = nt.new("ShaderNodeMixShader")
    nt.link(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.link(lit.outputs[0], mix.inputs[1])
    nt.link(flat.outputs[0], mix.inputs[2])
    nt.link(mix.outputs[0], out.inputs["Surface"])
    return w


def key(sc, target, azimuth=-35.0, elevation=40.0, distance=4.0, power=900.0, size=1.6, color=(1.0, 0.98, 0.95), name="LGT_Key"):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = power, size, color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    a, e = math.radians(azimuth), math.radians(elevation)
    o.location = Vector(target) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * distance
    core.look_at(o, Vector(target))
    return o


def camera(sc, target, azimuth=0.0, elevation=0.0, distance=4.0, lens=85.0, ortho=None, name="CAM_Studio"):
    """Camera on a sphere around target; azimuth 0 looks along +Y (the subject's front faces -Y)."""
    c = bpy.data.cameras.new(name)
    c.lens = lens
    if ortho:
        c.type = "ORTHO"
        c.ortho_scale = ortho
    o = bpy.data.objects.new(name, c)
    sc.collection.objects.link(o)
    aim(o, target, azimuth, elevation, distance)
    c.clip_start, c.clip_end = 0.01, distance * 6 + 50
    return o


def aim(cam, target, azimuth=0.0, elevation=0.0, distance=4.0):
    a, e = math.radians(azimuth), math.radians(elevation)
    cam.location = Vector(target) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * distance
    core.look_at(cam, Vector(target))
    return cam


def floor(sc, z=0.0, size=40.0, color=(0.2, 0.205, 0.215)):
    """Matte floor that catches the contact shadow."""
    g = core.box("STUDIO_Floor", (size, size, 0.02), (0, 0, z - 0.01), sc.collection)
    m = bpy.data.materials.new("MAT_Studio_Floor")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.85
    core.set_mat(g, m)
    return g
