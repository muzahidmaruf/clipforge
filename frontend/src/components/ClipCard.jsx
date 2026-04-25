import { useState, useRef } from 'react'
import { Download, Play, Pause, Captions, ChevronDown, ChevronUp, Copy, Check, Type, Loader2 } from 'lucide-react'
import { streamClip, downloadClip, burnSubtitles } from '../api/client'
import CaptionedPlayer from './CaptionedPlayer'

function getScoreColor(score) {
  if (score >= 80) return 'bg-score-green/20 text-score-green border-score-green/30'
  if (score >= 60) return 'bg-score-yellow/20 text-score-yellow border-score-yellow/30'
  return 'bg-score-red/20 text-score-red border-score-red/30'
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button
      onClick={copy}
      title="Copy to clipboard"
      className="shrink-0 p-1 rounded hover:bg-white/10 text-gray-500 hover:text-gray-300 transition-colors"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-score-green" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

function PlatformRow({ label, text, color }) {
  if (!text) return null
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className={`text-[10px] font-semibold uppercase tracking-wide ${color}`}>{label}</span>
        <CopyButton text={text} />
      </div>
      <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-line">{text}</p>
    </div>
  )
}

export default function ClipCard({ clip }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [showCaptions, setShowCaptions] = useState(false)
  const [showDescriptions, setShowDescriptions] = useState(false)
  const [burningSubtitles, setBurningSubtitles] = useState(false)
  const videoRef = useRef(null)

  const handleBurnSubtitles = async () => {
    setBurningSubtitles(true)
    try {
      const resp = await burnSubtitles(clip.id)
      const url = URL.createObjectURL(resp.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `clip_${clip.clip_index}_subtitled.mp4`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert('Subtitle burn failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBurningSubtitles(false)
    }
  }

  const hasDescriptions = clip.tiktok_description || clip.instagram_description || clip.youtube_title

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

        {/* Viral hook text overlay */}
        {clip.viral_hook_text && !showCaptions && (
          <div className="absolute bottom-10 left-0 right-0 flex justify-center px-3 pointer-events-none">
            <span className="bg-black/70 text-white text-xs font-bold px-2.5 py-1 rounded-lg text-center leading-snug max-w-[90%]">
              {clip.viral_hook_text}
            </span>
          </div>
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

        {/* Platform descriptions accordion */}
        {hasDescriptions && (
          <div className="border border-border rounded-xl overflow-hidden">
            <button
              onClick={() => setShowDescriptions((v) => !v)}
              className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-medium text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors"
            >
              <span>Platform Captions &amp; Title</span>
              {showDescriptions
                ? <ChevronUp className="w-3.5 h-3.5" />
                : <ChevronDown className="w-3.5 h-3.5" />
              }
            </button>
            {showDescriptions && (
              <div className="px-3 pb-3 space-y-3 border-t border-border pt-3">
                <PlatformRow
                  label="TikTok"
                  text={clip.tiktok_description}
                  color="text-[#69C9D0]"
                />
                <PlatformRow
                  label="Instagram"
                  text={clip.instagram_description}
                  color="text-[#E1306C]"
                />
                <PlatformRow
                  label="YouTube"
                  text={clip.youtube_title}
                  color="text-[#FF0000]"
                />
              </div>
            )}
          </div>
        )}

        <div className="flex gap-2">
          <a
            href={downloadClip(clip.id)}
            download
            className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-xl transition-colors"
          >
            <Download className="w-4 h-4" />
            Download
          </a>
          <button
            onClick={handleBurnSubtitles}
            disabled={burningSubtitles}
            title="Download with burned-in subtitles"
            className="px-3 py-2.5 bg-card border border-border hover:border-accent/50 text-gray-400 hover:text-white text-sm rounded-xl transition-colors disabled:opacity-50"
          >
            {burningSubtitles
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Type className="w-4 h-4" />
            }
          </button>
        </div>
      </div>
    </div>
  )
}
