"use client";

import { useEffect, useRef, useState } from "react";
import { site } from "@/data/site";
import { mailtoHref } from "@/lib/contact";
import Icon from "./Icons";

// The email as plain visible text + a small "Copy" button ("Copied!" for 2 seconds).
export default function CopyEmail({ className = "", small = false }) {
  const { email } = site.contact;
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(email);
    } catch {
      // Fallback for older browsers / non-https pages
      const t = document.createElement("textarea");
      t.value = email;
      t.setAttribute("readonly", "");
      t.style.position = "fixed";
      t.style.opacity = "0";
      document.body.appendChild(t);
      t.select();
      document.execCommand("copy");
      t.remove();
    }
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  }

  return (
    <span className={`inline-flex flex-wrap items-center gap-2 ${className}`}>
      <a href={mailtoHref} className={`break-all hover:text-white hover:underline ${small ? "text-xs" : "text-sm"}`}>
        {email}
      </a>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Email copied" : `Copy email address ${email}`}
        className="btn-fx inline-flex items-center gap-1 rounded-full border border-white/20 px-2.5 py-1 text-[0.65rem] font-semibold uppercase tracking-wider text-white/85 hover:border-white/50 hover:text-white"
      >
        <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" />
        {copied ? "Copied!" : "Copy"}
      </button>
      <span className="sr-only" role="status" aria-live="polite">
        {copied ? "Email address copied" : ""}
      </span>
    </span>
  );
}
