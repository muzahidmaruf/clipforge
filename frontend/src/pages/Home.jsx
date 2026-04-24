import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scissors, ChevronDown, Sparkles, Wand2, Layers } from 'lucide-react'
import UploadZone from '../components/UploadZone'
import JobList from '../components/JobList'
import { uploadVideo } from '../api/client'

const WHISPER_MODELS = [
  { value: 'tiny',   label: 'Tiny (fastest, lowest quality)' },
  { value: 'base',   label: 'Base (balanced)' },
  { value: 'small',  label: 'Small (better quality)' },
  { value: 'medium', label: 'Medium (best quality, 5GB RAM)' },
  { value: 'large',  label: 'Large (best, 10GB RAM)' },
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
  { value: 'qwen3.5:32b-cloud', label: 'Qwen 3.5 32B Cloud ★ recommended' },
  { value: 'qwen3.5:14b-cloud', label: 'Qwen 3.5 14B Cloud (faster)' },
  // ── Qwen 3 ────────────────────────────────────────────────────────────────
  { value: 'qwen3:32b-cloud',   label: 'Qwen 3 32B Cloud' },
  { value: 'qwen3:14b-cloud',   label: 'Qwen 3 14B Cloud' },
  { value: 'qwen3:8b-cloud',    label: 'Qwen 3 8B Cloud (edge)' },
  // ── Gemma 4 ───────────────────────────────────────────────────────────────
  { value: 'gemma4:31b-cloud',  label: 'Gemma 4 31B Cloud (256K ctx)' },
  { value: 'gemma4:26b-cloud',  label: 'Gemma 4 26B Cloud (MoE)' },
  { value: 'gemma4:e4b-cloud',  label: 'Gemma 4 E4B Cloud (edge)' },
  { value: 'gemma4:e2b-cloud',  label: 'Gemma 4 E2B Cloud (edge)' },
]

export default function Home() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [whisperModel, setWhisperModel] = useState('base')
  const [aiModel, setAiModel] = useState('qwen3.5:32b-cloud')
  const [showSettings, setShowSettings] = useState(false)
  const [mode, setMode] = useState('clips')             // 'clips' | 'clean' | 'both'
  const [numClips, setNumClips] = useState(5)           // 1..15
  const [whisperLanguage, setWhisperLanguage] = useState('auto')  // ISO 639-1 or 'auto'
  const navigate = useNavigate()

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile)
    setError(null)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setUploadProgress(0)
    setError(null)

    try {
      const response = await uploadVideo(file, whisperModel, aiModel, setUploadProgress, { mode, numClips, whisperLanguage })
      const { job_id } = response.data
      navigate(`/results/${job_id}`)
    } catch (err) {
      let msg = 'Upload failed. Please try again.'
      if (err.response?.data?.detail) {
        msg = err.response.data.detail
      } else if (err.message?.includes('Network Error')) {
        msg = 'Network error. Check connection or try a smaller file.'
      } else if (err.message) {
        msg = err.message
      }
      setError(msg)
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
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

        {/* Upload */}
        <UploadZone onFileSelect={handleFileSelect} disabled={uploading} />

        {file && (
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

            {uploading && (
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
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="mt-4 w-full py-4 bg-accent hover:bg-accent-hover disabled:bg-accent/50 text-white font-semibold rounded-2xl transition-colors"
            >
              {uploading
                ? 'Uploading...'
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
