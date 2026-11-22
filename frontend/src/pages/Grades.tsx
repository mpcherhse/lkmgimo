import { useSearchParams } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useLoad } from '../lib/useLoad'
import { pct } from '../lib/format'
import type { Discipline, Grades as G } from '../lib/types'
import { Empty, Letter, LoadError, Note, PageSkeleton, Panel, usePageTitle } from '../components/ui'

export default function Grades() {
  usePageTitle('Успеваемость')
  const [params, setParams] = useSearchParams()
  const sem = params.get('semester')
  const { data, error, loading, reload } = useLoad<G>(`/api/grades${sem ? `?semester=${sem}` : ''}`)
  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null
  const s = data.summary
  const w = data.weights

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Успеваемость</h1>
        {data.semesters.length > 1 && (
          <div className="field" style={{ minWidth: 220 }}>
            <label htmlFor="sem" className="sr-only">Семестр</label>
            <select id="sem" className="select" value={data.semester.code} onChange={(e) => setParams({ semester: e.target.value }, { replace: true })}>
              {data.semesters.map((x) => <option key={x.code} value={x.code}>{x.title}{x.current ? ' (текущий)' : ''}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-main">
        <Panel title={data.semester.title} id="sum">
          <div className="spread" style={{ alignItems: 'flex-end' }}>
            <div>
              <div className="row">
                <span className="score-big">{pct(s.complete ? s.rating : s.estimate)}</span><span className="muted">%</span>
                <Letter g={s.complete ? s.grade : s.estimate_grade} />
              </div>
              <p className="small muted" style={{ marginTop: 4 }}>
                {s.complete ? `Рейтинг за семестр${s.bonus ? `, включая бонус ${pct(s.bonus)} п.п. за научную и общественную работу` : ''}`
                  : `Предварительно: среднее по текущему контролю. Закрыто дисциплин: ${s.closed} из ${s.disciplines}`}
              </p>
            </div>
          </div>
          {data.attention.length > 0 && (
            <div className="stack-sm" style={{ marginTop: 12 }}>
              {data.attention.map((a) => <Note key={a.discipline} tone="amber"><b>{a.discipline}</b> — {pct(a.b1)}%. {a.text}.</Note>)}
            </div>
          )}
        </Panel>

        <div className="stack">
          {data.history.length > 0 && (
            <Panel title="По семестрам" id="hist" flush>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Семестр</th><th className="r">Рейтинг</th><th className="c">Оценка</th></tr></thead>
                  <tbody>
                    {data.history.map((h) => (
                      <tr key={h.code}><td>{h.title}</td><td className="r">{pct(h.rating)}%</td><td className="c"><Letter g={h.grade} /></td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
          {data.discount && (
            <Panel title="Скидка на обучение" id="disc">
              <p className="small">Средний рейтинг за {data.discount.semesters} из {data.discount.of} семестров: <b className="num">{pct(data.discount.average)}%</b>.</p>
              {data.discount.blocked_by_retake ? <Note tone="amber">Была пересдача — по правилам скидка за рейтинг не назначается.</Note>
                : data.discount.discount > 0 ? <Note tone="green">Проходите на скидку {data.discount.discount}%.</Note>
                : <p className="small muted">Скидка 30% — от 90%, 60% — от 95% без пересдач. До 30% не хватает {pct(data.discount.gap_to_30)} п.п.</p>}
            </Panel>
          )}
        </div>
      </div>

      <Panel title="Дисциплины" id="disc-list" flush>
        {data.disciplines.length === 0 ? <Empty title="Оценок пока нет">Первые результаты появятся после 1-го среза (до 6-й недели).</Empty>
          : data.disciplines.map((d) => <DisciplineRow key={d.discipline} d={d} current={data.semester.current} />)}
        <details className="explain">
          <summary><ChevronRight aria-hidden="true" />Как считается рейтинг</summary>
          <div className="panel-body small stack-sm">
            <p className="formula"><b>Рейтинг по дисциплине = {w.b1.toLocaleString('ru-RU')}·Б1 + {w.b2.toLocaleString('ru-RU')}·Б2 + {w.b3.toLocaleString('ru-RU')}·Б3</b></p>
            <p><b>Б1 — текущий контроль:</b> среднее трёх срезов (до 6-й, 12-й и 15–16-й недели) плюс премия преподавателя до 10 п.п., не больше 100%.</p>
            <p><b>Б2 — экзамен или зачёт.</b> Правило 70%: если Б1 не ниже 70%, зачёт ставится автоматически с оценкой Б1; если ниже — зачёт сдаётся, и оценка за него не выше 69%. Пересдача: в рейтинг идёт оценка минус 10 п.п. (вторая — минус 20).</p>
            <p><b>Б3 — социальные характеристики</b> (эрудиция, прилежание, активность, посещаемость) — выставляются в конце семестра.</p>
            <p><b>Рейтинг за семестр</b> — среднее по дисциплинам плюс бонус 0–5 за научную и общественную работу, не больше 100%.</p>
            <div className="table-wrap" style={{ marginTop: 4 }}>
              <table className="table">
                <thead><tr><th>Буква</th><th className="r">От, %</th><th>Оценка</th></tr></thead>
                <tbody>{data.scale.map((x) => <tr key={x.letter}><td><span className={`letter letter-${x.letter}`}>{x.letter}</span></td><td className="r">{x.from}</td><td>{x.word} ({x.five})</td></tr>)}</tbody>
              </table>
            </div>
          </div>
        </details>
      </Panel>
    </div>
  )
}

function DisciplineRow({ d, current }: { d: Discipline; current: boolean }) {
  const shown = d.final ?? d.b1
  const g = d.final !== null ? d.final_grade : d.b1_grade
  const slices = d.slices.map((x, i) => (x === null ? null : { n: i + 1, v: x })).filter(Boolean) as { n: number; v: number }[]
  return (
    <div className="disc">
      <div className="disc-top">
        <div className="grow">
          <div className="disc-name">{d.discipline}</div>
          <div className="small muted">{d.control_text}{d.teacher && ` · ${d.teacher}`}</div>
        </div>
        <div className="disc-result">
          <span className="score">{shown === null ? '—' : `${pct(shown)}%`}</span>
          <span className="row" style={{ justifyContent: 'flex-end', gap: 4, marginTop: 2 }}>
            {d.final === null && shown !== null && <span className="xs muted">предв.</span>}<Letter g={g} />
          </span>
        </div>
      </div>
      <div className="parts">
        <div className="part">
          <div className="k">Срезы {d.b1_slices}/3</div>
          <div className="v">{slices.length ? slices.map((x) => pct(x.v, 0)).join(' · ') : '—'}</div>
        </div>
        <div className="part">
          <div className="k">Б1 текущий{d.bonus ? `, премия +${pct(d.bonus, 0)}` : ''}</div>
          <div className="v">{d.b1 === null ? '—' : `${pct(d.b1)}%`}</div>
          {d.b1 !== null && (
            <div className="meter" aria-hidden="true"><i style={{ width: `${Math.min(100, d.b1)}%` }} />{d.control === 'zachet' && <b style={{ left: '70%' }} />}</div>
          )}
        </div>
        <div className="part">
          <div className="k">Б2 {d.control === 'exam' ? 'экзамен' : 'зачёт'}</div>
          <div className="v">
            {d.auto_zachet ? <>{pct(d.b2)}% <small>автомат</small></> : d.b2 !== null ? <>{pct(d.b2)}%{d.retakes ? <small> (пересдача, было {pct(d.exam_raw)})</small> : null}</> : '—'}
          </div>
        </div>
        <div className="part">
          <div className="k">Б3 соц. характеристики</div>
          <div className="v">{d.b3 === null ? '—' : `${pct(d.b3)}%`}</div>
        </div>
      </div>
      {current && d.zachet_cap && <p className="small" style={{ marginTop: 8, color: 'var(--amber-700)' }}>Текущий контроль ниже 70% — зачёт сдаётся, оценка за него не выше 69%.</p>}
      {current && d.needs && (
        <div className="needs">
          {d.control === 'zachet' && d.needs.items[0]?.auto
            ? <span>Если текущий контроль останется не ниже 70% — зачёт автоматом. Итог при Б3 = {pct(d.needs.assumed_social, 0)}%:</span>
            : <span>Сколько нужно на {d.control === 'exam' ? 'экзамене' : 'зачёте'}{d.needs.social_assumed ? ` (если Б3 = ${pct(d.needs.assumed_social, 0)}%)` : ''}:</span>}
          <ul>
            {d.needs.items.map((n) => (
              <li key={n.target} className={n.reachable ? '' : 'no'}>
                {n.target >= 90 ? 'A' : n.target >= 82 ? 'B' : n.target >= 75 ? 'C' : 'E'} (≥{n.target}): {n.auto ? (n.reachable ? 'уже есть' : 'не хватает') : n.reachable ? `${pct(n.need)}%` : 'недостижимо'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
