# Waterfall Valley: Blender build (Step 1 of 8)

Reference: `previews/reference_breakdown.png`. I matched the layout to the **left column** (Final + Clay, left panel).

## How to run
1. Blender (4.2+ or 5.x) → **File > New > General** (a new file, because the script deletes the objects in the current scene first).
2. **Scripting** tab → **Open** → `build_waterfall_scene.py` → **Run Script** (takes about 1-2 minutes).
3. The viewport switches to the camera view. Press **F12** to render the clay still.
   - Command line: `blender -b -P build_waterfall_scene.py` builds the scene and saves
     `~/waterfall_project/step1_clay.png` + `waterfall_valley.blend`.

## Step 1 contents (geometry + camera, grey clay)
| Collection | What is in it |
|---|---|
| Terrain | Valley ground (river channel, banks, grassy slopes), distant mountain range |
| Rocks | Amphitheatre cliff (layered strata, 12 m Solidify), right cliff wall, 18 hero boulders, 30 bank boulders, river stones |
| Water | River surface (z = 0), main waterfall curtain (27 m tall, 10→14 m wide), thin side strand |
| Vegetation | 20 pines on the left slope, 1 tall hero pine, about 14 on the cliff top, 45 bushes (blockout proxies) |
| Lights / Camera | Sun key (azimuth 24°, elevation 25°), `CAM_Main` 24 mm at 1.8 m, tilted 6° up |
| Leaves, Birds | Empty for now (Steps 2B and 3) |

Clay override: `MAT_Clay` (grey 0.6, roughness 0.8) on the View Layer. Render: Cycles 32 samples, denoise, AgX, 50% resolution.

## Settings you can change (top of the script)
- `MIRROR_X = True`: flips the whole layout (waterfall to the left, sun/tree top-left, as your text says).
- `CAM_LOC`, `CAM_PITCH_DEG`, `CAM_LENS`: framing.
- `PREVIEW_PERCENT`, `PREVIEW_SAMPLES`: clay test speed.

## Honest limits
- I couldn't run Blender in the sandbox. I tested the geometry with a dry run in pure Python and
  checked the composition with an offline z-buffer preview (`previews/step1_compare_reference.png`).
  Run it in real Blender and send a screenshot of the F12 result.
- The reference panel is wider (about 2.7:1), while our frame is 16:9, so more sky and foreground show above and below.
- Pines and bushes are blockout proxies (cones/blobs). Real needle clusters, the leafy foreground tree and grass come in Step 2B.

## Plan (pick up from here)
1. ✅ Plan + Clay match (this file)
2. Materials + lighting: turquoise water, strata rock + moss/lichen, Nishita sky, warm sun, mist, haze
3. 2B Leaves + vegetation: weeping foreground tree (top corner), translucent leaves, Geometry Nodes grass/bushes, needle pines
4. Animation: Bezier camera glide (1-480), 6-8 birds, wind sway, water flow, mist
5. Render: 1920x1080, 24 fps, Cycles 128 + denoise, MP4 H.264
6. Colour grade (colour-grading-expert)
7. Sound suggestion (sound-design-expert)

---

## MP4 without Blender: the `web_render/` route
You don't have Blender, so I rebuilt the same scene in **Three.js** (headless Chromium, software WebGL) and render it frame by frame.
This is **not Blender Cycles**: it's a real-time renderer, so the look is stylized-realistic (low-poly pines, simple shadows, no path tracing).

| Step | Tool | File |
|---|---|---|
| Geometry + vertex colours (grass, strata, moss, lichen, snow) | Python | `export_scene.py` → `scene_data/` |
| Materials, water shader (turquoise, flow, foam), waterfall, mist, backlit weeping tree, grass, birds, camera path, god rays | Three.js r170 | `scene.js`, `index.html` |
| 480 frames @ 1920x1080 | Playwright + Chromium | `render.js` |
| Colour grade (bloom, warm highlights, saturation 1.16, lifted blacks, vignette, grain) | ffmpeg | `grade_filter.txt`, `encode.sh` |
| Ambient sound (waterfall, river, wind, birds, soft pad), all synthesized | ffmpeg | `make_audio.sh` |

Run:
```bash
cd web_render && npm install three@0.170.0
python3 export_scene.py
node render.js frames 1 480 1 1920          # ~5-8 s/frame on CPU
./make_audio.sh && ./encode.sh frames ambience.wav waterfall_valley.mp4
```
