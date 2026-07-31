import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { register } from '../api/auth'
import { getErrorMessage } from '../lib/errors'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      await register({ email, password, full_name: fullName })
      navigate('/login')
    } catch (err) {
      setError(getErrorMessage(err, 'Registration failed'))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <h1 className="text-2xl font-bold text-white">Create account</h1>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <input
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white"
            placeholder="Full name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
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
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
            <li>Password must be at least 8 characters</li>
            <li>Password must contain at least one uppercase letter</li>
            <li>Password must contain at least one number</li>
            <li>Full name must be at least 2 characters</li>
          </ul>

          {error && (
            <p className="text-sm text-red-400 whitespace-pre-line">{error}</p>
          )}

          <button className="w-full rounded-lg bg-indigo-600 py-2 font-medium text-white hover:bg-indigo-500">
            Register
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="text-indigo-400">
            Login
          </Link>
        </p>
      </div>
    </div>
  )
}
