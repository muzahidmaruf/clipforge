import { cuePhase, easeOutCubic, easeOutBack, clamp01 } from './easing'

/**
 * Broadcast-style lower third. Slides in from left with a bright accent bar
 * that grows before the text reveals. Exits with a fade + slight drop.
 *
 * Props:
 *   cue: { t, title, sub }
 *   currentTime: seconds
 *   primaryColor: hex — accent bar + underline
 *   scale: number — uniform scale factor for the whole graphic (responsive)
 */
export default function LowerThird({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.7,
    holdDuration: 3.0,
    outDuration: 0.45,
  })

  if (phase === 'idle' || phase === 'done') return null

  // Timings within the entrance:
  //  0.00 → 0.25  accent bar grows L→R
  //  0.20 → 0.55  title slides in from left
  //  0.40 → 0.80  subtitle fades in
  const inP = phase === 'in' ? progress : 1
  const outP = phase === 'out' ? progress : 0

  const barT = clamp01(inP / 0.25)
  const titleT = clamp01((inP - 0.2) / 0.35)
  const subT = clamp01((inP - 0.4) / 0.4)

  const barWidth = easeOutCubic(barT)
  const titleX = (1 - easeOutBack(titleT)) * -40 // px
  const titleOpacity = titleT
  const subOpacity = subT

  // Exit
  const exitOpacity = 1 - easeOutCubic(outP)
  const exitY = easeOutCubic(outP) * 12

  const rootStyle = {
    position: 'absolute',
    left: `${6 * scale}%`,
    bottom: `${10 * scale}%`,
    display: 'flex',
    alignItems: 'center',
    gap: `${14 * scale}px`,
    opacity: exitOpacity,
    transform: `translateY(${exitY}px)`,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
  }

  return (
    <div style={rootStyle}>
      {/* Accent bar (grows L→R, colored) */}
      <div
        style={{
          width: `${6 * scale}px`,
          height: `${60 * scale}px`,
          background: `linear-gradient(180deg, ${primaryColor} 0%, ${primaryColor}dd 100%)`,
          boxShadow: `0 0 12px ${primaryColor}80`,
          transformOrigin: 'top center',
          transform: `scaleY(${barWidth})`,
          borderRadius: `${3 * scale}px`,
        }}
      />

      {/* Text block */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: `${4 * scale}px` }}>
        <div
          style={{
            fontSize: `${26 * scale}px`,
            fontWeight: 900,
            letterSpacing: '0.04em',
            color: '#ffffff',
            textShadow: '0 2px 12px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,1)',
            transform: `translateX(${titleX}px)`,
            opacity: titleOpacity,
            whiteSpace: 'nowrap',
          }}
        >
          {cue.title}
        </div>
        <div
          style={{
            fontSize: `${15 * scale}px`,
            fontWeight: 500,
            letterSpacing: '0.02em',
            color: primaryColor,
            textShadow: '0 2px 10px rgba(0,0,0,0.9)',
            opacity: subOpacity,
            whiteSpace: 'nowrap',
          }}
        >
          {cue.sub}
        </div>
      </div>
    </div>
  )
}
