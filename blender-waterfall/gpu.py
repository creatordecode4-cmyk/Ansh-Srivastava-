"""Run before -a: enable the GPU (OptiX/CUDA) and make the frame render resumable."""
import bpy

scene = bpy.context.scene
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev
    except TypeError:
        continue
    (prefs.refresh_devices if hasattr(prefs, "refresh_devices") else prefs.get_devices)()
    if any(d.type == dev for d in prefs.devices):
        for d in prefs.devices:
            d.use = d.type == dev
        scene.cycles.device = "GPU"
        print("GPU:", dev)
        break
scene.render.use_overwrite = False      # skip frames that already exist (resume after a disconnect)
scene.render.use_placeholder = True
