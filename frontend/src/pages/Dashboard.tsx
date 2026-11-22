import { Link } from 'react-router-dom'
import { ArrowRight, Bell, CalendarClock, CalendarCheck, ChevronRight, FilePlus2, TriangleAlert } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useLoad } from '../lib/useLoad'
import { dayMonth, daysUntil, pct, plural, relative, time, until, weekday } from '../lib/format'
import type { Dashboard as D } from '../lib/types'
import { LessonSlot } from '../components/LessonSlot'
import { Empty, Letter, LoadError, Note, PageSkeleton, Panel, StatusBadge, Steps, usePageTitle } from '../components/ui'

export default function Dashboard() {
  usePageTitle('Главная')
  const { me } = useAuth()
  const { data, error, loading, reload } = useLoad<D>('/api/dashboard')
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null
  const nowHM = time(new Date())
  const todayLessons = data.today.lessons
  const isToday = data.next?.date === data.today.date

  return (
    <div className="stack">
      <div className="today-strip">
        <h1>Здравствуйте, {me?.name?.first}</h1>
        <span className="muted">
          {data.today.weekday}, {data.today.human}
          {data.today.week && <> · {data.today.week}-я неделя, <span className="strong">{data.today.parity}</span></>}
        </span>
      </div>

      {data.rating.attention.length > 0 && (
        <Note tone="amber">
          <b>Требует внимания:</b>{' '}
          {data.rating.attention.map((a, i) => <span key={a.discipline}>{i > 0 && '; '}{a.discipline} — текущий контроль {pct(a.b1)}%</span>)}.{' '}
          <Link to="/grades">Подробнее в успеваемости</Link>
        </Note>
      )}

      <div className="grid grid-main">
        <div className="stack">
          <Panel title={isToday ? 'Следующая пара' : 'Ближайшее занятие'} id="next" action={<Link className="more" to="/schedule">Расписание<ChevronRight aria-hidden="true" /></Link>}>
            {data.next ? (
              <div className="next-pair">
                <div className="when">{data.next.start}<small>{isToday ? 'сегодня' : `${weekday(data.next.date)}, ${dayMonth(data.next.date)}`}</small></div>
                <div className="stack-sm" style={{ gap: 2 }}>
                  <span className={`kind kind-${data.next.kind}`}>{data.next.kind_text}</span>
                  <span className="strong">{data.next.discipline}</span>
                  <span className="small muted">
                    {data.next.online_url ? 'Онлайн' : `ауд. ${data.next.room}, ${data.next.building}`}{data.next.teacher && ` · ${data.next.teacher}`}
                  </span>
                  {data.next.change && <span className="change small"><TriangleAlert aria-hidden="true" />{data.next.change.title}</span>}
                </div>
              </div>
            ) : <Empty title="Занятий на неделе нет" />}
          </Panel>

          {todayLessons.length > 0 && (
            <section aria-labelledby="today-h">
              <div className="spread" style={{ marginBottom: 8 }}><h2 id="today-h" style={{ fontSize: 'var(--fs-md)' }}>Сегодня</h2></div>
              <div className="slots">
                {todayLessons.map((l) => (
                  <LessonSlot key={l.id} l={l} addToCalendar={false} now={l.start <= nowHM && nowHM < l.end && l.status !== 'cancelled'} past={l.end <= nowHM} />
                ))}
              </div>
            </section>
          )}

          {data.changes.length > 0 && (
            <Panel title="Изменения в расписании" id="changes" flush>
              <ul className="list">
                {data.changes.map((l) => (
                  <li key={l.id}>
                    <Link className="list-item" to={`/schedule?date=${l.date}`}>
                      <CalendarClock aria-hidden="true" style={{ width: 20, height: 20, color: l.status === 'cancelled' ? 'var(--red-600)' : 'var(--amber-700)', flex: 'none', marginTop: 2 }} />
                      <span className="grow">
                        <span className="title" style={{ display: 'block' }}>{l.change?.title}</span>
                        <span className="meta">{l.change?.text}</span>
                      </span>
                      <ChevronRight className="chev" aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel title="Дедлайны" id="dl" flush>
            {data.deadlines.length === 0 ? <Empty title="Ближайшие 3 недели — без дедлайнов" /> : (
              <ul className="list">
                {data.deadlines.map((d) => {
                  const left = daysUntil(d.due_at)
                  return (
                    <li key={d.id} className="list-item">
                      <span className="grow">
                        <span className="title" style={{ display: 'block' }}>{d.title}</span>
                        {d.details && <span className="meta">{d.details}</span>}
                      </span>
                      <span style={{ textAlign: 'right' }}>
                        <span className={`due small ${left <= 2 ? 'soon' : ''}`} style={{ display: 'block' }}>{until(d.due_at)}</span>
                        <span className="xs muted nowrap">{dayMonth(d.due_at)}, {time(d.due_at)}</span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </Panel>
        </div>

        <div className="stack">
          <Panel title="Рейтинг семестра" id="rating" action={<Link className="more" to="/grades">Подробнее<ChevronRight aria-hidden="true" /></Link>}>
            <div className="row"><span className="score-big">{pct(data.rating.estimate)}</span><span className="muted">%</span><Letter g={data.rating.estimate_grade} /></div>
            <p className="xs muted" style={{ marginTop: 4 }}>предварительно, по текущему контролю · {data.rating.semester.toLowerCase()}</p>
            {data.rating.previous && (
              <p className="small" style={{ marginTop: 10 }}>{data.rating.previous.title}: <span className="score">{pct(data.rating.previous.rating)}%</span> <Letter g={data.rating.previous.grade} /></p>
            )}
            <p className="small muted" style={{ marginTop: 12 }}>
              До сессии {data.session.days_left > 0 ? `${data.session.days_left} ${plural(data.session.days_left, 'день', 'дня', 'дней')}` : 'идёт сессия'} · {dayMonth(data.session.from)} — {dayMonth(data.session.to)}
            </p>
          </Panel>

          <Panel title="Заявки" id="req" action={<Link className="more" to="/requests">Все<ChevronRight aria-hidden="true" /></Link>} flush>
            {data.requests.length === 0 ? (
              <Empty title="Активных заявок нет"><p><Link to="/requests/new">Заказать справку</Link></p></Empty>
            ) : (
              <ul className="list">
                {data.requests.map((r) => (
                  <li key={r.id}>
                    <Link className="list-item" to={`/requests/${r.id}`}>
                      <span className="grow">
                        <span className="spread"><span className="title">{r.title}</span><StatusBadge status={r.status} text={r.status_text} /></span>
                        <Steps status={r.status} />
                        <span className="meta">№ {r.number} · {relative(r.updated_at)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <div className="panel-body" style={{ paddingTop: 4 }}>
              <Link to="/requests/new" className="btn btn-secondary btn-sm"><FilePlus2 aria-hidden="true" />Новая заявка</Link>
            </div>
          </Panel>

          <Panel title="Непрочитанное" id="unread" action={<Link className="more" to="/notifications">Все<ChevronRight aria-hidden="true" /></Link>} flush>
            {data.notifications.length === 0 ? <Empty title="Всё прочитано" icon={<Bell aria-hidden="true" />} /> : (
              <ul className="list">
                {data.notifications.map((n) => (
                  <li key={n.id}>
                    <Link className="list-item" to="/notifications?unread=1">
                      <span className="grow">
                        <span className="title" style={{ display: 'block' }}>{n.important && <span className="badge badge-red" style={{ marginRight: 6 }}>Важно</span>}{n.title}</span>
                        <span className="meta">{relative(n.created_at)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Link to="/calendar" className="cat-item">
            <CalendarCheck aria-hidden="true" />
            <span><span className="t" style={{ display: 'block' }}>Расписание в календаре телефона</span><span className="d">iPhone, Android, HarmonyOS — переносы обновятся сами</span></span>
            <ArrowRight aria-hidden="true" style={{ marginLeft: 'auto' }} />
          </Link>
        </div>
      </div>
    </div>
  )
}
