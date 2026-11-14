# Temple Fight – 30 s cinematic (Blender)

Oni Samurai vs Cyber Ronin in a Japanese temple courtyard at night.
Built entirely from Python scripts with headless Blender (`pip install bpy`), so the scene can be rebuilt anywhere.

## Status

| Stage | What | State |
|---|---|---|
| 1 | Arena (layout, props, lighting, fog, petals, snow) | Preview ready, procedural props; GLB props optional |
| 2 | Characters | Not started |
| 3 | Rigging and animation | Not started |
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
- `scripts/` – `lib.py` (mesh + material helpers), `build_arena.py`, `render_arena.py`, `fetch_assets.py`, `crop_props.py`
- `previews/` – stage preview renders
- `assets/`, `*.blend` – generated, not committed

## Scene conventions

Metres, +Y is north. Fighting area is the open floor around the origin (about 19 m x 31 m).
Torii at (0, 11.5), main temple west, stairs and upper terrace north.
Names: `COL_` collections, `CAM_` cameras, `LGT_` lights, `MAT_` materials, `FX_` particles and fields.

Textures, rocks and HDRI are CC0 from Poly Haven.
