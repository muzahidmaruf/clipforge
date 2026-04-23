import { AbsoluteFill, Video, useCurrentFrame, useVideoConfig } from 'remotion'

/**
 * Remotion composition that overlays word-by-word subtitles on a video.
 *
 * Props:
 *   videoSrc: URL of the video file
 *   words: [{ word: string, start: number, end: number }]  (times in seconds, relative to clip start)
 */
export const CaptionedClip = ({ videoSrc, words = [], fontFamily = 'Inter' }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const currentTime = frame / fps

  // Group words into "phrases" of ~4 words to show at once (TikTok style)
  // Each phrase is shown during the time range of its words.
  const phraseSize = 4
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

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <Video src={videoSrc} />

      {activePhrase && (
        <AbsoluteFill
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            paddingBottom: '18%',
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              maxWidth: '85%',
              textAlign: 'center',
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: '0.4em',
            }}
          >
            {activePhrase.words.map((w, idx) => {
              const isActive = currentTime >= w.start && currentTime <= w.end
              return (
                <span
                  key={idx}
                  style={{
                    fontFamily: `"${fontFamily}", Inter, system-ui, -apple-system, sans-serif`,
                    fontSize: '72px',
                    fontWeight: 800,
                    lineHeight: 1.1,
                    color: isActive ? '#FFD400' : '#FFFFFF',
                    textShadow:
                      '0 0 8px rgba(0,0,0,0.9), 0 0 16px rgba(0,0,0,0.7), 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000',
                    transform: isActive ? 'scale(1.08)' : 'scale(1)',
                    transition: 'transform 80ms ease-out',
                    textTransform: 'uppercase',
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
