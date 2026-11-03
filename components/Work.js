"use client";

import { useCallback, useRef, useState } from "react";
import { site } from "@/data/site";
import { getThumbnail } from "@/lib/video";
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

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
  return (
    <button
      type="button"
      onClick={(e) => onOpen(video, e)}
      aria-label={`Play video: ${video.title}`}
      className="glass group block w-full overflow-hidden rounded-2xl text-left transition duration-300 hover:-translate-y-1 hover:border-white/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
    >
      <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-[#2b2f37] via-[#1c1f24] to-[#0f1114]">
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
          <div className="flex h-full items-center justify-center">
            <span className="font-display text-metal text-3xl uppercase opacity-60">{video.category}</span>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        <span className="glass absolute left-3 top-3 rounded-full px-3 py-1 text-[0.65rem] uppercase tracking-wider text-white/85">
          {video.category}
        </span>
        <span className="absolute bottom-3 right-3 grid h-11 w-11 place-items-center rounded-full border border-white/40 bg-black/30 text-white backdrop-blur transition group-hover:scale-110 group-hover:bg-white group-hover:text-black">
          <Icon name="play" className="h-4 w-4 translate-x-[1px]" />
        </span>
      </div>
      <div className="p-4">
        <h3 className="text-base font-semibold text-white">{video.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-white/65">{video.description}</p>
      </div>
    </button>
  );
}
