import { useEffect, useRef, useState } from 'react'
import { motion as fm } from 'framer-motion'
import { BLUR_IN, BLUR_OFF, Glass, Modal, PopButton, SPRING, ScrollTrigger, useMotion, usePinTimeline } from '../lib/motion'
import { scrollToSection } from '../lib/scroll'
import { sectionVh, variants, type VariantId } from '../tokens'
import { carouselAt } from '../three/scrollStore'
import { PinSection } from './PinSection'

/** where in the pin each can is front and centre */
const STOPS = [0.04, 0.5, 0.96]

function VariantCard({ v, notified, onNotify, reveal = false }: { v: (typeof variants)[number]; notified: boolean; onNotify: () => void; reveal?: boolean }) {
  return (
    <Glass as="article" reveal={reveal ? 'pop' : false} hover className="p-5 text-center md:p-6">
      <p className="font-sans text-sm font-medium text-silver/70">{v.available ? 'Available now' : 'Coming soon'}</p>
      <h3 className="heading mt-1.5 text-2xl md:text-3xl">{v.name}</h3>
      <p className="mx-auto mt-2 max-w-md text-base text-silver/70">{v.blurb}</p>
      <div className="mt-4 flex min-h-[44px] items-center justify-center" aria-live="polite">
        {v.available ? (
          <PopButton href="#cta" reveal={false} onClick={(e) => (e.preventDefault(), scrollToSection('cta', 0.9))}>
            Buy Now
          </PopButton>
        ) : notified ? (
          <p className="pop-in font-sans text-lg font-medium text-silver">✓ You're on the list</p>
        ) : (
          <PopButton variant="ghost" reveal={false} onClick={onNotify}>
            Notify me
          </PopButton>
        )}
      </div>
    </Glass>
  )
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

/** "Notify me" dialog. Front-end only: nothing is sent or stored. */
function NotifyDialog({ variant, onClose, onDone }: { variant: (typeof variants)[number] | null; onClose: () => void; onDone: (id: VariantId) => void }) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    if (variant) (setEmail(''), setError(''))
  }, [variant])
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!variant) return
    if (!EMAIL.test(email.trim())) return setError('Enter a valid email, like you@example.com.')
    onDone(variant.id)
    onClose()
  }
  return (
    <Modal open={!!variant} onClose={onClose} title={variant ? `Notify me: ${variant.sub}` : 'Notify me'}>
      <p className="mt-3 text-base text-silver">We'll ping you the moment {variant?.name ?? 'it'} drops. Demo only: no email is sent or stored.</p>
      <form onSubmit={submit} noValidate className="mt-5">
        <label htmlFor="notify-email" className="sr-only">
          Email address
        </label>
        <input
          id="notify-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => (setEmail(e.target.value), error && setError(''))}
          aria-invalid={!!error}
          aria-describedby={error ? 'notify-error' : undefined}
          className={`h-12 w-full rounded-full border bg-midnight/60 px-5 text-base text-silver placeholder:text-silver/60 focus:outline-none ${error ? 'border-[#FF8A8A]' : 'border-frost/30 focus:border-silver'}`}
        />
        <p id="notify-error" role="alert" className="mt-2 min-h-[1.25rem] px-2 text-sm text-[#FF9C9C]">
          {error}
        </p>
        <PopButton type="submit" reveal={false} className="mt-1 w-full">
          Notify me
        </PopButton>
      </form>
    </Modal>
  )
}

export function Lineup() {
  const ref = useRef<HTMLElement>(null)
  const motion = useMotion()
  const [active, setActive] = useState(0)
  const [notified, setNotified] = useState<Partial<Record<VariantId, boolean>>>({})
  const notify = (id: VariantId) => setNotified((n) => ({ ...n, [id]: true }))
  const [asking, setAsking] = useState<(typeof variants)[number] | null>(null)

  // which can faces the camera (same curve the 3D carousel uses)
  useEffect(() => {
    if (!motion || !ref.current) return
    const st = ScrollTrigger.create({
      trigger: ref.current,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (s) => setActive(Math.round(carouselAt(s.progress))),
    })
    return () => st.kill()
  }, [motion])

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-lineup="head"]', { opacity: 0, filter: BLUR_IN, y: 30 }, { opacity: 1, filter: BLUR_OFF, y: 0, duration: 0.06 }, 0)
  })

  const v = variants[active]

  return (
    <PinSection id="lineup" vh={sectionVh.lineup} ref={ref} glow="left-[20%] top-[-6%] h-[42%] w-[60%]">
      <div className={motion ? 'absolute inset-0' : 'mx-auto max-w-6xl px-5 py-24'}>
        <div className={motion ? 'absolute inset-x-5 top-[11svh] text-center md:top-[12svh]' : 'text-center'}>
          <div data-lineup="head">
            <h2 id="lineup-title" className="heading text-[2rem] md:text-5xl">
              Pick Your <span>Chill.</span>
            </h2>
          </div>
        </div>
        {motion ? (
          <div className="absolute inset-x-5 bottom-[3svh] mx-auto max-w-xl">
            {/* the card pops each time the front can changes */}
            <fm.div key={v.id} initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ scale: SPRING, opacity: { duration: 0.3 } }}>
              <VariantCard v={v} notified={!!notified[v.id]} onNotify={() => setAsking(v)} />
            </fm.div>
            <div className="mt-3 flex justify-center gap-1" role="group" aria-label="Choose a flavour">
              {variants.map((x, i) => (
                <button
                  key={x.id}
                  type="button"
                  aria-label={x.name}
                  aria-pressed={i === active}
                  onClick={() => scrollToSection('lineup', STOPS[i])}
                  className="flex h-11 w-11 items-center justify-center"
                >
                  <span className={`block h-1.5 rounded-full transition-all duration-300 ${i === active ? 'w-8 bg-silver/70' : 'w-3 bg-frost/35'}`} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="mt-10 grid gap-5 md:grid-cols-3">
            {variants.map((x) => (
              <li key={x.id}>
                <VariantCard v={x} reveal notified={!!notified[x.id]} onNotify={() => setAsking(x)} />
              </li>
            ))}
          </ul>
        )}
      </div>
      <NotifyDialog variant={asking} onClose={() => setAsking(null)} onDone={notify} />
    </PinSection>
  )
}
