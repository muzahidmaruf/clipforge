export default function ProgressBar({ progress, label }) {
  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm text-gray-400">{label || 'Progress'}</span>
        <span className="text-sm font-medium text-white">{progress}%</span>
      </div>
      <div className="h-2 bg-card rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
