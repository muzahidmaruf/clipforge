import { cuePhase, easeOutCubic, easeOutQuint, easeOutBack, clamp01 } from './easing'

/**
 * Animated horizontal progress bar with big counter on top.
 *
 * Props:
 *   cue: { t, label: string, value: number (0-100) }
 *   currentTime
 *   primaryColor — bar gradient + number
 *   scale
 */
const FILL_DURATION = 1.2

export default function ProgressBar({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.5,
    holdDuration: FILL_DURATION + 1.8,
    outDuration: 0.5,
  })

  if (phase === 'idle' || phase === 'done') return null

  const inP = phase === 'in' ? progress : 1
  const outP = phase === 'out' ? progress : 0
  const localElapsed = currentTime - cue.t

  // Container entrance
  const containerT = clamp01(inP / 1.0)
  const containerScale = phase === 'out' ? 1 - outP * 0.12 : 0.85 + easeOutBack(containerT) * 0.15
  const containerOpacity = phase === 'out' ? 1 - easeOutCubic(outP) : easeOutCubic(containerT)

  // Fill runs 0.3s after container starts
  const fillStart = 0.3
  const fillElapsed = Math.max(0, localElapsed - fillStart)
  const fillT = clamp01(fillElapsed / FILL_DURATION)
  const fillEased = easeOutQuint(fillT)
  const fillPct = fillEased * cue.value // bar width in %
  const displayValue = Math.round(fillEased * cue.value)

  const rootStyle = {
    position: 'absolute',
    top: '30%',
    left: '50%',
    transform: `translate(-50%, 0) scale(${containerScale})`,
    width: '82%',
    maxWidth: `${620 * scale}px`,
    opacity: containerOpacity,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: `${18 * scale}px`,
  }

  return (
    <div style={rootStyle}>
      {/* Big counter */}
      <div
        style={{
          fontSize: `${130 * scale}px`,
          fontWeight: 900,
          lineHeight: 0.9,
          letterSpacing: '-0.03em',
          background: `linear-gradient(180deg, #ffffff 0%, ${primaryColor} 100%)`,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          filter: `drop-shadow(0 4px 22px rgba(0,0,0,0.8)) drop-shadow(0 0 28px ${primaryColor}40)`,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {displayValue}%
      </div>

      {/* Bar track */}
      <div
        style={{
          width: '100%',
          height: `${22 * scale}px`,
          background: 'rgba(0,0,0,0.55)',
          border: `1px solid rgba(255,255,255,0.12)`,
          borderRadius: `${14 * scale}px`,
          overflow: 'hidden',
          boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.5)',
          position: 'relative',
        }}
      >
        <div
          style={{
            width: `${fillPct}%`,
            height: '100%',
            background: `linear-gradient(90deg, ${primaryColor} 0%, ${primaryColor}dd 100%)`,
            boxShadow: `0 0 16px ${primaryColor}bb, inset 0 1px 0 rgba(255,255,255,0.35)`,
            borderRadius: `${14 * scale}px`,
            transition: 'none',
          }}
        />
        {/* Animated highlight that slides along the leading edge */}
        {fillT > 0 && fillT < 1 && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `calc(${fillPct}% - ${16 * scale}px)`,
              width: `${16 * scale}px`,
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent)',
              pointerEvents: 'none',
            }}
          />
        )}
      </div>

      {/* Label */}
      <div
        style={{
          fontSize: `${22 * scale}px`,
          fontWeight: 700,
          color: '#ffffff',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          textShadow: '0 2px 10px rgba(0,0,0,0.9)',
          textAlign: 'center',
        }}
      >
        {cue.label}
      </div>
    </div>
  )
}
