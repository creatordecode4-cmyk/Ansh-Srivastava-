// =====================================================================
//  YOUR WEBSITE CONTENT — EDIT ONLY THIS FILE
//  Sab kuch (naam, videos, links, stats) yahin se change hota hai.
//  Components ko touch karne ki zaroorat nahi hai.
//  Rule: text ko hamesha "quotes" ke andar rakho, aur har item ke baad comma (,) lagao.
// =====================================================================

export const site = {
  // ---------- BASIC INFO ----------
  name: "Your Name", //                 <-- EDIT: your full name
  initials: "AV", //                    <-- EDIT: logo initials (2 letters)
  role: "Video Editor",
  url: "https://your-site.vercel.app", // <-- EDIT: after deploying on Vercel

  // SEO (Google search + WhatsApp/Instagram link previews)
  seo: {
    title: "Your Name — Video Editor & Web Developer", //   <-- EDIT
    description:
      "Video editor for documentaries, slow-motion edits, shorts and ads. I also design and build websites with React, Next.js and AI tools.", // <-- EDIT
  },

  // ---------- HERO ----------
  hero: {
    label: "Stories that move people",
    heading: ["Video", "Editor"], // big heading, one word per line
    subtext:
      "I edit engaging videos — documentaries, slow-motion edits, shorts and ads — and build websites using modern web tech and AI.",
    photo: "/profile.jpg", //  <-- EDIT: replace the file public/profile.jpg with your own photo (same name)
    photoAlt: "Portrait of Your Name, video editor", // <-- EDIT
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
  // category must be EXACTLY one of: "Slow Motion", "Documentary", "Others"
  // videoUrl supports:
  //   YouTube:  https://www.youtube.com/watch?v=XXXX  or  https://youtu.be/XXXX  or  /shorts/XXXX
  //   Google Drive: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
  //     (Drive file ko "Anyone with the link → Viewer" share karna zaroori hai)
  // thumbnail: optional. Leave "" for YouTube = auto thumbnail.
  //   Your own image: put it in /public/thumbs/ and write "/thumbs/my-image.jpg"
  workCategories: ["All", "Slow Motion", "Documentary", "Others"],
  videos: [
    {
      title: "REPLACE ME — Slow Motion Edit 1",
      category: "Slow Motion",
      description: "REPLACE ME: short line about this edit (music, speed ramps, mood).",
      videoUrl: "", // <-- EDIT: paste YouTube or Google Drive link
      thumbnail: "",
    },
    {
      title: "REPLACE ME — Slow Motion Edit 2",
      category: "Slow Motion",
      description: "REPLACE ME: what makes this edit special?",
      videoUrl: "",
      thumbnail: "",
    },
    {
      title: "REPLACE ME — Documentary 1",
      category: "Documentary",
      description: "REPLACE ME: topic of the documentary and your role (script, edit, sound).",
      videoUrl: "",
      thumbnail: "",
    },
    {
      title: "REPLACE ME — Documentary 2",
      category: "Documentary",
      description: "REPLACE ME: storytelling, research visuals, pacing.",
      videoUrl: "",
      thumbnail: "",
    },
    {
      title: "REPLACE ME — Short / Reel",
      category: "Others",
      description: "REPLACE ME: a short-form video, ad or motion graphics piece.",
      videoUrl: "",
      thumbnail: "",
    },
    {
      title: "REPLACE ME — Ad / Promo",
      category: "Others",
      description: "REPLACE ME: product ad, promo or channel intro.",
      videoUrl: "",
      thumbnail: "",
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
      "Hi! I'm Your Name. I've been editing videos for 5+ years — starting on my phone and learning motion graphics, pacing and sound along the way.",
      "I also design and develop websites with React and Next.js, and I use AI tools to research, script and work faster.",
      "I love informative content, tech and storytelling — videos that teach something and keep people hooked till the last second.",
    ],
  },

  // ---------- CONTACT ----------
  contact: {
    heading: ["Let's create", "something", "extraordinary"],
    text: "I'm currently available for freelance projects and collaborations.",
    email: "yourname@gmail.com", //            <-- EDIT: your email
    location: "India", //                       <-- EDIT (or "")
    // Free key from https://web3forms.com (enter your email → key comes in inbox).
    // This key is meant to be public, it only lets people SEND you messages.
    web3formsKey: "YOUR_WEB3FORMS_KEY", //      <-- EDIT: paste your key
  },

  // ---------- SOCIAL LINKS ----------
  // Leave url "" to hide an icon.
  socials: [
    { name: "Instagram", url: "https://instagram.com/yourhandle" }, // <-- EDIT
    { name: "YouTube", url: "https://youtube.com/@yourchannel" }, //   <-- EDIT
    { name: "LinkedIn", url: "https://linkedin.com/in/yourname" }, //  <-- EDIT
  ],

  footerYear: 2026,
};
