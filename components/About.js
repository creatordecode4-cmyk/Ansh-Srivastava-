import { site } from "@/data/site";

export default function About() {
  return (
    <section id="about" className="grid gap-6 pt-20 md:grid-cols-[0.8fr_1.2fr]" aria-labelledby="about-title">
      <h2 id="about-title" data-reveal className="font-display text-metal text-5xl uppercase leading-none sm:text-6xl">
        {site.about.heading}
      </h2>
      <div data-reveal style={{ "--reveal-delay": "80ms" }} className="glass space-y-4 rounded-2xl p-6 text-[0.95rem] leading-relaxed text-white/75">
        {site.about.paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
    </section>
  );
}
