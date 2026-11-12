import { useEffect, useState } from 'react'
import { Logo } from './Logo'

export function Loader({ done }: { done: boolean }) {
  const [gone, setGone] = useState(false)
  useEffect(() => {
    if (!done) return
    const t = window.setTimeout(() => setGone(true), 700)
    return () => clearTimeout(t)
  }, [done])
  if (gone) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center gap-6 bg-midnight transition-opacity duration-700 ${done ? 'pointer-events-none opacity-0' : 'opacity-100'}`}
    >
      <Logo className="h-10 w-auto" />
      <div className="h-[2px] w-40 overflow-hidden rounded bg-frost/10">
        <div className="loader-bar h-full w-2/5 rounded bg-silver/80" />
      </div>
      <p className="eyebrow !text-xs">Chilling…</p>
    </div>
  )
}
