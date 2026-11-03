"use client";

import { useEffect, useState } from "react";

// Shows the preview log on screen when the URL has ?debug=1
export default function PreviewDebug() {
  const [on, setOn] = useState(false);
  const [lines, setLines] = useState([]);

  useEffect(() => {
    if (!new URLSearchParams(location.search).has("debug")) return;
    setOn(true);
    const env = [
      `UA: ${navigator.userAgent}`,
      `reducedMotion: ${matchMedia("(prefers-reduced-motion: reduce)").matches}`,
      `saveData: ${navigator.connection?.saveData ?? "n/a"}`,
      `hover: ${matchMedia("(hover: hover)").matches}`,
    ];
    const update = () => setLines([...env, ...(window.__previewLog || [])]);
    update();
    window.addEventListener("previewlog", update);
    return () => window.removeEventListener("previewlog", update);
  }, []);

  if (!on) return null;
  return (
    <div className="fixed inset-x-2 bottom-2 z-[60] max-h-[40vh] overflow-auto rounded-lg border border-white/20 bg-black/90 p-2 font-mono text-[10px] leading-tight text-green-300">
      {lines.map((l, i) => (
        <div key={i}>{l}</div>
      ))}
    </div>
  );
}
