// =====================================================================
//  YOUR WEBSITE CONTENT — EDIT ONLY THIS FILE
//  Sab kuch (naam, videos, links, stats) yahin se change hota hai.
//  Components ko touch karne ki zaroorat nahi hai.
//  Rule: text ko hamesha "quotes" ke andar rakho, aur har item ke baad comma (,) lagao.
// =====================================================================

// ---------- YOUR EMAIL (used everywhere: Email Me, Gmail, Copy, footer, social icon) ----------
const EMAIL = "anshsrivastavaedit3@gmail.com"; //          <-- change it here only
const EMAIL_SUBJECT = "Video editing project enquiry"; // subject for Email Me / Gmail

export const site = {
  // ---------- BASIC INFO ----------
  name: "Ansh Srivastava",
  initials: "AS",
  role: "Video Editor",
  // Your live address, used for Google / WhatsApp link previews.
  // On Vercel it is filled in automatically; set NEXT_PUBLIC_SITE_URL in Vercel to use a custom domain.
  url:
    process.env.NEXT_PUBLIC_SITE_URL ||
    (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000"),

  // SEO (Google search + WhatsApp/Instagram link previews)
  seo: {
    title: "Ansh Srivastava — Video Editor",
    description:
      "Video editor for documentaries, motion graphics, shorts and ads. I also design and build websites with React, Next.js and AI tools.", // <-- EDIT
  },

  // ---------- HERO ----------
  hero: {
    label: "Stories that move people",
    heading: ["Video", "Editor"], // big heading, one word per line
    subtext:
      "I edit engaging videos — documentaries, motion graphics, shorts and ads — and build websites using modern web tech and AI.",
    photo: "/profile.jpg", // to change the photo, overwrite public/profile.jpg (same name)
    photoAlt: "Ansh Srivastava, video editor",
    badgeTop: "Available for",
    badgeMain: "Freelance",
    badgeBottom: "Projects",
  },

  // ---------- STATS (honest numbers only) ----------
  stats: [
    { value: "5+", label: "Years Editing", icon: "sparkle" },
    { value: "3", label: "Skills: Editing · Web · AI", icon: "layers" },
    { value: "Mobile", label: "First Workflow", icon: "phone" },
    { value: "Open", label: "To First Clients", icon: "globe" },
  ],

  // ---------- WORK / VIDEOS ----------
  // category: any name, e.g. "Motion Graphics", "Documentary", "Others".
  //   Filter tabs are built automatically: a tab only appears if it has at least one video.
  // videoUrl supports:
  //   YouTube:  https://www.youtube.com/watch?v=XXXX  or  https://youtu.be/XXXX  or  /shorts/XXXX
  //   Google Drive: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
  //     (Drive file ko "Anyone with the link → Viewer" share karna zaroori hai)
  //   Your own file: put the .mp4 in /public/videos/ and write "/videos/my-video.mp4"
  // orientation: "horizontal" (16:9, default) or "vertical" (9:16 shorts/reels)
  // short: 1 line shown on the card · description: full text shown under the player
  // credit: OPTIONAL small credit line (card + under the player). A credit starting with
  //   "Re-edit" also shows a small "Re-edit" tag on the card.
  // Full videos in /public/videos/ are NEVER loaded on the card — only when the video is opened
  //   (cards autoplay only a short "preview" clip, if you add one).
  // preview: OPTIONAL short silent clip that autoplays on the card while you scroll,
  //   e.g. "/previews/my-video.mp4" (put the file in /public/previews/, 10-15 sec, 720p, under 4 MB).
  //   The full video (videoUrl — Drive, YouTube or .mp4) still opens with sound when the card is tapped.
  //   No preview → the card shows the thumbnail (+ a Play button for Drive).
  // thumbnail: optional. Leave "" for YouTube = auto thumbnail.
  //   Your own image: put it in /public/thumbs/ and write "/thumbs/my-image.jpg"
  videos: [
    {
      title: "Edited with Claude — Hinglish Motion Video",
      category: "Motion Graphics",
      orientation: "horizontal",
      short: "Hinglish face-cam video with motion graphics, 100% edited with Claude.",
      description:
        "A Hinglish face-cam video packed with motion graphics: animated UI cards, percentage counters, a 3D mic, toggles and kinetic captions about making AI edits that don't feel AI-made. 100% edited with Claude, as shown in the video.",
      credit: "Own edit. Edited with Claude.",
      videoUrl: "/videos/claude-edit.mp4",
      thumbnail: "/posters/claude-edit.jpg",
    },
    {
      title: "Orbit — AI App Promo",
      category: "Motion Graphics",
      orientation: "horizontal",
      short: "Motion-graphics promo for an AI app called Orbit.",
      description:
        "A 40-second motion-graphics promo for an AI app called Orbit, showing it answer questions, reply by voice in Hindi and English, and run deep research. Dark, glossy and smooth, with soft 3D icons and clean UI animations.",
      videoUrl: "/videos/orbit-promo.mp4",
      preview: "/previews/orbit.mp4",
      thumbnail: "/thumbs/orbit-promo.jpg",
    },
    {
      title: "Ember — AI Assistant Promo",
      category: "Motion Graphics",
      orientation: "horizontal",
      short: "Warm, cinematic promo for an AI assistant called Ember.",
      description:
        "A 30-second motion-graphics promo for an AI assistant called Ember, following a Diwali launch plan from idea to research to code. Warm amber tones and cinematic camera moves give it a premium, glowing feel.",
      videoUrl: "/videos/ember-promo.mp4",
      preview: "/previews/ember.mp4",
      thumbnail: "/thumbs/ember-promo.jpg",
    },
    {
      title: "Wispr Flow — Unofficial Spec Ad",
      category: "Motion Graphics",
      orientation: "horizontal",
      short: "Spec ad for a voice-typing app, made as a practice project.",
      description:
        "An unofficial 30-second spec ad for the voice-typing app Wispr Flow, showing spoken words turning into clean, edited text. Bright, minimal and smooth, with floating 3D shapes and crisp kinetic typography.",
      videoUrl: "/videos/wispr-flow-spec-ad.mp4",
      preview: "/previews/wispr-flow.mp4",
      thumbnail: "/thumbs/wispr-flow-spec-ad.jpg",
    },
    {
      title: "AI Agents Explained — Hinglish Reel",
      category: "Motion Graphics",
      orientation: "vertical",
      short: "Hinglish tech explainer reel with animated captions.",
      description:
        "A 90-second Hinglish talking-head reel explaining what an AI agent is and how people use it for AI automation, custom bots and lead generation. Fast-paced and clean, with animated captions, pop-up UI cards and soft pastel backgrounds.",
      videoUrl: "/videos/ai-agent-reel.mp4",
      preview: "/previews/ai-agent-reel.mp4",
      thumbnail: "/thumbs/ai-agent-reel.jpg",
    },
    {
      title: "2D Animation Story: Re-edit",
      category: "2D Animation",
      orientation: "vertical",
      description:
        "A vertical story video mixing live-action clips with 2D cartoon-style scenes. My re-edit: pacing, scene transitions and captions. Original concept by @Abhay.create.",
      credit: "Re-edit. Original: @Abhay.create",
      videoUrl: "/videos/2d-animation.mp4",
      thumbnail: "/posters/2d-animation.jpg",
    },
    {
      title: "2D Animation Story #2: Re-edit",
      category: "2D Animation",
      orientation: "vertical",
      description:
        "A vertical story video mixing face-cam clips with 2D cartoon-style scenes: a studio stage, colourful street scenes, an office and money and growth graphics. My re-edit: pacing, scene transitions and captions. Original concept by @Abhay.create.",
      credit: "Re-edit. Original: @Abhay.create",
      videoUrl: "/videos/2d-animation-2.mp4",
      thumbnail: "/posters/2d-animation-2.jpg",
    },
    {
      title: "SaaS Product Launch Motion",
      category: "Motion Graphics",
      orientation: "horizontal",
      description:
        "A dark, cinematic product-launch motion piece with 3D object reveals, UI screen animations and kinetic text. Style study inspired by modern AI product ads.",
      credit: "Own edit. Unofficial spec ad for Google Gemini, not affiliated.",
      videoUrl: "/videos/saas-motion.mp4",
      thumbnail: "/posters/saas-motion.jpg",
    },
    {
      title: "Velvo Chocolate Cola — 3D Product Ad",
      category: "3D Animation",
      orientation: "horizontal",
      short: "3D product ad for a chocolate cola: bottle reveal, liquid chocolate and fizz.",
      description:
        "A 30-second 3D product ad for a chocolate cola called Velvo: a dark bottle reveal, flowing liquid chocolate, falling cocoa beans and rising bubbles, ending on the logo. Warm, premium and cinematic, with smooth camera moves and elegant text.",
      credit: "Own 3D animation. Concept ad, not a client project.",
      videoUrl: "/videos/3d-chocolate-ad.mp4",
      thumbnail: "/posters/3d-chocolate-ad.jpg",
    },
    {
      title: "Desert Car Chase — 3D Animation",
      category: "3D Animation",
      orientation: "horizontal",
      short: "3D car chase: a red sports car and a police car on a desert highway.",
      description:
        "A 20-second 3D animated car chase: a red sports car speeds down a desert highway with a police car close behind. Fast and dramatic, with low tracking shots, side angles and a film-grain look.",
      credit: "Own 3D animation.",
      videoUrl: "/videos/3d-car-chase.mp4",
      thumbnail: "/posters/3d-car-chase.jpg",
    },
  ],

  // ---------- WEB PROJECTS ----------
  // url: your live site (https:// is added automatically if missing)
  // description: 1 short line about what the site is (leave "" to hide)
  // screenshot: OPTIONAL image in /public/sites/, e.g. "/sites/kaashi-weaves.jpg"
  //   (shown on the card, and in the viewer if the site can't be embedded)
  websites: [
    {
      title: "Clothes Web",
      url: "https://kaashi-weaves.vercel.app",
      description: "", // <-- EDIT: 1 line about what the site is
      screenshot: "",
    },
    {
      title: "3D Showcase",
      url: "https://ansh-3d-showcase.vercel.app",
      description: "", // <-- EDIT: 1 line about what the site is
      screenshot: "",
    },
    {
      title: "Arum",
      url: "https://ansh-cloth.vercel.app",
      description: "", // <-- EDIT: 1 line about what the site is
      screenshot: "",
    },
  ],

  // ---------- CAPABILITIES ----------
  capabilities: [
    { title: "Video Editing", text: "Clean, engaging edits for YouTube, documentaries, shorts and ads.", icon: "film" },
    { title: "Motion Graphics & Keyframes", text: "Animated text, smooth keyframes and transitions that guide the eye.", icon: "motion" },
    { title: "Storytelling & Pacing", text: "Strong hooks and rhythm that keep viewers watching till the end.", icon: "story" },
    { title: "Sound Design & Colour Grading", text: "Music, SFX and colour that set the right mood.", icon: "sound" },
    { title: "Web Design", text: "Modern, responsive layouts that look great on every phone.", icon: "monitor" },
    { title: "Web Development", text: "Fast websites built with React and Next.js, deployed on Vercel.", icon: "code" },
    { title: "AI-assisted Workflows", text: "Using AI tools to research, script and edit faster without losing quality.", icon: "ai" },
  ],

  // ---------- TOOLS ----------
  // short = 1–2 letters shown in the icon box
  tools: [
    { name: "Alight Motion", short: "Am" },
    { name: "React", short: "Re" },
    { name: "Next.js", short: "N" },
    { name: "Tailwind CSS", short: "Tw" },
    { name: "Vercel", short: "▲" },
    { name: "AI Tools", short: "AI" },
  ],

  // ---------- PROCESS ----------
  process: [
    { title: "Understand", text: "Goals, audience and the story you want to tell.", icon: "search" },
    { title: "Script / Plan", text: "Hook, structure, shot list and references.", icon: "target" },
    { title: "Edit", text: "Cutting, pacing, motion graphics and transitions.", icon: "scissors" },
    { title: "Polish", text: "Sound design, music and colour grading.", icon: "sparkle" },
    { title: "Deliver", text: "Export in the right format, on time, with revisions.", icon: "rocket" },
  ],

  // ---------- ABOUT ----------
  about: {
    heading: "About Me",
    paragraphs: [
      // <-- EDIT these lines in your own words
      "Hi, I'm Ansh Srivastava. I've been editing videos for 5+ years.",
      "I also do web design and web development, and I use AI tools to work faster.",
      "I don't have clients yet — I'm open to my first freelance projects. If you need a video edited or a website built, let's talk.",
    ],
  },

  // ---------- CONTACT ----------
  contact: {
    heading: ["Let's create", "something", "extraordinary"],
    text: "I'm currently available for freelance projects and collaborations.",
    email: EMAIL, //                            (set at the top of this file)
    emailSubject: EMAIL_SUBJECT,
    location: "", //                            <-- optional: your city (leave "" to hide)
    // Free key from https://web3forms.com — create it with anshsrivastavaedit3@gmail.com,
    // because form messages go to the email the key was created with (not set in code).
    // This key is meant to be public, it only lets people SEND you messages.
    web3formsKey: "YOUR_WEB3FORMS_KEY", //      <-- EDIT: paste your key
  },

  // ---------- SOCIAL LINKS ----------
  // Shown in the navbar, contact/CTA box and footer. Leave url "" to hide one.
  // icon must be one of: "instagram", "youtube", "x"
  socials: [
    { name: "Instagram", icon: "instagram", url: "https://www.instagram.com/ansh.ai01" },
    { name: "YouTube", icon: "youtube", url: "https://www.youtube.com/@Ansh.Ai0lk" },
    { name: "X", icon: "x", url: "https://x.com/Ansh_9h" },
  ],

  footerYear: 2026,
};
