import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, Download, Send, Undo2 } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { dateTime, dayMonth } from '../lib/format'
import type { RequestItem } from '../lib/types'
import { Empty, LoadError, Note, PageSkeleton, Panel, StatusBadge, Steps, useToast, usePageTitle } from '../components/ui'

const OPEN = ['submitted', 'accepted', 'in_progress', 'ready']

export default function RequestDetail() {
  const { id } = useParams()
  const { data, error, loading, reload, setData } = useLoad<RequestItem>(`/api/requests/${id}`)
  usePageTitle(data ? `${data.title} ${data.number}` : 'Заявка')
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  if (loading && !data) return <PageSkeleton />
  if (error && !data) {
    return error.status === 404
      ? <div className="stack"><Link to="/requests" className="back"><ChevronLeft aria-hidden="true" />Заявки</Link><Empty title="Заявка не найдена">Возможно, ссылка устарела.</Empty></div>
      : <LoadError error={error} retry={reload} />
  }
  if (!data) return null
  const r = data

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true); setErr(null)
    try { setData(await api.post<RequestItem>(`/api/requests/${r.id}/messages`, { text: text.trim() })); setText('') }
    catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }
  async function cancel() {
    if (!window.confirm('Отозвать заявку? Деканат её не увидит.')) return
    setBusy(true); setErr(null)
    try { setData(await api.post<RequestItem>(`/api/requests/${r.id}/cancel`)); toast('Заявка отозвана') }
    catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }

  return (
    <div className="stack">
      <Link to="/requests" className="back"><ChevronLeft aria-hidden="true" />Заявки</Link>
      <div className="page-head">
        <h1>{r.title}</h1>
        <div className="page-actions">
          {r.can_cancel && <button className="btn btn-danger btn-sm" onClick={cancel} disabled={busy}><Undo2 aria-hidden="true" />Отозвать</button>}
        </div>
        <p className="sub">№ {r.number} · подана {dateTime(r.created_at)}</p>
      </div>
      {err && <Note tone="red">{err}</Note>}

      <div className="grid grid-main">
        <div className="stack">
          <Panel>
            <div className="stack-sm">
              <div className="spread"><StatusBadge status={r.status} text={r.status_text} />{r.due_on && OPEN.includes(r.status) && r.status !== 'ready' && <span className="small muted">ориентировочно до {dayMonth(r.due_on)}</span>}</div>
              {OPEN.includes(r.status) && <Steps status={r.status} />}
              {r.status_comment && <p className="small">{r.status_comment}</p>}
              {r.status === 'ready' && r.document && (
                <Note tone="green">
                  <div className="spread">
                    <span>Документ № {r.document.number} готов. Действителен до {dayMonth(r.document.valid_until, true)}.</span>
                    <a className="btn btn-sm" href={`/api/requests/${r.id}/document.pdf`} download><Download aria-hidden="true" />Скачать PDF</a>
                  </div>
                </Note>
              )}
              {r.status === 'ready' && !r.document && <Note tone="green">Документ готов — заберите его в деканате, с собой нужен паспорт.</Note>}
              {r.status === 'done' && r.document && <a className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} href={`/api/requests/${r.id}/document.pdf`} download><Download aria-hidden="true" />Скачать PDF</a>}
            </div>
          </Panel>

          <Panel title="История и переписка" id="hist">
            <ol className="timeline">
              {r.events?.map((e, i) => (
                <li key={i}>
                  <span className={`pt ${e.status ? (e.status === 'rejected' || e.status === 'cancelled' ? 'rej' : e.status === 'ready' || e.status === 'done' ? 'ok' : '') : 'msg'}`} aria-hidden="true" />
                  <div className="when">{dateTime(e.at)} · {e.author === 'staff' ? (e.author_name || 'Деканат') : e.author === 'student' ? 'Вы' : 'Система'}</div>
                  {e.status_text && <div className="small strong">{e.status_text}</div>}
                  {e.message && <div className={`bubble ${e.author === 'staff' ? 'staff' : ''}`}>{e.message}</div>}
                </li>
              ))}
            </ol>
            {OPEN.includes(r.status) ? (
              <form onSubmit={send} className="stack-sm" style={{ marginTop: 4 }}>
                <label htmlFor="msg" className="label">Сообщение в деканат</label>
                <textarea id="msg" className="textarea" maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} placeholder="Уточнение или вопрос по заявке" />
                <div><button className="btn btn-secondary btn-sm" disabled={busy || !text.trim()}><Send aria-hidden="true" />Отправить</button></div>
              </form>
            ) : <p className="small muted">Заявка закрыта. Если остались вопросы — <Link to="/requests/new?type=question">напишите в деканат</Link>.</p>}
          </Panel>
        </div>

        <Panel title="Данные заявки" id="payload">
          <dl className="kv">
            {r.payload?.map((p) => <div key={p.label} style={{ display: 'contents' }}><dt>{p.label}</dt><dd>{p.value}</dd></div>)}
            {r.category !== 'question' && <><dt>Получение</dt><dd>{r.delivery === 'electronic' ? 'Электронно (PDF)' : 'На бумаге в деканате'}</dd></>}
          </dl>
        </Panel>
      </div>
    </div>
  )
}
