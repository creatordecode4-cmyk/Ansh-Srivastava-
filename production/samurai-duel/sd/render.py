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


def clay_override(sc, on=True):
    """Clay pass: every surface uses one grey material so only shape and light are judged."""
    for vl in sc.view_layers:
        vl.material_override = mats.clay() if on else None
