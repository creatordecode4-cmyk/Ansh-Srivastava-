// Small screen helpers shared by missions: fade to black, toast, objective banner, alert, cinematic bars.
export function createOverlays() {
  const $ = (id) => document.getElementById(id);
  const fadeEl = $('fade'), toastEl = $('toast'), bannerEl = $('banner'), alertEl = $('alert');
  let toastTimer = 0, bannerTimer = 0;

  return {
    // fade(true) = to black, fade(false) = back in. Resolves when the fade is done.
    fade(toBlack, ms = 400) {
      fadeEl.style.transitionDuration = `${ms}ms`;
      void fadeEl.offsetWidth;
      fadeEl.style.opacity = toBlack ? '1' : '0';
      return new Promise((resolve) => setTimeout(resolve, ms + 30));
    },
    toast(text, ms = 2200) {
      toastEl.textContent = text;
      toastEl.classList.add('on');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toastEl.classList.remove('on'), ms);
    },
    // Objective card: a big line across the screen that does not stop play.
    banner(text, ms = 4200) {
      bannerEl.textContent = text;
      bannerEl.classList.add('on');
      clearTimeout(bannerTimer);
      bannerTimer = setTimeout(() => bannerEl.classList.remove('on'), ms);
    },
    showAlert(title, sub = '') {
      $('alert-title').textContent = title;
      $('alert-sub').textContent = sub;
      alertEl.hidden = false;
    },
    hideAlert() { alertEl.hidden = true; },
    setCinematic(on) { document.body.classList.toggle('cine', on); },
  };
}
