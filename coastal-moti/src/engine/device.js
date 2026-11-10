// Device detection. Used to pick default quality and which control scheme to show.
export function isMobile() {
  const coarse = window.matchMedia?.('(pointer: coarse)').matches ?? false;
  const touch = navigator.maxTouchPoints > 0;
  const uaMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  return uaMobile || (coarse && touch);
}
