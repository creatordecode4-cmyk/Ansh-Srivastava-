import { site } from "@/data/site";
import { SocialLinks } from "./Icons";

export default function Footer() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-6 sm:flex-row sm:px-6">
        <p className="text-xs text-white/55">
          © {site.footerYear} {site.name}. All rights reserved.
          {/* Which version is live? Vercel fills this in at build time. */}
          <span className="ml-2 text-white/30">· build {(process.env.VERCEL_GIT_COMMIT_SHA || "local").slice(0, 7)}</span>
        </p>
        <div className="flex items-center gap-3">
          <span className="eyebrow !text-[0.6rem]">Let&apos;s connect</span>
          <SocialLinks socials={site.socials} />
        </div>
      </div>
    </footer>
  );
}
