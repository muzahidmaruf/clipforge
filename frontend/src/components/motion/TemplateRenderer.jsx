import { useEffect, useState, Component } from 'react'
import { cuePhase, easeOutCubic, clamp01 } from './easing'
import { loadTemplate } from './library'

/**
 * Renders a vendored motion-graphics template (magic-ui / motion-primitives /
 * react-bits) as a cue. The template is lazy-loaded on first render and
 * cached in module state.
 *
 * Backgrounds (react-bits/backgrounds) render full-bleed behind text.
 * Everything else renders centered.
 *
 * Props:
 *   cue: { t, library, name, category?, text? }
 */

const MODULE_CACHE = new Map() // key -> React component (or null if failed)

function cacheKey(cue) {
  return `${cue.library}/${cue.category || '-'}/${cue.name}`
}

// Vendored templates are 3rd-party: isolate any render errors so one bad
// component can't crash the entire player.
class TemplateErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch(err) {
    // eslint-disable-next-line no-console
    console.warn('[TemplateRenderer] template failed to render:', err)
  }
  render() {
    return this.state.failed ? null : this.props.children
  }
}

export default function TemplateRenderer({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const [Comp, setComp] = useState(() => MODULE_CACHE.get(cacheKey(cue)) || null)

  useEffect(() => {
    const key = cacheKey(cue)
    if (MODULE_CACHE.has(key)) {
      setComp(() => MODULE_CACHE.get(key))
      return
    }
    let cancelled = false
    loadTemplate(cue.library, cue.name, cue.category)
      .then((mod) => {
        if (cancelled) return
        MODULE_CACHE.set(key, mod || null)
        setComp(() => mod || null)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn('[TemplateRenderer] failed to load', key, err)
        MODULE_CACHE.set(key, null)
        setComp(() => null)
      })
    return () => {
      cancelled = true
    }
  }, [cue.library, cue.name, cue.category])

  const isBackground = cue.library === 'react-bits' && cue.category === 'backgrounds'

  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.5,
    holdDuration: isBackground ? 5.0 : 3.2,
    outDuration: 0.5,
  })

  if (phase === 'idle' || phase === 'done') return null
  if (!Comp) return null

  const inP = phase === 'in' ? easeOutCubic(progress) : 1
  const outP = phase === 'out' ? easeOutCubic(progress) : 0
  const opacity = clamp01(inP - outP)

  const wrapStyle = isBackground
    ? {
        position: 'absolute',
        inset: 0,
        opacity,
        pointerEvents: 'none',
        overflow: 'hidden',
        mixBlendMode: 'screen',
      }
    : {
        position: 'absolute',
        left: '50%',
        top: '50%',
        transform: `translate(-50%, -50%) scale(${scale})`,
        opacity,
        pointerEvents: 'none',
        fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
        color: '#ffffff',
        textShadow: '0 2px 12px rgba(0,0,0,0.85)',
        fontSize: 48,
        fontWeight: 900,
        whiteSpace: 'nowrap',
      }

  // Try to pass common props; templates ignore what they don't use.
  const childProps = {
    color: primaryColor,
    primaryColor,
  }
  if (cue.text) {
    childProps.text = cue.text
    childProps.children = cue.text
  }

  return (
    <div style={wrapStyle}>
      <TemplateErrorBoundary>
        <Comp {...childProps} />
      </TemplateErrorBoundary>
    </div>
  )
}
