import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scissors, ChevronDown, Sparkles, Wand2, Layers, Upload, Youtube, Link, LogOut } from 'lucide-react'
import UploadZone from '../components/UploadZone'
import JobList from '../components/JobList'
import { uploadVideo, importYouTube } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const WHISPER_MODELS = [
  // ── faster-whisper INT8 (3-5x faster on CPU) ────────────────────────────
  { value: 'base-fast',   label: '⚡ Base Fast — INT8, 3-5× faster on CPU (recommended)' },
  { value: 'small-fast',  label: '⚡ Small Fast — INT8, better quality, still fast' },
  { value: 'medium-fast', label: '⚡ Medium Fast — INT8, high quality' },
  { value: 'tiny-fast',   label: '⚡ Tiny Fast — INT8, fastest possible' },
  { value: 'large-fast',  label: '⚡ Large Fast — INT8, best quality' },
  // ── openai-whisper (original PyTorch) ───────────────────────────────────
  { value: 'base',   label: 'Base (standard, GPU-accelerated)' },
  { value: 'small',  label: 'Small (standard)' },
  { value: 'medium', label: 'Medium (standard, 5GB RAM)' },
  { value: 'tiny',   label: 'Tiny (standard, lowest quality)' },
  { value: 'large',  label: 'Large (standard, 10GB RAM)' },
]

const WHISPER_LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'bn',   label: 'বাংলা — Bengali / Bangla' },
  { value: 'en',   label: 'English' },
  { value: 'hi',   label: 'हिन्दी — Hindi' },
  { value: 'ur',   label: 'اردو — Urdu' },
  { value: 'ar',   label: 'العربية — Arabic' },
  { value: 'zh',   label: '中文 — Chinese' },
  { value: 'es',   label: 'Español — Spanish' },
  { value: 'fr',   label: 'Français — French' },
  { value: 'de',   label: 'Deutsch — German' },
  { value: 'pt',   label: 'Português — Portuguese' },
  { value: 'ru',   label: 'Русский — Russian' },
  { value: 'ja',   label: '日本語 — Japanese' },
  { value: 'ko',   label: '한국어 — Korean' },
  { value: 'tr',   label: 'Türkçe — Turkish' },
  { value: 'it',   label: 'Italiano — Italian' },
]

const AI_MODELS = [
  // ── Qwen 3.5 ──────────────────────────────────────────────────────────────
  { value: 'qwen3.5:32b-cloud', label: 'Qwen 3.5 32B Cloud ★ Best for multilingual (Bengali, Hindi, etc.)' },
  { value: 'qwen3.5:14b-cloud', label: 'Qwen 3.5 14B Cloud (faster)' },
  // ── Qwen 3 ────────────────────────────────────────────────────────────────
  { value: 'qwen3:32b-cloud',   label: 'Qwen 3 32B Cloud' },
  { value: 'qwen3:14b-cloud',   label: 'Qwen 3 14B Cloud' },
  { value: 'qwen3:8b-cloud',    label: 'Qwen 3 8B Cloud (edge)' },
  // ── Gemma 4 (English only) ─────────────────────────────────────────────────
  { value: 'gemma4:31b-cloud',  label: 'Gemma 4 31B Cloud (English only - NOT recommended for Bengali)' },
]

export default function Home() {
  const [inputMode, setInputMode] = useState('file')   // 'file' | 'youtube'
  const [file, setFile] = useState(null)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [whisperModel, setWhisperModel] = useState('base-fast')
  const [aiModel, setAiModel] = useState('qwen3.5:32b-cloud')
  const [showSettings, setShowSettings] = useState(false)
  const [mode, setMode] = useState('clips')             // 'clips' | 'clean' | 'both'
  const [numClips, setNumClips] = useState(5)           // 1..15
  const [whisperLanguage, setWhisperLanguage] = useState('auto')  // ISO 639-1 or 'auto'
  const navigate = useNavigate()
  const { user, signOut } = useAuth()

  const hasInput = inputMode === 'file' ? !!file : youtubeUrl.trim().length > 0

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile)
    setError(null)
  }

  const handleUpload = async () => {
    if (!hasInput) return

    // Pre-flight check: verify backend is reachable
    try {
      const healthCheck = await fetch('/api/health', { method: 'GET' })
      if (!healthCheck.ok) {
        throw new Error('Backend server is not responding')
      }
    } catch (fetchErr) {
      console.error('[Health Check] Failed:', fetchErr)
      setError('Cannot connect to backend server. Please ensure the backend is running on http://localhost:8000')
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setError(null)

    try {
      let response
      if (inputMode === 'youtube') {
        response = await importYouTube(youtubeUrl.trim(), whisperModel, aiModel, { mode, numClips, whisperLanguage })
      } else {
        response = await uploadVideo(file, whisperModel, aiModel, setUploadProgress, { mode, numClips, whisperLanguage })
      }
      const { job_id } = response.data
      navigate(`/results/${job_id}`)
    } catch (err) {
      console.error('[Upload] Error:', err)
      let msg = inputMode === 'youtube' ? 'YouTube import failed.' : 'Upload failed. Please try again.'
      if (err.response?.data?.detail) {
        msg = err.response.data.detail
      } else if (err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')) {
        msg = 'Network error during upload. This can happen with large files. Try: 1) Refresh the page, 2) Check backend is running, 3) Try a smaller file'
      } else if (err.message) {
        msg = err.message
      }
      setError(msg)
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      {/* User badge / logout */}
      {user && (
        <div className="absolute top-4 right-4 flex items-center gap-2 text-xs text-gray-400">
          <span className="hidden sm:inline">{user.email}</span>
          <button
            onClick={async () => { await signOut(); navigate('/login') }}
            title="Sign out"
            className="p-1.5 rounded-lg border border-border hover:border-accent/50 hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      )}
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent/10 mb-6">
            <Scissors className="w-8 h-8 text-accent" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-3">ClipForge</h1>
          <p className="text-lg text-gray-400">
            Upload a video. AI finds the best moments. Get viral-ready clips.
          </p>
        </div>

        {/* Input mode toggle */}
        <div className="flex rounded-xl border border-border overflow-hidden mb-4">
          <button
            onClick={() => { setInputMode('file'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors ${
              inputMode === 'file'
                ? 'bg-accent text-white'
                : 'bg-card text-gray-400 hover:text-white'
            }`}
          >
            <Upload className="w-4 h-4" /> Upload File
          </button>
          <button
            onClick={() => { setInputMode('youtube'); setError(null) }}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors ${
              inputMode === 'youtube'
                ? 'bg-accent text-white'
                : 'bg-card text-gray-400 hover:text-white'
            }`}
          >
            <Youtube className="w-4 h-4" /> YouTube URL
          </button>
        </div>

        {/* Upload or URL input */}
        {inputMode === 'file' ? (
          <UploadZone onFileSelect={handleFileSelect} disabled={uploading} />
        ) : (
          <div className="flex items-center gap-2 p-4 bg-card border border-border rounded-2xl">
            <Link className="w-5 h-5 text-gray-500 shrink-0" />
            <input
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e) => { setYoutubeUrl(e.target.value); setError(null) }}
              disabled={uploading}
              className="flex-1 bg-transparent text-white text-sm placeholder-gray-600 focus:outline-none"
            />
          </div>
        )}

        {hasInput && (
          <>
            {/* Mode selector */}
            <div className="mt-5 p-4 bg-card border border-border rounded-xl">
              <label className="block text-sm font-medium text-white mb-3">What do you want?</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'clips', icon: Sparkles, title: 'Viral clips', desc: 'AI-picked short clips' },
                  { id: 'clean', icon: Wand2, title: 'Clean cut', desc: 'Remove fillers + pauses' },
                  { id: 'both', icon: Layers, title: 'Both', desc: 'Clean + clips' },
                ].map(({ id, icon: Icon, title, desc }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setMode(id)}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      mode === id
                        ? 'border-accent bg-accent/10 text-white'
                        : 'border-border bg-background text-gray-300 hover:border-accent/40'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mb-1 ${mode === id ? 'text-accent' : 'text-gray-400'}`} />
                    <div className="text-sm font-semibold">{title}</div>
                    <div className="text-[11px] text-gray-500 leading-tight mt-0.5">{desc}</div>
                  </button>
                ))}
              </div>

              {(mode === 'clips' || mode === 'both') && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-white">Number of clips</label>
                    <span className="text-sm text-accent font-mono">{numClips}</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={15}
                    step={1}
                    value={numClips}
                    onChange={(e) => setNumClips(Number(e.target.value))}
                    className="w-full accent-accent"
                  />
                  <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                    <span>1</span>
                    <span>5</span>
                    <span>10</span>
                    <span>15</span>
                  </div>
                </div>
              )}

              {mode === 'clean' && (
                <p className="mt-3 text-xs text-gray-500 leading-relaxed">
                  Uploads the full video, detects filler words (um, uh, like, you know…) and long silent pauses in the transcript, then stitches only the spoken parts back into one long cleaned video.
                </p>
              )}
            </div>

            {/* Model Settings */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="mt-4 flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${showSettings ? 'rotate-180' : ''}`} />
              {showSettings ? 'Hide settings' : 'Model settings'}
            </button>

            {showSettings && (
              <div className="mt-3 p-4 bg-card border border-border rounded-xl space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white mb-2">Whisper Model</label>
                  <select
                    value={whisperModel}
                    onChange={(e) => setWhisperModel(e.target.value)}
                    className="w-full p-2.5 bg-background border border-border rounded-lg text-white text-sm focus:border-accent focus:outline-none"
                  >
                    {WHISPER_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {whisperModel.endsWith('-fast')
                      ? '⚡ faster-whisper INT8 — 3-5× faster on CPU, same accuracy'
                      : 'Standard openai-whisper — uses GPU if available'}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-white mb-2">Video Language</label>
                  <select
                    value={whisperLanguage}
                    onChange={(e) => setWhisperLanguage(e.target.value)}
                    className="w-full p-2.5 bg-background border border-border rounded-lg text-white text-sm focus:border-accent focus:outline-none"
                  >
                    {WHISPER_LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                  {whisperLanguage !== 'auto' && whisperLanguage !== 'en' && (
                    <p className="text-xs text-amber-400 mt-1">
                      💡 For best results with non-English, use Whisper <strong>Small</strong> or above.
                    </p>
                  )}
                  {whisperLanguage === 'auto' && (
                    <p className="text-xs text-gray-500 mt-1">
                      Auto-detect can misidentify Bangla/Hindi — set language explicitly for better accuracy.
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-white mb-2">AI Model (Ollama)</label>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    className="w-full p-2.5 bg-background border border-border rounded-lg text-white text-sm focus:border-accent focus:outline-none"
                  >
                    {AI_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">Uses Ollama Cloud API · model: {aiModel}</p>
                </div>
              </div>
            )}

            {uploading && inputMode === 'file' && (
              <div className="mt-4 mb-2">
                <div className="h-2 bg-card rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-sm text-gray-500 mt-1">Uploading: {uploadProgress}%</p>
              </div>
            )}
            {uploading && inputMode === 'youtube' && (
              <div className="mt-4 mb-2">
                <p className="text-sm text-gray-500 animate-pulse">⬇️ Downloading from YouTube…</p>
              </div>
            )}
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="mt-4 w-full py-4 bg-accent hover:bg-accent-hover disabled:bg-accent/50 text-white font-semibold rounded-2xl transition-colors"
            >
              {uploading
                ? (inputMode === 'youtube' ? 'Downloading…' : 'Uploading...')
                : mode === 'clean'
                  ? 'Clean Video'
                  : mode === 'both'
                    ? 'Clean + Generate Clips'
                    : `Generate ${numClips} Clip${numClips === 1 ? '' : 's'}`}
            </button>
          </>
        )}

        {error && (
          <div className="mt-4 p-4 bg-score-red/10 border border-score-red/30 rounded-xl">
            <p className="text-sm text-score-red">{error}</p>
          </div>
        )}

        {/* Recent Jobs */}
        <JobList />
      </div>
    </div>
  )
}
