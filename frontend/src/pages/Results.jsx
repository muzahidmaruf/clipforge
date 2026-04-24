import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Scissors, Download, Wand2, Trash2, Play, RotateCcw } from 'lucide-react'
import JobStatus from '../components/JobStatus'
import ClipGrid from '../components/ClipGrid'
import ConfirmDialog from '../components/ConfirmDialog'
import { getJob, deleteJob, resumeJob, restartJob, streamCleanedVideo, downloadCleanedVideo } from '../api/client'

const formatSeconds = (s) => {
  if (s == null || Number.isNaN(s)) return '—'
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return `${m}:${String(r).padStart(2, '0')}`
}

const POLL_INTERVAL = 3000

export default function Results() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showDeleteDialog, setShowDeleteDialog]   = useState(false)
  const [deleting, setDeleting]                   = useState(false)
  const [showRestartDialog, setShowRestartDialog] = useState(false)
  const [actionLoading, setActionLoading]         = useState(false)

  useEffect(() => {
    let interval
    
    const fetchJob = async () => {
      try {
        const response = await getJob(jobId)
        setJob(response.data)
        setError(null)
        
        // Stop polling when done
        if (['completed', 'failed'].includes(response.data.status)) {
          clearInterval(interval)
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load job')
      } finally {
        setLoading(false)
      }
    }

    fetchJob()
    interval = setInterval(fetchJob, POLL_INTERVAL)
    
    return () => clearInterval(interval)
  }, [jobId])

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteJob(jobId)
      navigate('/')
    } catch {
      setDeleting(false)
      setShowDeleteDialog(false)
    }
  }

  const handleResume = async () => {
    setActionLoading(true)
    try {
      await resumeJob(jobId)
      // Polling will pick up the new status automatically
    } catch { /* ignore */ } finally {
      setActionLoading(false)
    }
  }

  const handleRestart = async () => {
    setActionLoading(true)
    setShowRestartDialog(false)
    try {
      await restartJob(jobId)
    } catch { /* ignore */ } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  if (error && !job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-score-red mb-4">{error}</p>
          <Link to="/" className="text-accent hover:underline">Back home</Link>
        </div>
      </div>
    )
  }

  const isDone = job?.status === 'completed'
  const hasClips = job?.clips && job.clips.length > 0
  const cleaned = job?.cleaned
  const hasCleaned = cleaned?.available
  const mode = job?.mode || 'clips'

  return (
    <>
      <ConfirmDialog
        open={showDeleteDialog}
        title="Delete this project?"
        message={`"${job?.filename || `Job ${jobId.slice(0, 8)}`}" and all its clips will be permanently removed. This can't be undone.`}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteDialog(false)}
      />

      <ConfirmDialog
        open={showRestartDialog}
        title="Restart from scratch?"
        message="This will delete all checkpoints and clips, then re-run transcription and AI analysis from the beginning."
        confirmLabel="Restart"
        loading={actionLoading}
        onConfirm={handleRestart}
        onCancel={() => setShowRestartDialog(false)}
      />

    <div className="min-h-screen">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link
            to="/"
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="text-sm">Back</span>
          </Link>

          <div className="flex items-center gap-2 flex-1">
            <Scissors className="w-5 h-5 text-accent" />
            <span className="font-semibold text-white truncate">
              {job?.filename || `Job ${jobId.slice(0, 8)}...`}
            </span>
          </div>

          {/* Resume / Restart — only for failed jobs */}
          {job?.status === 'failed' && (
            <div className="flex items-center gap-1">
              <button
                onClick={handleResume}
                disabled={actionLoading}
                title="Resume from checkpoint"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-accent hover:bg-accent/10 border border-accent/30 hover:border-accent transition-colors disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                <span className="hidden sm:inline">Resume</span>
              </button>
              <button
                onClick={() => setShowRestartDialog(true)}
                disabled={actionLoading}
                title="Restart from scratch"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-orange-400 hover:bg-orange-400/10 border border-transparent hover:border-orange-400/20 transition-colors disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" />
                <span className="hidden sm:inline">Restart</span>
              </button>
            </div>
          )}

          {/* Delete project button */}
          {job && (
            <button
              onClick={() => setShowDeleteDialog(true)}
              title="Delete project"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-score-red hover:bg-score-red/10 border border-transparent hover:border-score-red/20 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span className="hidden sm:inline">Delete</span>
            </button>
          )}
        </div>

        {/* Processing status */}
        {!isDone && (
          <div className="mb-12">
            <JobStatus job={job} />
          </div>
        )}

        {/* Cleaned video panel */}
        {isDone && hasCleaned && (
          <div className="mb-10 p-5 bg-card border border-border rounded-2xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Wand2 className="w-5 h-5 text-accent" />
                <h2 className="text-xl font-bold text-white">Cleaned video</h2>
              </div>
              <a
                href={downloadCleanedVideo(job.job_id || jobId)}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                Download
              </a>
            </div>

            <video
              src={streamCleanedVideo(job.job_id || jobId)}
              controls
              className="w-full max-h-[60vh] rounded-xl bg-black"
              preload="metadata"
            />

            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              <div className="p-2 bg-background rounded-lg">
                <div className="text-[11px] text-gray-500 uppercase tracking-wide">Original</div>
                <div className="text-lg font-semibold text-white">{formatSeconds(cleaned.original_duration)}</div>
              </div>
              <div className="p-2 bg-background rounded-lg">
                <div className="text-[11px] text-gray-500 uppercase tracking-wide">Cleaned</div>
                <div className="text-lg font-semibold text-accent">{formatSeconds(cleaned.cleaned_duration)}</div>
              </div>
              <div className="p-2 bg-background rounded-lg">
                <div className="text-[11px] text-gray-500 uppercase tracking-wide">Saved</div>
                <div className="text-lg font-semibold text-white">
                  {formatSeconds(cleaned.saved_seconds)}
                  {cleaned.fillers_removed != null && (
                    <span className="ml-1 text-xs text-gray-500">· {cleaned.fillers_removed} fillers</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Clips grid */}
        {isDone && (mode === 'clips' || mode === 'both') && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-white">Your Clips</h2>
              <span className="text-sm text-gray-500">
                {job.clips_count || 0} clips generated
              </span>
            </div>

            <ClipGrid clips={job.clips} />
          </div>
        )}

        {/* Empty states */}
        {isDone && (mode === 'clips' || mode === 'both') && !hasClips && (
          <div className="text-center py-16">
            <p className="text-gray-500">No clips were generated from this video</p>
          </div>
        )}
        {isDone && mode === 'clean' && !hasCleaned && (
          <div className="text-center py-16">
            <p className="text-gray-500">Cleaning didn't produce an output — the transcript may have been empty.</p>
          </div>
        )}
      </div>
    </div>
    </>
  )
}
