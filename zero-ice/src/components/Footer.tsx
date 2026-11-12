import { scrollToSection } from '../lib/scroll'
import { Logo } from './Logo'
import { NAV_LINKS } from './Navbar'

const LINKS = NAV_LINKS

const SOCIALS = [
  { label: 'Instagram', d: 'M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5Zm5 5.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Zm0 2a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM17.5 5.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z' },
  { label: 'YouTube', d: 'M21.6 7.2a2.7 2.7 0 0 0-1.9-1.9C18 4.8 12 4.8 12 4.8s-6 0-7.7.5A2.7 2.7 0 0 0 2.4 7.2C2 8.9 2 12 2 12s0 3.100.4 4.800a2.7 2.7 0 0 0 1.900 1.900c1.700.5 7.700.5 7.700.5s6 0 7.700-.5a2.7 2.7 0 0 0 1.900-1.900c.4-1.700.4-4.800.4-4.800s0-3.100-.4-4.800ZM10 15.200V8.800l5.200 3.200L10 15.200Z' },
  { label: 'X', d: 'M17.5 3h3.100l-6.800 7.800L21.800 21h-6.200l-4.900-6.400L5.100 21H2l7.300-8.300L1.700 3H8l4.400 5.800L17.500 3Zm-1.100 16.200h1.700L7.100 4.700H5.300l11.100 14.500Z' },
]

export function Footer() {
  return (
    <footer className="relative z-20 border-t border-frost/10 px-5 pb-10 pt-16 md:px-10">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-10 md:flex-row md:items-start md:justify-between">
        <div>
          <Logo className="h-9 w-auto" />
          <p className="mt-3 font-sans text-lg font-medium text-silver/70">Bold taste. Zero guilt.</p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-8 gap-y-2">
            {LINKS.map((l) => (
              <li key={l.id}>
                <a
                  href={`#${l.id}`}
                  onClick={(e) => (e.preventDefault(), scrollToSection(l.id, l.into))}
                  className="inline-flex min-h-[44px] items-center font-sans text-lg font-medium text-silver/70 hover:text-silver"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <ul className="flex gap-3" aria-label="Social links (demo)">
          {SOCIALS.map((s) => (
            <li key={s.label}>
              <a href="#hero" onClick={(e) => e.preventDefault()} aria-label={`${s.label} (demo link)`} className="flex h-11 w-11 items-center justify-center rounded-full border border-frost/20 text-silver/70 transition-colors hover:border-silver hover:text-silver">
                <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                  <path d={s.d} fill="currentColor" fillRule="evenodd" />
                </svg>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="mx-auto mt-12 flex max-w-[1400px] flex-col gap-2 border-t border-frost/10 pt-6 text-sm text-silver/70 md:flex-row md:justify-between">
        <p className="max-w-3xl">ZERO ICE is a fictional brand created for a demo. Statistics, ratings and testimonials are placeholder demo data. Videos and images are AI-generated.</p>
        <p className="shrink-0">© 2026 ZERO ICE</p>
      </div>
    </footer>
  )
}
