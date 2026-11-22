import { useParams } from 'react-router-dom'
import { BadgeCheck, CircleX } from 'lucide-react'
import { useLoad } from '../lib/useLoad'
import { dayMonth } from '../lib/format'
import { Brand } from '../components/Brand'
import { ConceptBar } from '../components/Shell'
import { Note, Skeleton, usePageTitle } from '../components/ui'

type V = { valid: boolean; number: string; title: string; issued_at: string; valid_until: string; holder: string; faculty: string; revoked: boolean; note: string }

export default function Verify() {
  usePageTitle('Проверка документа')
  const { code } = useParams()
  const { data, error, loading } = useLoad<V>(`/api/verify/${encodeURIComponent(code ?? '')}`)
  return (
    <div className="auth">
      <ConceptBar />
      <div className="auth-main">
        <div className="auth-card stack">
          <div className="brand"><Brand /></div>
          <h1>Проверка подлинности документа</h1>
          {loading && <Skeleton lines={4} />}
          {error && <Note tone="red" icon={<CircleX aria-hidden="true" />}>{error.status === 404 ? 'Документ с таким кодом не найден. Проверьте ссылку или QR-код.' : error.message}</Note>}
          {data && (
            <>
              {data.valid
                ? <Note tone="green" icon={<BadgeCheck aria-hidden="true" />}><b>Документ действителен</b></Note>
                : <Note tone="red" icon={<CircleX aria-hidden="true" />}><b>{data.revoked ? 'Документ отозван' : 'Срок действия истёк'}</b></Note>}
              <dl className="kv">
                <dt>Документ</dt><dd>{data.title}</dd>
                <dt>Номер</dt><dd className="num">{data.number}</dd>
                <dt>Выдан</dt><dd>{dayMonth(data.issued_at, true)}</dd>
                <dt>Действителен до</dt><dd>{dayMonth(data.valid_until, true)}</dd>
                <dt>Владелец</dt><dd>{data.holder}</dd>
                <dt>Факультет</dt><dd>{data.faculty}</dd>
              </dl>
              <p className="xs muted">Для защиты персональных данных показаны только инициалы. {data.note}.</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
