// Easing + spring helpers shared by motion components.
// All functions take a normalized progress value in [0, 1] and return [0, 1].

export const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)
export const easeOutQuint = (t) => 1 - Math.pow(1 - t, 5)
export const easeInOutCubic = (t) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

// easeOutBack — overshoots then settles (Spring-like without runtime cost)
export const easeOutBack = (t, overshoot = 1.7) => {
  const c1 = overshoot
  const c3 = c1 + 1
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2)
}

// easeOutElastic — bouncy settle
export const easeOutElastic = (t) => {
  if (t === 0 || t === 1) return t
  const c4 = (2 * Math.PI) / 3
  return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1
}

// Clamp 0..1
export const clamp01 = (v) => Math.max(0, Math.min(1, v))

/**
 * Time a cue's life given the video's currentTime and the cue's start `t`.
 * Returns { progress, phase } where phase is 'in' | 'hold' | 'out' | 'idle' | 'done'.
 */
export const cuePhase = (currentTime, cueT, {
  inDuration = 0.6,
  holdDuration = 2.8,
  outDuration = 0.5,
} = {}) => {
  const elapsed = currentTime - cueT
  const total = inDuration + holdDuration + outDuration
  if (elapsed < 0) return { phase: 'idle', progress: 0, elapsed, total }
  if (elapsed >= total) return { phase: 'done', progress: 1, elapsed, total }
  if (elapsed < inDuration) {
    return { phase: 'in', progress: elapsed / inDuration, elapsed, total }
  }
  if (elapsed < inDuration + holdDuration) {
    return { phase: 'hold', progress: 1, elapsed, total }
  }
  return {
    phase: 'out',
    progress: (elapsed - inDuration - holdDuration) / outDuration,
    elapsed,
    total,
  }
}
