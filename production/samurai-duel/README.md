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

## Rigging and animation (Stage 3)
```bash
python3 tools/fetch_mocap.py                          # free motion-capture clips -> assets/mocap/ (once)
python3 -I tools/stage3_preview.py list               # segments of the motion test
python3 -I tools/stage3_preview.py render oni_walk    # one segment at 1280x720, 16 samples (15-20 s per frame)
python3 -I tools/stage3_preview.py render oni_strike --proxy --samples 6 --step 4   # quick clay check of a move
python3 -I tools/stage3_preview.py assemble           # previews/stage3_motion_test.mp4
python3 -I tools/rig_test.py oni                      # skeleton and skin weights on test poses
```
The first actor build of the Ronin drapes his cloth once (about 90 s) and stores it in
`assets/gen/ronin_actor_drape.npz`; after that an actor is ready in 2 to 3 seconds.

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
  - `rig.py` — Mixamo-named skeleton measured on each fighter, skin weights
  - `puppet.py` — poses a skeleton from a few controls (hips, chest, feet, hands, sword grips)
  - `mocap.py`, `motion.py` — motion-capture clips as controls; takes: placing, blending, foot locking, keyed moves
  - `actor.py` — a fighter in a shot: body, swords on tracks or in the hand, cloth run and stored
  - `soft.py`, `cache.py` — soft cage for the Oni's trousers; cloth stored on disk (PC2) for rendering
  - `retarget.py` — bone-by-bone carry-over of a downloaded FBX clip (for Mixamo files)
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

## Stage 3 notes
- The skeletons use Mixamo's bone names (65 bones with fingers) but are built here, from joints
  measured on each fighter's own model; nothing had to be uploaded to Mixamo.
- A pose is not 65 bone rotations but a handful of controls: where the hips are, how pelvis, chest
  and head are turned, where each foot stands and where each hand or the sword is. `puppet.py`
  solves legs and arms to those targets, so a planted foot cannot slide and a hand cannot miss
  the grip. `actor.perform()` reports any reach it could not make.
- Body motion comes from the free DeepMimic reference clips (walk, run, kick, spin kick, jump,
  punch ...; zlib licence, shipped inside the `pybullet` package). A clip is read as controls and
  scaled to each fighter's limb lengths, then the feet are locked: heel and ball contacts are
  held exactly where they land. Measured drift of a planted foot after solving: 0.00 mm.
- Moves the clips do not have (sword work) are keyed by hand with `Take.from_keys`: body controls
  blend between keys, feet only move in listed steps.
- A sword is put on a track (in its scabbard, relative to the chest, or in the world) and the
  hands are solved onto its grip, or it is carried by a hand that follows the body. Once a hand
  is closed on the grip the sword's place is read back from that hand, so it cannot float.
- Cloth on a moving fighter is guided (`garments.driven`): it starts as it hangs at rest, every
  vertex carries the nearest body weights, and springs tie it to that carried shape - rigid at the
  top, almost free at the hem. Free cloth with collisions alone could not keep up with a walking
  body. Three findings behind this, each measured:
  - changing a cloth setting part-way through a run makes Blender jolt every panel outward
  - pins tied to one bone sink into skin that bends with several bones; the collision then
    throws the neighbouring cloth out on every frame (the cape stood up like a flag)
  - Blender uses the 4th power of a pin weight as the strength of the tie
- The Oni's trousers are part of his body mesh. A coarse cloth cage (`soft.py`) is simulated in
  their place and the detailed mesh follows it through a Surface Deform modifier. His hair still
  moves rigidly with the head.
- Simulated cloth is written to PC2 files and played back by a Mesh Cache modifier, so rendering
  needs no simulation and can start at any frame.
- The preview is rendered without motion blur or depth of field so that every frame is sharp.
- Not done yet: the draw (sword leaving the scabbard), clips downloaded from Mixamo (the folder
  for them is `assets/user/mixamo/`; `retarget.py` carries such a clip over bone by bone).
