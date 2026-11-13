# Stylized Luxury Blue Palace (Blender, headless bpy)

An Indo-Mughal / Rajput style blue-and-gold palace with pools, gardens, a boundary wall,
hills and a lake. Game-art look, built 100% from Python: no downloaded models or textures.

| File | What it is |
|---|---|
| `build_palace.py` | The whole scene as code |
| `palace.blend` | Saved Blender scene (made with Blender 5.3) |
| `palace.glb` | Export for web / game / map use (flat colors, modifiers applied, 3 cameras) |
| `renders/palace_hero_front.png` | Front hero shot |
| `renders/palace_iso_map.png` | Isometric (orthographic) map-style view |
| `renders/palace_pool_low.png` | Low angle across the main pool |

## Run it

```bash
pip install bpy                       # Blender as a Python module (about 400 MB)
python3 build_palace.py               # full build: 3 PNGs + palace.blend + palace.glb (about 5 min on CPU)

python3 build_palace.py --stage 1 --preview     # palace only, half-res quick check
python3 build_palace.py --stage 2 --preview     # + pools      (3 = + garden, 4 = + terrain)
python3 build_palace.py --time night            # day | sunset | night
python3 build_palace.py --outline               # Freestyle toon outline
python3 build_palace.py --cams CAM_Iso_Map      # render only one camera
```

With normal desktop Blender: `blender -b -P build_palace.py -- --stage 4`.
On a server without a GPU, EEVEE needs software OpenGL: `apt-get install libegl1 libgl1-mesa-dri`.

## Change things

Everything is in `CONFIG` at the top of `build_palace.py`:

- `colors`: wall blue, gold, marble, water, lawn, flowers (hex codes)
- `pool_main` / `pool_side` / `channel`: size and position (paths, loungers and lights follow)
- `palace`: footprint and dome height
- `time_of_day` plus the `TIMES` table: sun angle, sun color, sky gradient, window and lamp glow
- `render`: resolution and samples

Building blocks are separate functions: `build_dome`, `build_chhatri`, `build_tower`, `build_window`,
`build_jharokha`, `build_parapet`, `build_pool`, `build_fountain`, `build_palm`, `build_cypress`,
`build_lamp`, `build_lounger`, and so on.

## Scene facts

- Units are meters. Palace body 120 x 60 m, 3 floors, main dome top at 45 m (finial about 51 m).
- Collections: `Palace`, `Pools`, `Garden`, `Terrain`, `Lights`, `Camera`. Object prefixes:
  `PAL_`, `POOL_`, `GDN_`, `SUR_`, `TER_`, `LGT_`, `CAM_`, materials `MAT_`.
- About 419k triangles after modifiers. Bevel on hard shapes, Array on parapets and channel lamps,
  Mirror for towers, side domes, side pools and the garden halves.
- EEVEE, AgX (Punchy look), soft sun shadows, ambient occlusion, bloom via the compositor Glare node.

## Honest limits

- The blue gradient, tile pattern and water ripples are procedural shaders, so they only exist in
  `palace.blend`. `palace.glb` uses flat colors instead.
- The 3 final PNGs are the `sunset` preset. `day`, `night` and `--outline` were only smoke-tested at
  half resolution; they run, but they were not tuned.
- Pools are raised basins sitting on the ground, not cut into the terrain.
- No rigging or animation; it is a still scene.
