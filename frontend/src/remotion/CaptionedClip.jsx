import { AbsoluteFill, Video, useCurrentFrame, useVideoConfig, spring } from 'remotion'

/**
 * Remotion composition that overlays word-by-word subtitles on a video.
 *
 * Props:
 *   videoSrc:   URL of the video file
 *   words:      [{ word, start, end }]  (seconds, relative to clip start)
 *   fontFamily: CSS family name
 *   primary:    active word color (hex)
 *   secondary:  inactive word color (hex)
 *   animation:  'none' | 'pop' | 'bounce' | 'fadeup' | 'emphasis'
 *   phraseSize: words per line
 *   position:   'top' | 'middle' | 'bottom'
 *   fontSize:   px
 */

const POSITION_ALIGN = {
  top: { alignItems: 'flex-start', paddingTop: '10%' },
  middle: { alignItems: 'center' },
  bottom: { alignItems: 'flex-end', paddingBottom: '18%' },
}

const isLoudWord = (text) => {
  if (!text) return false
  const t = text.trim()
  if (/[!?]$/.test(t)) return true
  if (/\d/.test(t)) return true
  const letters = t.replace(/[^A-Za-z]/g, '')
  return letters.length >= 3 && letters === letters.toUpperCase()
}

export const CaptionedClip = ({
  videoSrc,
  words = [],
  fontFamily = 'Inter',
  primary = '#FFD400',
  secondary = '#FFFFFF',
  animation = 'pop',
  phraseSize = 3,
  position = 'bottom',
  fontSize = 72,
}) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const currentTime = frame / fps

  const phrases = []
  for (let i = 0; i < words.length; i += phraseSize) {
    const group = words.slice(i, i + phraseSize)
    if (group.length === 0) continue
    phrases.push({
      words: group,
      start: group[0].start,
      end: group[group.length - 1].end,
    })
  }

  const activePhrase = phrases.find(
    (p) => currentTime >= p.start && currentTime <= p.end
  )

  const posStyle = POSITION_ALIGN[position] || POSITION_ALIGN.bottom

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <Video src={videoSrc} />

      {activePhrase && (
        <AbsoluteFill
          style={{
            display: 'flex',
            justifyContent: 'center',
            pointerEvents: 'none',
            ...posStyle,
          }}
        >
          <div
            style={{
              maxWidth: '85%',
              textAlign: 'center',
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              columnGap: '0.45em',
              rowGap: '0.15em',
            }}
          >
            {activePhrase.words.map((w, idx) => {
              const isActive = currentTime >= w.start && currentTime <= w.end
              const delta = currentTime - w.start
              const loud = isLoudWord(w.word)

              let transform = 'scale(1)'
              let opacity = 1
              let color = isActive ? primary : secondary
              let textShadow =
                '0 0 8px rgba(0,0,0,0.9), 0 0 16px rgba(0,0,0,0.7), 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000'

              if (animation === 'pop' && isActive) {
                const s = spring({ frame: frame - Math.round(w.start * fps), fps, config: { damping: 14, mass: 0.6 } })
                transform = `scale(${1 + s * 0.18})`
              } else if (animation === 'bounce' && isActive) {
                const s = spring({ frame: frame - Math.round(w.start * fps), fps, config: { damping: 10 } })
                transform = `translateY(${(1 - s) * -14}px) scale(${1 + s * 0.08})`
              } else if (animation === 'fadeup') {
                const s = spring({ frame: frame - Math.round(w.start * fps), fps, config: { damping: 20 } })
                opacity = currentTime < w.start ? 0 : s
                transform = `translateY(${(1 - s) * 18}px) scale(${isActive ? 1.06 : 1})`
              } else if (animation === 'emphasis' && isActive) {
                const s = spring({ frame: frame - Math.round(w.start * fps), fps, config: { damping: 8 } })
                const mag = loud ? 0.28 : 0.12
                transform = `scale(${1 + s * mag}) translateY(${loud ? -4 : 0}px)`
                if (loud) {
                  textShadow = `0 0 10px ${primary}, 0 0 22px ${primary}aa, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000`
                }
              }

              return (
                <span
                  key={idx}
                  style={{
                    fontFamily: `"${fontFamily}", Inter, system-ui, -apple-system, sans-serif`,
                    fontSize: `${fontSize}px`,
                    fontWeight: 800,
                    lineHeight: 1.1,
                    color,
                    textShadow,
                    textTransform: 'uppercase',
                    display: 'inline-block',
                    transform,
                    opacity,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {w.word}
                </span>
              )
            })}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  )
}
