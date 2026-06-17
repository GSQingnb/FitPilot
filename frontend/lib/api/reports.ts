import { apiFetch } from "./client"

export interface WeeklyReport {
  id: string
  user_id: string
  period_start: string
  period_end: string
  status: string
  source: string
  model_name: string | null
  metrics: Record<string, unknown>
  summary: string
  highlights: string[]
  issues: string[]
  recommendations: string[]
  created_at: string
  updated_at: string
}

export interface ReportListResponse {
  total: number
  limit: number
  offset: number
  items: WeeklyReport[]
}

export async function generateReport(userId: string, periodStart?: string, periodEnd?: string, force = false): Promise<WeeklyReport> {
  return apiFetch<WeeklyReport>(`/users/${userId}/weekly-reports/generate`, {
    method: "POST",
    body: JSON.stringify({
      period_start: periodStart || null,
      period_end: periodEnd || null,
      force,
    }),
  })
}

export async function listReports(userId: string, limit = 20, offset = 0): Promise<ReportListResponse> {
  return apiFetch<ReportListResponse>(`/users/${userId}/weekly-reports?limit=${limit}&offset=${offset}`)
}

export async function getReport(userId: string, reportId: string): Promise<WeeklyReport> {
  return apiFetch<WeeklyReport>(`/users/${userId}/weekly-reports/${reportId}`)
}
