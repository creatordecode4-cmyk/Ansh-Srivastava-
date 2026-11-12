import * as THREE from 'three'
import { brand, variants, type VariantId } from '../tokens'

/** texels are narrower than tall once wrapped on the can, so text is pre-stretched */
const X_FIX = 1 / 0.848
const FONT = '"Barlow Condensed", "Arial Narrow", sans-serif'

function spaced(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, spacing: number) {
  // manual letter-spacing, centred on x
  const widths = [...text].map((c) => ctx.measureText(c).width + spacing)
  let cx = x - (widths.reduce((a, b) => a + b, 0) - spacing) / 2
  ctx.textAlign = 'left'
  ;[...text].forEach((c, i) => {
    ctx.fillText(c, cx, y)
    cx += widths[i]
  })
  ctx.textAlign = 'center'
}

function drawTile(ctx: CanvasRenderingContext2D, ox: number, k: number, v: (typeof variants)[number]) {
  ctx.save()
  ctx.translate(ox, 0)
  ctx.scale(k, k)

  // slanted swoosh band: thick through the middle, tapering round both sides
  ctx.fillStyle = v.band
  ctx.beginPath()
  ctx.moveTo(0, 835)
  ctx.bezierCurveTo(110, 540, 300, 505, 520, 472)
  ctx.bezierCurveTo(740, 440, 910, 400, 1024, 300)
  ctx.bezierCurveTo(1000, 600, 800, 850, 330, 922)
  ctx.bezierCurveTo(190, 942, 60, 905, 0, 835)
  ctx.closePath()
  ctx.fill()

  // thin echo stripes under the band
  ctx.strokeStyle = v.band
  ctx.lineCap = 'round'
  ctx.lineWidth = 15
  ctx.beginPath()
  ctx.moveTo(1018, 452)
  ctx.bezierCurveTo(985, 690, 800, 890, 520, 928)
  ctx.stroke()
  ctx.lineWidth = 5
  ctx.beginPath()
  ctx.moveTo(1018, 560)
  ctx.bezierCurveTo(975, 740, 850, 880, 690, 926)
  ctx.stroke()

  ctx.textAlign = 'center'
  ctx.textBaseline = 'alphabetic'

  // top line
  ctx.save()
  ctx.translate(512, 178)
  ctx.scale(X_FIX, 1)
  ctx.fillStyle = v.band
  ctx.font = `700 25px ${FONT}`
  spaced(ctx, brand.top, 0, 0, 2.5)
  ctx.restore()

  // wordmark
  ctx.save()
  ctx.translate(520, 560)
  ctx.rotate(-0.135)
  ctx.scale(X_FIX, 1)
  ctx.font = `italic 900 216px ${FONT}`
  ctx.fillStyle = v.band
  ctx.fillText('ZERO', -14, -100)
  ctx.fillStyle = '#ffffff'
  ctx.font = `italic 900 226px ${FONT}`
  ctx.fillText('ICE', 52, 96)
  ctx.font = `600 44px ${FONT}`
  spaced(ctx, v.sub, 46, 158, 5)
  ctx.restore()

  // bottom claim
  ctx.save()
  ctx.translate(835, 868)
  ctx.scale(X_FIX, 1)
  ctx.fillStyle = v.band
  ctx.font = `800 27px ${FONT}`
  spaced(ctx, brand.bottom[0], 0, 0, 1.5)
  spaced(ctx, brand.bottom[1], 0, 30, 1.5)
  ctx.restore()

  // barcode on the side
  ctx.fillStyle = '#f4f6f8'
  ctx.fillRect(18, 640, 54, 130)
  ctx.fillStyle = '#0b0c0f'
  for (let y = 647, i = 0; y < 763; i++) {
    const h = [2, 4, 2, 6, 3, 2, 5][i % 7]
    ctx.fillRect(23, y, 44, h)
    y += h + [3, 2, 4, 2][i % 4]
  }
  ctx.restore()
}

/** Label wrap: two copies of the front design so every angle has a face. */
export function makeLabelTexture(id: VariantId, width = 2048): THREE.CanvasTexture {
  const v = variants.find((x) => x.id === id)!
  const W = width
  const H = width / 2
  const k = H / 1024
  const c = document.createElement('canvas')
  c.width = W
  c.height = H
  const ctx = c.getContext('2d')!

  // brushed aluminium base
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, v.base)
  g.addColorStop(0.5, v.base)
  g.addColorStop(1, v.base)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)
  for (let i = 0; i < 2600; i++) {
    ctx.fillStyle = Math.random() > 0.5 ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)'
    ctx.fillRect(Math.random() * W, Math.random() * H, 40 + Math.random() * 260, 1)
  }

  drawTile(ctx, 0, k, v)
  drawTile(ctx, W / 2, k, v)

  // bare metal above and below the print area
  ctx.fillStyle = id === 'original' ? '#dfe4e8' : '#d4d9de'
  ctx.fillRect(0, 0, W, 128 * k)
  ctx.fillRect(0, 936 * k, W, H)

  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.wrapS = THREE.RepeatWrapping
  tex.anisotropy = 8
  tex.needsUpdate = true
  return tex
}

/** Condensation: normal + roughness maps built from random droplet blobs. */
export function makeDropletMaps(width = 1024) {
  const W = width
  const H = width / 2
  const c = document.createElement('canvas')
  c.width = W
  c.height = H
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, W, H)
  const count = Math.round(1100 * (W / 1024) ** 2)
  for (let i = 0; i < count; i++) {
    const big = Math.random() < 0.12
    const r = (big ? 4 + Math.random() * 5 : 1.2 + Math.random() * 2.6) * (W / 1024)
    const x = Math.random() * W
    const y = Math.random() * H
    const sy = big ? 1.15 + Math.random() * 0.4 : 1
    for (const dx of [0, -W, W]) {
      ctx.save()
      ctx.translate(x + dx, y)
      ctx.scale(1, sy)
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r)
      g.addColorStop(0, 'rgba(255,255,255,1)')
      g.addColorStop(0.75, 'rgba(255,255,255,0.75)')
      g.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(0, 0, r, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
  }
  const src = ctx.getImageData(0, 0, W, H).data
  const hgt = (x: number, y: number) => src[(((y + H) % H) * W + ((x + W) % W)) * 4] / 255

  const nImg = ctx.createImageData(W, H)
  const rImg = ctx.createImageData(W, H)
  const strength = 3.2
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const dx = (hgt(x + 1, y) - hgt(x - 1, y)) * strength
      const dy = (hgt(x, y + 1) - hgt(x, y - 1)) * strength
      const len = Math.hypot(dx, dy, 1)
      const i = (y * W + x) * 4
      nImg.data[i] = (-dx / len) * 127.5 + 127.5
      nImg.data[i + 1] = (dy / len) * 127.5 + 127.5
      nImg.data[i + 2] = (1 / len) * 127.5 + 127.5
      nImg.data[i + 3] = 255
      // droplets are glossy, the brushed metal is rougher (with a little grain)
      const rough = hgt(x, y) > 0.2 ? 0.06 : 0.3 + Math.random() * 0.06
      rImg.data[i] = rImg.data[i + 1] = rImg.data[i + 2] = rough * 255
      rImg.data[i + 3] = 255
    }
  }
  const toTex = (img: ImageData) => {
    const cc = document.createElement('canvas')
    cc.width = W
    cc.height = H
    cc.getContext('2d')!.putImageData(img, 0, 0)
    const t = new THREE.CanvasTexture(cc)
    t.wrapS = THREE.RepeatWrapping
    t.anisotropy = 4
    return t
  }
  return { normalMap: toTex(nImg), roughnessMap: toTex(rImg) }
}

/** Soft radial puff used for the mist sprites. */
export function makeMistTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const ctx = c.getContext('2d')!
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
  g.addColorStop(0, 'rgba(255,255,255,0.9)')
  g.addColorStop(0.4, 'rgba(255,255,255,0.35)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 128, 128)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

/** Lumpy normal map that breaks up reflections on the ice cubes. */
export function makeFrostNormal(size = 256) {
  const c = document.createElement('canvas')
  c.width = c.height = size
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#808080'
  ctx.fillRect(0, 0, size, size)
  for (let i = 0; i < 90; i++) {
    const r = 8 + Math.random() * 40
    const x = Math.random() * size
    const y = Math.random() * size
    const light = Math.random() > 0.5
    for (const dx of [0, -size, size])
      for (const dy of [0, -size, size]) {
        const g = ctx.createRadialGradient(x + dx, y + dy, 0, x + dx, y + dy, r)
        g.addColorStop(0, light ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)')
        g.addColorStop(1, 'rgba(128,128,128,0)')
        ctx.fillStyle = g
        ctx.fillRect(x + dx - r, y + dy - r, r * 2, r * 2)
      }
  }
  const src = ctx.getImageData(0, 0, size, size).data
  const h = (x: number, y: number) => src[(((y + size) % size) * size + ((x + size) % size)) * 4] / 255
  const img = ctx.createImageData(size, size)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const dx = (h(x + 1, y) - h(x - 1, y)) * 6
      const dy = (h(x, y + 1) - h(x, y - 1)) * 6
      const len = Math.hypot(dx, dy, 1)
      const i = (y * size + x) * 4
      img.data[i] = (-dx / len) * 127.5 + 127.5
      img.data[i + 1] = (dy / len) * 127.5 + 127.5
      img.data[i + 2] = (1 / len) * 127.5 + 127.5
      img.data[i + 3] = 255
    }
  ctx.putImageData(img, 0, 0)
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  return t
}
