const TZ = 'Europe/Moscow'
const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
const WD = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']
const WD_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

function parts(d: Date) {
  const f = new Intl.DateTimeFormat('ru-RU', { timeZone: TZ, year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' })
  const o: Record<string, string> = {}
  for (const p of f.formatToParts(d)) o[p.type] = p.value
  return { y: +o.year, m: +o.month, d: +o.day, hh: o.hour === '24' ? '00' : o.hour, mm: o.minute }
}

export function toDate(v: string | Date) { return typeof v === 'string' ? new Date(v.length === 10 ? v + 'T12:00:00+03:00' : v) : v }

/** «22 ноября» или «22 ноября 2025», если год не текущий */
export function dayMonth(v: string | Date, withYear = false) {
  const p = parts(toDate(v))
  const now = parts(new Date())
  return `${p.d} ${MONTHS[p.m - 1]}${withYear || p.y !== now.y ? ' ' + p.y : ''}`
}
export function time(v: string | Date) { const p = parts(toDate(v)); return `${p.hh}:${p.mm}` }
export function dateTime(v: string | Date) { return `${dayMonth(v)}, ${time(v)}` }
export function weekday(v: string | Date) { return WD[toDate(v).getDay()] }
export function weekdayShort(v: string | Date) { return WD_SHORT[toDate(v).getDay()] }
export function isoDay(d: Date) {
  const p = parts(d)
  return `${p.y}-${String(p.m).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`
}
export function addDays(iso: string, n: number) {
  const d = new Date(iso + 'T12:00:00+03:00')
  d.setUTCDate(d.getUTCDate() + n)
  return isoDay(d)
}
export function mondayOf(iso: string) {
  const d = new Date(iso + 'T12:00:00+03:00')
  const wd = (d.getUTCDay() + 6) % 7
  return addDays(iso, -wd)
}

/** «сегодня, 14:00», «вчера», «3 дня назад», иначе дата */
export function relative(v: string | Date) {
  const d = toDate(v)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'только что'
  if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`
  const today = isoDay(new Date())
  const day = isoDay(d)
  if (day === today) return `сегодня, ${time(d)}`
  if (day === addDays(today, -1)) return `вчера, ${time(d)}`
  return dateTime(d)
}

/** через сколько дней дедлайн: «сегодня», «завтра», «через 5 дней» */
export function until(v: string | Date) {
  const days = Math.round((new Date(isoDay(toDate(v)) + 'T12:00:00+03:00').getTime() - new Date(isoDay(new Date()) + 'T12:00:00+03:00').getTime()) / 86400000)
  if (days < 0) return 'прошёл'
  if (days === 0) return 'сегодня'
  if (days === 1) return 'завтра'
  return `через ${days} ${plural(days, 'день', 'дня', 'дней')}`
}
export function daysUntil(v: string | Date) {
  return Math.round((new Date(isoDay(toDate(v)) + 'T12:00:00+03:00').getTime() - new Date(isoDay(new Date()) + 'T12:00:00+03:00').getTime()) / 86400000)
}

export function plural(n: number, one: string, few: string, many: string) {
  const a = Math.abs(n) % 100, b = a % 10
  if (a > 10 && a < 20) return many
  if (b > 1 && b < 5) return few
  if (b === 1) return one
  return many
}

export function pct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined) return '—'
  const r = Math.round(v * 10 ** digits) / 10 ** digits
  return r.toLocaleString('ru-RU', { maximumFractionDigits: digits })
}

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]).join('').toUpperCase()
}
