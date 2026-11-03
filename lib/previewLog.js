// Tiny logger for the video previews.
// Always logs to the browser console; open the site with ?debug=1 to also see it on screen
// (handy on a phone, where you can't open DevTools).
export function previewLog(level, ...args) {
  const msg = args.map((a) => (typeof a === "string" ? a : a?.message || JSON.stringify(a))).join(" ");
  (console[level] || console.log)("[preview]", ...args);
  if (typeof window === "undefined") return;
  window.__previewLog = (window.__previewLog || []).slice(-40);
  window.__previewLog.push(`${new Date().toLocaleTimeString()} ${level.toUpperCase()} ${msg}`);
  window.dispatchEvent(new Event("previewlog"));
}
