# Video Editor Portfolio (Next.js + Tailwind)

Dark, metallic portfolio for a video editor who also does web design/dev and uses AI tools.

## Edit your content
Everything lives in **`data/site.js`**: name, videos, stats, email, socials and the Web3Forms key.
To change the photo, overwrite `public/profile.jpg` (keep the same file name).

## Run locally
```bash
npm install
npm run dev     # open http://localhost:3000
```

## Deploy (Vercel, free)
Push to GitHub → vercel.com → Add New Project → import this repo → Deploy.
Every new push to the connected branch redeploys automatically.

## Folder structure
```
app/           layout.js (fonts + SEO), page.js (section order), globals.css (theme)
components/    Navbar, Hero, Stats, Work, VideoModal, Capabilities, Process, About, Contact, Footer, Icons
data/site.js   ALL editable content
lib/video.js   YouTube / Google Drive link → embed URL
public/        profile.jpg (+ add /thumbs/ for custom thumbnails)
```
