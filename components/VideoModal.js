"use client";

import { useEffect, useRef } from "react";
import { getEmbedUrl } from "@/lib/video";
import Icon from "./Icons";

// Keyboard-friendly lightbox: Esc closes, Tab stays inside, page scroll is locked.
// The iframe is created only when the modal opens, so the page stays fast.
export default function VideoModal({ video, onClose }) {
  const dialogRef = useRef(null);
  const closeRef = useRef(null);
  const embed = getEmbedUrl(video.videoUrl);

  useEffect(() => {
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && dialogRef.current) {
        const items = dialogRef.current.querySelectorAll('button, a[href], iframe, [tabindex]:not([tabindex="-1"])');
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="video-modal-title"
        className="glass w-full max-w-4xl overflow-hidden rounded-2xl bg-[#15171b]"
      >
        <div className="flex items-start justify-between gap-4 p-4">
          <div>
            <p className="eyebrow !text-[0.6rem]">{video.category}</p>
            <h2 id="video-modal-title" className="text-base font-semibold text-white sm:text-lg">
              {video.title}
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close video"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/20 text-white transition hover:bg-white hover:text-black"
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="relative aspect-video bg-black">
          {embed ? (
            <iframe
              src={embed}
              title={video.title}
              className="absolute inset-0 h-full w-full"
              allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
              allowFullScreen
              loading="lazy"
              referrerPolicy="strict-origin-when-cross-origin"
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
              <Icon name="film" className="h-10 w-10 text-white/40" />
              <p className="text-sm text-white/70">Video coming soon.</p>
              <p className="text-xs text-white/45">
                (Owner: add a YouTube or Google Drive link in <code>data/site.js</code> → videoUrl)
              </p>
            </div>
          )}
        </div>
        {video.description && <p className="p-4 text-sm leading-relaxed text-white/70">{video.description}</p>}
      </div>
    </div>
  );
}
