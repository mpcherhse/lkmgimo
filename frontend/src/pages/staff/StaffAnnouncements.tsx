import { useState, type FormEvent } from 'react'
import { Megaphone, Send } from 'lucide-react'
import { api, ApiError } from '../../lib/api'
import { useLoad } from '../../lib/useLoad'
import { relative } from '../../lib/format'
import { Empty, LoadError, Note, PageSkeleton, Panel, useToast, usePageTitle } from '../../components/ui'

type Groups = { faculties: { id: number; code: string; name: string }[]; groups: { id: number; code: string; kind: string; course: number; faculty_id: number }[] }
type A = { id: string; title: string; body: string; important: boolean; faculty: string; course: number | null; group: string | null; published_at: string; sent: number }

export default function StaffAnnouncements() {
  usePageTitle('Объявления')
  const toast = useToast()
  const groups = useLoad<Groups>('/api/staff/groups')
  const list = useLoad<{ items: A[] }>('/api/staff/announcements')
  const [f, setF] = useState({ title: '', body: '', important: false, faculty: '', course: '', group: '' })
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (groups.loading && !groups.data) return <PageSkeleton />
  if (groups.error && !groups.data) return <LoadError error={groups.error} retry={groups.reload} />
  const g = groups.data!
  const faculty = Number(f.faculty) || g.faculties[0]?.id
  const courses = [...new Set(g.groups.filter((x) => x.faculty_id === faculty).map((x) => x.course))].sort()
  const grps = g.groups.filter((x) => x.faculty_id === faculty && x.kind === 'academic' && (!f.course || x.course === Number(f.course)))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr(null)
    try {
      const r = await api.post<{ recipients: number }>('/api/staff/announcements', {
        title: f.title.trim(), body: f.body.trim(), important: f.important, faculty_id: faculty,
        course: f.course ? Number(f.course) : null, group_id: f.group ? Number(f.group) : null,
      })
      toast(`Опубликовано. Получателей: ${r.recipients}`)
      setF({ ...f, title: '', body: '', important: false })
      list.reload(true)
    } catch (x) { setErr((x as ApiError).message) } finally { setBusy(false) }
  }

  return (
    <div className="stack">
      <div className="page-head"><h1>Объявления</h1><p className="sub">Объявление приходит студентам в уведомления. «Важно» выделяется красным и поднимается наверх.</p></div>
      <div className="grid grid-main">
        <Panel title="Новое объявление" id="new">
          <form className="stack-sm" onSubmit={submit}>
            {err && <Note tone="red">{err}</Note>}
            <div className="row" style={{ alignItems: 'flex-end' }}>
              <div className="field"><label htmlFor="fac">Факультет</label>
                <select id="fac" className="select" value={faculty} onChange={(e) => setF({ ...f, faculty: e.target.value, course: '', group: '' })}>{g.faculties.map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</select>
              </div>
              <div className="field"><label htmlFor="crs">Курс</label>
                <select id="crs" className="select" value={f.course} onChange={(e) => setF({ ...f, course: e.target.value, group: '' })}><option value="">все</option>{courses.map((c) => <option key={c} value={c}>{c}</option>)}</select>
              </div>
              <div className="field"><label htmlFor="grp">Группа</label>
                <select id="grp" className="select" value={f.group} onChange={(e) => setF({ ...f, group: e.target.value })}><option value="">все</option>{grps.map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</select>
              </div>
            </div>
            <div className="field"><label htmlFor="t">Заголовок</label><input id="t" className="input" maxLength={140} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
            <div className="field"><label htmlFor="b">Текст</label><textarea id="b" className="textarea" maxLength={4000} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></div>
            <label className="check"><input type="checkbox" checked={f.important} onChange={(e) => setF({ ...f, important: e.target.checked })} />Важно — выделить и поднять наверх</label>
            <div><button className="btn" disabled={busy || f.title.trim().length < 3 || f.body.trim().length < 3}><Send aria-hidden="true" />Опубликовать</button></div>
          </form>
        </Panel>
        <Panel title="Опубликованные" id="list" flush>
          {list.data?.items.length ? (
            <ul className="list">
              {list.data.items.map((a) => (
                <li key={a.id} className="list-item">
                  <span className="grow">
                    <span className="title" style={{ display: 'block' }}>{a.important && <span className="badge badge-red" style={{ marginRight: 6 }}>Важно</span>}{a.title}</span>
                    <span className="meta">{a.faculty}{a.course ? `, ${a.course} курс` : ''}{a.group ? `, ${a.group}` : ''} · {relative(a.published_at)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : <Empty title="Объявлений пока нет" icon={<Megaphone aria-hidden="true" />} />}
        </Panel>
      </div>
    </div>
  )
}
