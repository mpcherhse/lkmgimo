import { type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import {
  Bell, CalendarDays, CalendarCheck, ClipboardList, FileText, GraduationCap, House, LayoutDashboard, LogOut, Megaphone, Menu, ShieldCheck, UserRound,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { initials } from '../lib/format'
import { Brand } from './Brand'

type Item = { to: string; label: string; icon: typeof House; end?: boolean; tab?: boolean }

const STUDENT: { group?: string; items: Item[] }[] = [
  { items: [
    { to: '/', label: 'Главная', icon: House, end: true, tab: true },
    { to: '/schedule', label: 'Расписание', icon: CalendarDays, tab: true },
    { to: '/grades', label: 'Успеваемость', icon: GraduationCap, tab: true },
    { to: '/requests', label: 'Заявки и справки', icon: FileText, tab: true },
    { to: '/notifications', label: 'Уведомления', icon: Bell },
  ] },
  { group: 'Настройки', items: [
    { to: '/calendar', label: 'Календарь на телефоне', icon: CalendarCheck },
    { to: '/profile', label: 'Профиль', icon: UserRound },
    { to: '/security', label: 'Безопасность', icon: ShieldCheck },
  ] },
]
const STAFF: { group?: string; items: Item[] }[] = [
  { items: [
    { to: '/staff', label: 'Обзор', icon: LayoutDashboard, end: true, tab: true },
    { to: '/staff/requests', label: 'Заявки', icon: ClipboardList, tab: true },
    { to: '/staff/schedule', label: 'Расписание групп', icon: CalendarDays, tab: true },
    { to: '/staff/announcements', label: 'Объявления', icon: Megaphone, tab: true },
  ] },
  { group: 'Настройки', items: [
    { to: '/notifications', label: 'Уведомления', icon: Bell },
    { to: '/security', label: 'Безопасность', icon: ShieldCheck },
  ] },
]

const TAB_SHORT: Record<string, string> = {
  '/': 'Главная', '/schedule': 'Расписание', '/grades': 'Оценки', '/requests': 'Заявки',
  '/staff': 'Обзор', '/staff/requests': 'Заявки', '/staff/schedule': 'Расписание', '/staff/announcements': 'Объявления',
}

export function ConceptBar() {
  return (
    <div className="concept" role="note">
      <strong>Концепт для конкурса «Цифровой деканат будущего».</strong> Не официальный сервис МГИМО — все данные вымышлены.
    </div>
  )
}

export function Shell({ title, children }: { title: string; children: ReactNode }) {
  const { me, logout } = useAuth()
  const loc = useLocation()
  if (!me) return null
  const nav = me.role === 'staff' ? STAFF : STUDENT
  const tabs = nav.flatMap((g) => g.items).filter((i) => i.tab)
  const moreActive = !tabs.some((t) => (t.end ? loc.pathname === t.to : loc.pathname.startsWith(t.to)))
  const sub = me.role === 'student' ? `${me.faculty} · ${me.group}` : me.position

  return (
    <>
      <a href="#main" className="sr-only">Перейти к содержанию</a>
      <ConceptBar />
      <div className="app">
        <nav className="rail" aria-label="Разделы кабинета">
          <Link to={me.role === 'staff' ? '/staff' : '/'} className="brand"><Brand /></Link>
          {nav.map((g, gi) => (
            <div key={gi}>
              {g.group && <div className="nav-group">{g.group}</div>}
              {g.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  <it.icon aria-hidden="true" />
                  <span>{it.label}</span>
                  {it.to === '/notifications' && me.unread > 0 && <span className="nav-count" aria-label={`непрочитанных: ${me.unread}`}>{me.unread}</span>}
                </NavLink>
              ))}
            </div>
          ))}
          <div className="rail-foot">
            <button className="nav-link" style={{ width: '100%', border: 0, background: 'transparent', cursor: 'pointer' }} onClick={logout}>
              <LogOut aria-hidden="true" /><span>Выйти</span>
            </button>
            <p style={{ marginTop: 8 }}>Учебный прототип. <Link to="/about">О проекте</Link></p>
          </div>
        </nav>

        <div className="main">
          <header className="topbar">
            <Link to={me.role === 'staff' ? '/staff' : '/'} className="brand" aria-label="На главную"><Brand sub={false} /></Link>
            <div className="topbar-title">{title}</div>
            <div className="topbar-actions">
              <NavLink to="/notifications" className="icon-btn" aria-label={`Уведомления${me.unread ? `, непрочитанных: ${me.unread}` : ''}`}>
                <Bell aria-hidden="true" />
                {me.unread > 0 && <span className="dot">{me.unread > 99 ? '99+' : me.unread}</span>}
              </NavLink>
              <Link to={me.role === 'staff' ? '/security' : '/profile'} className="user-chip">
                <span className="avatar" aria-hidden="true">{initials(me.short)}</span>
                <span className="who"><span className="small strong">{me.short}</span><small>{sub}</small></span>
              </Link>
            </div>
          </header>
          <main id="main" className="content">{children}</main>
        </div>
      </div>

      <nav className="tabbar" aria-label="Основные разделы">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => `tab ${isActive ? 'active' : ''}`}>
            <t.icon aria-hidden="true" />
            <span>{TAB_SHORT[t.to] ?? t.label}</span>
          </NavLink>
        ))}
        {tabs.length < 5 && (
          <NavLink to="/more" className={`tab ${moreActive ? 'active' : ''}`}>
            <Menu aria-hidden="true" />
            <span>Ещё</span>
            {me.unread > 0 && <span className="dot">{me.unread > 9 ? '9+' : me.unread}</span>}
          </NavLink>
        )}
      </nav>
    </>
  )
}
