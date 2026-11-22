import { Link } from 'react-router-dom'
import { CalendarDays, ChevronRight, ClipboardList, Megaphone } from 'lucide-react'
import { useLoad } from '../../lib/useLoad'
import { LoadError, Note, PageSkeleton, Panel, usePageTitle } from '../../components/ui'

type O = { name: string; position: string; faculties: { code: string; name: string }[]; counts: Record<string, number>; open: number; overdue: number; students: number }

export default function StaffHome() {
  usePageTitle('Обзор')
  const { data, error, loading, reload } = useLoad<O>('/api/staff/overview')
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null
  const c = data.counts
  const rows = [
    { key: 'submitted', label: 'Новые — ждут приёма' }, { key: 'accepted', label: 'Приняты' }, { key: 'in_progress', label: 'В работе' }, { key: 'ready', label: 'Готовы к выдаче' },
  ]
  return (
    <div className="stack">
      <div className="page-head">
        <h1>{data.name}</h1>
        <p className="sub">{data.position} · {data.faculties.map((f) => f.name).join(', ')} · студентов: {data.students}</p>
      </div>
      {data.overdue > 0 && <Note tone="red"><b>Просрочено заявок: {data.overdue}.</b> <Link to="/staff/requests">Открыть очередь</Link></Note>}
      <div className="grid grid-main">
        <Panel title="Очередь заявок" id="q" action={<Link className="more" to="/staff/requests">Все<ChevronRight aria-hidden="true" /></Link>} flush>
          <div className="table-wrap">
            <table className="table">
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key}><td><Link to={`/staff/requests?status=${r.key}`}>{r.label}</Link></td><td className="r strong">{c[r.key] ?? 0}</td></tr>
                ))}
                <tr><td className="muted">Всего открытых</td><td className="r strong">{data.open}</td></tr>
              </tbody>
            </table>
          </div>
        </Panel>
        <div className="stack">
          <Link to="/staff/requests?status=submitted" className="cat-item"><ClipboardList aria-hidden="true" /><span><span className="t" style={{ display: 'block' }}>Разобрать новые заявки</span><span className="d">Принять, ответить, выпустить справку</span></span></Link>
          <Link to="/staff/schedule" className="cat-item"><CalendarDays aria-hidden="true" /><span><span className="t" style={{ display: 'block' }}>Перенести или отменить занятие</span><span className="d">Студенты получат уведомление, календари обновятся</span></span></Link>
          <Link to="/staff/announcements" className="cat-item"><Megaphone aria-hidden="true" /><span><span className="t" style={{ display: 'block' }}>Опубликовать объявление</span><span className="d">Факультету, курсу или группе</span></span></Link>
        </div>
      </div>
    </div>
  )
}
