export type Role = 'student' | 'staff'
export interface Me {
  login: string; role: Role; demo: boolean; totp_enabled: boolean; sudo_until: string | null; session_id: string; unread: number
  short: string; name?: { last: string; first: string; middle: string }; faculty?: string; group?: string; course?: number
  position?: string; faculties?: string[]
}
export interface LessonChange { title: string; text: string; reason: string; at: string; prev: { date: string; start: string; room: string | null } | null }
export interface Lesson {
  id: string; discipline: string; kind: string; kind_text: string; date: string; start: string; end: string; pair: number | null
  teacher: string; room: string; building: string; online_url: string; status: 'ok' | 'moved' | 'cancelled'; groups: string[]; change: LessonChange | null
}
export interface Deadline { id: string; title: string; details: string; due_at: string; kind: 'study' | 'admin' | 'payment' }
export type ReqStatus = 'submitted' | 'accepted' | 'in_progress' | 'ready' | 'done' | 'rejected' | 'cancelled'
export interface RequestItem {
  id: string; number: string; type: string; title: string; category: string; status: ReqStatus; status_text: string; status_comment: string
  delivery: 'electronic' | 'paper'; created_at: string; updated_at: string; due_on: string | null; can_cancel: boolean
  document: { number: string; issued_at: string; valid_until: string } | null
  payload?: { label: string; value: string }[]
  events?: { at: string; status: ReqStatus | null; status_text: string | null; message: string; author: 'student' | 'staff' | 'system'; author_name: string }[]
}
export interface Field { name: string; label: string; type: 'text' | 'textarea' | 'select' | 'date' | 'number'; required?: boolean; options?: string[]; max?: number; hint?: string }
export interface RequestType { code: string; title: string; category: 'certificate' | 'statement' | 'question'; description: string; days: number; fields: Field[]; electronic: boolean }
export interface Notification { id: string; kind: string; title: string; body: string; link: string | null; important: boolean; created_at: string; read: boolean }
export interface Grade { percent: number; letter: string; five: number; word: string }
export interface Discipline {
  discipline: string; teacher: string; control: 'exam' | 'zachet'; control_text: string
  b1: number | null; b1_slices: number; b1_final: boolean; bonus: number; slices: (number | null)[]
  b2: number | null; exam_raw: number | null; b3: number | null; retakes: number; auto_zachet: boolean; zachet_cap: boolean
  final: number | null; final_grade: Grade | null; b1_grade: Grade | null
  needs: { assumed_social: number; social_assumed: boolean; items: { target: number; need: number | null; auto: boolean; reachable: boolean }[] } | null
}
export interface Grades {
  semesters: { code: string; title: string; current: boolean }[]
  semester: { code: string; title: string; current: boolean }
  summary: { complete: boolean; rating: number | null; grade: Grade | null; estimate: number | null; estimate_grade: Grade | null; bonus: number; disciplines: number; closed: number }
  disciplines: Discipline[]
  history: { code: string; title: string; rating: number; grade: Grade; bonus: number }[]
  attention: { discipline: string; b1: number; control: string; text: string }[]
  scale: { from: number; letter: string; five: number; word: string }[]
  weights: { b1: number; b2: number; b3: number }
  discount?: { average: number; semesters: number; of: number; discount: number; blocked_by_retake: boolean; gap_to_30: number | null } | null
}
export interface Dashboard {
  today: { date: string; weekday: string; human: string; week: number | null; parity: string | null; lessons: Lesson[] }
  next: Lesson | null; changes: Lesson[]; deadlines: Deadline[]
  requests: { id: string; number: string; title: string; status: ReqStatus; status_text: string; updated_at: string }[]
  notifications: { id: string; kind: string; title: string; body: string; important: boolean; created_at: string }[]
  rating: { semester: string; estimate: number | null; estimate_grade: Grade | null; previous: { title: string; rating: number; grade: Grade } | null; attention: Grades['attention'] }
  session: { from: string; to: string; days_left: number }
}
export interface ScheduleDay { date: string; weekday: string; human: string; week: number | null; parity: string | null; lessons: Lesson[] }
export interface Schedule { from: string; days: ScheduleDay[]; pairs: { n: number; start: string; end: string }[]; today: string; semester: { title: string; starts_on: string; ends_on: string } }
export interface SessionView { id: string; current: boolean; label: string; browser: string; os: string; mobile: boolean; ip: string; created_at: string; last_active_at: string; challenge: boolean }
