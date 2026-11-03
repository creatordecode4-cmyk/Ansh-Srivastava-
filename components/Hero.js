import Image from "next/image";
import { site } from "@/data/site";
import Icon from "./Icons";

export default function Hero() {
  const { hero } = site;
  return (
    <section id="top" className="relative grid items-end gap-8 pt-8 pb-10 md:grid-cols-[1.15fr_0.85fr] md:pt-12">
      <div className="relative z-10 order-2 md:order-1 md:pb-6">
        <p className="eyebrow mb-4">{hero.label}</p>
        <h1 className="font-display text-metal text-[22vw] leading-[0.88] uppercase sm:text-[9rem] md:text-[8.5rem] lg:text-[10rem]">
          {hero.heading.map((w) => (
            <span key={w} className="block">
              {w}
            </span>
          ))}
        </h1>
        <p className="mt-6 max-w-md text-[0.95rem] leading-relaxed text-white/75">{hero.subtext}</p>
        <div className="mt-8 flex flex-wrap items-center gap-4">
          <a
            href="#work"
            className="btn-silver inline-flex items-center gap-2 rounded-md px-6 py-3 text-xs font-semibold uppercase tracking-wider transition hover:brightness-110"
          >
            View My Work <Icon name="arrow" className="h-3.5 w-3.5" />
          </a>
          <a
            href="#contact"
            className="inline-flex items-center gap-2 rounded-md border border-white/20 px-6 py-3 text-xs font-semibold uppercase tracking-wider text-white/85 transition hover:border-white/50 hover:text-white"
          >
            Contact Me <Icon name="mail" className="h-4 w-4" />
          </a>
        </div>
      </div>

      <div className="relative order-1 mx-auto w-full max-w-[340px] md:order-2 md:max-w-none">
        {/* decorative arc like the reference */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-6 top-6 hidden h-[85%] w-[70%] rounded-r-full border border-l-0 border-white/15 md:block"
        />
        <div className="relative aspect-[4/5] overflow-hidden rounded-2xl md:rounded-none">
          <Image
            src={hero.photo}
            alt={hero.photoAlt}
            fill
            priority
            sizes="(max-width: 768px) 340px, 420px"
            className="object-cover object-top"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#121418] via-transparent to-transparent" />
        </div>
        <div className="glass absolute bottom-4 right-4 rounded-xl px-4 py-3 text-right md:-right-2 md:bottom-10">
          <p className="eyebrow !text-[0.6rem]">{hero.badgeTop}</p>
          <p className="font-display text-metal text-2xl uppercase leading-none">{hero.badgeMain}</p>
          <p className="eyebrow !text-[0.6rem] flex items-center justify-end gap-1">
            {hero.badgeBottom} <Icon name="arrow" className="h-3 w-3" />
          </p>
        </div>
        <Icon name="sparkle" className="absolute right-8 top-10 h-5 w-5 text-white/70" />
      </div>
    </section>
  );
}
