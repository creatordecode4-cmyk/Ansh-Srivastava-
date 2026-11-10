# Coastal Moti: The Lost Pearl

An original 3D third-person action-adventure for the browser, set on the Konkan coast.
Story campaign + a battle mode against bots. Runs on phones (touch) and PC (keyboard + mouse).

**Status: skeleton only.** A sky and an animated sea render; there is no gameplay yet.

## Run it

It is a plain static site: no install, no build step. You only need any static file server
(opening `index.html` directly with `file://` will not work, because browsers block ES modules there).

```bash
cd coastal-moti
python3 -m http.server 8080      # or: npx serve -l 8080
```

Open <http://localhost:8080>. To test on a phone on the same Wi-Fi, open `http://<your-PC-IP>:8080`
(note: install-to-home-screen and offline mode need **https** or `localhost`, so test those after deploying).

Free hosting that works as-is: GitHub Pages, Netlify, Cloudflare Pages, Vercel (deploy the `coastal-moti` folder).
All paths are relative, so it also works from a sub-folder URL.

## Folder structure

```
index.html            page shell, importmap (three → ./vendor), HUD placeholders
manifest.json         PWA manifest (name, icons, landscape, fullscreen)
sw.js                 service worker: precaches the app shell, cache-first, offline after first visit
vendor/               three.js 0.160.0 (pinned, vendored locally) + its MIT licence
src/
  main.js             entry point: device check, settings, quality button, starts the engine
  engine/             engine.js (renderer, scene, loop), sky.js, sea.js, quality.js, device.js
  ui/                 base.css, controlsHint.js
  save/               settings.js (localStorage)
  missions/ ai/ audio/   empty for now
assets/
  icons/              original app icon (SVG + 192/512 PNG)
  models/ textures/ audio/   empty for now
licenses/ASSETS.md    one line per third-party asset: name, author, URL, license
```

## Tech rules

- Pure static web project, no backend, no paid services, no paid assets.
- Three.js pinned at **0.160.0**, plain ES modules, no build step.
- Performance target: **30 FPS on a mid-range Android phone.** Low-poly models, simple lights,
  ONE shadow-casting directional light, instancing for repeated objects.
- Quality toggle Low / Medium / High (`src/engine/quality.js`). Mobile defaults to Low, PC to Medium.
  The choice is remembered.
- Controls: mobile = left virtual joystick + right buttons (Attack, Shakti, Burst, Tool, Dodge);
  PC = WASD + mouse + keys 1-5 for Shaktis. The right scheme is picked automatically.
- When you add or rename a file, add it to `PRECACHE` in `sw.js` and bump `CACHE_VERSION`.

## Originality and legal rules

- Everything is original: no names, characters, missions, dialogue, logos, fonts, HUD layouts,
  sounds or music from any existing game or film.
- Third-party assets must be CC0 or clearly commercial-use-allowed, and be listed in
  `licenses/ASSETS.md` before they are committed.
- No real-money mechanics, no loot boxes, no trading, no cash-out items.

## Story bible (use consistently everywhere)

| Who / what | Details |
|---|---|
| **Veer** (17) | Hero. Fisherman's son from Seepgaon, Konkan coast. Callsign **"Disha"**. |
| **Inspector Kavya Naik** | Coast Guard. Callsign **"Deepak"**. Calm, short sentences. |
| **Meenu** (9) | Veer's sister, on radio from home. Callsign **"Aangan"**. Light humor. |
| **Damini** (22) | Freelance treasure hunter with a drone. Callsign **"Cheel"**. Starts with the enemy, switches sides in Mission 3. |
| **Neelu** | A kingfisher that shows the way, like an objective marker. |
| **Baaz** | Leader of the smuggler gang **Kaala Jaal**. Calm, professional, never shouts. Puts out the Diya-Ghar lighthouse on purpose so ships crash in storms and his gang can loot them. |
| **Dadaji** | Veer's late grandfather. Appears only in short letters found at each clue. |
| **Rani Chandravati** | Fictional coastal queen from the 1700s. Seen only in murals and the lullaby. |
| **Chandramoti pearl** | The heart of the Diya-Ghar lighthouse. |
| **Dadaji's brass compass** | The key that fits the lamp socket. |

- **The lullaby is the treasure map.** Each line is one clue; each clue unlocks one Shakti:
  **Vayu** (wind), **Agni** (fire), **Jal** (water), **Bijli** (lightning), **Dharti** (earth).
- **The one big twist (Mission 4):** the "pirate queen" was a protector. The pearl was never
  treasure; it was the lighthouse's light.
- **Dialogue rules:** every line max 12 words. Military-radio tone ("Copy." "Move." "Sniper on the roof.").
  No crying, no long speeches.
