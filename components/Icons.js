// Simple inline SVG icons (no extra library needed).
// Use: <Icon name="film" className="h-6 w-6" />

const paths = {
  sparkle: <path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6L12 3z" />,
  layers: (
    <>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="2.5" width="10" height="19" rx="2" />
      <path d="M11 18.5h2" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
    </>
  ),
  film: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" />
    </>
  ),
  motion: (
    <>
      <path d="M4 18c3-8 6-12 16-12" />
      <circle cx="4" cy="18" r="1.6" />
      <circle cx="12" cy="9" r="1.6" />
      <circle cx="20" cy="6" r="1.6" />
    </>
  ),
  story: (
    <>
      <path d="M4 5h7a2 2 0 012 2v13a2 2 0 00-2-2H4V5z" />
      <path d="M20 5h-5a2 2 0 00-2 2v13a2 2 0 012-2h5V5z" />
    </>
  ),
  sound: <path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0" />,
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="1.5" />
      <path d="M9 20h6M12 16v4" />
    </>
  ),
  code: <path d="M9 7l-5 5 5 5M15 7l5 5-5 5" />,
  ai: (
    <>
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4M10 10h4v4h-4z" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  scissors: (
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <path d="M8 7.5L20 17M8 16.5L20 7" />
    </>
  ),
  rocket: (
    <>
      <path d="M14 4c3-1 5-1 6 0 1 1 1 3 0 6l-6 6-6-6 6-6z" />
      <path d="M8 10l-4 1 2-4h4M14 16l-1 4 4-2v-4M6 18l-2 2" />
      <circle cx="15.5" cy="8.5" r="1.3" />
    </>
  ),
  arrow: <path d="M7 17L17 7M9 7h8v8" />,
  play: <path d="M8 5.5v13l11-6.5-11-6.5z" fill="currentColor" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 7l9 6 9-6" />
    </>
  ),
  pin: (
    <>
      <path d="M12 21s-6-5.5-6-11a6 6 0 1112 0c0 5.5-6 11-6 11z" />
      <circle cx="12" cy="10" r="2.2" />
    </>
  ),
  instagram: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" />
    </>
  ),
  youtube: (
    <>
      <rect x="2.5" y="5.5" width="19" height="13" rx="3.5" />
      <path d="M10 9v6l5-3-5-3z" fill="currentColor" />
    </>
  ),
  linkedin: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M7.5 10.5V17M7.5 7.2v.1M11.5 17v-6.5M11.5 13c0-1.6 1-2.5 2.3-2.5S16.5 11.3 16.5 13v4" />
    </>
  ),
};

export default function Icon({ name, className = "h-5 w-5", ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
      {...props}
    >
      {paths[name] || paths.sparkle}
    </svg>
  );
}

export function SocialLinks({ socials, className = "" }) {
  return (
    <ul className={`flex items-center gap-3 ${className}`}>
      {socials
        .filter((s) => s.url)
        .map((s) => (
          <li key={s.name}>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${s.name} (opens in new tab)`}
              className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 text-white/70 transition hover:-translate-y-0.5 hover:border-white/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            >
              <Icon name={s.name.toLowerCase()} className="h-5 w-5" />
            </a>
          </li>
        ))}
    </ul>
  );
}
