"use client";

import { useEffect, useState } from "react";
import { site } from "@/data/site";
import Icon, { SocialLinks } from "./Icons";

const links = [
  { href: "#work", label: "Work" },
  { href: "#web", label: "Web" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#about", label: "About" },
  { href: "#contact", label: "Contact" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={`sticky top-0 z-40 transition-colors ${
        scrolled || open ? "border-b border-white/10 bg-[#121418]/85 backdrop-blur-md" : "bg-transparent"
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6" aria-label="Main">
        <a href="#top" className="font-display text-2xl tracking-wide text-metal" aria-label={`${site.name} — home`}>
          {site.initials}
        </a>

        <ul className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <li key={l.href}>
              <a href={l.href} className="text-xs uppercase tracking-[0.18em] text-white/70 transition hover:text-white">
                {l.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-3 md:flex">
          <SocialLinks socials={site.socials} small className="hidden !gap-2 lg:flex" />
          <a
            href="#contact"
            className="btn-fx btn-silver inline-flex items-center gap-2 rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-wider transition hover:brightness-110"
          >
            Let&apos;s Talk <Icon name="arrow" className="h-3.5 w-3.5" />
          </a>
        </div>

        <button
          type="button"
          className="btn-fx grid h-10 w-10 place-items-center rounded-lg border border-white/15 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          <Icon name={open ? "close" : "menu"} />
        </button>
      </nav>

      {open && (
        <div id="mobile-menu" className="border-t border-white/10 md:hidden">
          <ul className="mx-auto flex max-w-6xl flex-col px-4 py-3">
            {links.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="block py-3 text-sm uppercase tracking-[0.18em] text-white/80 hover:text-white"
                >
                  {l.label}
                </a>
              </li>
            ))}
            <li className="pt-2 pb-3">
              <a
                href="#contact"
                onClick={() => setOpen(false)}
                className="btn-fx btn-silver flex items-center justify-center gap-2 rounded-full px-5 py-3 text-xs font-semibold uppercase tracking-wider"
              >
                Let&apos;s Talk <Icon name="arrow" className="h-3.5 w-3.5" />
              </a>
            </li>
            <li className="flex justify-center pb-3">
              <SocialLinks socials={site.socials} />
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
