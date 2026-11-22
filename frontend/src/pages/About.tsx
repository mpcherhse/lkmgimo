import { Link } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { ConceptBar } from '../components/Shell'
import { Panel, usePageTitle } from '../components/ui'

function Body() {
  return (
    <div className="stack">
      <div className="page-head"><h1>О проекте</h1></div>
      <Panel>
        <div className="stack-sm small" style={{ maxWidth: '72ch' }}>
          <p><b>Цифровой деканат</b> — концепт личного кабинета студента для конкурса «Цифровой деканат будущего». Это учебный прототип, а не официальный сервис МГИМО: логотипы и фирменные знаки вуза не используются, все люди, оценки, заявки и документы вымышлены.</p>
          <p>Что внутри: главная «что важно сейчас», расписание с переносами и сессией, успеваемость по рейтинговой системе (срезы, правило 70%, «сколько нужно на экзамене»), заявки и справки со статусами и PDF с QR-проверкой, уведомления, календарь на телефоне (iPhone, Android, HarmonyOS), кабинет сотрудника деканата.</p>
          <p>Защита: пароли хранятся только в виде хэша Argon2id, ключ сеанса меняется каждые 30 минут, у сотрудников обязательна двухфакторная защита, чужие данные не открываются подстановкой адреса — это проверяется автотестами.</p>
          <p><a href="/process.pdf">Описание процесса разработки (PDF)</a></p>
        </div>
      </Panel>
    </div>
  )
}

export default function About({ standalone }: { standalone?: boolean }) {
  usePageTitle('О проекте')
  if (!standalone) return <Body />
  return (
    <div className="auth" style={{ background: 'var(--ground)' }}>
      <ConceptBar />
      <div className="content" style={{ maxWidth: 820 }}>
        <Link to="/" className="brand" style={{ color: 'var(--navy-900)', marginBottom: 16 }}><Brand /></Link>
        <Body />
        <p style={{ marginTop: 16 }}><Link to="/">Войти в кабинет</Link></p>
      </div>
    </div>
  )
}
