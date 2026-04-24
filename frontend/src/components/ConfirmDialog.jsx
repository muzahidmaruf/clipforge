import { useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'

/**
 * Minimal confirm dialog / modal.
 *
 * Props:
 *   open         boolean — whether the dialog is visible
 *   title        string
 *   message      string | ReactNode
 *   confirmLabel string (default "Delete")
 *   cancelLabel  string (default "Cancel")
 *   danger       boolean — styles the confirm button red (default true)
 *   onConfirm    () => void
 *   onCancel     () => void
 *   loading      boolean — disables buttons while an async action is running
 */
export default function ConfirmDialog({
  open,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  danger = true,
  onConfirm,
  onCancel,
  loading = false,
}) {
  const cancelRef = useRef(null)

  // Focus the cancel button when the dialog opens (safe default)
  useEffect(() => {
    if (open) cancelRef.current?.focus()
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') onCancel?.() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  if (!open) return null

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel?.() }}
    >
      {/* Panel */}
      <div className="w-full max-w-sm bg-card border border-border rounded-2xl shadow-2xl p-6 flex flex-col gap-4">
        {/* Icon + title */}
        <div className="flex items-start gap-3">
          <div className={`mt-0.5 flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${danger ? 'bg-score-red/15' : 'bg-accent/15'}`}>
            <AlertTriangle className={`w-5 h-5 ${danger ? 'text-score-red' : 'text-accent'}`} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white leading-tight">{title}</h2>
            {message && (
              <p className="mt-1 text-sm text-gray-400 leading-relaxed">{message}</p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-300 bg-background border border-border hover:border-gray-500 transition-colors disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50 ${
              danger
                ? 'bg-score-red hover:bg-score-red/80'
                : 'bg-accent hover:bg-accent-hover'
            }`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                {confirmLabel}…
              </span>
            ) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
