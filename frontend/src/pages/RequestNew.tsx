import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, FileBadge, FileQuestion, FileSignature, Send } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { plural } from '../lib/format'
import type { RequestItem, RequestType } from '../lib/types'
import { LoadError, Note, PageSkeleton, Panel, useToast, usePageTitle } from '../components/ui'

const CAT = { certificate: 'Справки', statement: 'Заявления', question: 'Вопрос' } as const
const CAT_ICON = { certificate: FileBadge, statement: FileSignature, question: FileQuestion }

export default function RequestNew() {
  usePageTitle('Новая заявка')
  const [params, setParams] = useSearchParams()
  const { data, error, loading, reload } = useLoad<{ items: RequestType[] }>('/api/request-types')
  const code = params.get('type')
  const type = data?.items.find((t) => t.code === code)
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null

  if (!type) {
    return (
      <div className="stack">
        <Link to="/requests" className="back"><ChevronLeft aria-hidden="true" />Заявки</Link>
        <div className="page-head"><h1>Новая заявка</h1></div>
        {(['certificate', 'statement', 'question'] as const).map((cat) => (
          <section key={cat} className="stack-sm" aria-labelledby={`c-${cat}`}>
            <h2 id={`c-${cat}`} style={{ fontSize: 'var(--fs-md)' }}>{CAT[cat]}</h2>
            <div className="catalog">
              {data.items.filter((t) => t.category === cat).map((t) => {
                const Icon = CAT_ICON[t.category]
                return (
                  <button key={t.code} className="cat-item" onClick={() => setParams({ type: t.code })}>
                    <Icon aria-hidden="true" />
                    <span>
                      <span className="t" style={{ display: 'block' }}>{t.title}</span>
                      <span className="d" style={{ display: 'block' }}>{t.description}</span>
                      <span className="xs muted" style={{ display: 'block', marginTop: 4 }}>
                        {t.category === 'question' ? 'Ответ обычно в течение 2 рабочих дней' : `Срок — ${t.days} ${plural(t.days, 'рабочий день', 'рабочих дня', 'рабочих дней')}`}
                        {t.category === 'certificate' && (t.electronic ? ' · электронно или на бумаге' : ' · только на бумаге')}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    )
  }
  return <RequestForm type={type} onBack={() => setParams({})} />
}

function RequestForm({ type, onBack }: { type: RequestType; onBack: () => void }) {
  const nav = useNavigate()
  const toast = useToast()
  const initial = useMemo(() => Object.fromEntries(type.fields.map((f) => [f.name, ''])), [type])
  const [values, setValues] = useState<Record<string, string>>(initial)
  const [delivery, setDelivery] = useState<'electronic' | 'paper'>(type.electronic ? 'electronic' : 'paper')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const errs: Record<string, string> = {}
    for (const f of type.fields) if (f.required && !values[f.name]?.trim()) errs[f.name] = 'Заполните поле'
    setErrors(errs)
    if (Object.keys(errs).length) { document.getElementById(`f-${Object.keys(errs)[0]}`)?.focus(); return }
    setBusy(true)
    setError(null)
    try {
      const payload = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim() !== '').map(([k, v]) => [k, v.trim()]))
      const r = await api.post<RequestItem>('/api/requests', { type: type.code, delivery: type.category === 'question' ? 'electronic' : delivery, payload })
      toast(`Заявка № ${r.number} отправлена`)
      nav(`/requests/${r.id}`, { replace: true })
    } catch (err) {
      const ae = err as ApiError
      setError(ae.message)
      const fields = ae.data.fields as string[] | undefined
      if (fields?.length) setErrors(Object.fromEntries(fields.map((f) => [f.replace(/^payload\./, ''), 'Проверьте поле'])))
      if (typeof ae.data.field === 'string') setErrors({ [ae.data.field]: ae.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <button type="button" className="back" style={{ border: 0, background: 'none', padding: 0, cursor: 'pointer' }} onClick={onBack}><ChevronLeft aria-hidden="true" />Все виды заявок</button>
      <div className="page-head">
        <h1>{type.title}</h1>
        <p className="sub">{type.description}</p>
      </div>
      <Panel>
        <div className="stack" style={{ maxWidth: 640 }}>
          {error && <Note tone="red">{error}</Note>}
          {type.fields.map((f) => (
            <div className="field" key={f.name}>
              <label htmlFor={`f-${f.name}`}>{f.label}{f.required ? '' : ' (необязательно)'}</label>
              {f.type === 'select' ? (
                <select id={`f-${f.name}`} className="select" value={values[f.name]} aria-invalid={!!errors[f.name]}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                  <option value="">Выберите…</option>
                  {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : f.type === 'textarea' ? (
                <textarea id={`f-${f.name}`} className="textarea" maxLength={f.max ?? 2000} value={values[f.name]} aria-invalid={!!errors[f.name]}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              ) : (
                <input id={`f-${f.name}`} className="input" type={f.type === 'date' ? 'date' : f.type === 'number' ? 'number' : 'text'} maxLength={f.max ?? 300}
                  value={values[f.name]} aria-invalid={!!errors[f.name]} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
              {f.hint && <span className="hint">{f.hint}</span>}
              {errors[f.name] && <span className="err">{errors[f.name]}</span>}
            </div>
          ))}
          {type.category !== 'question' && (
            <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
              <legend className="label" style={{ marginBottom: 6 }}>Как получить</legend>
              <div className="radio-cards">
                <label className="radio-card">
                  <input type="radio" name="delivery" checked={delivery === 'electronic'} disabled={!type.electronic} onChange={() => setDelivery('electronic')} />
                  <span><span className="strong small" style={{ display: 'block' }}>Электронно</span><span className="xs muted">PDF в заявке, проверка по QR-коду{!type.electronic && ' — для этого документа недоступно'}</span></span>
                </label>
                <label className="radio-card">
                  <input type="radio" name="delivery" checked={delivery === 'paper'} onChange={() => setDelivery('paper')} />
                  <span><span className="strong small" style={{ display: 'block' }}>На бумаге</span><span className="xs muted">в деканате, с паспортом</span></span>
                </label>
              </div>
            </fieldset>
          )}
          <div className="row">
            <button className="btn" disabled={busy}><Send aria-hidden="true" />{busy ? 'Отправляем…' : 'Отправить'}</button>
            <button type="button" className="btn btn-secondary" onClick={onBack}>Отмена</button>
          </div>
          <p className="xs muted">Пока деканат не принял заявку, её можно отозвать.</p>
        </div>
      </Panel>
    </form>
  )
}
