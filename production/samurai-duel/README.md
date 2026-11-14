# Samurai Duel — 30 s Blender cinematic

Build scripts for the Oni Samurai vs Cyber Ronin fight video. The scene is built by code
(headless `bpy`), so it can be rebuilt in any new session.

## Folders
- `refs/` — the 7 reference sheets (characters, arena, props).
- `sd/` — Python package that builds the scene (props, materials, lighting, FX).
- `tools/` — helpers (e.g. cropping single assets out of the sheets for image-to-3D).
- `previews/` — small preview renders shown at each stage.
- `assets/`, `out/` — downloaded CC0 assets and renders. Not in git; re-created by the scripts.

## Setup in a fresh session
```bash
NO_PROXY= no_proxy= python3 -m pip install bpy pillow numpy --break-system-packages --proxy "$HTTPS_PROXY"
```
Poly Haven (`api.polyhaven.com`, `dl.polyhaven.org`) must be on the environment's allowed hosts.
