import ClipCard from './ClipCard'

export default function ClipGrid({ clips }) {
  if (!clips || clips.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">No clips generated yet</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {clips.map((clip) => (
        <ClipCard key={clip.id} clip={clip} />
      ))}
    </div>
  )
}
