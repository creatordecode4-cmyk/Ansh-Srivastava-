# Temple Fight – 30 s cinematic (Blender)

Oni Samurai vs Cyber Ronin in a Japanese temple courtyard at night.
Built entirely from Python scripts with headless Blender (`pip install bpy`), so the scene can be rebuilt anywhere.

## Status

| Stage | What | State |
|---|---|---|
| 1 | Arena (layout, props, lighting, fog, petals, snow) | Preview ready, procedural props; GLB props optional |
| 2 | Characters (Oni Samurai, Cyber Ronin) | Tripo AI models, rigged and skinned on a shared skeleton |
| 3 | Rigging and animation | Full 30 s fight animated in code, 23 camera shots, sparks on every clash; preview video ready |
| 4 | Timeline, cameras, final render | Not started |

## Rebuild the arena

```bash
pip install bpy pillow
python3 scripts/fetch_assets.py      # CC0 textures, rocks and night HDRI from Poly Haven -> assets/
python3 scripts/build_arena.py       # writes arena.blend
python3 scripts/render_arena.py --cam CAM_Hero --res 1280x720 --spp 64 --out previews/hero.png
python3 scripts/render_arena.py --cam CAM_Hero --clay --out previews/clay.png
```

Cameras: `CAM_Hero`, `CAM_TopDown`, `CAM_Temple`, `CAM_Torii`.

## Build the characters

The fighters are the user's Tripo AI models. Put the two files in `assets/glb/` (not committed, about 59 MB each):
`oni_body.glb` and `ronin_body.glb`.

```bash
pip install scipy
python3 scripts/build_fighters.py --pose a --views front,34,side,back --res 480x860 --spp 48   # writes characters.blend + stills
python3 scripts/build_fighters.py --pose guard --views 34l                                    # skinning test, swords drawn
python3 scripts/render_standoff.py --res 1280x720 --spp 64 --out previews/stage2_standoff.png  # both in the arena, writes fight_scene.blend
```

What `scripts/fighters.py` does to each fused, un-rigged T-pose mesh:
1. scales it to real height (Oni 2.05 m to the horn tips, Ronin 1.95 m to the hat top) and halves the 2M triangles
2. fits the shared humanoid skeleton from `scripts/joints.py` (joints picked on gridded views, `scripts/landmark_glb.py`)
3. skins it: bone-heat weights solved on a clean voxel copy, transferred to the full mesh, with the hat and
   sheathed swords locked rigidly to one bone
4. cuts the sword hilts and the Ronin's hat into their own objects (`Oni_SheathedHilt`, `Ronin_SheathedHilt_L/R`, `Ronin_Hat`)
5. adds clean hand katanas (`Oni_Katana`, `Ronin_Katana_L/R`), hidden until drawn; `fighters.draw_swords()` swaps the two states

Still fused into the body mesh (no cloth simulation possible on them): the Ronin's cape and waist cloth, the Oni's hakama and hair.

## Animate the fight (Stage 3)

```bash
python3 scripts/fight_base.py --tag preview --ratio 0.10   # arena + rigged fighters (light meshes) -> fight_base_preview.blend
python3 scripts/build_fight.py --tag preview               # bake animation, cameras, sparks -> fight_scene_preview.blend
python3 scripts/render_fight.py --tag preview --frames 1-720 --res 480x270 --spp 8      # frames -> render_tmp/preview/
ffmpeg -framerate 24 -start_number 1 -i render_tmp/preview/f%04d.png -c:v libx264 -pix_fmt yuv420p previews/stage3_preview.mp4
```

- `rigctl.py` – IK feet and hands with pole targets on the shared skeleton (pole angles calibrated numerically).
- `anim.py` – procedural animation engine: named channels keyed in code with easing, solved to bone transforms and baked
  as keyframes. Feet are keyed in world space, so a planted foot cannot slide. Sword grips and blade directions are keyed
  in world space, so two blades are aimed through one shared contact point at every clash.
- `choreo.py` – the choreography (walk-ins, draw, dash and slow-motion clash, three overhead strikes, spin and kick,
  fast exchange, power slash, final crossing, back-to-back freeze).
- `shots.py` – 23 cameras bound to timeline markers (Blender cuts automatically), including side tracking shots of both walks.
- `fx.py` – sparks and a light flash at every clash, with camera shake driven by the same events.

## Swapping in image-to-3D props

Every hero prop is built procedurally, and is replaced automatically when a GLB with the matching
name exists in `assets/glb/`:

| File name | Source image |
|---|---|
| `stone_lantern.glb` | `prop_images/01_stone_lantern.png` |
| `broken_stone_lantern.glb` | `prop_images/02_broken_stone_lantern.png` |
| `torii_gate.glb` | `prop_images/03_torii_gate.png` |
| `paper_lantern.glb` | `prop_images/04_paper_lantern.png` |
| `temple_building.glb` | `prop_images/05_temple_building.png` |
| `cherry_tree.glb` | `prop_images/06_cherry_branch.png` |

## Folders

- `refs/` – the seven reference sheets
- `prop_images/` – each arena prop cropped out for image-to-3D
- `scripts/` – `lib.py` (mesh + material helpers), `build_arena.py`, `render_arena.py`, `fetch_assets.py`, `crop_props.py`, `charlib.py` (skeleton, katana), `joints.py`, `fighters.py`, `build_fighters.py`, `landmark_glb.py`, `inspect_glb.py`, `render_standoff.py`, `rigctl.py`, `anim.py`, `choreo.py`, `shots.py`, `fx.py`, `fight_base.py`, `build_fight.py`, `render_fight.py`
- `previews/` – stage preview renders
- `assets/`, `*.blend` – generated, not committed

## Scene conventions

Metres, +Y is north. Fighting area is the open floor around the origin (about 19 m x 31 m).
Torii at (0, 11.5), main temple west, stairs and upper terrace north.
Names: `COL_` collections, `CAM_` cameras, `LGT_` lights, `MAT_` materials, `FX_` particles and fields.

Textures, rocks and HDRI are CC0 from Poly Haven.
