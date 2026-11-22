import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CircleCheck, Info, Inbox, RefreshCw } from 'lucide-react'
import type { ApiError } from '../lib/api'
import type { Grade, ReqStatus } from '../lib/types'

export function Panel({ title, action, children, flush, className = '', id }: { title?: ReactNode; action?: ReactNode; children: ReactNode; flush?: boolean; className?: string; id?: string }) {
  return (
    <section className={`panel ${className}`} aria-labelledby={id}>
      {(title || action) && (
        <div className="panel-head">
          {title && <h2 id={id}>{title}</h2>}
          {action}
        </div>
      )}
      <div className={flush ? 'panel-flush' : 'panel-body'}>{children}</div>
    </section>
  )
}

export function Note({ tone = 'info', children, icon }: { tone?: 'info' | 'red' | 'amber' | 'green'; children: ReactNode; icon?: ReactNode }) {
  const Icon = tone === 'red' || tone === 'amber' ? AlertTriangle : tone === 'green' ? CircleCheck : Info
  return (
    <div className={`note ${tone !== 'info' ? 'note-' + tone : ''}`} role={tone === 'red' ? 'alert' : undefined}>
      {icon ?? <Icon aria-hidden="true" />}
      <div>{children}</div>
    </div>
  )
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="empty">
      {icon ?? <Inbox aria-hidden="true" />}
      <span className="strong">{title}</span>
      {children}
    </div>
  )
}

export function LoadError({ error, retry }: { error: ApiError; retry?: () => void }) {
  return (
    <Note tone="red">
      <div className="spread">
        <span>{error.message}</span>
        {retry && <button className="btn btn-secondary btn-sm" onClick={() => retry()}><RefreshCw aria-hidden="true" />Повторить</button>}
      </div>
    </Note>
  )
}

export function Skeleton({ lines = 3, height = 18 }: { lines?: number; height?: number }) {
  return (
    <div className="stack-sm" aria-busy="true" aria-label="Загрузка">
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skeleton" style={{ height, width: `${92 - i * 13}%` }} />)}
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="stack" aria-busy="true">
      <div className="skeleton" style={{ height: 28, width: 240 }} />
      <div className="panel panel-body"><Skeleton lines={4} /></div>
      <div className="panel panel-body"><Skeleton lines={3} /></div>
    </div>
  )
}

const STATUS_TONE: Record<ReqStatus, string> = {
  submitted: 'badge-grey', accepted: '', in_progress: 'badge-amber', ready: 'badge-green', done: 'badge-outline', rejected: 'badge-red', cancelled: 'badge-outline',
}
export function StatusBadge({ status, text }: { status: ReqStatus; text: string }) {
  return <span className={`badge ${STATUS_TONE[status]}`}>{text}</span>
}

const STEP: Record<ReqStatus, number> = { submitted: 1, accepted: 2, in_progress: 3, ready: 4, done: 4, rejected: 4, cancelled: 1 }
export function Steps({ status }: { status: ReqStatus }) {
  const n = STEP[status]
  return (
    <div className={`steps ${status === 'rejected' ? 'rej' : ''}`} aria-hidden="true">
      {[1, 2, 3, 4].map((i) => <span key={i} className={i <= n && status !== 'cancelled' ? 'on' : ''} />)}
    </div>
  )
}

export function Letter({ g }: { g: Grade | null | undefined }) {
  if (!g) return null
  return <span className={`letter letter-${g.letter}`} title={`${g.word}, ${g.five}`}>{g.letter}</span>
}

// ---------- всплывающие сообщения ----------
const ToastCtx = createContext<(msg: string) => void>(() => {})
export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null)
  const timer = useRef<number>()
  const show = useCallback((m: string) => {
    setMsg(m)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMsg(null), 3200)
  }, [])
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div aria-live="polite" className="sr-only">{msg}</div>
      {msg && <div className="toast" role="status">{msg}</div>}
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

export async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); return true } catch { return false }
}

export function usePageTitle(title: string) {
  useEffect(() => { document.title = `${title} — Цифровой деканат (концепт)` }, [title])
}
