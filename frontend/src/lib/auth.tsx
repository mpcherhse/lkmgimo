import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, onAuthError } from './api'
import type { Me } from './types'

interface AuthState {
  me: Me | null
  ready: boolean
  notice: string | null          // почему вас разлогинило (кража cookie, истёк срок и т. п.)
  challenge: boolean              // сеанс всплыл на другом устройстве — нужен пароль
  refresh: () => Promise<void>
  logout: () => Promise<void>
  setUnread: (n: number) => void
  clearChallenge: () => void
}
const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [ready, setReady] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [challenge, setChallenge] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setMe(await api.get<Me>('/api/me'))
      setChallenge(false)
    } catch (e) {
      const err = e as ApiError
      if (err.code === 'reauth_required') setChallenge(true)
      else setMe(null)
    } finally {
      setReady(true)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => onAuthError((e) => {
    if (e.code === 'reauth_required') { setChallenge(true); return }
    if (e.code === 'mfa_required') return
    setMe((prev) => {
      if (prev && e.code === 'session_revoked') setNotice(e.message)
      else if (prev) setNotice('Сеанс завершён — войдите снова')
      return null
    })
  }), [])

  const logout = useCallback(async () => {
    try { navigator.serviceWorker?.controller?.postMessage({ type: 'logout' }) } catch { /* нет service worker */ }
    try { await api.post('/api/logout') } catch { /* всё равно выходим */ }
    try { if ('caches' in window) for (const k of await caches.keys()) await caches.delete(k) } catch { /* нет кэша */ }
    setMe(null)
    setNotice(null)
  }, [])

  const setUnread = useCallback((n: number) => setMe((m) => (m ? { ...m, unread: n } : m)), [])
  const clearChallenge = useCallback(() => setChallenge(false), [])

  return <Ctx.Provider value={{ me, ready, notice, challenge, refresh, logout, setUnread, clearChallenge }}>{children}</Ctx.Provider>
}

export function useAuth() {
  const v = useContext(Ctx)
  if (!v) throw new Error('AuthProvider missing')
  return v
}
