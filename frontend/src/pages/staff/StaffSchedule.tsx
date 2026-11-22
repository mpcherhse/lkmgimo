import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Pencil } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { useLoad } from '../../lib/useLoad'
import { addDays, dayMonth, isoDay, mondayOf, weekday } from '../../lib/format'
import type { Lesson } from '../../lib/types'
import { LessonSlot } from '../../components/LessonSlot'
import { Empty, LoadError, Note, PageSkeleton, useToast, usePageTitle } from '../../components/ui'

type Groups = { faculties: { id: number; code: string; name: string }[]; groups: { id: number; code: string; kind: string; course: number; language: string | null; faculty_id: number }[] }
type Pairs = { n: number; start: string; end: string }[]

export default function StaffSchedule() {
  usePageTitle('Расписание групп')
  const [params, setParams] = useSearchParams()
  const groups = useLoad<Groups>('/api/staff/groups')
  const group = Number(params.get('group')) || groups.data?.groups.find((g) => g.kind === 'academic')?.id
  const today = isoDay(new Date())
  const from = params.get('from') || mondayOf(new Date(today + 'T12:00:00+03:00').getUTCDay() === 0 ? addDays(today, 1) : today)
  const lessons = useLoad<{ items: Lesson[]; pairs: Pairs }>(group ? `/api/staff/lessons?group=${group}&from=${from}&days=7` : null)
  const [editing, setEditing] = useState<string | null>(null)
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); p.set(k, v); setParams(p, { replace: true }); setEditing(null) }

  if (groups.loading && !groups.data) return <PageSkeleton />
  if (groups.error && !groups.data) return <LoadError error={groups.error} retry={groups.reload} />
  const g = groups.data!
  const byDay = (lessons.data?.items ?? []).reduce<Record<string, Lesson[]>>((a, l) => { (a[l.date] ||= []).push(l); return a }, {})

  return (
    <div className="stack">
      <div className="page-head"><h1>Расписание групп</h1><p className="sub">Перенос, смена аудитории, перевод в онлайн или отмена. Студенты группы сразу получают уведомление, а события в их календарях обновляются.</p></div>
      <div className="filters">
        <div className="field" style={{ minWidth: 220 }}>
          <label htmlFor="grp" className="sr-only">Группа</label>
          <select id="grp" className="select" value={group ?? ''} onChange={(e) => set('group', e.target.value)}>
            {g.faculties.map((f) => (
              <optgroup key={f.id} label={f.name}>
                {g.groups.filter((x) => x.faculty_id === f.id).map((x) => <option key={x.id} value={x.id}>{x.code}{x.language ? ` (${x.language})` : ''} · {x.course} курс</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="week-nav">
          <button className="icon-btn" onClick={() => set('from', addDays(from, -7))} aria-label="Предыдущая неделя"><ChevronLeft aria-hidden="true" /></button>
          <span className="label">{dayMonth(from)} — {dayMonth(addDays(from, 6))}</span>
          <button className="icon-btn" onClick={() => set('from', addDays(from, 7))} aria-label="Следующая неделя"><ChevronRight aria-hidden="true" /></button>
        </div>
      </div>
      {lessons.loading && !lessons.data ? <PageSkeleton /> : lessons.error ? <LoadError error={lessons.error} retry={lessons.reload} /> : (
        Object.keys(byDay).length === 0 ? <Empty title="Занятий на этой неделе нет" /> : Object.entries(byDay).map(([date, ls]) => (
          <section key={date} className="day">
            <div className="day-head"><h2>{dayMonth(date)}</h2><span className="wd">{weekday(date)}</span></div>
            <div className="slots">
              {ls.map((l) => (
                <div key={l.id}>
                  <LessonSlot l={l} showGroups addToCalendar={false}
                    extra={l.status !== 'cancelled' && editing !== l.id ? <button className="btn btn-secondary btn-sm" onClick={() => setEditing(l.id)} aria-label={`Изменить: ${l.discipline}, ${dayMonth(l.date)} ${l.start}`}><Pencil aria-hidden="true" />Изменить</button> : undefined} />
                  {editing === l.id && <ChangeForm l={l} pairs={lessons.data!.pairs} onDone={() => { setEditing(null); lessons.reload(true) }} onCancel={() => setEditing(null)} />}
                </div>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  )
}

function ChangeForm({ l, pairs, onDone, onCancel }: { l: Lesson; pairs: Pairs; onDone: () => void; onCancel: () => void }) {
  const toast = useToast()
  const [mode, setMode] = useState<'move' | 'room' | 'online' | 'cancel'>('move')
  const [day, setDay] = useState(l.date)
  const [pair, setPair] = useState(String(l.pair ?? 1))
  const [room, setRoom] = useState(l.room)
  const [reason, setReason] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setErr(null) }, [mode])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const body: Record<string, unknown> = { reason: reason.trim() }
    if (mode === 'cancel') body.cancel = true
    if (mode === 'move') { body.day = day; body.pair = Number(pair); if (room !== l.room) body.room = room }
    if (mode === 'room') body.room = room
    if (mode === 'online') body.online = true
    setBusy(true); setErr(null)
    try { const r = await api.post<{ notified: number }>(`/api/staff/lessons/${l.id}/change`, body); toast(`Сохранено. Уведомлено студентов: ${r.notified}`); onDone() }
    catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} className="stack-sm" style={{ padding: '12px 14px 14px', borderTop: '1px dashed var(--line)', background: '#fbfcfe' }}>
      <div className="seg" role="group" aria-label="Что изменить">
        {([['move', 'Перенести'], ['room', 'Аудитория'], ['online', 'Онлайн'], ['cancel', 'Отменить']] as const).map(([k, t]) => (
          <button type="button" key={k} aria-pressed={mode === k} onClick={() => setMode(k)}>{t}</button>
        ))}
      </div>
      {err && <Note tone="red">{err}</Note>}
      {mode === 'move' && (
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <div className="field"><label htmlFor={`d-${l.id}`}>Дата</label><input id={`d-${l.id}`} type="date" className="input" value={day} onChange={(e) => setDay(e.target.value)} /></div>
          <div className="field"><label htmlFor={`p-${l.id}`}>Пара</label>
            <select id={`p-${l.id}`} className="select" value={pair} onChange={(e) => setPair(e.target.value)}>{pairs.map((p) => <option key={p.n} value={p.n}>{p.n} — {p.start}–{p.end}</option>)}</select>
          </div>
          <div className="field" style={{ maxWidth: 140 }}><label htmlFor={`r-${l.id}`}>Аудитория</label><input id={`r-${l.id}`} className="input" value={room} onChange={(e) => setRoom(e.target.value)} /></div>
        </div>
      )}
      {mode === 'room' && <div className="field" style={{ maxWidth: 200 }}><label htmlFor={`r2-${l.id}`}>Новая аудитория</label><input id={`r2-${l.id}`} className="input" value={room} onChange={(e) => setRoom(e.target.value)} /></div>}
      {mode === 'online' && <p className="small muted">Занятие пройдёт онлайн в то же время, ссылка появится у студентов в расписании.</p>}
      <div className="field">
        <label htmlFor={`why-${l.id}`}>Причина (увидят студенты)</label>
        <input id={`why-${l.id}`} className="input" maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={mode === 'cancel' ? 'Например: болезнь преподавателя' : 'Например: конференция на факультете'} required minLength={3} />
      </div>
      <div className="row">
        <button className={`btn btn-sm ${mode === 'cancel' ? 'btn-danger' : ''}`} disabled={busy || reason.trim().length < 3}>{mode === 'cancel' ? 'Отменить занятие' : 'Сохранить и уведомить'}</button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>Закрыть</button>
      </div>
    </form>
  )
}
