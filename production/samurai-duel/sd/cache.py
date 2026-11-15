"""Simulated cloth stored on disk and played back.

Simulation and rendering are separate steps: the cloth is run once over a shot, its vertex
positions are written to a PC2 file (the plain point-cache format: a header and float32
positions, sample after sample), and for rendering the panel reads the file through a Mesh Cache
modifier. Renders then need no simulation, can start at any frame, and motion blur can sample
between frames.
"""
import struct

import numpy as np

SIM = ("ARMATURE", "CLOTH")
DRESS = ("SUBSURF", "SOLIDIFY")


def write_pc2(path, P, start=0.0, rate=1.0):
    """P: (samples, points, 3) positions in the object's own space."""
    P = np.asarray(P, dtype="<f4")
    with open(path, "wb") as fh:
        fh.write(struct.pack("<12siiffi", b"POINTCACHE2\0", 1, P.shape[1], start, rate, P.shape[0]))
        fh.write(P.tobytes())
    return path


def live(ob):
    """Put a panel back into simulating state (cache off, smoothing and thickness off in the viewport)."""
    for m in list(ob.modifiers):
        if m.type == "MESH_CACHE":
            ob.modifiers.remove(m)
    for m in ob.modifiers:
        if m.type in SIM:
            m.show_viewport = m.show_render = True
        elif m.type in DRESS:
            m.show_viewport = False            # the simulation result is read with the panel's own vertices only
            m.show_render = True


def playback(ob, path, first_frame):
    """Play positions from a PC2 file whose first sample belongs to scene frame first_frame."""
    for m in list(ob.modifiers):
        if m.type == "MESH_CACHE":
            ob.modifiers.remove(m)
    mc = ob.modifiers.new("Cache", "MESH_CACHE")
    mc.cache_format = "PC2"
    mc.filepath = path
    mc.frame_start = first_frame
    mc.frame_scale = 1.0
    mc.time_mode = "FRAME"
    mc.play_mode = "SCENE"
    mc.interpolation = "LINEAR"
    mc.deform_mode = "OVERWRITE"
    mc.forward_axis, mc.up_axis = "POS_Y", "POS_Z"
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    for m in ob.modifiers:
        if m.type in SIM:
            m.show_viewport = m.show_render = False
        elif m.type in DRESS:
            m.show_viewport = False
            m.show_render = True
    return mc
