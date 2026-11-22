import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Bell, CalendarClock, CheckCheck, FileText, Megaphone, ShieldAlert, Clock, GraduationCap } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLoad } from '../lib/useLoad'
import { relative } from '../lib/format'
import type { Notification } from '../lib/types'
import { Empty, LoadError, PageSkeleton, Panel, usePageTitle } from '../components/ui'

const KINDS: { key: string; label: string; icon: typeof Bell; tone?: string }[] = [
  { key: 'announcement', label: 'Объявления', icon: Megaphone },
  { key: 'schedule', label: 'Расписание', icon: CalendarClock, tone: 'amber' },
  { key: 'request', label: 'Заявки', icon: FileText },
  { key: 'deadline', label: 'Дедлайны', icon: Clock, tone: 'amber' },
  { key: 'grade', label: 'Оценки', icon: GraduationCap },
  { key: 'security', label: 'Безопасность', icon: ShieldAlert, tone: 'red' },
]

export default function Notifications() {
  usePageTitle('Уведомления')
  const { me, setUnread } = useAuth()
  const [params, setParams] = useSearchParams()
  const unread = params.get('unread') === '1'
  const kind = params.get('kind') || ''
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => { const t = setTimeout(() => setQuery(q), 300); return () => clearTimeout(t) }, [q])
  const url = `/api/notifications?limit=100${unread ? '&unread=true' : ''}${kind ? `&kind=${kind}` : ''}${query.trim().length > 1 ? `&q=${encodeURIComponent(query.trim())}` : ''}`
  const { data, error, loading, reload, setData } = useLoad<{ items: Notification[]; counts: Record<string, { unread: number; total: number }> }>(url)

  const totalUnread = data ? Object.values(data.counts).reduce((a, c) => a + c.unread, 0) : me?.unread ?? 0
  useEffect(() => { if (data) setUnread(totalUnread) }, [data, totalUnread, setUnread])

  function set(k: string, v: string | null) {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v); else p.delete(k)
    setParams(p, { replace: true })
  }
  async function read(n: Notification) {
    if (n.read || !data) return
    setData({ ...data, items: data.items.map((x) => (x.id === n.id ? { ...x, read: true } : x)), counts: { ...data.counts, [n.kind]: { ...data.counts[n.kind], unread: Math.max(0, (data.counts[n.kind]?.unread ?? 1) - 1) } } })
    try { await api.post(`/api/notifications/${n.id}/read`) } catch { reload(true) }
  }
  async function readAll() {
    await api.post('/api/notifications/read-all')
    reload(true)
  }
  const visible = KINDS.filter((k) => me?.role === 'student' || ['announcement', 'request', 'security'].includes(k.key))

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Уведомления</h1>
        <div className="page-actions">{totalUnread > 0 && <button className="btn btn-secondary btn-sm" onClick={readAll}><CheckCheck aria-hidden="true" />Прочитать все</button>}</div>
      </div>
      <div className="filters">
        <div className="seg" role="group" aria-label="Показывать">
          <button aria-pressed={!unread} onClick={() => set('unread', null)}>Все</button>
          <button aria-pressed={unread} onClick={() => set('unread', '1')}>Непрочитанные{totalUnread ? ` · ${totalUnread}` : ''}</button>
        </div>
        <label className="sr-only" htmlFor="nq">Поиск по уведомлениям</label>
        <input id="nq" className="input" type="search" placeholder="Поиск…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="seg" role="group" aria-label="Тип">
        <button aria-pressed={!kind} onClick={() => set('kind', null)}>Все типы</button>
        {visible.map((k) => (
          <button key={k.key} aria-pressed={kind === k.key} onClick={() => set('kind', k.key)}>
            {k.label}{data?.counts[k.key]?.unread ? ` · ${data.counts[k.key].unread}` : ''}
          </button>
        ))}
      </div>
      {loading && !data ? <PageSkeleton /> : error && !data ? <LoadError error={error} retry={reload} /> : (
        <Panel flush>
          {data!.items.length === 0 ? <Empty title={unread ? 'Непрочитанных нет' : 'Уведомлений нет'} icon={<Bell aria-hidden="true" />} /> : (
            <ul className="list">
              {data!.items.map((n) => {
                const k = KINDS.find((x) => x.key === n.kind) ?? KINDS[0]
                const Icon = k.icon
                return (
                  <li key={n.id} className={`notif ${n.read ? '' : 'unread'}`}>
                    <span className={`ic ${n.important ? 'red' : k.tone ?? ''}`} aria-hidden="true"><Icon /></span>
                    <div className="grow">
                      <div className="title">{n.important && <span className="badge badge-red" style={{ marginRight: 6 }}>Важно</span>}{n.title}</div>
                      {n.body && <div className="body">{n.body}</div>}
                      <div className="when">{k.label} · {relative(n.created_at)}{!n.read && <span className="sr-only"> · не прочитано</span>}</div>
                      <div className="row" style={{ marginTop: 4, gap: 4 }}>
                        {n.link && <Link className="btn btn-ghost btn-sm" to={n.link} onClick={() => read(n)}>Открыть</Link>}
                        {!n.read && <button className="btn btn-ghost btn-sm" onClick={() => read(n)}>Отметить прочитанным</button>}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      )}
    </div>
  )
}
