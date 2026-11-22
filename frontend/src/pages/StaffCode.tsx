import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { Brand } from '../components/Brand'
import { ConceptBar } from '../components/Shell'
import { Note, usePageTitle } from '../components/ui'

/** только на стенде жюри: текущий код 2FA общего демо-сотрудника, чтобы не ставить приложение-аутентификатор */
export default function StaffCode() {
  usePageTitle('Код 2FA для проверяющих')
  const [d, setD] = useState<{ login: string; code: string; valid_for: number } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [left, setLeft] = useState(0)
  useEffect(() => {
    let timer: number
    const load = async () => {
      try { const r = await api.get<{ login: string; code: string; valid_for: number }>('/api/demo/totp'); setD(r); setLeft(r.valid_for); timer = window.setTimeout(load, r.valid_for * 1000 + 300) }
      catch (e) { setErr((e as ApiError).status === 404 ? 'Подсказка отключена на этом стенде.' : (e as ApiError).message) }
    }
    load()
    return () => window.clearTimeout(timer)
  }, [])
  useEffect(() => { const t = window.setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000); return () => window.clearInterval(t) }, [])
  return (
    <div className="auth">
      <ConceptBar />
      <div className="auth-main">
        <div className="auth-card stack">
          <div className="brand"><Brand /></div>
          <h1>Код 2FA для проверяющих</h1>
          <p className="small muted">Сотрудникам деканата вход только с кодом из приложения-аутентификатора. Чтобы жюри не пришлось его настраивать, на демо-стенде текущий код общего аккаунта показан здесь. В действующей системе этой страницы нет.</p>
          {err && <Note tone="red">{err}</Note>}
          {d && (
            <>
              <div className="secret num" aria-live="polite" style={{ fontSize: '2rem', letterSpacing: '0.25em' }}>{d.code}</div>
              <p className="small">Аккаунт <b>{d.login}</b> · код сменится через <span className="num">{left}</span> с</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
