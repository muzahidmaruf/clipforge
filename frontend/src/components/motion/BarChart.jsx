import { cuePhase, easeOutCubic, easeOutQuint, easeOutBack, clamp01 } from './easing'

/**
 * Animated horizontal bar chart (2-4 bars). Each bar grows with a stagger.
 * Largest value gets primary color; others get white.
 *
 * Props:
 *   cue: { t, title?: string, bars: [{label, value}] }
 *   currentTime
 *   primaryColor
 *   scale
 */

const BAR_STAGGER = 0.15
const BAR_GROW = 0.8

export default function BarChart({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const bars = cue.bars || []
  const maxValue = Math.max(...bars.map((b) => b.value))
  const maxIdx = bars.findIndex((b) => b.value === maxValue)
  const hasTitle = !!cue.title

  const totalIn = (hasTitle ? 0.3 : 0) + BAR_STAGGER * bars.length + BAR_GROW
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: totalIn,
    holdDuration: 2.4,
    outDuration: 0.5,
  })
  if (phase === 'idle' || phase === 'done') return null

  const outP = phase === 'out' ? progress : 0
  const containerOpacity = phase === 'out' ? 1 - easeOutCubic(outP) : 1
  const containerY = phase === 'out' ? outP * 14 : 0

  // Title
  let titleOpacity = 0
  let titleScale = 0.9
  if (hasTitle) {
    const titleT = clamp01((currentTime - cue.t) / 0.45)
    titleOpacity = easeOutCubic(titleT)
    titleScale = 0.9 + easeOutBack(titleT) * 0.1
  }

  const rootStyle = {
    position: 'absolute',
    top: '22%',
    left: '50%',
    transform: `translate(-50%, ${containerY}px)`,
    width: '84%',
    maxWidth: `${640 * scale}px`,
    opacity: containerOpacity,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    gap: `${14 * scale}px`,
  }

  return (
    <div style={rootStyle}>
      {hasTitle && (
        <div
          style={{
            fontSize: `${26 * scale}px`,
            fontWeight: 800,
            color: '#ffffff',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            textAlign: 'center',
            opacity: titleOpacity,
            transform: `scale(${titleScale})`,
            textShadow: '0 2px 12px rgba(0,0,0,0.9)',
            marginBottom: `${10 * scale}px`,
          }}
        >
          {cue.title}
        </div>
      )}

      {bars.map((b, idx) => {
        const isMax = idx === maxIdx
        const barColor = isMax ? primaryColor : '#ffffff'
        const textColor = isMax ? primaryColor : '#dfe3ea'

        const localStart = cue.t + (hasTitle ? 0.3 : 0) + idx * BAR_STAGGER
        const growT = clamp01((currentTime - localStart) / BAR_GROW)
        const growEased = easeOutQuint(growT)
        if (currentTime < localStart) {
          return <div key={idx} style={{ height: `${48 * scale}px` }} />
        }

        const targetPct = (b.value / maxValue) * 100
        const width = targetPct * growEased
        const displayValue =
          Number.isInteger(b.value) ? Math.round(b.value * growEased).toString() : (b.value * growEased).toFixed(1)

        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: `${14 * scale}px` }}>
            {/* Label on left */}
            <div
              style={{
                width: `${84 * scale}px`,
                flexShrink: 0,
                fontSize: `${18 * scale}px`,
                fontWeight: 700,
                color: '#ffffff',
                textShadow: '0 2px 8px rgba(0,0,0,0.9)',
                textAlign: 'right',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {b.label}
            </div>

            {/* Bar track */}
            <div style={{ flex: 1, position: 'relative' }}>
              <div
                style={{
                  height: `${32 * scale}px`,
                  background: 'rgba(0,0,0,0.55)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: `${6 * scale}px`,
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    width: `${width}%`,
                    height: '100%',
                    background: isMax
                      ? `linear-gradient(90deg, ${primaryColor} 0%, ${primaryColor}ee 100%)`
                      : 'linear-gradient(90deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.7) 100%)',
                    boxShadow: isMax
                      ? `0 0 14px ${primaryColor}99, inset 0 1px 0 rgba(255,255,255,0.35)`
                      : 'inset 0 1px 0 rgba(255,255,255,0.45)',
                    borderRadius: `${6 * scale}px`,
                  }}
                />
              </div>
            </div>

            {/* Value on right */}
            <div
              style={{
                width: `${70 * scale}px`,
                flexShrink: 0,
                fontSize: `${26 * scale}px`,
                fontWeight: 900,
                color: textColor,
                textAlign: 'left',
                fontVariantNumeric: 'tabular-nums',
                textShadow: '0 2px 10px rgba(0,0,0,0.9)',
                letterSpacing: '-0.01em',
              }}
            >
              {displayValue}
            </div>
          </div>
        )
      })}
    </div>
  )
}
