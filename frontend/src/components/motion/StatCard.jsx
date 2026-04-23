import { cuePhase, easeOutBack, easeOutCubic, easeOutQuint, clamp01 } from './easing'

/**
 * Big number pop. If the number is purely numeric (with optional % or $),
 * it counts up with a spring. Otherwise it scales in.
 *
 * Props:
 *   cue: { t, number, label }
 *   currentTime: seconds
 *   primaryColor: accent / border
 *   scale: responsive scale (1 = 1080×1920 reference)
 */

// Parse "80%", "$2.4B", "10,000" → { prefix, numeric, suffix }
const parseNumber = (raw) => {
  const match = String(raw).match(/^(\D*)([\d,]+(?:\.\d+)?)(.*)$/)
  if (!match) return { prefix: '', numeric: null, suffix: raw, isNumeric: false }
  const [, prefix, digits, suffix] = match
  const numeric = parseFloat(digits.replace(/,/g, ''))
  if (isNaN(numeric)) return { prefix: '', numeric: null, suffix: raw, isNumeric: false }
  // Preserve decimal places and thousands separators for display
  const hasDecimal = digits.includes('.')
  const decimals = hasDecimal ? digits.split('.')[1].length : 0
  const hasCommas = digits.includes(',')
  return { prefix, numeric, suffix, isNumeric: true, decimals, hasCommas }
}

const formatCount = (value, { decimals, hasCommas }) => {
  const rounded = decimals > 0 ? value.toFixed(decimals) : Math.round(value).toString()
  if (!hasCommas) return rounded
  const [intPart, decPart] = rounded.split('.')
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return decPart ? `${withCommas}.${decPart}` : withCommas
}

export default function StatCard({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.8,
    holdDuration: 2.5,
    outDuration: 0.5,
  })

  if (phase === 'idle' || phase === 'done') return null

  const inP = phase === 'in' ? progress : 1
  const outP = phase === 'out' ? progress : 0

  // Card scales in with a spring
  const cardT = clamp01(inP / 0.5)
  const cardScale = phase === 'out' ? 1 - outP * 0.15 : 0.6 + easeOutBack(cardT, 2.0) * 0.4
  // Counter runs during in + first bit of hold (0 → 1.0 total)
  const countT = clamp01(inP / 0.9)
  const countEased = easeOutQuint(countT)

  const cardOpacity = phase === 'out' ? 1 - easeOutCubic(outP) : easeOutCubic(cardT)

  const parsed = parseNumber(cue.number)
  let displayNumber = cue.number
  if (parsed.isNumeric) {
    const v = parsed.numeric * countEased
    displayNumber = `${parsed.prefix}${formatCount(v, parsed)}${parsed.suffix}`
  }

  // Label fades in slightly after the number
  const labelT = clamp01((inP - 0.35) / 0.4)

  const rootStyle = {
    position: 'absolute',
    top: '22%',
    left: '50%',
    transform: `translate(-50%, 0) scale(${cardScale})`,
    opacity: cardOpacity,
    pointerEvents: 'none',
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    textAlign: 'center',
  }

  const numberStyle = {
    fontSize: `${140 * scale}px`,
    fontWeight: 900,
    lineHeight: 0.95,
    letterSpacing: '-0.03em',
    background: `linear-gradient(180deg, #ffffff 0%, ${primaryColor} 100%)`,
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
    filter: `drop-shadow(0 4px 24px rgba(0,0,0,0.75)) drop-shadow(0 0 32px ${primaryColor}40)`,
    fontVariantNumeric: 'tabular-nums',
  }

  const labelStyle = {
    marginTop: `${14 * scale}px`,
    fontSize: `${22 * scale}px`,
    fontWeight: 700,
    color: '#ffffff',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    opacity: labelT,
    transform: `translateY(${(1 - easeOutCubic(labelT)) * 10}px)`,
    textShadow: '0 2px 14px rgba(0,0,0,0.9)',
    padding: `${8 * scale}px ${16 * scale}px`,
    display: 'inline-block',
    background: 'rgba(0,0,0,0.35)',
    backdropFilter: 'blur(8px)',
    borderRadius: `${8 * scale}px`,
    border: `1px solid ${primaryColor}40`,
  }

  return (
    <div style={rootStyle}>
      <div style={numberStyle}>{displayNumber}</div>
      <div style={labelStyle}>{cue.label}</div>
    </div>
  )
}
