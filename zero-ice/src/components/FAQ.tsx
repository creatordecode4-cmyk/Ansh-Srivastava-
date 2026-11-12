import { useState } from 'react'

const ITEMS = [
  { q: 'What is ZERO ICE?', a: 'A diet cola with zero sugar and zero calories, made to be served ice cold. It is also a fictional brand, created for this demo.' },
  { q: 'What does it taste like?', a: 'Bold cola up front, then a clean, crisp finish. Best straight from the fridge or over ice.' },
  { q: 'Is it really zero sugar?', a: 'Yes. Zero sugar and zero calories per 330 ml can. The numbers on this page are sample values for demo purposes.' },
  { q: 'When do Lime and Cherry arrive?', a: 'Both are marked Coming Soon. Tap “Notify me” in the lineup to see how the sign-up would work.' },
  { q: 'Where can I buy it?', a: 'Nowhere yet. ZERO ICE is a demo brand, so there are no stores. Join the Drop to try the sign-up flow.' },
]

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0)
  return (
    <section id="faq" aria-labelledby="faq-title" className="relative z-20 bg-ink px-5 py-24 md:py-32">
      <div className="mx-auto max-w-3xl">
        <p className="eyebrow mb-2">09 · FAQ</p>
        <h2 id="faq-title" className="display text-6xl md:text-8xl">
          Cold, hard <span className="text-ice">answers.</span>
        </h2>
        <ul className="mt-10 border-t border-white/15">
          {ITEMS.map((item, i) => {
            const isOpen = open === i
            return (
              <li key={item.q} className="border-b border-white/15">
                <h3>
                  <button
                    type="button"
                    id={`faq-q-${i}`}
                    aria-expanded={isOpen}
                    aria-controls={`faq-a-${i}`}
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="flex w-full items-center justify-between gap-6 py-5 text-left font-display text-2xl font-bold uppercase tracking-wide text-white hover:text-ice md:text-3xl"
                  >
                    {item.q}
                    <span aria-hidden="true" className={`relative block h-5 w-5 shrink-0 transition-transform duration-300 ${isOpen ? 'rotate-45' : ''}`}>
                      <span className="absolute left-0 top-1/2 h-0.5 w-5 -translate-y-1/2 bg-ice" />
                      <span className="absolute left-1/2 top-0 h-5 w-0.5 -translate-x-1/2 bg-ice" />
                    </span>
                  </button>
                </h3>
                <div
                  id={`faq-a-${i}`}
                  role="region"
                  aria-labelledby={`faq-q-${i}`}
                  className={`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${isOpen ? 'grid-rows-[1fr] opacity-100' : 'invisible grid-rows-[0fr] opacity-0'}`}
                >
                  <div className="overflow-hidden">
                    <p className="max-w-2xl pb-6 text-lg leading-relaxed text-silver">{item.a}</p>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
