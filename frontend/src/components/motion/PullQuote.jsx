import { cuePhase, easeOutBack, easeOutCubic, clamp01 } from './easing'

/**
 * Full-screen pull quote. Dims the video, draws big opening quote mark,
 * scales the text in with a spring. Exits with a fade + scale-out.
 *
 * Props:
 *   cue: { t, text }
 *   currentTime: seconds
 *   primaryColor: hex — quote mark accent
 *   scale: responsive scale
 */
export default function PullQuote({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.7,
    holdDuration: 3.2,
    outDuration: 0.55,
  })

  if (phase === 'idle' || phase === 'done') return null

  const inP = phase === 'in' ? progress : 1
  const outP = phase === 'out' ? progress : 0

  // Stagger: backdrop dims first (0→0.4), quote mark pops (0.15→0.5), text scales (0.3→0.9)
  const dimT = clamp01(inP / 0.4)
  const markT = clamp01((inP - 0.15) / 0.35)
  const textT = clamp01((inP - 0.3) / 0.6)

  const dimOpacity =
    phase === 'out'
      ? (1 - outP) * 0.55
      : dimT * 0.55

  const markScale = phase === 'out' ? 1 - outP * 0.3 : easeOutBack(markT, 2.2)
  const markOpacity = phase === 'out' ? 1 - outP : clamp01(markT * 1.2)

  const textScale = phase === 'out' ? 1 - outP * 0.1 : 0.9 + easeOutBack(textT, 1.6) * 0.1
  const textY = phase === 'out' ? -outP * 12 : (1 - easeOutCubic(textT)) * 18
  const textOpacity = phase === 'out' ? 1 - outP : easeOutCubic(textT)

  // Animated backdrop: dark radial vignette + slow-rotating colored gradient
  // for a cinematic cross-light feel. Angle advances over time.
  const elapsed = Math.max(0, currentTime - cue.t)
  const angle = (elapsed * 12) % 360 // slow 30s revolution
  const hint = `${primaryColor}22` // 13% alpha tint

  const backdropStyle = {
    position: 'absolute',
    inset: 0,
    background: `
      radial-gradient(ellipse at center, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.55) 65%, rgba(0,0,0,0.3) 100%),
      conic-gradient(from ${angle}deg at 50% 50%, ${hint}, transparent 25%, ${hint} 50%, transparent 75%, ${hint})
    `,
    opacity: dimOpacity,
    pointerEvents: 'none',
    transition: 'none',
  }

  // Two slow-drifting light orbs behind the text for depth
  const orbT = elapsed * 0.5
  const orb1Style = {
    position: 'absolute',
    left: `${35 + Math.sin(orbT) * 8}%`,
    top: `${30 + Math.cos(orbT * 0.7) * 6}%`,
    width: '40%',
    height: '40%',
    borderRadius: '50%',
    background: `radial-gradient(circle at center, ${primaryColor}26 0%, transparent 60%)`,
    opacity: dimOpacity * 1.2,
    pointerEvents: 'none',
    filter: 'blur(30px)',
  }
  const orb2Style = {
    position: 'absolute',
    right: `${25 + Math.cos(orbT * 0.9) * 8}%`,
    bottom: `${30 + Math.sin(orbT * 1.2) * 6}%`,
    width: '45%',
    height: '45%',
    borderRadius: '50%',
    background: `radial-gradient(circle at center, rgba(255,255,255,0.14) 0%, transparent 60%)`,
    opacity: dimOpacity * 1.1,
    pointerEvents: 'none',
    filter: 'blur(40px)',
  }

  const wrapStyle = {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: `${32 * scale}px`,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
  }

  const markStyle = {
    fontSize: `${180 * scale}px`,
    lineHeight: 0.6,
    color: primaryColor,
    opacity: markOpacity,
    transform: `scale(${markScale}) translateY(${20 * scale}px)`,
    fontFamily: 'Georgia, "Times New Roman", serif',
    fontWeight: 900,
    filter: `drop-shadow(0 0 20px ${primaryColor}60)`,
    marginBottom: `${-30 * scale}px`,
    userSelect: 'none',
  }

  const quoteStyle = {
    fontSize: `${46 * scale}px`,
    fontWeight: 800,
    lineHeight: 1.15,
    textAlign: 'center',
    color: '#ffffff',
    letterSpacing: '-0.01em',
    maxWidth: '92%',
    textShadow: '0 4px 24px rgba(0,0,0,0.95), 0 0 2px rgba(0,0,0,1)',
    opacity: textOpacity,
    transform: `translateY(${textY}px) scale(${textScale})`,
  }

  // Bottom accent line
  const lineWidth = clamp01((inP - 0.5) / 0.4) * 100
  const lineStyle = {
    marginTop: `${24 * scale}px`,
    height: `${3 * scale}px`,
    width: `${lineWidth * 0.4}%`,
    background: primaryColor,
    borderRadius: `${2 * scale}px`,
    opacity: textOpacity,
    boxShadow: `0 0 12px ${primaryColor}99`,
  }

  return (
    <>
      <div style={backdropStyle} />
      <div style={orb1Style} />
      <div style={orb2Style} />
      <div style={wrapStyle}>
        <div style={markStyle}>“</div>
        <div style={quoteStyle}>{cue.text}</div>
        <div style={lineStyle} />
      </div>
    </>
  )
}
