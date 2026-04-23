import { useState, useCallback } from 'react'
import { Upload, X, Film } from 'lucide-react'

export default function UploadZone({ onFileSelect, disabled }) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [error, setError] = useState(null)

  const validateFile = (file) => {
    const allowed = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!allowed.includes(ext)) {
      return 'Invalid file type. Supported: mp4, mov, avi, mkv, webm'
    }
    if (file.size > 500 * 1024 * 1024) {
      return 'File too large. Max: 500MB'
    }
    return null
  }

  const handleFile = (file) => {
    const err = validateFile(file)
    if (err) {
      setError(err)
      return
    }
    setError(null)
    setSelectedFile(file)
    onFileSelect(file)
  }

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [onFileSelect])

  const handleInput = (e) => {
    const file = e.target.files[0]
    if (file) handleFile(file)
  }

  const clearFile = () => {
    setSelectedFile(null)
    setError(null)
    onFileSelect(null)
  }

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-200 cursor-pointer
          ${isDragOver 
            ? 'border-accent bg-accent/5' 
            : 'border-border hover:border-accent/50'
          }
        `}
      >
        <input
          type="file"
          accept=".mp4,.mov,.avi,.mkv,.webm"
          onChange={handleInput}
          disabled={disabled}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <div className="pointer-events-none">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
            <Upload className="w-8 h-8 text-accent" />
          </div>
          
          <p className="text-lg font-medium text-white mb-2">
            Drop your video here or click to browse
          </p>
          <p className="text-sm text-gray-500">
            MP4, MOV, AVI, MKV, WEBM · Up to 500MB · Up to 20 minutes
          </p>
        </div>
      </div>

      {selectedFile && (
        <div className="mt-4 p-4 bg-card border border-border rounded-xl flex items-center gap-3">
          <Film className="w-5 h-5 text-accent" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">{selectedFile.name}</p>
            <p className="text-xs text-gray-500">
              {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
            </p>
          </div>
          <button
            onClick={clearFile}
            className="p-1 hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-score-red">{error}</p>
      )}
    </div>
  )
}
