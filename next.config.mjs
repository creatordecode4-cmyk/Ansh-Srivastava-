import fs from "node:fs";
import path from "node:path";

// Warn (in the terminal / Vercel build log) if any card preview is too big for phones.
const PREVIEW_DIR = path.join(process.cwd(), "public", "previews");
const MAX_PREVIEW_BYTES = 4 * 1024 * 1024; // 4 MB
try {
  for (const file of fs.readdirSync(PREVIEW_DIR)) {
    if (!/\.(mp4|webm|mov)$/i.test(file)) continue;
    const { size } = fs.statSync(path.join(PREVIEW_DIR, file));
    if (size > MAX_PREVIEW_BYTES) {
      console.warn(
        `⚠️  public/previews/${file} is ${(size / 1024 / 1024).toFixed(1)} MB (limit 4 MB). ` +
          "Re-export it shorter (10-15 sec), 720p, without audio, so the site stays fast on phones."
      );
    }
  }
} catch {
  // no previews folder yet — nothing to check
}

// Warn if a full video is too big (slow to start on mobile data, and heavy for the repo).
const VIDEO_DIR = path.join(process.cwd(), "public", "videos");
const MAX_VIDEO_BYTES = 25 * 1024 * 1024; // 25 MB
try {
  for (const file of fs.readdirSync(VIDEO_DIR)) {
    if (!/\.(mp4|webm|mov)$/i.test(file)) continue;
    const { size } = fs.statSync(path.join(VIDEO_DIR, file));
    if (size > MAX_VIDEO_BYTES) {
      console.warn(
        `⚠️  public/videos/${file} is ${(size / 1024 / 1024).toFixed(1)} MB (limit 25 MB). ` +
          "Compress it (e.g. 720p or 1080p, H.264, CRF 26-28) before adding it to the site."
      );
    }
  }
} catch {
  // no videos folder — nothing to check
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
