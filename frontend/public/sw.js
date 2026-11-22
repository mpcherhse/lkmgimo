// Офлайн-оболочка: интерфейс открывается без сети, а расписание и главная показывают последнюю загруженную версию.
// Персональные данные кэшируются только на этом устройстве, не дольше 12 часов, и удаляются при выходе.
const SHELL = 'shell-v1'
const DATA = 'data-v2'
const OFFLINE_API = ['/api/me', '/api/dashboard', '/api/schedule', '/api/session', '/api/grades']

// Копия без сети живёт не дольше MAX_AGE: если сеанс завершили с другого устройства, потерянный телефон
// без сети не покажет кабинет дольше этого срока. Ответы, запрошенные до выхода, после выхода в кэш не попадают.
const MAX_AGE = 12 * 3600 * 1000
let loggedOutAt = 0

async function store(req, res, started) {
  if (started <= loggedOutAt) return
  const body = await res.blob()
  const headers = new Headers(res.headers)
  headers.set('x-sw-saved', String(Date.now()))
  if (started <= loggedOutAt) return
  await (await caches.open(DATA)).put(req, new Response(body, { status: res.status, headers }))
}
async function fresh(req) {
  const hit = await caches.match(req, { cacheName: DATA })
  if (!hit) return null
  const saved = Number(hit.headers.get('x-sw-saved') || 0)
  if (Date.now() - saved > MAX_AGE) { await (await caches.open(DATA)).delete(req); return null }
  return hit
}
self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'logout') { loggedOutAt = Date.now(); e.waitUntil(caches.delete(DATA)) }
})

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/', '/icon.svg', '/manifest.webmanifest'])).then(() => self.skipWaiting()))
})
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))).then(() => self.clients.claim()))
})
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.origin !== location.origin) return
  if (url.pathname.startsWith('/api/')) {
    if (!OFFLINE_API.some((p) => url.pathname === p)) return
    const started = Date.now()
    e.respondWith(fetch(e.request).then((res) => {
      if (res.ok) e.waitUntil(store(e.request, res.clone(), started))
      if (res.status === 401) e.waitUntil(caches.delete(DATA))
      return res
    }).catch(() => fresh(e.request).then((r) => r || Response.json({ detail: 'Нет сети — показать нечего' }, { status: 503 }))))
    return
  }
  if (url.pathname.startsWith('/cal/') || url.pathname.startsWith('/dav/')) return
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/')))
    return
  }
  if (url.pathname.startsWith('/assets/')) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)) }
      return res
    })))
  }
})
