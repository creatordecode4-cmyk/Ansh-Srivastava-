"""Falling cherry petals and light snow (particle systems), plus petals lying on the wet floor.

Each falling system is a pair: one fills the air at frame 1, the other keeps emitting from the
top so the air never empties during the 30 seconds.
"""
import math

import bpy
import numpy as np
from mathutils import Euler, Vector

from . import core, layout, mats, nature
from .mats import NT

AIR = dict(x0=-20.0, x1=22.0, y0=-18.0, y1=16.0, z1=13.0)


def _snow_mat():
    def build(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = NT(m.node_tree)
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.9, 0.92, 0.96, 1)
        b.inputs["Roughness"].default_value = 0.5
        b.inputs["Emission Color"].default_value = (0.8, 0.85, 1.0, 1)
        b.inputs["Emission Strength"].default_value = 0.05
        return m

    return mats.get("MAT_Snowflake", build)


def _emitter(name, col, volume):
    a = AIR
    if volume:
        ob = core.box(name, (a["x1"] - a["x0"], a["y1"] - a["y0"], a["z1"]), ((a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2, a["z1"] / 2), col)
    else:
        ob = core.mesh_obj(name, [(a["x0"], a["y0"], a["z1"]), (a["x1"], a["y0"], a["z1"]), (a["x1"], a["y1"], a["z1"]), (a["x0"], a["y1"], a["z1"])], [(0, 3, 2, 1)], col)
    ob.show_instancer_for_render = False
    ob.show_instancer_for_viewport = False
    ob.display_type = "WIRE"
    return ob


def _system(ob, name, inst, count, volume, size, gravity, brownian, drag, seed, frames=720, fall_speed=0.6):
    mod = ob.modifiers.new(name, "PARTICLE_SYSTEM")
    psys = ob.particle_systems[-1]
    psys.seed = seed
    ps = psys.settings
    ps.name = name
    ps.count = count
    ps.frame_start = 1
    ps.frame_end = 1 if volume else frames
    ps.lifetime = 4000
    ps.emit_from = "VOLUME" if volume else "FACE"
    ps.distribution = "RAND"
    ps.use_emit_random = True
    ps.normal_factor = 0.0
    ps.object_align_factor = (0.0, 0.0, -fall_speed)      # start already falling
    ps.factor_random = 0.25
    ps.physics_type = "NEWTON"
    ps.mass = 0.01
    ps.drag_factor = drag
    ps.brownian_factor = brownian
    ps.effector_weights.gravity = gravity
    ps.use_rotations = True
    ps.rotation_mode = "GLOB_Z"
    ps.rotation_factor_random = 1.0
    ps.phase_factor_random = 2.0
    ps.use_dynamic_rotation = True
    ps.angular_velocity_mode = "RAND"
    ps.angular_velocity_factor = 2.2
    ps.render_type = "OBJECT"
    ps.instance_object = inst
    ps.particle_size = size
    ps.size_random = 0.45
    ps.use_die_on_collision = False
    return psys


def falling(lib, col, petals=5200, snow=9000, frames=720):
    petal = nature.petal_mesh("PROP_Petal", lib, 0.034, 0.026)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0)
    flake = bpy.context.object
    flake.name = "PROP_Snowflake"
    core.link(flake, lib)
    core.set_mat(flake, _snow_mat())
    out = []
    for vol in (True, False):
        e = _emitter(f"FX_Petals_{'Fill' if vol else 'Rain'}", col, vol)
        rate = int(petals * frames / (AIR["z1"] / 0.55 * 24))     # keep the same density in the air over time
        out.append(_system(e, e.name, petal, petals if vol else rate, vol, 1.0, 0.0035, 0.5, 0.012, 11 + vol, frames, 0.55))
        e2 = _emitter(f"FX_Snow_{'Fill' if vol else 'Rain'}", col, vol)
        rate = int(snow * frames / (AIR["z1"] / 0.8 * 24))
        out.append(_system(e2, e2.name, flake, snow if vol else rate, vol, 0.007, 0.0045, 0.35, 0.02, 21 + vol, frames, 0.8))
    # gentle wind and turbulence so nothing falls in straight lines
    bpy.ops.object.effector_add(type="WIND", location=(0, 0, 6), rotation=(math.radians(90), 0, math.radians(-70)))
    wind = bpy.context.object
    wind.name = "FX_Wind"
    core.link(wind, col)
    wind.field.strength = 0.012
    wind.field.noise = 0.6
    bpy.ops.object.effector_add(type="TURBULENCE", location=(0, 0, 5))
    turb = bpy.context.object
    turb.name = "FX_Turbulence"
    core.link(turb, col)
    turb.field.strength = 0.02
    turb.field.size = 2.5
    turb.field.flow = 0.4
    return out


def ground_petals(lib, col, count=4200, seed=9):
    """Petals already fallen: scattered on the stone and floating on the puddles, thicker near the trees."""
    r = core.rng(seed)
    petal = bpy.data.objects.get("PROP_Petal") or nature.petal_mesh("PROP_Petal", lib, 0.034, 0.026)
    p = layout.PAVED
    anchors = [(x, y, cr) for (x, y, h, cr) in layout.CHERRY]
    xf = []
    tries = 0
    while len(xf) < count and tries < count * 30:
        tries += 1
        x, y = r.uniform(p["x0"] - 3, p["x1"] + 3), r.uniform(p["y0"], p["y1"] - 0.5)
        near = min(math.hypot(x - ax, y - ay) / (cr + 5.0) for ax, ay, cr in anchors)
        if r.random() > 0.12 + 0.88 * max(0.0, 1.0 - near):
            continue
        rot = Euler((r.gauss(0, 0.12), r.gauss(0, 0.12), r.uniform(0, 6.28))).to_matrix()
        xf.append(((x, y, 0.004 + r.random() * 0.004), rot, r.uniform(0.7, 1.3)))
    return core.face_instancer("FX_GroundPetals", petal, xf, col)
