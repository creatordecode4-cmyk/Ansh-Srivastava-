"use client";

import { useState } from "react";
import { site } from "@/data/site";
import Icon, { SocialLinks } from "./Icons";
import CopyEmail from "./CopyEmail";
import { gmailHref, mailtoHref } from "@/lib/contact";

export default function Contact() {
  const { contact } = site;
  const [status, setStatus] = useState({ state: "idle", msg: "" });

  async function handleSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;

    if (!contact.web3formsKey || contact.web3formsKey === "YOUR_WEB3FORMS_KEY") {
      setStatus({
        state: "error",
        msg: `The form isn't set up yet. Please email me at ${contact.email}.`,
      });
      return;
    }

    setStatus({ state: "loading", msg: "Sending…" });
    const data = new FormData(form);
    data.append("access_key", contact.web3formsKey);
    data.append("subject", `${contact.emailSubject} — ${data.get("name")}`);

    try {
      const res = await fetch("https://api.web3forms.com/submit", { method: "POST", body: data });
      const json = await res.json();
      if (json.success) {
        setStatus({ state: "success", msg: "Thanks! Your message was sent. I'll reply soon." });
        form.reset();
      } else {
        setStatus({ state: "error", msg: json.message || "Something went wrong. Please try again." });
      }
    } catch {
      setStatus({ state: "error", msg: "Network error. Please try again or email me directly." });
    }
  }

  const inputCls =
    "w-full rounded-lg border border-white/15 bg-black/30 px-4 py-3 text-sm text-white placeholder-white/40 outline-none transition focus:border-white/60";

  return (
    <section id="contact" className="pt-20 pb-10" aria-labelledby="contact-title">
      <div data-reveal className="cta-metal relative grid gap-10 overflow-hidden rounded-2xl border border-white/15 p-6 sm:p-10 lg:grid-cols-2">
        <div>
          <h2 id="contact-title" className="font-display text-metal text-5xl uppercase leading-[0.95] sm:text-6xl">
            {contact.heading.map((l) => (
              <span key={l} className="block">
                {l}
              </span>
            ))}
          </h2>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-white/75">{contact.text}</p>

          <ul className="mt-6 space-y-3 text-sm text-white/80">
            <li className="flex items-center gap-3">
              <Icon name="mail" className="h-4 w-4 shrink-0 text-white/60" />
              <CopyEmail />
            </li>
            {contact.location && (
              <li className="flex items-center gap-3">
                <Icon name="pin" className="h-4 w-4 text-white/60" />
                {contact.location}
              </li>
            )}
          </ul>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <a
              href={mailtoHref}
              className="btn-fx btn-silver inline-flex items-center gap-2 rounded-md px-6 py-3 text-xs font-semibold uppercase tracking-wider transition hover:brightness-110"
            >
              Email Me <Icon name="arrow" className="h-3.5 w-3.5" />
            </a>
            <a
              href={gmailHref}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-fx inline-flex items-center gap-2 rounded-md border border-white/25 px-6 py-3 text-xs font-semibold uppercase tracking-wider text-white/90 hover:border-white/50 hover:text-white"
            >
              <Icon name="gmail" className="h-4 w-4" /> Open in Gmail
            </a>
          </div>
          <SocialLinks socials={site.socials} className="mt-5" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* honeypot: hidden field that bots fill, humans don't */}
          <input type="checkbox" name="botcheck" className="hidden" tabIndex={-1} autoComplete="off" aria-hidden="true" />
          {/* Web3Forms delivers to the email the access key was created with (anshsrivastavaedit3@gmail.com).
              The visitor's "email" field becomes the reply-to address automatically. */}
          <input type="hidden" name="from_name" value={`${site.name} — Portfolio`} />
          <div>
            <label htmlFor="name" className="mb-1.5 block text-xs uppercase tracking-wider text-white/70">
              Name
            </label>
            <input id="name" name="name" type="text" required autoComplete="name" placeholder="Your name" className={inputCls} />
          </div>
          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs uppercase tracking-wider text-white/70">
              Email
            </label>
            <input id="email" name="email" type="email" required autoComplete="email" placeholder="you@example.com" className={inputCls} />
          </div>
          <div>
            <label htmlFor="message" className="mb-1.5 block text-xs uppercase tracking-wider text-white/70">
              Message
            </label>
            <textarea
              id="message"
              name="message"
              required
              rows={5}
              placeholder="Tell me about your video or website project…"
              className={`${inputCls} resize-y`}
            />
          </div>
          <button
            type="submit"
            disabled={status.state === "loading"}
            className="btn-fx btn-silver inline-flex w-full items-center justify-center gap-2 rounded-md px-6 py-3 text-xs font-semibold uppercase tracking-wider transition hover:brightness-110 disabled:opacity-60 sm:w-auto"
          >
            {status.state === "loading" ? "Sending…" : "Let's Work Together"} <Icon name="arrow" className="h-3.5 w-3.5" />
          </button>
          <p
            role="status"
            aria-live="polite"
            className={`min-h-5 text-sm ${
              status.state === "success" ? "text-emerald-300" : status.state === "error" ? "text-rose-300" : "text-white/60"
            }`}
          >
            {status.state !== "idle" && status.state !== "loading" ? status.msg : ""}
          </p>
        </form>
      </div>
    </section>
  );
}
