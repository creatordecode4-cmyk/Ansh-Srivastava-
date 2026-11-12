# ZERO ICE — 3D scroll-driven launch page (demo)

A cinematic, Apple-style product page for a fictional diet cola. One fixed WebGL can
rotates, travels and zooms as you scroll. Built with Vite, React, TypeScript, Tailwind,
three / @react-three/fiber / drei / postprocessing, GSAP ScrollTrigger and Lenis.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build into dist/
npm run preview
```

## Assets
- `public/videos/hero.mp4` — intro clip (plays once, then hands off to the 3D can)
- `public/videos/splash.mp4` — background of the Splash section. **Placeholder:** currently a
  loop cut from the hero clip. Drop your real 10-second splash video here with the same name.
- `public/images/hero-first.jpg`, `hero-last.jpg`, `splash-poster.jpg` — poster frames
- `public/models/can.glb` — optional. If present it replaces the procedural hero can.

## Structure
```
src/
  tokens.ts              brand colours, fonts, section lengths, flavour variants
  App.tsx                loader, fallback switch, section order
  lib/scroll.ts          Lenis + ScrollTrigger -> scroll store, scrollToSection
  lib/motion.tsx         motion/fallback detection, scrubbed timeline hook, reveal hook
  components/            Navbar, Hero, Marquee, Story, WhyZero, Splash, Taste, Lineup,
                         Nutrition, FanWall, FinalCTA, FAQ, Footer, Loader, Logo, PinSection
  three/
    scrollStore.ts       shared scroll state (written by GSAP, read in useFrame)
    choreography.ts      can + camera pose for every section, hero video match
    Scene.tsx            Canvas, camera rig, studio lighting, post-processing, quality
    Can.tsx              lathe can, pull-tab, condensation, optional GLB
    textures.ts          label, droplet, frost and mist textures generated in code
    IceCubes.tsx         refractive hero cubes, instanced cubes, crushed-ice bed
    Particles.tsx        droplets, splash burst, mist, sparkles
```

## Tuning
- Move or resize the can in a section: edit its pose in `three/choreography.ts`
  (`x`/`y` are viewport fractions, `s` is can height as a fraction of the viewport).
- Section scroll length: `sectionVh` in `tokens.ts`.
- Debug flags: `?no3d` forces the static fallback, `?q=high|low` forces quality,
  `?snap` removes pose smoothing.

## Fallbacks
No WebGL, a very low-end device, or `prefers-reduced-motion` skips the 3D layer and
smooth scrolling: the hero shows `hero-last.jpg` and sections render as normal blocks
with simple fade-ins.

ZERO ICE is a fictional brand created for a demo. Videos and images are AI-generated.
