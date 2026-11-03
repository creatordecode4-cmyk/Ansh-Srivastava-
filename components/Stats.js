import { site } from "@/data/site";
import Icon from "./Icons";

export default function Stats() {
  return (
    <section aria-label="Quick facts" className="glass grid grid-cols-2 rounded-2xl md:grid-cols-4">
      {site.stats.map((s, i) => (
        <div
          key={s.label}
          className={`flex flex-col items-center px-3 py-6 text-center md:py-8 ${
            i % 2 === 1 ? "border-l border-white/10" : ""
          } ${i >= 2 ? "border-t border-white/10 md:border-t-0" : ""} ${i === 2 ? "md:border-l" : ""}`}
        >
          <Icon name={s.icon} className="mb-3 h-6 w-6 text-white/70" />
          <p className="text-metal text-3xl font-light sm:text-4xl">{s.value}</p>
          <p className="eyebrow mt-2 !text-[0.62rem]">{s.label}</p>
        </div>
      ))}
    </section>
  );
}
