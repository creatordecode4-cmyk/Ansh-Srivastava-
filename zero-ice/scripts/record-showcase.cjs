/**
 * Records the ZERO ICE site + the /showcase laptop scene to showcase/zero-ice-showcase.mp4
 * and saves three 2x stills (hero, mid-section, showcase).
 *
 *   node scripts/record-showcase.cjs            build, serve on :4173, record, convert
 *   SLOWMO=8 node scripts/record-showcase.cjs   for machines without a GPU (see below)
 *   NO_SERVE=1 ...                              reuse a preview server that is already running
 *   CANVAS_DPR=1 ...                            pin the WebGL canvas pixel ratio (default 1 when SLOWMO > 1)
 *   USE_GL=swiftshader ...                      add --use-gl=swiftshader if the 3D scene is blank
 *
 * SLOWMO: headless Chromium without a GPU renders WebGL on the CPU at a few frames per second.
 * SLOWMO=n runs the page clock n times slower (rAF, timers, videos, CSS animations), records n times
 * longer, and ffmpeg speeds the result back up, so the final video plays in real time and stays smooth.
 * With a real GPU leave it at 1.
 */
const { chromium } = require('playwright')
const { spawn, spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'showcase')
const RAW = path.join(OUT, '.raw')
const PORT = 4173
const BASE = `http://localhost:${PORT}`
const SIZE = { width: 1440, height: 900 }
const K = Math.max(1, Number(process.env.SLOWMO) || 1)
/** canvas pixel ratio for the 3D layers; defaults to 1 in slow motion (CPU rendering), native otherwise */
const CANVAS_DPR = process.env.CANVAS_DPR || (K > 1 ? '1' : '')
const QUERY = CANVAS_DPR ? `?dpr=${CANVAS_DPR}` : ''
const SECTION_SECONDS = 1.5
const STEP_MS = 1000 / 30

const log = (...a) => console.log(`[record ${new Date().toISOString().slice(11, 19)}]`, ...a)
const fail = (step, err) => {
  console.error(`\nFAILED at step "${step}":\n${err && err.stack ? err.stack : err}`)
  process.exitCode = 1
}

function run(step, cmd, args) {
  log(step, '→', cmd, args.join(' '))
  const r = spawnSync(cmd, args, { cwd: ROOT, stdio: ['ignore', 'inherit', 'inherit'] })
  if (r.status !== 0) throw new Error(`${cmd} exited with ${r.status ?? r.signal}`)
}

async function waitForServer(ms = 30000) {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    try {
      const r = await fetch(BASE)
      if (r.ok) return
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  throw new Error(`preview server did not answer on ${BASE} within ${ms} ms`)
}

/** Slows the page clock down by k. Runs in the page before any site code. */
function dilate(k) {
  if (k === 1) return
  const pn = performance.now.bind(performance)
  const dn = Date.now.bind(Date)
  const d0 = dn()
  performance.now = () => pn() / k
  Date.now = () => d0 + (dn() - d0) / k
  const raf = window.requestAnimationFrame.bind(window)
  window.requestAnimationFrame = (cb) => raf((t) => cb(t / k))
  const st = window.setTimeout.bind(window)
  const si = window.setInterval.bind(window)
  window.setTimeout = (fn, d, ...a) => st(fn, (d || 0) * k, ...a)
  window.setInterval = (fn, d, ...a) => si(fn, (d || 0) * k, ...a)
  // videos + CSS animations/transitions follow the same clock
  si(() => {
    document.querySelectorAll('video').forEach((v) => {
      if (v.playbackRate !== 1 / k) v.playbackRate = 1 / k
    })
    document.getAnimations().forEach((a) => {
      if (a.playbackRate !== 1 / k) a.playbackRate = 1 / k
    })
  }, 50)
}

async function main() {
  let step = 'setup'
  let server = null
  let browser = null
  try {
    fs.mkdirSync(OUT, { recursive: true })
    fs.rmSync(RAW, { recursive: true, force: true })

    if (!process.env.NO_SERVE) {
      step = 'npm run build'
      run(step, 'npm', ['run', 'build'])
      step = `npm run preview -- --port ${PORT}`
      log(step)
      server = spawn('npm', ['run', 'preview', '--', '--port', String(PORT), '--strictPort'], { cwd: ROOT, stdio: 'ignore', detached: true })
    }
    step = 'wait for preview server'
    await waitForServer()

    step = 'launch chromium'
    const args = process.env.USE_GL ? [`--use-gl=${process.env.USE_GL}`] : []
    browser = await chromium.launch({ args })
    const context = await browser.newContext({ viewport: SIZE, deviceScaleFactor: 2, recordVideo: { dir: RAW, size: SIZE } })
    await context.addInitScript(dilate, K)
    const page = await context.newPage()
    const t0 = Date.now()
    page.on('pageerror', (e) => log('page error:', e.message))

    /** wait in page time (K times longer on the wall clock) */
    const wait = (ms) => page.waitForTimeout(ms * K)
    const still = async (name) => {
      const file = path.join(OUT, name)
      await page.screenshot({ path: file, scale: 'device' })
      log('still', name)
      return file
    }
    /** a blank WebGL canvas means the 3D scene did not render */
    const glCheck = async (label) => {
      const info = await page.evaluate(() => {
        const c = document.querySelector('canvas')
        if (!c) return { canvas: false }
        const gl = c.getContext('webgl2') || c.getContext('webgl')
        const ext = gl && gl.getExtension('WEBGL_debug_renderer_info')
        return { canvas: true, lost: !gl || gl.isContextLost(), renderer: gl && ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown' }
      })
      log(`${label}: 3D canvas`, JSON.stringify(info))
      if (!info.canvas || info.lost) throw new Error(`3D scene is blank on ${label} (${JSON.stringify(info)}). Re-run with USE_GL=swiftshader.`)
    }
    const scrollTo = (y) => page.evaluate((v) => window.scrollTo(0, v), y)
    /** constant-speed scroll between two offsets, driven by the clock so slow frames cannot stretch it */
    const glide = async (from, to, seconds) => {
      const total = seconds * 1000 * K
      const start = Date.now()
      for (;;) {
        const t = Math.min((Date.now() - start) / total, 1)
        await scrollTo(from + (to - from) * t)
        if (t >= 1) break
        await page.waitForTimeout(Math.min(STEP_MS * K, 120))
      }
    }

    // 1. the site: hero
    step = 'open the site'
    await page.goto(`${BASE}/${QUERY}`, { waitUntil: 'load' })
    await page.waitForSelector('#gl canvas', { state: 'attached', timeout: 120000 * K })
    // the loader unmounts once fonts, hero poster and the 3D scene are ready
    await page.waitForFunction(() => !document.querySelector('[role="status"]'), null, { timeout: 120000 * K })
    await glCheck('site')
    const heroAt = (Date.now() - t0) / 1000
    step = 'hero: wait 3 seconds'
    await page.mouse.move(720, 520)
    await wait(3000)
    const stills = [await still('still-01-hero.png')]

    // 2. scroll through every section, ~1.5 s each
    step = 'scroll through the sections'
    const sections = await page.evaluate(() => {
      const els = [...document.querySelectorAll('main > *'), document.querySelector('footer')].filter(Boolean)
      return els.map((el) => ({ id: el.id || el.tagName.toLowerCase(), top: Math.round(el.getBoundingClientRect().top + window.scrollY) }))
    })
    const maxY = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
    log(`${sections.length} sections, page height ${maxY + SIZE.height}px`)
    let y = 0
    for (let i = 0; i < sections.length; i++) {
      const next = Math.min(i + 1 < sections.length ? sections[i + 1].top : maxY, maxY)
      if (next > y) await glide(y, next, SECTION_SECONDS)
      y = Math.max(y, next)
      const arrived = sections[i + 1] && sections[i + 1].id

      if (arrived === 'numbers') {
        // mid-section still: the stats block with its "Demo numbers" tag
        step = 'mid-section still'
        await glide(y, y + 140, 0.4)
        y += 140
        await wait(2400)
        const tag = await page.getByText('Demo numbers').first().isVisible().catch(() => false)
        log('"Demo numbers" tag visible in the mid-section frame:', tag)
        if (!tag) throw new Error('"Demo numbers" tag is not visible in the mid-section frame')
        stills.push(await still('still-02-mid-section.png'))
        step = 'scroll through the sections'
      }
      if (arrived === 'love') {
        // 3a. hover one card
        step = 'hover a card'
        await glide(y, y + 260, 0.5)
        y += 260
        await wait(500)
        const card = page.locator('#love article').nth(1)
        await card.hover({ timeout: 15000 * K })
        await wait(1300)
        step = 'scroll through the sections'
      }
    }
    await wait(900)
    const disclaimer = await page.getByText('ZERO ICE is a fictional brand created for a demo').isVisible()
    log('footer "fictional brand" disclaimer visible at the end of the scroll:', disclaimer)
    if (!disclaimer) throw new Error('"fictional brand" disclaimer is not visible in the footer frame')

    // 3b. hover the Buy Now button (the nav one is always on screen)
    step = 'hover Buy Now'
    const buy = page.locator('header, nav').getByText('Buy Now', { exact: true }).first()
    const box = await buy.boundingBox()
    if (!box) throw new Error('Buy Now button not found in the navbar')
    await page.mouse.move(box.x + box.width / 2 - 260, box.y + 160, { steps: 4 })
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 })
    await wait(1400)

    // 4. the laptop
    step = 'open /showcase'
    await page.goto(`${BASE}/showcase${QUERY}`, { waitUntil: 'load' })
    await page.waitForSelector('canvas', { timeout: 60000 * K })
    await page.mouse.move(720, 620)
    await glCheck('/showcase')
    await wait(2200)
    step = 'showcase: scroll (open + orbit + zoom)'
    const runway = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
    await glide(0, runway * 0.5, 6.5)
    await wait(1000)
    stills.push(await still('still-03-showcase.png'))
    await glide(runway * 0.5, runway * 0.78, 4)
    await wait(1400)
    await glide(runway * 0.78, runway, 3.5)
    await wait(2200)
    const note = await page.getByText('fictional brands created for a demo').isVisible()
    log('showcase "fictional brands" disclaimer visible:', note)

    step = 'save the recording'
    const video = page.video()
    await context.close()
    const webm = await video.path()
    await browser.close()
    browser = null
    log('raw recording:', webm, `${(fs.statSync(webm).size / 1e6).toFixed(1)} MB`)

    // 5. webm -> mp4 (H.264, crf 20, 1440x900); drop the loading screen, undo the slow motion
    step = 'ffmpeg: webm → mp4'
    const mp4 = path.join(OUT, 'zero-ice-showcase.mp4')
    const vf = [K > 1 ? `setpts=(PTS-STARTPTS)/${K}` : null, `scale=${SIZE.width}:${SIZE.height}:flags=lanczos`, 'fps=30', 'format=yuv420p'].filter(Boolean).join(',')
    run(step, 'ffmpeg', ['-y', '-v', 'error', '-ss', heroAt.toFixed(2), '-i', webm, '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-movflags', '+faststart', mp4])

    step = 'ffprobe: length'
    const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4], { encoding: 'utf8' })
    if (probe.status !== 0) throw new Error(probe.stderr)
    fs.rmSync(RAW, { recursive: true, force: true })
    console.log('\nDone.')
    console.log('video :', mp4)
    stills.forEach((s) => console.log('still :', s))
    console.log('length:', `${Number(probe.stdout).toFixed(1)} s`)
  } catch (err) {
    fail(step, err)
  } finally {
    if (browser) await browser.close().catch(() => {})
    if (server) {
      try {
        process.kill(-server.pid)
      } catch {
        /* already gone */
      }
    }
  }
}

main()
