import { PopButton, Reveal } from '../lib/motion'
import { community } from '../data/brandStats'
import { DemoTag } from './CountUp'
import { FlowSection } from './PinSection'

export function Community() {
  return (
    <FlowSection id="community" glow="left-[-8%] top-0 h-[60%] w-[60%]">
      <div>
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <Reveal className="max-w-[72%] md:max-w-none">
            <p className="mb-3 text-sm font-medium text-silver/70">{community.tag}</p>
            <h2 id="community-title" className="heading text-[2rem] md:text-5xl">
              As Seen <span>Around Town.</span>
            </h2>
            <DemoTag label="Demo content" className="mt-4" />
          </Reveal>
          <PopButton href="#community" delay={0.2} onClick={(e) => e.preventDefault()} aria-label="Follow us (demo link)" className="self-start md:self-auto">
            Follow us
          </PopButton>
        </div>
        <ul className="mt-8 grid grid-cols-3 gap-2 md:mt-12 md:grid-cols-6 md:gap-4">
          {community.images.map((img, i) => (
            <Reveal as="li" kind="pop" delay={i * 0.08} key={img.src}>
              <figure className="group relative aspect-square overflow-hidden rounded-xl border border-frost/15">
                <img src={img.src} alt={img.alt} width={480} height={480} loading="lazy" decoding="async" className="h-full w-full object-cover saturate-[0.55] transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-midnight/90 via-transparent to-transparent" aria-hidden="true" />
                <figcaption className="absolute bottom-1.5 left-2 font-sans text-xs font-medium text-silver md:bottom-2.5 md:left-3 md:text-sm">{community.tag}</figcaption>
              </figure>
            </Reveal>
          ))}
        </ul>
      </div>
    </FlowSection>
  )
}
