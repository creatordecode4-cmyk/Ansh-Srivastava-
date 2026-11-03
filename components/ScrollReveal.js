"use client";

import { useEffect } from "react";

// Fades [data-reveal] elements in when they enter the screen and out when they leave.
// Also picks up elements added later (e.g. when you switch a Work filter tab).
export default function ScrollReveal() {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("reveal-ready");
    // Makes :active (pop + tap shine) fire reliably on touch screens.
    const noop = () => {};
    document.addEventListener("touchstart", noop, { passive: true });

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => e.target.classList.toggle("is-visible", e.isIntersecting));
      },
      { threshold: 0.05, rootMargin: "0px" }
    );

    const watched = new WeakSet();
    const scan = () =>
      document.querySelectorAll("[data-reveal]").forEach((el) => {
        if (!watched.has(el)) {
          watched.add(el);
          io.observe(el);
        }
      });
    scan();

    const mo = new MutationObserver(scan);
    mo.observe(document.body, { childList: true, subtree: true });

    return () => {
      io.disconnect();
      mo.disconnect();
      document.removeEventListener("touchstart", noop);
    };
  }, []);

  return null;
}
