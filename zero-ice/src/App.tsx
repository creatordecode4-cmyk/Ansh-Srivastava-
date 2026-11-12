import { Suspense, lazy, useEffect, useState } from 'react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { MotionContext, detectMotion } from './lib/motion'
import { initScroll } from './lib/scroll'
import { scrollStore } from './three/scrollStore'
import { Loader } from './components/Loader'
import { Navbar } from './components/Navbar'
import { ProgressBar } from './components/ProgressBar'
import { Hero } from './components/Hero'
import { Marquee } from './components/Marquee'
import { Story } from './components/Story'
import { WhyZero } from './components/WhyZero'
import { Splash } from './components/Splash'
import { Taste } from './components/Taste'
import { Lineup } from './components/Lineup'
import { Nutrition } from './components/Nutrition'
import { TrustStrip } from './components/TrustStrip'
import { Journey } from './components/Journey'
import { Numbers } from './components/Numbers'
import { Recommendations } from './components/Recommendations'
import { LoveIt } from './components/LoveIt'
import { Community } from './components/Community'
import { FinalCTA } from './components/FinalCTA'
import { FAQ } from './components/FAQ'
import { Footer } from './components/Footer'

const Scene = lazy(() => import('./three/Scene'))

const LABEL_FONTS = ['italic 900 100px "Barlow Condensed"', '800 40px "Barlow Condensed"', '700 40px "Barlow Condensed"', '600 40px "Barlow Condensed"']

export default function App() {
  const [motion] = useState(() => {
    scrollStore.isMobile = window.matchMedia('(max-width: 767px)').matches
    return detectMotion()
  })
  const [fonts, setFonts] = useState(false)
  const [poster, setPoster] = useState(false)
  const [scene, setScene] = useState(false)

  // fonts first: the can label is drawn to a canvas with them
  useEffect(() => {
    let alive = true
    const done = () => alive && setFonts(true)
    Promise.all(LABEL_FONTS.map((f) => document.fonts.load(f))).then(done, done)
    const t = window.setTimeout(done, 4000)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [])

  // never let a slow GPU hold the loader forever
  useEffect(() => {
    if (!motion) return
    const t = window.setTimeout(() => setScene(true), 7000)
    return () => clearTimeout(t)
  }, [motion])

  useEffect(() => {
    if (!motion) return
    const stop = initScroll()
    return stop
  }, [motion])

  useEffect(() => {
    if (fonts) ScrollTrigger.refresh()
  }, [fonts])

  const ready = fonts && poster && (!motion || scene)

  return (
    <MotionContext.Provider value={motion}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded focus:bg-cyan focus:px-4 focus:py-2 focus:text-silver">
        Skip to content
      </a>
      <Loader done={ready} />
      <div className="backdrop pointer-events-none fixed inset-0 z-0" aria-hidden="true" />
      {/* the 3D layer mounts only after the hero poster has painted */}
      {motion && fonts && poster && (
        <Suspense fallback={null}>
          <Scene onReady={() => setScene(true)} />
        </Suspense>
      )}
      {motion && <div className="vignette pointer-events-none fixed inset-0 z-[11]" aria-hidden="true" />}
      <ProgressBar />
      <Navbar />
      <main id="main">
        <Hero ready={ready} onPoster={() => setPoster(true)} />
        <Marquee />
        <TrustStrip />
        <Story />
        <Journey />
        <WhyZero />
        <Numbers />
        <Splash />
        <Taste />
        <Lineup />
        <Nutrition />
        <Recommendations />
        <LoveIt />
        <Community />
        <FinalCTA />
        <FAQ />
      </main>
      <Footer />
    </MotionContext.Provider>
  )
}
