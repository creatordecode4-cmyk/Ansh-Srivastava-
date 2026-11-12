/** ZERO ICE wordmark: italic "ZERO" + "ICE" knocked out of a slanted ice-blue band. */
export function Logo({ className = '', title = 'ZERO ICE' }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 196 44" className={className} role="img" aria-label={title} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="zi-band" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#4FB3FF" />
          <stop offset="1" stopColor="#1E6BFF" />
        </linearGradient>
      </defs>
      <text x="2" y="35" fontFamily='"Barlow Condensed","Arial Narrow",sans-serif' fontWeight="900" fontStyle="italic" fontSize="42" fill="#ffffff" letterSpacing="0.5">
        ZERO
      </text>
      <path d="M112 4 H194 L182 40 H100 Z" fill="url(#zi-band)" />
      <text x="147" y="35" textAnchor="middle" fontFamily='"Barlow Condensed","Arial Narrow",sans-serif' fontWeight="900" fontStyle="italic" fontSize="38" fill="#05070D" letterSpacing="1">
        ICE
      </text>
    </svg>
  )
}
