# Image-to-3D pack (Stage 1 props + Stage 2 characters)

Do these in order. If your free credits run out, stop — the arena already works with my stand-in props.

| Priority | Generate | Input images | Save the download as |
|---|---|---|---|
| 1 | Oni Samurai body | your 2 new hi-res images (prompt A) | `oni_body.glb` |
| 2 | Cyber Ronin body | your 2 new hi-res images (prompt B) | `ronin_body.glb` |
| 3 | Stone lantern | `props/lantern_front.png` + `props/lantern_side.png` | `lantern.glb` |
| 4 | Temple | `props/temple_front.png` | `temple.glb` |
| 5 | Torii gate | `props/torii_front.png` + `props/torii_side.png` | `torii.glb` |
| 6 | Broken lantern | `props/lantern_broken_front.png` + `props/lantern_broken_side.png` | `lantern_broken.glb` |

## Step 1 – make hi-res character views (in the AI image tool that made your sheets)

Your sheets are 1536x1024, so each figure is only 300-500 px tall. Image-to-3D copies what it sees, so
bigger and cleaner input gives a much better mesh. Attach the character sheet, paste the prompt, then
ask for the back view. You need 4 images in total (front + back for each character).

**Prompt A – Oni Samurai (attach `oni_sheet`)**

```
Use the attached character sheet as the exact design reference. Create ONE image: a full-body FRONT view
of this same Oni Samurai standing in a strict T-pose (arms straight out to the sides, palms down, fingers
slightly apart, feet shoulder-width apart). Orthographic look, camera at chest height, character centred
and filling 90% of the image height. Plain flat mid-grey background, soft even studio lighting, no cast
shadow on the background.
Keep every design detail identical to the sheet: red oni mask with two red-tipped horns, long white hair
in a high ponytail, bare pale torso with black harness straps, red tattoo on the right shoulder, black
sleeves, gold forearm bracers, black gloves, red rope belt with tassels, black hakama trousers fading to
red at the hems with black flame pattern, black tabi socks and red sandals.
REMOVE the katana and its scabbard completely: nothing on the hip, nothing in the hands.
No text, no labels, no extra views. Portrait 2:3, highest resolution.
```

Then send: `Now the BACK view of exactly the same character, same T-pose, same framing and lighting.`

**Prompt B – Cyber Ronin (attach `ronin_sheet`)**

```
Use the attached character sheet as the exact design reference. Create ONE image: a full-body FRONT view
of this same Cyber Ronin standing in a strict T-pose (arms straight out to the sides, palms down, fingers
slightly apart, feet shoulder-width apart). Orthographic look, camera at chest height, character centred
and filling 90% of the image height. Plain flat mid-grey background, soft even studio lighting, no cast
shadow on the background.
REMOVE the conical hat, the white cape and scarf, the white waist cloth and both katanas with their
sheaths, so the complete armoured robot body is visible: visor helmet with a black faceplate, chest armour
plate with two round bolts, white segmented armour panels on arms and legs, exposed black mechanical
joints, armoured boots. Nothing in the hands, nothing on the back.
Keep the armour design, proportions and white/black colours identical to the sheet.
No text, no labels, no extra views. Portrait 2:3, highest resolution.
```

Then send: `Now the BACK view of exactly the same character, same T-pose, same framing and lighting.`

Check before you continue: arms level, hands clearly separate from the body, legs not touching, no
weapon, plain background. If the tool changes the design, regenerate.

I build the hat, cape, waist cloth, katanas and scabbards myself in Blender from your parts sheets, so
they stay separate objects, the blades are straight, and the cloth can be simulated.

No way to regenerate? `characters_fallback/` has the T-pose views cropped from your sheets (upscaled).
They work, but the mesh will be softer and the Ronin's hat, cape and swords will be fused to the body.

## Step 2 – Tripo or Meshy

1. Choose Image to 3D. If the tool offers multi-view / multi-image, use it: front image first, then back
   (or side, for the props).
2. Turn textures ON. Turn PBR ON if it is free. Pose option, if shown: T-pose.
3. Generate, then download as **GLB**.
4. Rename the file exactly as in the table.

Free-plan credits and licences change often. Check the credit cost shown before each generation, and read
the licence line if you plan to monetise the video.

## Step 3 – send the files

Attach the GLB files in chat, or put them in one Google Drive folder shared as "Anyone with the link"
and send me the link.
