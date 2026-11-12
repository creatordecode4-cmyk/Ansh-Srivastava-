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
 * How the timing works: the page runs on a recording clock (rAF, performance.now, Date.now, timers,
 * videos, CSS animations). It runs SLOWMO times slower than real time and never advances by more than
 * one video frame (1/30 s) per rendered frame, so a slow frame can never skip time. Every rendered frame
 * is logged (real time -> page time) and the raw Playwright recording is retimed from that log, so the
 * final video plays at normal speed with no freezes, however slowly the machine rendered it.
 *
 * SLOWMO: headless Chromium without a GPU renders WebGL on the CPU at a few frames per second; SLOWMO=12
 * gives it time to produce enough frames. With a real GPU leave it at 1.
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
const FPS = 30
/** frame rate of Playwright's raw recording */
const RAW_FPS = 25

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

/** Recording clock. Runs in the page before any site code. */
function pageClock({ k, frameMs }) {
  const pn = performance.now.bind(performance)
  const dn = Date.now.bind(Date)
  const d0 = dn()
  let virt = 0
  let lastReal = pn()
  let stamp = -1
  /** flat list: real epoch ms, page ms, real epoch ms, page ms, ... one pair per rendered frame */
  const frames = []
  window.__clock = { frames, now: () => virt }
  const advance = (t) => {
    if (t === stamp) return
    stamp = t
    const real = pn()
    virt += Math.min((real - lastReal) / k, frameMs)
    lastReal = real
    frames.push(dn(), virt)
  }
  performance.now = () => virt
  Date.now = () => d0 + virt
  const raf = window.requestAnimationFrame.bind(window)
  window.requestAnimationFrame = (cb) =>
    raf((t) => {
      advance(t)
      cb(virt)
    })
  // keep the clock ticking even when the page is not asking for frames
  const keep = (t) => {
    advance(t)
    raf(keep)
  }
  raf(keep)
  const st = window.setTimeout.bind(window)
  const si = window.setInterval.bind(window)
  window.setTimeout = (fn, d, ...a) => st(fn, (d || 0) * k, ...a)
  window.setInterval = (fn, d, ...a) => si(fn, (d || 0) * k, ...a)
  if (k === 1) return
  // videos + CSS animations/transitions follow the slow clock
  si(() => {
    document.querySelectorAll('video').forEach((v) => {
      if (v.playbackRate !== 1 / k) v.playbackRate = 1 / k
    })
    document.getAnimations().forEach((a) => {
      if (a.playbackRate !== 1 / k) a.playbackRate = 1 / k
    })
  }, 50)
}

/**
 * Rebuilds the video from the raw recording: for every output frame, take the raw frame that was on
 * screen at that page time. `wanted` is a sorted list of raw frame numbers, one per output frame.
 */
async function retime(webm, wanted, mp4) {
  const frameBytes = SIZE.width * SIZE.height * 1.5
  const dec = spawn('ffmpeg', ['-v', 'error', '-i', webm, '-vf', `scale=${SIZE.width}:${SIZE.height}`, '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'], { stdio: ['ignore', 'pipe', 'ignore'] })
  const enc = spawn(
    'ffmpeg',
    ['-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-s', `${SIZE.width}x${SIZE.height}`, '-r', String(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4],
    { stdio: ['pipe', 'inherit', 'inherit'] },
  )
  const encDone = new Promise((res, rej) => enc.on('exit', (code) => (code === 0 ? res() : rej(new Error(`ffmpeg encoder exited with ${code}`)))))
  const write = (buf) => new Promise((res) => (enc.stdin.write(buf) ? res() : enc.stdin.once('drain', res)))
  let frame = Buffer.allocUnsafe(frameBytes)
  let fill = 0
  let index = 0
  let next = 0
  let written = 0
  let last = null
  for await (const chunk of dec.stdout) {
    let off = 0
    while (off < chunk.length && next < wanted.length) {
      const n = Math.min(frameBytes - fill, chunk.length - off)
      chunk.copy(frame, fill, off, off + n)
      fill += n
      off += n
      if (fill < frameBytes) continue
      fill = 0
      if (wanted[next] === index) {
        last = frame
        frame = Buffer.allocUnsafe(frameBytes)
        while (next < wanted.length && wanted[next] === index) {
          await write(last)
          next++
          written++
        }
      }
      index++
    }
    if (next >= wanted.length) break
  }
  dec.kill()
  // the recording ended before the last requested frames: hold the final frame
  while (last && next < wanted.length) {
    await write(last)
    next++
    written++
  }
  enc.stdin.end()
  await encDone
  return { written, rawFramesRead: index }
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
    await context.addInitScript(pageClock, { k: K, frameMs: 1000 / FPS })
    const page = await context.newPage()
    const t0 = Date.now()
    page.on('pageerror', (e) => log('page error:', e.message))

    /** page time in ms (the recording clock) */
    const now = () => page.evaluate(() => window.__clock.now())
    /** wait in page time */
    const wait = async (ms) => {
      const end = (await now()) + ms
      while ((await now()) < end) await page.waitForTimeout(100)
    }
    /** parts of the raw recording that go into the final video: { frames, from, to } in page time */
    const segments = []
    const keep = async (from) => segments.push({ frames: await page.evaluate(() => window.__clock.frames), from, to: await now() })
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
    /** constant-speed scroll between two offsets, driven by page time: one position per rendered frame */
    const glide = async (from, to, seconds) => {
      const start = await now()
      for (;;) {
        const t = await page.evaluate(
          ([a, b, t0, ms]) => {
            const k = Math.min((window.__clock.now() - t0) / ms, 1)
            window.scrollTo(0, a + (b - a) * k)
            return k
          },
          [from, to, start, seconds * 1000],
        )
        if (t >= 1) break
        await page.waitForTimeout(40)
      }
    }

    // 1. the site: hero
    step = 'open the site'
    await page.goto(`${BASE}/${QUERY}`, { waitUntil: 'load' })
    await page.waitForSelector('#gl canvas', { state: 'attached', timeout: 120000 * K })
    // the loader unmounts once fonts, hero poster and the 3D scene are ready
    await page.waitForFunction(() => !document.querySelector('[role="status"]'), null, { timeout: 120000 * K })
    await glCheck('site')

    // warm-up (cut from the final video): the first time each 3D object is drawn the renderer compiles
    // its shaders, which can freeze the page for a long time on a CPU renderer. Visit every part of the
    // page once so the recorded scroll never hits that freeze.
    step = 'warm up the 3D scene'
    const settle = (n = 3) =>
      page.evaluate((count) => new Promise((done) => {
        let i = 0
        const f = () => (++i >= count ? done() : requestAnimationFrame(f))
        requestAnimationFrame(f)
      }), n)
    const marks = await page.evaluate(() => {
      const out = []
      for (const el of [...document.querySelectorAll('main > *'), document.querySelector('footer')].filter(Boolean)) {
        const top = el.getBoundingClientRect().top + window.scrollY
        for (const f of [0, 0.25, 0.5, 0.75]) out.push(Math.round(top + el.offsetHeight * f))
      }
      return out
    })
    for (const m of marks) {
      await scrollTo(m)
      await settle()
    }
    await scrollTo(0)
    await settle(6)
    log(`warm-up done (${marks.length} positions)`)

    // replay the hero intro so the recording opens on it
    step = 'replay the hero intro'
    const replay = page.getByRole('button', { name: /replay/i })
    // the button only becomes active once the intro video has ended; other layers overlap it, so click through the DOM
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => /replay/i.test(b.textContent) && b.tabIndex === 0), null, { timeout: 60000 * K })
    await replay.evaluate((el) => el.click())
    // the 8 s intro runs on the page clock: join it for its last 3 seconds, so the scroll starts as it lands
    await page.waitForFunction(() => { const v = document.querySelector('#hero video') || document.querySelector('video'); return v && (v.ended || v.currentTime >= v.duration - 3.2) }, null, { timeout: 60000 * K })
    const heroFrom = await now()
    step = 'hero: wait 3 seconds'
    await page.mouse.move(720, 520)
    await wait(3000)
    await page.waitForFunction(() => { const v = document.querySelector('#hero video') || document.querySelector('video'); return v && v.ended }, null, { timeout: 60000 * K })
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
        await glide(y, y + 40, 0.3)
        y += 40
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

    await keep(heroFrom)

    // 4. the laptop
    step = 'open /showcase'
    await page.goto(`${BASE}/showcase${QUERY}`, { waitUntil: 'load' })
    await page.waitForSelector('canvas', { timeout: 60000 * K })
    await page.mouse.move(720, 620)
    await glCheck('/showcase')
    await page.evaluate(() => new Promise((done) => { let i = 0; const f = () => (++i >= 4 ? done() : requestAnimationFrame(f)); requestAnimationFrame(f) }))
    await wait(300)
    const showcaseFrom = await now()
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

    await keep(showcaseFrom)

    step = 'save the recording'
    const video = page.video()
    await context.close()
    const tEnd = Date.now()
    const webm = await video.path()
    await browser.close()
    browser = null
    const rawSeconds = Number(spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', webm], { encoding: 'utf8' }).stdout)
    log('raw recording:', webm, `${(fs.statSync(webm).size / 1e6).toFixed(1)} MB, ${rawSeconds.toFixed(0)} s (wall clock ${((tEnd - t0) / 1000).toFixed(0)} s)`)

    // 5. webm -> mp4 (H.264, crf 20, 1440x900), retimed from the frame log
    step = 'ffmpeg: webm → mp4'
    const mp4 = path.join(OUT, 'zero-ice-showcase.mp4')
    const wanted = []
    for (const seg of segments) {
      let i = 0
      for (let v = seg.from; v < seg.to; v += 1000 / FPS) {
        // first rendered frame after page time v: the frame for v is on screen right up to that moment
        while (i < seg.frames.length - 2 && seg.frames[i + 1] <= v) i += 2
        const raw = Math.max(0, Math.round(((seg.frames[i] - t0) / 1000) * RAW_FPS))
        wanted.push(Math.max(raw, wanted.length ? wanted[wanted.length - 1] : 0))
      }
    }
    log(step, `${wanted.length} frames from ${segments.length} segments`)
    const res = await retime(webm, wanted, mp4)
    log(`wrote ${res.written} frames (read ${res.rawFramesRead} raw frames)`)

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
