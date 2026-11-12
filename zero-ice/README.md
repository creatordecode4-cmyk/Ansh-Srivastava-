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
  lib/motion.tsx         motion presets (EASE, SPRING, revealVariants) and the shared
                         <Glass>, <Reveal>, <PopButton>, <Collapse>, <Modal>; fallback detection;
                         scrubbed GSAP timeline hook
  data/brandStats.ts     ALL demo figures, timeline, testimonials and badges (edit per client)
  components/            Navbar, Hero, Marquee, TrustStrip, Story, Journey, WhyZero, Numbers,
                         Splash, Taste, Lineup, Nutrition, Recommendations, LoveIt, Community,
                         FinalCTA, FAQ, Footer, Loader, Logo, CountUp, PinSection
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
- Theme: the five palette colours live in `tokens.ts` and flow into Tailwind and the 3D scene.
- Demo figures: everything numeric is in `src/data/brandStats.ts`.
- Move or resize the can in a section: edit its pose in `three/choreography.ts`
  (`x`/`y` are viewport fractions, `s` is can height as a fraction of the viewport).
- Section scroll length: `sectionVh` in `tokens.ts`.
- Debug flags: `?no3d` forces the static fallback, `?q=high|low` forces quality,
  `?snap` removes pose smoothing.

## Motion and glass
- Every surface is one `<Glass>` component styled by `.glass` in `index.css`.
- `<Reveal>` fades content in (rise + blur) when 25% is in view and lifts it out when it
  leaves upward. `kind="pop"` adds the spring. Stagger siblings with `delay` steps of 0.08-0.12.
- Pinned sections keep their scroll-scrubbed GSAP timelines; the whole stage is wrapped in one `<Reveal>`.
- Phones skip the filter blur and use a 12px backdrop blur. If the 3D performance monitor reports
  a struggling device, `html.lite-glass` swaps the blur for solid Deep Blue.
- Test reduced motion: Chrome DevTools > Rendering > "Emulate CSS media feature
  prefers-reduced-motion: reduce", then reload. You should see opacity-only fades, no rise, blur,
  spring or scale, final numbers shown at once, and no 3D layer.

## Fallbacks
No WebGL, a very low-end device, or `prefers-reduced-motion` skips the 3D layer and
smooth scrolling: the hero shows `hero-last.jpg` and sections render as normal blocks
with simple fade-ins.

ZERO ICE is a fictional brand created for a demo. Statistics, ratings and testimonials are
placeholder demo data. Videos and images are AI-generated.
