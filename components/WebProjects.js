"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { site } from "@/data/site";
import Icon from "./Icons";

// If the iframe hasn't loaded after this long, assume the site blocks embedding.
const LOAD_TIMEOUT_MS = 6000;

const withHttps = (url = "") => (/^https?:\/\//i.test(url) ? url : `https://${url}`);
const domainOf = (url = "") => {
  try {
    return new URL(withHttps(url)).hostname;
  } catch {
    return url;
  }
};

export default function WebProjects() {
  const sites = site.websites || [];
  const [index, setIndex] = useState(null); // open site index, or null
  const lastTrigger = useRef(null);

  const open = (i, e) => {
    lastTrigger.current = e.currentTarget;
    setIndex(i);
  };
  const close = useCallback(() => {
    setIndex(null);
    requestAnimationFrame(() => lastTrigger.current?.focus());
  }, []);

  if (!sites.length) return null;

  return (
    <section id="web" className="pt-20" aria-labelledby="web-title">
      <div className="mb-6">
        <h2 id="web-title" data-reveal className="font-display text-metal text-4xl uppercase leading-none sm:text-5xl">
          Web Design &amp; Development
        </h2>
        <p data-reveal style={{ "--reveal-delay": "80ms" }} className="mt-3 text-sm text-white/65">
          Websites I designed and built with the help of AI tools.
        </p>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sites.map((s, i) => (
          <li key={s.url} data-reveal style={{ "--reveal-delay": `${(i % 3) * 80}ms` }}>
            <button
              type="button"
              onClick={(e) => open(i, e)}
              aria-label={`Preview website: ${s.title}`}
              className="card-fx card-surface group block w-full overflow-hidden rounded-2xl text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              <div className="relative aspect-[16/10] overflow-hidden">
                <SiteImage site={s} />
                <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full border border-white/15 bg-black/70 px-3 py-1 text-[0.6rem] uppercase tracking-wider text-white/90">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Live site
                </span>
                <span className="absolute bottom-3 right-3 grid h-11 w-11 place-items-center rounded-full border border-white/40 bg-black/60 text-white transition group-hover:scale-110 group-hover:bg-white group-hover:text-black">
                  <Icon name="browser" className="h-5 w-5" />
                </span>
              </div>
              <div className="p-5">
                <p className="text-[0.65rem] uppercase tracking-[0.18em] text-white/55">{domainOf(s.url)}</p>
                <h3 className="mt-1.5 text-lg font-semibold leading-snug text-white">{s.title}</h3>
                {s.description && <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-white/65">{s.description}</p>}
              </div>
            </button>
          </li>
        ))}
      </ul>

      {index !== null && <SiteViewer sites={sites} index={index} setIndex={setIndex} onClose={close} />}
    </section>
  );
}

/** Screenshot if there is one, otherwise a dark gradient with the site name. */
function SiteImage({ site: s, big = false }) {
  if (s.screenshot) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={s.screenshot}
        alt={`Screenshot of ${s.title}`}
        loading="lazy"
        decoding="async"
        className="h-full w-full object-cover object-top transition duration-500 group-hover:scale-105"
      />
    );
  }
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-[radial-gradient(120%_90%_at_30%_0%,#3a3f48_0%,#1b1e23_45%,#0e1013_100%)] p-4 text-center">
      <span className={`font-display text-metal uppercase leading-none ${big ? "text-5xl sm:text-7xl" : "text-4xl"}`}>{s.title}</span>
      <span className="text-[0.65rem] uppercase tracking-[0.2em] text-white/45">{domainOf(s.url)}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Browser-style viewer                                               */
/* ------------------------------------------------------------------ */
function SiteViewer({ sites, index, setIndex, onClose }) {
  const s = sites[index];
  const url = withHttps(s.url);
  const total = sites.length;

  const [status, setStatus] = useState("loading"); // loading | loaded | failed
  const [dir, setDir] = useState("next"); // which way the swap animation slides
  const dialogRef = useRef(null);
  const closeRef = useRef(null);

  const go = useCallback(
    (step) => {
      setDir(step > 0 ? "next" : "prev");
      setIndex((i) => (i + step + total) % total);
    },
    [setIndex, total]
  );

  // New site → show spinner, start the 6s "can't embed" timer
  useEffect(() => {
    setStatus("loading");
    const t = setTimeout(() => setStatus((st) => (st === "loading" ? "failed" : st)), LOAD_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [index]);

  // Focus, scroll lock, keyboard (Esc / arrows / Tab trap)
  useEffect(() => {
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "Tab" && dialogRef.current) {
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
  }, [onClose, go]);

  const navBtn =
    "btn-fx inline-flex items-center gap-1.5 rounded-full border border-white/20 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/85 hover:border-white/50 hover:text-white";

  return (
    <div className="fixed inset-0 z-50 flex bg-black/90 sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Website preview: ${s.title}`}
        className="mx-auto flex h-full w-full max-w-6xl flex-col overflow-hidden border border-white/15 bg-[#15171b] sm:rounded-xl"
      >
        {/* ---- Browser top bar ---- */}
        <div className="flex items-center gap-2 border-b border-white/10 bg-[#1d2025] px-3 py-2.5">
          <div className="hidden items-center gap-1.5 sm:flex" aria-hidden="true">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]/80" />
            <span className="h-3 w-3 rounded-full bg-[#febc2e]/80" />
            <span className="h-3 w-3 rounded-full bg-[#28c840]/80" />
          </div>
          <div className="mx-1 flex min-w-0 flex-1 items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white/75">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" aria-hidden="true" />
            <span className="truncate">{domainOf(s.url)}</span>
          </div>
          <a href={url} target="_blank" rel="noopener noreferrer" className={`${navBtn} !px-3`} aria-label={`Open ${s.title} in a new tab`}>
            <Icon name="external" className="h-4 w-4" />
            <span className="hidden sm:inline">New tab</span>
          </a>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close website preview"
            className="btn-fx grid h-9 w-9 shrink-0 place-items-center rounded-full border border-white/20 text-white hover:bg-white hover:text-black"
          >
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>

        {/* ---- Page area (key = index → remount + swap animation) ---- */}
        <div key={index} className={`relative flex-1 bg-black ${dir === "next" ? "viewer-swap-next" : "viewer-swap-prev"}`}>
          {status !== "failed" && (
            <iframe
              src={url}
              title={`${s.title} — live website`}
              loading="lazy"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              onLoad={() => setStatus("loaded")}
              onError={() => setStatus("failed")}
              className={`absolute inset-0 h-full w-full border-0 bg-white transition-opacity duration-300 ${
                status === "loaded" ? "opacity-100" : "opacity-0"
              }`}
            />
          )}

          {status === "loading" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3" role="status" aria-live="polite">
              <span className="h-10 w-10 animate-spin rounded-full border-2 border-white/15 border-t-white" />
              <span className="text-xs uppercase tracking-[0.2em] text-white/55">Loading {domainOf(s.url)}…</span>
            </div>
          )}

          {status === "failed" && (
            <div className="absolute inset-0">
              <div className="absolute inset-0 opacity-20">
                <SiteImage site={s} big />
              </div>
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/50 p-6 text-center">
                <p className="text-base font-semibold text-white">This site can&apos;t be previewed here</p>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-fx btn-silver inline-flex items-center gap-2 rounded-md px-8 py-4 text-sm font-semibold uppercase tracking-wider"
                >
                  Open Live Site <Icon name="external" className="h-4 w-4" />
                </a>
              </div>
            </div>
          )}
        </div>

        {/* ---- Bottom bar: Previous / counter / Next ---- */}
        <div className="flex items-center justify-between gap-3 border-t border-white/10 bg-[#1d2025] px-3 py-2.5">
          <button type="button" onClick={() => go(-1)} className={navBtn} aria-label="Previous website">
            <Icon name="chevLeft" className="h-4 w-4" /> Previous
          </button>
          <div className="min-w-0 text-center">
            <p className="truncate text-sm font-semibold text-white">{s.title}</p>
            <p className="text-[0.65rem] uppercase tracking-[0.2em] text-white/50" aria-live="polite">
              {index + 1} / {total}
            </p>
          </div>
          <button type="button" onClick={() => go(1)} className={navBtn} aria-label="Next website">
            Next <Icon name="chevRight" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
