// Офлайн-оболочка: интерфейс открывается без сети, а расписание и главная показывают последнюю загруженную версию.
// Персональные данные кэшируются только на этом устройстве и удаляются при выходе.
const SHELL = 'shell-v1'
const DATA = 'data-v1'
const OFFLINE_API = ['/api/me', '/api/dashboard', '/api/schedule', '/api/session', '/api/grades']

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
    e.respondWith(fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(DATA).then((c) => c.put(e.request, copy)) }
      if (res.status === 401) caches.delete(DATA)
      return res
    }).catch(() => caches.match(e.request).then((r) => r || Response.json({ detail: 'Нет сети — показать нечего' }, { status: 503 }))))
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
