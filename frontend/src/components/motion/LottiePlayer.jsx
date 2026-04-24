import { useEffect, useState } from 'react'
import Lottie from 'lottie-react'
import { cuePhase, easeOutCubic, clamp01 } from './easing'
import { loadLottie } from './library'

/**
 * Plays a small Lottie JSON overlay at a corner (or center) of the video.
 *
 * Props:
 *   cue: { t, lottie_id, position?, scale? }
 *   scale: uniform stage scale (responsive)
 */

const JSON_CACHE = new Map()

const POSITION_STYLES = {
  'top-left':     { top: '6%',    left: '6%'  },
  'top-right':    { top: '6%',    right: '6%' },
  'bottom-left':  { bottom: '16%', left: '6%' },
  'bottom-right': { bottom: '16%', right: '6%' },
  'center':       { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' },
}

export default function LottiePlayer({ cue, currentTime, scale = 1 }) {
  const [data, setData] = useState(() => JSON_CACHE.get(cue.lottie_id) || null)

  useEffect(() => {
    if (JSON_CACHE.has(cue.lottie_id)) {
      setData(JSON_CACHE.get(cue.lottie_id))
      return
    }
    let cancelled = false
    loadLottie(cue.lottie_id)
      .then((json) => {
        if (cancelled) return
        JSON_CACHE.set(cue.lottie_id, json || null)
        setData(json || null)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn('[LottiePlayer] failed to load', cue.lottie_id, err)
        JSON_CACHE.set(cue.lottie_id, null)
        setData(null)
      })
    return () => { cancelled = true }
  }, [cue.lottie_id])

  const { phase, progress } = cuePhase(currentTime, cue.t, {
    inDuration: 0.3,
    holdDuration: 2.2,
    outDuration: 0.35,
  })

  if (phase === 'idle' || phase === 'done') return null
  if (!data) return null

  const inP = phase === 'in' ? easeOutCubic(progress) : 1
  const outP = phase === 'out' ? easeOutCubic(progress) : 0
  const opacity = clamp01(inP - outP)

  const userScale = Math.max(0.3, Math.min(1.5, Number(cue.scale) || 0.6))
  const position = POSITION_STYLES[cue.position] || POSITION_STYLES['center']

  // Base size (at scale=1, cue.scale=1): ~260px. Responsive to stage.
  const sizePx = 260 * userScale * scale

  const style = {
    position: 'absolute',
    width: sizePx,
    height: sizePx,
    opacity,
    pointerEvents: 'none',
    ...position,
  }

  // When centered, compose translate with scale-like transform already in position
  return (
    <div style={style}>
      <Lottie animationData={data} loop autoplay style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
