"""Render settings and passes (Cycles on CPU here; the same .blend renders on a GPU elsewhere)."""
import os

import bpy

from . import core, mats


def setup(sc, w=1920, h=1080, samples=128, threshold=0.02, volume_bounces=0, bounces=6):
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = threshold
    cy.adaptive_min_samples = 16
    cy.max_bounces = bounces
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 4
    cy.transmission_bounces = 4
    cy.transparent_max_bounces = 12
    cy.volume_bounces = volume_bounces
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 6.0     # tames fireflies from small bright lanterns in fog
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.use_light_tree = True
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.use_persistent_data = False
    return sc


def still(sc, path, camera=None, frame=None):
    if camera is not None:
        sc.camera = camera
    if frame is not None:
        sc.frame_set(frame)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def mask(sc, path, keep, samples=4):
    """A quick render in which only the objects in 'keep' show, flat white on black: a matte of where
    they are in the frame (motion blur as set). Everything is put back afterwards."""
    names = {o.name for o in keep}
    hidden = {}
    for o in bpy.data.objects:
        want = o.name not in names
        if o.hide_render != want:
            hidden[o.name] = o.hide_render
            o.hide_render = want
    white = bpy.data.materials.get("MAT_MaskWhite")
    if white is None:
        white = bpy.data.materials.new("MAT_MaskWhite")
        white.use_nodes = True
        nt = white.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1, 1, 1, 1)
        nt.links.new(em.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    black = bpy.data.worlds.get("WORLD_Black")
    if black is None:
        black = bpy.data.worlds.new("WORLD_Black")
        black.use_nodes = True
        black.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    vl, cy, vs = sc.view_layers[0], sc.cycles, sc.view_settings
    saved = (cy.samples, cy.use_denoising, cy.use_adaptive_sampling, sc.render.use_compositing, vs.view_transform, vs.look, vs.exposure,
             vl.material_override, vl.world_override, sc.render.filepath)
    try:
        cy.samples, cy.use_denoising, cy.use_adaptive_sampling = samples, False, False
        sc.render.use_compositing = False
        vs.view_transform, vs.look, vs.exposure = "Standard", "None", 0.0
        vl.material_override, vl.world_override = white, black
        still(sc, path)
    finally:
        (cy.samples, cy.use_denoising, cy.use_adaptive_sampling, sc.render.use_compositing, vs.view_transform, vs.look, vs.exposure,
         vl.material_override, vl.world_override, sc.render.filepath) = saved
        for name, h in hidden.items():
            bpy.data.objects[name].hide_render = h
    return path


def clay_override(sc, on=True):
    """Clay pass: every surface uses one grey material under a plain overcast sky, so only
    shape and light are judged."""
    w = bpy.data.worlds.get("WORLD_Clay")
    if w is None:
        w = bpy.data.worlds.new("WORLD_Clay")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.66, 0.74, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.75
    for vl in sc.view_layers:
        vl.material_override = mats.clay() if on else None
        vl.world_override = w if on else None


def _light_datas():
    return [l for l in bpy.data.lights]


def render_pass(sc, cams, kind, path):
    """beauty: the look. clay: grey override under neutral light. topdown: layout view from above."""
    fog = bpy.data.objects.get("FOG_Volume")
    moon = bpy.data.objects.get("Moon")
    fxc = bpy.data.collections.get("FX")
    water = bpy.data.objects.get("Water_Film")
    bg = sc.world.node_tree.nodes.get("Background") if sc.world else None
    saved = dict(exposure=sc.view_settings.exposure, look=sc.view_settings.look, bg=bg.inputs[1].default_value if bg else None,
                 lights={l.name: (l.energy, tuple(l.color)) for l in _light_datas()},
                 fog=fog.hide_render if fog else None, moon=moon.hide_render if moon else None, fx=fxc.hide_render if fxc else None)
    for f in (1, 2, 3):          # let the particle systems spawn and take a first step
        sc.frame_set(f)
    try:
        if kind == "beauty":
            sc.camera = cams["hero"]
        elif kind == "clay":
            sc.camera = cams["hero"]
            clay_override(sc, True)
            for l in _light_datas():
                if l.type == "SUN" and "Key" in l.name:
                    l.energy, l.color = 2.2, (1.0, 0.97, 0.93)
                else:
                    l.energy = 0.0
            if bg:
                bg.inputs[1].default_value = 3.2
            if moon:
                moon.hide_render = True
            if fxc:
                fxc.hide_render = True
            for o in (fog, water):       # the override would turn the fog box and the water sheet into grey solids
                if o:
                    o.hide_render = True
            sc.view_settings.exposure = 0.0
            sc.view_settings.look = "None"
        elif kind == "topdown":
            sc.camera = cams["topdown"]
            if fog:
                fog.hide_render = True
            if bg:
                bg.inputs[1].default_value = saved["bg"] * 7.0
            for l in _light_datas():
                if l.type == "SUN" and "Key" in l.name:
                    l.energy *= 2.5
            sc.view_settings.exposure = saved["exposure"] + 0.6
        return still(sc, path)
    finally:
        clay_override(sc, False)
        sc.view_settings.exposure, sc.view_settings.look = saved["exposure"], saved["look"]
        if bg:
            bg.inputs[1].default_value = saved["bg"]
        for l in _light_datas():
            if l.name in saved["lights"]:
                l.energy, l.color = saved["lights"][l.name]
        if fog:
            fog.hide_render = saved["fog"]
        if water:
            water.hide_render = False
        if moon:
            moon.hide_render = saved["moon"]
        if fxc:
            fxc.hide_render = saved["fx"]


def bloom(sc, strength=0.55, threshold=1.0, size=0.55):
    """Lens bloom on lanterns and the moon, done in the compositor on scene-linear values."""
    ng = bpy.data.node_groups.new("COMP_Arena", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    out = ng.nodes.new("NodeGroupOutput")
    for key, val in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", threshold), ("Strength", strength), ("Size", size), ("Smoothness", 0.6)):
        try:
            gl.inputs[key].default_value = val
        except Exception as e:  # menu names differ between versions: keep rendering without that option
            print("bloom option skipped:", key, e)
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    sc.render.compositor_device = "CPU"     # no GPU context in the headless workspace; switch to GPU on a render machine
    return ng
