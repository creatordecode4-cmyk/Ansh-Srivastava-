# Samurai Duel — 30 s Blender cinematic

Build scripts for the Oni Samurai vs Cyber Ronin fight video. The scene is built by code
(headless `bpy`), so it can be rebuilt in any new session.

## Setup in a fresh session
```bash
NO_PROXY= no_proxy= python3 -m pip install bpy pillow numpy --break-system-packages --proxy "$HTTPS_PROXY"
```
Poly Haven (`api.polyhaven.com`, `dl.polyhaven.org`) must be on the environment's allowed hosts;
textures, rock scans and the night HDRI are downloaded on first use into `assets/` (CC0).

## Build and render
```bash
python3 build_arena.py --save --pass beauty topdown clay --size 1920 1080 --samples 160 --tag _final
python3 tools/stage1_sheet.py _final        # preview sheets -> previews/
python3 build_arena.py --fast --pass beauty --size 960 540 --samples 48 --tag _test   # quick look-dev
python3 tools/prop_test.py lantern --neutral   # one prop on a neutral stage
```
`--save` writes `out/arena.blend`. No GPU is needed (Cycles on CPU, compositor on CPU).

## Folders
- `refs/` — the 7 reference sheets (characters, arena, props).
- `sd/` — the scene builder:
  - `layout.py` — every position, measured from the top-down panel of `refs/arena_breakdown.png`
  - `floor.py`, `torii.py`, `lantern.py`, `temple.py`, `roofs.py`, `dressing.py`, `nature.py` — props
  - `mats.py` — weathered PBR materials (wet film, moss, snow) on Poly Haven textures
  - `env.py`, `fx.py` — sky, blood moon, lights, fog, falling petals and snow
  - `arena.py` — assembles everything; masters live in the `PROPS_LIB` collection and are instanced
  - `render.py` — render settings, the three passes, bloom
- `tools/` — prop test stage, preview sheets, image-to-3D crop tool.
- `previews/` — preview images shown at each stage.
- `assets/`, `out/` — downloads and renders. Not in git; re-created by the scripts.

## Stage 1 notes
- Placement follows the top-down layout (1 px = 5.5 cm, origin at the middle of the fighting area,
  +Y toward the torii). The torii is scaled up to match the scale of the hero image.
- Outside the reference panel (south of y = -8 m) there are two framing cherry trees and a
  boundary wall with a gate, so reverse angles have a backdrop.
- Every prop is its own object; lanterns, tiles, rocks, banners, paper lanterns, blossoms and
  petals are instanced from one master each.
