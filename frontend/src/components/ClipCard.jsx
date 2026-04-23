import { useState, useRef } from 'react'
import { Download, Play, Pause, Captions } from 'lucide-react'
import { streamClip, downloadClip } from '../api/client'
import CaptionedPlayer from './CaptionedPlayer'

function getScoreColor(score) {
  if (score >= 80) return 'bg-score-green/20 text-score-green border-score-green/30'
  if (score >= 60) return 'bg-score-yellow/20 text-score-yellow border-score-yellow/30'
  return 'bg-score-red/20 text-score-red border-score-red/30'
}

export default function ClipCard({ clip }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [showCaptions, setShowCaptions] = useState(false)
  const videoRef = useRef(null)

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const handleVideoEnd = () => {
    setIsPlaying(false)
  }

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden hover:border-accent/30 transition-colors">
      {/* Video player */}
      <div className="relative aspect-[9/16] bg-black group">
        {showCaptions ? (
          <CaptionedPlayer clip={clip} />
        ) : (
          <>
            <video
              ref={videoRef}
              src={streamClip(clip.id)}
              className="w-full h-full object-contain"
              onEnded={handleVideoEnd}
              playsInline
              preload="metadata"
            />
            <button
              onClick={togglePlay}
              className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <div className="w-14 h-14 rounded-full bg-black/60 flex items-center justify-center">
                {isPlaying
                  ? <Pause className="w-6 h-6 text-white" />
                  : <Play className="w-6 h-6 text-white ml-1" />
                }
              </div>
            </button>
          </>
        )}

        {/* Caption toggle */}
        <button
          onClick={() => {
            if (videoRef.current && isPlaying) {
              videoRef.current.pause()
              setIsPlaying(false)
            }
            setShowCaptions((v) => !v)
          }}
          title={showCaptions ? 'Hide captions' : 'Preview with captions'}
          className={`absolute top-2 right-2 p-1.5 rounded-lg border transition-colors ${
            showCaptions
              ? 'bg-accent text-white border-accent'
              : 'bg-black/60 text-gray-300 border-white/10 hover:text-white'
          }`}
        >
          <Captions className="w-4 h-4" />
        </button>
      </div>

      {/* Clip info */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-white">
            Clip {clip.clip_index}
          </span>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${getScoreColor(clip.virality_score)}`}>
            {clip.virality_score}
          </span>
        </div>

        <p className="text-xs text-gray-500">
          {clip.start_time} — {clip.end_time} · {clip.duration.toFixed(1)}s
        </p>

        <p className="text-sm text-gray-300 leading-relaxed">
          <span className="text-accent font-medium">Hook: </span>{clip.hook}
        </p>

        <p className="text-xs text-gray-500 leading-relaxed">
          {clip.reason}
        </p>

        <a
          href={downloadClip(clip.id)}
          download
          className="flex items-center justify-center gap-2 w-full py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-xl transition-colors"
        >
          <Download className="w-4 h-4" />
          Download
        </a>
      </div>
    </div>
  )
}
