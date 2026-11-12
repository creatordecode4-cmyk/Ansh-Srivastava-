import { useRef, useState } from 'react'
import { BLUR_IN, BLUR_OFF, Glass, Modal, PopButton, usePinTimeline } from '../lib/motion'
import { sectionVh } from '../tokens'
import { PinSection } from './PinSection'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export function FinalCTA() {
  const ref = useRef<HTMLElement>(null)
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [stores, setStores] = useState(false)

  usePinTimeline(ref, (tl) => {
    tl.fromTo('[data-cta="item"]', { opacity: 0, filter: BLUR_IN, y: 40 }, { opacity: 1, filter: BLUR_OFF, y: 0, duration: 0.16, stagger: 0.07 }, 0.12)
    // the form block holds glass, so it fades without a filter (a parent filter would kill its backdrop blur)
    tl.fromTo('[data-cta="form"]', { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.16 }, 0.33)
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!EMAIL.test(email.trim())) {
      setError('Enter a valid email, like you@example.com.')
      return
    }
    setError('')
    setDone(true) // front-end only: nothing is sent anywhere
  }

  return (
    <PinSection id="cta" vh={sectionVh.cta} ref={ref} tone="gradient" glow="left-[-10%] top-[16%] hidden h-[64%] w-[60%] md:block">
      <div className="absolute inset-0 mx-auto max-w-[1500px]">
        <div className="absolute inset-x-5 top-[11svh] text-center md:inset-x-auto md:left-[7%] md:top-1/2 md:w-[44%] md:-translate-y-1/2 md:text-left">
          <p className="eyebrow mb-3" data-cta="item">
            The Drop
          </p>
          <h2 id="cta-title" className="display text-[12.5vw] md:text-[clamp(3.6rem,6vw,7.2rem)]" data-cta="item">
            Get your first case <span className="text-cyan">ice cold.</span>
          </h2>
          <p className="mx-auto mt-3 max-w-md text-base text-frost md:mx-0 md:mt-5 md:text-lg" data-cta="item">
            Be first in line when the next drop lands. No spam, just cold cola.
          </p>
          <div className="mt-4 min-h-[112px] md:mt-7" data-cta="form">
            {done ? (
              <div className="pop-in flex items-center justify-center gap-4 md:justify-start" role="status">
                <svg width="52" height="52" viewBox="0 0 52 52" className="success-ring shrink-0" aria-hidden="true">
                  <circle cx="26" cy="26" r="24" fill="#00D5E7" />
                  <path className="success-check" d="M15 27l8 8 14-17" fill="none" stroke="#071522" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <p className="text-left">
                  <span className="display block text-3xl md:text-4xl">You're in.</span>
                  <span className="text-frost">Demo only: no email was sent or stored.</span>
                </p>
              </div>
            ) : (
              <form onSubmit={submit} noValidate className="mx-auto max-w-md md:mx-0">
                <label htmlFor="drop-email" className="sr-only">
                  Email address
                </label>
                <Glass className={`flex !rounded-full p-1.5 ${error ? 'ring-1 ring-[#FF8A8A]' : 'focus-within:ring-1 focus-within:ring-cyan'}`}>
                  <input
                    id="drop-email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => (setEmail(e.target.value), error && setError(''))}
                    aria-invalid={!!error}
                    aria-describedby={error ? 'drop-error' : undefined}
                    className="min-w-0 flex-1 bg-transparent px-4 text-base text-silver placeholder:text-silver/70 focus:outline-none"
                  />
                  <PopButton type="submit" reveal={false} className="!px-5">
                    Join the Drop
                  </PopButton>
                </Glass>
                <p id="drop-error" role="alert" className="mt-2 min-h-[1.25rem] px-4 text-left text-sm text-[#FF9C9C]">
                  {error}
                </p>
              </form>
            )}
            <button
              type="button"
              onClick={() => setStores(true)}
              className="mt-1 inline-flex min-h-[44px] items-center gap-2 font-display text-lg font-bold uppercase tracking-widest text-silver underline decoration-cyan decoration-2 underline-offset-4 transition-colors hover:text-cyan"
            >
              Find a store
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
      <Modal open={stores} onClose={() => setStores(false)} title="Find a store">
        <p className="mt-3 text-base text-silver">ZERO ICE is a demo brand, so there are no stores yet. In a real launch this dialog would hold a postcode search and a map.</p>
        <PopButton reveal={false} className="mt-6 w-full" onClick={() => setStores(false)}>
          Got it
        </PopButton>
      </Modal>
    </PinSection>
  )
}
