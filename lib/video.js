// Helpers that turn normal share links into embeddable player URLs.

export function getYouTubeId(url = "") {
  const patterns = [
    /youtu\.be\/([\w-]{11})/,
    /youtube\.com\/watch\?(?:.*&)?v=([\w-]{11})/,
    /youtube\.com\/(?:embed|shorts|live)\/([\w-]{11})/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}

export function getDriveId(url = "") {
  const m =
    url.match(/drive\.google\.com\/file\/d\/([\w-]+)/) ||
    url.match(/drive\.google\.com\/(?:open|uc)\?(?:.*&)?id=([\w-]+)/);
  return m ? m[1] : null;
}

/** Returns an iframe-ready URL, or null if the link is empty/unsupported. */
export function getEmbedUrl(url = "") {
  const yt = getYouTubeId(url);
  if (yt) return `https://www.youtube-nocookie.com/embed/${yt}?autoplay=1&rel=0`;
  const drive = getDriveId(url);
  if (drive) return `https://drive.google.com/file/d/${drive}/preview`;
  return null;
}

/** Custom thumbnail first, then YouTube's auto thumbnail, else null. */
export function getThumbnail(video) {
  if (video.thumbnail) return video.thumbnail;
  const yt = getYouTubeId(video.videoUrl);
  if (yt) return `https://i.ytimg.com/vi/${yt}/hqdefault.jpg`;
  return null;
}
