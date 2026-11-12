// Headless frame renderer.
//   node render.cjs still [t=1.2] [out/still.png]   -> one approval frame
//   node render.cjs video                           -> out/frames/*.png + out/cozy-desk.mp4
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = __dirname;
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.cjs': 'text/javascript', '.json': 'application/json' };

function serve() {
  const server = http.createServer((req, res) => {
    const file = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\/$/, '/index.html'));
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () => ok(server)));
}

(async () => {
  const [mode = 'still', a1, a2] = process.argv.slice(2);
  const server = await serve();
  const browser = await chromium.launch({
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
  page.on('console', (m) => { if (m.type() !== 'log') console.log(`[page ${m.type()}]`, m.text()); });
  page.on('pageerror', (e) => console.log('[page error]', e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction('window.READY === true', null, { timeout: 120000 });
  const shot = await page.evaluate('window.SHOT');

  const grab = async (t, file) => {
    const url = await page.evaluate((tt) => { window.renderAt(tt); return document.getElementById('c').toDataURL('image/png'); }, t);
    fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64'));
  };

  if (mode === 'still') {
    const out = path.resolve(a2 || path.join(ROOT, 'out', 'still.png'));
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const t0 = Date.now();
    await grab(parseFloat(a1 ?? '1.2'), out);
    console.log(`still t=${a1 ?? 1.2}s -> ${out} (${Date.now() - t0} ms)`);
  } else {
    const dir = path.join(ROOT, 'out', 'frames');
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });
    const total = shot.FPS * shot.DURATION;
    for (let i = 0; i < total; i++) {
      await grab(i / shot.FPS, path.join(dir, `f_${String(i).padStart(4, '0')}.png`));
      if (i % 12 === 0) console.log(`frame ${i + 1}/${total}`);
    }
    const mp4 = path.join(ROOT, 'cozy-desk.mp4');
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(shot.FPS), '-i', path.join(dir, 'f_%04d.png'),
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4], { stdio: 'inherit' });
    console.log('video ->', mp4);
  }
  await browser.close();
  server.close();
})().catch((e) => { console.error(e); process.exit(1); });
