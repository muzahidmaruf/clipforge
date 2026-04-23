import { cuePhase, easeOutBack, easeOutCubic, easeOutElastic, clamp01 } from './easing'

/**
 * Kinetic typography — 2-5 words slam onto screen one by one.
 * Each word enters from a random direction with rotation + scale overshoot,
 * then settles. The group holds, then whole group scales out.
 *
 * Props:
 *   cue: { t, words: ["THIS", "CHANGES", "EVERYTHING"] }
 *   currentTime
 *   primaryColor
 *   scale
 */

// Deterministic per-word entrance vector based on index (so it's stable)
const ENTRY_VECTORS = [
  { x: -260, y: 40, r: -18 },
  { x: 260, y: -60, r: 16 },
  { x: -200, y: -80, r: -14 },
  { x: 220, y: 70, r: 20 },
  { x: 0, y: 180, r: 0 },
]

const PER_WORD_DURATION = 0.22 // seconds between each word landing
const WORD_IN = 0.35 // entrance duration per word

export default function KineticSlam({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const words = cue.words || []
  const count = words.length
  const groupInDuration = PER_WORD_DURATION * count + (WORD_IN - PER_WORD_DURATION)
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: groupInDuration,
    holdDuration: 1.6,
    outDuration: 0.4,
  })

  if (phase === 'idle' || phase === 'done') return null

  const outP = phase === 'out' ? progress : 0
  const groupOpacity = phase === 'out' ? 1 - easeOutCubic(outP) : 1
  const groupScale = phase === 'out' ? 1 + outP * 0.12 : 1

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: `${10 * scale}px`,
        pointerEvents: 'none',
        fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
        opacity: groupOpacity,
        transform: `scale(${groupScale})`,
      }}
    >
      {words.map((word, idx) => {
        const localStart = cue.t + idx * PER_WORD_DURATION
        const localElapsed = currentTime - localStart
        const t = clamp01(localElapsed / WORD_IN)

        // Not yet landing: hidden
        if (currentTime < localStart) {
          return <div key={idx} style={{ height: `${86 * scale}px` }} />
        }

        const vec = ENTRY_VECTORS[idx % ENTRY_VECTORS.length]
        const eased = easeOutElastic(t)
        const settleT = easeOutBack(t, 2.2)

        const x = (1 - settleT) * vec.x
        const y = (1 - settleT) * vec.y
        const r = (1 - settleT) * vec.r
        const s = 0.2 + eased * 0.95 // overshoots slightly past 1

        // Color: last word gets primary color for emphasis
        const isFinal = idx === count - 1
        const color = isFinal ? primaryColor : '#ffffff'

        const baseSize = isFinal ? 110 : 92
        return (
          <div
            key={idx}
            style={{
              fontSize: `${baseSize * scale}px`,
              fontWeight: 900,
              lineHeight: 0.92,
              letterSpacing: '-0.02em',
              color,
              textShadow:
                `0 6px 24px rgba(0,0,0,0.9), 0 0 2px rgba(0,0,0,1)${
                  isFinal ? `, 0 0 28px ${primaryColor}66` : ''
                }`,
              textTransform: 'uppercase',
              transform: `translate(${x}px, ${y}px) rotate(${r}deg) scale(${s})`,
              willChange: 'transform',
            }}
          >
            {word}
          </div>
        )
      })}
    </div>
  )
}
