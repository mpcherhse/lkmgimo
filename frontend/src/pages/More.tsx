import { Link } from 'react-router-dom'
import { Bell, CalendarCheck, ChevronRight, Info, LogOut, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { Panel, usePageTitle } from '../components/ui'

export default function More() {
  usePageTitle('Ещё')
  const { me, logout } = useAuth()
  const items = [
    { to: '/notifications', label: 'Уведомления', icon: Bell, extra: me?.unread ? `${me.unread} непрочитанных` : '' },
    ...(me?.role === 'student' ? [
      { to: '/calendar', label: 'Календарь на телефоне', icon: CalendarCheck, extra: 'iPhone, Android, HarmonyOS' },
      { to: '/profile', label: 'Профиль', icon: UserRound, extra: `${me.faculty} · ${me.group}` },
    ] : []),
    { to: '/security', label: 'Безопасность', icon: ShieldCheck, extra: 'Сеансы, история входов, 2FA' },
    { to: '/about', label: 'О проекте', icon: Info, extra: 'Концепт для конкурса' },
  ]
  return (
    <div className="stack">
      <div className="page-head"><h1>{me?.short}</h1><p className="sub">{me?.role === 'student' ? `${me.faculty} · ${me.course} курс · ${me.group}` : me?.position}</p></div>
      <Panel flush>
        <ul className="list more-list">
          {items.map((i) => (
            <li key={i.to}>
              <Link className="list-item" to={i.to}>
                <i.icon aria-hidden="true" />
                <span className="grow"><span className="title" style={{ display: 'block' }}>{i.label}</span>{i.extra && <span className="meta">{i.extra}</span>}</span>
                <ChevronRight className="chev" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      </Panel>
      <button className="btn btn-secondary" onClick={logout}><LogOut aria-hidden="true" />Выйти</button>
    </div>
  )
}
