"use client";

import { useEffect } from "react";

// Fades [data-reveal] elements in when they enter the screen and out when they leave.
// Also picks up elements added later (e.g. when you switch a Work filter tab).
export default function ScrollReveal() {
  useEffect(() => {
    const root = document.documentElement;
    if (!root.classList.contains("reveal-ready")) return; // reduced motion → nothing to do

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => e.target.classList.toggle("is-visible", e.isIntersecting));
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
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

    const mq = matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => mq.matches && root.classList.remove("reveal-ready");
    mq.addEventListener("change", onChange);

    return () => {
      io.disconnect();
      mo.disconnect();
      mq.removeEventListener("change", onChange);
    };
  }, []);

  return null;
}
