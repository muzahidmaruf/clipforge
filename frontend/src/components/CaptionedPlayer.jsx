import { useEffect, useRef, useState } from 'react'
import { Settings2 } from 'lucide-react'
import { streamClip } from '../api/client'

// Cache fonts globally so all cards share one fetch
let fontsCache = null
let fontsPromise = null
const loadFonts = () => {
  if (fontsCache) return Promise.resolve(fontsCache)
  if (fontsPromise) return fontsPromise
  fontsPromise = fetch('/api/fonts')
    .then((r) => (r.ok ? r.json() : { fonts: [] }))
    .then((d) => {
      fontsCache = d.fonts || []
      return fontsCache
    })
    .catch(() => {
      fontsCache = []
      return fontsCache
    })
  return fontsPromise
}

// User preferences persist via localStorage
const readPref = (key, fallback) => {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v
  } catch {
    return fallback
  }
}
const writePref = (key, value) => {
  try {
    localStorage.setItem(key, String(value))
  } catch {}
}

const POSITION_MAP = {
  top: { top: '10%', bottom: 'auto' },
  middle: { top: '50%', bottom: 'auto', transform: 'translateY(-50%)' },
  bottom: { top: 'auto', bottom: '15%' },
}

const SIZE_MAP = {
  small: 28,
  medium: 40,
  large: 56,
}

export default function CaptionedPlayer({ clip }) {
  const videoRef = useRef(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [words, setWords] = useState(null)
  const [error, setError] = useState(null)
  const [fonts, setFonts] = useState([])

  // Caption settings (persisted)
  const [fontFamily, setFontFamily] = useState(() => readPref('cf_font', 'Inter'))
  const [position, setPosition] = useState(() => readPref('cf_pos', 'bottom'))
  const [size, setSize] = useState(() => readPref('cf_size', 'medium'))
  const [phraseSize, setPhraseSize] = useState(() => Number(readPref('cf_wps', '3')))
  const [showSettings, setShowSettings] = useState(false)

  // Fetch subtitles
  useEffect(() => {
    let cancelled = false
    fetch(`/api/clips/${clip.id}/subtitles`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load subtitles')
        return r.json()
      })
      .then((data) => {
        if (!cancelled) setWords(data.words || [])
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
    return () => { cancelled = true }
  }, [clip.id])

  // Fetch font list
  useEffect(() => {
    let cancelled = false
    loadFonts().then((list) => {
      if (!cancelled) setFonts(list)
    })
    return () => { cancelled = true }
  }, [])

  // Track video currentTime with rAF for smoother caption updates (better than onTimeUpdate which fires ~4x/sec)
  useEffect(() => {
    let raf
    const tick = () => {
      if (videoRef.current && !videoRef.current.paused) {
        setCurrentTime(videoRef.current.currentTime)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  const handleTimeUpdate = () => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime)
  }

  // Group words into phrases
  const phrases = []
  if (words) {
    for (let i = 0; i < words.length; i += phraseSize) {
      const group = words.slice(i, i + phraseSize)
      if (group.length === 0) continue
      phrases.push({
        words: group,
        start: group[0].start,
        end: group[group.length - 1].end,
      })
    }
  }
  const activePhrase = phrases.find((p) => currentTime >= p.start && currentTime <= p.end)

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-black">
        <p className="text-xs text-score-red px-4 text-center">{error}</p>
      </div>
    )
  }

  const fontSize = SIZE_MAP[size] || SIZE_MAP.medium
  const posStyle = POSITION_MAP[position] || POSITION_MAP.bottom

  const savePref = (setter, key) => (v) => {
    setter(v)
    writePref(key, v)
  }

  return (
    <div className="relative w-full h-full bg-black">
      {/* Native video - perfect audio sync */}
      <video
        ref={videoRef}
        src={streamClip(clip.id)}
        className="w-full h-full object-contain"
        controls
        playsInline
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
      />

      {/* Caption overlay */}
      {activePhrase && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            ...posStyle,
            display: 'flex',
            justifyContent: 'center',
            pointerEvents: 'none',
            padding: '0 16px',
          }}
        >
          <div
            style={{
              maxWidth: '92%',
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              columnGap: '0.45em',
              rowGap: '0.15em',
            }}
          >
            {activePhrase.words.map((w, idx) => {
              const isActive = currentTime >= w.start && currentTime <= w.end
              return (
                <span
                  key={idx}
                  style={{
                    fontFamily: `"${fontFamily}", "Inter", system-ui, sans-serif`,
                    fontSize: `${fontSize}px`,
                    fontWeight: 800,
                    lineHeight: 1.15,
                    color: isActive ? '#FFD400' : '#FFFFFF',
                    textShadow:
                      '0 0 6px rgba(0,0,0,0.95), 0 0 12px rgba(0,0,0,0.7), 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000',
                    transform: isActive ? 'scale(1.08)' : 'scale(1)',
                    transition: 'transform 80ms ease-out, color 60ms linear',
                    textTransform: 'uppercase',
                    letterSpacing: '0.01em',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {w.word}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Settings toggle */}
      <button
        onClick={() => setShowSettings((v) => !v)}
        title="Caption settings"
        className={`absolute top-2 left-2 p-1.5 rounded-lg border transition-colors ${
          showSettings
            ? 'bg-accent text-white border-accent'
            : 'bg-black/60 text-gray-300 border-white/10 hover:text-white'
        }`}
      >
        <Settings2 className="w-4 h-4" />
      </button>

      {/* Settings panel */}
      {showSettings && (
        <div
          className="absolute top-12 left-2 right-2 max-w-xs bg-black/90 backdrop-blur border border-white/10 rounded-xl p-3 space-y-2 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          <div>
            <label className="block text-gray-400 mb-1">Font</label>
            <select
              value={fontFamily}
              onChange={(e) => savePref(setFontFamily, 'cf_font')(e.target.value)}
              style={{ fontFamily: `"${fontFamily}", sans-serif` }}
              className="w-full bg-background border border-border rounded px-2 py-1 text-white"
            >
              {fonts.length === 0 && <option value={fontFamily}>{fontFamily}</option>}
              {fonts.map((f) => (
                <option key={f} value={f} style={{ fontFamily: `"${f}", sans-serif` }}>{f}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Position</label>
            <div className="flex gap-1">
              {['top', 'middle', 'bottom'].map((p) => (
                <button
                  key={p}
                  onClick={() => savePref(setPosition, 'cf_pos')(p)}
                  className={`flex-1 py-1 rounded border text-xs capitalize ${
                    position === p
                      ? 'bg-accent text-white border-accent'
                      : 'bg-background text-gray-300 border-border'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Size</label>
            <div className="flex gap-1">
              {['small', 'medium', 'large'].map((s) => (
                <button
                  key={s}
                  onClick={() => savePref(setSize, 'cf_size')(s)}
                  className={`flex-1 py-1 rounded border text-xs capitalize ${
                    size === s
                      ? 'bg-accent text-white border-accent'
                      : 'bg-background text-gray-300 border-border'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-gray-400 mb-1">Words per line</label>
            <div className="flex gap-1">
              {[2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => savePref((v) => setPhraseSize(Number(v)), 'cf_wps')(n)}
                  className={`flex-1 py-1 rounded border text-xs ${
                    phraseSize === n
                      ? 'bg-accent text-white border-accent'
                      : 'bg-background text-gray-300 border-border'
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Loading indicator for subtitles */}
      {words === null && (
        <div className="absolute top-2 right-2 bg-black/60 rounded px-2 py-1 text-xs text-gray-300">
          Loading captions…
        </div>
      )}
    </div>
  )
}
