import type { ReqStatus } from '../../lib/types'
export interface StaffReq {
  id: string; number: string; title: string; category: string; status: ReqStatus; status_text: string; status_comment: string; delivery: 'electronic' | 'paper'
  created_at: string; updated_at: string; due_on: string | null; student: { name: string; group: string; course: number; faculty: string }
  next: ReqStatus[]; overdue: boolean
  payload?: { label: string; value: string }[]
  events?: { at: string; status: ReqStatus | null; status_text: string | null; message: string; author: string; author_name: string }[]
  document?: { number: string; verify: string } | null
}
export const NEXT_LABEL: Record<string, string> = { accepted: 'Принять', in_progress: 'В работу', ready: 'Готово', done: 'Выдано / закрыть', rejected: 'Отклонить' }
