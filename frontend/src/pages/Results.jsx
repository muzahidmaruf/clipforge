import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Scissors } from 'lucide-react'
import JobStatus from '../components/JobStatus'
import ClipGrid from '../components/ClipGrid'
import { getJob } from '../api/client'

const POLL_INTERVAL = 3000

export default function Results() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

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

  return (
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
          
          <div className="flex items-center gap-2">
            <Scissors className="w-5 h-5 text-accent" />
            <span className="font-semibold text-white">Job {jobId.slice(0, 8)}...</span>
          </div>
        </div>

        {/* Processing status */}
        {!isDone && (
          <div className="mb-12">
            <JobStatus job={job} />
          </div>
        )}

        {/* Results */}
        {isDone && (
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

        {/* Empty state */}
        {isDone && !hasClips && (
          <div className="text-center py-16">
            <p className="text-gray-500">No clips were generated from this video</p>
          </div>
        )}
      </div>
    </div>
  )
}
