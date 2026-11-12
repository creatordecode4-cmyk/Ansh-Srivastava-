/** Per-frame state of the /showcase scene (written by the rig, read by the laptop + captions). */
export const stage = {
  /** raw scroll progress 0..1 */
  target: 0,
  /** smoothed progress 0..1 */
  p: 0,
  /** lid angle in radians (0 = closed) */
  lid: 0,
}

export const LID_OPEN = (110 * Math.PI) / 180
