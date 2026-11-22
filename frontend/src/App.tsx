import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './lib/auth'
import { Shell } from './components/Shell'
import { PageSkeleton } from './components/ui'
import { Login } from './pages/Login'
import { Reauth } from './pages/Reauth'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Schedule = lazy(() => import('./pages/Schedule'))
const Grades = lazy(() => import('./pages/Grades'))
const Requests = lazy(() => import('./pages/Requests'))
const RequestNew = lazy(() => import('./pages/RequestNew'))
const RequestDetail = lazy(() => import('./pages/RequestDetail'))
const Notifications = lazy(() => import('./pages/Notifications'))
const CalendarPage = lazy(() => import('./pages/CalendarPage'))
const Profile = lazy(() => import('./pages/Profile'))
const Security = lazy(() => import('./pages/Security'))
const More = lazy(() => import('./pages/More'))
const About = lazy(() => import('./pages/About'))
const Verify = lazy(() => import('./pages/Verify'))
const StaffCode = lazy(() => import('./pages/StaffCode'))
const StaffHome = lazy(() => import('./pages/staff/StaffHome'))
const StaffRequests = lazy(() => import('./pages/staff/StaffRequests'))
const StaffRequest = lazy(() => import('./pages/staff/StaffRequest'))
const StaffSchedule = lazy(() => import('./pages/staff/StaffSchedule'))
const StaffAnnouncements = lazy(() => import('./pages/staff/StaffAnnouncements'))

function Page({ title, role, children }: { title: string; role?: 'student' | 'staff'; children: ReactNode }) {
  const { me } = useAuth()
  if (role && me && me.role !== role) return <Navigate to={me.role === 'staff' ? '/staff' : '/'} replace />
  return (
    <Shell title={title}>
      <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
    </Shell>
  )
}

export function App() {
  const { me, ready, challenge } = useAuth()
  const loc = useLocation()

  // публичные страницы: проверка справки, о проекте и код 2FA для жюри
  if (loc.pathname.startsWith('/verify/')) return <Suspense fallback={null}><Routes><Route path="/verify/:code" element={<Verify />} /></Routes></Suspense>
  if (loc.pathname === '/staff-code') return <Suspense fallback={null}><StaffCode /></Suspense>
  if (loc.pathname === '/about' && !me) return <Suspense fallback={null}><About standalone /></Suspense>

  if (!ready) return <div className="auth" aria-busy="true" />
  if (challenge) return <Reauth />
  if (!me) return <Login />

  const home = me.role === 'staff' ? '/staff' : '/'
  return (
    <Routes>
      <Route path="/" element={me.role === 'staff' ? <Navigate to="/staff" replace /> : <Page title="Главная" role="student"><Dashboard /></Page>} />
      <Route path="/schedule" element={<Page title="Расписание" role="student"><Schedule /></Page>} />
      <Route path="/grades" element={<Page title="Успеваемость" role="student"><Grades /></Page>} />
      <Route path="/requests" element={<Page title="Заявки и справки" role="student"><Requests /></Page>} />
      <Route path="/requests/new" element={<Page title="Новая заявка" role="student"><RequestNew /></Page>} />
      <Route path="/requests/:id" element={<Page title="Заявка" role="student"><RequestDetail /></Page>} />
      <Route path="/calendar" element={<Page title="Календарь на телефоне" role="student"><CalendarPage /></Page>} />
      <Route path="/profile" element={<Page title="Профиль" role="student"><Profile /></Page>} />
      <Route path="/notifications" element={<Page title="Уведомления"><Notifications /></Page>} />
      <Route path="/security" element={<Page title="Безопасность"><Security /></Page>} />
      <Route path="/more" element={<Page title="Ещё"><More /></Page>} />
      <Route path="/about" element={<Page title="О проекте"><About /></Page>} />
      <Route path="/staff" element={<Page title="Обзор" role="staff"><StaffHome /></Page>} />
      <Route path="/staff/requests" element={<Page title="Заявки" role="staff"><StaffRequests /></Page>} />
      <Route path="/staff/requests/:id" element={<Page title="Заявка" role="staff"><StaffRequest /></Page>} />
      <Route path="/staff/schedule" element={<Page title="Расписание групп" role="staff"><StaffSchedule /></Page>} />
      <Route path="/staff/announcements" element={<Page title="Объявления" role="staff"><StaffAnnouncements /></Page>} />
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  )
}
