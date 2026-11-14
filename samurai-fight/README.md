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

## Animation (Stage 3b)

```
python3 scripts/build_animatic.py                                    # arena + fighters + choreography + shot cameras
python3 scripts/render_frames.py build/animatic.blend build/animatic_frames 1 720   # resumable, ~5 s/frame at 512x288
bash scripts/encode.sh build/animatic_frames previews/stage3b_animatic.mp4 960 "BLOCKING"
python3 scripts/qa_animatic.py build/animatic.blend                 # foot-slide and blade-contact numbers
python3 scripts/choreo_strip.py <prefix> 270,308,392 [--oni|--ron] [--q34]   # fast pose checks without the arena
```

- `anim_lib.py` is the keyframing toolkit. Everything is keyed in world space with the character roots at the
  origin: feet are world plants (`plant`, `step`, `travel`, `slide`), the katana is the master and hands follow
  it through `GRIP_*` (switchable per hand with the `Grip` constraint influence), and `Actor.key()` solves hips,
  spine, head and IK poles from the feet and swords while respecting leg and arm reach.
  Facing is an angle: 0 = +X (east), 90 = +Y (north). Local pose coordinates are (left, forward, up).
- `choreo.py` holds the blocking for all beats. The duel runs north-south near x = -2.3: Oni stands at
  (-2.6, 0.2) facing north, Ronin at (-2.0, 10.3) under the torii facing south. Blade contacts use the
  `('thru', point, blade_dir, edge_dir, dist)` sword spec so both blades pass through the same world point.
- `build_animatic.py` adds one camera per shot bound to timeline markers, keys `FX_Clock` for the two
  slow-motion beats, hides the Oni's fused sheath handle at the draw frame and fades out at the end.
  The animatic renders the light `*_BodyLo` meshes; set `hide_render` the other way for final quality.
- Not in yet (Stage 4): sparks, splash, flame trail, cape tear, hat split, mask crack, cloth simulation,
  per-shot lighting, the Ronin's fused back-sword handles (still visible after the draw), thumb bones.
- The free DeepMimic motion capture was not used in this pass: walking and running are keyed step cycles.

## Stage status

1. Arena - procedural build + look pass done, review sheets posted; optional GLB props can still replace stand-ins.
2. Characters - meshes prepared, katanas built, accepted.
3. Rigging and animation - rig + IK controls done; blocking animatic of all beats rendered for review.
4. Timeline - shot cameras blocked; effects, cloth, lighting and final render not started.
