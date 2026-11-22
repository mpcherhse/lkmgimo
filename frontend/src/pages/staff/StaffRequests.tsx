import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronRight, ClipboardList } from 'lucide-react'
import { useLoad } from '../../lib/useLoad'
import { dayMonth, relative } from '../../lib/format'
import { Empty, LoadError, PageSkeleton, Panel, StatusBadge, usePageTitle } from '../../components/ui'
import type { StaffReq } from './types'

const FILTERS = [
  { key: 'open', label: 'Открытые' }, { key: 'submitted', label: 'Новые' }, { key: 'in_progress', label: 'В работе' }, { key: 'ready', label: 'Готовы' }, { key: 'all', label: 'Все' },
]

export default function StaffRequests() {
  usePageTitle('Заявки')
  const [params, setParams] = useSearchParams()
  const status = params.get('status') || 'open'
  const [q, setQ] = useState(params.get('q') || '')
  const [query, setQuery] = useState(q)
  useEffect(() => { const t = setTimeout(() => setQuery(q), 300); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useLoad<{ items: StaffReq[] }>(`/api/staff/requests?status=${status}${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ''}`)

  return (
    <div className="stack">
      <div className="page-head"><h1>Заявки</h1><p className="sub">Заявки студентов ваших факультетов. Сначала новые, затем по дате подачи.</p></div>
      <div className="filters">
        <div className="seg" role="group" aria-label="Статус">
          {FILTERS.map((f) => <button key={f.key} aria-pressed={status === f.key} onClick={() => setParams({ status: f.key }, { replace: true })}>{f.label}</button>)}
        </div>
        <label className="sr-only" htmlFor="sq">Поиск</label>
        <input id="sq" className="input" type="search" placeholder="Фамилия, номер или вид" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <PageSkeleton /> : error && !data ? <LoadError error={error} retry={reload} /> : (
        <Panel flush>
          {data!.items.length === 0 ? <Empty title="Заявок нет" icon={<ClipboardList aria-hidden="true" />} /> : (
            <ul className="list">
              {data!.items.map((r) => (
                <li key={r.id}>
                  <Link className="list-item" to={`/staff/requests/${r.id}`}>
                    <span className="grow stack-sm" style={{ gap: 3 }}>
                      <span className="spread"><span className="title">{r.title}</span><span className="row">{r.overdue && <span className="badge badge-red">просрочена</span>}<StatusBadge status={r.status} text={r.status_text} /></span></span>
                      <span className="small">{r.student.name} · {r.student.group}, {r.student.course} курс</span>
                      <span className="meta">№ {r.number} · подана {relative(r.created_at)}{r.due_on && ` · срок ${dayMonth(r.due_on)}`} · {r.delivery === 'electronic' ? 'электронно' : 'на бумаге'}</span>
                    </span>
                    <ChevronRight className="chev" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </div>
  )
}
