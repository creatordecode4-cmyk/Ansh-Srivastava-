# Samurai Duel — 30 s Blender cinematic

Build scripts for the Oni Samurai vs Cyber Ronin fight video. The scene is built by code
(headless `bpy`), so it can be rebuilt in any new session.

## Setup in a fresh session
```bash
NO_PROXY= no_proxy= python3 -m pip install bpy pillow numpy scipy scikit-image --break-system-packages --proxy "$HTTPS_PROXY"
```
Poly Haven (`api.polyhaven.com`, `dl.polyhaven.org`) must be on the environment's allowed hosts;
textures, rock scans and the night HDRI are downloaded on first use into `assets/` (CC0).

The two character models are the owner's own Tripo exports and are not in git. They sit in his
Google Drive (folders `3d` and `3d2`, link-shared) and go here:
- `assets/user/glb_f2a316b1/model.glb` — Cyber Ronin (`tripo_convert_f2a316b1...glb`)
- `assets/user/glb_5c88c26e/model.glb` — Oni Samurai (`tripo_convert_5c88c26e...glb`)

Download with `curl -L "https://drive.usercontent.google.com/download?id=<file id>&export=download&confirm=t"`
(`drive.usercontent.google.com` is on the allowed hosts). Run every script that reads them with
`python3 -I`.

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

## Characters (Stage 2)
```bash
python3 -I tools/stage2_sheet.py ronin      # previews/stage2_ronin.jpg + stage2_ronin_parts.jpg  (about 5 min)
python3 -I tools/stage2_sheet.py oni        # previews/stage2_oni.jpg + stage2_oni_parts.jpg
python3 -I tools/stage2_sheet.py duo        # both fighters in one frame
python3 -I tools/build_fighters.py ronin --hero    # quick four-view look
python3 tools/weapon_test.py oni --close    # katana and scabbard on the studio set
```
The first build of each fighter analyses and cuts the Tripo model and builds its collision skin
(1.5 to 3 min); the result is cached in `assets/gen/` and later builds take seconds, plus about
a minute of cloth simulation for the Ronin.

## Folders
- `refs/` — the 7 reference sheets (characters, arena, props).
- `sd/` — the scene builder:
  - `layout.py` — every position, measured from the top-down panel of `refs/arena_breakdown.png`
  - `floor.py`, `torii.py`, `lantern.py`, `temple.py`, `roofs.py`, `dressing.py`, `nature.py` — props
  - `mats.py` — weathered PBR materials (wet film, moss, snow) on Poly Haven textures
  - `env.py`, `fx.py` — sky, blood moon, lights, fog, falling petals and snow
  - `arena.py` — assembles everything; masters live in the `PROPS_LIB` collection and are instanced
  - `render.py` — render settings, the three passes, bloom
  - `scan.py` — measures an image-to-3D model face by face (texture, wall thickness, patches)
  - `envelope.py` — watertight outer skin of a messy mesh (what cloth collides with)
  - `ronin.py`, `oni.py` — take each fighter's Tripo model apart and cache the cleaned body
  - `weapons.py`, `charmats.py`, `kasa.py` — katanas, scabbards, tassels, the Ronin's hat
  - `garments.py` — simulated cloth: panels, pins, tears, fabric, cloth settings
  - `fighters.py` — assembles each fighter from separate objects
  - `studio.py` — neutral studio set for turnarounds
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

## Stage 2 notes
- A Tripo model is one fused skin. `scan.py` tells its regions apart with two measurements per
  face: metalness from the model's own texture and wall thickness from ray casts.
- Ronin: hat, both katanas, a stray third scabbard and every thin hanging cloth are cut away;
  everything below the waist on the right is a mirror of the left (the right thigh was fused
  into a cloth bundle); the top of the helmet is new (it was inside the hat). Hat (whole and
  two pre-cut halves), katanas, scabbards, cape, two hip cloths and two knot tails are separate
  objects.
- Oni: the katana tied to the left hip is cut away by mirroring the lower body from the right
  side; the cut runs through the black waist wrap. Katana, scabbard and three tassels are
  separate objects. Hakama, hair and the rope belt are still part of the body mesh; they get
  their motion in Stage 3.
- Cloth collides with the watertight skin from `envelope.py`, never with the cut model: cloth
  is pushed toward the side a face points to, and a cut-up scan has faces pointing both ways.
- Cloth settings for the 12.5 mm grid are in `garments.cloth()` with the measurements behind
  them. Mass and air drag are per vertex and must shrink with the grid; stiffness must not grow.
- Blade and scabbard designs are lifted from the parts sheets by `tools/extract_patterns.py`.
