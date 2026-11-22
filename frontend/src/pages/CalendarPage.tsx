import { useState } from 'react'
import { MonitorSmartphone, Copy, KeyRound, Link2, RefreshCw, Smartphone, Trash2, TabletSmartphone } from 'lucide-react'
import { api, ApiError } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { dateTime, relative } from '../lib/format'
import { copyText, LoadError, Note, PageSkeleton, Panel, useToast, usePageTitle } from '../components/ui'
import { ReauthInline } from './Security'

type Status = {
  feed: { created_at: string; last_used_at: string | null; hint: string } | null
  caldav: { server: string; host: string; login: string; principal: string }
  app_passwords: { id: string; label: string; created_at: string; last_used_at: string | null; client: string | null }[]
}
type Feed = { url: string; links: { https: string; webcal: string; google: string; outlook: string; yandex: string }; qr: string }

export default function CalendarPage() {
  usePageTitle('Календарь на телефоне')
  const toast = useToast()
  const { data, error, loading, reload } = useLoad<Status>('/api/calendar')
  const [feed, setFeed] = useState<Feed | null>(null)
  const [pw, setPw] = useState<{ password: string; login: string; server: string } | null>(null)
  const [label, setLabel] = useState('Телефон')
  const [needReauth, setNeedReauth] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function makeFeed() {
    if (data?.feed && !window.confirm('Выпустить новую ссылку? Старая перестанет работать на всех устройствах, где вы её добавили.')) return
    setBusy(true); setErr(null)
    try { setFeed(await api.post<Feed>('/api/calendar/feed')); reload(true) } catch (e) { setErr((e as ApiError).message) } finally { setBusy(false) }
  }
  async function makePassword() {
    setBusy(true); setErr(null)
    try { setPw(await api.post('/api/calendar/app-passwords', { label: label.trim() || 'Телефон' })); reload(true) }
    catch (e) { const ae = e as ApiError; if (ae.code === 'reauth_required') setNeedReauth(true); else setErr(ae.message) }
    finally { setBusy(false) }
  }
  async function revoke(id: string) {
    if (!window.confirm('Отозвать пароль? Календарь на этом устройстве перестанет обновляться.')) return
    try { await api.del(`/api/calendar/app-passwords/${id}`); reload(true); toast('Пароль приложения отозван') } catch (e) { setErr((e as ApiError).message) }
  }
  async function copy(t: string) { toast((await copyText(t)) ? 'Скопировано' : 'Не удалось скопировать — выделите и скопируйте вручную') }

  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <LoadError error={error} retry={reload} />
  if (!data) return null

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Календарь на телефоне</h1>
        <p className="sub">Расписание, сессия и дедлайны появятся в обычном календаре телефона. Переносы и отмены обновятся сами — календарь проверяет изменения примерно раз в час. Только чтение: изменить занятие из календаря нельзя.</p>
      </div>
      {err && <Note tone="red">{err}</Note>}

      <Panel title="1. Ссылка-подписка" id="feed">
        <div className="stack">
          <p className="small">Подходит для iPhone и Mac, Google Календаря (Android), Яндекс Календаря и Outlook. Ссылка личная: по ней виден ваш календарь — не публикуйте её.</p>
          {feed ? (
            <div className="grid grid-2" style={{ alignItems: 'start' }}>
              <div className="stack-sm">
                <div className="copy-row"><code>{feed.url}</code><button className="btn btn-secondary btn-sm" onClick={() => copy(feed.url)} aria-label="Скопировать ссылку"><Copy aria-hidden="true" /></button></div>
                <div className="row">
                  <a className="btn btn-sm" href={feed.links.webcal}><MonitorSmartphone aria-hidden="true" />iPhone / Mac</a>
                  <a className="btn btn-sm btn-secondary" href={feed.links.google} target="_blank" rel="noopener noreferrer"><Smartphone aria-hidden="true" />Google (Android)</a>
                  <a className="btn btn-sm btn-secondary" href={feed.links.outlook} target="_blank" rel="noopener noreferrer">Outlook</a>
                </div>
                <p className="xs muted">Ссылка показана один раз. Потеряли — выпустите новую, старая отключится.</p>
              </div>
              <div className="row" style={{ alignItems: 'flex-start' }}>
                <img className="qr" width={168} height={168} src={feed.qr} alt="QR-код ссылки на календарь" />
                <p className="small muted" style={{ maxWidth: 220 }}>Открыли кабинет на компьютере? Наведите камеру телефона на код — iPhone предложит подписаться на календарь.</p>
              </div>
            </div>
          ) : (
            <div className="row">
              <button className="btn" onClick={makeFeed} disabled={busy}>{data.feed ? <><RefreshCw aria-hidden="true" />Выпустить новую ссылку</> : <><Link2 aria-hidden="true" />Получить ссылку</>}</button>
              {data.feed && <span className="small muted">Действующая ссылка …{data.feed.hint} выпущена {relative(data.feed.created_at)}{data.feed.last_used_at ? `, календарь обновлялся ${relative(data.feed.last_used_at)}` : ', ещё не открывалась'}</span>}
            </div>
          )}
          <div className="cal-options">
            <div className="platform">
              <h3><MonitorSmartphone aria-hidden="true" />iPhone, iPad, Mac</h3>
              <ol><li>Нажмите «iPhone / Mac» или наведите камеру на QR-код.</li><li>Подтвердите «Подписаться».</li><li>Календарь «Учёба» появится в приложении «Календарь».</li></ol>
            </div>
            <div className="platform">
              <h3><Smartphone aria-hidden="true" />Android</h3>
              <ol><li>Нажмите «Google (Android)» и войдите в Google-аккаунт телефона.</li><li>Подтвердите «Добавить».</li><li>В Google Календаре включите синхронизацию календаря «Учёба».</li></ol>
              <p className="xs muted">Яндекс Календарь: «Добавить календарь» → «По ссылке», вставьте ссылку.</p>
            </div>
            <div className="platform">
              <h3><TabletSmartphone aria-hidden="true" />HarmonyOS</h3>
              <p className="small">В HarmonyOS нет подписки по ссылке — используйте способ 2 (CalDAV) ниже.</p>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="2. Аккаунт CalDAV" id="dav">
        <div className="stack">
          <p className="small">Для HarmonyOS («Календарь» → «Добавить аккаунт» → «CalDAV»), а также iPhone («Настройки» → «Календарь» → «Учётные записи» → «Другое» → «CalDAV»), macOS и Android через DAVx⁵. Вместо основного пароля — отдельный пароль приложения: его можно отозвать, не меняя пароль кабинета.</p>
          <dl className="kv">
            <dt>Сервер</dt><dd><span className="copy-row"><code>{data.caldav.server}</code><button className="btn btn-secondary btn-sm" onClick={() => copy(data.caldav.server)} aria-label="Скопировать адрес сервера"><Copy aria-hidden="true" /></button></span></dd>
            <dt>Логин</dt><dd><code className="code">{data.caldav.login}</code></dd>
            <dt>Пароль</dt><dd>пароль приложения (создайте ниже)</dd>
          </dl>
          {pw ? (
            <Note tone="green">
              <div className="stack-sm">
                <span>Пароль приложения — введите его в настройках календаря. Больше он показан не будет.</span>
                <div className="secret">{pw.password}</div>
                <button className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => copy(pw.password)}><Copy aria-hidden="true" />Скопировать</button>
              </div>
            </Note>
          ) : needReauth ? (
            <ReauthInline onDone={() => { setNeedReauth(false); makePassword() }} text="Чтобы создать пароль приложения, подтвердите вход паролем от кабинета." />
          ) : (
            <div className="row" style={{ alignItems: 'flex-end' }}>
              <div className="field" style={{ maxWidth: 260 }}>
                <label htmlFor="lbl">Название устройства</label>
                <input id="lbl" className="input" maxLength={60} value={label} onChange={(e) => setLabel(e.target.value)} />
              </div>
              <button className="btn" onClick={makePassword} disabled={busy}><KeyRound aria-hidden="true" />Создать пароль приложения</button>
            </div>
          )}
          {data.app_passwords.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Устройство</th><th>Создан</th><th>Последнее обновление</th><th /></tr></thead>
                <tbody>
                  {data.app_passwords.map((p) => (
                    <tr key={p.id}>
                      <td>{p.label}{p.client && <div className="xs muted wrap-any">{p.client.slice(0, 60)}</div>}</td>
                      <td className="nowrap">{dateTime(p.created_at)}</td>
                      <td className="nowrap">{p.last_used_at ? relative(p.last_used_at) : 'не подключался'}</td>
                      <td className="r"><button className="btn btn-danger btn-sm" onClick={() => revoke(p.id)}><Trash2 aria-hidden="true" />Отозвать</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Panel>
      <p className="xs muted">Экзамен или дедлайн можно добавить и по одному — кнопка «В календарь» рядом с событием скачивает файл .ics, его открывает любой календарь.</p>
    </div>
  )
}
