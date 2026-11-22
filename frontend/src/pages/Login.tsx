import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Eye, EyeOff, KeyRound, Landmark, LogIn } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Brand } from '../components/Brand'
import { ConceptBar } from '../components/Shell'
import { Note, usePageTitle } from '../components/ui'

type Demo = { login: string; password: string | null; who: string; role: string }

export function Login() {
  usePageTitle('Вход')
  const { refresh, notice } = useAuth()
  const [step, setStep] = useState<'password' | 'mfa'>('password')
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState<Demo[] | null>(null)
  const codeRef = useRef<HTMLInputElement>(null)

  useEffect(() => { api.get<{ items: Demo[] }>('/api/demo/accounts').then((d) => setDemo(d.items)).catch(() => setDemo(null)) }, [])
  useEffect(() => { if (step === 'mfa') codeRef.current?.focus() }, [step])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!login.trim() || !password) { setError('Введите логин и пароль'); return }
    setBusy(true)
    try {
      const r = await api.post<{ ok: boolean; mfa_required?: boolean }>('/api/login', { login: login.trim(), password })
      if (r.mfa_required) setStep('mfa')
      else await refresh()
    } catch (err) {
      setError((err as ApiError).message)
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (code.replace(/\s/g, '').length !== 6) { setError('Код — 6 цифр из приложения'); return }
    setBusy(true)
    try {
      await api.post('/api/login/mfa', { code: code.replace(/\s/g, '') })
      await refresh()
    } catch (err) {
      const ae = err as ApiError
      setError(ae.message)
      if (ae.code === 'mfa_expired') { setStep('password'); setCode('') }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <ConceptBar />
      <div className="auth-main">
        <div className="auth-card">
          <div className="brand"><Brand /></div>
          {step === 'password' ? (
            <form onSubmit={submit} className="stack" noValidate>
              <div>
                <h1>Вход в личный кабинет</h1>
                <p className="muted small">Студенты и сотрудники деканата</p>
              </div>
              {notice && <Note tone="amber">{notice}</Note>}
              {error && <Note tone="red">{error}</Note>}
              <div className="field">
                <label htmlFor="login">Логин</label>
                <input id="login" name="username" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} inputMode="email"
                  value={login} onChange={(e) => setLogin(e.target.value)} required placeholder="например, a.sokolova" />
              </div>
              <div className="field">
                <label htmlFor="password">Пароль</label>
                <div className="copy-row">
                  <input id="password" name="password" className="input" type={show ? 'text' : 'password'} autoComplete="current-password"
                    value={password} onChange={(e) => setPassword(e.target.value)} required />
                  <button type="button" className="icon-btn" onClick={() => setShow(!show)} aria-label={show ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={show}>
                    {show ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                  </button>
                </div>
              </div>
              <button className="btn btn-block" disabled={busy}><LogIn aria-hidden="true" />{busy ? 'Проверяем…' : 'Войти'}</button>
              <div className="divider">или</div>
              <button type="button" className="btn btn-secondary btn-block" aria-disabled="true" disabled title="Подключается вузом как оператором ЕСИА">
                <Landmark aria-hidden="true" />Войти через Госуслуги
              </button>
              <p className="xs muted">Вход через Госуслуги (ЕСИА) включается после регистрации системы вуза в ЕСИА — в концепте кнопка неактивна. Забыли пароль? Его сбрасывает деканат по паспорту.</p>
            </form>
          ) : (
            <form onSubmit={submitCode} className="stack" noValidate>
              <div>
                <h1>Код подтверждения</h1>
                <p className="muted small">Откройте приложение-аутентификатор (Яндекс Ключ, Google Authenticator и т. п.) и введите 6 цифр для «{login}».</p>
              </div>
              {error && <Note tone="red">{error}</Note>}
              <div className="field">
                <label htmlFor="code">Код из приложения</label>
                <input id="code" ref={codeRef} className="input code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]*" maxLength={7}
                  value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9 ]/g, ''))} required />
              </div>
              <button className="btn btn-block" disabled={busy}><KeyRound aria-hidden="true" />{busy ? 'Проверяем…' : 'Подтвердить'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => { setStep('password'); setCode(''); setError(null) }}>Другой аккаунт</button>
              {demo && demo.some((d) => d.role === 'staff') && (
                <Note>Для проверяющих: текущий код демо-сотрудника — на странице <a href="/staff-code" target="_blank" rel="noopener">/staff-code</a> (открывается в новой вкладке).</Note>
              )}
            </form>
          )}

          {demo && demo.length > 0 && step === 'password' && (
            <details className="demo-box" open>
              <summary>Тестовые аккаунты для проверки</summary>
              <ul className="demo-list">
                {demo.map((d) => (
                  <li key={d.login}>
                    <button type="button" onClick={() => { setLogin(d.login); setPassword(d.password ?? ''); setError(null) }}>
                      <span className="n">{d.login}</span>{d.password && <span className="muted small"> · {d.password}</span>}
                      <span className="d" style={{ display: 'block' }}>{d.who}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="xs muted" style={{ marginTop: 8 }}>Нажмите на аккаунт — поля заполнятся. В общих тестовых аккаунтах пароль и 2FA не меняются.</p>
            </details>
          )}
        </div>
      </div>
      <p className="auth-foot">Учебный прототип для конкурса. Не является официальным сервисом МГИМО, логотипы вуза не используются, все персональные данные вымышлены. <a href="/about">О проекте</a></p>
    </div>
  )
}
