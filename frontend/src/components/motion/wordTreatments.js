// Per-word visual treatments. Each function takes a progress value in [0, ∞]
// (0 = treatment just triggered, 1 = end of treatment duration) and returns
// partial inline style + optional backdrop/decorator elements.
//
// The CaptionedPlayer merges the returned `style` into the word span and
// renders the `decorators` inside/around it.

import { clamp01, easeOutCubic, easeOutBack, easeOutElastic } from './easing'

const DEFAULT_DURATION = 0.9 // seconds

// Normalize a word's text for matching (strip punctuation, lowercase)
export const normalizeWord = (s) =>
  (s || '').toLowerCase().replace(/[.,!?;:()[\]{}"'`""]/g, '').trim()

/**
 * Given a list of word_treatment cues and the current time, return a map:
 *   { "normalized word::approxTimeBucket": { treatment, progress } }
 * We key by word + time bucket so a word repeated at different moments stays
 * independent. Time bucket = round(t) to reduce false matches for near-ties.
 */
export const activeTreatments = (cues, currentTime, windowDuration = DEFAULT_DURATION) => {
  const map = new Map()
  for (const cue of cues || []) {
    if (cue.type !== 'word_treatment') continue
    const elapsed = currentTime - cue.t
    if (elapsed < -0.05 || elapsed > windowDuration) continue
    const progress = clamp01(elapsed / windowDuration)
    const key = `${normalizeWord(cue.word)}::${Math.round(cue.t)}`
    map.set(key, { treatment: cue.treatment, progress, cue })
  }
  return map
}

/**
 * Match a caption word to an active treatment. The phrase's wordStart is the
 * Whisper-reported start of this word (seconds from clip start). We look up
 * by normalized text + nearest bucket.
 */
export const matchTreatment = (activeMap, wordText, wordStart) => {
  const normalized = normalizeWord(wordText)
  // Check a 2-second window of buckets (this word could be ±1s from cue t)
  for (const offset of [0, -1, 1, -2, 2]) {
    const bucket = Math.round(wordStart) + offset
    const key = `${normalized}::${bucket}`
    if (activeMap.has(key)) return activeMap.get(key)
  }
  return null
}

// ---------------------------------------------------------------------------
// Treatment renderers. Each returns { style, decorators, containerStyle }.
// - style: merged into the word <span>
// - decorators: JSX children rendered INSIDE the span (absolutely positioned)
// - containerStyle: merged into the word's wrapping container (if the word
//   needs extra layout space)
// ---------------------------------------------------------------------------

export const applyTreatment = (treatment, progress, primaryColor) => {
  const p = clamp01(progress)
  // Bell curve for treatments that peak and return
  const bell = 1 - Math.abs(2 * p - 1)

  if (treatment === 'highlight') {
    // Yellow highlighter swipes in L→R, fills, then stays behind the word
    const swipe = easeOutCubic(clamp01(p / 0.35))
    return {
      style: {
        position: 'relative',
        color: p < 0.35 ? undefined : '#111',
        transition: 'color 80ms linear',
      },
      decorators: [
        {
          key: 'hl',
          style: {
            position: 'absolute',
            left: '-0.08em',
            right: '-0.08em',
            top: '6%',
            bottom: '10%',
            background: primaryColor,
            transformOrigin: 'left center',
            transform: `scaleX(${swipe})`,
            borderRadius: '3px',
            zIndex: -1,
            boxShadow: `0 0 8px ${primaryColor}aa`,
          },
        },
      ],
    }
  }

  if (treatment === 'scale_pop') {
    // Scales 1 → 2.2 → 1.1
    let scale
    if (p < 0.25) scale = 1 + easeOutBack(p / 0.25, 2) * 1.2
    else if (p < 0.6) scale = 2.2 - ((p - 0.25) / 0.35) * 1.1
    else scale = 1.1
    return {
      style: {
        transform: `scale(${scale})`,
        color: primaryColor,
        transition: 'none',
        textShadow: `0 0 ${8 + bell * 18}px ${primaryColor}99, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000`,
        zIndex: 2,
      },
    }
  }

  if (treatment === 'shake') {
    // Rapid horizontal tremor, dampening out
    const shake = Math.sin(p * Math.PI * 16) * 6 * (1 - p)
    const shakeY = Math.cos(p * Math.PI * 22) * 3 * (1 - p)
    return {
      style: {
        transform: `translate(${shake}px, ${shakeY}px)`,
        color: p < 0.6 ? '#ff4d4d' : undefined,
        transition: 'color 140ms linear',
        textShadow: `0 0 ${bell * 16}px #ff4d4daa, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000`,
      },
    }
  }

  if (treatment === 'strikethrough') {
    // Line draws through from left to right, word fades to gray
    const lineT = easeOutCubic(clamp01(p / 0.45))
    const opacity = p < 0.45 ? 1 : 1 - (p - 0.45) * 0.35
    return {
      style: {
        position: 'relative',
        opacity,
        color: p > 0.5 ? '#888' : undefined,
        transition: 'color 140ms linear',
      },
      decorators: [
        {
          key: 'strike',
          style: {
            position: 'absolute',
            left: '-0.05em',
            right: `calc(${(1 - lineT) * 100}% - 0.05em)`,
            top: '50%',
            height: '6px',
            background: '#ff3333',
            transform: 'translateY(-50%) rotate(-2deg)',
            boxShadow: '0 0 8px #ff3333aa',
            borderRadius: '2px',
            zIndex: 3,
          },
        },
      ],
    }
  }

  if (treatment === 'glow_pulse') {
    // Pulsing halo that peaks mid-treatment
    const intensity = bell * 1.2
    return {
      style: {
        color: primaryColor,
        textShadow: `
          0 0 ${4 + intensity * 20}px ${primaryColor},
          0 0 ${8 + intensity * 40}px ${primaryColor}cc,
          0 0 ${16 + intensity * 60}px ${primaryColor}66,
          2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000
        `,
        transform: `scale(${1 + bell * 0.12})`,
        transition: 'none',
      },
    }
  }

  if (treatment === 'color_flash') {
    // Flash primary color then fade back
    const flash = bell
    return {
      style: {
        color: flash > 0.5 ? primaryColor : undefined,
        transform: `scale(${1 + bell * 0.08})`,
        transition: 'color 120ms linear',
      },
    }
  }

  if (treatment === 'stamp') {
    // Rotate in from -25°, scale 2 → 1, with impact bounce
    const t = easeOutBack(clamp01(p / 0.4), 2.2)
    const rot = (1 - t) * -25
    const scale = 0.5 + t * 1.1 // peaks slightly above 1
    const finalScale = p > 0.4 ? 1 + (1 - clamp01((p - 0.4) / 0.4)) * 0.15 : scale
    return {
      style: {
        transform: `rotate(${rot * (1 - Math.min(1, (p - 0.4) / 0.4) * 0.4)}deg) scale(${finalScale})`,
        color: '#ff2222',
        border: p > 0.3 ? '4px solid #ff2222' : '0 solid #ff2222',
        padding: p > 0.3 ? '4px 12px' : '0 0',
        borderRadius: '6px',
        textShadow: '0 2px 6px rgba(0,0,0,0.8)',
        letterSpacing: '0.06em',
        transition: 'border 120ms linear, padding 120ms linear',
        zIndex: 2,
      },
    }
  }

  if (treatment === 'drop') {
    // Falls from above with impact + compression
    let y, scaleY
    if (p < 0.35) {
      // falling
      const t = easeOutCubic(p / 0.35)
      y = (1 - t) * -80
      scaleY = 0.7 + t * 0.3
    } else if (p < 0.55) {
      // impact squish
      const t = (p - 0.35) / 0.2
      y = 0
      scaleY = 1 - (1 - Math.abs(2 * t - 1)) * 0.25
    } else {
      y = 0
      scaleY = 1
    }
    return {
      style: {
        transform: `translateY(${y}px) scaleY(${scaleY})`,
        transition: 'none',
      },
    }
  }

  if (treatment === 'rise') {
    // Rises up, pulling light trails
    const t = easeOutCubic(clamp01(p / 0.7))
    const y = (1 - t) * 40
    const opacity = t
    return {
      style: {
        transform: `translateY(${y}px)`,
        color: primaryColor,
        opacity: 0.4 + opacity * 0.6,
        textShadow: `0 ${8 + t * 16}px ${16 + t * 24}px ${primaryColor}66, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000`,
      },
    }
  }

  if (treatment === 'underline_draw') {
    const lineT = easeOutCubic(clamp01(p / 0.5))
    return {
      style: { position: 'relative' },
      decorators: [
        {
          key: 'u',
          style: {
            position: 'absolute',
            left: 0,
            right: `${(1 - lineT) * 100}%`,
            bottom: '-4px',
            height: '4px',
            background: `repeating-linear-gradient(90deg, ${primaryColor} 0, ${primaryColor} 6px, transparent 6px, transparent 10px)`,
            boxShadow: `0 0 6px ${primaryColor}99`,
            zIndex: 2,
          },
        },
      ],
    }
  }

  if (treatment === 'blur_reveal') {
    // Blurred + transparent → sharpens into focus
    const t = easeOutCubic(clamp01(p / 0.5))
    const blur = (1 - t) * 14
    return {
      style: {
        filter: `blur(${blur}px)`,
        opacity: 0.3 + t * 0.7,
        transform: `scale(${0.85 + t * 0.15})`,
        transition: 'none',
      },
    }
  }

  if (treatment === 'chromatic') {
    // RGB-split glitch. Achieved via layered text-shadows offsetting R and B channels
    const mag = bell * 8
    return {
      style: {
        textShadow: `
          ${mag}px 0 0 #ff0066cc,
          -${mag}px 0 0 #00ccffcc,
          2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000
        `,
        transform: `translateX(${Math.sin(p * Math.PI * 20) * 2 * bell}px)`,
      },
    }
  }

  return { style: {}, decorators: [] }
}
