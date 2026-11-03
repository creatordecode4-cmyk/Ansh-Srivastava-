import { site } from "@/data/site";
import Icon from "./Icons";

export default function Process() {
  return (
    <section id="process" className="pt-20" aria-labelledby="process-title">
      <h2 id="process-title" className="eyebrow mb-6 !text-xs !text-white/80">
        My Editing Process
      </h2>
      <ol className="glass grid gap-px overflow-hidden rounded-2xl sm:grid-cols-2 lg:grid-cols-5">
        {site.process.map((step, i) => (
          <li key={step.title} className="group relative p-5 transition hover:bg-white/[0.03]">
            <p className="text-xs uppercase tracking-wider text-white/85">
              <span className="mr-2 text-white/45">{String(i + 1).padStart(2, "0")}</span>
              {step.title}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-white/60">{step.text}</p>
            <Icon
              name={step.icon}
              className="mt-4 h-7 w-7 text-white/60 transition group-hover:-translate-y-0.5 group-hover:text-white"
            />
            {i < site.process.length - 1 && (
              <span aria-hidden="true" className="absolute right-3 top-6 hidden text-white/25 lg:block">
                ⋯›
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
