import { useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CalendarCheck, ChevronLeft, ChevronRight, Printer } from 'lucide-react'
import { useLoad } from '../lib/useLoad'
import { addDays, dayMonth, isoDay, mondayOf, time } from '../lib/format'
import type { Lesson, Schedule as S } from '../lib/types'
import { LessonSlot } from '../components/LessonSlot'
import { Empty, LoadError, PageSkeleton, usePageTitle } from '../components/ui'

export default function Schedule() {
  usePageTitle('Расписание')
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'session' ? 'session' : 'week'
  const today = isoDay(new Date())
  // в воскресенье неделя уже прошла — по умолчанию показываем следующую
  const base = new Date(today + 'T12:00:00+03:00').getUTCDay() === 0 ? addDays(today, 1) : today
  const focus = params.get('date')
  const from = mondayOf(focus || params.get('from') || base)
  const go = (iso: string) => setParams({ from: iso }, { replace: true })

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Расписание</h1>
        <div className="page-actions no-print">
          <div className="seg" role="group" aria-label="Вид">
            <button aria-pressed={view === 'week'} onClick={() => setParams({ from }, { replace: true })}>Неделя</button>
            <button aria-pressed={view === 'session'} onClick={() => setParams({ view: 'session' }, { replace: true })}>Сессия</button>
          </div>
          <Link to="/calendar" className="btn btn-secondary btn-sm"><CalendarCheck aria-hidden="true" />В календарь телефона</Link>
          <button className="btn btn-ghost btn-sm" onClick={() => window.print()}><Printer aria-hidden="true" />Печать</button>
        </div>
        <p className="sub">Нашли неточность? <Link to="/requests/new?type=question">Напишите в деканат</Link> — ответ придёт в заявку.</p>
      </div>
      {view === 'week' ? <Week from={from} today={today} base={base} focus={focus} go={go} /> : <Session />}
    </div>
  )
}

function Week({ from, today, base, focus, go }: { from: string; today: string; base: string; focus: string | null; go: (iso: string) => void }) {
  const { data, error, loading, reload } = useLoad<S>(`/api/schedule?from=${from}&days=7`)
  const nowHM = time(new Date())
  useEffect(() => {
    if (!data || !focus) return
    document.getElementById(`d-${focus}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [data, focus])
  const days = useMemo(() => (data?.days ?? []).filter((d) => d.lessons.length > 0 || (d.weekday !== 'воскресенье')), [data])
  const first = data?.days.find((d) => d.week)

  return (
    <>
      <div className="spread no-print">
        <div className="week-nav">
          <button className="icon-btn" onClick={() => go(addDays(from, -7))} aria-label="Предыдущая неделя"><ChevronLeft aria-hidden="true" /></button>
          <span className="label">{dayMonth(from)} — {dayMonth(addDays(from, 6))}</span>
          <button className="icon-btn" onClick={() => go(addDays(from, 7))} aria-label="Следующая неделя"><ChevronRight aria-hidden="true" /></button>
          {mondayOf(base) !== from && <button className="btn btn-ghost btn-sm" onClick={() => go(mondayOf(base))}>{base === today ? 'Текущая неделя' : 'Ближайшая неделя'}</button>}
        </div>
        {first?.week && <span className="parity">{first.week}-я учебная неделя <b>{first.parity}</b></span>}
      </div>
      {loading && !data ? <PageSkeleton /> : error && !data ? <LoadError error={error} retry={reload} /> : data && (
        <div>
          {days.every((d) => d.lessons.length === 0) && <Empty title="На этой неделе занятий нет">Каникулы или сессия — переключитесь на «Сессия».</Empty>}
          {days.map((d) => (
            <section key={d.date} className="day" id={`d-${d.date}`} aria-labelledby={`h-${d.date}`}>
              <div className={`day-head ${d.date === today ? 'today' : ''}`}>
                <h2 id={`h-${d.date}`}>{d.human}</h2>
                <span className="wd">{d.weekday}</span>
              </div>
              {d.lessons.length === 0 ? <div className="day-empty">Нет занятий</div> : (
                <div className="slots">
                  {d.lessons.map((l: Lesson) => (
                    <LessonSlot key={l.id} l={l} showGroups={l.kind === 'lecture'}
                      now={d.date === today && l.start <= nowHM && nowHM < l.end && l.status !== 'cancelled'}
                      past={d.date < today || (d.date === today && l.end <= nowHM)} />
                  ))}
                </div>
              )}
            </section>
          ))}
          <p className="xs muted">Время московское. Пары по схеме вашего факультета: {data.pairs.map((p) => `${p.n} — ${p.start}`).join(', ')}.</p>
        </div>
      )}
    </>
  )
}

function Session() {
  const { data, error, loading, reload } = useLoad<{ semester: string; from: string; to: string; items: Lesson[] }>('/api/session')
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null
  const groups = data.items.reduce<Record<string, Lesson[]>>((acc, l) => { (acc[l.date] ||= []).push(l); return acc }, {})
  return (
    <div>
      <p className="muted small" style={{ marginBottom: 12 }}>{data.semester}: зачётная неделя в конце семестра, экзаменационная сессия {dayMonth(data.from)} — {dayMonth(data.to)}. Каждый экзамен можно добавить в календарь отдельно — напоминание придёт за день и за 2 часа.</p>
      {data.items.length === 0 ? <Empty title="Расписание сессии ещё не опубликовано" /> : Object.entries(groups).map(([date, ls]) => (
        <section key={date} className="day">
          <div className="day-head"><h2>{dayMonth(date)}</h2><span className="wd">{ls[0] && new Intl.DateTimeFormat('ru-RU', { weekday: 'long', timeZone: 'Europe/Moscow' }).format(new Date(date + 'T12:00:00+03:00'))}</span></div>
          <div className="slots">{ls.map((l) => <LessonSlot key={l.id} l={l} />)}</div>
        </section>
      ))}
    </div>
  )
}
