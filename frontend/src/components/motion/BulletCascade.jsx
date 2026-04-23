import { cuePhase, easeOutBack, easeOutCubic, clamp01 } from './easing'

/**
 * Vertical list that cascades in. Each item slides from the right with a
 * small overshoot + bullet dot grows first. Optional title above.
 *
 * Props:
 *   cue: { t, items: string[], title?: string }
 *   currentTime
 *   primaryColor — bullet dot + title accent
 *   scale
 */

const STAGGER = 0.2 // seconds between items
const ITEM_IN = 0.4 // each item entrance duration
const TITLE_IN = 0.5

export default function BulletCascade({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const items = cue.items || []
  const hasTitle = !!cue.title

  const titleLead = hasTitle ? 0.3 : 0
  const totalIn = titleLead + STAGGER * items.length + (ITEM_IN - STAGGER)
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: totalIn,
    holdDuration: 2.6,
    outDuration: 0.45,
  })

  if (phase === 'idle' || phase === 'done') return null

  const outP = phase === 'out' ? progress : 0
  const groupOpacity = phase === 'out' ? 1 - easeOutCubic(outP) : 1
  const groupX = phase === 'out' ? -outP * 30 : 0

  // Title
  let titleOpacity = 0
  let titleX = -20
  if (hasTitle) {
    const titleT = clamp01((currentTime - cue.t) / TITLE_IN)
    titleOpacity = easeOutCubic(titleT)
    titleX = (1 - easeOutBack(titleT)) * -30
  }

  const rootStyle = {
    position: 'absolute',
    top: '28%',
    left: `${8 * scale}%`,
    right: `${8 * scale}%`,
    display: 'flex',
    flexDirection: 'column',
    gap: `${18 * scale}px`,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    opacity: groupOpacity,
    transform: `translateX(${groupX}px)`,
  }

  return (
    <div style={rootStyle}>
      {hasTitle && (
        <div
          style={{
            fontSize: `${24 * scale}px`,
            fontWeight: 700,
            color: primaryColor,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            opacity: titleOpacity,
            transform: `translateX(${titleX}px)`,
            textShadow: '0 2px 10px rgba(0,0,0,0.9)',
            marginBottom: `${6 * scale}px`,
          }}
        >
          {cue.title}
        </div>
      )}

      {items.map((item, idx) => {
        const localStart = cue.t + titleLead + idx * STAGGER
        const localT = clamp01((currentTime - localStart) / ITEM_IN)
        if (currentTime < localStart) {
          return <div key={idx} style={{ height: `${54 * scale}px` }} />
        }

        const settleT = easeOutBack(localT, 1.6)
        const slideX = (1 - settleT) * 60
        const opacity = easeOutCubic(localT)
        const dotScale = clamp01(localT / 0.4)

        return (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: `${18 * scale}px`,
              opacity,
              transform: `translateX(${slideX}px)`,
            }}
          >
            {/* Animated bullet dot */}
            <div
              style={{
                width: `${18 * scale}px`,
                height: `${18 * scale}px`,
                borderRadius: '50%',
                background: primaryColor,
                flexShrink: 0,
                transform: `scale(${dotScale})`,
                boxShadow: `0 0 12px ${primaryColor}aa`,
              }}
            />

            <div
              style={{
                fontSize: `${34 * scale}px`,
                fontWeight: 800,
                color: '#ffffff',
                letterSpacing: '-0.005em',
                lineHeight: 1.05,
                textShadow: '0 2px 14px rgba(0,0,0,0.9), 0 0 2px rgba(0,0,0,1)',
              }}
            >
              {item}
            </div>
          </div>
        )
      })}
    </div>
  )
}
