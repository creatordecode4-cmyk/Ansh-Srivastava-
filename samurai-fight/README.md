# Samurai fight – 30 s Blender short (Oni Samurai vs Cyber Ronin)

Headless Blender (`bpy`) project. Everything is rebuilt from scripts, so no `.blend` is stored in git.

```
pip install bpy            # Blender 5.3 as a Python module (no GPU needed)
python3 scripts/build_arena.py      # -> build/arena.blend
bash scripts/render_stage1.sh       # -> build/stage1/*.png  (about 12 min on 4 CPU cores)
python3 scripts/render.py build/arena.blend out.png --cam CAM_Hero --res 960x540 --spp 24
```

| Folder | What |
|---|---|
| `refs/` | The 7 reference images (JPEG copies) |
| `scripts/` | `sf_lib.py` materials + helpers, `props.py` prop builders, `build_arena.py` layout/lights/cameras, `render.py` |
| `pack/` | Cropped images + prompts for the image-to-3D step (Tripo / Meshy) |
| `previews/` | Stage preview renders |

## Layout facts (Stage 1)

- Traced from the top-down panel of `arena_breakdown` at 35 px = 1 m, +Y = north = toward the torii.
  `sf_lib.px(x, y)` converts traced pixels to metres.
- Tiled court: X -14.6..14.9, Y -12.6..12.6. Fight centre (0, 1). Torii at (-2.2, 14.3) on a 0.5 m platform.
  Main temple faces the court at -30 degrees; six stone lanterns (two broken) at the traced glow positions.
- Every prop lives in a `PROP_*` collection inside `LIB` and is placed as a collection instance, so an
  image-to-3D GLB can replace a stand-in by swapping the collection contents.
- Cameras: `CAM_Hero` (low angle, like `arena.png`), `CAM_Fight`, `CAM_Wide` (drone start), `CAM_Top` (ortho layout check).
- Falling petals and snow are a deterministic Geometry Nodes system driven by `FX_Clock.location.z`
  (seconds). Keyframe that value for slow motion. No simulation cache is needed.
- Lighting: cold key sun + red rim sun from the moon (both hidden from volume scatter so the fog stays dark),
  red practicals in lanterns and temples, three mist-only lights behind the torii. AgX, exposure 0.

## Stage status

1. Arena – procedural blockout + look pass done, waiting for review and optional GLB props.
2. Characters – waiting for `oni_body.glb` / `ronin_body.glb` (see `pack/README.md`).
3. Rigging and animation – not started.
4. Timeline – not started.
