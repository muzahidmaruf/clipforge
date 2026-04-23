import { useEffect, useState, useRef } from 'react'
import LowerThird from './LowerThird'
import StatCard from './StatCard'
import PullQuote from './PullQuote'
import KineticSlam from './KineticSlam'
import BulletCascade from './BulletCascade'
import ProgressBar from './ProgressBar'
import BarChart from './BarChart'

const COMPONENTS = {
  lower_third: LowerThird,
  stat_card: StatCard,
  pull_quote: PullQuote,
  kinetic_slam: KineticSlam,
  bullet_cascade: BulletCascade,
  progress_bar: ProgressBar,
  bar_chart: BarChart,
}

/**
 * Renders the AI-directed motion graphics layer above the video.
 *
 * Responsive scale: we measure the container height and scale the 1080p
 * reference sizes so graphics look right at any player size.
 */
export default function MotionLayer({ clipId, currentTime, primaryColor = '#FFD400', enabled = true }) {
  const [cues, setCues] = useState([])
  const [scale, setScale] = useState(0.5)
  const wrapRef = useRef(null)

  // Fetch cues
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    fetch(`/api/clips/${clipId}/motion`)
      .then((r) => (r.ok ? r.json() : { cues: [] }))
      .then((d) => {
        if (!cancelled) setCues(d.cues || [])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [clipId, enabled])

  // Track container height for responsive scaling (1920 = scale 1)
  useEffect(() => {
    if (!wrapRef.current) return
    const ro = new ResizeObserver(([entry]) => {
      const h = entry.contentRect.height
      setScale(Math.max(0.25, Math.min(1.5, h / 1920)))
    })
    ro.observe(wrapRef.current)
    return () => ro.disconnect()
  }, [])

  if (!enabled) return <div ref={wrapRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />

  return (
    <div ref={wrapRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      {cues.map((cue, idx) => {
        const Component = COMPONENTS[cue.type]
        if (!Component) return null
        return (
          <Component
            key={`${cue.type}-${cue.t}-${idx}`}
            cue={cue}
            currentTime={currentTime}
            primaryColor={primaryColor}
            scale={scale}
          />
        )
      })}
    </div>
  )
}
