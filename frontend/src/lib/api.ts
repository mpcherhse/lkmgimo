// Один вход в API: тот же сайт, cookie сеанса HttpOnly (скрипт её не видит), заголовок x-lk-request для изменяющих запросов.
export class ApiError extends Error {
  status: number
  code?: string
  data: Record<string, unknown>
  constructor(status: number, message: string, data: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = typeof data.code === 'string' ? data.code : undefined
    this.data = data
  }
}

type Listener = (e: ApiError) => void
const authListeners = new Set<Listener>()
export function onAuthError(fn: Listener) {
  authListeners.add(fn)
  return () => { authListeners.delete(fn) }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') headers['x-lk-request'] = '1'
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(url, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз')
  }
  const text = await res.text()
  let data: Record<string, unknown> = {}
  try { data = text ? JSON.parse(text) : {} } catch { data = {} }
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : res.status >= 500 ? 'Сервер временно недоступен. Попробуйте через минуту' : 'Не удалось выполнить запрос'
    const err = new ApiError(res.status, msg, data)
    const sessionGone = res.status === 401 && (!err.code || err.code === 'login_required' || err.code === 'session_revoked')
    const challenged = res.status === 403 && err.code === 'reauth_required' && !!data.challenge
    if (sessionGone || challenged) authListeners.forEach((fn) => fn(err))
    throw err
  }
  return data as T
}

export const api = {
  get: <T,>(url: string) => request<T>('GET', url),
  post: <T,>(url: string, body?: unknown) => request<T>('POST', url, body ?? {}),
  put: <T,>(url: string, body?: unknown) => request<T>('PUT', url, body ?? {}),
  del: <T,>(url: string) => request<T>('DELETE', url),
}
