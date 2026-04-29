import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Scissors, UserPlus, Loader2, CheckCircle2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function Signup() {
  const { signUp } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [success, setSuccess]   = useState(false)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    setLoading(true)
    const { data, error } = await signUp(email.trim(), password)
    setLoading(false)
    if (error) {
      setError(error.message)
      return
    }
    // If email confirmation is disabled in Supabase the user is signed in immediately
    if (data.session) {
      navigate('/', { replace: true })
    } else {
      setSuccess(true)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-card border border-border rounded-2xl p-6 text-center">
          <CheckCircle2 className="w-10 h-10 text-score-green mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-white mb-1">Check your email</h2>
          <p className="text-sm text-gray-400">
            We sent a confirmation link to <strong>{email}</strong>. Click it to activate your account.
          </p>
          <Link to="/login" className="inline-block mt-4 text-sm text-accent hover:underline">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/10 mb-4">
            <Scissors className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-2xl font-bold text-white">Create account</h1>
          <p className="text-sm text-gray-400 mt-1">Start clipping in seconds</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3 bg-card border border-border rounded-2xl p-5">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Email</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full p-2.5 bg-background border border-border rounded-lg text-white text-sm focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Password</label>
            <input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-2.5 bg-background border border-border rounded-lg text-white text-sm focus:border-accent focus:outline-none"
            />
            <p className="text-[11px] text-gray-500 mt-1">At least 6 characters.</p>
          </div>

          {error && (
            <p className="text-xs text-score-red bg-score-red/10 border border-score-red/30 rounded-lg p-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {loading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <UserPlus className="w-4 h-4" />}
            Create account
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-4">
          Already registered?{' '}
          <Link to="/login" className="text-accent hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
