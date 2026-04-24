import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, AlertCircle, CheckCircle, Loader, Play, RotateCcw, Trash2, X } from 'lucide-react'
import { deleteJob, resumeJob, restartJob, cancelJob } from '../api/client'
import ConfirmDialog from './ConfirmDialog'

function getStatusIcon(status) {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4 text-score-green" />
    case 'failed':    return <AlertCircle className="w-4 h-4 text-score-red" />
    case 'pending':   return <Clock className="w-4 h-4 text-gray-500" />
    default:          return <Loader className="w-4 h-4 text-accent animate-spin" />
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'completed': return 'bg-score-green/10 text-score-green border-score-green/20'
    case 'failed':    return 'bg-score-red/10 text-score-red border-score-red/20'
    case 'pending':   return 'bg-gray-500/10 text-gray-400 border-gray-500/20'
    default:          return 'bg-accent/10 text-accent border-accent/20'
  }
}

const isActive = (job) =>
  ['pending', 'transcribing', 'analyzing', 'cutting'].includes(job.status)

const isStuck = (job) =>
  job.status === 'failed' ||
  (job.status === 'pending' && job.progress === 0)

export default function JobList() {
  const [jobs, setJobs]               = useState([])
  const [loading, setLoading]         = useState(true)
  const [actionLoading, setActionLoading] = useState({})
  // confirm dialog state
  const [confirmJob, setConfirmJob]       = useState(null)  // job object to delete
  const [deleting, setDeleting]           = useState(false)
  const [confirmRestart, setConfirmRestart] = useState(null) // job object to restart
  const navigate = useNavigate()

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/jobs')
      if (!res.ok) throw new Error()
      setJobs(await res.json())
    } catch {
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleCancel = async (e, jobId) => {
    e.stopPropagation()
    setActionLoading(prev => ({ ...prev, [jobId]: 'cancel' }))
    try {
      await cancelJob(jobId)
      await fetchJobs()
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [jobId]: null }))
    }
  }

  const handleResume = async (e, jobId) => {
    e.stopPropagation()
    setActionLoading(prev => ({ ...prev, [jobId]: 'resume' }))
    try {
      await resumeJob(jobId)
      await fetchJobs()
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [jobId]: null }))
    }
  }

  const confirmRestartAction = async () => {
    if (!confirmRestart) return
    setActionLoading(prev => ({ ...prev, [confirmRestart.job_id]: 'restart' }))
    try {
      await restartJob(confirmRestart.job_id)
      await fetchJobs()
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [confirmRestart.job_id]: null }))
      setConfirmRestart(null)
    }
  }

  // Step 1: show confirmation dialog
  const requestDelete = (e, job) => {
    e.stopPropagation()
    setConfirmJob(job)
  }

  // Step 2: user confirmed — actually delete
  const confirmDelete = async () => {
    if (!confirmJob) return
    setDeleting(true)
    try {
      await deleteJob(confirmJob.job_id)
      setJobs(prev => prev.filter(j => j.job_id !== confirmJob.job_id))
    } catch { /* ignore */ } finally {
      setDeleting(false)
      setConfirmJob(null)
    }
  }

  if (loading) return null
  if (jobs.length === 0) return null

  return (
    <>
      <ConfirmDialog
        open={!!confirmJob}
        title="Delete this project?"
        message={
          confirmJob
            ? `"${confirmJob.filename || `Job ${confirmJob.job_id.slice(0, 8)}`}" and all its clips will be permanently removed. This can't be undone.`
            : ''
        }
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setConfirmJob(null)}
      />

      <ConfirmDialog
        open={!!confirmRestart}
        title="Restart from scratch?"
        message={
          confirmRestart
            ? `This will delete all clips and checkpoints for "${confirmRestart.filename || `Job ${confirmRestart.job_id.slice(0, 8)}`}" and start over. Transcription + AI analysis will run again.`
            : ''
        }
        confirmLabel="Restart"
        loading={!!actionLoading[confirmRestart?.job_id]}
        onConfirm={confirmRestartAction}
        onCancel={() => setConfirmRestart(null)}
      />

      <div className="mt-12">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Jobs</h2>
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.job_id}
              onClick={() => navigate(`/results/${job.job_id}`)}
              className="w-full text-left p-4 bg-card border border-border rounded-xl hover:border-accent/30 transition-colors flex items-center gap-4 cursor-pointer"
            >
              {getStatusIcon(job.status)}

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {job.filename || `Job ${job.job_id.slice(0, 8)}`}
                </p>
                <p className="text-xs text-gray-500">
                  {job.status} · {job.progress}%
                  {job.error_message && (
                    <span className="text-score-red ml-2 truncate">{job.error_message}</span>
                  )}
                </p>
              </div>

              <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(job.status)}`}>
                {job.status}
              </span>

              {/* Action buttons — stop click propagation so row nav doesn't fire */}
              <div className="flex items-center gap-1 ml-1" onClick={e => e.stopPropagation()}>
                {/* Cancel — only for active jobs */}
                {isActive(job) && (
                  <button
                    onClick={(e) => handleCancel(e, job.job_id)}
                    disabled={!!actionLoading[job.job_id]}
                    title="Cancel"
                    className="p-1.5 rounded-lg text-gray-400 hover:text-orange-400 hover:bg-orange-400/10 transition-colors disabled:opacity-50"
                  >
                    <X className={`w-3.5 h-3.5 ${actionLoading[job.job_id] === 'cancel' ? 'animate-spin' : ''}`} />
                  </button>
                )}

                {/* Resume + Restart — only for stuck / failed jobs */}
                {isStuck(job) && (
                  <>
                    {/* Resume: continues from checkpoint */}
                    <button
                      onClick={(e) => handleResume(e, job.job_id)}
                      disabled={!!actionLoading[job.job_id]}
                      title="Resume from checkpoint"
                      className="p-1.5 rounded-lg text-gray-400 hover:text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
                    >
                      <Play className={`w-3.5 h-3.5 ${actionLoading[job.job_id] === 'resume' ? 'animate-pulse' : ''}`} />
                    </button>
                    {/* Restart: wipes checkpoints, starts fresh */}
                    <button
                      onClick={(e) => { e.stopPropagation(); setConfirmRestart(job) }}
                      disabled={!!actionLoading[job.job_id]}
                      title="Restart from scratch"
                      className="p-1.5 rounded-lg text-gray-400 hover:text-orange-400 hover:bg-orange-400/10 transition-colors disabled:opacity-50"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}

                {/* Delete — available on ALL jobs (not while a cancel/retry is in flight) */}
                <button
                  onClick={(e) => requestDelete(e, job)}
                  disabled={!!actionLoading[job.job_id]}
                  title="Delete project"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-score-red hover:bg-score-red/10 transition-colors disabled:opacity-50"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
