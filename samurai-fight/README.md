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

## Characters (Stage 2)

- Source: two Tripo image-to-3D GLBs kept in the owner's Google Drive folder `3d` (about 59 MB each, not in git).
  Download them into `build/glb_in/`, then:
  `python3 -I scripts/prep_characters.py <oni.glb> <ronin.glb> build/characters.blend`
  followed by `bash scripts/render_stage2.sh`.
- Each GLB is ONE fused watertight shell in a T-pose (1.9 M triangles, 1024 px base colour / normal /
  roughness-metallic). Hat, cape, waist cloth, hakama and sheathed swords are part of the body surface, so
  they cannot simply be split into objects. `prep_characters.py` welds UV-seam splits, scales to real height
  (Oni 1.98 m to the horn tips, Ronin 2.00 m to the hat tip), grounds the feet and decimates to 400k triangles.
- Drawn katanas are procedural (`scripts/weapons.py`): +Z along the blade, edge toward -Y, origin at the guard.
- The glTF importer leaves objects in quaternion rotation mode; set `rotation_mode = 'XYZ'` before using Euler angles.

## Rig (Stage 3a)

```
python3 scripts/rig_characters.py build/characters.blend build/characters_rigged.blend   # skeleton + skin weights
python3 scripts/rig_controls.py build/characters_rigged.blend build/characters_ctrl.blend  # IK controls + katanas
python3 scripts/build_standoff.py                                                         # both in the arena
```

- Skeleton uses Mixamo bone names (Hips, Spine, LeftArm, ...) so Mixamo clips can be retargeted later.
  Joint positions were measured on each T-pose mesh (`scripts/measure_char.py`) and live in `rig_characters.py`.
- Skin weights: Blender bone-heat on a 30k proxy of the watertight shell, copied to the 400k mesh by nearest
  vertex (scipy cKDTree). The Oni's sheathed sword is made rigid to the Hips bone.
- Fingers are one three-bone "mitten" block per hand (no thumb bone yet).
- Controls (children of `<Name>_Root`): `FOOT_L/R` + `KNEE_L/R` (leg IK, planted feet cannot slide),
  katana objects as the masters with `GRIP_L/R` children (arm IK and hand rotation follow the sword, so
  blade contact is set directly), `ELBOW_L/R` poles. Hips, spine, neck, head are FK.
- `scripts/stances.py` holds stances in character-local space (character faces -Y, its left is +X).
- Animation source: Mixamo is unreachable from the cloud workspace and needs the owner's login. Free
  DeepMimic motion capture (walk, run, kick, spin kick, spin, jump, roll) is available inside the `pybullet`
  source package on PyPI (`pip download --no-deps --no-binary :all: pybullet`, folder
  `examples/pybullet/gym/pybullet_data/data/motions/`). Sword work is to be hand-keyed through the IK controls.

## Stage status

1. Arena - procedural build + look pass done, review sheets posted; optional GLB props can still replace stand-ins.
2. Characters - meshes prepared, katanas built, previews posted and accepted ("Ok").
3. Rigging and animation - rig + IK controls + guard stances done (3a); animation not started.
4. Timeline - not started.
