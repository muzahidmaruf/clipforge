import { useState, useEffect } from 'react'

const STEPS = [
  { label: 'Transcribing Audio', icon: '🎙️', status: 'transcribing' },
  { label: 'Analyzing for Best Moments', icon: '🧠', status: 'analyzing' },
  { label: 'Cutting Clips', icon: '✂️', status: 'cutting' },
  { label: 'Done', icon: '✅', status: 'completed' },
]

export default function JobStatus({ job }) {
  const [animatedProgress, setAnimatedProgress] = useState(0)
  
  useEffect(() => {
    const target = job?.progress || 0
    const timer = setTimeout(() => setAnimatedProgress(target), 100)
    return () => clearTimeout(timer)
  }, [job?.progress])

  if (!job) return null

  const { status, progress, error_message } = job

  const getStepState = (step) => {
    if (status === 'failed') return 'failed'
    if (status === 'completed') return 'done'
    if (step.status === status) return 'active'
    
    const stepOrder = ['transcribing', 'analyzing', 'cutting', 'completed']
    const currentIdx = stepOrder.indexOf(status)
    const stepIdx = stepOrder.indexOf(step.status)
    return stepIdx < currentIdx ? 'done' : 'pending'
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-gray-400">Processing... {progress}%</span>
          <span className="text-sm text-gray-500">{status}</span>
        </div>
        <div className="h-2 bg-card rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
            style={{ width: `${animatedProgress}%` }}
          />
        </div>
      </div>

      {/* Step indicators */}
      <div className="space-y-3">
        {STEPS.map((step, idx) => {
          const state = getStepState(step)
          return (
            <div
              key={idx}
              className={`
                flex items-center gap-4 p-4 rounded-xl border transition-all duration-300
                ${state === 'active' 
                  ? 'bg-accent/5 border-accent/30' 
                  : state === 'done'
                  ? 'bg-card/50 border-border'
                  : state === 'failed'
                  ? 'bg-score-red/5 border-score-red/30'
                  : 'bg-card/30 border-border/50'
                }
              `}
            >
              <div className={`
                w-8 h-8 rounded-full flex items-center justify-center text-sm
                ${state === 'done' 
                  ? 'bg-score-green/20 text-score-green' 
                  : state === 'active'
                  ? 'bg-accent/20 text-accent'
                  : state === 'failed'
                  ? 'bg-score-red/20 text-score-red'
                  : 'bg-border text-gray-500'
                }
              `}>
                {state === 'done' ? '✓' : state === 'active' ? '○' : step.icon}
              </div>
              <span className={`
                text-sm font-medium
                ${state === 'active' ? 'text-white' : 'text-gray-400'}
              `}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>

      {error_message && (
        <div className="mt-6 p-4 bg-score-red/10 border border-score-red/30 rounded-xl">
          <p className="text-sm text-score-red">{error_message}</p>
        </div>
      )}
    </div>
  )
}
