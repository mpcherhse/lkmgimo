import { useState, type FormEvent } from 'react'
import { ShieldAlert } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Brand } from '../components/Brand'
import { ConceptBar } from '../components/Shell'
import { Note } from '../components/ui'

/** сеанс открыли на другом устройстве: продолжить можно только с паролем */
export function Reauth() {
  const { refresh, logout } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/me/reauth', { password })
      await refresh()
    } catch (err) {
      setError((err as ApiError).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="auth">
      <ConceptBar />
      <div className="auth-main">
        <form className="auth-card stack" onSubmit={submit}>
          <div className="brand"><Brand /></div>
          <Note tone="amber" icon={<ShieldAlert aria-hidden="true" />}>Этот сеанс открыли с другого устройства или браузера. Если это вы — подтвердите паролем. Если нет — выйдите и смените пароль.</Note>
          {error && <Note tone="red">{error}</Note>}
          <div className="field">
            <label htmlFor="rp">Пароль</label>
            <input id="rp" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button className="btn btn-block" disabled={busy || !password}>Подтвердить</button>
          <button type="button" className="btn btn-secondary btn-block" onClick={logout}>Выйти</button>
        </form>
      </div>
    </div>
  )
}
