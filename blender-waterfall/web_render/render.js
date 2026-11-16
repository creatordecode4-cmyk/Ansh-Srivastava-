// Render frames with headless Chromium (SwiftShader WebGL) and write JPEGs.
// Usage: node render.js <outDir> <start> <end> [step=1] [width=1920] [exposure=1.0]
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [outDir, start, end, step = '1', width = '1920', exp = '1.0'] = process.argv.slice(2);
const W = +width, H = Math.round(W * 9 / 16);
const ROOT = __dirname;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.bin': 'application/octet-stream' };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
(async () => {
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.setDefaultTimeout(0);
  page.on('console', (m) => console.log('[page]', m.text()));
  page.on('pageerror', (e) => console.log('[page error]', e.message));
  const t0 = Date.now();
  await page.goto(`http://127.0.0.1:${port}/index.html?w=${W}&h=${H}&exp=${exp}`);
  await page.waitForFunction('window.READY === true', null, { timeout: 900000 });
  console.log('scene ready in', ((Date.now() - t0) / 1000).toFixed(1), 's');
  for (let f = +start; f <= +end; f += +step) {
    const t1 = Date.now();
    await page.evaluate((fr) => window.renderFrame(fr), f);
    const buf = await page.screenshot({ type: 'jpeg', quality: 95, timeout: 0 });
    fs.writeFileSync(path.join(outDir, `f_${String(f).padStart(4, '0')}.jpg`), buf);
    console.log('frame', f, ((Date.now() - t1) / 1000).toFixed(2), 's');
  }
  await browser.close();
  server.close();
})().catch((e) => { console.error(e); process.exit(1); });
