"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { site } from "@/data/site";
import { getPreviewSource, getThumbnail, isVertical, sameCategory } from "@/lib/video";
import Icon from "./Icons";
import VideoModal from "./VideoModal";

// A card starts its muted preview when at least this much of it is on screen.
const PLAY_THRESHOLD = 0.6;

export default function Work() {
  const [filter, setFilter] = useState("All");
  const [active, setActive] = useState(null); // video open in the modal
  const [previewId, setPreviewId] = useState(null); // the ONE card currently playing
  const [autoplayOk, setAutoplayOk] = useState(false);
  const listRef = useRef(null);
  const lastTrigger = useRef(null);

  // "All" shows everything; every other tab shows ONLY its own category.
  const videos = filter === "All" ? site.videos : site.videos.filter((v) => sameCategory(v.category, filter));

  // No autoplay for people who asked their phone/computer for reduced motion,
  // or who turned on "Data Saver".
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setAutoplayOk(!mq.matches && !navigator.connection?.saveData);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  // Watch every card; the most visible one (>= 60%) gets to play.
  useEffect(() => {
    if (!autoplayOk || !listRef.current) {
      setPreviewId(null);
      return;
    }
    const ratios = new Map();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => ratios.set(e.target.dataset.previewId, e.intersectionRatio));
        let best = null;
        let bestRatio = PLAY_THRESHOLD;
        ratios.forEach((r, id) => {
          if (r >= bestRatio) {
            best = id;
            bestRatio = r;
          }
        });
        setPreviewId(best);
      },
      { threshold: [0, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 1] }
    );
    listRef.current.querySelectorAll("[data-preview-id]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [filter, autoplayOk]);

  const openVideo = (video, e) => {
    lastTrigger.current = e.currentTarget;
    setActive(video);
  };

  const closeVideo = useCallback(() => {
    setActive(null);
    requestAnimationFrame(() => lastTrigger.current?.focus());
  }, []);

  return (
    <section id="work" className="pt-20" aria-labelledby="work-title">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <h2 id="work-title" data-reveal className="eyebrow !text-xs !text-white/80">
          Featured Work
        </h2>
        <div
          role="group"
          aria-label="Filter videos by category"
          data-reveal
          className="-mx-4 flex gap-2 overflow-x-auto px-4 py-2 sm:mx-0 sm:px-0"
        >
          {site.workCategories.map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={filter === c}
              onClick={() => setFilter(c)}
              className={`btn-fx shrink-0 rounded-full border px-4 py-2 text-xs uppercase tracking-wider ${
                filter === c
                  ? "btn-silver border-transparent font-semibold"
                  : "border-white/15 text-white/70 hover:border-white/40 hover:text-white"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <ul ref={listRef} className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {videos.map((v, i) => (
          <li key={`${filter}-${v.title}`} data-reveal style={{ "--reveal-delay": `${(i % 3) * 80}ms` }}>
            <VideoCard
              video={v}
              onOpen={openVideo}
              playing={!active && previewId === v.title}
            />
          </li>
        ))}
      </ul>
      {videos.length === 0 && <p className="py-10 text-center text-sm text-white/60">No videos in this category yet.</p>}

      {active && <VideoModal video={active} onClose={closeVideo} />}
    </section>
  );
}

function VideoCard({ video, onOpen, playing }) {
  const thumb = getThumbnail(video);
  const vertical = isVertical(video);
  const preview = getPreviewSource(video.videoUrl);

  return (
    <div className="glass group relative overflow-hidden rounded-2xl transition duration-300 hover:-translate-y-1 hover:border-white/30 active:scale-[0.98]">
      {/* Thumbnail / preview: 16:9 for horizontal, 9:16 for vertical (shorts/reels) */}
      <div className={vertical ? "bg-black/40 px-6 pt-4 sm:px-10" : ""}>
        <div
          data-preview-id={video.title}
          className={`relative mx-auto overflow-hidden bg-gradient-to-br from-[#2b2f37] via-[#1a1c20] to-[#0e1013] ${
            vertical ? "aspect-[9/16] w-full max-w-[280px] rounded-xl" : "aspect-video"
          }`}
        >
          {thumb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumb}
              alt=""
              loading="lazy"
              decoding="async"
              className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            />
          ) : (
            <Icon name="film" className="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 text-white/10" />
          )}

          {preview?.type === "file" && <FilePreview src={preview.src} poster={thumb} playing={playing} />}
          {/* YouTube iframe exists ONLY while this card is the one playing */}
          {preview?.type === "iframe" && playing && (
            <iframe
              src={preview.src}
              title=""
              aria-hidden="true"
              tabIndex={-1}
              allow="autoplay; encrypted-media"
              className="pointer-events-none absolute inset-0 h-full w-full scale-[1.02] border-0"
            />
          )}

          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
          <span className="absolute left-3 top-3 rounded-full border border-white/15 bg-black/60 px-3 py-1 text-[0.6rem] uppercase tracking-wider text-white/90 backdrop-blur">
            {vertical ? "Vertical · 9:16" : video.category}
          </span>
          {playing && (
            <span className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[0.6rem] uppercase tracking-wider text-white/80 backdrop-blur">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-400" /> Preview
            </span>
          )}
          <span className="absolute bottom-3 right-3 grid h-11 w-11 place-items-center rounded-full border border-white/40 bg-black/40 text-white backdrop-blur transition group-hover:scale-110 group-hover:bg-white group-hover:text-black">
            <Icon name="play" className="h-4 w-4 translate-x-[1px]" />
          </span>
        </div>
      </div>
      <div className="p-5">
        <p className="text-[0.65rem] uppercase tracking-[0.18em] text-white/55">{video.category}</p>
        <h3 className="mt-1.5 text-lg font-semibold leading-snug text-white">{video.title}</h3>
        <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-white/65">{video.short || video.description}</p>
      </div>

      {/* The whole card is one big button → opens the full player with sound */}
      <button
        type="button"
        onClick={(e) => onOpen(video, e)}
        aria-label={`Play video with sound: ${video.title}`}
        className="absolute inset-0 z-10 rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      />
    </div>
  );
}

// Muted looping <video>. It is only created after the card first becomes the
// playing one (so nothing downloads early), then simply paused/resumed.
function FilePreview({ src, poster, playing }) {
  const ref = useRef(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (playing) setMounted(true);
  }, [playing]);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    if (playing) v.play().catch(() => {});
    else v.pause();
  }, [playing, mounted]);

  if (!mounted) return null;
  return (
    <video
      ref={ref}
      src={src}
      poster={poster || undefined}
      muted
      loop
      playsInline
      preload="metadata"
      aria-hidden="true"
      tabIndex={-1}
      className={`pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ${
        playing ? "opacity-100" : "opacity-0"
      }`}
    />
  );
}
