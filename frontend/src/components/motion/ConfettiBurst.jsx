import { useMemo } from 'react'
import { clamp01 } from './easing'

/**
 * Particle-based confetti burst. Deterministic per cue (seeded by cue.t)
 * so the same cue renders the same pattern every frame.
 *
 * Each particle: starts at an origin near the center-bottom, launches up with
 * a random angle/velocity, gravity pulls it down, spins as it falls.
 *
 * Props:
 *   cue: { t, intensity: 'low' | 'medium' | 'high' }
 *   currentTime
 *   primaryColor
 *   scale
 */

// Simple seedable PRNG (Mulberry32) — deterministic per seed
const mulberry32 = (seed) => {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const INTENSITY_COUNT = { low: 40, medium: 80, high: 140 }
const INTENSITY_DURATION = { low: 1.8, medium: 2.4, high: 3.2 }

export default function ConfettiBurst({ cue, currentTime, primaryColor = '#FFD400', scale = 1 }) {
  const intensity = cue.intensity || 'medium'
  const count = INTENSITY_COUNT[intensity]
  const life = INTENSITY_DURATION[intensity]

  // Build particles once per cue
  const particles = useMemo(() => {
    const seed = Math.floor(cue.t * 1000) + 1
    const rand = mulberry32(seed)
    const palette = [
      primaryColor,
      '#ffffff',
      '#ff4d8d', // pink
      '#4dd4ff', // cyan
      '#7cff9a', // mint
      '#ffb84d', // orange
    ]
    const arr = []
    for (let i = 0; i < count; i++) {
      // Two launch origins: left-bottom and right-bottom for a V-shaped burst
      const leftSide = rand() < 0.5
      const originX = leftSide ? 0.3 + rand() * 0.1 : 0.6 + rand() * 0.1
      const originY = 0.85 + rand() * 0.05
      // Angle upward with spread: -60° to +60° from straight up
      const angle = -Math.PI / 2 + (rand() - 0.5) * Math.PI * 0.7
      // Horizontal bias away from center for V-shape
      const hBias = leftSide ? -0.15 : 0.15
      const speed = 0.6 + rand() * 0.9 // screen-fractions/sec initial
      const vx = Math.cos(angle) * speed + hBias
      const vy = Math.sin(angle) * speed // negative = up
      const color = palette[Math.floor(rand() * palette.length)]
      const shape = rand() < 0.5 ? 'rect' : 'circle'
      const size = (8 + rand() * 10) * scale // px
      const rotSpeed = (rand() - 0.5) * 720 // deg/sec
      const initialRot = rand() * 360
      const lifeMul = 0.7 + rand() * 0.6 // per-particle life variance
      arr.push({ originX, originY, vx, vy, color, shape, size, rotSpeed, initialRot, lifeMul })
    }
    return arr
  }, [cue.t, count, primaryColor, scale])

  const elapsed = currentTime - cue.t
  if (elapsed < 0 || elapsed > life * 1.5) return null

  const gravity = 0.65 // screen-fractions/sec^2 (positive = down)

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      {particles.map((p, i) => {
        const pLife = life * p.lifeMul
        const t = elapsed // seconds
        if (t > pLife) return null

        // Kinematics: x = x0 + vx * t, y = y0 + vy * t + 0.5 * g * t^2 (screen fractions)
        const x = p.originX + p.vx * t
        const y = p.originY + p.vy * t + 0.5 * gravity * t * t
        if (y > 1.15) return null // off-screen bottom

        const rot = p.initialRot + p.rotSpeed * t
        // Fade out in the last 30% of life
        const fadeStart = pLife * 0.7
        const opacity = t > fadeStart ? clamp01(1 - (t - fadeStart) / (pLife - fadeStart)) : 1

        const baseStyle = {
          position: 'absolute',
          left: `${x * 100}%`,
          top: `${y * 100}%`,
          width: `${p.size}px`,
          height: p.shape === 'circle' ? `${p.size}px` : `${p.size * 0.5}px`,
          background: p.color,
          opacity,
          transform: `translate(-50%, -50%) rotate(${rot}deg)`,
          boxShadow: `0 2px 6px rgba(0,0,0,0.3)`,
          borderRadius: p.shape === 'circle' ? '50%' : `${p.size * 0.12}px`,
          willChange: 'transform, opacity',
        }

        return <div key={i} style={baseStyle} />
      })}
    </div>
  )
}
