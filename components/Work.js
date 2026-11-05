"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { site } from "@/data/site";
import { getPreviewSource, getThumbnail, isVertical, isVideoFile, sameCategory } from "@/lib/video";
import { loadYouTubeAPI } from "@/lib/youtube";
import { previewLog } from "@/lib/previewLog";
import PreviewDebug from "./PreviewDebug";
import Icon from "./Icons";
import VideoModal from "./VideoModal";

// A card's preview plays when at least 35% of it is on screen
// (low enough for tall 9:16 cards on small phones).
const PLAY_THRESHOLD = 0.35;
// Players (and the video src) exist only when a card is within ~1 screen of the viewport.
const NEAR_MARGIN = "100% 0px"; // ~1 screen above and below
// If YouTube hasn't started within this time, autoplay was blocked → show a Play button.
const BLOCKED_AFTER_MS = 1500;

export default function Work() {
  const [filter, setFilter] = useState("All");
  const [active, setActive] = useState(null); // video open in the modal
  const [previewId, setPreviewId] = useState(null); // the ONE card currently previewing
  const [nearIds, setNearIds] = useState(() => new Set()); // cards close enough to load a player
  const listRef = useRef(null);
  const lastTrigger = useRef(null);

  // "All" shows everything; every other tab shows ONLY its own category.
  // Tabs are built from the data: a category only gets a tab if it has at least one video
  // (in the order categories first appear in site.js).
  const categories = ["All"];
  site.videos.forEach((v) => {
    const c = (v.category || "").trim();
    if (c && !categories.some((x) => sameCategory(x, c))) categories.push(c);
  });

  const videos = filter === "All" ? site.videos : site.videos.filter((v) => sameCategory(v.category, filter));

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const targets = list.querySelectorAll("[data-preview-id]");

    // 1) "near" observer → lazily create players
    const near = new IntersectionObserver(
      (entries) => {
        setNearIds((prev) => {
          const next = new Set(prev);
          entries.forEach((e) => (e.isIntersecting ? next.add(e.target.dataset.previewId) : next.delete(e.target.dataset.previewId)));
          return next;
        });
      },
      { rootMargin: NEAR_MARGIN, threshold: 0 }
    );

    // 2) "play" observer → the most visible card (>= 35%) plays, all others pause
    const ratios = new Map();
    const els = new Map();
    const play = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          ratios.set(e.target.dataset.previewId, e.intersectionRatio);
          els.set(e.target.dataset.previewId, e.target);
        });
        // Most visible card wins; if two are equally visible (e.g. both 100%),
        // the one closest to the middle of the screen wins.
        const mid = window.innerHeight / 2;
        const distance = (id) => {
          const r = els.get(id).getBoundingClientRect();
          return Math.abs(r.top + r.height / 2 - mid);
        };
        let best = null;
        let bestRatio = 0;
        ratios.forEach((r, id) => {
          if (r < PLAY_THRESHOLD) return;
          const better = r > bestRatio + 0.01 || (Math.abs(r - bestRatio) <= 0.01 && best && distance(id) < distance(best));
          if (!best || better) {
            best = id;
            bestRatio = r;
          }
        });
        setPreviewId((prev) => {
          if (prev !== best) previewLog("info", `most visible card: ${best ?? "none"}`);
          return best;
        });
      },
      { threshold: [0, 0.2, PLAY_THRESHOLD, 0.5, 0.65, 0.8, 1] }
    );

    targets.forEach((el) => {
      near.observe(el);
      play.observe(el);
    });
    return () => {
      near.disconnect();
      play.disconnect();
    };
  }, [filter]);

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
          {categories.map((c) => (
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

      <ul ref={listRef} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {videos.map((v, i) => (
          <li key={`${filter}-${v.title}`} className="h-full" data-reveal style={{ "--reveal-delay": `${(i % 3) * 80}ms` }}>
            <VideoCard
              video={v}
              onOpen={openVideo}
              near={nearIds.has(v.title)}
              playing={!active && previewId === v.title}
              onManualPlay={() => setPreviewId(v.title)}
            />
          </li>
        ))}
      </ul>
      {videos.length === 0 && <p className="py-10 text-center text-sm text-white/60">No videos in this category yet.</p>}

      {active && <VideoModal video={active} onClose={closeVideo} />}
      <PreviewDebug />
    </section>
  );
}

function VideoCard({ video, onOpen, near, playing, onManualPlay }) {
  const thumb = getThumbnail(video);
  const vertical = isVertical(video);
  // Short local clip ("preview" in site.js) wins; otherwise fall back to the full video link.
  // The modal always plays the full video (videoUrl) with sound.
  // A full self-hosted video (/videos/*.mp4) is never loaded on the card: without a short
  // "preview" clip, the card just shows its poster + a Play button, and the video loads in the modal.
  const preview = video.preview
    ? { type: "file", src: video.preview, silent: true }
    : isVideoFile(video.videoUrl)
      ? null
      : getPreviewSource(video.videoUrl);
  const tag = video.tag || (/^re-?edit/i.test(video.credit || "") ? "Re-edit" : null);

  return (
    <div className="card-fx card-surface group relative flex h-full flex-col overflow-hidden rounded-2xl">
      {/* Thumbnail / preview: 16:9 for horizontal, 9:16 for vertical (shorts/reels) */}
      {/* Vertical videos: full 9:16 on phones (one column, no gaps possible); on 2-3 column
          screens they sit inside the same 16:9 frame as the others (video still uncropped,
          9:16 with dark sides) so every card has the same height and the grid has no holes. */}
      <div className={vertical ? "bg-black/40 px-6 pt-4 sm:bg-transparent sm:p-0" : ""}>
        <div
          data-preview-id={video.title}
          className={`relative mx-auto overflow-hidden bg-gradient-to-br from-[#2b2f37] via-[#1a1c20] to-[#0e1013] ${
            vertical ? "vertical-frame aspect-[9/16] w-full max-w-[280px] rounded-xl sm:aspect-video sm:max-w-none sm:rounded-none" : "aspect-video"
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

          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
          <div className="absolute left-3 top-3 flex flex-wrap gap-1.5">
            <span className="rounded-full border border-white/15 bg-black/60 px-3 py-1 text-[0.6rem] uppercase tracking-wider text-white/90">
              {vertical ? "Vertical · 9:16" : video.category}
            </span>
            {tag && (
              <span className="rounded-full border border-white/30 bg-white/90 px-3 py-1 text-[0.6rem] font-semibold uppercase tracking-wider text-black">
                {tag}
              </span>
            )}
          </div>
          {/* Poster-only cards (no preview clip): a clear Play button; tapping the card opens the player */}
          {!preview && video.videoUrl && (
            <span className="pointer-events-none absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/50 bg-white/90 text-black transition group-hover:scale-110">
              <Icon name="play" className="h-6 w-6 translate-x-[2px]" />
            </span>
          )}
          {/* "open full video" hint */}
          <span className="pointer-events-none absolute bottom-3 right-3 grid h-11 w-11 place-items-center rounded-full border border-white/40 bg-black/60 text-white transition group-hover:scale-110 group-hover:bg-white group-hover:text-black">
            <Icon name="arrow" className="h-4 w-4" />
          </span>

          {preview?.type === "drive" && <DrivePreview src={preview.src} near={near} title={video.title} />}
          {preview && preview.type !== "drive" && near && (
            <Preview source={preview} poster={thumb} playing={playing} onManualPlay={onManualPlay} title={video.title} />
          )}
        </div>
      </div>
      <div className="p-5">
        <p className="text-[0.65rem] uppercase tracking-[0.18em] text-white/55">{video.category}</p>
        <h3 className="mt-1.5 text-lg font-semibold leading-snug text-white">{video.title}</h3>
        <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-white/65">{video.short || video.description}</p>
        {video.credit && <p className="mt-2 text-xs text-white/45">{video.credit}</p>}
      </div>

      {/* The whole card is one big button → opens the full player with sound */}
      <button
        type="button"
        onClick={(e) => onOpen(video, e)}
        aria-label={`Open video with sound: ${video.title}`}
        className="absolute inset-0 z-10 rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      />
    </div>
  );
}

/**
 * ALWAYS-MUTED looping preview inside a card (sound only ever plays in the modal).
 * Works for local MP4s (native <video>) and YouTube (IFrame Player API).
 * This component only exists while the card is within ~1 screen of the viewport,
 * so far-away cards have no <video>/src at all. Only the playing card uses
 * preload="metadata"; nearby paused cards use preload="none" and show just the thumbnail.
 * If the browser blocks autoplay, a Play button appears; one tap starts it.
 */
function Preview({ source, poster, playing, onManualPlay, title }) {
  const videoRef = useRef(null); // <video> for files
  const ytHostRef = useRef(null); // container for the YouTube player
  const ytRef = useRef(null); // YT.Player instance
  const ytReadyRef = useRef(false);
  const playingRef = useRef(playing);
  const timerRef = useRef(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);

  const isFile = source.type === "file";
  const saveData = typeof navigator !== "undefined" && navigator.connection?.saveData;

  // play() wrapped in try/catch: older browsers can throw synchronously, newer ones reject the promise.
  const playFile = async (why) => {
    const v = videoRef.current;
    if (!v) return;
    try {
      v.muted = true; // previews are permanently muted
      await v.play();
      setBlocked(false);
      previewLog("info", `playing ${source.src} (${why})`);
    } catch (err) {
      // NotAllowedError = browser blocked autoplay; AbortError = paused/scrolled away before it started
      previewLog(err?.name === "AbortError" ? "info" : "warn", `play() failed for ${source.src}: ${err?.name} – ${err?.message}`);
      if (err?.name === "NotAllowedError" || why === "tap") setBlocked(true);
    }
  };

  const doPause = () => {
    clearTimeout(timerRef.current);
    if (isFile) videoRef.current?.pause();
    else if (ytReadyRef.current) ytRef.current.pauseVideo();
    setIsPlaying(false);
  };

  const doPlay = () => {
    clearTimeout(timerRef.current);
    if (isFile) {
      playFile("scroll");
      return;
    }
    if (!ytReadyRef.current) return; // onReady will call doPlay again
    ytRef.current.mute();
    ytRef.current.playVideo();
    timerRef.current = setTimeout(() => {
      const YT = window.YT;
      if (ytRef.current?.getPlayerState?.() !== YT?.PlayerState?.PLAYING) {
        previewLog("warn", `YouTube ${source.id} did not start within ${BLOCKED_AFTER_MS}ms (state ${ytRef.current?.getPlayerState?.()}) → showing Play button`);
        setBlocked(true);
      }
    }, BLOCKED_AFTER_MS);
  };

  // ---- create the YouTube player lazily ----
  useEffect(() => {
    if (isFile) return;
    let cancelled = false;
    const host = ytHostRef.current;
    loadYouTubeAPI()
      .then((YT) => {
        if (cancelled || !host) return;
        const el = document.createElement("div");
        host.appendChild(el);
        ytRef.current = new YT.Player(el, {
          videoId: source.id,
          width: "100%",
          height: "100%",
          playerVars: { mute: 1, controls: 0, playsinline: 1, loop: 1, playlist: source.id, modestbranding: 1, rel: 0, disablekb: 1 },
          events: {
            onReady: () => {
              ytReadyRef.current = true;
              ytRef.current.mute();
              if (playingRef.current && !saveData) doPlay();
            },
            onStateChange: (e) => {
              if (e.data === YT.PlayerState.PLAYING) {
                clearTimeout(timerRef.current);
                ytRef.current.mute(); // stay muted, always
                setBlocked(false);
                setIsPlaying(true);
              } else if (e.data === YT.PlayerState.ENDED) {
                ytRef.current.seekTo(0);
                ytRef.current.playVideo();
              } else if (e.data === YT.PlayerState.PAUSED) {
                setIsPlaying(false);
              }
            },
          },
        });
      })
      .catch((err) => {
        previewLog("error", `YouTube API failed to load: ${err?.message}`);
        setBlocked(true);
      });
    return () => {
      cancelled = true;
      clearTimeout(timerRef.current);
      ytReadyRef.current = false;
      try {
        ytRef.current?.destroy();
      } catch {}
      ytRef.current = null;
      if (host) host.innerHTML = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFile, source.id]);

  // ---- play when this card is the most visible one, pause (and hide) otherwise ----
  useEffect(() => {
    playingRef.current = playing;
    if (playing) {
      if (saveData) {
        previewLog("info", "Data Saver is on → waiting for a tap");
        setBlocked(true);
      } else doPlay();
    } else {
      doPause();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // A real tap = user gesture → browser allows playback; after this, scroll-autoplay works too.
  const handleTapPlay = (e) => {
    e.stopPropagation();
    setBlocked(false);
    onManualPlay();
    if (isFile) playFile("tap");
    else if (ytReadyRef.current) {
      ytRef.current.mute();
      ytRef.current.playVideo();
    }
  };

  const show = playing && isPlaying;

  return (
    <>
      {isFile ? (
        <video
          ref={videoRef}
          src={source.src}
          poster={poster || undefined}
          muted
          loop
          playsInline
          disablePictureInPicture
          preload={playing ? "metadata" : "none"}
          aria-hidden="true"
          tabIndex={-1}
          onPlaying={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onVolumeChange={(e) => {
            if (!e.currentTarget.muted) e.currentTarget.muted = true; // never allow sound on a card
          }}
          onError={() => previewLog("error", `video error for ${source.src}: code ${videoRef.current?.error?.code} ${videoRef.current?.error?.message || ""}`)}
          className={`pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
            show ? "opacity-100" : "opacity-0"
          }`}
        />
      ) : (
        <div
          ref={ytHostRef}
          aria-hidden="true"
          className={`pointer-events-none absolute inset-0 scale-[1.02] transition-opacity duration-300 [&_iframe]:pointer-events-none [&_iframe]:h-full [&_iframe]:w-full ${
            show ? "opacity-100" : "opacity-0"
          }`}
        />
      )}

      {show && (
        <span className="pointer-events-none absolute right-3 top-3 z-[5] flex items-center gap-1.5 rounded-full bg-black/75 px-2.5 py-1 text-[0.6rem] uppercase tracking-wider text-white/85">
          <span className="h-1.5 w-1.5 rounded-full bg-red-400" /> Preview
        </span>
      )}

      {/* Autoplay blocked → big round Play button (z-20 sits above the card button) */}
      {blocked && playing && !show && (
        <button
          type="button"
          onClick={handleTapPlay}
          aria-label={`Play preview: ${title}`}
          className="btn-fx absolute left-1/2 top-1/2 z-20 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/50 bg-white/90 text-black"
        >
          <Icon name="play" className="h-6 w-6 translate-x-[2px]" />
        </button>
      )}
    </>
  );
}

/**
 * Google Drive can't be started/paused from our page, so scroll-autoplay is unreliable.
 * Instead: a clear Play button; tapping it loads Drive's player right in the card
 * (Drive may ask for one more tap on its own ▶). Unloaded again when scrolled far away.
 */
function DrivePreview({ src, near, title }) {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!near) setLoaded(false);
  }, [near]);

  if (loaded) {
    return (
      <iframe
        src={src}
        title={`Preview: ${title}`}
        allow="autoplay; encrypted-media; fullscreen"
        allowFullScreen
        className="absolute inset-0 z-20 h-full w-full border-0 bg-black"
      />
    );
  }
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        previewLog("info", `Drive preview loaded: ${src}`);
        setLoaded(true);
      }}
      aria-label={`Play preview: ${title}`}
      className="btn-fx absolute left-1/2 top-1/2 z-20 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/50 bg-white/90 text-black"
    >
      <Icon name="play" className="h-6 w-6 translate-x-[2px]" />
    </button>
  );
}
