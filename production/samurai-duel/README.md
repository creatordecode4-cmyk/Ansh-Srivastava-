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

## The film (Stage 4)
```bash
python3 -I tools/stage4_film.py shots                                   # usage and presets
python3 -I tools/stage4_film.py render 1 240 --preset block --step 8 --no-cloth    # staging check: every 8th frame, about 10 s each
python3 -I tools/stage4_film.py render 1 118 --preset look --cloth-to 240          # preview frames; the cloth is run once for the whole intro
python3 -I tools/stage4_film.py render 119 240 --preset look --reuse-cloth         # second half, cloth played back from the first run
python3 -I tools/stage4_film.py assemble --out previews/stage4_intro.mp4
python3 -I tools/stage3_preview.py render s4_oni --proxy --samples 8 --step 3      # one fighter's part in clay on the studio floor
python3 -I tools/stage4_film.py render 241 360 --preset block --step 4 --no-cloth --fight   # the fight: both whole parts, effects, camera shake
python3 -I tools/stage4_film.py render 241 720 --preset look --fight --cloth-to 720 --tag _prev   # fight preview; the first job runs the cloth for the whole film
python3 -I tools/stage4_film.py render 241 720 --preset look --fight --reuse-cloth --skip-done --tag _prev   # further jobs fill in what is missing
python3 -I tools/stage4_film.py assemble --tag _prev --from 241 --out previews/stage4_fight.mp4
python3 -I tools/stage4_film.py assemble --tag ,_prev --out previews/stage4_film.mp4   # intro (look) + fight (look_prev): the whole 30 s
```
One render job here may run for two hours at most, and all jobs share 15 GB of memory. A film
render holds 4 to 5 GB after an hour; three fit side by side, with nothing else running.
Two or three jobs on the same four cores do not finish sooner in total (about 2 frames a minute
at the look preset either way); they are only a way to stay inside the two-hour limit.

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
  - `skin.py`, `clear.py` — the body as a solid; keeping hands, scabbards, hat, blades and cloth out of it
  - `retarget.py` — bone-by-bone carry-over of a downloaded FBX clip (for Mixamo files)
  - `film.py` — Stage 4: the time map (film frames against take frames), each fighter's part, the shots' cameras
  - `hits.py`, `fightfx.py` — sparks and spray as projectiles with a formula; the fight's effects per film frame
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
- Nothing may pass through anything else. A captured performer is slim, unarmoured and bare-headed;
  on the broad, armoured fighters his motion puts hands inside hips, a scabbard through the
  trousers, a cape through the swords and an arm through the hat. `skin.py` poses the watertight
  skin and answers how far outside the body a point is; `clear.py` resolves each contact while a
  shot is baked (`Actor.perform`):
  - free hands are pushed out along the body's surface normal, elbows are turned out of the way
  - the hat is a solid (`clear.Hat`), not a ring of points: a thin blade slips between points.
    A free arm is kept out of the cylinder that stands on the rim (the shoulder is under the brim,
    so a hand over the hat means a forearm through it). Each arm has one sideways way out, eased
    over time, so a hand rising past the head swings out round the rim instead of jumping. An arm
    that only brushes the hat (a fist pumping up under the brim in the dash) is moved the shortest
    way off it instead; which of the two applies is settled once per stretch of frames
  - a hand closed on a planned sword cannot be moved: there the choreography has to be clean
    (the Oni's guard is at chest height because his arms are short for his trunk; the Ronin's two
    blades in the spinning kick keep the captured rhythm of his wrists but stay beside the body
    and below the brim, pointing out and back)
  - scabbards lie on two points of the skin (back) or hang from the belt and are pushed aside by
    the leg (hip), instead of being glued to one bone; they are fitted again after the arms have
    been moved, because the shoulders move with them
  - the hat gives up tilt where its brim would meet shoulders or sword grips
  - a carried sword's wrist is turned until the blade clears body and hat (the blade is tested
    every centimetre against the hat's own cone)
  - after a cloth run, cloth left inside the body is put back on its surface; the cape is pinned
    under the scabbards; the Oni's trouser legs press together instead of crossing
  `Actor.clip_report()` gives the worst overlap per kind of contact in millimetres (arm in body,
  arm in arm, scabbard, hat, strap arms, blade in body / arm / hat), and the cloth run reports
  how many frames have a drawn blade passing through cloth and how many cloth points came up
  through the hat (none in any preview shot). Measured on the preview
  shots, before -> after: Oni walk arm 79 -> 11 (his hand rests on the scabbard), scabbard
  14 -> 0; Ronin walk arm 72 -> 0; Ronin dash arm in the hat's space 27 -> 0; Oni cut arm 51 -> 0
  (142 with the first, navel-high guard); Ronin spinning kick with both blades, as captured: arm
  in body 116, arm in the hat's space 167, blade in body 133, blade in his own arm 72, 67 cm of
  blade through the hat -> all 0 with the planned swords. The same kick with free hands and the
  swords sheathed also clears to 0.
  The side test is only trusted near the skin and away from the open rims of body regions.
  Still open: the two strap arms under the hat are rigid and dip up to 15 mm into the shoulder
  when the head tilts hard in the spinning kick (they should hang and swing like the tassels);
  cloth is not tested against other cloth; at the crotch the thigh plates of a leg kicked high
  sink into each other under the waist cloth.
- The preview is rendered without motion blur or depth of field so that every frame is sharp.
- Not done yet: the draw (sword leaving the scabbard), clips downloaded from Mixamo (the folder
  for them is `assets/user/mixamo/`; `retarget.py` carries such a clip over bone by bone).

## Stage 4 notes
- The film is 720 frames at 24 fps. Each fighter's part is one unbroken take (`film.oni_intro`,
  `film.ronin_intro`, later the fight); the film shows it through a time map (`film.TIME`): a cut
  may skip a stretch, a beat may be shown slowed down. Frames are rendered one by one at the
  scene time the map gives them, with the camera of the shot they belong to, so slow motion and
  cuts need no re-timing of the animation.
- Intro, 0-10 s: drone push-in with a tilt up to the torii and the moon; the Oni walks in (low
  angle, the mask, the hand on the katana); over his shoulder the Ronin comes out of the mist in
  front of the torii; from below, two fingers lift the brim and the visor glints against the moon;
  the Oni's thumb pushes the guard; side on, both blades come out.
- The draws are cut, not shown whole. Reaching across to the left hip, the Oni's right forearm
  passes 7-12 cm into his belt whatever grip is tried (arms 54 cm, belt knot 27 cm out in front),
  and a 73 cm blade drawn over the Ronin's shoulder needs 78 cm of reach from a 54 cm arm. The
  film shows the start (thumb on the guard) and the end (blades clear) and skips 8 take frames
  between them. On the frames it shows, the takes measure clean.
- A walk captured from a performer is joined to a keyed stop on the frame where the front foot
  has just come down: the keyed part starts from the captured feet, and the place he stands is
  taken from the planted foot, which then only has to turn.
- A hand can hold the scabbard itself (`on='saya'`) while the sword leaves it, turn a belt-worn
  scabbard toward the other hand (`steer`), or rest on the hat (placed in the hat's own space).
- Cost on 4 CPU cores with both fighters in the arena: about 5 microseconds per sample and pixel.
  640x360 / 6 samples without fog: 10 s per frame. 960x540 / 8 samples with fog and bloom:
  35-45 s. 1080p / 128 samples: 20-25 min, which for 720 frames is not a job for this machine.
- The fight, 10-30 s, is written beat by beat in `film.fight()`; each beat carries both parts on
  from where the last left them: the dash and clash (slowed to a quarter), three overhead cuts
  stopped on crossed blades (held, driven back skidding, driven down), the Ronin's slip, spin and
  kick with the Oni thrown back across the floor, a three-blow exchange, the Oni's one-handed
  level cut with the Ronin leaping back, the crossing, and the still ending.
- Blades meet by construction, not by eye. One sword is placed from its own fighter's body (in
  his chest's frame, at places measured clear of his armour); the other is laid on a point of
  that blade, held from a fist placed in the second fighter's chest frame, and that fighter is
  stood where the reach is right. Measured at every clash: blade centre lines 1-7 mm apart.
- The Oni's sword work is built from the stations of the Stage 3 overhead cut and one-handed
  sweeps; with arms of 54 cm in front of a deep chest, two hands on the grip only work before the
  breastbone and above.
- Running: the clip's strides are stretched or shortened to cover exactly the distance to the
  mark, and a run is stopped over two steps (the last stride lands under the body, the other
  foot swings through and lands ahead), so that a fighter stops with his weight between his feet.
- A skid is the one case where a foot on the ground is meant to travel (`slide=True` steps).
- The crossing is seen from the side, where the two pass through one line; in depth they are a
  sword's length apart, and the blades meet between them.
- A blow that lands is held for 3 film frames (rows with rate 0 in the time map); the camera's
  jolt runs in film frames and so carries on through the hold.
- Measured on the whole fight (take frames 248-667): blade centre lines 2-7 mm apart at all eight
  clashes; nothing of one fighter inside the other (nearest: the Ronin's blades 27 and 42 mm from
  the Oni's head as he leans out of the spinning cut, the Oni's point 45 mm from the Ronin as he
  leaps back); planted feet do not drift. What still reads above zero: the Oni's trouser legs
  against each other in runs and lunges (the collision skin; the cloth cage is parted afterwards),
  and the hat's strap arms 14 mm into the Ronin's shoulders during the spinning kick.
- Effects (`sd/fightfx.py`) are functions of time, drawn from `film.EVENTS`: sparks and an impact
  flash at every clash (the flash runs in film frames, so it flares while the blow is held), water
  from stamping and skidding feet, fire on the Oni's blade for his great cut (flames stand on the
  blade and along the path of the swing, with a point light), the cut in the Ronin's cape (a mask
  on the simulated cape plus the cut-off piece falling by formula), his hat as two pre-cut halves
  from the frame it parts, and the crack laid on the Oni's mask by ray casts and grown over seven
  frames. The last half second fades to black.
- Cloth for the whole film (scene frames 1-729) takes about 17 minutes to simulate. In the run the
  fight preview was rendered from, 78679 of 5.7 million cloth points were inside the Ronin's body
  or too close (deepest 87 mm) and were put back; 312 stayed inside; no blade passes through cloth,
  nothing came up through the hat and nothing went below the ground. The Oni's trouser cage had
  115867 points (over the whole film) through the other leg, put back on their own side.
- The Oni's hair is not simulated: on his model it is a short stiff mane (no vertex held by the
  head is more than 22 cm from the middle of the skull, 14 cm behind it), which rides with the head.
- Finished picture: preset `half` or `final` adds motion blur that follows the time map and depth
  of field focused on what each shot looks at.
- Intro preview (`previews/stage4_intro.mp4`, stills in `previews/stage4_intro.jpg`): 240 frames at
  the look preset. On the frames it shows, the takes measure: Oni's hand on his scabbard 10.5 mm
  (it rests there), his trouser legs 45 mm into each other at the crotch as he walks (the cloth
  cage is then put back on its own side, 30018 points over the shot), the Ronin's fingers on the
  brim 45 mm into the space kept clear round the hat (they hold it); cloth: 17801 of 2.1 million
  points inside the body, 0 after they are put back, no blade through cloth.
- The camera's near clip is 30 cm: a snowflake drifting past the lens filled a corner of the last
  frame of the standoff until it was.
- Fight preview (`previews/stage4_fight.mp4`, film frames 241-720; stills, one per shot, in
  `previews/stage4_fight.jpg`) and the whole film (`previews/stage4_film.mp4`: the intro preview's
  frames 1-240 joined to the fight's): look preset, no motion blur or depth of field, labels burned
  in. With two jobs side by side a fight frame took 62-74 s; each job first spends 7 minutes
  building the fight and 1 minute loading the cloth. The intro in this film is still the one built
  without the fight (`out/stage4/look`); the finished film is rendered from the fight build alone.

