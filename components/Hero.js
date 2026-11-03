import Image from "next/image";
import { site } from "@/data/site";
import Icon from "./Icons";

export default function Hero() {
  const { hero } = site;
  return (
    <section id="top" className="relative grid grid-cols-[1fr_0.75fr] items-end gap-0 pt-6 pb-8 md:grid-cols-[1.2fr_0.8fr] md:pt-10">
      {/* Text (left) */}
      <div className="relative z-10 col-span-2 row-start-2 md:col-span-1 md:row-start-1 md:pb-10">
        <p className="eyebrow mb-3">{hero.label}</p>
        <h1 className="font-display text-metal whitespace-nowrap text-[23vw] leading-[0.86] uppercase md:mr-[-30%] md:text-[9.5rem] lg:text-[11.5rem]">
          {hero.heading.map((w) => (
            <span key={w} className="block">
              {w}
            </span>
          ))}
        </h1>
        <p className="mt-5 max-w-md text-[0.95rem] leading-relaxed text-white/75">{hero.subtext}</p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
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

      {/* Photo (right) — blends into the background like the reference */}
      <div className="relative col-span-2 row-start-1 mx-auto -mb-16 w-full max-w-[360px] md:col-span-1 md:col-start-2 md:mb-0 md:max-w-none">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-4 top-8 h-[80%] w-[75%] rounded-r-full border border-l-0 border-white/15"
        />
        <div className="relative aspect-[4/5]">
          <Image src={hero.photo} alt={hero.photoAlt} fill priority sizes="(max-width: 768px) 360px, 460px" className="object-cover object-top" />
          {/* soft fades so the photo melts into the background */}
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#121418] via-transparent via-40% to-transparent" />
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-r from-[#121418] via-transparent via-30% to-transparent" />
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-b from-[#121418]/70 via-transparent via-20% to-transparent" />
        </div>
        <Icon name="sparkle" className="absolute right-6 top-1/3 h-5 w-5 text-white/70" />
        <div className="absolute bottom-20 right-0 z-10 text-right md:bottom-12">
          <p className="eyebrow !text-[0.6rem]">{hero.badgeTop}</p>
          <p className="font-display text-metal text-3xl uppercase leading-none md:text-4xl">{hero.badgeMain}</p>
          <p className="eyebrow !text-[0.6rem] mt-1 flex items-center justify-end gap-1">
            {hero.badgeBottom} <Icon name="arrow" className="h-3 w-3" />
          </p>
        </div>
      </div>
    </section>
  );
}
