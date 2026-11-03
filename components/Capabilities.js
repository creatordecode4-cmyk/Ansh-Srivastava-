import { site } from "@/data/site";
import Icon from "./Icons";

export default function Capabilities() {
  return (
    <section id="capabilities" className="grid gap-10 pt-20 lg:grid-cols-[1.4fr_1fr] lg:gap-0">
      <div className="lg:border-r lg:border-white/10 lg:pr-10">
        <h2 className="eyebrow mb-6 border-b border-white/10 pb-4 !text-xs !text-white/80">Core Capabilities</h2>
        <ul className="grid gap-6 sm:grid-cols-2">
          {site.capabilities.map((c) => (
            <li key={c.title} className="group flex gap-4">
              <Icon
                name={c.icon}
                className="mt-0.5 h-8 w-8 shrink-0 text-white/70 transition group-hover:-translate-y-0.5 group-hover:text-white"
              />
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-white">{c.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-white/60">{c.text}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="lg:pl-10">
        <h2 className="eyebrow mb-6 border-b border-white/10 pb-4 !text-xs !text-white/80">Tools &amp; Technologies</h2>
        <ul className="glass grid grid-cols-2 gap-3 rounded-2xl p-4 sm:grid-cols-3">
          {site.tools.map((t) => (
            <li
              key={t.name}
              className="flex items-center gap-3 rounded-lg p-2 transition hover:bg-white/5"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-white/15 bg-white/5 text-xs font-bold text-white/90">
                {t.short}
              </span>
              <span className="text-sm text-white/80">{t.name}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
