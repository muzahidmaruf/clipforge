import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, Film, AlertCircle, CheckCircle, Loader, RefreshCw, Trash2, X } from 'lucide-react'
import { deleteJob, retryJob, cancelJob } from '../api/client'

function getStatusIcon(status) {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4 text-score-green" />
    case 'failed': return <AlertCircle className="w-4 h-4 text-score-red" />
    case 'pending': return <Clock className="w-4 h-4 text-gray-500" />
    default: return <Loader className="w-4 h-4 text-accent animate-spin" />
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'completed': return 'bg-score-green/10 text-score-green border-score-green/20'
    case 'failed': return 'bg-score-red/10 text-score-red border-score-red/20'
    case 'pending': return 'bg-gray-500/10 text-gray-400 border-gray-500/20'
    default: return 'bg-accent/10 text-accent border-accent/20'
  }
}

const isActive = (job) =>
  ['pending', 'transcribing', 'analyzing', 'cutting'].includes(job.status)

const isStuck = (job) =>
  job.status === 'failed' ||
  (job.status === 'pending' && job.progress === 0)

export default function JobList() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState({})
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
    } catch {
    } finally {
      setActionLoading(prev => ({ ...prev, [jobId]: null }))
    }
  }

  const handleRetry = async (e, jobId) => {
    e.stopPropagation()
    setActionLoading(prev => ({ ...prev, [jobId]: 'retry' }))
    try {
      await retryJob(jobId)
      await fetchJobs()
    } catch {
    } finally {
      setActionLoading(prev => ({ ...prev, [jobId]: null }))
    }
  }

  const handleDelete = async (e, jobId) => {
    e.stopPropagation()
    setActionLoading(prev => ({ ...prev, [jobId]: 'delete' }))
    try {
      await deleteJob(jobId)
      setJobs(prev => prev.filter(j => j.job_id !== jobId))
    } catch {
    } finally {
      setActionLoading(prev => ({ ...prev, [jobId]: null }))
    }
  }

  if (loading) return null
  if (jobs.length === 0) return null

  return (
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
            {isActive(job) && (
              <div className="flex items-center gap-1 ml-1" onClick={e => e.stopPropagation()}>
                <button
                  onClick={(e) => handleCancel(e, job.job_id)}
                  disabled={!!actionLoading[job.job_id]}
                  title="Cancel"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-orange-400 hover:bg-orange-400/10 transition-colors disabled:opacity-50"
                >
                  <X className={`w-3.5 h-3.5 ${actionLoading[job.job_id] === 'cancel' ? 'animate-spin' : ''}`} />
                </button>
              </div>
            )}
            {isStuck(job) && (
              <div className="flex items-center gap-1 ml-1" onClick={e => e.stopPropagation()}>
                <button
                  onClick={(e) => handleRetry(e, job.job_id)}
                  disabled={!!actionLoading[job.job_id]}
                  title="Retry"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${actionLoading[job.job_id] === 'retry' ? 'animate-spin' : ''}`} />
                </button>
                <button
                  onClick={(e) => handleDelete(e, job.job_id)}
                  disabled={!!actionLoading[job.job_id]}
                  title="Delete"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-score-red hover:bg-score-red/10 transition-colors disabled:opacity-50"
                >
                  <Trash2 className={`w-3.5 h-3.5 ${actionLoading[job.job_id] === 'delete' ? 'animate-spin' : ''}`} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
