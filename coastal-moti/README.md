# Coastal Moti: The Lost Pearl

An original 3D third-person action-adventure for the browser, set on the Konkan coast.
Story campaign + a battle mode against bots. Runs on phones (touch) and PC (keyboard + mouse).

**Status: Mission 0 "Andhera" is playable** with placeholder art (about 4 minutes: storm night, compass
tutorial, lighthouse cutscene, stealth escape with checkpoints). Mission 1 is only a placeholder card.

## Controls

| Action | PC | Phone / tablet |
|---|---|---|
| Move | WASD (or arrows) | Left thumb: virtual joystick (appears where you touch) |
| Run | hold Shift | push the joystick to its edge |
| Look | mouse (click once to capture it) | drag on the right half of the screen |
| Attack | left click or J | Attack button |
| Shakti (current power) | right click or Q | Shakti button |
| Select Shakti | 1-5 | tap a Shakti icon |
| Burst (charges by dealing damage) | F | Burst button |
| Tool | E | Tool button |
| Dodge-roll | Space | Dodge button |
| Pause | Esc or P | pause button |

The scheme is picked automatically (touch devices get the joystick and buttons).

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
index.html            page shell, importmap (three -> ./vendor), HUD and overlay markup
manifest.json         PWA manifest
sw.js                 service worker: precache + network-first with offline fallback
vendor/               three.js 0.160.0 (pinned, vendored) + its MIT licence
src/
  main.js             entry point: device check, settings, starts the game
  game.js             wires all systems together and runs the frame loop
  engine/
    engine.js         renderer, scene, lights, loop, quality + environment switching
    environments.js   look presets: ENV_DAY, ENV_STORM_NIGHT (sky, light, sea, fog, rain, lightning)
    weather.js        rain (one draw call, animated in the shader) and lightning
    world.js          level loader + builder helpers + collision / line-of-sight API
    player.js         third-person controller: walk, run, dodge-roll, attack, Shakti, Burst, Tool
    cameraRig.js      follow camera with wall avoidance + cutscene camera
    input.js combat.js health.js shaktis.js sky.js sea.js quality.js device.js events.js mathx.js
  levels/
    seepgaon.js       the village, the hill and the Diya-Ghar lighthouse (storm night)
    testArena.js      daytime combat test island
  ai/
    guard.js          stealth guard: fixed waypoint route, torch vision cone, hearing
    bot.js            combat bot: patrol, investigate, chase, shoot, cover
  missions/
    missionManager.js mission flow, objectives, checkpoints, scripts, saving
    andhera.js        Mission 0 "Andhera"
    mission1Placeholder.js
    systemsCheck.js   combat test mission (developer only)
  ui/                 hud.js, touchControls.js, pauseMenu.js, missionCard.js, radio.js, overlays.js,
                      compassTutorial.js, letter.js, *.css
  audio/audio.js      sound hooks (synthesized placeholder sounds, storm ambience, thunder)
  save/               save.js (progress, checkpoint, flags), settings.js (quality, sound)
assets/               icons/ (original) · models/ textures/ audio/ are still empty
licenses/ASSETS.md    one line per third-party asset: name, author, URL, license
```

## Mission 0 "Andhera" (23:40 · Seepgaon Diya-Ghar)

1. The lighthouse flickers three times and goes dark. Baba's radio call cuts off.
2. **Compass tutorial:** take Dadaji's brass compass from the porch and turn it. The needle always swings
   back to the same direction: the island. Saves the flag `compassPointsToIsland` (needed in the finale).
3. Climb the lane to the Diya-Ghar. Cutscene: men in black cut the lamp wires.
4. **Stealth escape:** four guards walk fixed routes. The lit cone on the ground is exactly what a torch
   can see; walls and houses cut it. Standing under a street lamp makes Veer visible from far away
   (the HUD shows HIDDEN / IN LIGHT / SEEN). Running close to a guard makes it stop and look.
   If the meter fills: "Spotted", then back to the last checkpoint.
5. Take Dadaji's tin box at the boat shed (half a map + a letter), then get home.
6. Objective card, one-line card, then the Mission 1 placeholder card.

Checkpoints (saved to localStorage, a refresh resumes there): `compass`, `escape`, `mid`, `box`.
Flags saved in `progress.flags`: `hasCompass`, `compassPointsToIsland`, `hasHalfMap`, `hasDadajiLetter1`.
To replay the mission after finishing it: pause menu -> "Reset all progress".
Developer option: open `/?mission=t0_systems_check` for the daytime combat test arena.

## How to add a mission

A mission is a plain object registered in `src/game.js` with `game.missions.register(mission)`.
`src/missions/andhera.js` is the full example. The minimum is:

```js
export const mission = {
  id: 'm1_example', name: 'Mission name', location: 'Seepgaon Diya-Ghar', time: '23:40',
  level: 'seepgaon',
  objectives: [{ id: 'reach', text: 'Reach the gate', target: { x: 0, z: 0 } }],
  endLine: 'Optional one-line card at the end.',
  start(ctx, checkpoint) { ctx.placePlayer(0, 38); ctx.radio('Aangan', 'Move.'); },
  update(ctx, dt)        { if (ctx.playerNear({ x: 0, z: 0 }, 2.5)) ctx.completeObjective('reach'); },
  complete(ctx)          { ctx.unlockShakti('vayu'); },
};
```

`ctx` also offers `checkpoint(id)`, `fail(title)`, `setFlag(name)`, `skipTo(objectiveId)`,
`script(async (s) => { await s.wait(2); ... })` for timed sequences, `spawnBot(...)`, `setTarget(pos)` and
`setObjectiveText(id, text)`. Radio lines over 12 words are cut and reported in the console.

## Sound hooks

Every event calls `game.audio.play('<name>')` (attack, hit, hurt, dodge, radio, objective, thunder, static,
flicker, pickup ...). Today each name is a short synthesized sound, and the storm ambience is filtered noise.
To swap in a real file: `game.audio.load('attack', 'assets/audio/attack.ogg')`, then add the file to
`licenses/ASSETS.md`.

## Known limits

- All art is placeholder shapes; characters have no skeletal animation.
- "Climbing the lighthouse" is a cutscene: there are no interiors, stairs, jumping or climbing yet.
- Guards never leave their routes (by design for this mission) and do not search for the player.
- Line of sight is checked in 2D against walls, houses and tall stacks; low props do not hide Veer.
- Combat bots (test arena) still have no path-finding.
- Shakti effects and all damage numbers are placeholder tuning.
- Not yet profiled on a real phone. The 30 FPS target must be checked on a mid-range Android device.
- Stealth difficulty was tuned with an automated walker, not with human players.

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
- `window.__moti` exposes the game object in the browser console for debugging.

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
