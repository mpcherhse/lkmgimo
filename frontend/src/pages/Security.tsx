import { useState, type FormEvent } from 'react'
import { KeyRound, Laptop, LogOut, ShieldCheck, Smartphone } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLoad } from '../lib/useLoad'
import { dateTime, relative } from '../lib/format'
import type { SessionView } from '../lib/types'
import { LoadError, Note, PageSkeleton, Panel, useToast, usePageTitle } from '../components/ui'

type Sessions = { current: SessionView | null; others: SessionView[]; ttl_days: number; ttl_options: number[]; sudo_until: string | null }
type Login = { at: string; result: string; reason: string | null; device: string; ip: string }

export function ReauthInline({ onDone, text }: { onDone: () => void; text: string }) {
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { await api.post('/api/me/reauth', { password }); onDone() } catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} className="note stack-sm" style={{ display: 'flex', flexDirection: 'column' }}>
      <span>{text}</span>
      {err && <span className="small" style={{ color: 'var(--red-700)' }}>{err}</span>}
      <div className="row">
        <label className="sr-only" htmlFor="reauth-pw">Пароль</label>
        <input id="reauth-pw" className="input" style={{ maxWidth: 260 }} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Пароль" />
        <button className="btn" disabled={busy || !password}>Подтвердить</button>
      </div>
    </form>
  )
}

function SessionRow({ s, onEnd }: { s: SessionView; onEnd?: () => void }) {
  const Icon = s.mobile ? Smartphone : Laptop
  return (
    <li className="list-item">
      <Icon aria-hidden="true" style={{ width: 20, height: 20, color: 'var(--navy-600)', flex: 'none', marginTop: 2 }} />
      <span className="grow">
        <span className="title" style={{ display: 'block' }}>{s.label}{s.current && <span className="badge badge-green" style={{ marginLeft: 6 }}>это устройство</span>}{s.challenge && <span className="badge badge-amber" style={{ marginLeft: 6 }}>ждёт пароль</span>}</span>
        <span className="meta">{[s.browser, s.os].filter(Boolean).join(', ')}{s.ip ? ` · ${s.ip}` : ''} · вход {dateTime(s.created_at)} · активность {relative(s.last_active_at)}</span>
      </span>
      {onEnd && <button className="btn btn-danger btn-sm" onClick={onEnd}>Завершить</button>}
    </li>
  )
}

export default function Security() {
  usePageTitle('Безопасность')
  const { me, refresh } = useAuth()
  const toast = useToast()
  const sessions = useLoad<Sessions>('/api/me/sessions')
  const logins = useLoad<{ items: Login[] }>('/api/me/logins')
  const [err, setErr] = useState<string | null>(null)
  const [pw, setPw] = useState({ current: '', next: '' })
  const [check, setCheck] = useState<{ problems: string[]; strength: string } | null>(null)
  const [totp, setTotp] = useState<{ secret: string; qr: string } | null>(null)
  const [code, setCode] = useState('')
  const [reauthFor, setReauthFor] = useState<null | 'totp'>(null)

  async function end(id: string) { try { await api.del(`/api/me/sessions/${id}`); sessions.reload(true); toast('Сеанс завершён') } catch (e) { setErr((e as ApiError).message) } }
  async function endOthers() {
    if (!window.confirm('Завершить все сеансы, кроме этого?')) return
    try { const r = await api.post<{ terminated: number }>('/api/me/sessions/terminate-others'); sessions.reload(true); toast(`Завершено сеансов: ${r.terminated}`) } catch (e) { setErr((e as ApiError).message) }
  }
  async function ttl(days: number) { try { await api.put('/api/me/session-ttl', { days }); sessions.reload(true); toast('Сохранено') } catch (e) { setErr((e as ApiError).message) } }
  async function checkPw(v: string) {
    setPw((p) => ({ ...p, next: v }))
    if (v.length < 4) { setCheck(null); return }
    try { setCheck(await api.post('/api/me/password/check', { password: v })) } catch { setCheck(null) }
  }
  async function changePw(e: FormEvent) {
    e.preventDefault(); setErr(null)
    try { await api.post('/api/me/password', { current: pw.current, new: pw.next }); setPw({ current: '', next: '' }); setCheck(null); toast('Пароль изменён, другие сеансы завершены'); sessions.reload(true) }
    catch (x) { setErr((x as ApiError).message) }
  }
  async function totpSetup() {
    setErr(null)
    try { setTotp(await api.post('/api/me/2fa/setup')) } catch (x) { const ae = x as ApiError; if (ae.code === 'reauth_required') setReauthFor('totp'); else setErr(ae.message) }
  }
  async function totpEnable(e: FormEvent) {
    e.preventDefault(); setErr(null)
    try { await api.post('/api/me/2fa/enable', { code }); setTotp(null); setCode(''); await refresh(); toast('Двухфакторная защита включена') } catch (x) { setErr((x as ApiError).message) }
  }

  if (sessions.loading && !sessions.data) return <PageSkeleton />
  if (sessions.error && !sessions.data) return <LoadError error={sessions.error} retry={sessions.reload} />
  const s = sessions.data!

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Безопасность</h1>
        <p className="sub">Где выполнен вход, история входов, пароль и второй фактор. Ключ сеанса меняется каждые 30 минут: если кто-то скопирует ваш вход, сеанс завершится и вы получите уведомление.</p>
      </div>
      {err && <Note tone="red">{err}</Note>}
      {me?.demo && <Note>Это общий тестовый аккаунт для проверяющих: смена пароля и 2FA в нём отключены, чтобы никого не запереть. Всё остальное работает.</Note>}

      <div className="grid grid-2">
        <Panel title="Сеансы" id="sess" flush action={s.others.length > 0 ? <button className="btn btn-ghost btn-sm more" onClick={endOthers}><LogOut aria-hidden="true" />Завершить остальные</button> : undefined}>
          <ul className="list">
            {s.current && <SessionRow s={s.current} />}
            {s.others.map((o) => <SessionRow key={o.id} s={o} onEnd={() => end(o.id)} />)}
          </ul>
          <div className="panel-body" style={{ paddingTop: 4 }}>
            <div className="field" style={{ maxWidth: 320 }}>
              <label htmlFor="ttl">Выходить автоматически, если не заходил</label>
              <select id="ttl" className="select" value={s.ttl_days} onChange={(e) => ttl(Number(e.target.value))}>
                {s.ttl_options.map((d) => <option key={d} value={d}>{d} дней</option>)}
              </select>
            </div>
          </div>
        </Panel>

        <Panel title="Второй фактор (2FA)" id="tfa">
          {me?.totp_enabled ? (
            <Note tone="green" icon={<ShieldCheck aria-hidden="true" />}>Включён. При входе нужен код из приложения-аутентификатора.{me.role === 'staff' && ' Для сотрудников деканата обязателен.'}</Note>
          ) : totp ? (
            <form className="stack-sm" onSubmit={totpEnable}>
              <p className="small">Отсканируйте код в Яндекс Ключе, Google Authenticator или другом приложении и введите 6 цифр.</p>
              <div className="row" style={{ alignItems: 'flex-start' }}>
                <img className="qr" width={168} height={168} src={totp.qr} alt="QR-код для приложения-аутентификатора" />
                <div className="stack-sm"><span className="xs muted">Или введите ключ вручную:</span><code className="code">{totp.secret}</code></div>
              </div>
              <div className="row">
                <input className="input code-input" style={{ maxWidth: 180 }} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} aria-label="Код из приложения" />
                <button className="btn" disabled={code.length !== 6}>Включить</button>
              </div>
            </form>
          ) : reauthFor === 'totp' ? (
            <ReauthInline text="Подтвердите вход паролем, чтобы настроить второй фактор." onDone={() => { setReauthFor(null); totpSetup() }} />
          ) : (
            <div className="stack-sm">
              <p className="small">Даже если пароль узнают, без телефона войти не получится.</p>
              <button className="btn btn-secondary" style={{ alignSelf: 'flex-start' }} onClick={totpSetup} disabled={me?.demo}><KeyRound aria-hidden="true" />Включить 2FA</button>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid grid-2">
        <Panel title="Смена пароля" id="pw">
          <form className="stack-sm" onSubmit={changePw}>
            <div className="field"><label htmlFor="cur">Текущий пароль</label><input id="cur" className="input" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} disabled={me?.demo} /></div>
            <div className="field">
              <label htmlFor="new">Новый пароль</label>
              <input id="new" className="input" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => checkPw(e.target.value)} disabled={me?.demo} aria-describedby="pw-hint" />
              <span id="pw-hint" className="hint">Лучше фраза из 3–4 слов с цифрами внутри. Пароль проверяется по словарю частых паролей и русским словам в английской раскладке.</span>
              {check && <span className={check.problems.length ? 'err' : 'hint'}>{check.problems[0] ?? `Надёжность: ${check.strength}`}</span>}
            </div>
            <button className="btn" style={{ alignSelf: 'flex-start' }} disabled={me?.demo || !pw.current || !pw.next || !!check?.problems.length}>Сменить пароль</button>
          </form>
        </Panel>

        <Panel title="История входов за 30 дней" id="logins" flush>
          {logins.data && (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Когда</th><th>Устройство</th><th>Результат</th></tr></thead>
                <tbody>
                  {logins.data.items.slice(0, 15).map((l, i) => (
                    <tr key={i}>
                      <td className="nowrap">{dateTime(l.at)}</td>
                      <td>{l.device}<div className="xs muted">{l.ip}</div></td>
                      <td>{l.result === 'ok' ? <span className="badge badge-green">вход</span> : <span className="badge badge-red">{({ password: 'неверный пароль', mfa: 'неверный код 2FA', locked: 'заблокирован' } as Record<string, string>)[l.reason ?? ''] ?? 'отказ'}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
