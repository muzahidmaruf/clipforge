import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scissors, ChevronDown } from 'lucide-react'
import UploadZone from '../components/UploadZone'
import JobList from '../components/JobList'
import { uploadVideo } from '../api/client'

const WHISPER_MODELS = [
  { value: 'tiny', label: 'Tiny (fastest, lowest quality)' },
  { value: 'base', label: 'Base (balanced)' },
  { value: 'small', label: 'Small (better quality)' },
  { value: 'medium', label: 'Medium (best quality, 5GB RAM)' },
  { value: 'large', label: 'Large (bestest, 10GB RAM)' },
]

const AI_MODELS = [
  { value: 'gemma4:31b-cloud', label: 'Gemma 4 31B Cloud (dense, 256K ctx)' },
  { value: 'gemma4:26b-cloud', label: 'Gemma 4 26B Cloud (MoE, 256K ctx)' },
  { value: 'gemma4:e4b-cloud', label: 'Gemma 4 E4B Cloud (edge, 128K ctx)' },
  { value: 'gemma4:e2b-cloud', label: 'Gemma 4 E2B Cloud (edge, 128K ctx)' },
]

export default function Home() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [whisperModel, setWhisperModel] = useState('base')
  const [aiModel, setAiModel] = useState('gemma4:31b-cloud')
  const [showSettings, setShowSettings] = useState(false)
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
      const response = await uploadVideo(file, whisperModel, aiModel, setUploadProgress)
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
                  <p className="text-xs text-gray-500 mt-1">Cloud model selected: {aiModel}</p>
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
              {uploading ? 'Uploading...' : 'Generate Clips'}
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
