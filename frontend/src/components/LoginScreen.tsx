import { useState } from 'react'
import { createUser } from '../api'
import { setUsername } from '../auth'

interface Props {
  onLogin: (username: string) => void
}

export default function LoginScreen({ onLogin }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const name = value.trim()
    if (!name) return
    setLoading(true)
    setError(null)
    try {
      await createUser(name)
      setUsername(name)
      onLogin(name)
    } catch {
      setError('Could not connect. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      <h1>Coffee recommendations</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          value={value}
          onChange={e => setValue(e.target.value)}
          disabled={loading}
          placeholder="e.g. alice"
          autoFocus
        />
        <button type="submit" disabled={loading || !value.trim()}>
          {loading ? 'Connecting…' : 'Continue'}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  )
}
