import { useEffect, useRef, useState } from 'react'
import { scrollToSection, setScrollLocked } from '../lib/scroll'
import { Logo } from './Logo'

/** id + how far into the pinned section to land so its content is on screen */
export const NAV_LINKS: { label: string; id: string; into: number }[] = [
  { label: 'Story', id: 'story', into: 0.55 },
  { label: 'Journey', id: 'journey', into: 0.9 },
  { label: 'Numbers', id: 'numbers', into: 0 },
  { label: 'Reviews', id: 'reviews', into: 0 },
  { label: 'Lineup', id: 'lineup', into: 0.05 },
  { label: 'FAQ', id: 'faq', into: 0 },
]
const LINKS = NAV_LINKS

export function Navbar() {
  const [solid, setSolid] = useState(false)
  const [open, setOpen] = useState(false)
  const toggle = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    setScrollLocked(open)
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        toggle.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const go = (id: string, into: number) => (e: React.MouseEvent) => {
    e.preventDefault()
    setOpen(false)
    setScrollLocked(false)
    scrollToSection(id, into)
  }

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300 ${
        solid || open ? 'border-b border-frost/10 bg-midnight/70 backdrop-blur-xl' : 'border-b border-transparent bg-transparent'
      }`}
    >
      <nav aria-label="Primary" className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-5 md:h-[72px] md:px-10">
        <a href="#hero" onClick={go('hero', 0)} aria-label="ZERO ICE, back to top" className="shrink-0">
          <Logo className="h-7 w-auto md:h-8" />
        </a>
        <ul className="hidden items-center gap-7 lg:gap-9 md:flex">
          {LINKS.map((l) => (
            <li key={l.id}>
              <a href={`#${l.id}`} onClick={go(l.id, l.into)} className="font-display text-lg font-bold uppercase tracking-widest text-frost transition-colors hover:text-silver">
                {l.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-3">
          <a href="#cta" onClick={go('cta', 0.9)} className="btn-primary !min-h-[40px] !px-5 !text-base">
            Buy Now
          </a>
          <button
            ref={toggle}
            type="button"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-frost/20 md:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen((o) => !o)}
          >
            <span className="relative block h-3.5 w-5" aria-hidden="true">
              <span className={`absolute left-0 h-0.5 w-5 bg-silver transition-transform duration-300 ${open ? 'top-1.5 rotate-45' : 'top-0'}`} />
              <span className={`absolute left-0 top-1.5 h-0.5 w-5 bg-silver transition-opacity duration-200 ${open ? 'opacity-0' : ''}`} />
              <span className={`absolute left-0 h-0.5 w-5 bg-silver transition-transform duration-300 ${open ? 'top-1.5 -rotate-45' : 'top-3'}`} />
            </span>
          </button>
        </div>
      </nav>
      <div id="mobile-menu" hidden={!open} className="border-t border-frost/10 bg-midnight/95 px-5 pb-8 pt-4 md:hidden">
        <ul className="flex flex-col">
          {LINKS.map((l) => (
            <li key={l.id}>
              <a href={`#${l.id}`} onClick={go(l.id, l.into)} className="display block border-b border-frost/10 py-4 text-4xl">
                {l.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </header>
  )
}
