# Asset & third-party licenses

Rule: every file under `/assets` and `/vendor` that we did not make ourselves gets ONE line here
**before** it is committed. Only CC0 or clearly commercial-use-allowed licenses. No exceptions.

Format: `name | author | URL | license | where it is used`

## Third-party code

- three.js 0.160.0 (`vendor/three.module.min.js`) | three.js authors | https://github.com/mrdoob/three.js | MIT (full text in `vendor/THREE-LICENSE.txt`) | 3D rendering engine

## Third-party art, audio, fonts

- None yet. The sky and sea are generated in code (shaders); the UI uses the device's system font.

## Original work made for this project (no third-party licence needed)

- App icon (`assets/icons/icon.svg`, `icon-192.png`, `icon-512.png`) | project team | – | original | PWA / home-screen icon
- Sky and sea shaders (`src/engine/sky.js`, `src/engine/sea.js`) | project team | – | original | environment

## Free assets to add later (suggested sources, all CC0 — check each pack's page again when downloading)

- Characters with animations (Veer, Kavya, Damini, Kaala Jaal gang): Quaternius character packs — https://quaternius.com
- Boats, docks, huts, crates, palm trees, rocks, lighthouse parts: Kenney "Pirate Kit" / "Nature Kit" — https://kenney.nl/assets ; Quaternius nature packs
- Kingfisher (Neelu) and drone (Cheel's): a low-poly bird and drone from Quaternius / Kenney, recoloured
- Sand, rock, wood, plaster textures (1K is enough for mobile): Poly Haven — https://polyhaven.com/textures
- Sky HDRIs, if we ever replace the shader sky: Poly Haven — https://polyhaven.com/hdris
- UI click and combat sound effects: Kenney audio packs — https://kenney.nl/assets/category:Audio
- Music and the lullaby: must be ORIGINAL (record or compose it ourselves); do not use an existing song.
