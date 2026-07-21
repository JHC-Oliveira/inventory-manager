import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { getErrorMessage } from '../lib/errors'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      const data = await login({ email, password })
      setAuth(data.access_token, data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(getErrorMessage(err, 'Invalid email or password'))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <h1 className="text-2xl font-bold text-white">Inventory Manager</h1>
        <p className="mt-2 text-sm text-slate-400">Sign in to continue</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <input
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setError('')
            }}
          />

          {error && <p className="text-sm text-red-400 whitespace-pre-line">{error}</p>}

          <button className="w-full rounded-lg bg-indigo-600 py-2 font-medium text-white hover:bg-indigo-500">
            Sign in
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-400">
          No account? <Link to="/register" className="text-indigo-400">Register</Link>
        </p>
      </div>
    </div>
  )
}