import { Link } from 'react-router-dom'
import { Mail, Phone, MapPin } from 'lucide-react'
import { useLoad } from '../lib/useLoad'
import { LoadError, Note, PageSkeleton, Panel, usePageTitle } from '../components/ui'

type P = {
  last_name: string; first_name: string; middle_name: string; faculty: { code: string; name: string }; program: string; profile: string; level: string
  course: number; group: string; languages: { code: string; language: string }[]; record_book: string; funding: string; email: string; phone: string
  enrolled_year: number; advisor: string; dean: { office: string; phone: string; email: string }
}

export default function Profile() {
  usePageTitle('Профиль')
  const { data, error, loading, reload } = useLoad<P>('/api/profile')
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null
  const p = data
  return (
    <div className="stack">
      <div className="page-head">
        <h1>{p.last_name} {p.first_name} {p.middle_name}</h1>
        <p className="sub">{p.faculty.name} · {p.course} курс · группа {p.group}</p>
      </div>
      <div className="grid grid-main">
        <Panel title="Учёба" id="study">
          <dl className="kv">
            <dt>Уровень</dt><dd>{p.level}</dd>
            <dt>Направление</dt><dd>{p.program}</dd>
            <dt>Профиль</dt><dd>{p.profile}</dd>
            <dt>Факультет</dt><dd>{p.faculty.name} ({p.faculty.code})</dd>
            <dt>Курс и группа</dt><dd>{p.course} курс, {p.group}</dd>
            <dt>Языковые группы</dt><dd>{p.languages.map((l) => `${l.language} — ${l.code}`).join('; ') || '—'}</dd>
            <dt>Основа обучения</dt><dd>{p.funding}</dd>
            <dt>Год поступления</dt><dd>{p.enrolled_year}</dd>
            <dt>Зачётная книжка</dt><dd className="num">{p.record_book}</dd>
            {p.advisor && <><dt>Куратор</dt><dd>{p.advisor}</dd></>}
          </dl>
        </Panel>
        <div className="stack">
          <Panel title="Контакты" id="contacts">
            <dl className="kv">
              <dt>Почта</dt><dd>{p.email}</dd>
              <dt>Телефон</dt><dd>{p.phone || '—'}</dd>
            </dl>
            <p className="xs muted">Изменить данные можно заявлением в деканат: <Link to="/requests/new?type=question">написать</Link>.</p>
          </Panel>
          <Panel title="Деканат факультета" id="dean">
            <ul className="list">
              <li className="stack-sm" style={{ gap: 6 }}>
                <span className="row small"><MapPin aria-hidden="true" style={{ width: 16, height: 16 }} />{p.dean.office}</span>
                <span className="row small"><Phone aria-hidden="true" style={{ width: 16, height: 16 }} /><a href={`tel:${p.dean.phone.replace(/[^+\d]/g, '')}`}>{p.dean.phone}</a></span>
                <span className="row small"><Mail aria-hidden="true" style={{ width: 16, height: 16 }} /><a href={`mailto:${p.dean.email}`}>{p.dean.email}</a></span>
              </li>
            </ul>
          </Panel>
        </div>
      </div>
      <Note>Все данные в концепте вымышлены.</Note>
    </div>
  )
}
