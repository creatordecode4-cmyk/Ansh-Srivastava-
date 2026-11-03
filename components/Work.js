"use client";

import { useCallback, useRef, useState } from "react";
import { site } from "@/data/site";
import { getThumbnail, isVertical } from "@/lib/video";
import Icon from "./Icons";
import VideoModal from "./VideoModal";

export default function Work() {
  const [filter, setFilter] = useState("All");
  const [active, setActive] = useState(null);
  const lastTrigger = useRef(null);

  const videos = filter === "All" ? site.videos : site.videos.filter((v) => v.category === filter);

  const openVideo = (video, e) => {
    lastTrigger.current = e.currentTarget;
    setActive(video);
  };

  const closeVideo = useCallback(() => {
    setActive(null);
    // give focus back to the card that opened the modal
    requestAnimationFrame(() => lastTrigger.current?.focus());
  }, []);

  return (
    <section id="work" className="pt-20" aria-labelledby="work-title">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <h2 id="work-title" className="eyebrow !text-xs !text-white/80">
          Featured Work
        </h2>
        <div role="group" aria-label="Filter videos by category" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
          {site.workCategories.map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={filter === c}
              onClick={() => setFilter(c)}
              className={`shrink-0 rounded-full border px-4 py-2 text-xs uppercase tracking-wider transition ${
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

      <ul className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {videos.map((v) => (
          <li key={v.title}>
            <VideoCard video={v} onOpen={openVideo} />
          </li>
        ))}
      </ul>
      {videos.length === 0 && <p className="py-10 text-center text-sm text-white/60">No videos in this category yet.</p>}

      {active && <VideoModal video={active} onClose={closeVideo} />}
    </section>
  );
}

function VideoCard({ video, onOpen }) {
  const thumb = getThumbnail(video);
  const vertical = isVertical(video);
  return (
    <button
      type="button"
      onClick={(e) => onOpen(video, e)}
      aria-label={`Play video: ${video.title}`}
      className="glass group block w-full overflow-hidden rounded-2xl text-left transition duration-300 hover:-translate-y-1 hover:border-white/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
    >
      {/* Thumbnail: 16:9 for horizontal videos, 9:16 for vertical (shorts/reels) */}
      <div className={vertical ? "bg-black/40 px-6 pt-4 sm:px-10" : ""}>
        <div
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
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
          <span className="absolute left-3 top-3 rounded-full border border-white/15 bg-black/60 px-3 py-1 text-[0.6rem] uppercase tracking-wider text-white/90 backdrop-blur">
            {vertical ? "Vertical · 9:16" : video.category}
          </span>
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
    </button>
  );
}
