import type { ReactNode } from 'react'
import { CalendarPlus, MapPin, MonitorPlay, TriangleAlert, Ban, UserRound, Users } from 'lucide-react'
import { dayMonth } from '../lib/format'
import type { Lesson } from '../lib/types'

export function LessonSlot({ l, now, past, showGroups, addToCalendar = true, extra }: { l: Lesson; now?: boolean; past?: boolean; showGroups?: boolean; addToCalendar?: boolean; extra?: ReactNode }) {
  const cls = ['slot', now ? 'now' : '', past ? 'past' : '', l.status === 'cancelled' ? 'cancelled' : '', l.status === 'moved' ? 'moved' : ''].join(' ')
  const room = l.room && (/^[0-9]|^[А-ЯA-Z]-?[0-9]/.test(l.room) ? `ауд. ${l.room}` : l.room)
  const where = l.online_url ? 'Онлайн' : [room, l.building].filter(Boolean).join(', ')
  return (
    <div className={cls}>
      <div className="slot-time">
        <div className="t">{l.start}</div>
        <div className="e">{l.end}</div>
        {l.pair && <div className="p">{l.pair} пара</div>}
      </div>
      <div className="slot-body">
        <span className={`kind kind-${l.kind}`}>{l.kind_text}{now ? ' · идёт сейчас' : ''}</span>
        <span className="d">{l.discipline}</span>
        {l.change && (
          <span className={`change ${l.status === 'cancelled' ? 'cancel' : ''}`}>
            {l.status === 'cancelled' ? <Ban aria-hidden="true" /> : <TriangleAlert aria-hidden="true" />}
            <span>
              <b>{l.status === 'cancelled' ? 'Отменено' : 'Изменение'}</b>
              {l.change.prev && l.status === 'moved' && (l.change.prev.date !== l.date || l.change.prev.start !== l.start)
                ? <> · было {dayMonth(l.change.prev.date)}, {l.change.prev.start}</> : null}
              {l.change.prev?.room && l.change.prev.room !== l.room && l.status === 'moved' ? <> · была ауд. {l.change.prev.room}</> : null}
              {l.change.reason ? <> · {l.change.reason}</> : null}
            </span>
          </span>
        )}
        <span className="info">
          {where && <span>{l.online_url ? <MonitorPlay aria-hidden="true" /> : <MapPin aria-hidden="true" />}{where}</span>}
          {l.teacher && <span><UserRound aria-hidden="true" />{l.teacher}</span>}
          {showGroups && l.groups.length > 0 && <span><Users aria-hidden="true" />{l.groups.join(', ')}</span>}
        </span>
        {extra && <span className="actions no-print">{extra}</span>}
        {!extra && (l.online_url || addToCalendar) && l.status !== 'cancelled' && (
          <span className="actions no-print">
            {l.online_url && <a className="btn btn-sm btn-secondary" href={l.online_url} target="_blank" rel="noopener noreferrer"><MonitorPlay aria-hidden="true" />Подключиться</a>}
            {addToCalendar && (l.kind === 'exam' || l.kind === 'zachet' || l.kind === 'consult' || l.status === 'moved') && (
              <a className="btn btn-sm btn-ghost" href={`/api/lessons/${l.id}/event.ics`} download><CalendarPlus aria-hidden="true" />В календарь</a>
            )}
          </span>
        )}
      </div>
    </div>
  )
}
