/**
 * ALL brand figures, ratings, quotes and badges live here.
 * ZERO ICE is a fictional demo brand: everything in this file is placeholder
 * demo data. Replace it per client; no component hard-codes a number.
 */
export const DEMO_TAG = 'Demo numbers'

export interface Stat {
  value: number
  decimals?: number
  /** glued to the number, same size: "K+", "%", "+" */
  suffix?: string
  /** smaller trailing unit: "/ 5" */
  unit?: string
  label: string
  /** 0..1 fill for the progress bar */
  fill?: number
}

/** A. Trust strip */
export const trustStats: Stat[] = [
  { value: 5, suffix: '+', label: 'Years of Chill' },
  { value: 250, suffix: 'K+', label: 'Happy Customers' },
  { value: 98, suffix: '%', label: 'Would Recommend' },
  { value: 4.8, decimals: 1, unit: '/ 5', label: 'Average Rating' },
]

/** B. Journey timeline */
export const journey = {
  title: ['5 Years.', 'Zero Compromise.'],
  steps: [
    { year: '2021', text: 'The first cold idea' },
    { year: '2022', text: 'First can hits the shelves' },
    { year: '2023', text: '100K cans sold' },
    { year: '2024', text: 'Going national' },
    { year: '2025', text: 'Zero Ice Lime & Cherry in the lab' },
    { year: '2026', text: 'Today: 250K+ customers' },
  ],
}

/** C. Numbers that matter */
export const bigStats: Stat[] = [
  { value: 5, suffix: '+', label: 'Years in the game', fill: 0.5 },
  { value: 250, suffix: 'K+', label: 'Happy customers', fill: 0.82 },
  { value: 3, suffix: 'M+', label: 'Cans enjoyed', fill: 0.9 },
  { value: 40, suffix: '+', label: 'Cities served', fill: 0.64 },
  { value: 72, suffix: '%', label: 'Repeat buyers', fill: 0.72 },
  { value: 4.8, decimals: 1, unit: '/ 5', label: 'Customer rating', fill: 0.96 },
]

/** D. Recommendations */
export const recommend = { percent: 98, text: 'of customers would recommend ZERO ICE' }

export const testimonials = [
  { name: 'Maya', city: 'Austin', rating: 5, quote: 'Tastes like the first sip, every sip. My fridge has a dedicated shelf now.' },
  { name: 'Arjun', city: 'Pune', rating: 5, quote: 'I came for zero sugar. I stayed for the crack of the can.' },
  { name: 'Leo', city: 'Manchester', rating: 4, quote: 'Bold cola, clean finish. Exactly what it says on the can.' },
  { name: 'Sofia', city: 'Toronto', rating: 5, quote: 'Ice cold with pizza night is now a house rule.' },
  { name: 'Kenji', city: 'Osaka', rating: 5, quote: 'Crisp, cold and not too sweet. The can looks great on my desk too.' },
  { name: 'Zara', city: 'Dubai', rating: 4, quote: 'My whole office switched. The Lime drop cannot come soon enough.' },
]

/** Obviously fictional outlets. Never put a real publication, award or company here. */
export const badges = ['Taste Lab Weekly', 'Cold Drink Awards', 'Fit Sip Magazine', 'Campus Picks', 'The Fizz Report']

/** E. Why people love it */
export const loveCards = [
  { icon: 'snow', title: 'Ice-cold crisp', stat: '9 out of 10 say it is best served ice cold' },
  { icon: 'bolt', title: 'Bold taste, no guilt', stat: '9 out of 10 say it tastes bold' },
  { icon: 'meal', title: 'Perfect with any meal', stat: '8 out of 10 pair it with lunch or dinner' },
] as const

/** F. Community feed */
export const community = {
  tag: '#StayZeroIce',
  images: [
    { src: '/images/community/01.jpg', alt: 'ZERO ICE can hit by a cola splash' },
    { src: '/images/community/02.jpg', alt: 'Ice cubes flying past a ZERO ICE can' },
    { src: '/images/community/03.jpg', alt: 'Cola splashing over crushed ice' },
    { src: '/images/community/04.jpg', alt: 'ZERO ICE can standing in crushed ice' },
    { src: '/images/community/05.jpg', alt: 'Close-up of condensation on a ZERO ICE can' },
    { src: '/images/community/06.jpg', alt: 'ZERO ICE can in cold blue mist' },
  ],
}
