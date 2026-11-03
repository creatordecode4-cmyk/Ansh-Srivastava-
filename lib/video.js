// Helpers that turn normal share links into something the player can use.

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

/** A video file you host yourself, e.g. "/videos/my-edit.mp4" (inside /public). */
export function isVideoFile(url = "") {
  return /\.(mp4|webm|mov)(\?.*)?$/i.test(url);
}

/**
 * What the modal should play:
 *   { type: "file",   src }  → native <video> player (files in /public/videos)
 *   { type: "iframe", src }  → YouTube / Google Drive embed
 *   null                     → no link yet
 */
export function getVideoSource(url = "") {
  if (!url) return null;
  if (isVideoFile(url)) return { type: "file", src: url };
  const yt = getYouTubeId(url);
  if (yt) return { type: "iframe", src: `https://www.youtube-nocookie.com/embed/${yt}?autoplay=1&rel=0` };
  const drive = getDriveId(url);
  if (drive) return { type: "iframe", src: `https://drive.google.com/file/d/${drive}/preview` };
  return null;
}

/** Custom thumbnail first, then YouTube's auto thumbnail, else null. */
export function getThumbnail(video) {
  if (video.thumbnail) return video.thumbnail;
  const yt = getYouTubeId(video.videoUrl);
  if (yt) return `https://img.youtube.com/vi/${yt}/hqdefault.jpg`;
  return null;
}

export function isVertical(video) {
  return video.orientation === "vertical";
}

/**
 * Muted, looping preview for the card (autoplay on scroll).
 * Google Drive can't autoplay muted previews, so Drive cards just show the thumbnail.
 */
export function getPreviewSource(url = "") {
  if (!url) return null;
  if (isVideoFile(url)) return { type: "file", src: url };
  const yt = getYouTubeId(url);
  if (yt)
    return {
      type: "iframe",
      src: `https://www.youtube-nocookie.com/embed/${yt}?autoplay=1&mute=1&loop=1&playlist=${yt}&playsinline=1&controls=0&modestbranding=1&rel=0&disablekb=1`,
    };
  return null;
}

/** Category match that ignores extra spaces / capital letters, so typos in site.js don't hide a video. */
export function sameCategory(a = "", b = "") {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}
