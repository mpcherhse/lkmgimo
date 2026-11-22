import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, ExternalLink, Send } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { useLoad } from '../../lib/useLoad'
import { dateTime, dayMonth } from '../../lib/format'
import { Empty, LoadError, Note, PageSkeleton, Panel, StatusBadge, useToast, usePageTitle } from '../../components/ui'
import { NEXT_LABEL, type StaffReq } from './types'

export default function StaffRequest() {
  const { id } = useParams()
  const { data, error, loading, reload, setData } = useLoad<StaffReq>(`/api/staff/requests/${id}`)
  usePageTitle(data ? `Заявка № ${data.number}` : "Заявка")
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (loading && !data) return <PageSkeleton />
  if (error && !data) return error.status === 404 ? <Empty title="Заявка не найдена">Она относится к другому факультету или не существует.</Empty> : <LoadError error={error} retry={reload} />
  if (!data) return null
  const r = data

  async function move(status: string) {
    if (status === 'rejected' && !comment.trim()) { setErr('Укажите причину отказа в комментарии — студент её увидит'); return }
    setBusy(true); setErr(null)
    try { setData(await api.post<StaffReq>(`/api/staff/requests/${r.id}/status`, { status, comment: comment.trim() })); setComment(''); toast('Статус изменён, студент получил уведомление') }
    catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }
  async function send(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try { setData(await api.post<StaffReq>(`/api/staff/requests/${r.id}/messages`, { text: msg.trim() })); setMsg(''); toast('Ответ отправлен') }
    catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }

  return (
    <div className="stack">
      <Link to="/staff/requests" className="back"><ChevronLeft aria-hidden="true" />Заявки</Link>
      <div className="page-head">
        <h1>{r.title}</h1>
        <p className="sub">№ {r.number} · {r.student.name}, {r.student.group} ({r.student.faculty}), {r.student.course} курс · подана {dateTime(r.created_at)}</p>
      </div>
      {err && <Note tone="red">{err}</Note>}
      <div className="grid grid-main">
        <div className="stack">
          <Panel title="Статус" id="st">
            <div className="stack-sm">
              <div className="row"><StatusBadge status={r.status} text={r.status_text} />{r.overdue && <span className="badge badge-red">просрочена</span>}{r.due_on && <span className="small muted">срок {dayMonth(r.due_on)}</span>}</div>
              {r.next.length > 0 ? (
                <>
                  <div className="field">
                    <label htmlFor="cm">Комментарий к смене статуса (увидит студент)</label>
                    <textarea id="cm" className="textarea" style={{ minHeight: 64 }} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Например: справка будет готова завтра после 14:00" />
                  </div>
                  <div className="row">
                    {r.next.map((s) => (
                      <button key={s} className={`btn btn-sm ${s === 'rejected' ? 'btn-danger' : s === 'ready' || s === 'done' ? '' : 'btn-secondary'}`} disabled={busy} onClick={() => move(s)}>{NEXT_LABEL[s]}</button>
                    ))}
                  </div>
                  {r.next.includes('ready') && r.delivery === 'electronic' && r.category === 'certificate' && <p className="xs muted">«Готово» для электронной справки выпустит PDF с QR-кодом проверки — студент скачает его в заявке.</p>}
                </>
              ) : <p className="small muted">Заявка закрыта.</p>}
              {r.document && <p className="small">Документ № {r.document.number} · <a href={r.document.verify} target="_blank" rel="noopener">страница проверки<ExternalLink aria-hidden="true" style={{ display: 'inline', width: 14, height: 14, marginLeft: 3, verticalAlign: -2 }} /></a></p>}
            </div>
          </Panel>
          <Panel title="История и переписка" id="hist">
            <ol className="timeline">
              {r.events?.map((e, i) => (
                <li key={i}>
                  <span className={`pt ${e.status ? (e.status === 'rejected' || e.status === 'cancelled' ? 'rej' : e.status === 'ready' || e.status === 'done' ? 'ok' : '') : 'msg'}`} aria-hidden="true" />
                  <div className="when">{dateTime(e.at)} · {e.author_name || (e.author === 'staff' ? 'Деканат' : 'Студент')}</div>
                  {e.status_text && <div className="small strong">{e.status_text}</div>}
                  {e.message && <div className={`bubble ${e.author === 'staff' ? 'staff' : ''}`}>{e.message}</div>}
                </li>
              ))}
            </ol>
            <form onSubmit={send} className="stack-sm">
              <label htmlFor="ans" className="label">Ответ студенту</label>
              <textarea id="ans" className="textarea" maxLength={2000} value={msg} onChange={(e) => setMsg(e.target.value)} />
              <div><button className="btn btn-secondary btn-sm" disabled={busy || !msg.trim()}><Send aria-hidden="true" />Отправить</button></div>
            </form>
          </Panel>
        </div>
        <Panel title="Данные заявки" id="pl">
          <dl className="kv">
            {r.payload?.map((p) => <div key={p.label} style={{ display: 'contents' }}><dt>{p.label}</dt><dd>{p.value}</dd></div>)}
            <dt>Получение</dt><dd>{r.delivery === 'electronic' ? 'Электронно (PDF)' : 'На бумаге в деканате'}</dd>
          </dl>
        </Panel>
      </div>
    </div>
  )
}
