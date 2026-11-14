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
python3 build_arena.py --save --pass beauty topdown clay --size 1920 1080 --samples 128 --tag _final
python3 tools/stage1_sheet.py _final        # preview sheets -> previews/
python3 build_arena.py --pass beauty --size 960 540 --samples 48 --tag _test          # look-dev test, about 3 min
python3 build_arena.py --no-fog --no-particles --no-bloom --pass beauty --size 640 360 --samples 16 --tag _comp   # framing test, 45 s
python3 build_arena.py --fast --size 640 360 --samples 28 --anim 36 --push 1.0 --tag _motion   # particle motion test
python3 tools/prop_test.py lantern --neutral   # one prop on a neutral stage
python3 tools/props_sheet.py                   # all props -> previews/stage1_props.jpg
```
Measured on 4 CPU cores: 1080p beauty at 128 samples takes 20 to 25 minutes, top-down about 10, clay about 3.
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
- Look: version A (commit eeda84a) was a brighter, pinker night. Version B, the current one, is
  closer to `refs/arena.png`: pale blossoms with dark centres, grey-violet sky, cool mist lit by
  the moonlight key, deep-red lantern light, a cratered blood moon. The framing trees stand 4.5
  to 5.5 m from the hero camera so only their branch tips enter the top corners.
- Falling petals and snow are particle systems (unit mass, velocity damping, light gravity);
  `previews/stage1_motion_test_A.mp4` is the 36-frame check, rendered with the version A look.
