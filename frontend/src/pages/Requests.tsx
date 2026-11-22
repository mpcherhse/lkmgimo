import { Link, useSearchParams } from 'react-router-dom'
import { ChevronRight, FilePlus2, FileText } from 'lucide-react'
import { useLoad } from '../lib/useLoad'
import { dayMonth, relative } from '../lib/format'
import type { RequestItem } from '../lib/types'
import { Empty, LoadError, PageSkeleton, Panel, StatusBadge, Steps, usePageTitle } from '../components/ui'

const OPEN = ['submitted', 'accepted', 'in_progress', 'ready']

export default function Requests() {
  usePageTitle('Заявки и справки')
  const { data, error, loading, reload } = useLoad<{ items: RequestItem[] }>('/api/requests')
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'closed' ? 'closed' : 'open'
  const setTab = (t: 'open' | 'closed') => setParams(t === 'open' ? {} : { tab: t }, { replace: true })
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  const items = data?.items ?? []
  const open = items.filter((r) => OPEN.includes(r.status))
  const closed = items.filter((r) => !OPEN.includes(r.status))
  const list = tab === 'open' ? open : closed

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Заявки и справки</h1>
        <div className="page-actions"><Link to="/requests/new" className="btn"><FilePlus2 aria-hidden="true" />Новая заявка</Link></div>
        <p className="sub">Справки, заявления и вопросы в деканат — со статусом и перепиской. Электронная справка скачивается здесь же, бумажную забирают в деканате.</p>
      </div>
      <div className="seg" role="group" aria-label="Фильтр">
        <button aria-pressed={tab === 'open'} onClick={() => setTab('open')}>В работе · {open.length}</button>
        <button aria-pressed={tab === 'closed'} onClick={() => setTab('closed')}>Завершённые · {closed.length}</button>
      </div>
      <Panel flush>
        {list.length === 0 ? (
          <Empty title={tab === 'open' ? 'Заявок в работе нет' : 'Завершённых заявок нет'} icon={<FileText aria-hidden="true" />}>
            {tab === 'open' && <p><Link to="/requests/new">Заказать справку или написать в деканат</Link></p>}
          </Empty>
        ) : (
          <ul className="list">
            {list.map((r) => (
              <li key={r.id}>
                <Link className="list-item" to={`/requests/${r.id}`}>
                  <span className="grow stack-sm" style={{ gap: 4 }}>
                    <span className="spread"><span className="title">{r.title}</span><StatusBadge status={r.status} text={r.status_text} /></span>
                    {OPEN.includes(r.status) && <Steps status={r.status} />}
                    <span className="meta">
                      № {r.number} · подана {dayMonth(r.created_at)} · обновлена {relative(r.updated_at)}
                      {r.due_on && OPEN.includes(r.status) && r.status !== 'ready' && <> · срок до {dayMonth(r.due_on)}</>}
                    </span>
                    {r.status_comment && <span className="small">{r.status_comment}</span>}
                  </span>
                  <ChevronRight className="chev" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}
